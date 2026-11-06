# graphagents/scripts/surveillance/webhook_tripwire.py
"""Passive webhook tripwire: logs raw webhook POSTs for delivery diagnosis.

Runs on the docker-network gateway address so the VoceChat container can
reach it. Never parses or trusts the payloads — capture only. Part of the
surveillance kit (see start.sh); the polling listener is the primary
collection mechanism, this is the tripwire for webhook deliveries.
"""
import argparse
import http.server
import json

CAPTURE_LOG = ".surveillance/webhook-capture.jsonl"


class TripwireHandler(http.server.BaseHTTPRequestHandler):
    """Respond 200 to GET (VoceChat's webhook URL check) and log POSTs raw."""

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length > 0 else b""
        entry = {
            "from": self.client_address[0],
            "path": self.path,
            "content_type": self.headers.get("Content-Type"),
            "length": length,
            "len_mod16": len(raw) % 16,
            "body_repr": repr(raw[:600]),
        }
        with open(CAPTURE_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        pass


def main():
    global CAPTURE_LOG
    parser = argparse.ArgumentParser(description="Webhook capture tripwire")
    parser.add_argument("--bind", default="172.23.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--log", default=CAPTURE_LOG)
    args = parser.parse_args()
    CAPTURE_LOG = args.log

    server = http.server.HTTPServer((args.bind, args.port), TripwireHandler)
    print(f"[tripwire] capturing webhook POSTs on {args.bind}:{args.port} -> {CAPTURE_LOG}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
