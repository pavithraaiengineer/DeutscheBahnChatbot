# DeBian AI Rail Assistant

DeBian is a customer-support assistant for rail passengers.

It supports the requested flow:

1. User asks question by voice, image, or text
2. Backend receives request
3. Language is detected
4. Voice is converted to text if needed — MVP placeholder
5. Image is analyzed if uploaded — MVP placeholder
6. Agent classifies intent
7. Agent calls the correct MCP-like tool
8. Delay/compensation data is retrieved
9. PII is masked
10. Response streams back to user
11. Analytics are written locally — production target: BigQuery
12. Evaluation logs are stored for quality improvement

## Why this version is stable

This version avoids the Python 3.14 dependency conflicts you hit earlier.

The backend uses Python standard library only.

No Pydantic, FastAPI, LangChain, or Streamlit is required to run the backend.

The code is structured so real LangChain, MCP, Pinecone, Databricks, BigQuery, and GCP services can be added after the MVP runs.

## Project Structure

```text
debian-ai-assistant/
├── app/
│   ├── main.py
│   ├── agents/
│   │   └── debian_agent.py
│   ├── tools/
│   │   ├── delay_tool.py
│   │   ├── compensation_tool.py
│   │   ├── route_tool.py
│   │   ├── human_handoff_tool.py
│   │   └── pii_masking_tool.py
│   ├── rag/
│   │   ├── retriever.py
│   │   └── query_optimizer.py
│   ├── evaluation/
│   │   └── eval_pipeline.py
│   └── security/
│       └── governance.py
├── frontend/
│   └── streamlit_app.py
├── Dockerfile
├── requirements.txt
└── README.md
```

## Run Backend

From the project root:

```powershell
cd C:\Users\priya\AIcoursework\Final_Project\debian-ai-assistant
python -m app.main
```

Open:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/
```

## Run Frontend Without Installing Streamlit

Open a second PowerShell terminal.

From the project root:

```powershell
python frontend\streamlit_app.py
```

Open:

```text
http://127.0.0.1:8501
```

This starts the no-install fallback UI.

## Optional Streamlit Frontend

Only if you want the real Streamlit UI:

```powershell
pip install streamlit
streamlit run frontend\streamlit_app.py
```

## Test Chat

POST `/assist`:

```json
{
  "message": "I want compensation for delayed train ICE 572",
  "language": "en",
  "train_number": "ICE 572"
}
```

## Test Claim

POST `/claim`:

```json
{
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
}
```

Expected masked output:

```json
"masked_account_number": "******************3000"
```

## Streaming Test

Open in browser:

```text
http://127.0.0.1:8000/stream?message=I%20need%20compensation&language=en
```

## Docker Run

Build:

```powershell
docker build -t debian-ai-assistant .
```

Run:

```powershell
docker run -p 8080:8080 debian-ai-assistant
```

Open:

```text
http://127.0.0.1:8080/docs
```

## GCP Cloud Run Deployment

```bash
gcloud run deploy debian-ai-assistant \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 2
```

## Production Extensions

Add these after the MVP runs:

- LangChain / LangGraph orchestration in `app/agents/debian_agent.py`
- Actual MCP server around `app/tools`
- Pinecone vector DB in `app/rag/retriever.py`
- Databricks ETL and Feature Store
- BigQuery analytics writer in `app/security/governance.py`
- Google Speech-to-Text for voice
- Gemini Vision / Vision API for images
- GKE deployment and Terraform infrastructure
- OpenTelemetry, Prometheus, Grafana, and FinOps dashboards
