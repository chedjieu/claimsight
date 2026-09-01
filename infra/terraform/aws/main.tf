# ClaimSight on AWS — ECS Fargate + RDS + ElastiCache + S3.
# Same app contracts as local Compose and GCP.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "db_password" {
  type      = string
  sensitive = true
}

provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "docs" {
  bucket = "claimsight-docs-${var.region}"
}

resource "aws_db_instance" "pg" {
  identifier          = "claimsight-pg"
  engine              = "postgres"
  engine_version      = "16"
  instance_class      = "db.t3.medium"
  allocated_storage   = 20
  db_name             = "claimsight"
  username            = "claimsight"
  password            = var.db_password
  skip_final_snapshot = true
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "claimsight-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
}

resource "aws_ecs_cluster" "claimsight" {
  name = "claimsight"
}

output "bucket" {
  value = aws_s3_bucket.docs.bucket
}

output "cluster" {
  value = aws_ecs_cluster.claimsight.name
}
