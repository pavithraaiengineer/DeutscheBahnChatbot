"""
DeBian backend.

Run:
    python -m app.main

Open:
    http://127.0.0.1:8000/docs

Local backend uses Python standard library only for stability.
Production can replace this with FastAPI while preserving the same modules.
"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from app.agents.debian_agent import DeBianAgent
from app.config import config_status
from app.databricks.etl_pipeline import run_etl_pipeline, read_feature_table
from app.databricks.feature_store import get_delay_features
from app.evaluation.eval_pipeline import run_eval_suite
from app.rag.retriever import search_rag, upsert_rag_documents
from app.security.governance import sanitize_payload, governance_status
from app.session_store.firestore_store import save_session, save_claim, get_store_status
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
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            return send_json(self, 200, {
                "status": "running",
                "service": "DeBian AI Rail Assistant",
                "docs": "/docs",
                "config": config_status(),
                "architecture": "GKE + Terraform + Databricks + Pinecone + BigQuery + Secret Manager + Monitoring",
            })

        if path == "/docs":
            return send_html(self, 200, DOCS_HTML)

        if path == "/infra/status":
            return send_json(self, 200, {
                "config": config_status(),
                "governance": governance_status(),
                "session_store": get_store_status(),
            })

        if path.startswith("/delay/"):
            train_number = unquote(path.replace("/delay/", "", 1))
            return send_json(self, 200, get_delay_status(
                train_number=train_number,
                station_name=query.get("station", [None])[0],
                planned_start_time=query.get("planned_start_time", [None])[0],
            ))

        if path == "/etl/run":
            return send_json(self, 200, run_etl_pipeline())

        if path == "/features":
            return send_json(self, 200, read_feature_table())

        if path == "/feature":
            train = query.get("train", [""])[0]
            return send_json(self, 200, get_delay_features(train) if train else {"error": "train query parameter required"})

        if path == "/rag-search":
            user_query = query.get("query", [""])[0]
            language = query.get("language", ["auto"])[0]
            document_type = query.get("document_type", [None])[0]
            top_k = int(query.get("top_k", ["3"])[0])
            return send_json(self, 200, search_rag(user_query, language=language, top_k=top_k, document_type=document_type))

        if path == "/eval/run":
            return send_json(self, 200, run_eval_suite())

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
                time.sleep(0.04)

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
                result = AGENT.respond(message, payload)
                if payload.get("session_id"):
                    save_session(payload["session_id"], {"last_message": message, "last_response": result})
                return send_json(self, 200, result)

            if path == "/claim":
                result = submit_compensation_claim(payload)
                save_claim(result["claim_id"], result)
                return send_json(self, 200, result)

            if path == "/route":
                return send_json(self, 200, get_alternative_routes(payload.get("origin", ""), payload.get("destination", "")))

            if path == "/human-assistance":
                return send_json(self, 200, request_human_handoff(
                    language=payload.get("language", "en"),
                    reason=payload.get("reason", "customer requested support"),
                    priority=payload.get("priority", "normal"),
                ))

            if path == "/rag/upsert":
                documents = payload.get("documents", [])
                if not isinstance(documents, list):
                    return send_json(self, 400, {"error": "documents must be a list"})
                return send_json(self, 200, upsert_rag_documents(documents))

            if path == "/session/save":
                return send_json(self, 200, save_session(payload.get("session_id", "default"), payload))

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
  <p>Complete production-style project: GKE, Terraform, Databricks-style ETL, Feature Store, Pinecone/local RAG, security, monitoring-ready.</p>

  <div class="card"><h2>GET /</h2><p>Health check.</p></div>
  <div class="card"><h2>GET /infra/status</h2><p>Config, governance, session-store status.</p></div>
  <div class="card"><h2>GET /delay/ICE%20572</h2><p>Mock/real-time-ready delay lookup.</p></div>
  <div class="card"><h2>GET /delay/ICE%20572?station=Frankfurt(Main)Hbf&planned_start_time=2026-05-20T10:00:00</h2><p>Real-time-ready DB Timetables API mode if credentials exist.</p></div>
  <div class="card"><h2>GET /etl/run</h2><p>Run Databricks-style Bronze/Silver/Gold ETL.</p></div>
  <div class="card"><h2>GET /features</h2><p>Read Gold feature table.</p></div>
  <div class="card"><h2>GET /feature?train=ICE%20572</h2><p>Read one train's feature row.</p></div>
  <div class="card"><h2>GET /rag-search?query=refund%20delay&language=en</h2><p>Search Pinecone if configured, otherwise local vector DB fallback.</p></div>
  <div class="card"><h2>GET /eval/run</h2><p>Evaluation service sample suite.</p></div>
  <div class="card"><h2>GET /stream?message=I%20need%20compensation&language=en</h2><p>Streaming response.</p></div>

  <div class="card">
    <h2>POST /claim</h2>
    <pre>{
  "train_number": "ICE 572",
  "station_name": "Frankfurt(Main)Hbf",
  "planned_start_time": "2026-05-20T10:00:00",
  "actual_start_time": "2026-05-20T11:35:00",
  "trip_not_started": false,
  "alternative_transport": "Regional train",
  "ticket_price": 80,
  "delay_minutes": 95,
  "refund_method": "bank_account",
  "account_number": "DE89370400440532013000",
  "claim_form": true
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
