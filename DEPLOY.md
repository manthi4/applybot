# Deploying ApplyBot

GCP Cloud Run + Firestore, managed with Terraform.

## Prerequisites

- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud`)
- [Terraform](https://developer.hashicorp.com/terraform/install) (>= 1.5)
- [Docker](https://docs.docker.com/get-docker/)

## 1. GCP Project Setup

```bash
# Create a new project (or use an existing one)
gcloud projects create applybot-prod --name="ApplyBot"
gcloud config set project applybot-prod

# Enable billing (required for Cloud Run, Firestore)
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
anthropic_api_key = "sk-ant-..."
serpapi_key        = ""
image_tag         = "latest"
```

## 3. Deploy Infrastructure

```bash
cd infra

terraform init
terraform plan        # Review what will be created
terraform apply       # Confirm with 'yes'
```

This creates:
- Firestore database (FIRESTORE_NATIVE mode) with composite indexes
- Artifact Registry repository
- Secret Manager secrets (API keys)
- Cloud Run service (scales 0–1)
- Cloud Functions + Cloud Scheduler for daily discovery
- IAM bindings (Cloud Run → Firestore, Secrets)

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

# Run with GCP credentials (Firestore uses ADC)
docker run -p 8000:8000 \
  -e GCP_PROJECT_ID="your-project-id" \
  -e GOOGLE_APPLICATION_CREDENTIALS="/app/credentials.json" \
  -v /path/to/credentials.json:/app/credentials.json:ro \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  applybot
```

## 9. CI/CD with GitHub Actions

Two workflows automate Terraform and Docker deployments.

### Prerequisites

1. **Create a GCS bucket for Terraform remote state:**

   ```bash
   gsutil mb -l us-central1 gs://applybot-tfstate
   gsutil versioning set on gs://applybot-tfstate
   ```

2. **Create a dedicated CI service account** with minimal permissions:

   ```bash
   PROJECT_ID="your-gcp-project-id"
   gcloud iam service-accounts create applybot-ci --display-name="ApplyBot CI"
   for role in \
     roles/artifactregistry.writer \
     roles/run.admin \
     roles/datastore.user \
     roles/secretmanager.admin \
     roles/storage.admin \
     roles/cloudfunctions.admin \
     roles/iam.serviceAccountUser; do
     gcloud projects add-iam-policy-binding "$PROJECT_ID" \
       --member="serviceAccount:applybot-ci@${PROJECT_ID}.iam.gserviceaccount.com" \
       --role="$role"
   done
   gcloud iam service-accounts keys create ci-key.json \
     --iam-account="applybot-ci@${PROJECT_ID}.iam.gserviceaccount.com"
   ```

3. **Configure GitHub Secrets** in your repo settings:

   | Secret | Description |
   |--------|-------------|
   | `GCP_SA_KEY` | Contents of `ci-key.json` |
   | `GCP_PROJECT_ID` | GCP project ID (e.g. `applybot-prod`) |
   | `TF_VAR_ANTHROPIC_API_KEY` | Anthropic API key |
   | `TF_VAR_SERPAPI_KEY` | SerpAPI key (optional) |

4. **Configure GitHub Variables** (optional overrides):

   | Variable | Default | Description |
   |----------|---------|-------------|
   | `GCP_REGION` | `us-central1` | GCP region |
   | `IMAGE_TAG` | `latest` | Default image tag for Terraform |

### Usage

```bash
# Terraform — manual triggers
gh workflow run terraform.yml                    # plan + apply
gh workflow run terraform.yml -f action=plan     # plan only

# Docker — manual triggers
gh workflow run docker.yml                       # tag = short SHA
gh workflow run docker.yml -f image_tag=v2       # custom tag

# Commit-message triggers (push to main)
git commit -m "update infra --tf-apply"          # runs terraform apply
git commit -m "fix bug --docker"                 # builds & pushes Docker image
```

## 10. Tear Down

```bash
cd infra

# Firestore database has deletion_protection = true by default.
# To destroy, first set delete_protection_state = "DELETE_PROTECTION_DISABLED"
# in firestore.tf, run terraform apply, then:

terraform destroy
```

## Cost Estimate

At minimal usage (scale-to-zero):
- **Cloud Run**: Free tier covers up to 2M requests/month
- **Firestore**: Free tier covers 1 GiB storage + 50K reads + 20K writes per day
- **Artifact Registry**: ~$0.10/GB/month storage
- **Secret Manager**: Free tier covers 10,000 access operations/month

Total: **~$0–2/month** at low usage. Firestore free tier is generous for this use case.
