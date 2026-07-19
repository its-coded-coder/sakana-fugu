# Architecture

This document describes the internal architecture of the Sakana Chat proxy.

## Overview

The proxy has three main components:

1. **Client library** (`sakana.py`) – Thin wrapper around chat.sakana.ai’s HTTP API
2. **Session management** (`sakana_session.py`) – Headless browser logic to mint fresh guest sessions
3. **Proxy server** (`sakana_server.py`) – HTTP frontend with session pooling and retries

All three work together to let you run many concurrent conversations while staying under chat.sakana.ai’s guest usage limits.

## Client library (`sakana.py`)

`SakanaClient` is a simple HTTP client for chat.sakana.ai.

### Key methods

- `create_conversation(prompt, thinking=False, web_search=True, tone="default")` – Start a new conversation
- `send(conversation_id, prompt, parent_id, thinking=False, web_search=True, tone="default", on_token=None)` – Send a message and stream the response
- `get_conversation(conversation_id)` – Fetch conversation state
- `compact(conversation_id, leaf_message_id)` – Compact conversation history

### Authentication

`SakanaClient` uses two cookies for authentication:

- `cf_clearance` – Cloudflare’s anti-bot challenge token
- `sakana-chat` – Sakana’s guest session ID

These are set on the `requests.Session` and sent with every request.

### Streaming

`send()` uses Server-Sent Events (SSE) to stream tokens:

- Opens a streaming POST to `/conversation/{conversation_id}`
- Parses JSON lines from the response
- Calls `on_token(token)` for each `stream` event
- Returns the final answer text from the `finalAnswer` event

### Conversation lifecycle

1. `create_conversation()` – Creates a new conversation and returns its ID
2. `send()` – Sends messages within that conversation
3. `compact()` – Optionally trims conversation history
4. `get_conversation()` – Inspects conversation state

## Session management (`sakana_session.py`)

This module handles minting fresh guest sessions when existing ones hit rate limits.

### Guest sessions

chat.sakana.ai gives anonymous visitors a `sakana-chat` guest ID, protected by Cloudflare’s `cf_clearance` cookie. Each guest ID has a usage quota; when exceeded, the API returns 429 「利用量の上限に達しました」.

To get a fresh guest ID, you need to load the site in a new browser context so Cloudflare issues a new challenge.

### Headless browser

`mint_sessions()` uses Playwright to:

- Launch a headless Chromium browser
- Create a fresh browser context for each session
- Load `https://chat.sakana.ai/`
- Wait for Cloudflare’s JS challenge to settle
- Extract `cf_clearance` and `sakana-chat` cookies
- Return a list of session dicts

Each session dict contains:

```json
{
  "cf_clearance": "...",
  "sakana_chat": "...",
  "ua": "Mozilla/5.0 ...",
  "ts": 1783194841.1542082
}
```

### Persistence

- `load_session()` / `save_session()` – Read/write the current session to `sakana_session.json`
- `load_pool()` / `save_pool()` – Read/write the session pool to `sakana_pool.json`
- `_atomic_write()` – Atomic file write with a temp file

### Concurrency

- `_refresh_lock` ensures only one thread runs Playwright at a time
- `mint_sessions()` can mint multiple sessions in one browser launch
- `refresh_session()` mints a single session and persists it

## Proxy server (`sakana_server.py`)

The proxy server is a threaded HTTP server that load-balances requests across a pool of guest sessions.

### SessionPool

`SessionPool` manages a rotating pool of guest sessions:

- `sessions` – List of `Session` objects
- `idx` – Round-robin index for picking sessions
- `lock` – Protects pool state
- `minting` – Flag to prevent concurrent replenishment

Each `Session` has:

- `cf`, `chat` – Cookie values
- `sid` – Short session ID for logging
- `client` – `SakanaClient` instance
- `lock` – Per-session lock
- `last` – Timestamp of last request
- `exhausted` – Whether this session hit a rate limit

### Request flow

1. **Pick session** – `SessionPool.pick()` chooses a live session (round-robin)
2. **Acquire lock** – The session’s lock ensures only one request uses it at a time
3. **Rate limit** – Wait `MIN_INTERVAL` seconds since the last request
4. **Forward request** – Use `SakanaClient` to send the request to chat.sakana.ai
5. **Handle errors** – Retry with exponential backoff on transient errors
6. **Mark exhausted** – If 429, mark the session exhausted and trigger replenishment

### Replenishment

When a session is exhausted:

- `mark_exhausted()` sets `exhausted = True`
- `replenish()` runs in a background thread to:
  - Mint new sessions via `mint_sessions()`
  - Add them to the pool
  - Persist the updated pool to `sakana_pool.json`

### HTTP API

The server exposes endpoints that mirror chat.sakana.ai’s API:

- `POST /conversation` – Create a new conversation
- `POST /conversation/{conversation_id}` – Send a message
- `GET /api/conversation/{conversation_id}` – Get conversation state
- `POST /conversation/{conversation_id}/compact` – Compact conversation history

Each endpoint:

- Picks a session
- Forwards the request
- Returns the response with appropriate status codes

## Data flow

### Typical request

1. Client sends HTTP request to proxy
2. Proxy picks a live session from the pool
3. Proxy forwards request to chat.sakana.ai via `SakanaClient`
4. chat.sakana.ai responds
5. Proxy returns response to client

### Session exhaustion

1. chat.sakana.ai returns 429 for a session
2. Proxy marks that session as exhausted
3. Proxy triggers background replenishment
4. Replenishment mints new sessions and adds them to the pool
5. Future requests use the new sessions

### Logging

- All requests and errors are logged to `sakana_server.log`
- Session exhaustion and replenishment are logged with session IDs
- Retries and backoffs are logged for debugging

## Configuration and tuning

Key knobs:

- `POOL_SIZE` – How many sessions to keep live
- `CONVO_REUSE` – Messages per conversation before starting fresh
- `MIN_INTERVAL` – Minimum seconds between requests per session
- `MAX_RETRIES` / `BACKOFF` – Retry behavior on transient errors
- `MAX_SESSION_REFRESH` – How many inline refreshes to attempt per request

These let you balance throughput against the risk of hitting rate limits.

## Next steps

- [Quickstart](quickstart.md) – High-level overview
- [Operations](operations.md) – Running and monitoring the proxy
- [Integrations](integrations.md) – Using the proxy from other tools