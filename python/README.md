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
# From the repository root:
python -m pip install ./python
# From the python/ package directory:
python -m pip install .
```

Package dependencies are declared in `pyproject.toml`; `requirements.txt` is
provided at the repository root for users of the original script.

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
ALCF may require an ALCF-primary Globus identity; see the
[repository troubleshooting guide](https://github.com/NERSC/iri-api-get-globus-token#common-troubleshooting).
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

Run these commands from the `python/` package directory:

```bash
python -m pip install -e . build
python -m unittest discover -s tests -v
python -m build
```
