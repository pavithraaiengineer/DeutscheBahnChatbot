# DeBian Production Architecture

```text
User
 ↓
Web / Mobile UI
Text + Voice + Image + Multilingual Support
 ↓
GKE Ingress / API Gateway
 ↓
Kubernetes Services on GKE
 ├── FastAPI backend
 ├── LangChain / LangGraph agent service
 ├── MCP tool server
 ├── Streaming service
 ├── Human handoff service
 └── Evaluation service
 ↓
Data Layer
 ├── Cloud Storage: raw files, images, documents
 ├── Dataflow / Dataproc / Databricks ETL pipelines
 ├── BigQuery: analytics + reporting
 ├── Databricks Delta Lake: governed lakehouse
 ├── Feature Store: delay prediction features
 ├── Pinecone: vector database for RAG
 └── Cloud SQL / Firestore: user sessions, claims, status
 ↓
Security + Governance
 ├── Secret Manager
 ├── IAM
 ├── Kubernetes RBAC
 ├── Cloud DLP API
 ├── Databricks Unity Catalog
 ├── Audit logs
 └── PII masking
 ↓
Monitoring + FinOps
 ├── Cloud Monitoring
 ├── Cloud Logging
 ├── Prometheus / Grafana
 ├── OpenTelemetry
 └── Cost dashboards
```

## Terraform-managed infrastructure

- GKE cluster
- VPC + subnets
- Artifact Registry
- Cloud Storage buckets
- BigQuery datasets
- Cloud SQL / Firestore
- Secret Manager secrets
- IAM roles
- Service accounts
- Monitoring resources

## Kubernetes services

- debian-api-service
- debian-agent-service
- debian-mcp-tool-server
- debian-rag-service
- debian-compensation-service
- debian-human-handoff-service
- debian-evaluation-service

The local MVP runs these modules in one backend process. The production design splits them into microservices.

## Data layers

### Bronze Layer

- Raw DB Open Data
- GTFS
- Delay logs
- Uploaded images
- Documents

### Silver Layer

- Cleaned station data
- Train schedules
- Delay events
- Passenger-rights docs

### Gold Layer

- Compensation eligibility table
- Route recommendation table
- Customer-support analytics
- Delay prediction features

## Feature Store columns

- train_number
- route_id
- station_id
- planned_departure_time
- historical_delay_minutes
- weekday
- weather_signal
- route_congestion_score
- previous_station_delay
- cancellation_flag

## ML / decision use cases

- Predict delay risk
- Estimate compensation eligibility
- Recommend alternative travel routes
- Prioritize human escalation

## RAG documents

- DB help documents
- Passenger-rights policy
- Compensation rules
- Station FAQs
- Ticket refund instructions
- Multilingual support articles
- Internal SOP documents

## Pinecone metadata

```json
{
  "language": "de / en",
  "document_type": "passenger_rights",
  "region": "germany",
  "valid_from": "2026-01-01",
  "valid_to": "2026-12-31",
  "source_url": "internal://source",
  "confidence_score": 0.95
}
```
