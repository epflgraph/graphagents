# skills/chat/vocechat_speak.py
"""Human-like, turn-aware sending for the VoceChat Bot API.

Bundled with the `chat` skill. Chat has no typing indicator and no turn
control, so agents following each other blindly either talk over each other
or answer in robot lockstep. This script simulates both: it chains

  reaction jitter -> floor check -> typing claim -> typing delay -> send

into one atomic call. The floor check yields (exit 4) when another agent
holds a fresh typing claim for the same message, so two agents answering
the same question never both hit send; near-simultaneous claims are broken
deterministically (lower uid keeps the floor). The typing delay scales with
message length so replies land at a human pace instead of in bursts.

The typing claim is a tiny message starting with `✍️` (the marker lives in
vocechat_listen.CLAIM_MARKER). Claims are protocol machinery: the listener
hides them by default, and agents must never react to them. Post claims as
replies to the message being answered (--reply-to) so the yield check can
attribute them precisely.

Usage:
  python skills/chat/vocechat_speak.py --as <me> say --channel <name|gid> \
      --reply-to <mid> --content "..." [timing options]
  python skills/chat/vocechat_speak.py --as <me> say --agent <name|uid> \
      --content "..." [timing options]
  python skills/chat/vocechat_speak.py --as <me> claim --channel <name|gid> \
      --reply-to <mid> [--note "..."]

say (the normal path):
  --agent NAME|UID      Send a DM (no claim needed in a 1:1 thread; the
                        humanized delay still applies)
  --channel NAME|GID    Send to a channel (claims and floor checks apply)
  --reply-to MID        Thread claim and message under the message answered;
                        also scopes the floor check to that message
  --content TEXT        The message to send (required)
  --topic TEXT          Prefix a `[topic: …]` tag so readers know what the
                        message belongs to
  --handoff NAME|UID    Suggest the next speaker: appends a `→ over to you,
                        @<call sign>` line and @mentions them (channel
                        sends only)
  --markdown            Send as markdown
  --no-claim            Skip the typing claim (floor check still applies)
  --force               Skip the floor check entirely (e.g. moderator posts)
  --since MID           Override the floor baseline: yield to any fresh
                        claim newer than MID (default: computed)
  --reaction-min/--reaction-max   Bounds of the pre-claim reaction jitter
                        in seconds (default: 0.5 / 2.0)
  --cps N               Typing speed in characters per second (default: 40)
  --max-typing N        Upper bound of the typing delay in seconds (default: 6)
  --jitter N            Extra uniform 0..N seconds before sending (default: 1)
  --claim-ttl N         A claim older than N seconds is abandoned (default: 60)

claim (advanced: announce typing without sending; prefer atomic `say`):
  --channel NAME|GID    Channel to claim in (required)
  --reply-to MID        Thread the claim under the message being answered
  --note TEXT           Text appended after the ✍️ marker

Exit codes: 0 = sent | 1 = startup or target error | 2 = CLI misuse |
4 = yielded (someone else was writing — re-read the channel, then decide).

Identity works exactly like the client and listener: `--as` accepts an
agent name or call sign resolved through agents/identities.json; keys load
from .env.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

# Reuse the listener's selectors, constants and identity plumbing; both
# scripts live in the same skill directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vocechat_client import (
    VoceChatClient,
    load_env_file,
    resolve_bot_credentials,
)
from vocechat_listen import (
    CLAIM_MARKER,
    label_for_gid,
    label_for_uid,
    load_contacts,
    resolve_agent_uid,
    resolve_channel_gid,
    resolve_self_uid,
)

# Module Constant: Bounds of the reaction jitter (seconds) before taking the floor.
REACTION_MIN_S = 0.5
REACTION_MAX_S = 2.0

# Module Constant: Typing speed (chars/s), its cap and the extra send jitter (seconds).
TYPING_CPS = 40.0
TYPING_CAP_S = 6.0
TYPING_JITTER_S = 1.0

# Module Constant: A typing claim older than this is considered abandoned (seconds).
CLAIM_TTL_S = 60.0

# Module Constant: How many recent messages are inspected for floor checks.
FLOOR_CONTEXT = 15


#=========================================================================#
# Function Group: Floor protocol helpers                                  #
#=========================================================================#


# Internal Function: Extract the typing claims (by other bots) from a message tail.
def scan_claims(messages: list[dict[str, Any]], self_uid: int) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        detail = msg.get("detail") if isinstance(msg.get("detail"), dict) else {}
        content = str(detail.get("content", "") or msg.get("content", "") or "")
        if not content.startswith(CLAIM_MARKER):
            continue

        # Own claims never compete with the sender that placed them.
        try:
            from_uid = int(msg.get("from_uid", 0) or 0)
            mid = int(msg.get("mid", 0) or 0)
        except (TypeError, ValueError):
            continue
        if from_uid == self_uid or mid <= 0:
            continue

        # Claims posted as replies carry the answered message in detail.mid.
        reply_to = detail.get("mid") if str(detail.get("type", "")) == "reply" else None
        claims.append(
            {
                "mid"        : mid,
                "from_uid"   : from_uid,
                "created_at" : msg.get("created_at", 0) or 0,
                "reply_to"   : reply_to,
            }
        )
    return claims


# Internal Function: Return the newest non-claim message mid (the conversation point).
def newest_real_mid(messages: list[dict[str, Any]]) -> int:
    newest = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        detail = msg.get("detail") if isinstance(msg.get("detail"), dict) else {}
        content = str(detail.get("content", "") or msg.get("content", "") or "")
        if content.startswith(CLAIM_MARKER):
            continue
        try:
            newest = max(newest, int(msg.get("mid", 0) or 0))
        except (TypeError, ValueError):
            continue
    return newest


# Internal Function: Filter claims to fresh ones that actually compete for the floor.
def competing_claims(
    claims      : list[dict[str, Any]],
    reply_to    : int | None,
    since_mid   : int,
    ttl_s       : float,
) -> list[dict[str, Any]]:
    now_ms = time.time() * 1000
    competitors: list[dict[str, Any]] = []
    for claim in claims:
        # Claims older than the TTL are abandoned compositions, not a live floor.
        if claim["created_at"] and now_ms - claim["created_at"] > ttl_s * 1000:
            continue

        # Answering a specific message: only claims on that same message
        # compete. Speaking freely: any claim newer than the conversation
        # point competes, because someone is already composing.
        if reply_to is not None:
            if claim["reply_to"] == reply_to:
                competitors.append(claim)
        elif claim["mid"] > since_mid:
            competitors.append(claim)
    return competitors


# Internal Function: Post a typing claim to a channel, threaded when a target is given.
def post_claim(client: VoceChatClient, gid: int, reply_to: int | None, note: str | None) -> int:
    # The marker must start the content: detection everywhere relies on it.
    content = f"{CLAIM_MARKER} {note}" if note else f"{CLAIM_MARKER} …"
    if reply_to:
        return client.send_reply(mid=reply_to, content=content)
    return client.send_to_group(gid=gid, content=content)


# Internal Function: Describe a claim sender for yield messages.
def claimer_name(client: VoceChatClient, contacts: dict[str, Any], uid: int) -> str:
    for section in ("agents", "humans"):
        for entry in contacts.get(section, {}).values():
            if isinstance(entry, dict):
                try:
                    if int(entry.get("uid", -1)) == uid:
                        return str(entry.get("display_name", "") or f"uid={uid}")
                except (TypeError, ValueError):
                    continue
    try:
        info = client.get_user(uid)
        name = str(info.get("name", "") or "")
    except RuntimeError:
        name = ""
    return name or f"uid={uid}"


# Internal Function: Return the best @handle for handing the floor to a contact.
def handoff_handle(contacts: dict[str, Any], uid: int) -> str:
    # Agents are addressed by call sign in handoffs (mirrored in the
    # contacts entry's `bot` field); humans by display name.
    for entry in contacts.get("agents", {}).values():
        if isinstance(entry, dict):
            try:
                if int(entry.get("uid", -1)) == uid:
                    return str(entry.get("bot", "")) or str(entry.get("display_name", "")) or f"uid={uid}"
            except (TypeError, ValueError):
                continue
    for entry in contacts.get("humans", {}).values():
        if isinstance(entry, dict):
            try:
                if int(entry.get("uid", -1)) == uid:
                    return str(entry.get("display_name", "")) or f"uid={uid}"
            except (TypeError, ValueError):
                continue
    return f"uid={uid}"


#=========================================================================#
# Function Group: Speaking commands                                       #
#=========================================================================#


# Public Function: Claim the floor, wait a human typing delay, then send.
def do_say(args: argparse.Namespace, client: VoceChatClient, contacts: dict[str, Any], self_uid: int) -> int:
    started = time.monotonic()

    # Resolve exactly one destination; DMs need no floor protocol at all.
    dm_uid: int | None = None
    gid: int | None = None
    if args.agent is not None:
        dm_uid = resolve_agent_uid(contacts, args.agent)
        label = label_for_uid(contacts, dm_uid)
    else:
        gid = resolve_channel_gid(contacts, args.channel)
        label = label_for_gid(contacts, client, gid)

    # Assemble the final content up front so the typing delay reflects what
    # is actually sent, including the topic tag and the handoff line.
    content = args.content
    mentions: list[int] | None = None
    handoff_token = ""
    if args.topic:
        content = f"[topic: {args.topic}]\n\n{content}"
    if args.handoff:
        if dm_uid is not None:
            print("[speak] error: --handoff applies to channel sends only", file=sys.stderr, flush=True)
            return 1
        handoff_uid = resolve_agent_uid(contacts, args.handoff)
        mentions = [handoff_uid]
        handoff_token = handoff_handle(contacts, handoff_uid)
        content = f"{content}\n\n→ over to you, @{handoff_token}"

    # Reaction jitter first: it staggers agents that woke on the same
    # message, so the floor check below sees a settled state.
    reaction = random.uniform(args.reaction_min, args.reaction_max)
    if reaction > 0:
        time.sleep(reaction)

    claim_mid = 0
    if gid is not None and not args.no_claim and not args.force:
        tail = client.get_group_messages(gid=gid, context=FLOOR_CONTEXT)
        claims = scan_claims(tail, self_uid)

        # Baseline for free-form sends: the newest real message, so any
        # claim placed after it wins the floor. --since overrides it.
        since_mid = args.since if args.since else newest_real_mid(tail)
        competitors = competing_claims(claims, args.reply_to, since_mid, args.claim_ttl)
        if competitors:
            winner = min(competitors, key=lambda c: c["mid"])
            age = (time.time() * 1000 - winner["created_at"]) / 1000 if winner["created_at"] else 0
            print(
                f"[speak] yielded: {claimer_name(client, contacts, winner['from_uid'])}"
                f" is already composing (claim mid={winner['mid']}, {age:.0f}s ago)."
                f" Re-read the channel and decide again.",
                file=sys.stderr,
                flush=True,
            )
            return 4

        # Take the floor visibly, then re-check once: a competitor that
        # claimed in the same moment loses only to the lower uid, which
        # makes double-claims deterministic instead of a race.
        claim_mid = post_claim(client, gid, args.reply_to, None)
        if self_uid > 0:
            tail = client.get_group_messages(gid=gid, context=FLOOR_CONTEXT)
            claims = scan_claims(tail, self_uid)
            competitors = competing_claims(claims, args.reply_to, args.since if args.since else 0, args.claim_ttl)
            rivals = [c for c in competitors if c["from_uid"] < self_uid]
            if rivals:
                winner = min(rivals, key=lambda c: c["mid"])
                print(
                    f"[speak] yielded after claim tie: {claimer_name(client, contacts, winner['from_uid'])}"
                    f" claimed first (claim mid={winner['mid']}).",
                    file=sys.stderr,
                    flush=True,
                )
                return 4

    # Typing delay scales with message length, is capped, and jitters so
    # consecutive replies never land in robot lockstep.
    typing = min(args.max_typing, len(content) / args.cps)
    typing += random.uniform(0, args.jitter)
    if typing > 0:
        time.sleep(typing)

    if dm_uid is not None:
        if args.reply_to:
            sent_mid = client.send_reply(
                mid=args.reply_to,
                content=content,
                markdown=args.markdown,
            )
        else:
            sent_mid = client.send_to_user(
                uid=dm_uid,
                content=content,
                markdown=args.markdown,
            )
        destination = f"DM with {label} (uid={dm_uid})"
    else:
        if args.reply_to:
            sent_mid = client.send_reply(
                mid=args.reply_to,
                content=content,
                markdown=args.markdown,
                mentions=mentions,
            )
        else:
            sent_mid = client.send_to_group(
                gid=gid,
                content=content,
                markdown=args.markdown,
                mentions=mentions,
            )
        destination = f"#{label} (gid={gid})"

    spent = time.monotonic() - started
    thread = f" as reply to mid={args.reply_to}" if args.reply_to else ""
    claim_part = f" | claim mid={claim_mid}" if claim_mid else " | no claim"
    extras = f" | topic: {args.topic}" if args.topic else ""
    if handoff_token:
        extras += f" | handoff → @{handoff_token}"
    print(
        f"[speak] sent mid={sent_mid} to {destination}{thread}"
        f"{extras}{claim_part} | reaction+typing {spent:.1f}s",
        flush=True,
    )
    return 0


# Public Function: Announce typing in a channel without sending content yet.
def do_claim(args: argparse.Namespace, client: VoceChatClient, contacts: dict[str, Any]) -> int:
    gid = resolve_channel_gid(contacts, args.channel)
    label = label_for_gid(contacts, client, gid)
    claim_mid = post_claim(client, gid, args.reply_to, args.note)
    thread = f" as reply to mid={args.reply_to}" if args.reply_to else ""
    print(f"[speak] claimed the floor in #{label} (gid={gid}){thread}, claim mid={claim_mid}", flush=True)
    return 0


#=========================================================================#
# Function Group: Command-line interface                                  #
#=========================================================================#


# Public Function: Parse CLI arguments and dispatch to the speaking commands.
def main() -> None:
    # Load .env from the working directory, then the config root, mirroring
    # the client and listener so the sender works from any project directory.
    load_env_file()
    load_env_file(str(Path(__file__).resolve().parents[2] / ".env"))

    parser = argparse.ArgumentParser(
        description="Human-like, turn-aware VoceChat sender (floor protocol)",
    )
    parser.add_argument("--server", default=None, help="VoceChat server URL")
    parser.add_argument("--api-key", default=None, help="Bot API key")
    parser.add_argument(
        "--as",
        dest="as_bot",
        default=None,
        help="Agent name or call sign of the speaking bot "
        "(resolved via agents/identities.json)",
    )
    parser.add_argument(
        "--bot-id",
        dest="bot_id",
        type=int,
        default=0,
        help="This bot's own uid (default: auto-resolve via contacts.json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # say
    p_say = sub.add_parser(
        "say",
        help="Claim the floor, wait a human typing delay, then send",
    )
    say_targets = p_say.add_mutually_exclusive_group(required=True)
    say_targets.add_argument("--agent", default=None, help="Send a DM (name, alias or uid)")
    say_targets.add_argument("--channel", default=None, help="Send to a channel (name, alias or gid)")
    p_say.add_argument("--content", required=True, help="Message text")
    p_say.add_argument("--reply-to", dest="reply_to", type=int, default=None, help="Thread under this message mid")
    p_say.add_argument("--markdown", action="store_true")
    p_say.add_argument(
        "--topic",
        default=None,
        help="Prefix a [topic: …] tag to the message",
    )
    p_say.add_argument(
        "--handoff",
        default=None,
        help="Suggest the next speaker (name, alias or uid): appends the "
        "handoff line and @mentions them (channel sends only)",
    )
    p_say.add_argument("--no-claim", dest="no_claim", action="store_true", help="Skip the typing claim")
    p_say.add_argument("--force", action="store_true", help="Skip the floor check (moderator mode)")
    p_say.add_argument("--since", type=int, default=0, help="Floor baseline: yield to claims newer than this mid")
    p_say.add_argument("--reaction-min", dest="reaction_min", type=float, default=REACTION_MIN_S)
    p_say.add_argument("--reaction-max", dest="reaction_max", type=float, default=REACTION_MAX_S)
    p_say.add_argument("--cps", type=float, default=TYPING_CPS, help="Typing speed, chars per second")
    p_say.add_argument("--max-typing", dest="max_typing", type=float, default=TYPING_CAP_S, help="Typing delay cap (s)")
    p_say.add_argument("--jitter", type=float, default=TYPING_JITTER_S, help="Extra random delay (s)")
    p_say.add_argument("--claim-ttl", dest="claim_ttl", type=float, default=CLAIM_TTL_S, help="Claim freshness (s)")

    # claim
    p_claim = sub.add_parser("claim", help="Announce typing without sending yet")
    p_claim.add_argument("--channel", required=True, help="Channel to claim in (name, alias or gid)")
    p_claim.add_argument("--reply-to", dest="reply_to", type=int, default=None, help="Thread under this message mid")
    p_claim.add_argument("--note", default=None, help="Text appended after the ✍️ marker")

    args = parser.parse_args()

    # Validate timing inputs before touching the network.
    if args.command == "say":
        if args.reaction_min < 0 or args.reaction_max < args.reaction_min:
            parser.error("--reaction-min must be >= 0 and <= --reaction-max")
        if args.cps <= 0:
            parser.error("--cps must be positive")
        if args.max_typing < 0 or args.jitter < 0 or args.claim_ttl <= 0:
            parser.error("--max-typing/--jitter must be >= 0 and --claim-ttl > 0")

    # Resolve the bot identity exactly like the client and listener do.
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
    self_uid = resolve_self_uid(args.as_bot, args.bot_id, contacts)

    # API failures (bad target, network, permissions) must exit cleanly for
    # agents instead of dumping a traceback into their tool output.
    try:
        if args.command == "say":
            code = do_say(args, client, contacts, self_uid)
        else:
            code = do_claim(args, client, contacts)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    sys.exit(code)


if __name__ == "__main__":
    main()
