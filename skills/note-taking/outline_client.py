# skills/note-taking/outline_client.py
"""Outline API client for the project knowledge base.

Bundled with the `note-taking` skill. Talks to the self-hosted Outline
instance (https://www.getoutline.com) where agents take notes and build
wikis per Graph service collection. Uses only the standard library.

Usage:
  python outline_client.py --as senior-hexa-developer collection-docs --collection agents
  python outline_client.py --as senior-hexa-developer create --collection agents --title "Wiki start" --file page.md
  python outline_client.py --as graphai-engineer search --query "graphai endpoints" --collection ai
  python outline_client.py --as graphai-engineer edit --id <document-id> --file updated.md
  python outline_client.py --as agentic-coding-manager read --id <document-id>
  python outline_client.py --as agentic-coding-manager collections

Identity (--as <agent or call sign>):
  Agents are identity-agnostic: pass your own agent name
  (--as senior-hexa-developer) or your call sign (whatever it currently
  is — see agents/identities.json). Both resolve through the central
  registry, which maps each agent to the exact OUTLINE_ key variable.
  Without --as the client falls back to OUTLINE_API_KEY.

Collections can be named by friendly name (see collections.json), by
collection id (UUID), or by their Outline name (fuzzy match on
collections.list).

Environment variables (or .env file):
  OUTLINE_SERVER              Base URL of the Outline server (no trailing /)
  OUTLINE_<AGENT>_API_KEY     Per-agent API key as named in agents/identities.json
  OUTLINE_API_KEY             Fallback API key when no --as is given
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:  # Optional: trust certifi's CA bundle when Python's default paths are incomplete.
    import certifi
except ImportError:  # pragma: no cover
    certifi = None


def _ssl_context():
    """Return an SSL context trusting certifi's CA bundle, or None for the default."""
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return None


class OutlineError(RuntimeError):
    """Raised for any Outline API error with a human-readable message."""


# Module-level: .env files merged into os.environ during this run.
_LOADED_ENV_FILES: list[Path] = []


#==================#
# Class Definition #
#==================#
class OutlineClient:
    """Client for the Outline RPC API.

    Every Outline endpoint is a POST to `{server}/api/{method}` with a JSON
    body, authenticated with `Authorization: Bearer <api-key>`.
    """

    # Internal Function: Perform an RPC call and return the parsed data payload.
    def _call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.server.rstrip('/')}/api/{method}"
        payload = json.dumps(params or {}).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        req = Request(url, data=payload, headers=headers, method="POST")

        # Send the request and parse the standard Outline envelope.
        try:
            with urlopen(req, timeout=self.timeout, context=_ssl_context()) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read().decode("utf-8", errors="replace")).get("error", "")
            except Exception:
                pass
            raise OutlineError(f"Outline API error {exc.code} on {method}: {detail}") from exc
        except URLError as exc:
            raise OutlineError(f"Cannot reach Outline at {self.server}: {exc.reason}") from exc

        if not isinstance(body, dict):
            raise OutlineError(f"Unexpected response shape on {method}: {body!r}")
        if body.get("ok") is not True:
            raise OutlineError(f"Outline API error on {method}: {body.get('error', body)}")
        return body.get("data")

    # Public Method: Initialize the client with server URL and API key.
    def __init__(
        self,
        server: str | None = None,
        api_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.server = server or os.environ.get("OUTLINE_SERVER", "")
        self.api_key = api_key or os.environ.get("OUTLINE_API_KEY", "")
        self.timeout = timeout

        if not self.server:
            raise OutlineError(
                "OUTLINE_SERVER is not set. Set it in .env or pass --server."
            )
        if not self.api_key:
            raise OutlineError(
                "No API key. This project uses per-agent keys: rerun with "
                "--as <agent> so OUTLINE_<AGENT>_API_KEY is resolved"
                f".{_identities_hint()} Alternatively pass --api-key directly."
            )

    # Public Method: Verify the key and return current user/team info.
    def auth_info(self) -> dict[str, Any]:
        return self._call("auth.info")

    # Public Method: List all collections visible to the key.
    def list_collections(self, limit: int = 100) -> list[dict[str, Any]]:
        data = self._call("collections.list", {"limit": limit})
        if isinstance(data, list):
            return data
        return []

    # Public Method: Get metadata of a single collection by id.
    def collection_info(self, collection_id: str) -> dict[str, Any]:
        data = self._call("collections.info", {"id": collection_id})
        if isinstance(data, dict):
            return data
        return {}

    # Public Method: Get the nested document structure of a collection.
    def collection_documents(self, collection_id: str) -> list[dict[str, Any]]:
        data = self._call("collections.documents", {"id": collection_id})
        if isinstance(data, list):
            return data
        return []

    # Public Method: List documents, optionally scoped to a collection.
    def list_documents(
        self,
        collection_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if collection_id:
            params["collectionId"] = collection_id
        data = self._call("documents.list", params)
        if isinstance(data, list):
            return data
        return []

    # Public Method: Fetch one document with its full markdown text.
    def get_document(self, document_id: str) -> dict[str, Any]:
        data = self._call("documents.info", {"id": document_id})
        if isinstance(data, dict):
            return data
        return {}

    # Public Method: Create a document in a collection and return it.
    def create_document(
        self,
        collection_id: str,
        title: str,
        text: str = "",
        parent_document_id: str | None = None,
        publish: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "collectionId": collection_id,
            "title": title,
            "text": text,
            "publish": publish,
        }
        if parent_document_id:
            params["parentDocumentId"] = parent_document_id
        data = self._call("documents.create", params)
        return self._extract_document(data)

    # Public Method: Replace (or append to) a document's markdown text.
    def update_document(
        self,
        document_id: str,
        title: str | None = None,
        text: str | None = None,
        append: bool = False,
        publish: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"id": document_id, "publish": publish}
        if title is not None:
            params["title"] = title
        if text is not None:
            params["text"] = text
            if append:
                params["append"] = True
        data = self._call("documents.update", params)
        return self._extract_document(data)

    # Public Method: Full-text search documents, optionally in one collection.
    def search(
        self,
        query: str,
        collection_id: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"query": query, "limit": limit}
        if collection_id:
            params["collectionId"] = collection_id
        data = self._call("documents.search", params)
        if isinstance(data, list):
            return data
        return []

    # Public Method: Archive a document (soft delete, reversible).
    def archive_document(self, document_id: str) -> dict[str, Any]:
        data = self._call("documents.archive", {"id": document_id})
        return self._extract_document(data)

    # Public Method: Permanently delete a document. Not reversible.
    def delete_document(self, document_id: str) -> None:
        self._call("documents.delete", {"id": document_id})

    # Internal Function: Unwrap the {document: {...}} envelope if present.
    def _extract_document(self, data: Any) -> dict[str, Any]:
        if isinstance(data, dict) and isinstance(data.get("document"), dict):
            return data["document"]
        if isinstance(data, dict):
            return data
        return {}


#====================================#
# Function Group: Name resolution     #
#====================================#


# Public Function: Load the friendly collection directory from collections.json.
def load_collection_map() -> dict[str, Any]:
    """Return the contents of collections.json, or an empty structure."""
    path = Path(__file__).resolve().parent / "collections.json"
    if not path.exists():
        return {"collections": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"collections": {}}
    return data if isinstance(data, dict) else {"collections": {}}


# Internal Function: Resolve a collection name, alias or UUID to its id.
def _resolve_collection_id(client: OutlineClient, name: str) -> str:
    if re.fullmatch(r"[0-9a-fA-F-]{36}", name):
        return name

    mapping = load_collection_map().get("collections", {})
    normalized = name.strip().lower()
    for catalog_name, entry in mapping.items():
        keys = {catalog_name.lower()}
        keys.update(str(a).lower() for a in entry.get("aliases", []))
        if normalized in keys:
            cid = entry.get("id")
            if cid:
                return str(cid)

    # Fall back to live lookup: match the friendly name against Outline.
    needle = normalized.replace("-", " ").replace("_", " ")
    for collection in client.list_collections():
        cname = str(collection.get("name", "")).lower().replace("_", " ")
        if cname == needle:
            return str(collection.get("id"))

    raise OutlineError(
        f"Unknown collection '{name}'. Not in collections.json and no exact "
        "name match on the server. Run `collections` to list them."
    )


#====================================#
# Function Group: Presentation        #
#====================================#


# Public Function: Print one Outline document summary row.
def print_document(doc: dict[str, Any]) -> None:
    """Print id, title, url and updated date of a document."""
    print(
        f"  id={doc.get('id')}\n"
        f"    title: {doc.get('title')}\n"
        f"    url:   {doc.get('url')}\n"
        f"    updated: {doc.get('updatedAt')}"
    )


# Public Function: Print the nested document tree of a collection.
def print_tree(nodes: list[dict[str, Any]], indent: int = 0) -> None:
    """Recursively print a collections.documents navigation tree."""
    for node in nodes:
        title = node.get("title") or node.get("name")
        print(f"{'  ' * indent}- {title}  (id={node.get('id')})")
        print_tree(node.get("children") or [], indent + 1)


#===========================================#
# Function Group: Agent identity             #
#===========================================#


# Internal Function: Load the central identity registry (agents/identities.json).
def load_identity_registry() -> dict[str, Any]:
    """Return the central identity registry, or {} when unreadable.

    The registry is the single source of truth for agent call signs and the
    exact, per-service key variable names. Agents stay identity-agnostic:
    --as accepts an agent name or a call sign and this registry resolves it.
    """
    path = Path(__file__).resolve().parents[2] / "agents" / "identities.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


# Internal Function: Find an agent entry by agent name or call sign.
def lookup_identity(name: str) -> dict[str, Any] | None:
    """Return {'agent': ..., **entry} for an agent name or call sign, else None."""
    agents = load_identity_registry().get("agents", {})
    lowered = name.strip().lower()
    entry = agents.get(lowered)
    if isinstance(entry, dict):
        return {"agent": lowered, **entry}
    for agent, candidate in agents.items():
        if str(candidate.get("call_sign", "")).lower() == lowered:
            return {"agent": agent, **candidate}
    return None


# Internal Function: Describe available identities for error messages.
def _identities_hint() -> str:
    """Return the error suffix listing available identities, or '' when none exist."""
    identities = [
        f"{agent} ({entry.get('call_sign', '?')})"
        for agent, entry in load_identity_registry().get("agents", {}).items()
        if isinstance(entry, dict)
    ]
    if not identities:
        # Fall back to variable names when the registry cannot be read.
        for var in os.environ:
            if var.startswith("OUTLINE_") and var.endswith("_API_KEY"):
                middle = var[len("OUTLINE_") : -len("_API_KEY")]
                if middle:
                    identities.append(middle.replace("_", "-").lower())
    if not identities:
        return ""
    return (
        f" Available identities: {', '.join(identities)} — pass --as <agent name"
        f" or call sign> (e.g. --as {identities[0].split(' ')[0]})."
    )


# Public Function: Resolve the Outline API key for an agent name or call sign.
def resolve_agent_credentials(agent: str) -> str:
    """Return the Outline API key for an agent or call sign.

    Resolution order:
      1. The exact key variable named in agents/identities.json for the
         identity (resolved by agent name or call sign).
      2. The OUTLINE_<CALLSIGN>_API_KEY convention variable (back-compat).
      3. The OUTLINE_<GIVEN-NAME>_API_KEY convention variable (back-compat
         for identities missing from the registry).
    Raises OutlineError when nothing resolves; only variable names appear
    in errors, never values.
    """
    candidates: list[str] = []
    identity = lookup_identity(agent)
    if identity:
        explicit_var = (identity.get("keys") or {}).get("outline")
        if explicit_var:
            candidates.append(explicit_var)
        call_sign = str(identity.get("call_sign", "")).upper().replace(" ", "_")
        if call_sign:
            candidates.append(f"OUTLINE_{call_sign}_API_KEY")
    suffix = agent.strip().upper().replace("-", "_").replace(" ", "_")
    convention_var = f"OUTLINE_{suffix}_API_KEY"
    if convention_var not in candidates:
        candidates.append(convention_var)

    for var in candidates:
        key = os.environ.get(var, "")
        if key:
            return key
    raise OutlineError(
        f"No Outline key resolved for '{agent}' (tried: {', '.join(candidates)})."
        f"{_identities_hint()} Keys load automatically from a .env (first one"
        " found walking up from the current directory, then the agents repo"
        " root). To add a key, create it in Outline (Settings -> API & Apps)"
        " while logged in as that agent's user, then add the named variable"
        " to .env."
    )


#====================================#
# Function Group: Command-line interface #
#====================================#


# Public Function: Parse CLI arguments and dispatch to the appropriate command.
def main() -> None:
    # Load .env files without any manual sourcing: the first .env found walking
    # up from the current directory, then the agents repo root as fallback so
    # the client also works when invoked from outside any configured project.
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        env_path = candidate / ".env"
        if env_path.is_file():
            _load_env_file(str(env_path))
            break
    _load_env_file(str(Path(__file__).resolve().parents[2] / ".env"))

    parser = argparse.ArgumentParser(description="Outline API client")
    parser.add_argument("--server", default=None, help="Outline server URL")
    parser.add_argument("--api-key", default=None, help="Outline API key")
    parser.add_argument(
        "--as",
        dest="as_agent",
        default=None,
        help="Agent name or call sign (e.g. senior-hexa-developer): "
        "resolved via agents/identities.json",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("auth", help="Verify the key and show current user/team")
    sub.add_parser("collections", help="List collections")

    p_cd = sub.add_parser("collection-docs", help="Show the document tree of a collection")
    p_cd.add_argument("--collection", required=True)

    p_l = sub.add_parser("list", help="List documents in a collection")
    p_l.add_argument("--collection", default=None)
    p_l.add_argument("--limit", type=int, default=50)

    p_r = sub.add_parser("read", help="Read a document (markdown to stdout)")
    p_r.add_argument("--id", required=True)

    p_c = sub.add_parser("create", help="Create a document in a collection")
    p_c.add_argument("--collection", required=True)
    p_c.add_argument("--title", required=True)
    p_c.add_argument("--text", default=None, help="Markdown body (or use --file)")
    p_c.add_argument("--file", default=None, help="Read the markdown body from a file")
    p_c.add_argument("--parent", default=None, help="parentDocumentId for nested notes")
    p_c.add_argument("--draft", action="store_true", help="Create unpublished draft")

    p_e = sub.add_parser("edit", help="Replace a document's text or append to it")
    p_e.add_argument("--id", required=True)
    p_e.add_argument("--title", default=None)
    p_e.add_argument("--text", default=None, help="Markdown body (or use --file)")
    p_e.add_argument("--file", default=None, help="Read the markdown body from a file")
    p_e.add_argument("--append", action="store_true", help="Append instead of replacing")

    p_s = sub.add_parser("search", help="Search documents")
    p_s.add_argument("--query", required=True)
    p_s.add_argument("--collection", default=None)
    p_s.add_argument("--limit", type=int, default=25)

    p_a = sub.add_parser("archive", help="Archive a document (reversible)")
    p_a.add_argument("--id", required=True)

    p_d = sub.add_parser("delete", help="Delete a document permanently")
    p_d.add_argument("--id", required=True)

    args = parser.parse_args()

    # Resolve the agent identity first when one is given (agent name or call
    # sign, via agents/identities.json), falling back to OUTLINE_API_KEY otherwise.
    api_key = args.api_key
    if args.as_agent:
        try:
            api_key = api_key or resolve_agent_credentials(args.as_agent)
        except OutlineError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    try:
        client = OutlineClient(server=args.server, api_key=api_key)
        _dispatch(client, args)
    except OutlineError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


# Internal Function: Route a parsed CLI invocation to its client call.
def _dispatch(client: OutlineClient, args: argparse.Namespace) -> None:
    if args.command == "auth":
        info = client.auth_info()
        user = info.get("user", {})
        team = info.get("team", {})
        print(f"  user: {user.get('name')} (id={user.get('id')})")
        print(f"  team: {team.get('name')}")
        return

    if args.command == "collections":
        for c in client.list_collections():
            print(f"  id={c.get('id')}  name={c.get('name')!r}")
        return

    if args.command == "collection-docs":
        cid = _resolve_collection_id(client, args.collection)
        print_tree(client.collection_documents(cid))
        return

    if args.command == "list":
        cid = _resolve_collection_id(client, args.collection) if args.collection else None
        docs = client.list_documents(collection_id=cid, limit=args.limit)
        if not docs:
            print("  (no documents)")
        for doc in docs:
            print_document(doc)
        return

    if args.command == "read":
        doc = client.get_document(args.id)
        print(f"# {doc.get('title')}\n")
        print(doc.get("text", ""))
        return

    if args.command == "create":
        text = _read_text(args.text, args.file)
        cid = _resolve_collection_id(client, args.collection)
        doc = client.create_document(
            collection_id=cid,
            title=args.title,
            text=text,
            parent_document_id=args.parent,
            publish=not args.draft,
        )
        print(f"  created: {doc.get('title')}")
        print(f"  id:  {doc.get('id')}")
        print(f"  url: {doc.get('url')}")
        return

    if args.command == "edit":
        text = _read_text(args.text, args.file)
        doc = client.update_document(
            document_id=args.id,
            title=args.title,
            text=text,
            append=args.append,
        )
        print(f"  updated: {doc.get('title')}")
        print(f"  url: {doc.get('url')}")
        return

    if args.command == "search":
        cid = _resolve_collection_id(client, args.collection) if args.collection else None
        results = client.search(args.query, collection_id=cid, limit=args.limit)
        if not results:
            print("  (no results)")
        for hit in results:
            doc = hit.get("document", hit) if isinstance(hit, dict) else hit
            print_document(doc)
        return

    if args.command == "archive":
        doc = client.archive_document(args.id)
        print(f"  archived: {doc.get('title')}")
        return

    if args.command == "delete":
        client.delete_document(args.id)
        print(f"  deleted: {args.id}")
        return


# Internal Function: Take the markdown body from --text or --file.
def _read_text(text: str | None, file: str | None) -> str | None:
    if file:
        path = Path(file)
        if not path.exists():
            raise OutlineError(f"File not found: {file}")
        return path.read_text(encoding="utf-8")
    return text


# Public Function: Load key=value pairs from a .env file into os.environ.
def _load_env_file(env_path: str) -> None:
    """Load assignments from a .env file without overriding existing values."""
    path = Path(env_path)
    if not path.exists() or path in _LOADED_ENV_FILES:
        return
    _LOADED_ENV_FILES.append(path)
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


if __name__ == "__main__":
    main()
