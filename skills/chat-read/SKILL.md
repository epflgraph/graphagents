---
name: chat-read
description: Read a new incoming chat message from another service. Use when the user asks to check for new messages, notify about incoming chat, or process unread messages in .opencode/chat/.
---

# Inter-Service Chat Read / Notify

Check the local service's inbox (its own folder under `.opencode/chat`) for incoming messages from other services and mark them as read.

## What to look for

- Only process files with status `_[UNREAD]` in the filename.
- Ignore files with status `_[READ]` or `_[POSTED]`.
- In principle there should be at most one `_[UNREAD]` message at a time, but if more exist, read the newest by filename timestamp and report any additional unread messages.

## Filename convention

```
.opencode/chat/<service-dev-representative>/YYYY-MM-DD_HHhMMm_[<REMOTE-SERVICE>]_[UNREAD]_<title>.md
```

## How to find unread messages

- Search the `.opencode/chat` folder recursively for files whose name literally contains `_[UNREAD]_`.
- **Important:** square brackets are special in most glob engines. A pattern like `**/*_[UNREAD]_*.md` will **not** match the literal string `[UNREAD]`; it will be interpreted as a character class matching one of `U`, `N`, `R`, `E`, or `D`.
- Prefer a shell `find` with escaped brackets:
  ```bash
  find .opencode/chat -type f -name '*_\[UNREAD\]_*.md'
  ```
- Alternatively, list the directory contents and filter for the literal substring `_[UNREAD]_`.

## Workflow

1. List files in the local inbox folder using a search method that does not interpret square brackets as glob character classes (see "How to find unread messages" above).
2. Identify the `_[UNREAD]` file (or files).
3. Read the newest unread message.
4. Summarize the message to the user, including:
   - sender service (from `[<REMOTE-SERVICE>]`)
   - subject (level-1 heading)
   - key points and any requests
5. After reading, rename the file from `_[UNREAD]` to `_[READ]` so it is not processed again. In the rename command, escape the literal brackets the same way as for searching.
6. If there are additional unread messages, list them and ask whether to read them next.

## When there are no unread messages

Inform the user clearly that the inbox is empty.

## Safety

- Do not read files outside `.opencode/chat` for this purpose.
- Do not delete chat files.
- Do not modify the message body; only change the filename status token.
