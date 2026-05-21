variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  default     = "europe-west1"
}

variable "zone" {
  type        = string
  default     = "europe-west1-b"
}

variable "cluster_name" {
  type        = string
  default     = "debian-gke"
}

variable "bigquery_dataset" {
  type        = string
  default     = "debian_analytics"
}
