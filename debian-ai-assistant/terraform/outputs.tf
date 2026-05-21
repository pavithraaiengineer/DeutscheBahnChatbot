output "artifact_registry_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.debian_repo.repository_id}"
}

output "gke_cluster_name" {
  value = google_container_cluster.gke.name
}

output "gke_cluster_location" {
  value = google_container_cluster.gke.location
}

output "vpc_name" {
  value = google_compute_network.vpc.name
}

output "subnet_name" {
  value = google_compute_subnetwork.subnet.name
}

output "gcs_lake_bucket" {
  value = google_storage_bucket.debian_lake.name
}

output "bigquery_dataset" {
  value = google_bigquery_dataset.analytics.dataset_id
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}
