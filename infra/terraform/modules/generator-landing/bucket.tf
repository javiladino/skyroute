data "aws_caller_identity" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = "eu-west-3"
  name_prefix = "skyroute-${var.env}"
  bucket_name = "${local.name_prefix}-data-${local.account_id}"
}

resource "aws_s3_bucket" "data" {
  bucket        = local.bucket_name
  force_destroy = false

  #checkov:skip=CKV_AWS_21:Sin versioning por Ruling Bucket; lifecycle de 30 días y datos regenerables por el generador determinista.
  #checkov:skip=CKV_AWS_145:SSE-S3 por Ruling Bucket; KMS vetado (foundations/current/plan.md:237).
  #checkov:skip=CKV_AWS_144:Convention Region, todo en eu-west-3; sin réplica cross-region.
  #checkov:skip=CKV_AWS_18:Sin access logging, riesgo aceptado en proposal (como el bucket de state); datos sintéticos con lifecycle de 30 días
  #checkov:skip=CKV2_AWS_62:Sin notificaciones de eventos: no hay consumidor de landing/ en esta fase.
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_policy" "data" {
  bucket = aws_s3_bucket.data.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.data.arn,
          "${aws_s3_bucket.data.arn}/*",
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.data]
}

# Convention Medallion layers: landing/ es crudo y dura 30 días.
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "expire-landing-30d"
    status = "Enabled"

    filter {
      prefix = "landing/"
    }

    expiration {
      days = 30
    }
  }

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
