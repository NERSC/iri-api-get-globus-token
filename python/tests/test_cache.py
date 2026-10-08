import contextlib
import io
import json
import multiprocessing
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from nersc_tokens import _backend as backend
from nersc_tokens import auth, cli


def refresh_in_process(path, facility, started, entered, release, results):
    """Exercise the public API with independent processes sharing one cache."""
    def refresh(*args, **kwargs):
        entered.set()
        if release is not None and not release.wait(10):
            raise RuntimeError("Test refresh was not released")
        return ({"scope": backend.FACILITY_SCOPE_MAP[facility]["scope"],
                 "access_token": facility + "-new",
                 "refresh_token": facility + "-rotated",
                 "expires_at_seconds": time.time() + 3600}, "client")

    started.set()
    try:
        with patch.object(backend, "refresh_tokens_with_client_ids", side_effect=refresh):
            results.put(auth.get_access_token("iri", token_file=path,
                                              facility=facility, force_refresh=True))
    except Exception as exc:
        results.put(type(exc).__name__)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "private" / "tokens.json"
        self.data = {"other_tokens": [
            {"scope": backend.FACILITY_SCOPE_MAP[facility]["scope"],
             "access_token": facility + "-old", "refresh_token": facility + "-refresh",
             "expires_at_seconds": 1}
            for facility in ("nersc", "alcf")
        ]}
        backend.save_tokens(self.path, self.data)

    def test_overlapping_atomic_writes_use_private_unique_files(self):
        replace = os.replace
        temporary_files = []

        def overlapping_replace(source, target):
            temporary_files.append(source)
            self.assertEqual(source.stat().st_mode & 0o777, 0o600)
            if len(temporary_files) == 1:
                backend.save_tokens(self.path, {"other_tokens": []})
            replace(source, target)

        with patch.object(backend.os, "replace", side_effect=overlapping_replace):
            backend.save_tokens(self.path, self.data)
        self.assertEqual(len(set(temporary_files)), 2)
        self.assertEqual(json.loads(self.path.read_text()), self.data)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_failed_write_preserves_cache_and_removes_temporary_file(self):
        with patch.object(backend.json, "dump", side_effect=TypeError("invalid data")):
            with self.assertRaises(TypeError):
                backend.save_tokens(self.path, {})
        self.assertEqual(json.loads(self.path.read_text()), self.data)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_concurrent_facility_refreshes_preserve_both_rotated_credentials(self):
        ctx = multiprocessing.get_context("spawn")
        first_started, first_entered, release_first = ctx.Event(), ctx.Event(), ctx.Event()
        second_started, second_entered = ctx.Event(), ctx.Event()
        results = ctx.Queue()
        first = ctx.Process(target=refresh_in_process, args=(
            self.path, "nersc", first_started, first_entered, release_first, results))
        second = ctx.Process(target=refresh_in_process, args=(
            self.path, "alcf", second_started, second_entered, None, results))
        first.start()
        try:
            self.assertTrue(first_entered.wait(10))
            second.start()
            self.assertTrue(second_started.wait(10))
            self.assertFalse(second_entered.wait(0.5), "A second refresh bypassed the cache lock")
            release_first.set()
            first.join(10)
            second.join(10)
            self.assertEqual(first.exitcode, 0)
            self.assertEqual(second.exitcode, 0)
            self.assertEqual({results.get(timeout=1), results.get(timeout=1)},
                             {"nersc-new", "alcf-new"})
            saved = auth.read_tokens(self.path)
            for facility in ("nersc", "alcf"):
                token = backend.get_facility_token(saved, facility)
                self.assertEqual(token["access_token"], facility + "-new")
                self.assertEqual(token["refresh_token"], facility + "-rotated")
        finally:
            release_first.set()
            for process in (first, second):
                if process.pid is not None:
                    process.join(2)
                    if process.is_alive():
                        process.terminate()
                        process.join(2)
            results.close()
            results.join_thread()

    def test_non_string_scopes_fail_cleanly_and_fresh_login_recovers(self):
        fresh = {"resource_server": backend.RESOURCE_SERVER,
                 "scope": " ".join(backend.REQUIRED_SCOPES),
                 "other_tokens": [{"scope": backend.NERSC_IRI_SCOPE,
                                   "access_token": "new", "expires_at_seconds": time.time() + 3600}]}
        for scope in (None, 42, ["invalid"], {"invalid": True}):
            for top_level in (False, True):
                with self.subTest(scope=scope, top_level=top_level):
                    malformed = {"other_tokens": [{"scope": "unrelated"}]}
                    entry = malformed if top_level else malformed["other_tokens"][0]
                    entry["scope"] = scope
                    backend.save_tokens(self.path, malformed)
                    with self.assertRaises(auth.AuthError):
                        auth.read_tokens(self.path)
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(cli.main(["get-token", "iri", "--token-file", str(self.path)]), 1)
                    with patch.object(backend, "interactive_login", return_value=json.loads(json.dumps(fresh))):
                        auth.login("iri", token_file=self.path)
                    self.assertEqual(auth.get_access_token("iri", token_file=self.path), "new")


if __name__ == "__main__":
    unittest.main()
