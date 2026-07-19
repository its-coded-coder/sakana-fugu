import json
import os
import re
import secrets
import sys
import time

import requests

BASE = "https://chat.sakana.ai"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0"

ENV_FILE = os.environ.get(
    "SAKANA_ENV_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
)


def _load_dotenv(path=ENV_FILE):
    """Populate os.environ from a local .env (existing vars win)."""
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val


def _write_dotenv(cf, chat, path=ENV_FILE):
    """Persist the resolved tokens as env vars for future runs / other tools."""
    try:
        with open(path, "w") as f:
            f.write(f"SAKANA_CF_CLEARANCE={cf}\nSAKANA_CHAT={chat}\n")
        os.environ["SAKANA_CF_CLEARANCE"] = cf
        os.environ["SAKANA_CHAT"] = chat
    except OSError:
        pass


_load_dotenv()

CF_CLEARANCE = os.environ.get("SAKANA_CF_CLEARANCE", "")
SAKANA_CHAT = os.environ.get("SAKANA_CHAT", "")


def uuid7():
    ts = int(time.time() * 1000).to_bytes(6, "big")
    b = bytearray(ts + secrets.token_bytes(10))
    b[6] = (b[6] & 0x0F) | 0x70
    b[8] = (b[8] & 0x3F) | 0x80
    h = b.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def extract_answer(text):
    if not text:
        return ""
    m = re.search(r"<answer>(.*?)</answer>", text, re.S)
    return m.group(1).strip() if m else text.strip()


class SakanaClient:
    def __init__(self, cf_clearance, sakana_chat, agent_id="namazu"):
        self.agent_id = agent_id
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Accept": "*/*",
            "Origin": BASE,
            "Referer": BASE + "/",
        })
        self.session.cookies.set("cf_clearance", cf_clearance, domain="chat.sakana.ai")
        self.session.cookies.set("sakana-chat", sakana_chat, domain="chat.sakana.ai")

    def create_conversation(self, prompt, thinking=False, web_search=True, tone="default"):
        r = self.session.post(f"{BASE}/conversation", json={
            "inputs": prompt,
            "enableThinking": thinking,
            "toneMode": tone,
            "webSearchEnabled": web_search,
            "agentId": self.agent_id,
        })
        r.raise_for_status()
        return r.json()

    def send(self, conversation_id, prompt, parent_id, thinking=False, web_search=True,
             tone="default", on_token=None):
        data = {
            "inputs": prompt,
            "id": parent_id,
            "is_retry": False,
            "is_continue": False,
            "enableThinking": thinking,
            "toneMode": tone,
            "webSearchEnabled": web_search,
            "userMessageId": uuid7(),
        }
        r = self.session.post(
            f"{BASE}/conversation/{conversation_id}",
            files={"data": (None, json.dumps(data))},
            stream=True,
        )
        r.raise_for_status()
        final = None
        tokens = []
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = evt.get("type")
            if kind == "stream":
                token = evt.get("token", "").replace("\x00", "")
                if token:
                    tokens.append(token)
                    if on_token:
                        on_token(token)
            elif kind == "finalAnswer":
                final = evt.get("text", "")
        # Fall back to the streamed tokens if no (or empty) finalAnswer arrived.
        if not (final or "").strip() and tokens:
            final = "".join(tokens)
        return final

    def get_conversation(self, conversation_id):
        r = self.session.get(f"{BASE}/api/conversation/{conversation_id}")
        r.raise_for_status()
        return r.json()

    def compact(self, conversation_id, leaf_message_id):
        r = self.session.post(
            f"{BASE}/conversation/{conversation_id}/compact",
            json={"leafMessageId": leaf_message_id},
        )
        r.raise_for_status()
        return r.json()

    def agents(self):
        r = self.session.get(f"{BASE}/api/agents")
        r.raise_for_status()
        return r.json()

    def get_settings(self):
        r = self.session.get(f"{BASE}/api/v2/user/settings")
        r.raise_for_status()
        return r.json()

    def update_settings(self, settings):
        r = self.session.post(f"{BASE}/settings", json=settings)
        r.raise_for_status()
        return r.json() if r.content else None

    @staticmethod
    def _leaf(convo):
        leaves = [m for m in convo["messages"] if not m["children"]]
        return max(leaves, key=lambda m: len(m["ancestors"]))["id"]

    def ask(self, prompt, thinking=False, web_search=True, tone="default",
            on_token=None, conversation_id=None):
        if conversation_id is None:
            created = self.create_conversation(
                prompt, thinking=thinking, web_search=web_search, tone=tone
            )
            conversation_id = created["conversationId"]
            parent_id = created["systemMessageId"]
        else:
            parent_id = self._leaf(self.get_conversation(conversation_id))
        raw = self.send(
            conversation_id, prompt, parent_id, thinking=thinking,
            web_search=web_search, tone=tone, on_token=on_token,
        )
        return {
            "conversation_id": conversation_id,
            "raw": raw,
            "answer": extract_answer(raw),
        }


def resolve_credentials(auto_mint=True):
    """Return (cf_clearance, sakana_chat), fetching them automatically.

    Resolution order, so a fresh clone runs with zero configuration:
      1. SAKANA_CF_CLEARANCE / SAKANA_CHAT environment variables.
      2. A previously persisted guest session (sakana_session.json).
      3. A freshly minted guest session (headless browser), if auto_mint.
    """
    cf = os.environ.get("SAKANA_CF_CLEARANCE", CF_CLEARANCE)
    chat = os.environ.get("SAKANA_CHAT", SAKANA_CHAT)
    if cf and chat:
        return cf, chat

    import sakana_session

    saved = sakana_session.load_session()
    if saved:
        _write_dotenv(saved["cf_clearance"], saved["sakana_chat"])
        return saved["cf_clearance"], saved["sakana_chat"]

    if not auto_mint:
        raise RuntimeError("no credentials and auto_mint disabled")

    print("No session found; minting a fresh guest session...", file=sys.stderr)
    data = sakana_session.refresh_session()
    _write_dotenv(data["cf_clearance"], data["sakana_chat"])
    return data["cf_clearance"], data["sakana_chat"]


def main():
    try:
        cf, chat = resolve_credentials()
    except Exception as e:
        sys.exit(f"Could not obtain a session: {e}")

    prompt = " ".join(sys.argv[1:]) or "hi"
    client = SakanaClient(cf, chat)
    result = client.ask(prompt)
    print(result["answer"])


if __name__ == "__main__":
    main()
