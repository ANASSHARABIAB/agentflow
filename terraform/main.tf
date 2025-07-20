terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  required_version = ">= 1.0"
}

provider "google" {
  project = var.project_id
  region  = var.gcs_location
}

# Global bucket for shared knowledge base and prompts
resource "google_storage_bucket" "shared_knowledgebase" {
  name                        = "${var.project_id}-shared-knowledgebase"
  location                    = var.gcs_location
  force_destroy               = true
  uniform_bucket_level_access = true

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 365
    }
  }
}

# User data bucket (documents, saved prompts, uploads)
resource "google_storage_bucket" "user_data" {
  name                        = "${var.project_id}-user-data"
  location                    = var.gcs_location
  force_destroy               = true
  uniform_bucket_level_access = true
}

# Service account for Cloud Run
resource "google_service_account" "upload_service_sa" {
  account_id   = "upload-service-sa"
  display_name = "Upload Service Cloud Run Service Account"
}

resource "google_cloud_run_service" "upload_service" {
  name     = "upload-service"
  location = var.gcs_location

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/upload-service:latest" # Adjust tag as needed

        env {
          name  = "USER_BUCKET"
          value = google_storage_bucket.user_data.name
        }
        env {
          name  = "SHARED_BUCKET"
          value = google_storage_bucket.shared_knowledgebase.name
        }
      }
      service_account_name = google_service_account.upload_service_sa.email
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Allow public unauthenticated invocations (for public API)
resource "google_cloud_run_service_iam_member" "public_invoker" {
  location = google_cloud_run_service.upload_service.location
  project  = var.project_id
  service  = google_cloud_run_service.upload_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}