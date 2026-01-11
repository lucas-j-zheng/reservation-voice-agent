# Terraform Configuration Placeholder
# For future GCP/Railway deployment

terraform {
  required_version = ">= 1.0"

  # Backend configuration will be added when deploying
  # backend "gcs" {
  #   bucket = "sam-terraform-state"
  #   prefix = "terraform/state"
  # }
}

# Provider configuration placeholder
# provider "google" {
#   project = var.project_id
#   region  = var.region
# }

# Variables placeholder
variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# Outputs placeholder
output "status" {
  value = "Terraform infrastructure not yet configured"
}
