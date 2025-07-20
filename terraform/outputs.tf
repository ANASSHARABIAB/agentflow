output "shared_knowledgebase_bucket" {
  value = google_storage_bucket.shared_knowledgebase.name
}

output "user_data_bucket" {
  value = google_storage_bucket.user_data.name
}
