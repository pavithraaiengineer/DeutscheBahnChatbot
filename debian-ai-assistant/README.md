# DeBian AI Rail Assistant

DeBian is a production-style AI customer-support assistant for rail passengers.

It includes:

- guided chatbot frontend
- text, voice placeholder, image placeholder, multilingual support
- compensation claim workflow
- real-time-ready delay lookup
- PII masking
- MCP-style tools
- RAG with Pinecone or local fallback
- Databricks-style Bronze/Silver/Gold ETL
- Feature Store style delay prediction features
- evaluation logs
- analytics/audit logs
- Kubernetes manifests for GKE
- Terraform for GCP infrastructure

## Project structure

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

Extra production folders are also included:

```text
app/databricks/
app/vector_db/
app/session_store/
k8s/
terraform/
scripts/
docs/
```

## Run backend locally

```powershell
cd debian-ai-assistant
python -m app.main
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Run frontend locally

No-install fallback UI:

```powershell
python frontend\streamlit_app.py
```

Open:

```text
http://127.0.0.1:8501
```

Optional Streamlit UI:

```powershell
pip install streamlit
streamlit run frontend\streamlit_app.py
```

## Important test URLs

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/infra/status
http://127.0.0.1:8000/etl/run
http://127.0.0.1:8000/features
http://127.0.0.1:8000/feature?train=ICE%20572
http://127.0.0.1:8000/rag-search?query=refund%20delay&language=en
http://127.0.0.1:8000/eval/run
http://127.0.0.1:8000/delay/ICE%20572
```

## Demo claim flow

Use the frontend and click **Claim compensation**.

Use:

```text
Train number: ICE 572
Station: Frankfurt(Main)Hbf
Planned start time: 2026-05-20T10:00:00
Actual start time: 2026-05-20T11:35:00
Delay: 95
Alternative transport: Regional train
Ticket price: 80
Refund method: bank_account
IBAN: DE89370400440532013000
```

Expected:

```text
Compensation: 25%
Amount: 20 EUR
Masked account: ******************3000
```

## .env

Create local `.env` from `.env.example`.

Never push `.env`.

## Docker

```powershell
docker build -t debian-ai-assistant .
docker run -p 8080:8080 debian-ai-assistant
```

Open:

```text
http://127.0.0.1:8080/docs
```

## Terraform

```powershell
cd terraform
copy terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

## GKE deploy

After Terraform:

```powershell
.\scripts\deploy_gke.ps1 -ProjectId your-gcp-project-id
```

## Architecture

See:

```text
docs/ARCHITECTURE.md
```
