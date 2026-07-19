# Operations

This document covers running, monitoring, and troubleshooting the Sakana Chat proxy.

## Running the proxy

### Prerequisites

- Python 3.8+
- Playwright (`playwright install chromium`)
- Network access to `https://chat.sakana.ai`

### Installation

1. Install Python dependencies:

```bash
pip install requests playwright
```

2. Install the Chromium browser for Playwright:

```bash
playwright install chromium
```

### Starting the server

Run the server directly:

```bash
python sakana_server.py
```

By default it listens on `localhost:8000`.

### Configuration via environment

You can configure the proxy using environment variables:

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

Example with custom settings:

```bash
export SAKANA_POOL_SIZE=5
export SAKANA_MIN_INTERVAL=5
python sakana_server.py
```

## Monitoring

### Logs

The proxy logs to `sakana_server.log` by default. Each line includes:

- Timestamp
- Request method and path
- Session ID (shortened)
- Response status
- Any errors or retries

Example log entries:

```
[pool] session d6c2f6c0 exhausted; 2 live remain
[server] POST /conversation session=d6c2f6c0 status=200
[server] POST /conversation session=32c3d249 status=429 retry=1
```

### Session pool status

The pool state is persisted in `sakana_pool.json`. You can inspect it to see:

- How many live sessions are available
- When sessions were last refreshed

Example:

```json
[
  {
    "cf_clearance": "...",
    "sakana_chat": "d6c2f6c0-6e03-4d4d-8a9f-d783922b21f4"
  },
  ...
]
```

### Health checks

You can check if the proxy is responsive by sending a simple request:

```bash
curl -X POST http://localhost:8000/conversation \
  -H "Content-Type: application/json" \
  -d '{"inputs": "test"}'
```

A healthy proxy will return a valid response from chat.sakana.ai.

## Troubleshooting

### Common issues

#### Rate limits (429)

If you see many 429 responses:

- Increase `SAKANA_POOL_SIZE` to spread load across more sessions
- Increase `SAKANA_MIN_INTERVAL` to slow down requests per session
- Check that `SAKANA_WEB_SEARCH` is disabled if you don’t need it (web search uses more quota)

#### Playwright errors

If session minting fails:

- Ensure `playwright install chromium` ran successfully
- Check that the machine can reach `https://chat.sakana.ai`
- Try increasing `timeout_ms` and `settle_ms` in `mint_sessions()` if Cloudflare is slow

#### Network issues

If requests fail with connection errors:

- Verify network connectivity to `chat.sakana.ai`
- Check for firewalls or proxies blocking the connection
- Ensure DNS resolution works for `chat.sakana.ai`

### Debugging

#### Enable verbose logging

You can add more logging by modifying `sakana_server.py` to print additional debug information.

#### Manual session refresh

You can manually refresh sessions using `sakana_session.py`:

```bash
python sakana_session.py 3  # Mint 3 new sessions
```

This will print the new session IDs and cookie lengths.

#### Inspect pool state

Check `sakana_pool.json` to see:

- How many sessions are live
- Whether sessions are being properly refreshed

## Performance tuning

### Throughput vs. rate limits

To maximize throughput without hitting rate limits:

- **Increase `POOL_SIZE`** – More sessions spread the load
- **Adjust `MIN_INTERVAL`** – Slower requests per session reduce quota usage
- **Use `CONVO_REUSE`** – Reuse conversations to avoid creating many new ones

### Memory and CPU

The proxy is lightweight:

- Each session uses a small amount of memory for its `requests.Session`
- Playwright is only used during session minting, not for normal requests
- The HTTP server is threaded but not heavily CPU-bound

For high concurrency, ensure your machine has enough RAM for the session pool and enough CPU for the HTTP server.

## Security considerations

### Cookies and tokens

- `cf_clearance` and `sakana-chat` cookies are sensitive; treat them like passwords
- They are stored in `sakana_session.json` and `sakana_pool.json`
- Keep these files secure and don’t share them

### Network security

- The proxy listens on `localhost:8000` by default
- If exposing it to other machines, use a reverse proxy with TLS
- Consider firewall rules to limit who can access the proxy

### Rate limiting

- The proxy helps you stay under chat.sakana.ai’s guest limits
- It does not prevent abuse if you send too many requests through it
- Implement your own rate limiting if needed

## Next steps

- [Quickstart](quickstart.md) – High-level overview
- [Architecture](architecture.md) – Internal components and data flow
- [Integrations](integrations.md) – Using the proxy from other tools