"""ALCF-style subcommands for IRI tokens."""

import argparse
import json
import sys
from pathlib import Path

from globus_sdk.exc import GlobusAPIError, GlobusConnectionError

from . import _backend as backend
from . import auth


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage NERSC and ALCF IRI Globus tokens.")
    commands = parser.add_subparsers(dest="action")
    for action, description in {
        "login": "Authenticate with Globus.",
        "get-token": "Print access tokens, refreshing when needed.",
        "refresh-token": "Refresh saved facility tokens without interactive login.",
        "test-token": "Test whether facility IRI APIs accept the tokens.",
        "list-services": "List supported services.",
        "clear-tokens": "Remove this application's saved tokens.",
    }.items():
        command = commands.add_parser(action, help=description, description=description)
        if action in ("login", "get-token", "refresh-token", "test-token"):
            command.add_argument("service", choices=auth.SERVICES,
                                 nargs="?" if action == "login" else None)
            command.add_argument("--facilities", nargs="+", choices=backend.FACILITY_SCOPE_MAP,
                                 default=["nersc"], help="Facilities to manage (default: nersc).")
        if action != "list-services":
            command.add_argument("--token-file", type=Path, help="Override the token file.")
        if action in ("login", "get-token", "test-token"):
            command.add_argument("--force-login", action="store_true", help="Force a new interactive login; implies prompt=login.")
            prompts = command.add_mutually_exclusive_group()
            prompts.add_argument("--prompt-login", action="store_true", help="Force identity-provider re-authentication.")
            prompts.add_argument("--no-prompt-login", action="store_true", help="Allow reuse of an existing browser login session.")
        if action == "get-token":
            command.add_argument("--refresh", action="store_true", help="Force refresh (alias for refresh-token).")
        if action == "test-token":
            command.add_argument("--alcf-validate-path", help="ALCF home path; default: /home/$USER/.")
            command.add_argument("--alcf-validate-resource-id", default=backend.ALCF_HOME_RESOURCE_ID)
            command.add_argument("--iri-validate-url", help="Override the validation endpoint for one facility.")
    args = parser.parse_args(argv)
    if args.action is None:
        parser.print_help()
        return 0
    if args.action in ("get-token", "test-token"):
        if (args.prompt_login or args.no_prompt_login) and not args.force_login:
            parser.error("Login prompt options require --force-login for this command.")
        if getattr(args, "refresh", False) and args.force_login:
            parser.error("Choose only one of --refresh or --force-login.")
    facilities = list(dict.fromkeys(getattr(args, "facilities", ["nersc"])))
    if getattr(args, "iri_validate_url", None) and len(facilities) != 1:
        parser.error("--iri-validate-url requires exactly one facility.")
    try:
        if args.action == "list-services":
            print(json.dumps([{"service_name": name, **config, "facilities": list(backend.FACILITY_SCOPE_MAP)}
                              for name, config in auth.SERVICES.items()], indent=2))
        elif args.action == "clear-tokens":
            removed = auth.clear_tokens(token_file=args.token_file)
            print("Tokens removed." if removed else "No tokens found.")
        else:
            if args.action == "login" or getattr(args, "force_login", False):
                prompt = args.prompt_login or (args.force_login and not args.no_prompt_login)
                auth.login(args.service, token_file=args.token_file, facilities=facilities, prompt_login=prompt)
                print("Login successful.", file=sys.stderr)
            if args.action != "login":
                tokens = {facility: auth.get_access_token(
                    args.service, token_file=args.token_file, facility=facility,
                    force_refresh=args.action == "refresh-token" or getattr(args, "refresh", False),
                ) for facility in facilities}
                if args.action in ("get-token", "refresh-token"):
                    print(next(iter(tokens.values())) if len(tokens) == 1 else json.dumps(tokens))
                else:
                    for facility, token in tokens.items():
                        backend.validate_iri_token({"access_token": token}, backend.get_validate_url(args, facility))
                    print(json.dumps({"ready": True, "error": None}))
    except (auth.AuthError, RuntimeError, OSError, ValueError,
            GlobusAPIError, GlobusConnectionError):
        # Avoid exposing SDK exception/request data, tokens, or API response bodies.
        message = "Operation failed. Check connectivity and run 'nersc-tokens login iri' with the same --facilities."
        if args.action == "test-token":
            print(json.dumps({"ready": False, "error": message}))
        else:
            print(message, file=sys.stderr)
        return 1
    return 0
