# Sakana Chat Proxy – Quickstart

This repository contains a Python proxy server that lets you run many concurrent conversations with Sakana AI’s chat.sakana.ai service while staying under its guest usage limits.

It does this by:
- Using a rotating pool of guest sessions (`sakana-chat` cookies + Cloudflare `cf_clearance`)
- Automatically refreshing sessions when they hit rate limits
- Exposing a simple HTTP API that forwards requests to chat.sakana.ai

If you’re building a tool or agent that needs to talk to Sakana Chat frequently, this proxy lets you manage session limits and concurrency in one place.

## Repository overview

Main files:
- `/sakana.py` – Client library for chat.sakana.ai
- `/sakana_server.py` – HTTP proxy server and session pool
- `/sakana_session.py` – Headless browser logic to mint fresh guest sessions
- `/sakana_session.json` – Current guest session (cookie data)
- `/sakana_pool.json` – Pool of live guest sessions
- `/sakana_server.log` – Server request/error log

This is a small, focused codebase with three main components:

1. **Client library** (`sakana.py`) – Thin wrapper around chat.sakana.ai’s HTTP API
2. **Session management** (`sakana_session.py`) – Uses Playwright to get fresh guest cookies
3. **Proxy server** (`sakana_server.py`) – HTTP frontend that load-balances across sessions

## How it works

### Guest sessions and rate limits

chat.sakana.ai gives anonymous visitors a `sakana-chat` guest ID, protected by Cloudflare (`cf_clearance`). Each guest ID has a usage quota; when exceeded, the API returns 429 「利用量の上限に達しました」.

This proxy:
- Maintains a pool of guest sessions (`sakana_pool.json`)
- Rotates requests across sessions to spread usage
- Detects 429s and marks sessions as exhausted
- Automatically refreshes exhausted sessions using a headless browser (`sakana_session.py`)

### Client library (`sakana.py`)

`SakanaClient` is a thin wrapper around chat.sakana.ai’s endpoints:

- `create_conversation()` – Start a new conversation
- `send()` – Send a message and stream the response
- `get_conversation()` – Fetch conversation state
- `compact()` – Compact conversation history
- `agents()` – List available agents
- `get_settings()` / `update_settings()` – Get/update user settings
- `ask()` – High-level helper to send a prompt and get an answer

It handles cookie authentication (`cf_clearance`, `sakana-chat`) and SSE streaming.

### Session minting (`sakana_session.py`)

Uses Playwright to:
- Launch a headless Chromium browser
- Load chat.sakana.ai in a fresh context
- Wait for Cloudflare’s JS challenge to settle
- Extract `cf_clearance` and `sakana-chat` cookies
- Save them to `sakana_session.json` / `sakana_pool.json`

This lets you programmatically obtain fresh guest sessions without manual browser interaction.

### Proxy server (`sakana_server.py`)

A threaded HTTP server that:
- Loads the session pool on startup
- Picks a live session for each request (round-robin)
- Forwards requests to chat.sakana.ai via `SakanaClient`
- Retries with exponential backoff on transient errors
- Logs requests and errors to `sakana_server.log`
- Replenishes the pool in the background when sessions are exhausted

## Getting started

### Prerequisites

- Python 3.8+
- Playwright (`playwright install chromium`)
- A working network connection to chat.sakana.ai

### Running the proxy

1. Install dependencies:

```bash
pip install requests playwright
playwright install chromium
```

2. Start the server:

```bash
python sakana_server.py
```

By default it listens on `localhost:8000`.

### Example usage

Send a request to the proxy:

```bash
curl -X POST http://localhost:8000/conversation \
  -H "Content-Type: application/json" \
  -d '{"inputs": "Hello, who are you?"}'
```

The proxy will:
- Pick a live guest session
- Forward the request to chat.sakana.ai
- Return the model’s response

## Configuration

Environment variables:

- `SAKANA_LOG` – Log file path (default: `sakana_server.log`)
- `SAKANA_MIN_INTERVAL` – Minimum seconds between requests per session (default: 3)
- `SAKANA_MAX_RETRIES` – Max retries per request (default: 4)
- `SAKANA_BACKOFF` – Backoff base seconds (default: 5)
- `SAKANA_WEB_SEARCH` – Enable web search (default: false)
- `SAKANA_POOL_SIZE` – Number of guest sessions to keep live (default: 3)
- `SAKANA_MAX_SESSION_REFRESH` – Max inline session refreshes per request (default: 2)
- `SAKANA_UA` – User-Agent for headless browser (default: Firefox 152)
- `SAKANA_SESSION_FILE` – Path to current session JSON (default: `sakana_session.json`)
- `SAKANA_POOL_FILE` – Path to session pool JSON (default: `sakana_pool.json`)

## Next steps

- [Architecture](architecture.md) – Deep dive on components and data flow
- [Operations](operations.md) – Running, monitoring, and troubleshooting
- [Integrations](integrations.md) – Using the proxy from other tools

When working in this repository, read this quickstart first, then follow its links to the relevant architecture, workflow, domain, operation, and testing notes.