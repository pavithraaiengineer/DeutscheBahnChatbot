provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

resource "google_compute_network" "vpc" {
  name                    = "debian-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "debian-subnet"
  ip_cidr_range = "10.10.0.0/20"
  region        = var.region
  network       = google_compute_network.vpc.id
}

resource "google_artifact_registry_repository" "debian_repo" {
  location      = var.region
  repository_id = "debian"
  description   = "Docker repository for DeBian AI Assistant"
  format        = "DOCKER"
}

resource "google_storage_bucket" "debian_lake" {
  name                        = "${var.project_id}-debian-lake"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
}

resource "google_bigquery_dataset" "analytics" {
  dataset_id                 = var.bigquery_dataset
  location                   = "EU"
  delete_contents_on_destroy = true
}

resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
}

resource "google_secret_manager_secret" "db_client_id" {
  secret_id = "debian-db-client-id"
  replication { auto {} }
}

resource "google_secret_manager_secret" "db_api_key" {
  secret_id = "debian-db-api-key"
  replication { auto {} }
}

resource "google_secret_manager_secret" "pinecone_api_key" {
  secret_id = "debian-pinecone-api-key"
  replication { auto {} }
}

resource "google_service_account" "runtime" {
  account_id   = "debian-runtime"
  display_name = "DeBian Runtime Service Account"
}

resource "google_project_iam_member" "runtime_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_container_cluster" "gke" {
  name     = var.cluster_name
  location = var.zone

  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.subnet.name

  remove_default_node_pool = true
  initial_node_count       = 1

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

resource "google_container_node_pool" "nodes" {
  name       = "debian-node-pool"
  location   = var.zone
  cluster    = google_container_cluster.gke.name
  node_count = 1

  node_config {
    machine_type    = "e2-standard-2"
    service_account = google_service_account.runtime.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  autoscaling {
    min_node_count = 1
    max_node_count = 3
  }
}
