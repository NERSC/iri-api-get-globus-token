# NERSC Tokens

`nersc-tokens` is a pip-installable CLI for NERSC IRI API tokens, with the
same core subcommands as `alcf-tokens`, plus explicit token refresh. It supports
NERSC and ALCF through `--facilities`, defaulting to NERSC. Requires Python 3.10
or newer. The existing facility scopes and Globus client IDs are reused.

## Install

Install from PyPI:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install nersc-tokens
```

Or install from a checkout:

```bash
python -m pip install ./python
```

Package dependencies are declared in `python/pyproject.toml`; `requirements.txt` is
also provided for users of the original script.

## Commands

```bash
nersc-tokens --help
nersc-tokens list-services
nersc-tokens login            # currently authorizes the single supported service
nersc-tokens login iri
nersc-tokens get-token iri
nersc-tokens refresh-token iri
nersc-tokens test-token iri
nersc-tokens clear-tokens
```

For login, open the displayed Globus URL, authenticate with your NERSC account,
grant consent, and paste the authorization code into the terminal.
Use `--force-login` with `login`, `get-token`, or `test-token` to force a new
browser authorization with `prompt=login`. `--prompt-login` explicitly requests
identity-provider re-authentication; `--no-prompt-login` permits reuse of the
browser session. For retrieval or testing, prompt options require `--force-login`.
`login` always starts a new authorization flow, with a fresh identity-provider
prompt only when requested by these options.
`get-token` prints only the access token to stdout, so shell usage is:

```bash
export IRI_TOKEN_NERSC="$(nersc-tokens get-token iri)"
```

`test-token` checks the NERSC account/projects endpoint and prints
`{"ready": true, "error": null}` on success; failures return exit status 1.
`python -m nersc_tokens` exposes the same CLI.

## Multiple facilities

```bash
nersc-tokens login iri --facilities nersc alcf --force-login
nersc-tokens get-token iri --facilities alcf
nersc-tokens get-token iri --facilities nersc alcf
nersc-tokens refresh-token iri --facilities nersc alcf
nersc-tokens test-token iri --facilities alcf --alcf-validate-path /home/<username>/
```

Single-facility retrieval prints a bare access token; multiple facilities print
a JSON object keyed by facility (`nersc` and `alcf`). Login and refresh preserve
unselected facility tokens. ALCF selection uses its specific Globus client ID.
ALCF may require an ALCF-primary Globus identity; see troubleshooting below.
`test-token` also accepts `--alcf-validate-resource-id` and, for one facility,
`--iri-validate-url` as in the original script.

## Refresh and storage

Access and refresh tokens are stored in `~/.globus/nersc_tokens/tokens.json`
with private file permissions. This separate location avoids overwriting the
original script's combined NERSC/ALCF credentials. `clear-tokens` removes only
this application's token file, without revoking tokens at Globus.
Concurrent commands serialize cache updates so refreshing one facility preserves
the other facility's latest credentials. An adjacent `.lock` file coordinates
access and remains after `clear-tokens`; it contains no tokens.

`get-token` returns a cached token until it is within 60 seconds of expiry,
then uses its refresh token to obtain a new access token. Force a refresh with:

```bash
nersc-tokens get-token iri --refresh
nersc-tokens refresh-token iri
export IRI_TOKEN_NERSC="$(nersc-tokens get-token iri)"
```

If tokens are missing or refresh fails, run `nersc-tokens login iri` again.
Token retrieval opens an interactive login only with explicit `--force-login`;
`refresh-token` never opens a browser and fails if refresh is unavailable.
Refresh tokens stay in the
token file; `IRI_TOKEN_NERSC` should contain the access token.
To explicitly use the original script's saved credentials, pass
`--token-file ~/.globus/auth_tokens.json` to the relevant subcommand.

Python callers can obtain tokens without interactive login:

```python
from nersc_tokens.auth import AuthError, get_access_token

token = get_access_token("iri")  # refreshes when needed; raises AuthError on failure
alcf_token = get_access_token("iri", facility="alcf")
```

## Development

```bash
python -m pip install -e ./python build
python -m unittest discover -s python/tests -v
python -m build python
```

## Publishing

The release workflow builds from `python/` and publishes to PyPI through GitHub
Trusted Publishing. See [publisher setup and release steps](python/PUBLISHING.md).
PyPI registration is a separate, one-time account setup; the first release creates
the project.

## Original `get_globus_token.py` usage

Run the compatibility script from a full repository checkout. Its implementation
is included in `python/nersc_tokens/_backend.py`.

This document explains how to use:

`get_globus_token.py`

## What it does

- Gets tokens for both the NERSC IRI API and the ALCF IRI API by default.
- Supports `--facilities` to request tokens for only the listed facilities.
- Uses the ALCF-specific Globus client ID `8b84fc2d-49e9-49ea-b54d-b3a29a70cf31` whenever `alcf` is requested.
- Requests a Globus Auth token with these required scopes:
  - `openid`
  - `profile`
  - `email`
  - `urn:globus:auth:scope:auth.globus.org:view_identities`
  - NERSC IRI token: `https://auth.globus.org/scopes/ed3e577d-f7f3-4639-b96e-ff5a8445d699/iri_api`
  - ALCF IRI token: `https://auth.globus.org/scopes/6be511f6-a071-471f-9bc0-02a0d0836723/filesystem`
- Preserves the full token response, including `other_tokens`.
- Extracts the NERSC IRI access token from `other_tokens`.
- Requires tokens for the selected facilities to be present in `other_tokens`.
- Prints both the NERSC IRI access token and the ALCF IRI access token with `--print-token`.
- Can optionally validate selected facility tokens by calling facility IRI endpoints.
- Saves token data to a secure local file by default.
- Reuses and refreshes saved tokens when possible.

## Prerequisites

1. Python 3.10+.
2. Install the script dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

3. For ALCF token acquisition, you must complete the Globus login flow. The ALCF login depends on that Globus authentication step to obtain the ALCF token.

## Default behavior (recommended)

Run:

```bash
python get_globus_token.py
```

What happens:

1. If a refresh token exists in the token file, the script tries to refresh automatically.
2. If refresh is not possible, it starts interactive login and prints a Globus URL to obtain both the NERSC IRI API token and the ALCF IRI API token.
3. If `alcf` is selected, the script uses the ALCF Globus client ID `8b84fc2d-49e9-49ea-b54d-b3a29a70cf31`.
4. ALCF token acquisition requires the Globus login flow; use that login flow before completing the ALCF login/consent sequence.
5. After you authorize, paste the returned auth code in the terminal.
6. Token JSON is saved to:
   - `~/.globus/auth_tokens.json`
7. The NERSC IRI and ALCF IRI access tokens from `other_tokens` are **not** printed by default.

## Select facilities

By default, the script requests tokens for both facilities:

```bash
python get_globus_token.py --facilities nersc alcf
```

You can limit token acquisition to a subset:

```bash
python get_globus_token.py --facilities nersc
python get_globus_token.py --facilities alcf
```

When `alcf` is included, the script switches to the ALCF-specific client ID and the interactive flow must be completed through Globus login to obtain the ALCF token.

ALCF's IRI API may require your ALCF identity to be the primary Globus Auth identity. If you use both NERSC and ALCF and want to request both tokens in one login flow, use a Globus session whose primary identity is your ALCF identity.

Supported facility names are:

- `nersc`
- `alcf`

## Print token to terminal (optional)

```bash
python get_globus_token.py --print-token
```

Use this only when needed, since terminal logs/history may expose tokens.
The printed tokens correspond to the selected facilities. By default that means the NERSC IRI API token and the ALCF IRI API token.

## Force a new interactive login

```bash
python get_globus_token.py --force-login
```

This skips refresh and always performs browser auth. By default, it also adds `prompt=login` to the Globus authorization URL so Globus forces a fresh login instead of silently reusing an existing browser session.

If you need a new authorization flow but want to allow Globus to reuse an existing browser session, pass:

```bash
python get_globus_token.py --force-login --no-prompt-login
```

## Force a fresh IdP login prompt explicitly

```bash
python get_globus_token.py --force-login --prompt-login
```

`--prompt-login` adds `prompt=login` to the Globus authorization URL so Globus forces a fresh login at the identity provider instead of reusing an existing browser session. This is implied by `--force-login`, but the explicit flag is still accepted.
This is useful when the server side shows an empty `session_info.authentications` object or when the IRI API returns `401` with a token that otherwise looks valid.

## Refresh saved tokens only

```bash
python get_globus_token.py --refresh-only
```

This attempts to refresh saved tokens without opening a browser login flow.
It refreshes the top-level Globus Auth token when possible and also refreshes the selected facility tokens from `other_tokens` when their refresh tokens are available.
If only one facility is selected, only that facility token is required to refresh successfully; tokens for other facilities already present in the file are preserved.
The script tries the known Globus client IDs during refresh, so a token file created by the default combined NERSC+ALCF flow can still refresh an existing NERSC token when you run `--facilities nersc`.
If refresh is not possible, or if refresh does not return all requested facility tokens, the script exits with an error instead of starting interactive login.

## Validate an IRI token

```bash
python get_globus_token.py --validate-iri
```

By default, `--validate-iri` validates every selected facility. With the default selected facilities, it validates both NERSC and ALCF.

For NERSC, validation calls:

```bash
GET https://api.iri.nersc.gov/api/v1/account/projects
```

If the response includes `session_info.authentications: {}`, the script treats that as a bad session and exits with guidance to re-run using `--force-login`.

For ALCF, validation calls the filesystem listing endpoint:

```bash
GET https://api.alcf.anl.gov/api/v1/filesystem/ls/6115bd2c-957a-4543-abff-5fae52992ff2?path=/home/<username>/
```

The default ALCF resource ID is Home, and the default path is `/home/$USER/` expanded by the script. Override it if your ALCF username differs from your local username:

```bash
python get_globus_token.py --facilities alcf --validate-iri --alcf-validate-path /home/<alcf-username>/
```

To validate only one facility, select only that facility:

```bash
python get_globus_token.py --facilities alcf --validate-iri
```

`--iri-validate-url` is only valid when one facility is selected with `--facilities`.

You can combine validation with token printing or refresh-only mode:

```bash
python get_globus_token.py --refresh-only --validate-iri --print-token
python get_globus_token.py --force-login --validate-iri
python get_globus_token.py --facilities nersc --validate-iri --print-token
python get_globus_token.py --facilities alcf --refresh-only --validate-iri
python get_globus_token.py --facilities nersc alcf --refresh-only --validate-iri
```

## Use a custom token file path

```bash
python get_globus_token.py --token-file /path/to/auth_tokens.json
```

The script writes with private permissions (`0600`) and sets parent directory permissions to `0700`.

## Common troubleshooting

- `ModuleNotFoundError` for `globus_sdk` or `filelock`
  - Install dependencies: `python -m pip install -r requirements.txt`
- Refresh fails and script asks for login again
  - This is expected when refresh token expired/revoked.
- Refresh-only mode fails
  - Re-run without `--refresh-only` to allow interactive login, or use `--force-login` to start a fresh browser auth flow.
- Authorization code exchange fails with `invalid_grant`
  - Re-run the script and paste a fresh authorization code from Globus. This can happen if the code was empty, expired, or already used.
- `Missing required scopes`
  - Re-run with `--force-login` and ensure consent is granted for requested scopes.
- `Missing token for required NERSC IRI API scope`
  - Re-run with `--force-login` and ensure consent is granted for the NERSC IRI scope.
- `Missing token for required ALCF IRI API scope`
  - Re-run with `--force-login` and ensure consent is granted for the ALCF IRI scope. If `alcf` is selected, the script uses the ALCF-specific client ID `8b84fc2d-49e9-49ea-b54d-b3a29a70cf31`.
- ALCF IRI API rejects a token even though the ALCF scope is present
  - ALCF may require the ALCF identity to be the primary Globus Auth identity. If your Globus account has a NERSC identity as primary and an ALCF identity linked underneath it, the ALCF IRI API may still reject the token.
  - One working recovery path is to unlink the ALCF identity from the Globus account whose primary identity is NERSC, then log in to Globus using the ALCF identity and do not link it back to the NERSC-primary account before requesting the ALCF token.
- IRI API returns `401`
  - Re-run the script with `--force-login` and open the authorization URL in a Chrome incognito window before completing login.
- Server shows `session_info.authentications: {}`
  - Re-run the script with `--force-login` so Globus forces a fresh identity-provider login instead of reusing an existing browser session.
