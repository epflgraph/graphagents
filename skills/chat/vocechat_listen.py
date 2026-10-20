# skills/chat/vocechat_listen.py
"""Polling listener for the VoceChat Bot API: wait for NEW chat messages.

Bundled with the `chat` skill and complementary to `vocechat_client.py`:
the client's read commands answer "what are the recent messages?", while
this script answers "tell me when something new arrives". It lets an agent
sit in a discussion loop and react to incoming messages without being told
to re-check its inbox after every turn.

Each watched conversation keeps a watermark: the highest message id (mid)
already reported. Every --interval seconds the script pulls the recent
messages of each target, emits only entries above the watermark (filtered
so the listening bot does not react to its own messages), and advances the
watermark. History is never replayed unless --history is given.

Usage:
  python skills/chat/vocechat_listen.py --as <me> --agent <name|uid> [options]
  python skills/chat/vocechat_listen.py --as <me> --channel <name|gid> [options]
  python skills/chat/vocechat_listen.py --as <me> --all [options]

Target (exactly one of --agent / --channel / --all is required):
  --agent NAME|UID    DMs with one agent or human (contacts.json name,
                      alias, or raw uid)
  --channel NAME|GID  One channel (contacts.json name, alias, or raw gid)
  --all               Every channel the bot is in plus DMs with every
                      contact listed in contacts.json

Options:
  --interval N        Seconds between polls (default: 10, minimum: 1)
  --once              Exit (code 0) as soon as new message(s) are printed;
                      combined with --max-wait, exit code 3 when the wait
                      expired with nothing new
  --max-wait N        Stop after N seconds no matter what (0 = keep
                      running until Ctrl+C, default)
  --history N         Also print the last N messages of each target at
                      startup (marked HISTORY, never re-alerted)
  --include-self      Do not hide my own messages
  --for-me            Channel messages only when the floor is handed to me
                      (mentions property or @my-name in the text)
  --json              Machine-readable output: one JSON object per message
                      on stdout (banner and warnings go to stderr)
  --show-claims       Also emit typing-claim messages (default: hidden)
  --bot-id N          This bot's own uid, used to filter its messages out
                      of channels; otherwise taken from VOCECHAT_BOT_ID or
                      resolved via contacts.json + agents/identities.json

Exit codes: 0 = new message(s) seen or clean stop | 1 = startup error |
3 = --once wait expired with no new messages.

Identity works exactly like the client: `--as` accepts an agent name or
call sign resolved through agents/identities.json; keys load from .env.

Known limitations:
  - The bot only sees channels it is a member of (server-side rule).
  - --all covers DM threads with contacts.json entries only; the Bot API
    cannot enumerate DM threads with unknown users.
  - At most POLL_CONTEXT messages per target per cycle are inspected; for
    very busy channels lower --interval accordingly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Make the sibling client importable regardless of the invocation directory,
# then reuse its HTTP client, .env loading and identity resolution.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vocechat_client import (
    VoceChatClient,
    load_env_file,
    lookup_identity,
    resolve_bot_credentials,
)

# Module Constant: Floor for the poll interval so tight loops cannot hammer the server.
MIN_INTERVAL_S = 1.0

# Module Constant: How many recent messages are inspected per target and poll cycle.
POLL_CONTEXT = 50

# Module Constant: Messages starting with this marker are typing claims, not content.
CLAIM_MARKER = "✍️"


#==================#
# Class Definition #
#==================#
class ListenTarget:
    """One watched conversation: a DM thread (uid) or a channel (gid).

    The watermark is the highest message id (mid) already reported for
    this target; only messages above it count as new.
    """

    # Public Method: Initialize the target with kind, conversation id, label and watermark.
    def __init__(self, kind: str, tid: int, label: str, watermark: int = 0) -> None:
        self.kind = kind          # "dm" or "group"
        self.tid = tid            # uid for DMs, gid for channels
        self.label = label        # human-readable conversation name
        self.watermark = watermark

    # Public Method: Return a short human-readable tag for banners and output.
    def tag(self) -> str:
        if self.kind == "dm":
            return f"DM with {self.label}"
        return f"#{self.label}"


class ChatListener:
    """Poll all watched targets and emit only their new messages.

    The listener owns the poll loop, the sender-name cache and the two
    output formats (human-readable text or JSON lines). Sender filtering:
    DM targets show only the contact's own messages (a DM thread has just
    two participants, so this also removes the bot's own replies without
    needing its uid); channel targets hide the bot's own messages when its
    uid is known.
    """

    # Public Method: Store the client, resolved targets and output options.
    def __init__(
        self,
        client: VoceChatClient,
        contacts: dict[str, Any],
        targets: list[ListenTarget],
        self_uid: int,
        interval: float,
        include_self: bool,
        as_json: bool,
        show_claims: bool,
        only_for_me: bool,
        listen_all: bool,
    ) -> None:
        self.client = client
        self.contacts = contacts
        self.targets = targets
        self.self_uid = self_uid          # 0 when unknown: disables channel self-filtering
        self.interval = interval
        self.include_self = include_self  # True disables all sender filtering
        self.as_json = as_json
        self.show_claims = show_claims    # False hides typing-claim machinery
        self.only_for_me = only_for_me    # channel filter: only floor handoffs to me
        self.listen_all = listen_all      # --all mode refreshes the channel set each cycle
        self._user_names: dict[int, str] = {}
        self._my_names: list[str] | None = None

    # Internal Method: Find the contact entry (agents or humans) for a uid.
    def _contact_by_uid(self, uid: int) -> tuple[str, str, dict[str, Any]] | None:
        for section in ("agents", "humans"):
            for key, entry in self.contacts.get(section, {}).items():
                if not isinstance(entry, dict):
                    continue
                try:
                    if int(entry.get("uid", -1)) == uid:
                        return section, key, entry
                except (TypeError, ValueError):
                    continue
        return None

    # Internal Method: Map a sender uid to a readable display name, cached.
    def _sender_name(self, uid: int) -> str:
        if uid in self._user_names:
            return self._user_names[uid]

        # Prefer the contact directory: it carries curated display names.
        hit = self._contact_by_uid(uid)
        if hit is not None:
            name = str(hit[2].get("display_name", "")) or f"uid={uid}"
            self._user_names[uid] = name
            return name

        # Fall back to the server profile once per unknown uid; cache the
        # fallback too so a failing lookup is not retried every message.
        name = ""
        try:
            info = self.client.get_user(uid)
            name = str(info.get("name", "") or "")
        except (RuntimeError, ValueError):
            name = ""
        self._user_names[uid] = name or f"uid={uid}"
        return self._user_names[uid]

    # Internal Method: Fetch the recent messages of one target (DM or channel).
    def _fetch(self, target: ListenTarget, context: int) -> list[dict[str, Any]]:
        if target.kind == "dm":
            return self.client.get_user_messages(uid=target.tid, context=context)
        return self.client.get_group_messages(gid=target.tid, context=context)

    # Internal Method: Convert one raw API message into the normalized output shape.
    def _normalize(
        self,
        msg: Any,
        target: ListenTarget,
        history: bool,
    ) -> dict[str, Any] | None:
        if not isinstance(msg, dict):
            return None
        try:
            mid = int(msg.get("mid", 0) or 0)
        except (TypeError, ValueError):
            return None
        if mid <= 0:
            return None

        # The messages endpoints nest payloads like webhook events do; edits
        # carry the new text one level deeper and replies tag the parent mid.
        detail = msg.get("detail") if isinstance(msg.get("detail"), dict) else {}
        dtype = str(detail.get("type", ""))
        if dtype == "edit":
            inner = detail.get("detail") if isinstance(detail.get("detail"), dict) else {}
            content = str(inner.get("content", "") or "")
            content_type = str(inner.get("content_type", "") or "")
        else:
            content = str(detail.get("content", "") or msg.get("content", "") or "")
            content_type = str(detail.get("content_type", "") or msg.get("content_type", "") or "")
        if not content:
            content = json.dumps(msg, ensure_ascii=False)
        reply_to = detail.get("mid") if dtype == "reply" else None

        try:
            from_uid = int(msg.get("from_uid", 0) or 0)
        except (TypeError, ValueError):
            from_uid = 0

        # The mentions property drives floor routing: `say --handoff` sets
        # it, and --for-me matches against it.
        props = detail.get("properties") if isinstance(detail.get("properties"), dict) else {}
        mentions = props.get("mentions") if isinstance(props.get("mentions"), list) else []

        return {
            "kind"         : target.kind,
            "target_id"    : target.tid,
            "target_name"  : target.label,
            "from_uid"     : from_uid,
            "from_name"    : self._sender_name(from_uid),
            "mid"          : mid,
            "created_at"   : msg.get("created_at", 0) or 0,
            "content_type" : content_type,
            "reply_to_mid" : reply_to,
            "content"      : content,
            "mentions"     : mentions,
            "history"      : history,
        }

    # Internal Method: Collect the @tokens that address this bot in message text.
    def _my_name_tokens(self) -> list[str]:
        if self._my_names is not None:
            return self._my_names

        # contacts.json mirrors call signs in the `bot` field and aliases
        # cover nicknames; any of them may follow an @ in a handoff line.
        tokens: list[str] = []
        hit = self._contact_by_uid(self.self_uid) if self.self_uid > 0 else None
        if hit is not None:
            entry = hit[2]
            tokens.append(str(hit[1]).lower())
            if entry.get("bot"):
                tokens.append(str(entry["bot"]).lower())
            tokens.extend(str(alias).lower() for alias in entry.get("aliases", []))
        self._my_names = tokens
        return self._my_names

    # Internal Method: Decide whether a message hands the floor to this bot.
    def _addressed_to_me(self, msg: dict[str, Any]) -> bool:
        # The mentions property is authoritative when the sender used it.
        if self.self_uid > 0:
            for uid in msg.get("mentions") or []:
                try:
                    if int(uid) == self.self_uid:
                        return True
                except (TypeError, ValueError):
                    continue

        # Text fallback for handoffs typed without the mentions property.
        content = str(msg.get("content", "")).lower()
        return any(f"@{token}" in content for token in self._my_name_tokens())

    # Internal Method: Decide whether a message passes the target's sender filter.
    def _passes_filter(self, msg: dict[str, Any], target: ListenTarget) -> bool:
        # Typing claims are protocol machinery, not conversation content:
        # a waiting agent must never wake on someone else's "typing" bubble.
        if not self.show_claims and msg["content"].startswith(CLAIM_MARKER):
            return False

        # Floor routing: in channels, wake only when the floor is handed to
        # me. DM threads are for me by definition, so they always pass.
        if self.only_for_me and target.kind != "dm" and not self._addressed_to_me(msg):
            return False

        if self.include_self:
            return True

        # In a DM thread the only interesting sender is the contact itself;
        # this filters the bot's own replies without needing its uid.
        if target.kind == "dm":
            return msg["from_uid"] == target.tid

        # In channels, drop the bot's own messages when its uid is known.
        if self.self_uid <= 0:
            return True
        return msg["from_uid"] != self.self_uid

    # Internal Method: Build the conversation origin label for a text output line.
    def _origin(self, msg: dict[str, Any]) -> str:
        if msg["kind"] == "dm":
            return f"DM with {msg['target_name']} (uid={msg['target_id']})"
        return f"#{msg['target_name']} (gid={msg['target_id']})"

    # Internal Method: Emit normalized messages to stdout as text or JSON lines.
    def _emit(self, messages: list[dict[str, Any]]) -> None:
        for msg in messages:
            if self.as_json:
                print(json.dumps(msg, ensure_ascii=False), flush=True)
                continue

            ts = msg.get("created_at") or 0
            ts_str = ""
            if ts:
                ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts / 1000))
            flag = "HISTORY " if msg["history"] else ""
            head = (
                f"[{ts_str or 'no-timestamp'}] {flag}{self._origin(msg)}"
                f" | from {msg['from_name']} (uid={msg['from_uid']})"
                f" | mid={msg['mid']}"
            )
            if msg.get("reply_to_mid"):
                head += f" (reply to mid={msg['reply_to_mid']})"
            print(head, flush=True)
            for line in msg["content"].splitlines() or [""]:
                print(f"    {line}", flush=True)

    # Public Method: Seed a target: print optional history and set the watermark.
    def prime_target(self, target: ListenTarget, history: int) -> None:
        if history > 0:
            raw = self._fetch(target, history)
            normalized = [
                m
                for m in (self._normalize(x, target, history=True) for x in raw)
                if m is not None and self._passes_filter(m, target)
            ]
            normalized.sort(key=lambda m: m["mid"])
            if normalized:
                self._emit(normalized)
                target.watermark = max(m["mid"] for m in normalized)
                return

        # Without history (or with nothing reportable) start from the newest
        # message so only messages arriving after startup are reported.
        raw = self._fetch(target, 1)
        newest = 0
        for msg in raw:
            normalized = self._normalize(msg, target, history=False)
            if normalized is not None:
                newest = max(newest, normalized["mid"])
        target.watermark = newest

    # Public Method: Run one poll cycle over all targets; return emitted count.
    def poll_cycle(self) -> int:
        total = 0
        for target in self.targets:
            try:
                raw = self._fetch(target, POLL_CONTEXT)
            except RuntimeError as exc:
                print(f"[listen] warning: {target.tag()}: {exc}", file=sys.stderr, flush=True)
                continue

            # Keep only messages above the watermark that pass the sender
            # filter, oldest first, then advance the watermark so nothing
            # is ever reported twice.
            news: list[dict[str, Any]] = []
            for msg in raw:
                normalized = self._normalize(msg, target, history=False)
                if normalized is None or normalized["mid"] <= target.watermark:
                    continue
                if not self._passes_filter(normalized, target):
                    continue
                news.append(normalized)
            if news:
                news.sort(key=lambda m: m["mid"])
                target.watermark = max(target.watermark, news[-1]["mid"])
                self._emit(news)
                total += len(news)
        return total

    # Public Method: Synchronize channel targets with the bot's current groups (--all).
    def refresh_group_targets(self) -> None:
        try:
            groups = self.client.get_groups()
        except RuntimeError as exc:
            print(f"[listen] warning: could not refresh groups: {exc}", file=sys.stderr, flush=True)
            return

        # Adopt new channels (seeded like startup targets so their history
        # is not replayed) and retire ones the bot was removed from.
        current: dict[int, dict[str, Any]] = {}
        for group in groups:
            if not isinstance(group, dict):
                continue
            try:
                gid = int(group.get("gid", 0) or 0)
            except (TypeError, ValueError):
                continue
            if gid > 0:
                current[gid] = group

        for gid, group in current.items():
            if any(t.kind == "group" and t.tid == gid for t in self.targets):
                continue
            target = ListenTarget("group", gid, str(group.get("name", "") or f"gid={gid}"))
            try:
                self.prime_target(target, history=0)
            except RuntimeError as exc:
                print(f"[listen] warning: skipping new channel {target.tag()}: {exc}", file=sys.stderr, flush=True)
                continue
            self.targets.append(target)
            print(f"[listen] + now also watching {target.tag()}", file=sys.stderr, flush=True)

        # Drop channels the bot is no longer a member of.
        self.targets = [t for t in self.targets if t.kind != "group" or t.tid in current]

    # Public Method: Print the startup banner and watched targets to stderr.
    def announce(self, once: bool, max_wait: float) -> None:
        me = f"uid={self.self_uid}" if self.self_uid > 0 else "uid unknown (channel self-filter off)"
        print(f"[listen] watching as this bot (self {me})", file=sys.stderr, flush=True)
        if self.only_for_me:
            print("[listen] floor filter: channel messages only when handed to me", file=sys.stderr, flush=True)
        for target in self.targets:
            print(f"[listen]   {target.tag()}  (watermark: mid > {target.watermark})", file=sys.stderr, flush=True)
        if once:
            mode = "exit on first new message"
        elif max_wait > 0:
            mode = f"stop after {max_wait:g}s"
        else:
            mode = "run until Ctrl+C"
        print(
            f"[listen] interval: {self.interval:g}s | mode: {mode}"
            f" | output: {'json' if self.as_json else 'text'}",
            file=sys.stderr,
            flush=True,
        )

    # Public Method: Run the poll loop and return the process exit code.
    def run(self, once: bool, max_wait: float) -> int:
        deadline = time.monotonic() + max_wait if max_wait > 0 else None
        seen_any = False

        while True:
            if self.listen_all:
                self.refresh_group_targets()
            total = self.poll_cycle()
            seen_any = seen_any or total > 0

            # --once callers (agents waiting for a reply) exit as soon as
            # anything new was printed; --max-wait bounds the total wait so
            # one tool call can never hang forever.
            if once and total:
                return 0
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return 3 if (once and not seen_any) else 0
                time.sleep(min(self.interval, remaining))
            else:
                time.sleep(self.interval)


#=========================================================================#
# Function Group: Contact directory and target resolution                 #
#=========================================================================#


# Public Function: Load the contact directory stored next to this script.
def load_contacts() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "contacts.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


# Internal Function: Collect contact entries matching a name, alias or display name.
def match_contacts(
    contacts: dict[str, Any],
    name: str,
    sections: tuple[str, ...],
) -> list[tuple[str, str, dict[str, Any]]]:
    lowered = name.strip().lower()
    exact: list[tuple[str, str, dict[str, Any]]] = []
    fuzzy: list[tuple[str, str, dict[str, Any]]] = []

    # Exact matches on key or alias win; display-name substring matches are
    # the documented fallback when the caller was less precise.
    for section in sections:
        for key, entry in contacts.get(section, {}).items():
            if not isinstance(entry, dict):
                continue
            aliases = [str(alias).lower() for alias in entry.get("aliases", [])]
            if key.lower() == lowered or lowered in aliases:
                exact.append((section, key, entry))
            elif lowered and lowered in str(entry.get("display_name", "")).lower():
                fuzzy.append((section, key, entry))
    return exact or fuzzy


# Internal Function: Describe the known contacts for resolution error messages.
def _contacts_hint(contacts: dict[str, Any]) -> str:
    agents = [key for key, _ in contacts.get("agents", {}).items()]
    humans = [key for key, _ in contacts.get("humans", {}).items()]
    channels = [key for key, _ in contacts.get("channels", {}).items()]
    parts = []
    if agents or humans:
        parts.append("agents/humans: " + ", ".join(agents + humans))
    if channels:
        parts.append("channels: " + ", ".join(channels))
    return "; ".join(parts) if parts else "contacts.json is empty or unreadable"


# Internal Function: Resolve the --agent selector (name, alias or raw uid) to a uid.
def resolve_agent_uid(contacts: dict[str, Any], selector: str) -> int:
    stripped = selector.strip()
    if stripped.isdigit():
        return int(stripped)

    # One match resolves; anything else is an error that lists the options.
    matches = match_contacts(contacts, stripped, ("agents", "humans"))
    if len(matches) == 1:
        return int(matches[0][2]["uid"])
    if len(matches) > 1:
        options = ", ".join(key for _, key, _ in matches)
        raise ValueError(f"'{selector}' is ambiguous, matching: {options}")
    raise ValueError(f"No agent or human matches '{selector}'. {_contacts_hint(contacts)}")


# Internal Function: Resolve the --channel selector (name, alias or raw gid) to a gid.
def resolve_channel_gid(contacts: dict[str, Any], selector: str) -> int:
    stripped = selector.strip()
    if stripped.isdigit():
        return int(stripped)

    matches = match_contacts(contacts, stripped, ("channels",))
    if len(matches) == 1:
        return int(matches[0][2]["gid"])
    if len(matches) > 1:
        options = ", ".join(key for _, key, _ in matches)
        raise ValueError(f"'{selector}' is ambiguous, matching: {options}")
    raise ValueError(f"No channel matches '{selector}'. {_contacts_hint(contacts)}")


# Internal Function: Return a readable label for a uid, from the contact directory.
def label_for_uid(contacts: dict[str, Any], uid: int) -> str:
    for section in ("agents", "humans"):
        for entry in contacts.get(section, {}).values():
            if not isinstance(entry, dict):
                continue
            try:
                if int(entry.get("uid", -1)) == uid:
                    return str(entry.get("display_name", "") or f"uid={uid}")
            except (TypeError, ValueError):
                continue
    return f"uid={uid}"


# Internal Function: Return a readable label for a gid, from contacts or the server.
def label_for_gid(contacts: dict[str, Any], client: VoceChatClient, gid: int) -> str:
    for entry in contacts.get("channels", {}).values():
        if not isinstance(entry, dict):
            continue
        try:
            if int(entry.get("gid", -1)) == gid:
                return str(entry.get("display_name", "") or f"gid={gid}")
        except (TypeError, ValueError):
            continue

    # Raw gid selectors are not in the directory: ask the server once.
    try:
        info = client.get_group(gid)
        name = str(info.get("name", "") or "")
    except RuntimeError:
        name = ""
    return name or f"gid={gid}"


# Internal Function: Determine this bot's own uid for channel self-filtering.
def resolve_self_uid(as_bot: str | None, cli_bot_id: int, contacts: dict[str, Any]) -> int:
    if cli_bot_id > 0:
        return cli_bot_id
    try:
        env_id = int(os.environ.get("VOCECHAT_BOT_ID", "0") or "0")
    except ValueError:
        env_id = 0
    if env_id > 0:
        return env_id

    # contacts.json mirrors call signs in the `bot` field, so the --as
    # identity (agent name or call sign) maps to the agent entry carrying
    # this bot's uid.
    if as_bot:
        identity = lookup_identity(as_bot)
        call_sign = str((identity or {}).get("call_sign", "")).strip().lower()
        wanted = as_bot.strip().lower()
        for key, entry in contacts.get("agents", {}).items():
            if not isinstance(entry, dict):
                continue
            if key.lower() == wanted or (call_sign and str(entry.get("bot", "")).lower() == call_sign):
                try:
                    return int(entry.get("uid", 0) or 0)
                except (TypeError, ValueError):
                    return 0
    return 0


# Internal Function: Build the target list from the CLI selectors and contact directory.
def build_targets(
    args: argparse.Namespace,
    client: VoceChatClient,
    contacts: dict[str, Any],
) -> list[ListenTarget]:
    if args.agent is not None:
        uid = resolve_agent_uid(contacts, args.agent)
        return [ListenTarget("dm", uid, label_for_uid(contacts, uid))]

    if args.channel is not None:
        gid = resolve_channel_gid(contacts, args.channel)
        return [ListenTarget("group", gid, label_for_gid(contacts, client, gid))]

    # --all: every channel the bot is in plus DM threads with all known
    # contacts (the Bot API cannot enumerate unknown DM threads).
    targets: list[ListenTarget] = []
    for group in client.get_groups():
        if not isinstance(group, dict):
            continue
        try:
            gid = int(group.get("gid", 0) or 0)
        except (TypeError, ValueError):
            continue
        if gid > 0:
            targets.append(ListenTarget("group", gid, str(group.get("name", "") or f"gid={gid}")))
    for section in ("agents", "humans"):
        for entry in contacts.get(section, {}).values():
            if not isinstance(entry, dict):
                continue
            try:
                uid = int(entry.get("uid", 0) or 0)
            except (TypeError, ValueError):
                continue
            if uid > 0:
                targets.append(ListenTarget("dm", uid, str(entry.get("display_name", "") or f"uid={uid}")))
    return targets


#=========================================================================#
# Function Group: Command-line interface                                  #
#=========================================================================#


# Public Function: Parse CLI arguments and run the polling listener.
def main() -> None:
    # Load .env from the working directory, then the config root, mirroring
    # the client so the listener works from any project directory.
    load_env_file()
    load_env_file(str(Path(__file__).resolve().parents[2] / ".env"))

    parser = argparse.ArgumentParser(
        description="Poll VoceChat for new messages (discussion-loop listener)",
    )
    parser.add_argument("--server", default=None, help="VoceChat server URL")
    parser.add_argument("--api-key", default=None, help="Bot API key")
    parser.add_argument(
        "--as",
        dest="as_bot",
        default=None,
        help="Agent name or call sign of the listening bot "
        "(resolved via agents/identities.json)",
    )
    parser.add_argument(
        "--bot-id",
        dest="bot_id",
        type=int,
        default=0,
        help="This bot's own uid (channel self-filter; default: auto-resolve)",
    )

    # Exactly one target selector defines what is watched.
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "--agent",
        default=None,
        help="Listen to DMs with one agent/human (name, alias or uid)",
    )
    target_group.add_argument(
        "--channel",
        default=None,
        help="Listen to one channel (name, alias or gid)",
    )
    target_group.add_argument(
        "--all",
        dest="listen_all",
        action="store_true",
        help="Listen to all my channels + DMs with all known contacts",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Seconds between polls (default: 10, minimum: 1)",
    )
    parser.add_argument(
        "--max-wait",
        dest="max_wait",
        type=float,
        default=0.0,
        help="Stop after N seconds no matter what (0 = run until Ctrl+C)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exit as soon as the first new message(s) are printed",
    )
    parser.add_argument(
        "--history",
        type=int,
        default=0,
        help="Print the last N messages of each target at startup",
    )
    parser.add_argument(
        "--include-self",
        dest="include_self",
        action="store_true",
        help="Do not hide my own messages",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="One JSON object per message on stdout (banner goes to stderr)",
    )
    parser.add_argument(
        "--show-claims",
        dest="show_claims",
        action="store_true",
        help="Also emit typing-claim messages (default: hidden)",
    )
    parser.add_argument(
        "--for-me",
        dest="only_for_me",
        action="store_true",
        help="Channel messages only when the floor is handed to me "
        "(mentions property or @my-name in the text)",
    )

    args = parser.parse_args()

    # Validate the timing options before touching the network.
    if args.interval <= 0:
        parser.error("--interval must be a positive number of seconds")
    if args.max_wait < 0:
        parser.error("--max-wait cannot be negative")
    if args.history < 0:
        parser.error("--history cannot be negative")

    interval = max(MIN_INTERVAL_S, args.interval)

    # Resolve the bot identity exactly like the client does.
    api_key = args.api_key
    if args.as_bot:
        try:
            api_key = api_key or resolve_bot_credentials(args.as_bot)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    try:
        client = VoceChatClient(server=args.server, api_key=api_key)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    contacts = load_contacts()
    try:
        targets = build_targets(args, client, contacts)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    listener = ChatListener(
        client=client,
        contacts=contacts,
        targets=targets,
        self_uid=resolve_self_uid(args.as_bot, args.bot_id, contacts),
        interval=interval,
        include_self=args.include_self,
        as_json=args.as_json,
        show_claims=args.show_claims,
        only_for_me=args.only_for_me,
        listen_all=args.listen_all,
    )

    # Never watch the bot's own DM thread: nothing can arrive there.
    if listener.self_uid > 0:
        listener.targets = [
            t for t in listener.targets if not (t.kind == "dm" and t.tid == listener.self_uid)
        ]

    # Seed watermarks (and optionally print history) before entering the
    # loop; a failure here means a bad target or permissions, which is fatal.
    try:
        for target in listener.targets:
            listener.prime_target(target, history=args.history)
    except RuntimeError as exc:
        print(f"Error: cannot initialize watch targets: {exc}", file=sys.stderr)
        sys.exit(1)

    listener.announce(once=args.once, max_wait=args.max_wait)

    try:
        code = listener.run(once=args.once, max_wait=args.max_wait)
    except KeyboardInterrupt:
        print("\n[listen] stopped.", file=sys.stderr, flush=True)
        code = 0
    sys.exit(code)


if __name__ == "__main__":
    main()
