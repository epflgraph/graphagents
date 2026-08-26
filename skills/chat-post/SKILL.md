---
name: chat-post
description: Post an inter-service chat message to another service's inbox under .opencode/chat/. Use when the agent needs to send a question, update, or response to a remote service team, or when the user asks to post/notify another service.
---

# Inter-Service Chat Post

Post a markdown message to a target service's chat inbox. The chat lives under `.opencode/chat/<target-service-folder>/` and follows the naming convention:

```
.opencode/chat/<target>/YYYY-MM-DD_HHhMMm_[<SOURCE-SERVICE>]_[POSTED]_<title>.md
```

- `<target>`: the folder name of the remote service (e.g. `graphai-dev`, `data-pipeline-dev`). This is the "private chat" channel for that service.
- `<SOURCE-SERVICE>`: the local repo root folder name (e.g. `graphregistry`). One per repo checkout.
- `<title>`: a short, URL-safe title derived from the message subject.

## When to use

- The user asks to notify / message / write to another service.
- You need to escalate a question, report a bug, or share a result with a remote service.
- You are responding to a previously read message and want to reply to the originating service.

## How to post

1. Determine the target service folder under `.opencode/chat/`.
2. Create the file using the current UTC/local time in the timestamp.
3. Use `POSTED` status in the filename because the filesystem is not actually synchronized across machines.
4. Write a concise markdown message with a level-1 heading as the subject and any needed context, reproduction steps, questions, or decisions.
5. Do not modify existing chat files unless explicitly asked.

## Filename rules

- Date/time: `YYYY-MM-DD_HHhMMm_`
- Source token: `[<SOURCE-SERVICE>]` in uppercase, e.g. `[GRAPHREGISTRY]`
- Status: `[POSTED]`
- Title: lowercase, words joined by underscores, stripped of special chars, e.g. `video_get_file_client_hang.md`
- Example: `.opencode/chat/graphai-dev/2026-07-01_09h03m_[GRAPHREGISTRY]_[POSTED]_video_get_file_client_hang.md`

## Template

```markdown
# <Subject>

Hi <target service> team,

<Message body>

## Context / Reproduction

...

## Request

...

Thanks!
```

## Safety

- Do not post to a target folder that does not exist; ask the user to confirm the channel name.
- Do not post secrets, credentials, or private config values.
- Keep messages focused on a single issue or decision.
