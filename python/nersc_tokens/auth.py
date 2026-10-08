"""Non-interactive access token retrieval with automatic refresh."""

import contextlib
import sys
import time
from pathlib import Path

import globus_sdk

from . import _backend as backend

SERVICES = {
    "iri": {
        "description": "NERSC and ALCF IRI APIs",
        "documentation_url": "https://api.iri.nersc.gov/docs",
    }
}


class AuthError(RuntimeError):
    """Authentication requires user intervention."""


def token_path(token_file=None):
    return Path(token_file) if token_file is not None else (
        Path.home() / ".globus" / "nersc_tokens" / "tokens.json"
    )


def check_service(service):
    if service not in SERVICES:
        raise AuthError(f"Unknown service '{service}'. Valid values: iri")


def read_tokens(token_file):
    try:
        data = backend.load_tokens(token_path(token_file))
        if data is not None and (not isinstance(data, dict) or not isinstance(data.get("other_tokens", []), list)
                                 or any(not isinstance(item, dict) for item in data.get("other_tokens", []))):
            raise ValueError("Invalid token data")
        return data
    except (OSError, ValueError) as exc:
        raise AuthError("Cannot read token file. Run 'nersc-tokens login iri'.") from exc


def login(service=None, *, token_file=None, facilities=None, prompt_login=True):
    if service is not None:
        check_service(service)
    facilities = facilities or ["nersc"]
    client = globus_sdk.NativeAppAuthClient(backend.get_client_id(facilities))
    with contextlib.redirect_stdout(sys.stderr):
        data = backend.interactive_login(client, facilities, prompt_login=prompt_login)
    backend.validate_auth_data(data, facilities)
    try:
        previous = read_tokens(token_file) or {}
    except AuthError:
        previous = {}  # A fresh login can recover a malformed cache.
    for item in previous.get("other_tokens", []):
        if not any(backend.FACILITY_SCOPE_MAP[f]["scope"] in backend.parse_scope_string(item.get("scope", "")) for f in facilities):
            data.setdefault("other_tokens", []).append(item)
    backend.save_tokens(token_path(token_file), data)


def get_access_token(service, *, token_file=None, force_refresh=False, facility="nersc"):
    check_service(service)
    if facility not in backend.FACILITY_SCOPE_MAP:
        raise AuthError(f"Unknown facility: {facility}")
    scope = backend.FACILITY_SCOPE_MAP[facility]["scope"]
    stored = read_tokens(token_file)
    try:
        data = backend.get_facility_token(stored or {}, facility)
    except (RuntimeError, AttributeError, TypeError) as exc:
        raise AuthError(f"No IRI token stored. Run 'nersc-tokens login iri --facilities {facility}'.") from exc
    expires = data.get("expires_at_seconds", 0)
    if not force_refresh and isinstance(expires, (int, float)) and expires > time.time() + 60:
        if data.get("access_token"):
            return data["access_token"]
    refresh = data.get("refresh_token")
    if not refresh:
        raise AuthError(f"No usable refresh token. Run 'nersc-tokens login iri --facilities {facility}'.")
    with contextlib.redirect_stdout(sys.stderr):
        refreshed, _ = backend.refresh_tokens_with_client_ids(
            refresh, backend.get_refresh_client_ids([facility]), token_label=backend.FACILITY_SCOPE_MAP[facility]["label"]
        )
    if refreshed is None:
        raise AuthError(f"Token refresh failed. Run 'nersc-tokens login iri --facilities {facility}'.")
    # A successful refresh must contain a new token for this service. Never
    # return an expired cached token merely because another token refreshed.
    data = dict(refreshed)
    if scope not in backend.parse_scope_string(data.get("scope", "")):
        raise AuthError(f"Refresh returned no IRI scope. Run 'nersc-tokens login iri --facilities {facility}'.")
    expires = data.get("expires_at_seconds", 0)
    if not data.get("access_token") or not isinstance(expires, (int, float)) or expires <= time.time():
        raise AuthError(f"Refresh returned no access token. Run 'nersc-tokens login iri --facilities {facility}'.")
    data.setdefault("refresh_token", refresh)
    backend.save_tokens(
        token_path(token_file),
        backend.replace_token_for_scope(stored, scope, data),
    )
    return data["access_token"]


def clear_tokens(*, token_file=None):
    path = token_path(token_file)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True
