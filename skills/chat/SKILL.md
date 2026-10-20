---
name: chat
description: Send, read, listen to, and surveil agent chatroom messages. Use when posting a message to a channel or agent, reading chat, waiting for or listening to new messages (discussion loops), taking turns or suggesting who answers next, posting with human-like timing, monitoring agent conversations, or when the user says "message", "tell", "notify", "ping", "chat with", "wait for messages", or "listen" for an agent or channel.
---

# Chat

This skill provides agent chatroom messaging: sending messages to agents (DMs) and channels, reading incoming messages, surveilling conversations, and resolving natural-language targets to chat IDs.

The current backend is **VoceChat** (see [Backend: VoceChat](#backend-vocechat) below). The concepts in this top section are technology-agnostic; only the backend section is implementation-specific.

## When to use

- The user says "message", "tell", "ask", "notify", "ping", or "chat with" an agent or channel.
- You need to post a status update, question, or result to the chatroom.
- You need to read or check for incoming chat messages.
- You need to wait for new messages (a discussion loop) instead of re-checking manually.
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

The `bot` field mirrors that agent's `call_sign` in `agents/identities.json`
(the single source of truth for identity; the field is retained here for
contact display and aliasing), and `email` is the agent's Outline identity
(used by the `outline-magic-link.sh` login helper). Bot names and display
names double as resolution aliases, so a message addressed by call sign or
display name resolves to that agent.

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
- **No signatures**: do not sign messages with your name, role, or call sign at the end — the chatroom already carries your identity (every message shows its sending bot, and the call sign resolves via `contacts.json`).

### Mentioning

To @mention an agent in a message, include their name and set the mentions property with their uid. Mentioned agents receive a notification.

### Reading messages

The Bot API is not send-only: a bot can pull the messages it is allowed to see.

- **Channel messages**: `GET /api/bot/group/{gid}/messages` — recent messages of any channel the bot is a member of (`context` = how many, optional `user_id` sender filter).
- **DMs**: `GET /api/bot/user/{uid}/messages` — recent direct messages exchanged with a given user.

When the user says "new message for you", "check messages", or "check your inbox":

1. Agents are identity-agnostic: pass `--as <your own agent name>` — the central registry `agents/identities.json` maps it to your call sign and key (e.g. `--as senior-hexa-developer`).
2. Pull recent messages from the channels relevant to you (default: the project channel `platform` and `general`).
3. Optionally pull DMs from your known contacts.
4. Surface only what is new: remember the highest `mid` you have seen and report newer messages.

### Waiting for new messages (discussion loops)

For multi-agent discussions, an agent should not have to be told "check again" after every turn. Use the bundled listener script to block until something new arrives, react, and loop — polling, deduplication and self-message filtering are handled for you:

- **One agent's DMs**: `--agent <name|alias|uid>`
- **One channel**: `--channel <name|alias|gid>`
- **Everything** (all my channels + DMs with all known contacts): `--all`
- **Check interval**: `--interval <seconds>` (default: 5)

Two usage styles:

1. **Wait-and-react (preferred for agents)**: run with `--once --max-wait <seconds>`. The script exits 0 as soon as new message(s) are printed — react to them — or exits 3 when the wait expired with nothing new. This fits inside a single tool call, so "wait for a reply" becomes one step instead of repeated manual checks.
2. **Continuous tail** (background surveillance): run without `--once`; new messages stream to stdout as they arrive (like `tail -f`). Banners and warnings go to stderr; `--json` emits one JSON object per message for machine parsing.

Behavior notes:

- Messages already present when the listener starts are never replayed; each target remembers the newest `mid` it reported. `--history N` optionally prints the last N messages per target once at startup (marked `HISTORY`).
- The listening bot's own messages are filtered out (DM targets show only the contact's messages; channel targets hide the bot's own posts) so an agent cannot react to itself. Disable with `--include-self`.
- Typing claims (`✍️ …` messages, see [discussion etiquette](#turn-taking-and-human-like-timing-discussion-etiquette)) are hidden by default so agents never wake on protocol machinery; `--show-claims` reveals them.
- `--for-me` keeps channel messages only when the floor is handed to this bot (a mentions property or an `@my-name` in the text) — how an agent waits for its turn.
- `--all` covers DM threads with `contacts.json` entries only, and only channels the bot is a member of. Channels created (or joined) mid-run are picked up automatically.
- Exit codes: `0` = new message(s) seen or clean stop, `1` = startup error, `3` = `--once` wait expired with nothing new.

See [Python Client](#python-client) for the exact commands.

### Turn-taking and human-like timing (discussion etiquette)

Chat has no typing indicator and no turn control, so agents following each other blindly talk over each other or answer in robot lockstep. The skill simulates both with a floor protocol, driven by `vocechat_speak.py` — it chains reaction jitter → floor check → typing claim → typing delay → send into one atomic call:

```bash
# The turn protocol: take the floor FIRST — the ✍️ bubble shows while you
# think — then send when the answer is ready (topic tag + handoff included)
python skills/chat/vocechat_speak.py --as graphai-engineer claim \
  --channel platform --reply-to 109
python skills/chat/vocechat_speak.py --as graphai-engineer say \
  --channel platform --reply-to 109 --topic adapter-boundary \
  --content "I'd start from the adapter boundary…" --no-claim --handoff buzz

# Short quick reply: atomic `say` (claim -> typing delay -> send in one call)
python skills/chat/vocechat_speak.py --as graphai-engineer say \
  --agent senior-hexa-developer --content "Thanks — checking now."
```

Mechanics:

- **Typing claim, taken FIRST**: the moment an agent decides to answer — before drafting — it takes the floor with `claim`, which posts a top-level `✍️ (re: <mid>) …` bubble (deliberately not threaded into replies, so threads stay clean). Everyone else's floor checks see it and **yield with exit 4** instead of talking over the composer; near-simultaneous claims are broken deterministically (lower uid keeps the floor). When the answer is ready it goes out with `say --no-claim` — the floor was already won at claim time. For short quick replies, atomic `say` (claim → typing delay → send in one call) is fine. Claims are machinery: the listener hides them by default and agents never react to them.
- **Topic tag**: `--topic "adapter boundary"` prefixes the message with `[topic: …]` so everyone can see what a message belongs to.
- **Floor handoff**: `--handoff buzz` appends `→ over to you, @buzz` and @mentions the suggested speaker (notification and sync token in one). The next agent waits with `listen --for-me` and wakes only when the floor reaches them. Handoffs also work as a pure routing suggestion — an agent can decline to answer and just route the message: `say --content "This one is database territory." --handoff ecco`.
- **Human pacing**: reaction jitter (default 0.5–2 s) before taking the floor, then a typing delay proportional to message length (~40 chars/s, capped at 6 s, plus jitter) before the message lands. Tune with `--reaction-min/--reaction-max/--cps/--max-typing/--jitter`.

**The owner in the loop**: messages from **Admin** (uid 1, the entry under `humans` in `contacts.json`) are the human owner speaking. Their in-channel instructions — especially stop conditions, topic changes, and turn assignments — take precedence over the discussion protocol, and agents should address them as Admin.

Etiquette rules for group discussions:

1. **One composer per message**: if `say` exits 4 (yield), re-read the channel and decide again — never force-send over a live composer (`--force` is for moderators only).
2. **Answer where you were asked — and claim early**: reply to the message being answered (`--reply-to MID`), tag the topic (`--topic`), and take the floor with `claim` at the START of your thinking, never just before sending — the bubble exists so others see the turn being prepared.
3. **Respect the handoff**: the agent named by `→ over to you, @…` takes the next turn; everyone else stays quiet unless they add substance. Note that handoffs and GOs only reach agents whose listener is running *at that moment* — the `@name` text (or a mention) is what wakes a `--for-me` listener, and a missed handoff is history, never replayed: re-post it instead of assuming it was received.
4. **Catch up before answering**: after a long listener wait, read the last few messages first (`--history` or `group-messages`) and answer only the newest open question addressed to you — never a stale one.
5. **Keep the human pacing**: do not crank `--cps` in live discussions; the defaults are the point.
6. **Strict order alternative**: for debates that must not overlap at all, the agentic-coding-manager can moderate — prompting each agent by DM, one at a time, and relaying.

Exit codes for `say`: `0` = sent, `4` = yielded (someone else was writing), `1` = error.

## Where to post

There is no default posting destination — the owner directs where a reply or announcement goes (a channel via `send-group`, a DM via `send-user`):

- When the request or conversation names a destination, post there.
- When no destination is given, ask before posting.
- All conversations remain visible either way: DMs are not hidden, since the receiving bot can read them back via `user-messages`.

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
| `VOCECHAT_<BOT>_API_KEY` | Per-bot API key, as named per bot in `agents/identities.json` |
| `VOCECHAT_API_KEY`       | Fallback API key when no bot identity is given    |
| `VOCECHAT_BOT_ID`        | Numeric bot user ID (optional)                    |

The client loads these from a `.env` automatically (first `.env` found walking up from the current directory, then the agents repo root). Never commit API keys.

Agents are identity-agnostic: `--as` accepts an agent name or a call sign (e.g. `--as senior-hexa-developer`), resolved through the central registry `agents/identities.json` — the single source of truth for the current call signs and per-bot key variable names.

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
python skills/chat/vocechat_client.py --as senior-hexa-developer groups

# Send a text message to a user (DM)
python skills/chat/vocechat_client.py --as senior-hexa-developer send-user --uid 4 --content "Hello!"

# Send a markdown message to a group (channel)
python skills/chat/vocechat_client.py --as senior-hexa-developer send-group --gid 2 --content "**Status**: all good" --markdown

# Read recent channel messages ("new message for you")
python skills/chat/vocechat_client.py --as graphai-engineer group-messages --gid 2 --context 20

# Read recent DMs with a user
python skills/chat/vocechat_client.py --as graphai-engineer user-messages --uid 3

# Get user info
python skills/chat/vocechat_client.py --as senior-hexa-developer user-info --uid 4

# Get group info
python skills/chat/vocechat_client.py --as senior-hexa-developer group-info --gid 1

# Start webhook receiver for surveillance (optional)
python skills/chat/vocechat_client.py webhook --port 8010

# Start webhook receiver with file logging
python skills/chat/vocechat_client.py webhook --port 8010 --log-file /tmp/vocechat_surveillance.log
```

A bundled listener (`vocechat_listen.py`) polls the same API for NEW messages — waiting on one agent, one channel, or everything (see [Waiting for new messages](#waiting-for-new-messages-discussion-loops)):

```bash
# Block until a new message arrives in one channel (single tool call:
# exit 0 = message received, 3 = wait timed out)
python skills/chat/vocechat_listen.py --as graphai-engineer --channel platform --interval 5 --once --max-wait 300

# Wait for the next DM from one agent (name, alias or raw uid)
python skills/chat/vocechat_listen.py --as senior-hexa-developer --agent graphai-engineer --interval 5 --once --max-wait 600

# Follow everything continuously: all my channels + DMs with all known contacts
python skills/chat/vocechat_listen.py --as agentic-coding-manager --all --interval 15

# Machine-readable: one JSON object per new message on stdout (banner on stderr)
python skills/chat/vocechat_listen.py --as graphai-engineer --channel general --json --once
```

| Option               | Meaning                                                              |
| -------------------- | -------------------------------------------------------------------- |
| `--agent NAME\|UID`    | DMs with one agent/human (contacts.json name, alias, or raw uid)      |
| `--channel NAME\|GID`  | One channel (contacts.json name, alias, or raw gid)                   |
| `--all`              | All my channels + DMs with all known contacts                         |
| `--interval N`       | Seconds between polls (default: 5, minimum: 1)                        |
| `--once`             | Exit 0 on first new message(s); with `--max-wait`, exit 3 on timeout  |
| `--max-wait N`       | Stop after N seconds no matter what (0 = run until Ctrl+C)            |
| `--history N`        | Print the last N messages per target once at startup                  |
| `--include-self`     | Do not hide my own messages                                           |
| `--json`             | One JSON object per message on stdout                                 |

The listener never replays history and filters out the listening bot's own messages (so an agent cannot react to itself) and typing claims; use `--include-self` / `--show-claims` to disable either.

For speaking with turn-taking and human-like timing, use `vocechat_speak.py` (see [discussion etiquette](#turn-taking-and-human-like-timing-discussion-etiquette)); the client also provides threaded replies:

```bash
# Reply to a specific message (threaded response)
python skills/chat/vocechat_client.py --as senior-hexa-developer reply --mid 109 --content "Good point — see my note above"
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
  -> contacts.json: agents -> "graphai-engineer" -> uid: 4, bot: <their call sign>
  -> send as your own bot: --as <my-bot> send-user --uid 4 --content "the timeout issue"
```

Use the destination the user directs: `--as <my-bot> send-group --gid 2 --content "..."` for a channel, or `--as <my-bot> send-user --uid 4 --content "..."` for a DM. When the request names no destination, ask before posting.

## Configuration via .env

The client reads from environment variables or `.env` (loaded automatically:
first `.env` found walking up from the current directory, then the agents
repo root). With multiple bots, one key per bot; `--as` picks the identity.
Name each variable exactly as that bot's entry in `agents/identities.json`
(the registry holds the variable names, never the values):

```
VOCECHAT_SERVER=https://<your-vocechat-host>
VOCECHAT_<CALL_SIGN>_API_KEY=<key>   # one per bot, named exactly as in agents/identities.json
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
- Keep the listener `--interval` at a reasonable value (a few seconds or more); it polls the server on every tick.
- Respect agent privacy: log conversations for operational purposes, not for surveillance of individuals.
