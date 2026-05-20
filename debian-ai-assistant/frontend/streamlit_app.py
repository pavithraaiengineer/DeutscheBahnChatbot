"""
DeBian frontend.

This file has two modes:

1. Streamlit mode:
   streamlit run frontend/streamlit_app.py

2. No-install fallback mode:
   python frontend/streamlit_app.py
   Then open http://127.0.0.1:8501

The fallback mode is included so the project still runs even if Streamlit is not installed.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DEFAULT_API_BASE = "http://127.0.0.1:8000"


def api_post(api_base: str, path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{api_base}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def api_get(api_base: str, path: str) -> dict:
    with urllib.request.urlopen(f"{api_base}{path}", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run_streamlit() -> None:
    import streamlit as st

    st.set_page_config(page_title="DeBian", page_icon="🚆", layout="wide")

    st.title("DeBian — Digital Rail Assistant")
    st.caption("Text, voice/image placeholders, multilingual support, compensation workflow, PII masking, analytics/evaluation logs.")

    api_base = st.sidebar.text_input("Backend URL", DEFAULT_API_BASE)
    language = st.sidebar.selectbox("Language", ["en", "de", "fr", "ta"])

    if st.sidebar.button("Check Backend"):
        try:
            st.sidebar.success(api_get(api_base, "/")["service"])
        except Exception as error:
            st.sidebar.error(f"Backend not reachable: {error}")

    tab_chat, tab_claim, tab_human = st.tabs(["Chat", "Compensation Claim", "Human Assistance"])

    with tab_chat:
        message = st.text_area("Ask by text", "I want compensation for delayed train ICE 572")
        train_number = st.text_input("Train number for delay lookup", "ICE 572")
        voice_file = st.file_uploader("Voice input placeholder", type=["wav", "mp3", "m4a"], key="voice")
        image_file = st.file_uploader("Image input placeholder", type=["png", "jpg", "jpeg"], key="image")

        if st.button("Ask DeBian"):
            payload = {
                "message": message,
                "language": language,
                "train_number": train_number,
                "voice_uploaded": voice_file is not None,
                "image_uploaded": image_file is not None,
            }
            try:
                st.json(api_post(api_base, "/assist", payload))
            except Exception as error:
                st.error(error)

    with tab_claim:
        col1, col2 = st.columns(2)

        with col1:
            claim_train_number = st.text_input("Train number", "ICE 572")
            planned_start_time = st.text_input("Planned start time", "2026-05-20T10:00:00")
            actual_start_time = st.text_input("Actual start time", "2026-05-20T11:35:00")
            trip_not_started = st.checkbox("Trip never started due to delay")

        with col2:
            alternative_transport = st.text_input("Alternative transport used", "Regional train")
            ticket_price = st.number_input("Ticket price", min_value=0.0, value=80.0)
            delay_minutes = st.number_input("Delay minutes", min_value=0, value=95)
            refund_method = st.selectbox("Refund method", ["bank_account", "voucher"])

        account_number = st.text_input("IBAN/account number", "DE89370400440532013000")
        home_address = st.text_input("Home address for voucher", "Sample Street 1, 60311 Frankfurt")

        if st.button("Submit Claim"):
            payload = {
                "train_number": claim_train_number,
                "planned_start_time": planned_start_time,
                "actual_start_time": actual_start_time,
                "trip_not_started": trip_not_started,
                "alternative_transport": alternative_transport,
                "ticket_price": ticket_price,
                "delay_minutes": delay_minutes,
                "refund_method": refund_method,
                "account_number": account_number if refund_method == "bank_account" else None,
                "home_address": home_address if refund_method == "voucher" else None,
                "claim_form": True,
                "language": language,
            }
            try:
                st.json(api_post(api_base, "/claim", payload))
            except Exception as error:
                st.error(error)

    with tab_human:
        reason = st.text_area("Reason", "Customer requested a callback")
        if st.button("Request Human Assistance"):
            try:
                st.json(api_post(api_base, "/human-assistance", {"language": language, "reason": reason}))
            except Exception as error:
                st.error(error)


FALLBACK_HTML = r"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>DeBian Fallback UI</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background: radial-gradient(circle at bottom, #3a1115, #111 55%); color: white; }
    main { max-width: 1000px; margin: 0 auto; padding: 34px; display: grid; grid-template-columns: 360px 1fr; gap: 22px; }
    section { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.14); border-radius: 28px; padding: 26px; }
    h1 { font-size: 60px; margin: 26px 0 0; } h1 span { color: #e30613; }
    input, textarea, select, button { width: 100%; box-sizing: border-box; padding: 13px; border-radius: 12px; margin: 8px 0; background: rgba(0,0,0,.25); color: white; border: 1px solid rgba(255,255,255,.15); }
    button { background: #e30613; border: none; cursor: pointer; font-weight: bold; }
    pre { background: rgba(0,0,0,.35); padding: 16px; border-radius: 16px; overflow-x: auto; min-height: 240px; }
    .badge { color: #aaa; border: 1px solid rgba(255,255,255,.15); display: inline-block; border-radius: 999px; padding: 8px 14px; }
  </style>
</head>
<body>
  <main>
    <section>
      <div class="badge">● KI-ASSISTENT · AI ASSISTANT</div>
      <h1>De<span>Bi</span>an</h1>
      <p>Your Digital Rail Assistant</p>
      <input id="apiBase" value="http://127.0.0.1:8000" />
      <button onclick="health()">Check Backend</button>
      <button onclick="human()">Request Human Assistance</button>
    </section>

    <section>
      <h2>Chat</h2>
      <select id="language"><option value="en">English</option><option value="de">Deutsch</option><option value="ta">Tamil</option></select>
      <textarea id="message">I want compensation for delayed train ICE 572</textarea>
      <input id="trainNumber" value="ICE 572" />
      <button onclick="assist()">Ask DeBian</button>

      <h2>Compensation Claim</h2>
      <input id="ticketPrice" value="80" />
      <input id="delayMinutes" value="95" />
      <input id="iban" value="DE89370400440532013000" />
      <button onclick="claim()">Submit Claim</button>

      <pre id="output">Start backend first: python -m app.main</pre>
    </section>
  </main>
<script>
function apiBase(){ return document.getElementById("apiBase").value.replace(/\/$/, ""); }
function show(x){ document.getElementById("output").innerText = typeof x === "string" ? x : JSON.stringify(x, null, 2); }
async function post(path, payload){
  const res = await fetch(apiBase()+path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
  show(await res.json());
}
async function health(){ const res = await fetch(apiBase()+"/"); show(await res.json()); }
async function assist(){
  await post("/assist", {
    message: document.getElementById("message").value,
    language: document.getElementById("language").value,
    train_number: document.getElementById("trainNumber").value
  });
}
async function claim(){
  await post("/claim", {
    train_number: document.getElementById("trainNumber").value,
    planned_start_time: "2026-05-20T10:00:00",
    actual_start_time: "2026-05-20T11:35:00",
    trip_not_started: false,
    alternative_transport: "Regional train",
    ticket_price: Number(document.getElementById("ticketPrice").value),
    delay_minutes: Number(document.getElementById("delayMinutes").value),
    refund_method: "bank_account",
    account_number: document.getElementById("iban").value,
    claim_form: true
  });
}
async function human(){ await post("/human-assistance", {language:"en", reason:"customer requested callback"}); }
</script>
</body>
</html>
"""


class FallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = FALLBACK_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_fallback_ui() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8501), FallbackHandler)
    print("Streamlit not installed. Running fallback UI instead.")
    print("Open http://127.0.0.1:8501")
    server.serve_forever()


if __name__ == "__main__":
    try:
        run_streamlit()
    except ModuleNotFoundError:
        run_fallback_ui()
