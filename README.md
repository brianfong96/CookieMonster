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

Or let CookieMonster launch Chrome directly with a specific profile:

```bash
cookie-monster capture \
  --launch-browser \
  --browser chrome \
  --user-data-dir "/Users/brianfong/Library/Application Support/Google/Chrome" \
  --profile-directory Default \
  --open-url "https://supabase.com/dashboard/project/udnotkgtmnyxagnsmjxv" \
  --target-hint supabase.com \
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

- `16 passed`

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
