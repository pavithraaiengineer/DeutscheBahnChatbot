"""
DeBian guided frontend.

Run:
    python frontend\streamlit_app.py

Open:
    http://127.0.0.1:8501
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


FALLBACK_HTML = r"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>DeBian Guided Chatbot</title>
  <style>
    :root { --red:#e30613; --bg:#111113; --panel:rgba(255,255,255,.08); --border:rgba(255,255,255,.14); --muted:#aaa; }
    body { margin:0; font-family:Arial,sans-serif; background:radial-gradient(circle at 70% 80%, rgba(227,6,19,.32), transparent 32%), radial-gradient(circle at 20% 20%, rgba(57,86,255,.20), transparent 24%), var(--bg); color:white; min-height:100vh; }
    main { max-width:1120px; margin:0 auto; padding:28px; display:grid; grid-template-columns:340px 1fr; gap:22px; }
    section { background:var(--panel); border:1px solid var(--border); border-radius:28px; padding:26px; box-shadow:0 20px 70px rgba(0,0,0,.35); }
    h1 { font-size:60px; margin:28px 0 4px; letter-spacing:-2px; } h1 span { color:var(--red); }
    input, select, button { width:100%; box-sizing:border-box; padding:13px; border-radius:14px; margin:8px 0; background:rgba(0,0,0,.28); color:white; border:1px solid var(--border); }
    button { background:var(--red); border:none; cursor:pointer; font-weight:bold; }
    .secondary { background:rgba(255,255,255,.12); border:1px solid var(--border); }
    .quick { display:grid; grid-template-columns:repeat(2,1fr); gap:10px; margin:16px 0; }
    .chat { height:540px; overflow-y:auto; background:rgba(0,0,0,.25); border:1px solid var(--border); border-radius:20px; padding:16px; }
    .msg { max-width:84%; padding:12px 14px; border-radius:16px; margin:10px 0; white-space:pre-wrap; line-height:1.45; }
    .bot { background:rgba(255,255,255,.12); border:1px solid var(--border); }
    .user { background:var(--red); margin-left:auto; }
    .row { display:grid; grid-template-columns:1fr 130px; gap:10px; margin-top:14px; }
    .hint { color:var(--muted); font-size:13px; line-height:1.4; }
    @media(max-width:900px){ main{grid-template-columns:1fr; padding:18px;} }
  </style>
</head>
<body>
<main>
<section>
  <h1>De<span>Bi</span>an</h1>
  <p>Your Digital Rail Assistant</p>
  <input id="apiBase" value="http://127.0.0.1:8000" />
  <select id="language"><option value="en">English</option><option value="de">Deutsch</option><option value="ta">தமிழ்</option></select>
  <button class="secondary" onclick="checkBackend()">Check Backend</button>
  <button class="secondary" onclick="runETL()">Run ETL</button>
  <button class="secondary" onclick="infra()">Infra Status</button>
  <p id="status" class="hint">Start backend first: python -m app.main</p>
</section>
<section>
  <h2>Hello Example user 👋</h2>
  <p class="hint">I am DeBian. I can help with delay checks, compensation claims, alternative routes, and human support.</p>
  <div class="quick">
    <button onclick="book()">🎫 Book a ticket</button>
    <button onclick="startClaim()">💶 Claim compensation</button>
    <button onclick="startDelay()">🚆 Check delay</button>
    <button onclick="human()">☎️ Human assistance</button>
  </div>
  <div id="chat" class="chat"></div>
  <div class="row"><input id="input" placeholder="Type here..." onkeydown="if(event.key==='Enter')send()" /><button onclick="send()">Send</button></div>
</section>
</main>
<script>
let step=null, claim={};

function api(){return document.getElementById("apiBase").value.replace(/\/$/,"")}
function lang(){return document.getElementById("language").value}
function add(role,text){
  let d=document.createElement("div");
  d.className="msg "+(role==="user"?"user":"bot");
  d.innerText=text;
  chat.appendChild(d);
  chat.scrollTop=chat.scrollHeight;
}

async function post(path,payload){
  let r=await fetch(api()+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  return await r.json();
}
async function get(path){let r=await fetch(api()+path); return await r.json();}

function formatDelay(d){
  const train = d.train_number || "your train";
  if(d.status === "unknown"){
    return `I could not find delay data for ${train} yet.\n\nFor this demo, try ICE 572, ICE 999, or RE 50.\nFor live mode, configure DB API credentials and provide station name plus planned start time.`;
  }
  let lines = [`Status for ${train}: ${d.status}.`];
  if(d.delay_minutes !== null && d.delay_minutes !== undefined) lines.push(`Delay: approximately ${d.delay_minutes} minutes.`);
  if(d.origin && d.destination) lines.push(`Route: ${d.origin} → ${d.destination}.`);
  if(d.station_name) lines.push(`Station: ${d.station_name}.`);
  if(d.planned_start_time) lines.push(`Planned start time: ${d.planned_start_time}.`);
  if(d.actual_start_time) lines.push(`Actual start time: ${d.actual_start_time}.`);
  if(d.platform) lines.push(`Platform: ${d.platform}.`);
  if(String(d.source || "").startsWith("mock")) lines.push("Note: this is demo data. For live data, configure DB API credentials.");
  if(d.delay_minutes >= 60) lines.push("You may be able to continue with a compensation claim.");
  return lines.join("\n");
}

function formatClaim(r){
  let c = r.compensation || {};
  let lines = [`Your compensation claim has been submitted.\nReference: ${r.claim_id || "created"}.`];
  if(c.eligible){
    lines.push(`Estimated compensation: ${c.percentage}% = ${c.amount} ${c.currency || "EUR"}.`);
  } else {
    lines.push("Based on the demo rules, this journey is probably not eligible for compensation.");
  }
  if(r.masked_account_number) lines.push(`Confirmed account: ${r.masked_account_number}.`);
  if(r.home_address_confirmed) lines.push("Voucher delivery address has been confirmed.");
  lines.push("Sensitive data has been masked.");
  return lines.join("\n");
}

async function checkBackend(){
  try{
    let d=await get("/");
    status.innerText="✅ "+d.service+" | LLM configured: "+d.config.llm_configured;
  }catch(e){status.innerText="❌ Backend not reachable";}
}
async function runETL(){
  let d=await get("/etl/run");
  add("bot", `Data layer pipeline completed.\n\nBronze, Silver, and Gold layers were generated.\nPipeline: ${d.pipeline}`);
}
async function infra(){
  let d=await get("/infra/status");
  add("bot", `Infrastructure status checked.\n\nLLM configured: ${d.config.llm_configured}\nPinecone configured: ${d.config.pinecone_configured}\nDatabricks configured: ${d.config.databricks_configured}\nSession store: ${d.session_store.mode}`);
}

function book(){step=null; add("bot","Please tell me origin, destination, date, and preferred time.");}
function startClaim(){
  step="train_number";
  claim={language:lang(), claim_form:true};
  add("bot","I will guide your compensation claim step by step.\n\nWhat is your train number?\nExample: ICE 572");
}
function startDelay(){step="delay_train"; add("bot","Enter train number.\nExample: ICE 572, ICE 999, or RE 50");}
async function human(){
  const r = await post("/human-assistance",{language:lang(),reason:"customer clicked human assistance"});
  add("bot", `I created a human assistance request.\nReference: ${r.handoff_id}\nStatus: ${r.handoff_status}`);
}

async function send(){
  let t=input.value.trim();
  if(!t)return;
  add("user",t);
  input.value="";
  if(step){await guided(t); return;}
  let r=await post("/assist",{message:t,language:lang()});
  add("bot", r.response + (r.used_llm ? "\n\nLLM: used" : "\n\nLLM: fallback mode"));
}

async function guided(t){
 if(step==="delay_train"){
   const d = await get("/delay/"+encodeURIComponent(t));
   add("bot", formatDelay(d));
   step=null;
   return;
 }
 if(step==="train_number"){claim.train_number=t; step="station_name"; add("bot","Which station should I use?\nExample: Frankfurt(Main)Hbf"); return;}
 if(step==="station_name"){claim.station_name=t; step="planned_start_time"; add("bot","What was your planned start time?\nExample: 2026-05-20T10:00:00"); return;}
 if(step==="planned_start_time"){claim.planned_start_time=t; step="actual"; add("bot","What was the actual start time?\nYou can also type: not started"); return;}
 if(step==="actual"){
   if(t.toLowerCase().includes("not")){claim.trip_not_started=true; claim.actual_start_time=null;}
   else{claim.trip_not_started=false; claim.actual_start_time=t;}
   step="delay"; add("bot","How many minutes was the delay?\nExample: 95"); return;
 }
 if(step==="delay"){claim.delay_minutes=Number(t); step="alternative"; add("bot","Which alternative travel option did you use?\nExample: Regional train, next ICE, bus, taxi, or none"); return;}
 if(step==="alternative"){claim.alternative_transport=t||"none"; step="price"; add("bot","What was the ticket price in EUR?\nExample: 80"); return;}
 if(step==="price"){claim.ticket_price=Number(t.replace(",",".")); step="refund"; add("bot","How would you like to receive compensation?\nType: bank_account or voucher"); return;}
 if(step==="refund"){
   claim.refund_method=t.toLowerCase();
   if(claim.refund_method==="bank_account"){step="account"; add("bot","Please enter your IBAN/account number.\nI will only show the last 4 digits.");}
   else{step="address"; add("bot","Please enter your home address for voucher confirmation.");}
   return;
 }
 if(step==="account"){claim.account_number=t; claim.home_address=null; await submit(); return;}
 if(step==="address"){claim.home_address=t; claim.account_number=null; await submit(); return;}
}
async function submit(){
  let r=await post("/claim",claim);
  add("bot", formatClaim(r));
  step=null; claim={};
}

add("bot","Hello Example user 👋\n\nI am DeBian, your Digital Rail Assistant.");
add("bot","Choose: Book a ticket, Claim compensation, Check delay, or Human assistance.");
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
    print("Running DeBian UI at http://127.0.0.1:8501")
    server.serve_forever()


if __name__ == "__main__":
    run_fallback_ui()
