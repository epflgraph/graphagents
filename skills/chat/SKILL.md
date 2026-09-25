---
name: chat
description: Send, read, and surveil agent chatroom messages. Use when posting a message to a channel or agent, reading chat, monitoring agent conversations, or when the user says "message", "tell", "notify", "ping", or "chat with" an agent or channel.
---

# Chat

This skill provides agent chatroom messaging: sending messages to agents (DMs) and channels, reading incoming messages, surveilling conversations, and resolving natural-language targets to chat IDs.

The current backend is **VoceChat** (see [Backend: VoceChat](#backend-vocechat) below). The concepts in this top section are technology-agnostic; only the backend section is implementation-specific.

## When to use

- The user says "message", "tell", "ask", "notify", "ping", or "chat with" an agent or channel.
- You need to post a status update, question, or result to the chatroom.
- You need to read or check for incoming chat messages.
- You need to monitor (surveil) agent conversations in real time.
- The `/chat` command is invoked.

## Natural Language Intent Parsing

When a user or the `/chat` command gives a natural-language chat instruction, extract these components before sending:

### Components to extract

| Component    | How to detect                                              | Examples                              |
| ------------ | ---------------------------------------------------------- | ------------------------------------- |
| **Intent**   | "message", "tell", "ask", "notify", "ping", "send", "post" | "tell the graphai dev"                |
| **Target**   | Agent name, channel name, or "channel"/"group"/"DM"        | "graphai dev", "general channel"      |
| **Content**  | Everything after "about"/"that"/"to say"/":" or in quotes  | "about the timeout issue"             |
| **Format**   | "markdown" keyword -> markdown, else plain text            | "post markdown summary"               |
| **Mentions** | "@name" tokens in the content                              | "@graphai-engineer what's the status" |

### Target resolution rules

1. If the target matches an agent name in `contacts.json` -> **DM** (send to user).
2. If the target matches a channel name in `contacts.json` -> **channel post** (send to group).
3. If the target contains "channel" or "group" -> look up the channel name in `contacts.json`.
4. If the target is ambiguous or not found -> list available contacts from `contacts.json` and ask for clarification.
5. Default to the `general` channel if no target is specified.

### Content extraction rules

- If the instruction contains "about", "that", or "to say", everything after that word is the message content.
- If the content is in quotes, use the text inside the quotes.
- If the content is in parentheses, use the text inside.
- Otherwise, use everything after the target name.
- Strip filler words ("this", "the", "an") from the beginning of the content only if they are not part of the intended message.

### Resolution examples

| Input                                                      | Target       | Type    | Content                              |
| ---------------------------------------------------------- | ------------ | ------- | ------------------------------------ |
| "tell the graphai dev about the timeout issue"             | graphai-engineer | DM   | the timeout issue                    |
| "message the graphai dev about this issue (token expired)" | graphai-engineer | DM   | token expired                        |
| "post to general: deployment complete"                     | general      | Channel | deployment complete                  |
| "notify the engineering channel that the build passed"     | engineering  | Channel | the build passed                     |
| "ping senior-hexa-developer asking about the adapter"      | senior-hexa-developer | DM | about the adapter                   |
| "new message for you"                                      | (self)       | Read    | Check your own channels and DMs      |

## Contact Directory

Agent and channel IDs are stored in `skills/chat/contacts.json`. This file maps human-readable names to backend-specific IDs.

Structure:

```json
{
  "agents": {
    "<agent-name>": {
      "uid": <int>,
      "bot": "<bot-name>",
      "email": "<outline-address>",
      "display_name": "<Human Readable Name>",
      "aliases": ["<short-name>", "<nickname>"]
    }
  },
  "humans": {
    "<name>": {
      "uid": <int>,
      "email": "<real-address>",
      "display_name": "<Human Readable Name>",
      "aliases": []
    }
  },
  "channels": {
    "<channel-name>": {
      "gid": <int>,
      "display_name": "<Human Readable Name>",
      "aliases": ["<short-name>"]
    }
  }
}
```

The `bot` field names the VoceChat bot this agent speaks as (it drives the
client's `--as <bot>` flag), and `email` is the agent's Outline identity
(used by the `outline-magic-link.sh` login helper). Bot names double as
resolution aliases, so "write to Hubert" resolves to `graphai-engineer`.

### Resolution process

1. Read `skills/chat/contacts.json`.
2. Match the target text against:
   - Agent/channel keys (exact match).
   - `aliases` arrays (case-insensitive).
   - `display_name` (case-insensitive substring).
3. If multiple matches, prefer agents over channels for DM-style verbs ("tell", "ask", "ping"), and channels for broadcast verbs ("post", "notify", "broadcast").
4. If still ambiguous, ask the user.

### Updating contacts

When a new agent or channel is created in the chatroom:
1. Get the uid/gid from the chat server.
2. Add an entry to `contacts.json`.
3. Include relevant aliases (short names, nicknames the user might type).

## Message Concepts

### Message types

| Type    | Description                          | When to use                           |
| ------- | ------------------------------------ | ------------------------------------- |
| DM      | Direct message to a specific agent   | Private question, individual task     |
| Channel | Post to a group/channel              | Status update, broadcast, discussion  |
| Reply   | Reply to a specific message          | Threaded response                     |
| File    | Upload and send a file               | Sharing logs, screenshots, reports    |

### Message format

- **Plain text**: simple messages, quick updates.
- **Markdown**: formatted messages with headers, bold, lists, code blocks.
- Use markdown for: status reports, multi-section updates, code snippets.
- Use plain text for: quick pings, single-line messages.

### Mentioning

To @mention an agent in a message, include their name and set the mentions property with their uid. Mentioned agents receive a notification.

### Reading messages

The Bot API is not send-only: a bot can pull the messages it is allowed to see.

- **Channel messages**: `GET /api/bot/group/{gid}/messages` — recent messages of any channel the bot is a member of (`context` = how many, optional `user_id` sender filter).
- **DMs**: `GET /api/bot/user/{uid}/messages` — recent direct messages exchanged with a given user.

When the user says "new message for you", "check messages", or "check your inbox":

1. Identify your own bot via the agent-to-bot mapping in `contacts.json` (e.g. `senior-hexa-developer` -> `buzz`).
2. Pull recent messages from the channels relevant to you (default: the project channel `registry-graphai` and `general`).
3. Optionally pull DMs from your known contacts.
4. Surface only what is new: remember the highest `mid` you have seen and report newer messages.

## Channel-First Policy

All agent-to-agent communication goes through **channels** (e.g. `registry-graphai`), not DMs:

- The human owner follows every agent conversation in the VoceChat web UI — this is a surveillance requirement.
- Channels keep the read path simple: one `group-messages` pull per channel shows the whole conversation.
- DMs are acceptable only for genuinely private 1:1 exchanges; they are not hidden either, since the receiving bot can read them back via `user-messages`.

## Conversation Surveillance

To monitor agent conversations in real time:

1. Ensure a surveillance bot is created and added to all relevant channels.
2. Set a webhook URL on the bot pointing to the webhook receiver.
3. Run the webhook receiver to capture, log, and analyze all messages.

The surveillance receiver:
- Listens for incoming webhook POST events.
- Parses and displays each event (new message, reply, edit, delete, new user).
- Logs events to a file for later analysis.

### Surveillance use cases

- **Detect blockers**: agent posts "blocked" or "stuck" -> intervene.
- **Detect off-topic drift**: conversation moves away from the task -> redirect.
- **Detect conflicts**: two agents propose contradictory approaches -> resolve.
- **Detect unanswered questions**: a question sits without a reply for too long -> delegate.
- **Status monitoring**: track progress across agents and channels.

---

## Backend: VoceChat

VoceChat is a superlight (20 MB), open-source, self-hosted chat server written in Rust. It provides DM, group channels, replies, @mentions, file sharing, burn-after-reading messages, an open REST API, bot webhooks, and an embeddable website widget.

- Official site: <https://voce.chat>
- Documentation: <https://doc.voce.chat/>
- API Swagger: `<server-url>/api/swagger`
- GitHub: <https://github.com/Privoce/vocechat-server>

### Server Configuration

| Variable                 | Description                                        |
| ------------------------ | -------------------------------------------------- |
| `VOCECHAT_SERVER`        | Base URL of the VoceChat server (no trailing `/`) |
| `VOCECHAT_<BOT>_API_KEY` | Per-bot API key, e.g. `VOCECHAT_buzz_API_KEY`    |
| `VOCECHAT_API_KEY`       | Fallback API key when no bot identity is given    |
| `VOCECHAT_BOT_ID`        | Numeric bot user ID (optional)                    |

Store these in `.env` or export them before running scripts. Never commit API keys.

Each agent speaks as its own bot: the client's `--as <bot>` flag resolves
`VOCECHAT_<BOT>_API_KEY` (e.g. `--as buzz`, `--as hubert`). The agent-to-bot
mapping lives in `contacts.json` (the `bot` field of each agent entry).

### Authentication

#### Bot API (x-api-key)

All Bot API endpoints require the `x-api-key` header. The key is generated per-bot in Settings -> Bot & Webhook.

```
x-api-key: <your-bot-api-key>
```

#### User API (JWT)

User endpoints require a JWT bearer token obtained via login:

```
POST /api/token/login
Content-Type: application/json

{
  "credential": { "type": "email", "email": "user@example.com", "password": "..." },
  "device": "agent-client"
}
```

Response:

```json
{
  "server_id": "...",
  "token": "<jwt-access-token>",
  "refresh_token": "<refresh-token>",
  "expired_in": 3600,
  "user": { "uid": 1, "name": "Admin", "is_admin": true }
}
```

Use `Authorization: Bearer <jwt-token>`. Refresh with `POST /api/token/refresh`.

### Bot API Endpoints

All Bot API endpoints are prefixed with `/api/bot`.

#### Get bot groups (channels)

```
GET /api/bot?public_only=false
x-api-key: <key>
```

Returns an array of group objects the bot is a member of (name, gid, members, description, etc.).

#### Send message to a user (DM)

```
POST /api/bot/send_to_user/{uid}
Content-Type: text/plain
x-api-key: <key>

Hello, this is a text message.
```

#### Send message to a group (channel)

```
POST /api/bot/send_to_group/{gid}
Content-Type: text/markdown
x-api-key: <key>

**Hello** from the _agent_!
```

#### Message content types

| Content-Type          | Body format                          | Use case                     |
| --------------------- | ------------------------------------ | ---------------------------- |
| `text/plain`          | Raw text string                      | Simple text messages         |
| `text/markdown`       | Markdown string                      | Formatted messages           |
| `vocechat/file`       | JSON: `{"path": "<uploaded-path>"}`  | Files (upload first)         |
| `application/json`    | JSON: `{"to", "subject", "content"}` | Email (requires SMTP setup)  |

#### Mention users

Set the `X-Properties` header with a JSON object:

```
X-Properties: {"mentions":[<uid1>,<uid2>]}
```

#### Get user info

```
GET /api/bot/user/{uid}?uid={uid}
x-api-key: <key>
```

Returns uid, email, name, gender, language, is_admin, is_bot, avatar_updated_at, create_by.

Note: VoceChat requires the uid both as a path segment and as a query
parameter on this route (the same quirk applies to group info).

#### Get group info

```
GET /api/bot/group/{gid}?gid={gid}
x-api-key: <key>
```

Returns the same group object shape as the bot groups listing.

#### Read channel messages

```
GET /api/bot/group/{gid}/messages?context={n}&user_id={uid}
x-api-key: <key>
```

Returns the recent messages of a channel the bot is a member of. `context`
limits the number of messages (e.g. 20); `user_id` optionally filters by
sender.

#### Read DM messages

```
GET /api/bot/user/{uid}/messages?context={n}
x-api-key: <key>
```

Returns the recent direct messages exchanged with the given user.

#### Other message endpoints

The Bot API also supports `POST /api/bot/reply/{mid}` (reply to a message),
`POST /api/bot/edit/{mid}`, and `POST /api/bot/delete/{mid}`.

#### Upload a file

Two-step process:

**Step 1: Prepare**

```
POST /api/bot/file/prepare
Content-Type: application/json
x-api-key: <key>

{ "content_type": "image/png", "filename": "screenshot.png" }
```

Returns a `file_id` (UUID string).

**Step 2: Upload chunk(s)**

```
POST /api/bot/file/upload
Content-Type: application/json
x-api-key: <key>

{ "file_id": "<uuid>", "chunk_data": "<base64>", "chunk_is_last": true }
```

Returns `{ "path": "/resource/<hash>.png", "size": 1024, "hash": "...", "image_properties": { "width": 800, "height": 600 } }`.

Use the returned `path` in a `vocechat/file` content-type message.

### Webhook Events

When a webhook URL is configured for a bot, VoceChat sends `POST` requests for each event. The webhook URL must respond `200` to `GET`.

#### New message

```json
{
  "created_at": 1672048481664,
  "detail": {
    "content": "hello this is my message",
    "content_type": "text/plain",
    "expires_in": null,
    "properties": null,
    "type": "normal"
  },
  "from_uid": 7910,
  "mid": 2978,
  "target": { "gid": 2 }
}
```

`target` can be `{ "gid": N }` (group) or `{ "uid": N }` (DM).

#### Reply

```json
{
  "created_at": 1672061091917,
  "detail": {
    "content": "I want to reply to a message",
    "content_type": "text/plain",
    "mid": 2858,
    "properties": { "mentions": [] },
    "type": "reply"
  },
  "from_uid": 722,
  "mid": 2981,
  "target": { "uid": 13466 }
}
```

`detail.mid` is the message being replied to.

#### Edit

```json
{
  "created_at": 1672060767247,
  "detail": {
    "detail": {
      "content": "edited message text",
      "content_type": "text/plain",
      "properties": null,
      "type": "edit"
    },
    "mid": 2890,
    "type": "reaction"
  },
  "from_uid": 722,
  "mid": 2979,
  "target": { "uid": 13466 }
}
```

`detail.mid` is the message being edited.

#### Deletion

```json
{
  "created_at": 1672060943856,
  "detail": {
    "detail": { "type": "delete" },
    "mid": 2889,
    "type": "reaction"
  },
  "from_uid": 722,
  "mid": 2980,
  "target": { "uid": 13466 }
}
```

`detail.mid` is the deleted message's ID.

#### New user signup

When a new user signs up, the webhook receives `"newuser"` as the body.

#### AES encryption

If a 16-byte secret is set on the bot, webhook payloads are AES-encrypted. Decrypt with AES + PKCS7 unpadding to get the original JSON.

### Surveillance Setup

1. **Create a surveillance bot** in Settings -> Bot & Webhook.
2. **Add the bot to every channel** where agents communicate.
3. **Set a webhook URL** pointing to the webhook receiver script.
4. **Run the webhook receiver** to capture, log, and analyze all messages in real time.

```
[Agent A] --> posts message --> [VoceChat Server] --> webhook POST --> [Surveillance Receiver]
[Agent B] --> posts reply   --> [VoceChat Server] --> webhook POST --> [Surveillance Receiver]
                                                                         |
                                                                         v
                                                              Log file + real-time display
```

The surveillance bot can also send messages back to channels using the Bot API, enabling automated acknowledgments, intervention, status summaries, and keyword alerts.

## Python Client

A bundled Python client (`vocechat_client.py`) provides all Bot API operations and a webhook receiver. Uses only the standard library.

```bash
# List all groups the bot is in
python skills/chat/vocechat_client.py --as buzz groups

# Send a text message to a user (DM)
python skills/chat/vocechat_client.py --as buzz send-user --uid 4 --content "Hello!"

# Send a markdown message to a group (channel)
python skills/chat/vocechat_client.py --as buzz send-group --gid 2 --content "**Status**: all good" --markdown

# Read recent channel messages ("new message for you")
python skills/chat/vocechat_client.py --as hubert group-messages --gid 2 --context 20

# Read recent DMs with a user
python skills/chat/vocechat_client.py --as hubert user-messages --uid 3

# Get user info
python skills/chat/vocechat_client.py --as buzz user-info --uid 4

# Get group info
python skills/chat/vocechat_client.py --as buzz group-info --gid 1

# Start webhook receiver for surveillance (optional)
python skills/chat/vocechat_client.py webhook --port 8010

# Start webhook receiver with file logging
python skills/chat/vocechat_client.py webhook --port 8010 --log-file /tmp/vocechat_surveillance.log
```

The client can also be imported as a module:

```python
from vocechat_client import VoceChatClient

client = VoceChatClient(server="https://vocechat.example.com", api_key="xxx")
groups = client.get_groups()
client.send_to_group(gid=2, content="**Hello** agents!", markdown=True)
```

### Sending via the contact directory

To send a message using a contact name instead of a raw uid/gid:

1. Read `skills/chat/contacts.json`.
2. Look up the agent or channel by name or alias.
3. Extract the `uid` (for DMs) or `gid` (for channels).
4. Call the client with the resolved ID.

Example resolution:

```
"tell the graphai dev about the timeout issue"
  -> target: "graphai dev"
  -> contacts.json: agents -> "graphai-engineer" -> uid: 4, bot: hubert
  -> send as your own bot: --as <my-bot> send-user --uid 4 --content "the timeout issue"
```

For agent-to-agent traffic prefer the project channel over DMs (see the
Channel-First Policy): `--as <my-bot> send-group --gid 2 --content "..."`.

## Configuration via .env

The client reads from environment variables or `.env`. With multiple bots,
store one key per bot; the client's `--as <bot>` flag picks the identity:

```
VOCECHAT_SERVER=http://graphregistry.<your-domain>:3009
VOCECHAT_buzz_API_KEY=<168-hex-char-key>
VOCECHAT_HUBERT_API_KEY=<168-hex-char-key>
VOCECHAT_VICTORIA_API_KEY=<168-hex-char-key>
```

Validate the keys at any time with `scripts/test-keys.sh` — it checks the
format and live auth without ever printing key values.

`.env` is gitignored: every server that runs agents needs its own copy with
at least its local bot's key.

## Safety

- Never expose or commit the `x-api-key` or JWT tokens.
- The webhook receiver should run on a trusted network or behind a reverse proxy.
- Do not send secrets, credentials, or private data through chat messages.
- The surveillance bot should only monitor channels it has been explicitly added to.
- Respect agent privacy: log conversations for operational purposes, not for surveillance of individuals.
