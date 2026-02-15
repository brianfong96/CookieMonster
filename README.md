# CookieMonster

CookieMonster is a modular Python CLI that connects to Chrome DevTools, captures auth-related headers (`Cookie`, `Authorization`, CSRF headers), and replays HTTP requests for automation.

Use it only for systems and accounts you are authorized to access.

## Cross-Platform CLI Packaging

The project is packaged with `pyproject.toml` and exposes a real CLI entrypoint:

- Command: `cookie-monster`
- Module fallback: `python -m cookie_monster`
- Supported OS: macOS and Windows (Python 3.10+)

Install locally:

```bash
python3 -m pip install -e .
```

Install with dev/test tooling:

```bash
python3 -m pip install -e '.[dev]'
```

## Architecture (KISS + DRY)

- `cookie_monster/chrome_discovery.py`: Chrome DevTools target discovery + startup retry
- `cookie_monster/cdp.py`: minimal websocket CDP client
- `cookie_monster/capture.py`: network event capture pipeline
- `cookie_monster/replay.py`: replay engine using captured headers
- `cookie_monster/storage.py`: JSONL persistence/load
- `cookie_monster/models.py`, `cookie_monster/config.py`: shared data contracts
- `cookie_monster/cli.py`: `capture` and `replay` commands

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
  --output data/captures.jsonl
```

### 3. Replay using captured headers

```bash
cookie-monster replay \
  --capture-file data/captures.jsonl \
  --method GET \
  --url-contains github.com \
  --request-url https://github.com/settings/profile \
  --output data/response.json
```

## TDD and Tests

Tests are in `tests/` and cover capture, replay, storage, discovery, and CLI behavior.

Run tests:

```bash
pytest
```

Current local result:

- `11 passed`

## E2E Script (Chrome + GitHub)

Automated smoke script:

```bash
python3 scripts/e2e_github.py --duration 25
```

Optional headless mode:

```bash
python3 scripts/e2e_github.py --duration 25 --headless
```

Use a specific Chrome profile (for existing logged-in GitHub session):

```bash
python3 scripts/e2e_github.py --duration 25 --user-data-dir "/path/to/chrome-profile"
```

This script launches Chrome with remote debugging, captures GitHub request headers, then replays to `https://github.com/settings/profile` and writes:

- capture file: `/tmp/cookie-monster-github-captures.jsonl`
- replay output: `/tmp/cookie-monster-github-response.json`

If your GitHub session is logged in in that launched Chrome profile, replay should return an authenticated response; otherwise expect redirect/login response codes.
