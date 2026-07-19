# sakana-fugu

An OpenAI-compatible proxy that turns **sakana.ai free-tier guest sessions**
into an unlimited, drop-in API endpoint. Point Claude Code, Cursor, Continue,
any other IDE assistant, or any OpenAI SDK / `curl` at it and use it like a
normal chat-completions API — no accounts, no keys, no manual tokens.

It works by continuously minting fresh guest sessions with a headless browser
and rotating a self-replenishing pool of them behind a standard
`/v1/chat/completions` endpoint, so when one free session hits its quota the
next takes over transparently.

> **Educational purposes only.** This project is provided as-is for research and
> educational use. The author does **not** endorse misuse and takes **no
> liability** for anything a user does with it — you are solely responsible for
> how you use this project and for complying with the terms of service of any
> third party it interacts with. See the full disclaimer at the bottom.

## Quickstart

```bash
git clone https://github.com/its-coded-coder/sakana-fugu.git
cd sakana-fugu
./setup.sh          # installs deps + the headless Chromium used to mint tokens

python3 sakana_server.py   # OpenAI-compatible server on http://localhost:4000
```

The first run mints a guest session automatically; there is nothing to
configure.

## Use it with `curl`

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-anything" \
  -d '{
    "model": "namazu",
    "messages": [{"role": "user", "content": "Say hello in one line."}]
  }'
```

Streaming works too — add `"stream": true` and the server emits standard
OpenAI `text/event-stream` chunks. The `Authorization` header is ignored (any
value works), since the endpoint is unauthenticated and local.

## Use it with Claude Code

This server exposes the **OpenAI** format (`/v1/chat/completions`). Claude Code
speaks the **Anthropic Messages** format, so route it through any
OpenAI-compatible translator — e.g. [LiteLLM](https://github.com/BerriAI/litellm),
which proxies Anthropic-shaped requests to this endpoint:

```bash
# 1. run this server (mints its own sessions)
python3 sakana_server.py

# 2. run a LiteLLM proxy that points at it
litellm --model openai/namazu --api_base http://localhost:4000/v1 --port 8000

# 3. point Claude Code at the translator
export ANTHROPIC_BASE_URL="http://localhost:8000"
export ANTHROPIC_API_KEY="sk-anything"
claude
```

Any tool that natively supports an OpenAI-compatible base URL (see below) can
skip the translator and talk to `http://localhost:4000/v1` directly.

## Use it with any IDE / SDK

Any tool that lets you set a custom OpenAI-compatible base URL will work — set:

- **Base URL:** `http://localhost:4000/v1`
- **API key:** any non-empty string (e.g. `sk-anything`)
- **Model:** `namazu`

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:4000/v1", api_key="sk-anything")
print(client.chat.completions.create(
    model="namazu",
    messages=[{"role": "user", "content": "Hello!"}],
).choices[0].message.content)
```

You can also skip the server and use the client directly:

```bash
python3 sakana.py "explain the fugu fish in one line"
```

## How tokens are handled

`sakana.py` resolves credentials in this order, minting on demand:

1. `SAKANA_CF_CLEARANCE` / `SAKANA_CHAT` environment variables, if set.
2. A local `.env` file (auto-loaded on import).
3. A cached session in `sakana_session.json`.
4. A freshly minted guest session (headless browser via Playwright).

Once resolved, the tokens are written back to `.env` as
`SAKANA_CF_CLEARANCE` / `SAKANA_CHAT`, so they are available as environment
variables to later runs and any other tooling — no manual `export` needed.
`.env` is gitignored and never committed.

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

## Disclaimer

This software is provided **for educational and research purposes only**, on an
**"as-is" basis, without warranty of any kind**, express or implied. By using
this project you acknowledge that you do so **entirely at your own risk**. The
author accepts **no responsibility or liability** for any misuse, damages, data
loss, account restrictions, or any other consequences arising from the use or
inability to use this software. It is **your responsibility** to ensure your use
complies with all applicable laws and the terms of service of any third-party
service accessed through it. If you do not agree, do not use this project.
