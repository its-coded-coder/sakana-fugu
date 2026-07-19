# sakana-fugu

A thin Python client and OpenAI-compatible proxy for `chat.sakana.ai`.

Guest sessions are fetched **automatically** — a headless browser mints the
`cf_clearance` + `sakana-chat` cookies the API needs, so a fresh clone runs
with zero manual token wrangling.

## Quickstart

```bash
git clone https://github.com/its-coded-coder/sakana-fugu.git
cd sakana-fugu
./setup.sh          # installs deps + the headless Chromium used to mint tokens
```

Then either:

```bash
# One-off query (mints and caches a session on first run)
python3 sakana.py "explain the fugu fish in one line"

# OpenAI-compatible server on :4000, with a self-replenishing session pool
python3 sakana_server.py
```

## How tokens are handled

`sakana.py` resolves credentials in this order, minting on demand:

1. `SAKANA_CF_CLEARANCE` / `SAKANA_CHAT` environment variables, if set.
2. A cached session in `sakana_session.json`.
3. A freshly minted guest session (headless browser via Playwright).

The server keeps a rotating pool of guest sessions (`SAKANA_POOL_SIZE`, default
3), marks any that hit the guest quota as exhausted, and replenishes the pool
in the background. Cached sessions and the pool are stored locally and are
gitignored — they are never committed.

### Useful environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `SAKANA_POOL_SIZE` | `3` | Live guest sessions kept in the server pool |
| `SAKANA_WEB_SEARCH` | `0` | Enable web search for server completions |
| `PORT` | `4000` | Server listen port |
| `SAKANA_SESSION_FILE` | `sakana_session.json` | Cached single-session path |
| `SAKANA_POOL_FILE` | `sakana_pool.json` | Cached pool path |

## Requirements

Python 3.9+ and the packages in `requirements.txt` (installed by `setup.sh`).
