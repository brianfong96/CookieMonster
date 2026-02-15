from __future__ import annotations

import argparse
import json
import webbrowser
from importlib.metadata import PackageNotFoundError, version
from subprocess import Popen

from .api_server import serve_api
from .browser_profiles import default_user_data_dir, list_profiles
from .capture import capture_requests
from .chrome_discovery import list_page_targets
from .chrome_launcher import launch_browser, wait_for_debug_endpoint
from .config import CaptureConfig, ReplayConfig
from .crypto import resolve_key
from .diffing import compare_capture_files
from .doctor import run_doctor
from .plugins import auto_detect_adapter, get_adapter, list_adapters
from .recipes import Recipe, list_recipes, load_recipe, save_recipe
from .replay import replay_with_capture
from .security_utils import redact_headers
from .session_health import analyze_session_health
from .storage import load_captures


def _tool_version() -> str:
    try:
        return version("cookie-monster-cli")
    except PackageNotFoundError:
        return "0.0.0"


def _emit(payload: dict, output_format: str) -> None:
    if output_format == "ndjson":
        print(json.dumps(payload, separators=(",", ":")))
        return
    print(json.dumps(payload, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cookie-monster",
        description=(
            "Capture auth headers from your own browser DevTools network traffic "
            "and replay requests for automation."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_tool_version()}")
    parser.add_argument("--format", choices=["json", "ndjson"], default="json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture", help="Capture request headers from browser")
    capture_parser.add_argument("--chrome-host", default="127.0.0.1")
    capture_parser.add_argument("--chrome-port", type=int, default=9222)
    capture_parser.add_argument(
        "--browser",
        default="chrome",
        choices=["chrome", "edge"],
        help="Browser to launch when using --launch-browser",
    )
    capture_parser.add_argument("--duration", type=int, default=30)
    capture_parser.add_argument("--max-records", type=int, default=100)
    capture_parser.add_argument("--target-hint", default=None, help="Match target tab/request URLs by substring")
    capture_parser.add_argument("--output", default="captures.jsonl")
    capture_parser.add_argument(
        "--header",
        action="append",
        default=None,
        help="Repeatable header name allowlist (default captures cookie/auth headers)",
    )
    capture_parser.add_argument("--include-all-headers", action="store_true")
    capture_parser.add_argument("--adapter", default=None, choices=list_adapters())
    capture_parser.add_argument("--auto-adapter", action="store_true")
    capture_parser.add_argument("--filter-host", default=None)
    capture_parser.add_argument("--filter-path", default=None)
    capture_parser.add_argument("--filter-method", default=None)
    capture_parser.add_argument("--filter-resource-type", default=None)
    capture_parser.add_argument("--capture-post-data", action="store_true")
    capture_parser.add_argument("--max-post-data-bytes", type=int, default=65536)
    capture_parser.add_argument("--redact-output", action="store_true")
    capture_parser.add_argument("--launch-browser", action="store_true")
    capture_parser.add_argument("--launch-chrome", action="store_true", help="Deprecated alias")
    capture_parser.add_argument("--browser-path", default=None)
    capture_parser.add_argument("--chrome-path", default=None, help="Deprecated alias")
    capture_parser.add_argument("--user-data-dir", default=None)
    capture_parser.add_argument("--profile-directory", default=None)
    capture_parser.add_argument("--open-url", default=None)
    capture_parser.add_argument("--headless", action="store_true")
    capture_parser.add_argument("--keep-open", action="store_true")
    capture_parser.add_argument("--encryption-key", default=None)
    capture_parser.add_argument("--encryption-key-env", default="COOKIE_MONSTER_ENCRYPTION_KEY")

    replay_parser = subparsers.add_parser("replay", help="Replay HTTP request from captured headers")
    replay_parser.add_argument("--capture-file", default="captures.jsonl")
    replay_parser.add_argument("--request-url", required=True)
    replay_parser.add_argument("--method", default="GET")
    replay_parser.add_argument("--url-contains", default=None)
    replay_parser.add_argument("--timeout", type=int, default=20)
    replay_parser.add_argument("--output", default=None)
    replay_parser.add_argument("--data", default=None)
    replay_parser.add_argument("--json-body-file", default=None)
    replay_parser.add_argument("--use-captured-body", action="store_true")
    replay_parser.add_argument("--retry-attempts", type=int, default=1)
    replay_parser.add_argument("--retry-backoff", type=float, default=0.5)
    replay_parser.add_argument("--allowed-domain", action="append", default=None)
    replay_parser.add_argument("--adapter", default=None, choices=list_adapters())
    replay_parser.add_argument("--auto-adapter", action="store_true")
    replay_parser.add_argument("--redact-output", action="store_true")
    replay_parser.add_argument("--no-enforce-capture-host", action="store_true")
    replay_parser.add_argument("--encryption-key", default=None)
    replay_parser.add_argument("--encryption-key-env", default="COOKIE_MONSTER_ENCRYPTION_KEY")

    targets_parser = subparsers.add_parser("list-targets", help="List browser page targets from DevTools")
    targets_parser.add_argument("--chrome-host", default="127.0.0.1")
    targets_parser.add_argument("--chrome-port", type=int, default=9222)

    profiles_parser = subparsers.add_parser("profile-list", help="List local browser profiles")
    profiles_parser.add_argument("--browser", default="chrome", choices=["chrome", "edge"])
    profiles_parser.add_argument("--user-data-dir", default=None)

    doctor_parser = subparsers.add_parser("doctor", help="Run connectivity and environment checks")
    doctor_parser.add_argument("--browser", default="chrome", choices=["chrome", "edge"])
    doctor_parser.add_argument("--chrome-host", default="127.0.0.1")
    doctor_parser.add_argument("--chrome-port", type=int, default=9222)
    doctor_parser.add_argument("--user-data-dir", default=None)

    serve_parser = subparsers.add_parser("serve", help="Run local HTTP API mode")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)
    serve_parser.add_argument("--api-token", default=None)
    serve_parser.add_argument("--api-token-env", default="COOKIE_MONSTER_API_TOKEN")

    ui_parser = subparsers.add_parser("ui", help="Run local UI for encrypted auth cache checks")
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", type=int, default=8787)
    ui_parser.add_argument("--api-token", default=None)
    ui_parser.add_argument("--api-token-env", default="COOKIE_MONSTER_API_TOKEN")
    ui_parser.add_argument("--no-open", action="store_true")

    adapters_parser = subparsers.add_parser("adapter-list", help="List built-in site adapters")
    adapters_parser.add_argument("--verbose", action="store_true")

    health_parser = subparsers.add_parser("session-health", help="Analyze token/session health from capture file")
    health_parser.add_argument("--capture-file", required=True)
    health_parser.add_argument("--encryption-key", default=None)
    health_parser.add_argument("--encryption-key-env", default="COOKIE_MONSTER_ENCRYPTION_KEY")

    diff_parser = subparsers.add_parser("diff-captures", help="Compare two capture files for header/method changes")
    diff_parser.add_argument("--a", required=True, help="First capture file")
    diff_parser.add_argument("--b", required=True, help="Second capture file")
    diff_parser.add_argument("--a-key", default=None)
    diff_parser.add_argument("--b-key", default=None)

    recipe_save_parser = subparsers.add_parser("recipe-save", help="Save a named recipe from CLI options")
    recipe_save_parser.add_argument("--name", required=True)
    recipe_save_parser.add_argument("--capture-file", default="captures.jsonl")
    recipe_save_parser.add_argument("--request-url", required=True)
    recipe_save_parser.add_argument("--target-hint", default=None)
    recipe_save_parser.add_argument("--url-contains", default=None)
    recipe_save_parser.add_argument("--method", default="GET")
    recipe_save_parser.add_argument("--adapter", default=None, choices=list_adapters())
    recipe_save_parser.add_argument("--base-dir", default=None)

    recipe_run_parser = subparsers.add_parser("recipe-run", help="Run capture+replay from named recipe")
    recipe_run_parser.add_argument("--name", required=True)
    recipe_run_parser.add_argument("--base-dir", default=None)
    recipe_run_parser.add_argument("--duration", type=int, default=None)
    recipe_run_parser.add_argument("--max-records", type=int, default=None)

    recipe_list_parser = subparsers.add_parser("recipe-list", help="List saved recipes")
    recipe_list_parser.add_argument("--base-dir", default=None)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    launched_proc: Popen[bytes] | None = None

    if args.command == "capture":
        adapter = None
        if args.adapter:
            adapter = get_adapter(args.adapter)
        elif args.auto_adapter:
            adapter = auto_detect_adapter(args.target_hint or args.open_url or "")
        adapter_defaults = adapter.defaults() if adapter else None
        encryption_key = resolve_key(args.encryption_key, args.encryption_key_env)

        if args.launch_chrome or args.launch_browser:
            launched_proc = launch_browser(
                browser=args.browser,
                browser_path=args.browser_path or args.chrome_path,
                host=args.chrome_host,
                port=args.chrome_port,
                user_data_dir=args.user_data_dir,
                profile_directory=args.profile_directory,
                open_url=args.open_url,
                headless=args.headless,
            )
            wait_for_debug_endpoint(args.chrome_host, args.chrome_port)

        config = CaptureConfig(
            chrome_host=args.chrome_host,
            chrome_port=args.chrome_port,
            duration_seconds=args.duration,
            max_records=args.max_records,
            target_hint=args.target_hint,
            output_file=args.output,
            header_allowlist=args.header or CaptureConfig().header_allowlist,
            include_all_headers=args.include_all_headers,
            filter_host_contains=args.filter_host,
            filter_path_contains=args.filter_path,
            filter_method=args.filter_method,
            filter_resource_type=args.filter_resource_type,
            capture_post_data=args.capture_post_data,
            max_post_data_bytes=args.max_post_data_bytes,
            encryption_key=encryption_key,
        )
        if adapter_defaults:
            if config.target_hint is None:
                config.target_hint = adapter_defaults.target_hint
            if config.filter_host_contains is None:
                config.filter_host_contains = adapter_defaults.filter_host_contains
            if config.filter_path_contains is None:
                config.filter_path_contains = adapter_defaults.filter_path_contains
        try:
            captures = capture_requests(config)
            sample = [c.to_dict() for c in captures[:3]]
            if args.redact_output:
                for item in sample:
                    item["headers"] = redact_headers(dict(item.get("headers", {})))
            _emit(
                {
                    "captured": len(captures),
                    "output": config.output_file,
                    "adapter": adapter.name if adapter else None,
                    "encrypted": bool(encryption_key),
                    "sample": sample,
                },
                args.format,
            )
        finally:
            if launched_proc is not None and not args.keep_open:
                launched_proc.terminate()
        return

    if args.command == "replay":
        adapter = None
        if args.adapter:
            adapter = get_adapter(args.adapter)
        elif args.auto_adapter:
            adapter = auto_detect_adapter(args.request_url)
        adapter_defaults = adapter.defaults() if adapter else None
        allowed_domains = args.allowed_domain or []
        if adapter_defaults:
            for d in adapter_defaults.allowed_domains:
                if d not in allowed_domains:
                    allowed_domains.append(d)
        url_contains = args.url_contains
        if url_contains is None and adapter_defaults:
            url_contains = adapter_defaults.replay_url_contains
        encryption_key = resolve_key(args.encryption_key, args.encryption_key_env)

        config = ReplayConfig(
            capture_file=args.capture_file,
            request_url=args.request_url,
            method=args.method,
            url_contains=url_contains,
            timeout_seconds=args.timeout,
            output_file=args.output,
            body=args.data,
            json_body_file=args.json_body_file,
            use_captured_body=args.use_captured_body,
            retry_attempts=args.retry_attempts,
            retry_backoff_seconds=args.retry_backoff,
            allowed_domains=allowed_domains,
            redact_output=args.redact_output,
            enforce_capture_host=not args.no_enforce_capture_host,
            encryption_key=encryption_key,
        )
        response = replay_with_capture(config)
        _emit(
            {
                    "status_code": response.status_code,
                    "content_type": response.headers.get("Content-Type", ""),
                    "adapter": adapter.name if adapter else None,
                    "body_preview": response.text[:400],
                },
                args.format,
            )
        return

    if args.command == "list-targets":
        targets = list_page_targets(args.chrome_host, args.chrome_port)
        mapped = [
            {
                "id": t.get("id"),
                "title": t.get("title"),
                "url": t.get("url"),
                "type": t.get("type"),
            }
            for t in targets
        ]
        _emit({"targets": mapped, "count": len(mapped)}, args.format)
        return

    if args.command == "profile-list":
        user_data_dir = args.user_data_dir or default_user_data_dir(args.browser)
        if not user_data_dir:
            raise RuntimeError("Could not determine user data dir. Pass --user-data-dir")
        profiles = list_profiles(user_data_dir)
        _emit({"browser": args.browser, "user_data_dir": user_data_dir, "profiles": profiles}, args.format)
        return

    if args.command == "doctor":
        report = run_doctor(args.browser, args.chrome_host, args.chrome_port, args.user_data_dir)
        _emit(report, args.format)
        return

    if args.command == "serve":
        api_token = resolve_key(args.api_token, args.api_token_env)
        serve_api(args.host, args.port, api_token=api_token)
        return

    if args.command == "ui":
        if not args.no_open:
            webbrowser.open(f"http://{args.host}:{args.port}/ui")
        api_token = resolve_key(args.api_token, args.api_token_env)
        serve_api(args.host, args.port, api_token=api_token)
        return

    if args.command == "adapter-list":
        names = list_adapters()
        if not args.verbose:
            _emit({"adapters": names}, args.format)
            return
        detailed = []
        for name in names:
            adapter = get_adapter(name)
            defaults = adapter.defaults()
            detailed.append(
                {
                    "name": name,
                    "target_hint": defaults.target_hint,
                    "filter_host_contains": defaults.filter_host_contains,
                    "allowed_domains": defaults.allowed_domains,
                }
            )
        _emit({"adapters": detailed}, args.format)
        return

    if args.command == "session-health":
        key = resolve_key(args.encryption_key, args.encryption_key_env)
        captures = load_captures(args.capture_file, encryption_key=key)
        health = analyze_session_health(captures)
        _emit(
            {
                "has_cookie": health.has_cookie,
                "bearer_token_count": health.bearer_token_count,
                "jwt_expired": health.jwt_expired,
                "jwt_expires_at": health.jwt_expires_at,
            },
            args.format,
        )
        return

    if args.command == "diff-captures":
        diff = compare_capture_files(args.a, args.b, encryption_key_a=args.a_key, encryption_key_b=args.b_key)
        _emit(
            {
                "headers_added": diff.headers_added,
                "headers_removed": diff.headers_removed,
                "method_changed": diff.method_changed,
            },
            args.format,
        )
        return

    if args.command == "recipe-save":
        adapter = get_adapter(args.adapter) if args.adapter else None
        defaults = adapter.defaults() if adapter else None
        cap = CaptureConfig(
            target_hint=args.target_hint or (defaults.target_hint if defaults else None),
            output_file=args.capture_file,
            filter_host_contains=(defaults.filter_host_contains if defaults else None),
        )
        rep = ReplayConfig(
            capture_file=args.capture_file,
            request_url=args.request_url,
            method=args.method,
            url_contains=args.url_contains or (defaults.replay_url_contains if defaults else None),
            allowed_domains=list(defaults.allowed_domains) if defaults else [],
        )
        path = save_recipe(Recipe(name=args.name, capture=cap, replay=rep), base_dir=args.base_dir)
        _emit({"saved": str(path), "name": args.name}, args.format)
        return

    if args.command == "recipe-list":
        _emit({"recipes": list_recipes(base_dir=args.base_dir)}, args.format)
        return

    if args.command == "recipe-run":
        recipe = load_recipe(args.name, base_dir=args.base_dir)
        if args.duration is not None:
            recipe.capture.duration_seconds = args.duration
        if args.max_records is not None:
            recipe.capture.max_records = args.max_records
        captures = capture_requests(recipe.capture)
        response = replay_with_capture(recipe.replay)
        _emit(
            {
                "name": args.name,
                "captured": len(captures),
                "status_code": response.status_code,
                "request_url": recipe.replay.request_url,
            },
            args.format,
        )
        return

    parser.error("Unknown command")


if __name__ == "__main__":
    main()
