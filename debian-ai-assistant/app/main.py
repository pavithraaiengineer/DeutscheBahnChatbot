"""
DeBian backend.

Run:
    python -m app.main

Open:
    http://127.0.0.1:8000/docs

This backend uses Python standard library only to avoid Windows/Python version conflicts.
It follows the requested DB flow and project structure.
"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from app.agents.debian_agent import DeBianAgent
from app.security.governance import sanitize_payload
from app.tools.compensation_tool import submit_compensation_claim
from app.tools.delay_tool import get_delay_status
from app.tools.human_handoff_tool import request_human_handoff
from app.tools.route_tool import get_alternative_routes


HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8000"))
AGENT = DeBianAgent()


def send_json(handler: BaseHTTPRequestHandler, status_code: int, payload: dict) -> None:
    body = json.dumps(sanitize_payload(payload), ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


def send_html(handler: BaseHTTPRequestHandler, status_code: int, html: str) -> None:
    body = html.encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


class DeBianHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        # Do not log request bodies to reduce PII leakage.
        print(f"{self.address_string()} - {format % args}")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            return send_json(
                self,
                200,
                {
                    "status": "running",
                    "service": "DeBian AI Rail Assistant",
                    "docs": "/docs",
                    "flow": "voice/image/text -> language detection -> agent -> MCP-like tools -> PII masking -> analytics/evaluation",
                },
            )

        if path == "/docs":
            return send_html(self, 200, DOCS_HTML)

        if path.startswith("/delay/"):
            train_number = unquote(path.replace("/delay/", "", 1))
            return send_json(self, 200, get_delay_status(train_number))

        if path == "/stream":
            message = query.get("message", ["Hello"])[0]
            language = query.get("language", ["en"])[0]
            response = AGENT.respond(message, {"language": language}).get("response", "")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            for token in response.split():
                self.wfile.write(f"data: {token}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(0.05)

            self.wfile.write("data: [DONE]\n\n".encode("utf-8"))
            self.wfile.flush()
            return

        return send_json(self, 404, {"error": "Not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            payload = self.read_json()

            if path in {"/chat", "/assist"}:
                message = str(payload.get("message", "")).strip()
                if not message:
                    return send_json(self, 400, {"error": "message is required"})
                return send_json(self, 200, AGENT.respond(message, payload))

            if path == "/claim":
                return send_json(self, 200, submit_compensation_claim(payload))

            if path == "/route":
                return send_json(self, 200, get_alternative_routes(payload.get("origin", ""), payload.get("destination", "")))

            if path == "/human-assistance":
                return send_json(
                    self,
                    200,
                    request_human_handoff(
                        language=payload.get("language", "en"),
                        reason=payload.get("reason", "customer requested support"),
                    ),
                )

            return send_json(self, 404, {"error": "Not found"})

        except json.JSONDecodeError:
            return send_json(self, 400, {"error": "Invalid JSON body"})
        except ValueError as error:
            return send_json(self, 400, {"error": str(error)})
        except Exception as error:
            return send_json(self, 500, {"error": "Internal server error", "detail": str(error)})


DOCS_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>DeBian API Docs</title>
  <style>
    body { font-family: Arial, sans-serif; background: #111; color: #f7f7f7; margin: 40px; line-height: 1.5; }
    h1 { color: #e30613; }
    .card { background: #1c1c1f; border: 1px solid #333; border-radius: 18px; padding: 18px; margin: 16px 0; }
    code, pre { background: #27272a; padding: 12px; border-radius: 10px; display: block; overflow-x: auto; }
  </style>
</head>
<body>
  <h1>DeBian API Docs</h1>
  <p>Backend is running. This MVP implements the requested DB flow using standard Python.</p>

  <div class="card">
    <h2>GET /</h2>
    <p>Health check.</p>
  </div>

  <div class="card">
    <h2>POST /assist</h2>
    <pre>{
  "message": "I want compensation for delayed train ICE 572",
  "language": "en",
  "train_number": "ICE 572"
}</pre>
  </div>

  <div class="card">
    <h2>GET /stream?message=I%20need%20help&language=en</h2>
    <p>Server-Sent Events streaming endpoint.</p>
  </div>

  <div class="card">
    <h2>GET /delay/ICE%20572</h2>
    <p>Mock delay lookup.</p>
  </div>

  <div class="card">
    <h2>POST /claim</h2>
    <pre>{
  "train_number": "ICE 572",
  "planned_start_time": "2026-05-20T10:00:00",
  "actual_start_time": "2026-05-20T11:35:00",
  "trip_not_started": false,
  "alternative_transport": "Regional train",
  "ticket_price": 80,
  "delay_minutes": 95,
  "refund_method": "bank_account",
  "account_number": "DE89370400440532013000",
  "home_address": null,
  "claim_form": true
}</pre>
  </div>

  <div class="card">
    <h2>POST /route</h2>
    <pre>{
  "origin": "Frankfurt(Main)Hbf",
  "destination": "Berlin Hbf"
}</pre>
  </div>

  <div class="card">
    <h2>POST /human-assistance</h2>
    <pre>{
  "language": "en",
  "reason": "Customer requested a callback"
}</pre>
  </div>
</body>
</html>
"""


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), DeBianHandler)
    print(f"DeBian backend running at http://127.0.0.1:{PORT}")
    print(f"Docs: http://127.0.0.1:{PORT}/docs")
    server.serve_forever()


if __name__ == "__main__":
    run()
