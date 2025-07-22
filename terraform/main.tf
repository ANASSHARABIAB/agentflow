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

# Reference the existing secret in Secret Manager
data "google_secret_manager_secret_version" "upload_service_sa_key" {
  secret  = "upload-service-sa-key"
  project = var.project_id
  # If you want the latest version, omit version; otherwise, specify it
}

# Grant Secret Manager Accessor to the Cloud Run service account
resource "google_project_iam_member" "upload_service_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.upload_service_sa.email}"
}

# Update Cloud Run to mount the secret as a file and set env var
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
        env {
          name  = "GOOGLE_APPLICATION_CREDENTIALS"
          value = "/secrets/upload-service-sa-key"
        }
      }

      # Mount the secret as a file
      volumes {
        name = "upload-service-sa-key"
        secret {
          secret_name = data.google_secret_manager_secret_version.upload_service_sa_key.secret
          items {
            key  = data.google_secret_manager_secret_version.upload_service_sa_key.secret
            path = "upload-service-sa-key"
          }
        }
      }

      containers {
        # ... existing container config ...
        volume_mounts {
          name      = "upload-service-sa-key"
          mount_path = "/secrets"
          read_only = true
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

# Storage Object Admin on both buckets
resource "google_storage_bucket_iam_member" "user_data_object_admin" {
  bucket = google_storage_bucket.user_data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.upload_service_sa.email}"
}

resource "google_storage_bucket_iam_member" "shared_knowledgebase_object_admin" {
  bucket = google_storage_bucket.shared_knowledgebase.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.upload_service_sa.email}"
}

# Firestore User
resource "google_project_iam_member" "upload_service_firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.upload_service_sa.email}"
}
