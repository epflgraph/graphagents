---
description: Send a chat message to an agent or channel via natural language. E.g. /chat tell the graphai dev about the timeout issue.
agent: agentic-coding-manager
---

Parse the following natural-language chat instruction and send the message using the **chat** skill.

$ARGUMENTS

## Steps

1. **Parse the intent** using the Natural Language Intent Parsing rules in the `chat` skill.
   - Extract: target, message content, format (plain/markdown), mentions.
   - Use the content extraction rules (after "about"/"that"/"to say"/quotes/parentheses).

2. **Resolve the target** using `skills/chat/contacts.json`.
   - Match agent names, channel names, and aliases (case-insensitive).
   - DM-style verbs ("tell", "ask", "ping") prefer agents.
   - Broadcast verbs ("post", "notify", "broadcast") prefer channels.
   - If the target is not found or is ambiguous, list available contacts and ask for clarification.

3. **Send the message** using `skills/chat/vocechat_client.py`.
   - DM: `python skills/chat/vocechat_client.py send-user --uid <uid> --content "<content>"`
   - Channel: `python skills/chat/vocechat_client.py send-group --gid <gid> --content "<content>"`
   - Add `--markdown` if the message contains formatting.
   - Add `--mentions <uid> <uid>` if specific agents should be notified.

4. **Confirm the result** to the user:
   - Who the message was sent to (display name + uid/gid).
   - The message content (truncated if long).
   - The message ID returned by the server.
   - If the send failed, report the error and suggest troubleshooting.

## Examples

```
/chat tell the graphai dev about the timeout issue on /video/retrieve_url
  -> DM to GraphAI Engineer (uid=3): "the timeout issue on /video/retrieve_url"

/chat post to general: deployment complete, all tests pass
  -> Channel post to General (gid=1): "deployment complete, all tests pass"

/chat notify the engineering channel that the build passed
  -> Channel post to Engineering (gid=2): "that the build passed"

/chat ping senior-hexa-developer asking about the adapter boundary
  -> DM to Senior Hexa Developer (uid=2): "about the adapter boundary"

/chat message the graphai dev about this issue (token expired on /token)
  -> DM to GraphAI Engineer (uid=3): "token expired on /token"
```
