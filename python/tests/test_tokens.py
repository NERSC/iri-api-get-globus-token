import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import globus_sdk
import requests

from nersc_tokens import _backend as backend
from nersc_tokens import auth, cli


def oauth_response(data):
    """Construct a real SDK response with the wire-format expires_in field."""
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(data).encode()
    response.headers["Content-Type"] = "application/json"
    return globus_sdk.OAuthTokenResponse(
        response, globus_sdk.NativeAppAuthClient(backend.DEFAULT_CLIENT_ID)
    )


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "private" / "tokens.json"
        self.data = {"other_tokens": [{
            "scope": backend.NERSC_IRI_SCOPE, "access_token": "cached",
            "refresh_token": "refresh", "expires_at_seconds": time.time() + 3600,
        }, {"scope": "unrelated", "access_token": "preserved"}]}
        backend.save_tokens(self.path, self.data)

    def test_cached_token_and_clean_stdout(self):
        output = io.StringIO()
        with patch.object(backend, "refresh_tokens_with_client_ids") as refresh:
            with contextlib.redirect_stdout(output):
                result = cli.main(["get-token", "iri", "--token-file", str(self.path)])
            refresh.assert_not_called()
        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), "cached\n")

    def test_refresh_preserves_other_tokens_and_refresh_token(self):
        refreshed = {"scope": backend.NERSC_IRI_SCOPE, "access_token": "new",
                     "resource_server": "nersc-iri", "expires_in": 3600,
                     "token_type": "Bearer", "other_tokens": []}
        response = oauth_response(refreshed)
        client = Mock()
        client.oauth2_refresh_token.return_value = response
        with patch.object(globus_sdk, "NativeAppAuthClient", return_value=client):
            self.assertEqual(auth.get_access_token("iri", token_file=self.path, force_refresh=True), "new")
        data = json.loads(self.path.read_text())
        self.assertEqual(data["other_tokens"][1], self.data["other_tokens"][1])
        self.assertEqual(data["other_tokens"][0]["refresh_token"], "refresh")
        self.assertGreater(data["other_tokens"][0]["expires_at_seconds"], time.time())
        self.assertNotIn("expires_at_seconds", response.data)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_expired_token_refresh_failure_is_not_returned(self):
        self.data["other_tokens"][0]["expires_at_seconds"] = 1
        backend.save_tokens(self.path, self.data)
        with patch.object(backend, "refresh_tokens_with_client_ids", return_value=(None, None)):
            with self.assertRaises(auth.AuthError):
                auth.get_access_token("iri", token_file=self.path)

    def test_missing_credentials_never_login(self):
        with patch.object(backend, "interactive_login") as login:
            with self.assertRaises(auth.AuthError):
                auth.get_access_token("iri", token_file=self.path.with_name("missing"))
            login.assert_not_called()

    def test_invalid_refresh_scope_not_saved(self):
        with patch.object(backend, "refresh_tokens_with_client_ids", return_value=({"scope": "other", "access_token": "bad"}, "id")):
            with self.assertRaises(auth.AuthError):
                auth.get_access_token("iri", token_file=self.path, force_refresh=True)
        self.assertEqual(json.loads(self.path.read_text()), self.data)

    def test_test_token_json_and_failure_status(self):
        for failure in (False, True):
            output = io.StringIO()
            with patch.object(backend, "validate_iri_token", side_effect=RuntimeError("bad") if failure else None):
                with contextlib.redirect_stdout(output):
                    result = cli.main(["test-token", "iri", "--token-file", str(self.path)])
            self.assertEqual(json.loads(output.getvalue())["ready"], not failure)
            self.assertEqual(result, int(failure))

    def test_clear_does_not_remove_other_file(self):
        other = self.path.with_name("other.json")
        other.write_text("{}")
        self.assertTrue(auth.clear_tokens(token_file=self.path))
        self.assertFalse(auth.clear_tokens(token_file=self.path))
        self.assertTrue(other.exists())

    def test_multi_facility_output(self):
        output = io.StringIO()
        with patch.object(auth, "get_access_token", side_effect=["nersc-token", "alcf-token"]):
            with contextlib.redirect_stdout(output):
                result = cli.main(["get-token", "iri", "--facilities", "nersc", "alcf"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), {"nersc": "nersc-token", "alcf": "alcf-token"})

    def test_refresh_command_forces_refresh_without_login(self):
        with patch.object(auth, "get_access_token", return_value="new") as get:
            with patch.object(auth, "login") as login:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.main(["refresh-token", "iri", "--facilities", "alcf"]), 0)
                login.assert_not_called()
                self.assertTrue(get.call_args.kwargs["force_refresh"])
                self.assertEqual(get.call_args.kwargs["facility"], "alcf")

    def test_force_login_prompt_options(self):
        for option, expected in [(None, True), ("--no-prompt-login", False), ("--prompt-login", True)]:
            args = ["get-token", "iri", "--force-login", "--facilities", "nersc", "alcf"]
            if option:
                args.append(option)
            with patch.object(auth, "login") as login:
                with patch.object(auth, "get_access_token", return_value="token"):
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(cli.main(args), 0)
                self.assertEqual(login.call_args.kwargs["prompt_login"], expected)
                self.assertEqual(login.call_args.kwargs["facilities"], ["nersc", "alcf"])

    def test_alcf_refresh_uses_alcf_scope(self):
        self.data["other_tokens"].append({"scope": backend.ALCF_IRI_SCOPE, "refresh_token": "alcf-refresh"})
        backend.save_tokens(self.path, self.data)
        refreshed = {"scope": backend.ALCF_IRI_SCOPE, "access_token": "alcf-new", "expires_at_seconds": time.time() + 3600}
        with patch.object(backend, "refresh_tokens_with_client_ids", return_value=(refreshed, "id")) as refresh:
            self.assertEqual(auth.get_access_token("iri", token_file=self.path, facility="alcf"), "alcf-new")
            self.assertEqual(refresh.call_args.args[0], "alcf-refresh")
            self.assertEqual(refresh.call_args.args[1][0], backend.ALCF_CLIENT_ID)
        self.assertEqual(json.loads(self.path.read_text())["other_tokens"][0]["access_token"], "cached")

    def test_login_preserves_unselected_facility(self):
        response = oauth_response({
            "resource_server": backend.RESOURCE_SERVER,
            "scope": " ".join(backend.REQUIRED_SCOPES), "access_token": "auth",
            "expires_in": 3600, "token_type": "Bearer",
            "other_tokens": [{"scope": backend.ALCF_IRI_SCOPE, "access_token": "alcf",
                              "resource_server": "alcf-iri", "expires_in": 3600,
                              "token_type": "Bearer"}],
        })
        client = Mock()
        client.oauth2_exchange_code_for_tokens.return_value = response
        with patch.object(globus_sdk, "NativeAppAuthClient", return_value=client):
            with patch("builtins.input", return_value="code"), contextlib.redirect_stderr(io.StringIO()):
                auth.login("iri", token_file=self.path, facilities=["alcf"])
        saved = json.loads(self.path.read_text())
        self.assertEqual(backend.get_facility_token(saved, "nersc")["access_token"], "cached")
        self.assertGreater(saved["expires_at_seconds"], time.time())
        self.assertNotIn("expires_at_seconds", response.data["other_tokens"][0])
        with patch.object(backend, "refresh_tokens_with_client_ids") as refresh:
            self.assertEqual(auth.get_access_token("iri", token_file=self.path, facility="alcf"), "alcf")
            refresh.assert_not_called()

    def test_validation_timeout_returns_failure_status(self):
        output = io.StringIO()
        with patch.object(backend.urllib.request, "urlopen", side_effect=TimeoutError) as request:
            with contextlib.redirect_stdout(output):
                result = cli.main(["test-token", "iri", "--token-file", str(self.path)])
        self.assertEqual(result, 1)
        self.assertFalse(json.loads(output.getvalue())["ready"])
        self.assertEqual(request.call_args.kwargs["timeout"], 30)


if __name__ == "__main__":
    unittest.main()
