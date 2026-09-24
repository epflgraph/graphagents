# skills/chat/vocechat_client.py
"""VoceChat Bot API client and webhook receiver for conversation surveillance.

Bundled with the `chat` skill. Provides the VoceChat backend implementation
for sending messages, querying users/groups, reading recent messages, and
receiving webhook events.

Usage:
  python vocechat_client.py --as spike groups
  python vocechat_client.py --as spike send-user --uid 4 --content "Hello!"
  python vocechat_client.py --as spike send-group --gid 2 --content "**Status**" --markdown
  python vocechat_client.py --as hubert group-messages --gid 2 --context 20
  python vocechat_client.py --as hubert user-messages --uid 3
  python vocechat_client.py --as spike user-info --uid 4
  python vocechat_client.py --as spike group-info --gid 1
  python vocechat_client.py webhook --port 8010
  python vocechat_client.py webhook --port 8010 --log-file /tmp/vocechat.log

Identity:
  Each agent speaks as its own bot. `--as spike` resolves the API key from
  VOCECHAT_SPIKE_API_KEY, `--as hubert` from VOCECHAT_HUBERT_API_KEY, etc.
  Without `--as` the client falls back to VOCECHAT_API_KEY.

Environment variables (or .env file):
  VOCECHAT_SERVER          Base URL of the VoceChat server
  VOCECHAT_<BOT>_API_KEY   Per-bot API key (e.g. VOCECHAT_SPIKE_API_KEY)
  VOCECHAT_API_KEY         Fallback API key when no --as is given
  VOCECHAT_BOT_ID          Bot user ID (optional)
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


#==================#
# Class Definition #
#==================#
class VoceChatClient:
    """Client for the VoceChat Bot REST API.

    Wraps all bot endpoints: group listing, messaging, user/group info,
    and file uploads. Uses only the standard library.
    """

    # Internal Function: Build the full URL for an API path.
    def _url(self, path: str) -> str:
        return f"{self.server.rstrip('/')}/api/bot{path}"

    # Internal Function: Perform an HTTP request and return parsed JSON or text.
    def _request(
        self,
        method: str,
        path: str,
        body: str | bytes | None = None,
        content_type: str = "application/json",
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        headers = {"x-api-key": self.api_key, "Content-Type": content_type}
        if extra_headers:
            headers.update(extra_headers)

        data = None
        if body is not None:
            if isinstance(body, str):
                data = body.encode("utf-8")
            else:
                data = body

        req = Request(self._url(path), data=data, headers=headers, method=method)

        # Send the request and read the response.
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise RuntimeError(
                f"VoceChat API error {exc.code} on {method} {path}: {detail}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Cannot reach VoceChat server at {self.server}: {exc.reason}"
            ) from exc

        if not raw:
            return None

        text = raw.decode("utf-8", errors="replace")

        # Try to parse JSON, fall back to raw text.
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return text

    # Public Method: Initialize the client with server URL and API key.
    def __init__(
        self,
        server: str | None = None,
        api_key: str | None = None,
        bot_id: int | None = None,
        timeout: int = 30,
    ) -> None:
        self.server = server or os.environ.get("VOCECHAT_SERVER", "")
        self.api_key = api_key or os.environ.get("VOCECHAT_API_KEY", "")
        self.bot_id = bot_id or int(os.environ.get("VOCECHAT_BOT_ID", "0") or "0")
        self.timeout = timeout

        if not self.server:
            raise ValueError(
                "VOCECHAT_SERVER is not set. Set it in .env or pass --server."
            )
        if not self.api_key:
            raise ValueError(
                "No API key: pass --as <bot> (resolves VOCECHAT_<BOT>_API_KEY), "
                "set VOCECHAT_API_KEY in .env, or pass --api-key."
            )

    # Public Method: Get all groups (channels) the bot is a member of.
    def get_groups(self, public_only: bool = False) -> list[dict[str, Any]]:
        result = self._request("GET", f"?public_only={'true' if public_only else 'false'}")
        if isinstance(result, list):
            return result
        return []

    # Public Method: Send a text or markdown message to a user (DM).
    def send_to_user(
        self,
        uid: int,
        content: str,
        markdown: bool = False,
        mentions: list[int] | None = None,
    ) -> int:
        content_type = "text/markdown" if markdown else "text/plain"
        extra_headers: dict[str, str] = {}
        if mentions:
            extra_headers["X-Properties"] = json.dumps({"mentions": mentions})
        result = self._request(
            "POST",
            f"/send_to_user/{uid}",
            body=content,
            content_type=content_type,
            extra_headers=extra_headers,
        )
        return int(result) if result is not None else 0

    # Public Method: Send a text or markdown message to a group (channel).
    def send_to_group(
        self,
        gid: int,
        content: str,
        markdown: bool = False,
        mentions: list[int] | None = None,
    ) -> int:
        content_type = "text/markdown" if markdown else "text/plain"
        extra_headers: dict[str, str] = {}
        if mentions:
            extra_headers["X-Properties"] = json.dumps({"mentions": mentions})
        result = self._request(
            "POST",
            f"/send_to_group/{gid}",
            body=content,
            content_type=content_type,
            extra_headers=extra_headers,
        )
        return int(result) if result is not None else 0

    # Public Method: Get information about a user by their UID.
    # VoceChat requires the uid both as a path segment and as a query
    # parameter: the route is /user/{uid} but the handler reads the query.
    def get_user(self, uid: int) -> dict[str, Any]:
        result = self._request("GET", f"/user/{uid}?uid={uid}")
        if isinstance(result, dict):
            return result
        return {}

    # Public Method: Get information about a group by its GID.
    # VoceChat requires the gid both as a path segment and as a query
    # parameter: the route is /group/{gid} but the handler reads the query.
    def get_group(self, gid: int) -> dict[str, Any]:
        result = self._request("GET", f"/group/{gid}?gid={gid}")
        if isinstance(result, dict):
            return result
        return {}

    # Public Method: Get recent messages of a group (channel) the bot is a
    # member of. `context` limits the number of messages returned and
    # `user_id` filters by sender uid. This is the pull-based read path
    # behind "new message for you".
    def get_group_messages(
        self,
        gid: int,
        context: int | None = None,
        user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        path = f"/group/{gid}/messages"
        params: list[str] = []

        # Optional pagination and sender filters as query parameters.
        if context is not None:
            params.append(f"context={context}")
        if user_id is not None:
            params.append(f"user_id={user_id}")
        if params:
            path += "?" + "&".join(params)

        result = self._request("GET", path)
        if isinstance(result, list):
            return result
        return []

    # Public Method: Get recent DM messages exchanged with a user.
    # `context` limits the number of messages returned.
    def get_user_messages(
        self,
        uid: int,
        context: int | None = None,
    ) -> list[dict[str, Any]]:
        path = f"/user/{uid}/messages"

        # Optional pagination as a query parameter.
        if context is not None:
            path += f"?context={context}"

        result = self._request("GET", path)
        if isinstance(result, list):
            return result
        return []

    # Public Method: Prepare a file upload and return the file_id (UUID).
    def prepare_upload(self, content_type: str, filename: str) -> str:
        body = json.dumps({"content_type": content_type, "filename": filename})
        result = self._request(
            "POST", "/file/prepare", body=body, content_type="application/json"
        )
        return str(result) if result else ""

    # Public Method: Upload a file chunk and return the stored path.
    def upload_file(
        self, file_id: str, chunk_data: bytes, chunk_is_last: bool = True
    ) -> dict[str, Any]:
        body = json.dumps(
            {
                "file_id": file_id,
                "chunk_data": base64.b64encode(chunk_data).decode("ascii"),
                "chunk_is_last": chunk_is_last,
            }
        )
        result = self._request(
            "POST", "/file/upload", body=body, content_type="application/json"
        )
        if isinstance(result, dict):
            return result
        return {}

    # Public Method: Upload an entire file in one chunk and return the path.
    def upload_file_simple(self, file_path: str, content_type: str) -> str:
        path = Path(file_path)
        data = path.read_bytes()
        file_id = self.prepare_upload(content_type, path.name)
        if not file_id:
            raise RuntimeError("Failed to prepare file upload")
        result = self.upload_file(file_id, data, chunk_is_last=True)
        return result.get("path", "")

    # Public Method: Send a file message to a user after uploading.
    def send_file_to_user(self, uid: int, file_path: str, content_type: str) -> int:
        stored_path = self.upload_file_simple(file_path, content_type)
        body = json.dumps({"path": stored_path})
        result = self._request(
            "POST",
            f"/send_to_user/{uid}",
            body=body,
            content_type="vocechat/file",
        )
        return int(result) if result is not None else 0

    # Public Method: Send a file message to a group after uploading.
    def send_file_to_group(self, gid: int, file_path: str, content_type: str) -> int:
        stored_path = self.upload_file_simple(file_path, content_type)
        body = json.dumps({"path": stored_path})
        result = self._request(
            "POST",
            f"/send_to_group/{gid}",
            body=body,
            content_type="vocechat/file",
        )
        return int(result) if result is not None else 0


#=========================================================================#
# Function Group: Webhook event parsing and formatting                    #
#=========================================================================#


# Internal Function: Parse a raw webhook payload into a structured event dict.
def parse_webhook_event(raw_body: bytes) -> dict[str, Any]:
    """Parse a VoceChat webhook payload into a structured event dictionary."""
    text = raw_body.decode("utf-8", errors="replace")

    # Handle the "newuser" plain-text signal.
    if text.strip() == "newuser":
        return {"type": "newuser", "raw": text}

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"type": "unknown", "raw": text}

    detail = data.get("detail", {})

    # Determine event type from the nested detail structure.
    if isinstance(detail, dict):
        inner_type = detail.get("type", "")

        if inner_type == "normal":
            return {
                "type": "message",
                "mid": data.get("mid"),
                "from_uid": data.get("from_uid"),
                "target": data.get("target", {}),
                "content": detail.get("content", ""),
                "content_type": detail.get("content_type", "text/plain"),
                "created_at": data.get("created_at"),
                "properties": detail.get("properties"),
                "expires_in": detail.get("expires_in"),
            }

        if inner_type == "reply":
            return {
                "type": "reply",
                "mid": data.get("mid"),
                "from_uid": data.get("from_uid"),
                "target": data.get("target", {}),
                "content": detail.get("content", ""),
                "content_type": detail.get("content_type", "text/plain"),
                "reply_to_mid": detail.get("mid"),
                "created_at": data.get("created_at"),
                "properties": detail.get("properties"),
            }

        if inner_type == "edit":
            inner = detail.get("detail", {})
            return {
                "type": "edit",
                "mid": data.get("mid"),
                "from_uid": data.get("from_uid"),
                "target": data.get("target", {}),
                "edited_mid": detail.get("mid"),
                "new_content": inner.get("content", ""),
                "content_type": inner.get("content_type", "text/plain"),
                "created_at": data.get("created_at"),
            }

        if inner_type == "reaction":
            inner = detail.get("detail", {})
            reaction_type = inner.get("type", "")
            if reaction_type == "delete":
                return {
                    "type": "delete",
                    "mid": data.get("mid"),
                    "from_uid": data.get("from_uid"),
                    "target": data.get("target", {}),
                    "deleted_mid": detail.get("mid"),
                    "created_at": data.get("created_at"),
                }
            if reaction_type == "edit":
                return {
                    "type": "edit",
                    "mid": data.get("mid"),
                    "from_uid": data.get("from_uid"),
                    "target": data.get("target", {}),
                    "edited_mid": detail.get("mid"),
                    "new_content": inner.get("content", ""),
                    "content_type": inner.get("content_type", "text/plain"),
                    "created_at": data.get("created_at"),
                }

    return {"type": "unknown", "raw": text}


# Internal Function: Format a parsed webhook event into a human-readable string.
def format_event(event: dict[str, Any]) -> str:
    """Format a parsed webhook event for terminal display."""
    etype = event.get("type", "unknown")
    ts = event.get("created_at")
    ts_str = ""
    if ts:
        ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts / 1000))

    target = event.get("target", {})
    target_str = ""
    if "gid" in target:
        target_str = f"group#{target['gid']}"
    elif "uid" in target:
        target_str = f"user#{target['uid']}"

    if etype == "message":
        lines = [
            f"[{ts_str}] MESSAGE  from={event.get('from_uid')}  to={target_str}",
            f"  mid={event.get('mid')}  type={event.get('content_type')}",
            f"  {event.get('content', '')}",
        ]
        return "\n".join(lines)

    if etype == "reply":
        lines = [
            f"[{ts_str}] REPLY    from={event.get('from_uid')}  to={target_str}",
            f"  mid={event.get('mid')}  reply_to={event.get('reply_to_mid')}",
            f"  {event.get('content', '')}",
        ]
        return "\n".join(lines)

    if etype == "edit":
        lines = [
            f"[{ts_str}] EDIT     from={event.get('from_uid')}  to={target_str}",
            f"  edited_mid={event.get('edited_mid')}",
            f"  new: {event.get('new_content', '')}",
        ]
        return "\n".join(lines)

    if etype == "delete":
        lines = [
            f"[{ts_str}] DELETE   from={event.get('from_uid')}  to={target_str}",
            f"  deleted_mid={event.get('deleted_mid')}",
        ]
        return "\n".join(lines)

    if etype == "newuser":
        return f"[{ts_str}] NEWUSER  {event.get('raw', '')}"

    return f"[{ts_str}] UNKNOWN  {event.get('raw', '')}"


#=========================================================================#
# Function Group: Webhook receiver server                                 #
#=========================================================================#


# Internal Function: Create a request handler class bound to a log file path.
def _make_handler(log_file: str | None):
    """Create a BaseHTTPRequestHandler subclass that logs VoceChat webhook events."""

    class WebhookHandler(BaseHTTPRequestHandler):
        # Public Method: Respond 200 to GET so VoceChat accepts the webhook URL.
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        # Public Method: Parse and log incoming webhook POST events.
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length > 0 else b""

            event = parse_webhook_event(raw_body)
            formatted = format_event(event)

            print(formatted, flush=True)

            # Append to log file if configured.
            if log_file:
                try:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(formatted + "\n\n")
                except OSError as exc:
                    print(f"  [warn] could not write log: {exc}", flush=True)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, fmt, *args):
            pass

    return WebhookHandler


# Public Function: Start the webhook receiver HTTP server.
def run_webhook_server(port: int = 8010, log_file: str | None = None) -> None:
    """Start an HTTP server that receives VoceChat webhook events."""
    handler = _make_handler(log_file)
    server = HTTPServer(("0.0.0.0", port), handler)
    print(f"VoceChat webhook receiver listening on port {port}", flush=True)
    if log_file:
        print(f"Logging to: {log_file}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
        server.shutdown()


#=========================================================================#
# Function Group: Environment loading                                     #
#=========================================================================#


# Public Function: Load environment variables from a .env file if present.
def load_env_file(env_path: str = ".env") -> None:
    """Load key=value pairs from a .env file into os.environ."""
    path = Path(env_path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# Public Function: Resolve the API key of a bot from per-bot env variables.
def resolve_bot_credentials(bot: str) -> str:
    """Return the API key for a bot name such as 'spike' or 'hubert'.

    Looks up VOCECHAT_<BOT>_API_KEY (name upper-cased, dashes and spaces
    become underscores). Raises ValueError with an actionable message when
    the variable is missing.
    """
    suffix = bot.strip().upper().replace("-", "_").replace(" ", "_")
    key = os.environ.get(f"VOCECHAT_{suffix}_API_KEY", "")
    if not key:
        raise ValueError(
            f"VOCECHAT_{suffix}_API_KEY is not set. Add it to .env or pass "
            "--api-key explicitly."
        )
    return key


#=========================================================================#
# Function Group: Command-line interface                                   #
#=========================================================================#


# Public Function: Print a list of message dicts in a compact readable form.
def print_messages(messages: list[dict[str, Any]]) -> None:
    """Print messages with timestamp, sender and content.

    Handles both nested webhook-style payloads ({detail: {content}}) and flat
    ones ({content}), and falls back to raw JSON for unknown shapes.
    """
    if not messages:
        print("  (no messages)")
        return

    for msg in messages:
        if not isinstance(msg, dict):
            print(f"  {msg!r}")
            continue

        # The messages endpoint nests the payload the same way webhook events do.
        detail = msg.get("detail")
        if isinstance(detail, dict):
            content = detail.get("content", "")
        else:
            content = msg.get("content", "")

        # Fall back to raw JSON when the payload shape is not recognized.
        if not content:
            content = json.dumps(msg, ensure_ascii=False)

        ts = msg.get("created_at")
        ts_str = ""
        if ts:
            ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts / 1000))

        print(f"  [mid={msg.get('mid', '?')} | {ts_str} | from={msg.get('from_uid', '?')}]")
        print(f"    {content}")


# Public Function: Parse CLI arguments and dispatch to the appropriate command.
def main() -> None:
    # Load .env from the working directory, then from the repo root so the
    # client also works when invoked from outside the project.
    load_env_file()
    load_env_file(str(Path(__file__).resolve().parents[2] / ".env"))

    parser = argparse.ArgumentParser(
        description="VoceChat Bot API client and webhook receiver"
    )
    parser.add_argument("--server", default=None, help="VoceChat server URL")
    parser.add_argument("--api-key", default=None, help="Bot API key")
    parser.add_argument(
        "--as",
        dest="as_bot",
        default=None,
        help="Bot identity (e.g. spike, hubert): resolves VOCECHAT_<BOT>_API_KEY",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # groups
    sub.add_parser("groups", help="List all groups the bot is in")

    # send-user
    p_su = sub.add_parser("send-user", help="Send a message to a user (DM)")
    p_su.add_argument("--uid", type=int, required=True)
    p_su.add_argument("--content", required=True)
    p_su.add_argument("--markdown", action="store_true")
    p_su.add_argument("--mentions", type=int, nargs="*", default=None)

    # send-group
    p_sg = sub.add_parser("send-group", help="Send a message to a group (channel)")
    p_sg.add_argument("--gid", type=int, required=True)
    p_sg.add_argument("--content", required=True)
    p_sg.add_argument("--markdown", action="store_true")
    p_sg.add_argument("--mentions", type=int, nargs="*", default=None)

    # user-info
    p_ui = sub.add_parser("user-info", help="Get user info by UID")
    p_ui.add_argument("--uid", type=int, required=True)

    # group-info
    p_gi = sub.add_parser("group-info", help="Get group info by GID")
    p_gi.add_argument("--gid", type=int, required=True)

    # group-messages
    p_gm = sub.add_parser("group-messages", help="Read recent messages of a channel")
    p_gm.add_argument("--gid", type=int, required=True)
    p_gm.add_argument("--context", type=int, default=None, help="Number of recent messages")
    p_gm.add_argument("--user-id", type=int, default=None, help="Filter by sender uid")

    # user-messages
    p_um = sub.add_parser("user-messages", help="Read recent DMs with a user")
    p_um.add_argument("--uid", type=int, required=True)
    p_um.add_argument("--context", type=int, default=None, help="Number of recent messages")

    # webhook
    p_wh = sub.add_parser("webhook", help="Start webhook receiver for surveillance")
    p_wh.add_argument("--port", type=int, default=8010)
    p_wh.add_argument("--log-file", default=None)

    args = parser.parse_args()

    # Webhook receiver does not need an API key.
    if args.command == "webhook":
        run_webhook_server(port=args.port, log_file=args.log_file)
        return

    # All other commands need a client. Resolve the bot identity first when
    # one is given (e.g. --as spike -> VOCECHAT_SPIKE_API_KEY).
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

    if args.command == "groups":
        groups = client.get_groups()
        for g in groups:
            print(f"  gid={g.get('gid')}  name={g.get('name')}  members={g.get('members')}")
        if not groups:
            print("  (no groups)")

    elif args.command == "send-user":
        mid = client.send_to_user(
            uid=args.uid,
            content=args.content,
            markdown=args.markdown,
            mentions=args.mentions,
        )
        print(f"Sent message to user#{args.uid}, mid={mid}")

    elif args.command == "send-group":
        mid = client.send_to_group(
            gid=args.gid,
            content=args.content,
            markdown=args.markdown,
            mentions=args.mentions,
        )
        print(f"Sent message to group#{args.gid}, mid={mid}")

    elif args.command == "user-info":
        info = client.get_user(args.uid)
        print(json.dumps(info, indent=2, ensure_ascii=False))

    elif args.command == "group-info":
        info = client.get_group(args.gid)
        print(json.dumps(info, indent=2, ensure_ascii=False))

    elif args.command == "group-messages":
        messages = client.get_group_messages(
            gid=args.gid,
            context=args.context,
            user_id=args.user_id,
        )
        print_messages(messages)

    elif args.command == "user-messages":
        messages = client.get_user_messages(
            uid=args.uid,
            context=args.context,
        )
        print_messages(messages)


if __name__ == "__main__":
    main()
