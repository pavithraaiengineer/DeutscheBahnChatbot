"""
DeBian guided chatbot frontend.

Replace:
    frontend/streamlit_app.py

Run backend first:
    python -m app.main

Run frontend:
    python frontend\streamlit_app.py

Open:
    http://127.0.0.1:8501

This file supports two modes:
1. Streamlit mode if Streamlit is installed.
2. No-install fallback UI if Streamlit is not installed.
"""

from __future__ import annotations

import json
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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
    st.caption("Guided customer-support assistant for tickets, delay support, compensation, and human handoff.")

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Hello Example user 👋\n\n"
                    "I am DeBian, your Digital Rail Assistant. "
                    "How can I help you today?"
                ),
            }
        ]

    if "claim_step" not in st.session_state:
        st.session_state.claim_step = None

    if "claim_data" not in st.session_state:
        st.session_state.claim_data = {}

    api_base = st.sidebar.text_input("Backend URL", DEFAULT_API_BASE)
    language = st.sidebar.selectbox("Language", ["en", "de", "fr", "ta"])

    if st.sidebar.button("Check Backend"):
        try:
            st.sidebar.success(api_get(api_base, "/")["service"])
        except Exception as error:
            st.sidebar.error(f"Backend not reachable: {error}")

    st.subheader("Quick Actions")
    col1, col2, col3, col4 = st.columns(4)

    if col1.button("🎫 Book a ticket"):
        st.session_state.claim_step = None
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": (
                    "Sure. I can help you book a ticket.\n\n"
                    "Please tell me:\n"
                    "1. Origin station\n"
                    "2. Destination station\n"
                    "3. Travel date\n"
                    "4. Preferred time"
                ),
            }
        )

    if col2.button("💶 Claim compensation"):
        st.session_state.claim_step = "train_number"
        st.session_state.claim_data = {"language": language, "claim_form": True}
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": (
                    "I can guide you through the compensation claim step by step.\n\n"
                    "First question: what is your train number?\n"
                    "Example: ICE 572"
                ),
            }
        )

    if col3.button("🚆 Check delay"):
        st.session_state.claim_step = "delay_train_number"
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": "Please enter your train number.\nExample: ICE 572",
            }
        )

    if col4.button("☎️ Human assistance"):
        st.session_state.claim_step = None
        try:
            result = api_post(
                api_base,
                "/human-assistance",
                {"language": language, "reason": "customer clicked human assistance"},
            )
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "I created a human assistance request.\n\n"
                        f"{json.dumps(result, indent=2, ensure_ascii=False)}"
                    ),
                }
            )
        except Exception as error:
            st.session_state.messages.append(
                {"role": "assistant", "content": f"Could not request human assistance: {error}"}
            )

    st.divider()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("Type your answer here...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        if st.session_state.claim_step:
            response = handle_guided_step_streamlit(user_input, api_base)
            st.session_state.messages.append({"role": "assistant", "content": response})
        else:
            try:
                response = api_post(
                    api_base,
                    "/assist",
                    {"message": user_input, "language": language},
                )
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": response.get("response", json.dumps(response, indent=2, ensure_ascii=False)),
                    }
                )
            except Exception as error:
                st.session_state.messages.append(
                    {"role": "assistant", "content": f"Backend error: {error}"}
                )

        st.rerun()


def handle_guided_step_streamlit(user_input: str, api_base: str) -> str:
    import streamlit as st

    step = st.session_state.claim_step
    claim = st.session_state.claim_data

    if step == "delay_train_number":
        try:
            result = api_get(api_base, f"/delay/{user_input.strip()}")
            st.session_state.claim_step = None
            return f"Delay status:\n\n{json.dumps(result, indent=2, ensure_ascii=False)}"
        except Exception as error:
            st.session_state.claim_step = None
            return f"Could not check delay: {error}"

    if step == "train_number":
        claim["train_number"] = user_input.strip()
        st.session_state.claim_step = "planned_start_time"
        return "Thank you. What was your planned start time?\nExample: 2026-05-20T10:00:00"

    if step == "planned_start_time":
        claim["planned_start_time"] = user_input.strip()
        st.session_state.claim_step = "actual_or_not_started"
        return "Did the train actually start?\n\nEnter the actual start time, or type: not started"

    if step == "actual_or_not_started":
        if "not" in user_input.lower():
            claim["trip_not_started"] = True
            claim["actual_start_time"] = None
        else:
            claim["trip_not_started"] = False
            claim["actual_start_time"] = user_input.strip()

        st.session_state.claim_step = "delay_minutes"
        return "How many minutes was the delay?\nExample: 95"

    if step == "delay_minutes":
        try:
            claim["delay_minutes"] = int(user_input.strip())
        except ValueError:
            return "Please enter the delay as a number of minutes.\nExample: 95"

        st.session_state.claim_step = "alternative_transport"
        return "Which alternative travel option did you use?\nExample: Regional train, next ICE, bus, taxi, or none"

    if step == "alternative_transport":
        claim["alternative_transport"] = user_input.strip() or "none"
        st.session_state.claim_step = "ticket_price"
        return "What was the ticket price in EUR?\nExample: 80"

    if step == "ticket_price":
        try:
            claim["ticket_price"] = float(user_input.strip().replace(",", "."))
        except ValueError:
            return "Please enter the ticket price as a number.\nExample: 80"

        st.session_state.claim_step = "refund_method"
        return "How would you like to receive compensation?\n\nType exactly: bank_account or voucher"

    if step == "refund_method":
        value = user_input.strip().lower()
        if value not in {"bank_account", "voucher"}:
            return "Please type exactly one of these options:\n\nbank_account\nvoucher"

        claim["refund_method"] = value

        if value == "bank_account":
            st.session_state.claim_step = "account_number"
            return "Please enter your IBAN/account number.\n\nFor security, DeBian will only show the last 4 digits."
        else:
            st.session_state.claim_step = "home_address"
            return "Please enter your home address for the voucher confirmation."

    if step == "account_number":
        claim["account_number"] = user_input.strip()
        claim["home_address"] = None
        return submit_guided_claim_streamlit(api_base)

    if step == "home_address":
        claim["home_address"] = user_input.strip()
        claim["account_number"] = None
        return submit_guided_claim_streamlit(api_base)

    st.session_state.claim_step = None
    return "Something went wrong. Please start again with Claim compensation."


def submit_guided_claim_streamlit(api_base: str) -> str:
    import streamlit as st

    claim = st.session_state.claim_data

    try:
        result = api_post(api_base, "/claim", claim)
        st.session_state.claim_step = None
        st.session_state.claim_data = {}

        return (
            "Your compensation claim has been submitted.\n\n"
            "Security confirmation: your account number is masked and only the last four digits are visible.\n\n"
            f"{json.dumps(result, indent=2, ensure_ascii=False)}"
        )
    except Exception as error:
        st.session_state.claim_step = None
        st.session_state.claim_data = {}
        return f"Could not submit claim: {error}"


FALLBACK_HTML = r"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>DeBian Guided Chatbot</title>
  <style>
    :root {
      --db-red: #e30613;
      --bg: #111113;
      --panel: rgba(255,255,255,.08);
      --border: rgba(255,255,255,.14);
      --text: #f7f7f7;
      --muted: #aaa;
    }

    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background:
        radial-gradient(circle at 70% 80%, rgba(227, 6, 19, .32), transparent 32%),
        radial-gradient(circle at 20% 20%, rgba(57, 86, 255, .20), transparent 24%),
        var(--bg);
      color: var(--text);
      min-height: 100vh;
    }

    main {
      max-width: 1100px;
      margin: 0 auto;
      padding: 28px;
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 22px;
    }

    section {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 26px;
      box-shadow: 0 20px 70px rgba(0,0,0,.35);
      backdrop-filter: blur(14px);
    }

    .badge {
      color: var(--muted);
      border: 1px solid var(--border);
      display: inline-block;
      border-radius: 999px;
      padding: 8px 14px;
      letter-spacing: 1.5px;
      font-size: 12px;
    }

    h1 {
      font-size: 60px;
      margin: 28px 0 4px;
      letter-spacing: -2px;
    }

    h1 span { color: var(--db-red); }

    input, textarea, select, button {
      width: 100%;
      box-sizing: border-box;
      padding: 13px;
      border-radius: 14px;
      margin: 8px 0;
      background: rgba(0,0,0,.28);
      color: white;
      border: 1px solid var(--border);
      outline: none;
    }

    button {
      background: var(--db-red);
      border: none;
      cursor: pointer;
      font-weight: bold;
      transition: .2s;
    }

    button:hover {
      filter: brightness(1.1);
      transform: translateY(-1px);
    }

    .secondary {
      background: rgba(255,255,255,.12);
      border: 1px solid var(--border);
    }

    .quick-actions {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      margin: 16px 0;
    }

    .chat-box {
      height: 520px;
      overflow-y: auto;
      background: rgba(0,0,0,.25);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 16px;
    }

    .msg {
      max-width: 84%;
      padding: 12px 14px;
      border-radius: 16px;
      margin: 10px 0;
      white-space: pre-wrap;
      line-height: 1.45;
    }

    .bot {
      background: rgba(255,255,255,.12);
      border: 1px solid var(--border);
    }

    .user {
      background: var(--db-red);
      margin-left: auto;
    }

    .row {
      display: grid;
      grid-template-columns: 1fr 130px;
      gap: 10px;
      margin-top: 14px;
    }

    .hint {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
    }

    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; padding: 18px; }
    }
  </style>
</head>
<body>
  <main>
    <section>
      <div class="badge">● KI-ASSISTENT · AI ASSISTANT</div>
      <h1>De<span>Bi</span>an</h1>
      <p>Your Digital Rail Assistant</p>

      <label>Backend URL</label>
      <input id="apiBase" value="http://127.0.0.1:8000" />

      <label>Language</label>
      <select id="language">
        <option value="en">English</option>
        <option value="de">Deutsch</option>
        <option value="fr">Français</option>
        <option value="ta">தமிழ்</option>
      </select>

      <button class="secondary" onclick="checkBackend()">Check Backend</button>
      <p id="backendStatus" class="hint">Backend not checked yet.</p>

      <p class="hint">
        Start backend first:
        <br><b>python -m app.main</b>
      </p>
    </section>

    <section>
      <h2>Hello Example user 👋</h2>
      <p class="hint">I am DeBian, your Digital Rail Assistant. How can I help you today?</p>

      <div class="quick-actions">
        <button onclick="startBooking()">🎫 Book a ticket</button>
        <button onclick="startClaim()">💶 Claim compensation</button>
        <button onclick="startDelay()">🚆 Check delay</button>
        <button onclick="humanAssistance()">☎️ Human assistance</button>
      </div>

      <div id="chatBox" class="chat-box"></div>

      <div class="row">
        <input id="userInput" placeholder="Type your answer here..." onkeydown="if(event.key==='Enter'){sendUserInput();}" />
        <button onclick="sendUserInput()">Send</button>
      </div>
    </section>
  </main>

<script>
let claimStep = null;
let claimData = {};

function apiBase() {
  return document.getElementById("apiBase").value.replace(/\/$/, "");
}

function language() {
  return document.getElementById("language").value;
}

function addMessage(role, text) {
  const chatBox = document.getElementById("chatBox");
  const div = document.createElement("div");
  div.className = "msg " + (role === "user" ? "user" : "bot");
  div.innerText = text;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function post(path, payload) {
  const res = await fetch(apiBase() + path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  return await res.json();
}

async function checkBackend() {
  try {
    const res = await fetch(apiBase() + "/");
    const data = await res.json();
    document.getElementById("backendStatus").innerText = "✅ Backend running: " + data.service;
  } catch (e) {
    document.getElementById("backendStatus").innerText = "❌ Backend not reachable. Start backend first.";
  }
}

function startBooking() {
  claimStep = null;
  addMessage("bot", "Sure. I can help you book a ticket.\n\nPlease tell me:\n1. Origin station\n2. Destination station\n3. Travel date\n4. Preferred time");
}

function startClaim() {
  claimStep = "train_number";
  claimData = {
    language: language(),
    claim_form: true
  };
  addMessage("bot", "I can guide you through the compensation claim step by step.");
  addMessage("bot", "First question: what is your train number?\nExample: ICE 572");
}

function startDelay() {
  claimStep = "delay_train_number";
  addMessage("bot", "Please enter your train number.\nExample: ICE 572");
}

async function humanAssistance() {
  claimStep = null;
  const result = await post("/human-assistance", {
    language: language(),
    reason: "customer clicked human assistance"
  });
  addMessage("bot", "Human assistance request created:\n" + JSON.stringify(result, null, 2));
}

async function sendUserInput() {
  const input = document.getElementById("userInput");
  const text = input.value.trim();
  if (!text) return;

  addMessage("user", text);
  input.value = "";

  if (claimStep) {
    await handleGuidedStep(text);
    return;
  }

  const result = await post("/assist", {
    message: text,
    language: language()
  });
  addMessage("bot", result.response || JSON.stringify(result, null, 2));
}

async function handleGuidedStep(text) {
  if (claimStep === "delay_train_number") {
    const res = await fetch(apiBase() + "/delay/" + encodeURIComponent(text));
    const data = await res.json();
    addMessage("bot", "Delay status:\n" + JSON.stringify(data, null, 2));
    claimStep = null;
    return;
  }

  if (claimStep === "train_number") {
    claimData.train_number = text;
    claimStep = "planned_start_time";
    addMessage("bot", "Thank you. What was your planned start time?\nExample: 2026-05-20T10:00:00");
    return;
  }

  if (claimStep === "planned_start_time") {
    claimData.planned_start_time = text;
    claimStep = "actual_or_not_started";
    addMessage("bot", "Did the train actually start?\n\nEnter the actual start time, or type: not started");
    return;
  }

  if (claimStep === "actual_or_not_started") {
    if (text.toLowerCase().includes("not")) {
      claimData.trip_not_started = true;
      claimData.actual_start_time = null;
    } else {
      claimData.trip_not_started = false;
      claimData.actual_start_time = text;
    }
    claimStep = "delay_minutes";
    addMessage("bot", "How many minutes was the delay?\nExample: 95");
    return;
  }

  if (claimStep === "delay_minutes") {
    const minutes = Number(text);
    if (!Number.isFinite(minutes)) {
      addMessage("bot", "Please enter the delay as a number.\nExample: 95");
      return;
    }
    claimData.delay_minutes = minutes;
    claimStep = "alternative_transport";
    addMessage("bot", "Which alternative travel option did you use?\nExample: Regional train, next ICE, bus, taxi, or none");
    return;
  }

  if (claimStep === "alternative_transport") {
    claimData.alternative_transport = text || "none";
    claimStep = "ticket_price";
    addMessage("bot", "What was the ticket price in EUR?\nExample: 80");
    return;
  }

  if (claimStep === "ticket_price") {
    const price = Number(text.replace(",", "."));
    if (!Number.isFinite(price)) {
      addMessage("bot", "Please enter the ticket price as a number.\nExample: 80");
      return;
    }
    claimData.ticket_price = price;
    claimStep = "refund_method";
    addMessage("bot", "How would you like to receive compensation?\n\nType exactly: bank_account or voucher");
    return;
  }

  if (claimStep === "refund_method") {
    const method = text.toLowerCase();
    if (method !== "bank_account" && method !== "voucher") {
      addMessage("bot", "Please type exactly: bank_account or voucher");
      return;
    }

    claimData.refund_method = method;

    if (method === "bank_account") {
      claimStep = "account_number";
      addMessage("bot", "Please enter your IBAN/account number.\n\nFor security, DeBian will only show the last 4 digits.");
    } else {
      claimStep = "home_address";
      addMessage("bot", "Please enter your home address for the voucher confirmation.");
    }
    return;
  }

  if (claimStep === "account_number") {
    claimData.account_number = text;
    claimData.home_address = null;
    await submitClaim();
    return;
  }

  if (claimStep === "home_address") {
    claimData.home_address = text;
    claimData.account_number = null;
    await submitClaim();
    return;
  }
}

async function submitClaim() {
  const result = await post("/claim", claimData);
  addMessage("bot", "Your compensation claim has been submitted.");
  addMessage("bot", "Security confirmation: your account number is masked. Only the last four digits are visible.");
  addMessage("bot", JSON.stringify(result, null, 2));
  claimStep = null;
  claimData = {};
}

addMessage("bot", "Hello Example user 👋\n\nI am DeBian, your Digital Rail Assistant.");
addMessage("bot", "Please choose one option:\n\n🎫 Book a ticket\n💶 Claim compensation\n🚆 Check delay\n☎️ Human assistance");
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
    print("Streamlit not installed. Running guided fallback UI.")
    print("Open http://127.0.0.1:8501")
    server.serve_forever()


if __name__ == "__main__":
    try:
        run_streamlit()
    except ModuleNotFoundError:
        run_fallback_ui()
