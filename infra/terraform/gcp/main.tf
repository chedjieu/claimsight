# ClaimSight on GCP — Cloud Run + Cloud SQL + Memorystore + GCS.
# Apply after local Phase 4 demo. Does not rewrite agent code.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_sql_database_instance" "claimsight" {
  name             = "claimsight-pg"
  database_version = "POSTGRES_16"
  region           = var.region
  settings {
    tier = "db-custom-1-3840"
    database_flags {
      name  = "cloudsql.enable_pgvector"
      value = "on"
    }
  }
}

resource "google_sql_database" "app" {
  name     = "claimsight"
  instance = google_sql_database_instance.claimsight.name
}

resource "google_storage_bucket" "docs" {
  name     = "${var.project_id}-claimsight-docs"
  location = var.region
}

resource "google_redis_instance" "broker" {
  name           = "claimsight-redis"
  tier           = "BASIC"
  memory_size_gb = 1
  region         = var.region
}

resource "google_cloud_run_v2_service" "api" {
  name     = "claimsight-api"
  location = var.region
  template {
    containers {
      image = "gcr.io/${var.project_id}/claimsight-api:latest"
      ports {
        container_port = 8000
      }
      env {
        name  = "S3_BUCKET"
        value = google_storage_bucket.docs.name
      }
    }
  }
}

output "api_uri" {
  value = google_cloud_run_v2_service.api.uri
}
