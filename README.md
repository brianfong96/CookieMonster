# CookieMonster

CookieMonster is a modular Python CLI that connects to Chrome DevTools, captures auth-related headers (`Cookie`, `Authorization`, CSRF headers), and replays HTTP requests for automation.

Use it only for systems and accounts you are authorized to access.

## Cross-Platform CLI Packaging

The project is packaged with `pyproject.toml` and exposes a real CLI entrypoint:

- Command: `cookie-monster`
- Module fallback: `python -m cookie_monster`
- Supported OS: macOS and Windows (Python 3.10+)
- PyPI package name: `cookie-monster-cli`

Install locally:

```bash
python3 -m pip install -e .
```

Install with dev/test tooling:

```bash
python3 -m pip install -e '.[dev]'
```

Build release artifacts (PyPI-ready):

```bash
./scripts/release_pypi.sh
```

Publish to PyPI (maintainer credentials required):

```bash
python3 -m twine upload dist/*
```

After publish, users can install from anywhere:

```bash
python3 -m pip install cookie-monster-cli
```

## Architecture (KISS + DRY)

- `cookie_monster/chrome_discovery.py`: Chrome DevTools target discovery + startup retry
- `cookie_monster/chrome_launcher.py`: browser launcher (`chrome`/`edge`) with profile support
- `cookie_monster/cdp.py`: minimal websocket CDP client
- `cookie_monster/capture.py`: network event capture pipeline
- `cookie_monster/replay.py`: replay engine using captured headers
- `cookie_monster/storage.py`: JSONL persistence/load
- `cookie_monster/plugins/`: adapter scaffold + built-in adapters (`supabase`, `github`, `gmail`)
- `cookie_monster/models.py`, `cookie_monster/config.py`: shared data contracts
- `cookie_monster/cli.py`: command entrypoint (`capture`, `replay`, `profile-list`, `list-targets`, `doctor`, `serve`)
- `cookie_monster/api_server.py`: local HTTP API mode
- `cookie_monster/ui.py`: simple browser UI and CookieMonster logo
- `cookie_monster/browser_profiles.py`: profile discovery from browser Local State
- `cookie_monster/security_utils.py`: redaction + replay guardrails
- `cookie_monster/client.py`: stable programmatic API (`CookieMonsterClient`)
- `cookie_monster/browser_session.py`: context manager for launched browser lifecycle
- `cookie_monster/policy.py`: replay policy engine (allow/deny rules)
- `cookie_monster/recipes.py`: named workflow recipes
- `cookie_monster/session_health.py`: cookie/JWT health checks
- `cookie_monster/diffing.py`: capture-to-capture header/method diff

## Usage

### 1. Start Chrome with remote debugging

macOS:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --remote-allow-origins=* \
  --user-data-dir=/tmp/cookie-monster-profile
```

Windows (PowerShell):

```powershell
"$env:ProgramFiles\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --remote-allow-origins=* `
  --user-data-dir=$env:TEMP\cookie-monster-profile
```

### 2. Capture auth headers from browser traffic

```bash
cookie-monster capture \
  --chrome-host 127.0.0.1 \
  --chrome-port 9222 \
  --target-hint github.com \
  --duration 45 \
  --max-records 200 \
  --capture-post-data \
  --output data/captures.jsonl
```

Or let CookieMonster launch Chrome directly with a specific profile:

```bash
cookie-monster capture \
  --launch-browser \
  --browser chrome \
  --user-data-dir "/Users/brianfong/Library/Application Support/Google/Chrome" \
  --profile-directory Default \
  --open-url "https://supabase.com/dashboard/project/udnotkgtmnyxagnsmjxv" \
  --target-hint supabase.com \
  --adapter supabase \
  --include-all-headers \
  --duration 30 \
  --output data/supabase-captures.jsonl
```

Launch Edge instead:

```bash
cookie-monster capture \
  --launch-browser \
  --browser edge \
  --open-url "https://mail.google.com" \
  --target-hint google.com \
  --duration 30 \
  --output data/gmail-captures.jsonl
```

### 3. Replay using captured headers

```bash
cookie-monster replay \
  --capture-file data/captures.jsonl \
  --method POST \
  --url-contains api.example.com \
  --request-url https://api.example.com/v1/items \
  --use-captured-body \
  --allowed-domain api.example.com
```

For explicit bodies, override captured payload:

```bash
cookie-monster replay \
  --capture-file data/captures.jsonl \
  --method GET \
  --url-contains github.com \
  --request-url https://github.com/settings/profile \
  --allowed-domain github.com \
  --retry-attempts 3 \
  --retry-backoff 1.0 \
  --output data/response.json
```

Encrypted capture file (key can come from env):

```bash
export COOKIE_MONSTER_ENCRYPTION_KEY='YOUR_FERNET_KEY'
cookie-monster capture --target-hint github.com --encryption-key-env COOKIE_MONSTER_ENCRYPTION_KEY
cookie-monster replay --capture-file captures.jsonl --request-url https://github.com --encryption-key-env COOKIE_MONSTER_ENCRYPTION_KEY
```

JSON body replay (for POST APIs):

```bash
cookie-monster replay \
  --capture-file data/captures.jsonl \
  --method POST \
  --url-contains api.example.com \
  --request-url https://api.example.com/v1/items \
  --json-body-file payload.json \
  --allowed-domain api.example.com
```

### 4. Additional commands

List debuggable tabs:

```bash
cookie-monster list-targets --chrome-host 127.0.0.1 --chrome-port 9222
```

List local browser profiles:

```bash
cookie-monster profile-list --browser chrome
cookie-monster profile-list --browser edge
```

Run diagnostics:

```bash
cookie-monster doctor --browser chrome --chrome-host 127.0.0.1 --chrome-port 9222
cookie-monster adapter-list --verbose
cookie-monster session-health --capture-file data/captures.jsonl
cookie-monster diff-captures --a data/captures-old.jsonl --b data/captures-new.jsonl
cookie-monster recipe-save --name supabase --capture-file data/captures.jsonl --request-url https://supabase.com/dashboard/project/udnotkgtmnyxagnsmjxv --adapter supabase
cookie-monster recipe-list
cookie-monster recipe-run --name supabase
```

Run local API mode:

```bash
cookie-monster serve --host 127.0.0.1 --port 8787
cookie-monster ui --host 127.0.0.1 --port 8787
# Optional API auth token:
cookie-monster serve --api-token 'replace-me'
# Or from env:
COOKIE_MONSTER_API_TOKEN='replace-me' cookie-monster ui
```

Security note:
- Non-loopback API binds are blocked by default.
- To intentionally expose the API beyond localhost, set `COOKIE_MONSTER_ALLOW_REMOTE=1`.
- If `--api-token` (or `COOKIE_MONSTER_API_TOKEN`) is set, POST API endpoints require `X-CM-Token`.

Example API call:

```bash
curl -sS http://127.0.0.1:8787/health
curl -sS -X POST http://127.0.0.1:8787/capture -H 'content-type: application/json' -d '{\"duration_seconds\":10,\"target_hint\":\"supabase.com\"}'
curl -sS -X POST http://127.0.0.1:8787/session-health -H 'content-type: application/json' -d '{\"capture_file\":\"data/captures.jsonl\"}'
curl -sS -X POST http://127.0.0.1:8787/diff -H 'content-type: application/json' -d '{\"a\":\"data/captures-old.jsonl\",\"b\":\"data/captures-new.jsonl\"}'
curl -sS -X POST http://127.0.0.1:8787/ui/check-auth -H 'content-type: application/json' -d '{\"url\":\"https://supabase.com/dashboard/project/udnotkgtmnyxagnsmjxv\"}'
```

## Simple UI

Launch:

```bash
cookie-monster ui
# or
cm ui
```

Then open:

```text
http://127.0.0.1:8787/ui
```

Stop UI:

- If running in current terminal: press `Ctrl+C`
- If running in background: `pkill -f "cookie-monster ui"` (or `pkill -f "cm ui"`)

UI features:
- Enter URL and cache auth from your local profile into encrypted cache (`~/.cookie_monster/ui/captures.enc.jsonl`)
- Check whether auth headers are cached for that URL
- Inspect latest matching captures with redacted headers
- CookieMonster branded logo header

## Library API (Programmatic Use)

CookieMonster now exposes a stable library entrypoint:

```python
from cookie_monster import CookieMonsterClient, CaptureConfig, ReplayConfig
from cookie_monster.policy import ReplayPolicy

client = CookieMonsterClient(policy=ReplayPolicy(allowed_domains=[\"supabase.com\", \"api.supabase.com\"]))

capture_result = client.capture(
    CaptureConfig(
        target_hint=\"supabase.com\",
        include_all_headers=True,
        output_file=\"captures.jsonl\",
    )
)

replay_result = client.replay(
    ReplayConfig(
        capture_file=\"captures.jsonl\",
        request_url=\"https://supabase.com/dashboard/project/udnotkgtmnyxagnsmjxv\",
        allowed_domains=[\"supabase.com\"],
        enforce_capture_host=False,
    )
)
print(capture_result.count, replay_result.status_code)
```

Async methods are available:

```python
capture_result = await client.capture_async(CaptureConfig(...))
replay_result = await client.replay_async(ReplayConfig(...))
```

## TDD and Tests

Tests are in `tests/` and cover capture, replay, storage, discovery, and CLI behavior.

Run tests:

```bash
pytest
```

Run lint:

```bash
ruff check .
```

Current local result:

- `41 passed`
- `ruff check .` clean

## Man Page

A manual page is included at:

- `man/cookie-monster.1`

View directly:

```bash
man ./man/cookie-monster.1
```

Install to user manpath (macOS/Linux):

```bash
mkdir -p "$HOME/.local/share/man/man1"
cp man/cookie-monster.1 "$HOME/.local/share/man/man1/"
man cookie-monster
```

## E2E Script (Any Site, Chrome or Edge)

Automated smoke script:

```bash
python3 scripts/e2e_site.py --duration 25
```

Optional headless mode:

```bash
python3 scripts/e2e_site.py --duration 25 --headless
```

Use a specific profile and browser:

```bash
python3 scripts/e2e_site.py \
  --browser edge \
  --duration 25 \
  --user-data-dir "/path/to/browser-user-data-dir" \
  --target-url "https://mail.google.com" \
  --target-hint google.com \
  --replay-url "https://mail.google.com" \
  --url-contains google.com \
  --include-all-headers
```

This script launches the chosen browser with remote debugging, captures request headers, then replays to your target URL and writes:

- capture file: `/tmp/cookie-monster-github-captures.jsonl`
- replay output: `/tmp/cookie-monster-github-response.json`

If your session is logged in in that launched profile, replay should return authenticated content; otherwise expect login/redirect pages.

## Publishing Checklist For Other Computers

The repo now includes:

- `pyproject.toml` with console script entrypoint (`cookie-monster`)
- `LICENSE` (MIT)
- `MANIFEST.in` (includes man page)
- CI matrix workflow: `.github/workflows/ci.yml`
- PyPI publish workflow: `.github/workflows/publish-pypi.yml`

Before first public release:

1. Create package on PyPI (`cookie-monster-cli`) and configure Trusted Publisher for this GitHub repo.
2. Bump version in `pyproject.toml`.
3. Create GitHub release (publish workflow uploads to PyPI).
