# VoceChat Setup Guide

Date: 2026-09-08

## Overview

VoceChat is used as the agent chatroom for this project. Agents communicate through VoceChat channels using the Bot API. The agentic-coding-manager agent surveils conversations via a webhook receiver.

## Sources of truth

- VoceChat documentation: <https://doc.voce.chat/>
- API Swagger: `<server-url>/api/swagger`
- Bot & Webhook guide: <https://doc.voce.chat/bot/bot-and-webhook>
- Skill: `skills/chat/SKILL.md`
- Client script: `skills/chat/vocechat_client.py`
- Contact directory: `skills/chat/contacts.json`

## Server installation

### Docker (recommended)

```bash
docker run -d --restart=always -p 3000:3000 --name vocechat-server privoce/vocechat-server:latest
```

Open `http://localhost:3000/` and complete the initial admin setup.

### Alternative installs

- Docker + Caddy: <https://doc.voce.chat/install/docker-caddy>
- Docker + Nginx: <https://doc.voce.chat/install/docker-nginx>
- Shell install: <https://doc.voce.chat/install/shell>

## Bot creation

1. Log in as admin.
2. Go to Settings -> Bot & Webhook.
3. Click "New", set bot name (e.g., "Agent Manager").
4. Optionally set a bot avatar.
5. Note the Bot ID (the number after `#`).

## API key generation

1. In the bot settings, click "Create API Key".
2. Name it (e.g., "surveillance-key").
3. Copy the key immediately — it won't be shown again.
4. If lost or exposed, delete the key and create a new one.

## Environment configuration

Create or update `.env` in the project root:

```
VOCECHAT_SERVER=http://localhost:3000
VOCECHAT_API_KEY=your-bot-api-key-here
VOCECHAT_BOT_ID=1
```

The `vocechat_client.py` script (bundled with the `chat` skill) and any agent with the `chat` skill will read these variables.

## Adding the bot to channels

1. Open each channel where agents should communicate.
2. Add the bot as a member (channel settings -> add member).
3. The bot can now send messages to and receive webhooks from that channel.

## Webhook configuration

1. Ensure the webhook receiver is running:
   ```bash
   python skills/chat/vocechat_client.py webhook --port 8010 --log-file /tmp/vocechat_surveillance.log
   ```
2. In the bot settings, set the webhook URL:
   ```
   http://<receiver-host>:8010/
   ```
3. The webhook URL must return `200` on `GET`. The receiver handles this.
4. VoceChat will now POST events (new message, reply, edit, delete, new user) to the receiver.

### Webhook URL requirements

- Must be reachable from the VoceChat server.
- Must respond `200` to `GET`.
- Receives `POST` with JSON payloads for each event.
- If behind a reverse proxy, ensure WebSocket headers are forwarded if using WebSocket features.

## AES encryption (optional)

For encrypted webhook payloads:

1. Set a 16-byte secret string in the bot's webhook settings.
2. The receiver must decrypt with AES + PKCS7 unpadding.
3. If not set, messages are transmitted in plaintext.

## Using the client

### CLI

```bash
# List all channels the bot is in
python skills/chat/vocechat_client.py groups

# Send a text message to a user
python skills/chat/vocechat_client.py send-user --uid 1 --content "Hello!"

# Send a markdown message to a channel
python skills/chat/vocechat_client.py send-group --gid 2 --content "**Status**: all good" --markdown

# Get user info
python skills/chat/vocechat_client.py user-info --uid 1

# Get group info
python skills/chat/vocechat_client.py group-info --gid 2

# Start webhook receiver
python skills/chat/vocechat_client.py webhook --port 8010

# Start webhook receiver with file logging
python skills/chat/vocechat_client.py webhook --port 8010 --log-file /tmp/vocechat_surveillance.log
```

### Python module

```python
from vocechat_client import VoceChatClient

client = VoceChatClient(server="http://localhost:3000", api_key="xxx")
groups = client.get_groups()
client.send_to_group(gid=2, content="**Hello** agents!", markdown=True)
```

## VoceChat API summary

### Bot API (x-api-key header)

| Method | Endpoint                        | Purpose                     |
| ------ | ------------------------------- | --------------------------- |
| GET    | `/api/bot?public_only=false`    | List bot's groups           |
| POST   | `/api/bot/send_to_user/{uid}`   | Send message to user (DM)   |
| POST   | `/api/bot/send_to_group/{gid}`  | Send message to group       |
| GET    | `/api/bot/user?uid={uid}`       | Get user info               |
| GET    | `/api/bot/group?gid={gid}`      | Get group info              |
| POST   | `/api/bot/file/prepare`         | Prepare file upload         |
| POST   | `/api/bot/file/upload`          | Upload file chunk           |

### Content types

| Content-Type       | Body                                |
| ------------------ | ----------------------------------- |
| `text/plain`       | Raw text                            |
| `text/markdown`    | Markdown string                     |
| `vocechat/file`    | JSON: `{"path": "<uploaded-path>"}` |
| `application/json` | JSON: `{"to","subject","content"}`  |

### Webhook event types

- `normal` — new message
- `reply` — reply to a message
- `edit` (inside `reaction`) — edited message
- `delete` (inside `reaction`) — deleted message
- `newuser` — new user signed up

## Security notes

- Never commit `.env` or API keys to git.
- The webhook receiver should run on a trusted network or behind a reverse proxy.
- Do not send secrets or credentials through VoceChat messages.
- The surveillance bot should only monitor channels it has been explicitly added to.
- Rotate API keys if they are exposed.

## Related

- `skills/chat/SKILL.md` — full API documentation (chat skill, VoceChat backend)
- `skills/chat/vocechat_client.py` — Python client and webhook receiver
- `skills/chat/contacts.json` — agent/channel contact directory
- `skills/agentic-coding/SKILL.md` — agent coordination patterns
- `agents/agentic-coding-manager.md` — the manager agent
