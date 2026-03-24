# Deploying ApplyBot

GCP Cloud Run + Cloud SQL PostgreSQL, managed with Terraform.

## Prerequisites

- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud`)
- [Terraform](https://developer.hashicorp.com/terraform/install) (>= 1.5)
- [Docker](https://docs.docker.com/get-docker/)

## 1. GCP Project Setup

```bash
# Create a new project (or use an existing one)
gcloud projects create applybot-prod --name="ApplyBot"
gcloud config set project applybot-prod

# Enable billing (required for Cloud SQL, Cloud Run)
# Visit: https://console.cloud.google.com/billing
# Link your project to a billing account

# Authenticate
gcloud auth login
gcloud auth application-default login
```

## 2. Configure Terraform Variables

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your actual values:

```hcl
project_id        = "applybot-prod"
region            = "us-central1"
db_password       = "your-strong-db-password"
anthropic_api_key = "sk-ant-..."
serpapi_key        = "your-serpapi-key"
image_tag         = "v1"
```

## 3. Deploy Infrastructure

```bash
cd infra

terraform init
terraform plan        # Review what will be created
terraform apply       # Confirm with 'yes'
```

This creates:
- Cloud SQL PostgreSQL 15 instance (`db-f1-micro`)
- Artifact Registry repository
- Secret Manager secrets (API keys, DB password)
- Cloud Run service (scales 0–1)
- IAM bindings (Cloud Run → Cloud SQL, Secrets)

Note the outputs — you'll need the `artifact_registry` URL:

```bash
terraform output artifact_registry
# → us-central1-docker.pkg.dev/applybot-prod/applybot
```

## 4. Build and Push Docker Image

```bash
# From the project root directory
cd ..

# Configure Docker to authenticate with Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build the image
docker build -t applybot .

# Tag for Artifact Registry (use the registry URL from terraform output)
REGISTRY=$(cd infra && terraform output -raw artifact_registry)
docker tag applybot ${REGISTRY}/applybot:v1

# Push
docker push ${REGISTRY}/applybot:v1
```

## 5. Deploy to Cloud Run

After pushing the image, Terraform can deploy it (if the image tag matches `var.image_tag`):

```bash
cd infra
terraform apply   # Will update Cloud Run to use the pushed image
```

Or if the image tag was already set correctly during `terraform apply`, Cloud Run will pull it on next revision.

## 6. Verify

```bash
# Get the dashboard URL
cd infra && terraform output dashboard_url

# Check health endpoint
curl $(terraform output -raw dashboard_url)/healthz
# → ok

# Open in browser
open $(terraform output -raw dashboard_url)
```

## 7. Deploying Updates

```bash
# Build new image
docker build -t applybot .

# Tag with new version
REGISTRY=$(cd infra && terraform output -raw artifact_registry)
docker tag applybot ${REGISTRY}/applybot:v2
docker push ${REGISTRY}/applybot:v2

# Update Terraform variable and apply
cd infra
# Update image_tag in terraform.tfvars to "v2"
terraform apply
```

## 8. Local Development (Docker)

To test the Docker build locally before deploying:

```bash
# Build
docker build -t applybot .

# Run with local SQLite (default)
docker run -p 8000:8000 applybot

# Run with a Postgres connection
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+psycopg://user:pass@host/applybot" \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  applybot
```

## 9. Tear Down

```bash
cd infra

# Cloud SQL has deletion_protection = true by default.
# To destroy, first disable it:
#   Edit cloud_sql.tf: deletion_protection = false
#   terraform apply

terraform destroy
```

## Cost Estimate

At minimal usage (scale-to-zero):
- **Cloud Run**: Free tier covers up to 2M requests/month
- **Cloud SQL** (`db-f1-micro`): ~$7–10/month (always on)
- **Artifact Registry**: ~$0.10/GB/month storage
- **Secret Manager**: Free tier covers 10,000 access operations/month

Total: **~$8–12/month** at low usage, dominated by Cloud SQL.
