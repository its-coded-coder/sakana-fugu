#!/usr/bin/env bash
# One-shot bootstrap: install Python deps and the headless browser used to
# mint guest sessions. After this, the client and server fetch their own
# tokens automatically on first run.
set -euo pipefail

cd "$(dirname "$0")"

python3 -m pip install -r requirements.txt
python3 -m playwright install --with-deps chromium

echo
echo "Setup complete. Try:"
echo "  python3 sakana.py \"hello\"      # one-off query"
echo "  python3 sakana_server.py         # OpenAI-compatible server on :4000"
