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

from importlib.resources import path
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from app.agents.debian_agent import DeBianAgent
from app.auth import login, register, update_iban, get_profile, require_role, decode_token
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
from app.tools.occupancy_tool import get_occupancy, get_fleet_analytics
from app.tools.route_tool import get_alternative_routes


HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8000"))
AGENT = DeBianAgent()


def _bearer(handler: BaseHTTPRequestHandler) -> str:
    """Extract Bearer token from Authorization header."""
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


def send_json(handler: BaseHTTPRequestHandler, status_code: int, payload: dict) -> None:
    body = json.dumps(sanitize_payload(payload), ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))


    def read_multipart(self):
        import re
        ct = self.headers.get("Content-Type", "")
        m = re.search(r"boundary=([^\s;]+)", ct)
        if not m:
            return b"", "audio.webm"
        boundary = m.group(1).encode()
        data = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        for part in data.split(b"--" + boundary):
            if b'name="audio"' in part:
                sep = b"\r\n\r\n"
                idx = part.find(sep)
                if idx == -1:
                    continue
                audio = part[idx + 4:].rstrip(b"\r\n--")
                fn = re.search(rb'filename="([^"]+)"', part)
                return audio, (fn.group(1).decode() if fn else "audio.webm")
        return b"", "audio.webm"

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

        # AFTER — role-aware filtering
        if path == "/rag-search":
            user_query = query.get("query", [""])[0]
            language = query.get("language", ["auto"])[0]
            document_type = query.get("document_type", [None])[0]
            top_k = int(query.get("top_k", ["3"])[0])
            # Decode the token to get the caller's role; default to "customer" if no token
            token_payload = decode_token(_bearer(self))
            user_role = token_payload.get("role", "customer") if token_payload else "customer"
            return send_json(self, 200, search_rag(user_query, language=language, top_k=top_k, document_type=document_type, user_role=user_role))


        if path == "/eval/run":
            return send_json(self, 200, run_eval_suite())

        # --- occupancy (employee/admin only) --------------------------------
        if path.startswith("/occupancy/"):
            token_payload, err = require_role(_bearer(self), "employee")
            if err:
                return send_json(self, 403, {"error": err})
            train_number = unquote(path.replace("/occupancy/", "", 1))
            return send_json(self, 200, get_occupancy(train_number))

        # --- analytics dashboard (admin only) --------------------------------
        if path == "/analytics/fleet":
            token_payload, err = require_role(_bearer(self), "admin")
            if err:
                return send_json(self, 403, {"error": err})
            return send_json(self, 200, get_fleet_analytics())

        # --- user profile (any authenticated user) --------------------------
        if path == "/user/profile":
            token_payload, err = require_role(_bearer(self), "customer")
            if err:
                return send_json(self, 403, {"error": err})
            profile = get_profile(token_payload["sub"])
            if not profile:
                return send_json(self, 404, {"error": "User not found."})
            return send_json(self, 200, profile)

        if path == "/stream":
            message = query.get("message", ["Hello"])[0]
            language = query.get("language", ["en"])[0]
            stream_token_payload = decode_token(_bearer(self))
            stream_role = stream_token_payload.get("role", "customer") if stream_token_payload else "customer"
            response = AGENT.respond(message, {"language": language}, user_role=stream_role).get("response", "")

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

        if path == "/transcribe":
            try:
                import urllib.request as _ur
                audio, fname = self.read_multipart()
                if not audio:
                    return send_json(self, 400, {"error": "No audio received"})
                api_key = os.environ.get("OPENAI_API_KEY", "")
                if not api_key:
                    return send_json(self, 503, {"error": "OPENAI_API_KEY not set in .env"})
                # Build a correct multipart/form-data body for OpenAI Whisper
                NL = b"\r\n"
                BD = b"----DebianWhisper"
                body = b"".join([
                    b"--" + BD + NL,
                    b'Content-Disposition: form-data; name="file"; filename="audio.webm"' + NL,
                    b"Content-Type: audio/webm" + NL + NL,
                    audio + NL,
                    b"--" + BD + NL,
                    b'Content-Disposition: form-data; name="model"' + NL + NL,
                    b"whisper-1" + NL,
                    b"--" + BD + b"--" + NL,
                ])
                req = _ur.Request(
                    "https://api.openai.com/v1/audio/transcriptions",
                    data=body,
                    headers={
                        "Authorization": "Bearer " + api_key,
                        "Content-Type": "multipart/form-data; boundary=----DebianWhisper",
                    },
                    method="POST"
                )
                with _ur.urlopen(req, timeout=30) as r:
                    result = json.loads(r.read())
                return send_json(self, 200, {"text": result.get("text", "")})
            except Exception as e:
                return send_json(self, 500, {"error": str(e)})

        if path == "/upload-document":
            return _handle_upload_document(self)

        # --- auth -----------------------------------------------------------
        if path == "/auth/login":
            try:
                body = self.read_json()
                result = login(body.get("username", ""), body.get("password", ""))
                return send_json(self, 200 if result["success"] else 401, result)
            except Exception as e:
                return send_json(self, 500, {"error": str(e)})

        if path == "/auth/register":
            try:
                body = self.read_json()
                requested_role = body.get("role", "customer")
                # Only admins may create employee or admin accounts.
                if requested_role in {"employee", "admin"}:
                    reg_token_payload, reg_err = require_role(_bearer(self), "admin")
                    if reg_err:
                        return send_json(self, 403, {"error": f"Only admins may assign role '{requested_role}'. {reg_err}"})
                result = register(
                    username=body.get("username", ""),
                    password=body.get("password", ""),
                    full_name=body.get("full_name", ""),
                    email=body.get("email", ""),
                    role=requested_role,
                )
                return send_json(self, 200 if result["success"] else 400, result)
            except Exception as e:
                return send_json(self, 500, {"error": str(e)})

        # --- IBAN update (customer only) -------------------------------------
        if path == "/user/iban":
            token_payload, err = require_role(_bearer(self), "customer")
            if err:
                return send_json(self, 403, {"error": err})
            try:
                body = self.read_json()
                result = update_iban(token_payload["sub"], body.get("iban", ""))
                return send_json(self, 200 if result["success"] else 400, result)
            except Exception as e:
                return send_json(self, 500, {"error": str(e)})

        try:
            payload = self.read_json()

            if path in {"/chat", "/assist"}:
                message = str(payload.get("message", "")).strip()
                if not message:
                    return send_json(self, 400, {"error": "message is required"})
                chat_token_payload = decode_token(_bearer(self))
                chat_role = chat_token_payload.get("role", "customer") if chat_token_payload else "customer"
                result = AGENT.respond(message, payload, history=payload.get("history", []), user_role=chat_role)
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


def _handle_upload_document(handler: BaseHTTPRequestHandler) -> None:
    """
    POST /upload-document  (multipart/form-data)
    Fields:
      file     – the uploaded file (image or document)
      message  – optional user question about the file
      language – optional language code (default: en)
    Returns JSON with the LLM analysis and, when a ticket is detected,
    structured rail-specific advice (delay status, compensation hints).
    """
    import re, base64, urllib.request as _ur, mimetypes

    ct = handler.headers.get("Content-Type", "")
    m = re.search(r"boundary=([^\s;]+)", ct)
    if not m:
        return send_json(handler, 400, {"error": "multipart boundary not found"})

    boundary = m.group(1).encode()
    raw = handler.rfile.read(int(handler.headers.get("Content-Length", "0")))

    # ── parse multipart parts ────────────────────────────────────────────
    file_data = b""
    file_name = "upload"
    file_mime = "application/octet-stream"
    user_message = ""
    language = "en"

    for part in raw.split(b"--" + boundary):
        if not part.strip() or part.strip() == b"--":
            continue
        sep = b"\r\n\r\n"
        idx = part.find(sep)
        if idx == -1:
            continue
        header_block = part[:idx].decode("utf-8", errors="ignore")
        body = part[idx + 4:].rstrip(b"\r\n")

        disp_m = re.search(r'name="([^"]+)"', header_block)
        if not disp_m:
            continue
        field_name = disp_m.group(1)

        if field_name == "file":
            fn_m = re.search(r'filename="([^"]+)"', header_block)
            file_name = fn_m.group(1) if fn_m else "upload"
            ct_m = re.search(r"Content-Type:\s*(\S+)", header_block, re.IGNORECASE)
            file_mime = ct_m.group(1).strip() if ct_m else (
                mimetypes.guess_type(file_name)[0] or "application/octet-stream"
            )
            file_data = body
        elif field_name == "message":
            user_message = body.decode("utf-8", errors="ignore").strip()
        elif field_name == "language":
            language = body.decode("utf-8", errors="ignore").strip() or "en"

    if not file_data:
        return send_json(handler, 400, {"error": "No file received"})

    api_key = os.environ.get("OPENAI_API_KEY", "")
    model   = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    # ── build vision / document content for the LLM ──────────────────────
    b64 = base64.b64encode(file_data).decode()
    is_image = file_mime.startswith("image/")
    is_pdf   = file_mime == "application/pdf"

    SYSTEM = (
        "You are DeBian, a smart Digital Rail Assistant specialising in Deutsche Bahn "
        "and European rail travel. A passenger has uploaded a document or image. "
        "Analyse it carefully.\n\n"
        "If it is a train ticket or booking confirmation:\n"
        "  • Extract: train number, origin, destination, departure date/time, arrival, seat, price, booking reference.\n"
        "  • Then call the delay lookup in your mind (use plausible demo data if you cannot connect) "
        "    and say whether the train is likely on time or delayed.\n"
        "  • If the delay is ≥60 min or the trip was cancelled, explain exactly how to raise a "
        "    compensation claim (EU Regulation 1371/2007 / §17 ERegG): amounts, deadlines, steps.\n\n"
        "If it is any other document (invoice, ID, schedule, photo, etc.):\n"
        "  • Summarise what you see and offer rail-related help where relevant.\n\n"
        "Be concise, helpful, and reply in the passenger's language."
    )

    prompt = user_message if user_message else (
        "Please analyse this document and help me with any rail-related information."
    )

    if is_image:
        user_content = [
            {
                "type": "input_image",
                "image_url": f"data:{file_mime};base64,{b64}",
            },
            {"type": "input_text", "text": prompt},
        ]
    elif is_pdf:
        # Responses API supports file input for PDFs
        user_content = [
            {
                "type": "input_file",
                "filename": file_name,
                "file_data": f"data:application/pdf;base64,{b64}",
            },
            {"type": "input_text", "text": prompt},
        ]
    else:
        # Plain text / other: send raw decoded text
        try:
            text_content = file_data.decode("utf-8", errors="replace")
        except Exception:
            text_content = "(binary file – could not decode)"
        user_content = [
            {"type": "input_text", "text": f"File name: {file_name}\n\nContent:\n{text_content[:6000]}\n\n{prompt}"},
        ]

    if not api_key:
        # Fallback: no LLM – return structured acknowledgement
        return send_json(handler, 200, {
            "analysis": (
                f"I received your file '{file_name}' ({file_mime}, {len(file_data):,} bytes). "
                "To get a full AI analysis of your document — including ticket details, delay status "
                "and compensation guidance — please configure OPENAI_API_KEY in your .env file."
            ),
            "file_name": file_name,
            "file_mime": file_mime,
            "file_size": len(file_data),
            "used_llm": False,
        })

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": user_content},
        ],
        "max_output_tokens": 600,
        "temperature": 0.2,
    }

    try:
        req = _ur.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with _ur.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # extract text from Responses API shape
        texts = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                    texts.append(content["text"])
        if not texts and isinstance(data.get("output_text"), str):
            texts = [data["output_text"]]

        analysis = "\n".join(texts).strip() or "I could not analyse this document."

        return send_json(handler, 200, {
            "analysis": analysis,
            "file_name": file_name,
            "file_mime": file_mime,
            "file_size": len(file_data),
            "used_llm": True,
        })

    except Exception as exc:
        return send_json(handler, 500, {"error": f"LLM call failed: {exc}", "used_llm": False})


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), DeBianHandler)
    print(f"DeBian backend running at http://127.0.0.1:{PORT}")
    print(f"Docs: http://127.0.0.1:{PORT}/docs")
    server.serve_forever()


if __name__ == "__main__":
    run()
