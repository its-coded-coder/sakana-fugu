# Integrations

This document explains how to use the Sakana Chat proxy from other tools and programming languages.

## HTTP API

The proxy exposes a simple HTTP API that mirrors chat.sakana.ai’s endpoints. You can use it from any HTTP client.

### Base URL

By default, the proxy runs on:

```
http://localhost:8000
```

You can change the host and port by modifying `sakana_server.py`.

### Endpoints

#### Create a conversation

```http
POST /conversation
Content-Type: application/json

{
  "inputs": "Your prompt here",
  "enableThinking": false,
  "toneMode": "default",
  "webSearchEnabled": false,
  "agentId": "namazu"
}
```

Response:

```json
{
  "id": "conversation-id",
  "title": "Generated title",
  "messages": [...],
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-01T00:00:00Z"
}
```

#### Send a message

```http
POST /conversation/{conversation_id}
Content-Type: application/json

{
  "inputs": "Your message here",
  "id": "parent-message-id",
  "is_retry": false,
  "is_continue": false,
  "enableThinking": false,
  "toneMode": "default",
  "webSearchEnabled": false,
  "userMessageId": "uuid7"
}
```

The response is a stream of Server-Sent Events (SSE). Each line is a JSON object:

```json
{"type": "stream", "token": "Hello"}
{"type": "stream", "token": " world"}
{"type": "finalAnswer", "text": "Hello world"}
```

#### Get conversation state

```http
GET /api/conversation/{conversation_id}
```

Response:

```json
{
  "id": "conversation-id",
  "title": "Generated title",
  "messages": [...],
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-01T00:00:00Z"
}
```

#### Compact conversation history

```http
POST /conversation/{conversation_id}/compact
Content-Type: application/json

{
  "leafMessageId": "message-id"
}
```

Response: The updated conversation state.

## Using from Python

### Direct HTTP calls

You can use `requests` or any HTTP library:

```python
import requests

response = requests.post(
    "http://localhost:8000/conversation",
    json={
        "inputs": "Hello, who are you?",
        "enableThinking": False,
        "toneMode": "default",
        "webSearchEnabled": False,
        "agentId": "namazu"
    }
)
conversation = response.json()
```

### Using SakanaClient directly

If you’re already in Python, you can use `SakanaClient` directly instead of the proxy:

```python
from sakana import SakanaClient

client = SakanaClient(cf_clearance, sakana_chat)
conversation = client.create_conversation("Hello")
answer = client.send(conversation["id"], "Follow-up", conversation["messages"][-1]["id"])
```

The proxy is most useful when you need to manage multiple sessions or run at high concurrency.

## Using from other languages

### JavaScript/Node.js

```javascript
const response = await fetch('http://localhost:8000/conversation', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    inputs: 'Hello, who are you?',
    enableThinking: false,
    toneMode: 'default',
    webSearchEnabled: false,
    agentId: 'namazu'
  })
});
const conversation = await response.json();
```

### Go

```go
import (
    "bytes"
    "encoding/json"
    "net/http"
)

type ConversationRequest struct {
    Inputs          string `json:"inputs"`
    EnableThinking  bool   `json:"enableThinking"`
    ToneMode        string `json:"toneMode"`
    WebSearchEnabled bool  `json:"webSearchEnabled"`
    AgentId         string `json:"agentId"`
}

reqBody, _ := json.Marshal(ConversationRequest{
    Inputs: "Hello, who are you?",
    EnableThinking: false,
    ToneMode: "default",
    WebSearchEnabled: false,
    AgentId: "namazu",
})

resp, _ := http.Post("http://localhost:8000/conversation", "application/json", bytes.NewBuffer(reqBody))
defer resp.Body.Close()

var conversation map[string]interface{}
json.NewDecoder(resp.Body).Decode(&conversation)
```

### Rust

```rust
use reqwest::Client;
use serde_json::json;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = Client::new();
    let response = client
        .post("http://localhost:8000/conversation")
        .json(&json!({
            "inputs": "Hello, who are you?",
            "enableThinking": false,
            "toneMode": "default",
            "webSearchEnabled": false,
            "agentId": "namazu"
        }))
        .send()
        .await?;
    let conversation: serde_json::Value = response.json().await?;
    Ok(())
}
```

## Streaming responses

To handle streaming responses, you need to parse SSE lines:

### Python example

```python
import requests

response = requests.post(
    "http://localhost:8000/conversation/conversation-id",
    json={
        "inputs": "Your message",
        "id": "parent-message-id",
        "is_retry": False,
        "is_continue": False,
        "enableThinking": False,
        "toneMode": "default",
        "webSearchEnabled": False,
        "userMessageId": "uuid7"
    },
    stream=True
)

for line in response.iter_lines():
    if not line:
        continue
    event = json.loads(line)
    if event["type"] == "stream":
        print(event["token"], end="", flush=True)
    elif event["type"] == "finalAnswer":
        print("\n" + event["text"])
```

### JavaScript example

```javascript
const response = await fetch('http://localhost:8000/conversation/conversation-id', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    inputs: 'Your message',
    id: 'parent-message-id',
    is_retry: false,
    is_continue: false,
    enableThinking: false,
    toneMode: 'default',
    webSearchEnabled: false,
    userMessageId: 'uuid7'
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  
  const lines = decoder.decode(value).split('\n');
  for (const line of lines) {
    if (!line) continue;
    const event = JSON.parse(line);
    if (event.type === 'stream') {
      process.stdout.write(event.token);
    } else if (event.type === 'finalAnswer') {
      console.log('\n' + event.text);
    }
  }
}
```

## Error handling

The proxy returns standard HTTP status codes:

- `200` – Success
- `429` – Rate limit exceeded (session exhausted)
- `500` – Internal server error
- Other 4xx/5xx – Forwarded from chat.sakana.ai or network errors

Check the response status and retry with exponential backoff if needed.

## Next steps

- [Quickstart](quickstart.md) – High-level overview
- [Architecture](architecture.md) – Internal components and data flow
- [Operations](operations.md) – Running and monitoring the proxy