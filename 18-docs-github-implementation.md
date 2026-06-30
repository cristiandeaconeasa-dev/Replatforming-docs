# 18 — Docs GitHub Implementation Guide

> **Scope:** A concrete, step-by-step implementation guide for the docs-as-code platform described in [doc 16](16-docs-github-strategy.md). Covers: GCP infrastructure setup, hub repo creation, CI/CD pipeline, per-repo docs convention, adopting existing repos, creating new repos with docs, maintenance procedures, and access management. **For Confluence content migration, see [doc 16 §6](16-docs-github-strategy.md#6-migration-plan). This guide covers platform infrastructure only.**
>
> **Audience:** Platform engineer implementing the docs platform. Every command is copy-paste ready. Every YAML file is complete.
>
> **Drafted:** 2026-06-30 — validated against Pricer's existing GCP infrastructure (`platform-dev-p01`, `europe-north1`, Cloud Run, IAP) and the `evo-dtoflow-protos` docs model.

---

## Table of Contents

1. [Infrastructure Setup](#1-infrastructure-setup) — GCP project, Cloud Run, IAP, DNS
2. [Hub Repo: `evo-docs`](#2-hub-repo-evo-docs) — Complete file-by-file setup
3. [Creating a New Repo with Docs](#3-creating-a-new-repo-with-docs) — Template + conventions
4. [Adopting an Existing Repo](#4-adopting-an-existing-repo) — Step-by-step guide
5. [Adding & Removing Docs from the Hub](#5-adding--removing-docs-from-the-hub)
6. [CI/CD Pipeline Details](#6-cicd-pipeline-details)
7. [Maintenance Procedures](#7-maintenance-procedures)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Infrastructure Setup

### 1.1 Prerequisites

- GCP project with billing enabled (`platform-dev-p01` recommended — same as the rest of the platform)
- `gcloud` CLI authenticated
- GitHub repo `PricerAB/evo-docs` (already exists, currently empty)
- Docker installed locally (for testing the Dockerfile)

### 1.2 Enable Required GCP APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iap.googleapis.com \
  cloudbuild.googleapis.com \
  --project=platform-dev-p01
```

### 1.3 Create Artifact Registry Repository

```bash
gcloud artifacts repositories create evo-docs \
  --repository-format=docker \
  --location=europe-north1 \
  --project=platform-dev-p01
```

### 1.4 Set Up Workload Identity Federation (for GitHub Actions → GCP)

This lets GitHub Actions deploy to Cloud Run without storing long-lived service account keys.

```bash
# Create a service account for the CI pipeline
gcloud iam service-accounts create evo-docs-ci \
  --display-name="evo-docs CI/CD" \
  --project=platform-dev-p01

# Grant required roles
gcloud projects add-iam-policy-binding platform-dev-p01 \
  --member="serviceAccount:evo-docs-ci@platform-dev-p01.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding platform-dev-p01 \
  --member="serviceAccount:evo-docs-ci@platform-dev-p01.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding platform-dev-p01 \
  --member="serviceAccount:evo-docs-ci@platform-dev-p01.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Create Workload Identity Pool
gcloud iam workload-identity-pools create "github-pool" \
  --project="platform-dev-p01" \
  --location="global" \
  --display-name="GitHub Actions Pool"

# Get the pool ID
POOL_ID=$(gcloud iam workload-identity-pools describe "github-pool" \
  --project="platform-dev-p01" \
  --location="global" \
  --format="value(name)")

# Create a provider for the evo-docs repo
gcloud iam workload-identity-pools providers create-oidc "evo-docs-provider" \
  --project="platform-dev-p01" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="evo-docs GitHub Actions" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Allow the evo-docs repo to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding \
  "evo-docs-ci@platform-dev-p01.iam.gserviceaccount.com" \
  --project="platform-dev-p01" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/PricerAB/evo-docs"
```

**Note the WIF provider name** — you'll add it as `WIF_PROVIDER` secret in GitHub. It looks like:
`projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/evo-docs-provider`

### 1.5 Deploy Cloud Run Service (Initial Empty Deploy)

First, we need an initial deploy so IAP can be configured. Use a placeholder container:

```bash
# Create a minimal placeholder
mkdir -p /tmp/evo-docs-placeholder
cat > /tmp/evo-docs-placeholder/Dockerfile << 'EOF'
FROM nginx:alpine
RUN echo '<html><body><h1>Pricer Docs — Coming Soon</h1></body></html>' \
  > /usr/share/nginx/html/index.html
EOF

# Build and push
gcloud builds submit /tmp/evo-docs-placeholder \
  --tag=europe-north1-docker.pkg.dev/platform-dev-p01/evo-docs/placeholder \
  --project=platform-dev-p01

# Deploy
gcloud run deploy evo-docs \
  --image=europe-north1-docker.pkg.dev/platform-dev-p01/evo-docs/placeholder \
  --region=europe-north1 \
  --platform=managed \
  --allow-unauthenticated \
  --project=platform-dev-p01
```

### 1.6 Configure IAP (Identity-Aware Proxy)

IAP for Cloud Run requires a **Serverless NEG + external load balancer**. The `gcloud iap web` commands target App Engine/Compute Engine, not Cloud Run directly. Here's the correct approach:

**Step 1: Configure the OAuth consent screen** (one-time per project):
- Go to: https://console.cloud.google.com/apis/credentials/consent
- Set to **"Internal"** (only `@pricer.com` accounts)

**Step 2: Remove unauthenticated access from Cloud Run:**

```bash
gcloud run services update evo-docs \
  --region=europe-north1 \
  --project=platform-dev-p01 \
  --no-allow-unauthenticated
```

**Step 3: Grant IAP service account permission to invoke Cloud Run:**

```bash
# Get the project number
PROJECT_NUMBER=$(gcloud projects describe platform-dev-p01 --format='value(projectNumber)')

# Grant the IAP service agent invoker permission
gcloud run services add-iam-policy-binding evo-docs \
  --region=europe-north1 \
  --project=platform-dev-p01 \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

**Step 4: Set up Serverless NEG + Load Balancer with IAP** (when ready for `docs.pricer.com` — see §1.7):

For the initial setup, use the Cloud Console: **Cloud Run → evo-docs → Security → "Use Identity-Aware Proxy"** and enable it. Then add the `IAP-secured Web App User` role to `domain:pricer.com`.

For programmatic setup via gcloud (after the load balancer is created):

```bash
# Grant access to all @pricer.com users
gcloud iap web add-iam-policy-binding \
  --resource-type=backend-services \
  --member="domain:pricer.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --project=platform-dev-p01

# Or grant access to specific groups
gcloud iap web add-iam-policy-binding \
  --member="group:platform-team@pricer.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --project=platform-dev-p01
```

> **Phase 1 simplification:** Use the Cloud Console for IAP setup. The Serverless NEG + load balancer approach is documented in §1.7 (DNS). Until then, the auto-generated `*.a.run.app` URL with `--no-allow-unauthenticated` provides IAP protection without the load balancer.

### 1.7 DNS Configuration (when ready for `docs.pricer.com`)

```bash
# Create a global external load balancer with IAP
# 1. Reserve a global static IP
gcloud compute addresses create docs-pricer-ip --global

# 2. Create a managed SSL certificate
gcloud compute ssl-certificates create docs-pricer-cert \
  --domains=docs.pricer.com --global

# 3. Map the IP to Cloud Run via Serverless NEG
gcloud compute network-endpoint-groups create docs-pricer-neg \
  --region=europe-north1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=evo-docs

# 4. Create backend service, URL map, target proxy, forwarding rule
# (Full load balancer setup is ~6 more commands — see GCP docs:
#  https://cloud.google.com/load-balancing/docs/https/setting-up-https-serverless)

# 5. Add CNAME record in Pricer's DNS:
#    docs.pricer.com → <static-ip-from-step-1>
```

> **For Phase 1, skip DNS** — use the auto-generated Cloud Run URL (`evo-docs-xxxxx-oc.a.run.app`). DNS + load balancer can wait until the site has content worth sharing.

---

## 2. Hub Repo: `evo-docs`

This is the complete file-by-file setup for the central documentation hub.

### 2.1 Repository Structure

```
evo-docs/
├── mkdocs.yml
├── Dockerfile
├── nginx.conf
├── requirements.txt
├── docs/
│   └── index.md
├── scripts/
│   ├── sync-repos.sh          # Clones all doc-source repos
│   └── generate-nav.py        # Auto-generates mkdocs nav from cloned repos
├── .github/
│   └── workflows/
│       └── build-and-deploy.yml
├── .gitignore
└── README.md
```

### 2.2 `mkdocs.yml`

```yaml
site_name: "Pricer Documentation"
site_description: "Pricer AB platform documentation — architecture, services, APIs, and onboarding"
repo_url: https://github.com/PricerAB/evo-docs
edit_uri: ""  # Disable edit links (content comes from other repos)

theme:
  name: material
  logo: _assets/pricer-logo.svg  # Add logo later
  features:
    - navigation.sections
    - navigation.indexes
    - navigation.tracking
    - navigation.expand
    - search.suggest
    - search.highlight
    - search.share
    - content.code.copy
    - content.code.annotate
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode

plugins:
  - search:
      separator: '[\s\-,:!=\[\]()"/]+'
      lang:
        - en

markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - admonition
  - pymdownx.details
  - tables
  - toc:
      permalink: true

# The nav section is GENERATED by scripts/generate-nav.py at build time.
# Keep a minimal static nav for the landing page:
nav:
  - Home: docs/index.md
  # REST OF NAV IS AUTO-GENERATED FROM _sources/
```

### 2.3 `docs/index.md` (Landing Page)

```markdown
# Pricer Documentation

Welcome to the Pricer AB platform documentation.

## Platform

<div class="grid cards" markdown>

-   :material-database:{ .lg .middle } **DTOflow Platform**

    ---

    The cloud data backbone — Spanner, Pub/Sub, gRPC, CQS, and DTO conventions.

    [:octicons-arrow-right-24: Platform overview](platform/index.md)

-   :material-package-variant-closed:{ .lg .middle } **Cloud Run Services**

    ---

    21+ services running on Cloud Run — item registry, link registry, rendering, transmission, and more.

    [:octicons-arrow-right-24: Services](services/index.md)

-   :material-sync:{ .lg .middle } **Replatforming**

    ---

    Migrating data, APIs, and rendering from per-store R3Server to the shared DTOflow cloud.

    [:octicons-arrow-right-24: Replatforming guide](replatforming/index.md)

-   :material-book-open-variant:{ .lg .middle } **Architecture Decision Records**

    ---

    ADRs documenting key architectural decisions.

    [:octicons-arrow-right-24: ADRs](decisions/index.md)

</div>

## Quick Links

- [DTOflow Architecture](platform/architecture.md)
- [Core Data Flows](flows/item-update.md)
- [Phase 1 Migration Plan](replatforming/17-phase-1-plan.md)
- [Tenant Migration Guide](replatforming/14-tenant-migration.md)

## Repositories

Documentation is sourced from multiple PricerAB repositories. See the [repo index](repo-index.md) for the full list.

---

*Built from source at [:material-github: PricerAB/evo-docs](https://github.com/PricerAB/evo-docs)*
```

### 2.4 `requirements.txt`

```
mkdocs-material>=9.5.0
pymdown-extensions>=10.0
pyyaml>=6.0
```

### 2.5 `scripts/sync-repos.sh`

This script clones all doc-source repos into `_sources/`. It's the core of the aggregation approach.

```bash
#!/bin/bash
# sync-repos.sh — Clone all doc-source repos into _sources/
# Run from the evo-docs repo root.
set -euo pipefail

SOURCES_DIR="_sources"
REPO_LIST_FILE="repos.txt"
GITHUB_ORG="PricerAB"

# Use GITHUB_TOKEN if available (CI), otherwise use gh CLI auth
if [ -n "${GITHUB_TOKEN:-}" ]; then
    CLONE_PREFIX="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_ORG}"
else
    CLONE_PREFIX="https://github.com/${GITHUB_ORG}"
fi

echo "=== Syncing doc-source repos ==="

# Clean previous sources but preserve .gitkeep
rm -rf "${SOURCES_DIR:?}"/*
touch "${SOURCES_DIR}/.gitkeep"

if [ ! -f "$REPO_LIST_FILE" ]; then
    echo "ERROR: repos.txt not found. Create it with one repo name per line."
    exit 1
fi

FAILED=0
while IFS= read -r repo; do
    # Skip comments and empty lines
    [[ "$repo" =~ ^#.*$ ]] && continue
    [[ -z "$repo" ]] && continue

    echo "  Cloning ${repo}..."
    if git clone --depth 1 --filter=blob:none \
        "${CLONE_PREFIX}/${repo}.git" \
        "${SOURCES_DIR}/${repo}" 2>&1 | tail -1; then
        echo "    ✅ ${repo}"
    else
        echo "    ❌ ${repo} — clone failed"
        FAILED=1
    fi
done < "$REPO_LIST_FILE"

if [ $FAILED -eq 1 ]; then
    echo "WARNING: Some repos failed to clone. Check repos.txt and access tokens."
    echo "The build will continue with available repos."
fi

echo "=== Generating nav from cloned repos ==="
python3 scripts/generate-nav.py

echo "=== Sync complete ==="
find "${SOURCES_DIR}" -maxdepth 1 -type d | tail -n +2 | while read -r d; do
    echo "  $(basename "$d") ($(find "$d" -name '*.md' | wc -l | tr -d ' ') md files)"
done
```

### 2.6 `scripts/generate-nav.py`

Auto-generates the `nav:` section of `mkdocs.yml` from cloned repos.

```python
#!/usr/bin/env python3
"""generate-nav.py — Scan _sources/ for docs and generate mkdocs nav structure.

For each cloned repo in _sources/:
1. If the repo has docs/mkdocs.yml, extract its nav structure.
2. Otherwise, scan docs/ for .md files and create a flat nav.
3. Merge all navs into the hub's mkdocs.yml.
"""

import os
import yaml
from pathlib import Path

SOURCES_DIR = "_sources"
MKDOCS_YML = "mkdocs.yml"
NAV_MARKER = "# REST OF NAV IS AUTO-GENERATED FROM _sources/"

# Category mapping — which top-level section each repo belongs to
# Add repos to the appropriate category as they're onboarded.
CATEGORY_MAP = {
    # Platform Architecture
    "evo-dtoflow-protos": {
        "section": "Platform Architecture",
        "label": "DTOflow & DTOs",
    },
    "evo-docs": {"section": None},  # hub repo itself — skip

    # Services
    "platform-item-registry-api": {
        "section": "Services",
        "label": "Item Registry API",
    },
    "platform-link-service": {
        "section": "Services",
        "label": "Link Service",
    },
    "platform-evaluation-engine": {
        "section": "Services",
        "label": "Studio Link Evaluator",
    },
    "platform-image-render-service": {
        "section": "Services",
        "label": "Studio Renderer",
    },
    "platform-ecc-link-projector": {
        "section": "Services",
        "label": "ECC Link Projector",
    },
    "platform-migration-helper": {
        "section": "Services",
        "label": "Migration Helper",
    },
    "platform-scenario-service": {
        "section": "Services",
        "label": "Scenario Service",
    },
    "platform-dtoflow-server-spanner": {
        "section": "Services",
        "label": "DTOflow Spanner Server",
    },
    "platform-customer-data": {
        "section": "Services",
        "label": "Customer Data",
    },

    # Replatforming
    "replatforming-onboarding": {
        "section": "Replatforming",
        "label": "Onboarding Guide",
    },

    # Consumer Apps
    "chain-management-centralization": {
        "section": "Consumer Apps",
        "label": "Central-Manager",
    },
    "plaza-mobile-ui-backend": {
        "section": "Consumer Apps",
        "label": "Plaza Mobile BFF",
    },
    "plaza-mobile-ui-frontend": {
        "section": "Consumer Apps",
        "label": "Plaza Mobile App",
    },

    # Infrastructure
    "cloud-infra-terragrunt-terraform": {
        "section": "Infrastructure",
        "label": "Infrastructure (IaC)",
    },
    "platform-gcp-resources": {
        "section": "Infrastructure",
        "label": "GCP Resources",
    },
}


def scan_repo_docs(repo_name: str, repo_path: Path) -> list[dict] | None:
    """Scan a repo's docs/ folder and return nav entries."""
    docs_path = repo_path / "docs"
    if not docs_path.is_dir():
        return None

    # Check for per-repo mkdocs.yml which may have a nav section
    per_repo_mkdocs = repo_path / "mkdocs.yml"
    if per_repo_mkdocs.exists():
        try:
            with open(per_repo_mkdocs) as f:
                config = yaml.safe_load(f)
            if config and "nav" in config:
                return rewrite_paths(repo_name, config["nav"])
        except Exception:
            pass

    # Fallback: flat list of .md files
    md_files = sorted(docs_path.rglob("*.md"))
    if not md_files:
        return None

    nav = []
    for f in md_files:
        rel = f.relative_to(docs_path)
        src_path = f"_sources/{repo_name}/docs/{rel}"
        title = f.stem.replace("-", " ").replace("_", " ").title()
        if rel == Path("index.md"):
            nav.insert(0, {title: src_path})
        else:
            nav.append({title: src_path})
    return nav


def rewrite_paths(repo_name: str, nav: list) -> list:
    """Rewrite paths in a nav structure to point to _sources/."""
    result = []
    for item in nav:
        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, str):
                    if not value.startswith("http") and not value.startswith("_"):
                        # If path references a file outside docs/ (e.g., ../README.md),
                        # rewrite relative to the repo root, not docs/
                        if value.startswith("../") or not value.startswith("docs/"):
                            value = f"_sources/{repo_name}/{value.lstrip('./')}"
                        else:
                            value = f"_sources/{repo_name}/{value}"
                        # Remove double slashes if any
                        value = value.replace("//", "/")
                    result.append({key: value})
                elif isinstance(value, list):
                    result.append({key: rewrite_paths(repo_name, value)})
                else:
                    result.append(item)
        elif isinstance(item, str):
            result.append(item)
        else:
            result.append(item)
    return result


def main():
    sources = Path(SOURCES_DIR)
    if not sources.is_dir():
        print("No _sources/ directory — skipping nav generation")
        return

    # Group nav entries by section
    sections: dict[str, list] = {}

    for repo_dir in sorted(sources.iterdir()):
        if not repo_dir.is_dir() or repo_dir.name.startswith("."):
            continue

        repo_name = repo_dir.name
        nav_entries = scan_repo_docs(repo_name, repo_dir)
        if not nav_entries:
            continue

        category = CATEGORY_MAP.get(repo_name, {})
        section = category.get("section", "Other")
        label = category.get("label", repo_name.replace("-", " ").title())

        if section is None:  # Skip (e.g., hub repo itself)
            continue

        if section not in sections:
            sections[section] = []

        # Add as a sub-section with the repo's label
        sections[section].append({label: nav_entries})

    # Generate nav lines
    nav_lines = []
    for section in ["Platform Architecture", "Services", "Replatforming",
                     "Consumer Apps", "Infrastructure", "Other"]:
        if section in sections:
            nav_lines.append(f"  - {section}:")
            for entry in sections[section]:
                for label, items in entry.items():
                    nav_lines.append(f"      - {label}:")
                    for nav_item in items:
                        nav_lines.append(f"        - {yaml.dump(nav_item, default_flow_style=True).strip()}")

    # Update mkdocs.yml
    with open(MKDOCS_YML, "r") as f:
        content = f.read()

    if NAV_MARKER not in content:
        print(f"ERROR: Nav marker not found in {MKDOCS_YML}")
        return

    before = content.split(NAV_MARKER)[0]
    new_nav = "\n".join(nav_lines)
    new_content = f"{before}{NAV_MARKER}\n{new_nav}\n"

    with open(MKDOCS_YML, "w") as f:
        f.write(new_content)

    print(f"Generated nav with {sum(len(v) for v in sections.values())} repos "
          f"across {len(sections)} sections")


if __name__ == "__main__":
    main()
```

### 2.7 `repos.txt` (Doc-Source Registry)

One repo per line. This is the canonical list of repos that contribute docs. Add/remove repos here to control what appears on the site.

```
# Pricer Documentation Sources
# One repo per line. Lines starting with # are ignored.
# The sync script clones each repo into _sources/<name>/.

# Platform Core
evo-dtoflow-protos

# Cloud Run Services
platform-item-registry-api
platform-link-service
platform-evaluation-engine
platform-image-render-service
platform-ecc-link-projector
platform-migration-helper
platform-scenario-service
platform-dtoflow-server-spanner
platform-customer-data

# Replatforming
replatforming-onboarding

# Consumer Apps
chain-management-centralization
plaza-mobile-ui-backend
plaza-mobile-ui-frontend

# Infrastructure
cloud-infra-terragrunt-terraform
platform-gcp-resources
```

### 2.8 `Dockerfile`

> **Important:** The Dockerfile expects `_sources/` to already exist (populated by `scripts/sync-repos.sh`) before `docker build`. In CI, `sync-repos.sh` runs before `docker build`. For local Docker builds, run `sync-repos.sh` first.

```dockerfile
# Stage 1: Build the mkdocs site
FROM python:3.12-alpine AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# _sources/ must exist (from sync-repos.sh run before docker build)
COPY . .
RUN mkdocs build --strict

# Stage 2: Serve with nginx
FROM nginx:alpine

# Custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy the built site
COPY --from=builder /app/site /usr/share/nginx/html

# Health check
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://localhost:8080/ || exit 1

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
```

### 2.9 `nginx.conf`

```nginx
worker_processes auto;
error_log /dev/stderr warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    sendfile on;
    keepalive_timeout 65;
    gzip on;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml application/xml+rss text/javascript
               image/svg+xml;

    server {
        listen 8080;
        server_name _;
        root /usr/share/nginx/html;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        location / {
            index index.html;
            try_files $uri $uri.html $uri/ =404;
        }

        # Cache static assets aggressively
        location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg|woff2?|ttf|eot)$ {
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

### 2.10 `.github/workflows/build-and-deploy.yml`

```yaml
name: Build & Deploy Docs

on:
  push:
    branches: [main]
    paths:
      - 'repos.txt'
      - 'mkdocs.yml'
      - 'docs/**'
      - 'scripts/**'
      - '.github/workflows/build-and-deploy.yml'
  schedule:
    - cron: '0 6 * * *'   # Daily at 6:00 UTC — catches changes in source repos
  workflow_dispatch:        # Manual trigger from GitHub UI

env:
  PROJECT_ID: platform-dev-p01
  REGION: europe-north1
  SERVICE_NAME: evo-docs

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    env:
      REPO: europe-north1-docker.pkg.dev/platform-dev-p01/evo-docs/evo-docs

    steps:
      - name: Checkout hub repo
        uses: actions/checkout@v4

      - name: Generate GitHub App token (for cross-repo clone access)
        id: app-token
        uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ secrets.DOCS_APP_ID }}
          private-key: ${{ secrets.DOCS_APP_PRIVATE_KEY }}

      - name: Sync source repos
        run: |
          chmod +x scripts/sync-repos.sh
          ./scripts/sync-repos.sh
        env:
          GITHUB_TOKEN: ${{ steps.app-token.outputs.token }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Build mkdocs site
        run: mkdocs build --strict

      - name: Check for broken links
        if: always()
        run: |
          # Check internal links are valid
          find site -name "*.html" | head -1
          echo "Link checking complete (add lychee or markdown-link-check for full validation)"

      - name: Auth to GCP
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.GCP_SA }}

      - name: Configure Docker
        run: gcloud auth configure-docker europe-north1-docker.pkg.dev

      - name: Build and push Docker image
        run: |
          IMAGE_TAG="${REPO}:${GITHUB_SHA::7}"
          docker build -t "$IMAGE_TAG" .
          docker push "$IMAGE_TAG"

      - name: Deploy to Cloud Run
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: ${{ env.SERVICE_NAME }}
          region: ${{ env.REGION }}
          image: "${REPO}:${GITHUB_SHA::7}"

      - name: Show deployed URL
        run: |
          gcloud run services describe $SERVICE_NAME \
            --region=$REGION \
            --format='value(status.url)'
```

### 2.11 `.gitignore`

```
_sources/
site/
__pycache__/
*.pyc
.DS_Store
```

### 2.12 GitHub Secrets to Configure

| Secret | Value | Where to Get It |
|--------|-------|----------------|
| `WIF_PROVIDER` | Workload Identity Federation provider string | Output of §1.4 — `projects/.../providers/evo-docs-provider` |
| `GCP_SA` | `evo-docs-ci@platform-dev-p01.iam.gserviceaccount.com` | Created in §1.4 |
| `DOCS_APP_ID` | GitHub App ID | Create a GitHub App (see §2.13) |
| `DOCS_APP_PRIVATE_KEY` | GitHub App private key | From the GitHub App settings |

### 2.13 GitHub App for Cross-Repo Access

The CI pipeline needs read access to all doc-source repos. A GitHub App is the recommended approach.

> **Prerequisite:** Creating a GitHub App in the PricerAB organization requires **organization owner** permissions. If you don't have owner access, coordinate with the PricerAB GitHub admin.

1. **Create a GitHub App:**
   - Go to `https://github.com/organizations/PricerAB/settings/apps/new`
   - Name: `Pricer Docs Aggregator`
   - Homepage URL: `https://github.com/PricerAB/evo-docs`
   - Uncheck "Active" under Webhook (no webhook needed)
   - Permissions: **Repository → Contents → Read-only**
   - Where can this app be installed? **Only on this account**

2. **Generate a private key** and download it.

3. **Install the app** on the PricerAB organization:
   - Go to `https://github.com/organizations/PricerAB/settings/installations`
   - Choose "Install" next to the app
   - Select **All repositories** (or select specific doc-source repos)

4. **Add secrets to evo-docs repo:**
   - `DOCS_APP_ID` → App ID (from app settings)
   - `DOCS_APP_PRIVATE_KEY` → The full private key content

---

## 3. Creating a New Repo with Docs

When creating a brand-new PricerAB repo, include docs from day one.

### 3.1 Step-by-Step

#### Step 1: Create the repo with the standard structure

```
my-new-service/
├── docs/
│   └── index.md
├── mkdocs.yml
├── README.md
├── src/
│   └── ... (your code)
└── ...
```

#### Step 2: Write `docs/index.md`

Use this template:

```markdown
# <Service Name>

> **Repo:** `github.com/PricerAB/<repo-name>`
> **Tech:** <Java 21 / Node.js / Python / ...>
> **Deployed:** Cloud Run `europe-north1` / GKE / ...

## What it does

<One paragraph explaining this service's role in the Pricer platform.>

## DTOs owned

| DTO | Description |
|-----|-------------|
| `example.v1` | What this DTO represents |

## DTOs subscribed to

| DTO | Why |
|-----|-----|
| `storeitemvalues.v1` | React to item price changes |

## How to run locally

```bash
./gradlew quarkusDev   # If Java
npm run dev            # If Node.js
```

## Architecture

<Optional: internal architecture diagram or description>

## Operations

<Optional: how to deploy, monitor, debug>

## Related docs

- [DTOflow Architecture](/platform/architecture/)
- [Related Service](/services/related-service/)
```

#### Step 3: Add `mkdocs.yml`

```yaml
site_name: "<Service Name>"
docs_dir: docs
theme:
  name: material

nav:
  - Home: index.md
```

#### Step 4: Add CI validation (optional but recommended)

Create `.github/workflows/docs-check.yml` in the service repo:

```yaml
name: Docs Check
on:
  pull_request:
    paths:
      - 'docs/**'
      - 'mkdocs.yml'

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install mkdocs-material
      - run: mkdocs build --strict
```

#### Step 5: Register in the hub

Add the repo name to `evo-docs/repos.txt`:

```bash
# In the evo-docs repo:
echo "my-new-service" >> repos.txt

# If the repo needs a custom category label, add it to:
# evo-docs/scripts/generate-nav.py → CATEGORY_MAP
```

Commit and push — the next daily build (or manual trigger) will include the new docs.

#### Step 6: Verify

```bash
# In evo-docs, run locally:
./scripts/sync-repos.sh
mkdocs serve
# Open http://localhost:8000 and verify the new service appears
```

---

## 4. Adopting an Existing Repo

Most PricerAB repos exist today without docs. Here's how to adopt one.

### 4.1 Quick Adoption (Minimal — 10 minutes)

For repos that just need a presence on the docs site:

```bash
cd path/to/existing-repo

# 1. Create docs folder with minimal content
mkdir -p docs
cat > docs/index.md << 'EOF'
# <Repo Name>

> **Repo:** `github.com/PricerAB/<repo-name>`
> **Tech:** <Java 21 / Node.js>

## What it does

<Brief description>

## How to run locally

```bash
./gradlew quarkusDev
```

## Related docs

- [Platform Architecture](/platform/architecture/)
EOF

# 2. Add mkdocs.yml
cat > mkdocs.yml << 'EOF'
site_name: "<Repo Name>"
docs_dir: docs
theme:
  name: material
nav:
  - Home: index.md
EOF

# 3. Commit
git add docs/ mkdocs.yml
git commit -m "docs: add minimal docs for evo-docs hub"
git push
```

### 4.2 Full Adoption (Tier 1/2 repos — 2-4 hours)

For platform services and consumer apps:

#### Step 1: Audit the repo

```bash
# What does this service do? Check:
# - README.md (current docs)
# - src/main/java/... (code structure)
# - application.yml / application.properties (configuration)
# - proto files (DTOs owned/subscribed)
# - build.gradle / package.json (dependencies, build commands)
```

#### Step 2: Create the docs structure

```
docs/
├── index.md            # Overview + quick start
├── architecture.md     # Internal design (optional)
├── api.md              # API reference (if it exposes APIs)
├── operations.md       # Deploy, monitor, debug (optional)
└── changelog.md        # Major changes (optional)
```

#### Step 3: Write `docs/index.md`

Follow the template from §3.1 Step 2, but fill in details gleaned from the audit.

**Key things to capture:**
- Which DTOs does this service own? (Check proto imports or Spanner writes)
- Which DTOs does it subscribe to? (Check CQS subscription config or application.yml)
- What's the tech stack? (build.gradle / package.json)
- How do you run it locally? (README.md or Makefile)
- What other services does it depend on?

#### Step 4: Add the per-repo CI check

Create `.github/workflows/docs-check.yml` (same as §3.1 Step 4).

#### Step 5: Register in the hub

```bash
# In evo-docs:
echo "my-existing-repo" >> repos.txt
git add repos.txt
git commit -m "docs: register my-existing-repo in doc hub"
```

#### Step 6: Add to `generate-nav.py`

```python
# In evo-docs/scripts/generate-nav.py, add to CATEGORY_MAP:
"my-existing-repo": {
    "section": "Services",         # or "Consumer Apps", "Infrastructure", etc.
    "label": "My Service Label",   # Display name on the docs site
},
```

### 4.3 Adopting `evo-dtoflow-protos` (the gold standard)

This is the reference repo. Its docs already exist on a branch — the task is finding and merging them:

```bash
# 1. Find where the docs live
git clone git@github.com:PricerAB/evo-dtoflow-protos.git
cd evo-dtoflow-protos
git branch -r | grep -i doc   # Look for documentation branches

# 2. Check each candidate branch for docs/ folder
for branch in $(git branch -r | grep -i doc | sed 's/origin\///'); do
    echo "=== $branch ==="
    git ls-tree -r --name-only "origin/$branch" | grep "^docs/" | head -5
done

# 3. Merge the correct branch to main
# (Assuming central-documentation or similar)
git checkout main
git merge origin/<docs-branch>
git push origin main
```

### 4.4 Adopting `Replatforming/onboarding/` (local docs → GitHub repo)

This folder contains 17+ comprehensive onboarding docs. It needs to become a tracked GitHub repo:

```bash
# 1. Create the repo on GitHub: PricerAB/replatforming-onboarding

# 2. Initialize locally
mkdir replatforming-onboarding
cd replatforming-onboarding
git init

# 3. Copy docs (with full path rewriting for cross-references)
cp -r /Users/cridea/Projects/AI/Replatforming/onboarding/* docs/

# 4. Add mkdocs.yml
cat > mkdocs.yml << 'EOF'
site_name: "Replatforming Onboarding"
docs_dir: docs
theme:
  name: material
  features:
    - navigation.sections
    - content.code.copy

nav:
  - Home: README.md
  - 01 Systems Architecture: 01-systems-architecture.md
  - 02 Tenant Model: 02-tenant-model.md
  - 03 Replatforming Deep Dive: 03-replatforming-deep-dive.md
  - 04 Target Architecture: 04-target-architecture.md
  - 05 Core Concepts: 05-core-concepts-deep-dive.md
  - 07 M2M Token Manager: 07-m2m-token-manager-deep-dive.md
  - 08 DTOflow Deep Dive: 08-dtoflow-deep-dive.md
  - 10 Item Pipeline: 10-item-pipeline-deep-dive.md
  - 11 Link Pipeline: 11-link-pipeline-deep-dive.md
  - 12 Rendering Pipeline: 12-rendering-pipeline-deep-dive.md
  - 13 Core Data Flows: 13-core-data-flows.md
  - 14 Tenant Migration: 14-tenant-migration.md
  - 15 Overall Status: 15-overall-status.md
  - 16 Docs GitHub Strategy: 16-docs-github-strategy.md
  - 17 Phase 1 Plan: 17-phase-1-plan.md
EOF

# 5. Rewrite cross-references
# All relative links like [doc 03](03-...) need to become mkdocs-friendly.
# Run a sed script:
find docs -name "*.md" -exec sed -i '' \
  -e 's|(03-replatforming-deep-dive.md)|(03-replatforming-deep-dive/)|g' \
  -e 's|(04-target-architecture.md)|(04-target-architecture/)|g' \
  # ... repeat for all doc references
  {} +

# 6. Push
git add -A
git commit -m "Initial onboarding docs from local Replatforming/onboarding/"
git remote add origin git@github.com:PricerAB/replatforming-onboarding.git
git push -u origin main
```

---

## 5. Adding & Removing Docs from the Hub

### 5.1 Adding a New Doc-Source Repo

1. **The repo must have `docs/` with at least `docs/index.md`** (see §3 or §4)
2. **Add the repo name to `evo-docs/repos.txt`:**

```bash
cd evo-docs
echo "new-repo-name" >> repos.txt
```

3. **Add category mapping** in `scripts/generate-nav.py`:

```python
"new-repo-name": {
    "section": "Services",      # Pick the right section
    "label": "New Service",     # Display name
},
```

4. **Verify locally:**

```bash
./scripts/sync-repos.sh
mkdocs serve
# Open http://localhost:8000 — new repo should appear in nav
```

5. **Commit and push:**

```bash
git add repos.txt scripts/generate-nav.py
git commit -m "docs: add new-repo-name to doc hub"
git push
```

The next daily build (or manual workflow trigger) will pick it up. To deploy immediately: go to GitHub → Actions → Build & Deploy Docs → Run workflow.

### 5.2 Removing a Doc-Source Repo

1. **Remove the repo from `evo-docs/repos.txt`** (delete the line or comment it out with `#`)
2. **Remove the category mapping** from `scripts/generate-nav.py` (optional — it will just be unused)
3. **Commit and push**

No other cleanup needed. The next build will simply not clone that repo.

### 5.3 Adding a Single Page to an Existing Repo

Simply add the `.md` file to the repo's `docs/` folder. The next hub build picks it up automatically (the `generate-nav.py` script scans all `.md` files).

If you want the page to appear in a specific position in the nav, update the repo's `mkdocs.yml` nav section.

### 5.4 Removing a Single Page

Delete the `.md` file from the repo's `docs/` folder. If the repo's `mkdocs.yml` has a nav that references it, update that too. No hub-side changes needed.

---

## 6. CI/CD Pipeline Details

### 6.1 Triggers

| Trigger | When | Purpose |
|---------|------|---------|
| **Push to main** | When `repos.txt`, `mkdocs.yml`, `docs/**`, or pipeline files change in `evo-docs` | Deploy hub-side changes immediately |
| **Daily schedule** | 6:00 UTC every day | Catch changes in source repos without needing webhooks |
| **Manual trigger** | On demand via GitHub Actions UI | Deploy immediately after adding a new repo |

### 6.2 What Happens During a Build

```
1. Checkout evo-docs hub repo
2. Generate GitHub App token (for cross-repo clone access)
3. Run sync-repos.sh:
   a. Clean _sources/
   b. For each repo in repos.txt:
      - git clone --depth 1 into _sources/<repo>/
   c. Run generate-nav.py:
      - Scan each _sources/<repo>/docs/ for .md files
      - Read each repo's mkdocs.yml nav if available
      - Generate the nav section in evo-docs/mkdocs.yml
4. pip install mkdocs-material + dependencies
5. mkdocs build --strict (fails on broken links or missing files)
6. Build Docker image:
   a. Stage 1: Python image → mkdocs build → site/ output
   b. Stage 2: nginx:alpine → copy site/ → serve on :8080
7. Push image to Artifact Registry
8. Deploy to Cloud Run (rolling update — zero downtime)
9. Print deployed URL
```

### 6.3 Build Time Estimate

| Step | ~Time |
|------|-------|
| Checkout + token generation | 10s |
| Clone 15 repos (--depth 1) | 30-45s |
| Generate nav | 5s |
| mkdocs build | 15-30s |
| Docker build + push | 60-90s |
| Cloud Run deploy | 30-60s |
| **Total** | **~3-4 minutes** |

### 6.4 Adding the Daily Build to Source Repos (Webhook Alternative)

If you want docs to update faster than daily, each source repo can trigger the hub build via `repository_dispatch`:

In each source repo, add `.github/workflows/trigger-docs-rebuild.yml`:

```yaml
name: Trigger Docs Rebuild
on:
  push:
    branches: [main]
    paths:
      - 'docs/**'

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger evo-docs rebuild
        uses: peter-evans/repository-dispatch@v3
        with:
          token: ${{ secrets.DOCS_TRIGGER_TOKEN }}
          repository: PricerAB/evo-docs
          event-type: rebuild-docs
```

And in `evo-docs/.github/workflows/build-and-deploy.yml`, add:

```yaml
on:
  repository_dispatch:
    types: [rebuild-docs]
  # ... existing triggers
```

---

## 7. Maintenance Procedures

### 7.1 Daily Maintenance (Automated)

The daily CI build handles:
- **Freshness:** Re-clones all source repos each build — docs are always up to date
- **Broken links:** `mkdocs build --strict` fails the build if any link is broken
- **Missing repos:** `sync-repos.sh` warns but continues if a repo can't be cloned (repo may be deleted or renamed)

If the daily build fails, GitHub Actions sends a notification. Check the logs for the failing step.

### 7.2 Weekly Maintenance (Manual — 5 minutes)

```bash
cd evo-docs

# 1. Check for new repos in the org that might need docs
gh repo list PricerAB --limit 100 --json name --jq '.[].name' > /tmp/all-repos.txt
grep -v -f repos.txt /tmp/all-repos.txt | grep -v "^evo-docs$" > /tmp/missing-from-docs.txt
echo "Repos not in docs hub:"
cat /tmp/missing-from-docs.txt

# 2. Check for renamed/deleted repos (listed in repos.txt but not on GitHub)
while IFS= read -r repo; do
    [[ "$repo" =~ ^#.*$ ]] && continue
    [[ -z "$repo" ]] && continue
    if ! gh repo view "PricerAB/$repo" --json name &>/dev/null; then
        echo "STALE: $repo no longer exists — may have been renamed or deleted"
        echo "  Search for it: gh search repos --owner=PricerAB $repo"
    fi
done < repos.txt

# 3. Verify the deployed site is healthy
curl -sI "https://evo-docs-xxxxx-oc.a.run.app" | head -1
# Should return: HTTP/2 200
```

### 7.3 Monthly Maintenance (Manual — 15 minutes)

```bash
# 1. Check for mkdocs-material updates
pip install --upgrade mkdocs-material
mkdocs build --strict  # Verify nothing breaks with the new version

# 2. Audit cross-repo links
# Install lychee: brew install lychee
lychee --base docs.pricer.com site/ 2>&1 | tee link-audit.txt
# Review broken links and fix in source repos

# 3. Review IAP access list
gcloud iap web get-iam-policy \
  --resource-type=backend-services \
  --project=platform-dev-p01
# Verify only @pricer.com accounts have access

# 4. Rotate GitHub App private key (every 6 months or per security policy)
# Generate new key in GitHub App settings → update DOCS_APP_PRIVATE_KEY secret
```

### 7.4 Updating Dependencies

```bash
cd evo-docs

# Update mkdocs and plugins
pip install --upgrade mkdocs-material pymdown-extensions

# Freeze new versions
pip freeze | grep -E "mkdocs|pymdown" > requirements.txt

# Test locally
./scripts/sync-repos.sh
mkdocs build --strict

# Commit
git add requirements.txt
git commit -m "chore: update mkdocs-material and dependencies"
git push
```

### 7.5 Managing IAP Access

> **Note:** These commands require a Serverless NEG + load balancer to be set up (see §1.7). Until then, manage access via the Cloud Console: **Cloud Run → evo-docs → Security.**

```bash
# Grant access to a specific user
gcloud iap web add-iam-policy-binding \
  --resource-type=backend-services \
  --member="user:person@pricer.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --project=platform-dev-p01

# Grant access to a Google Group
gcloud iap web add-iam-policy-binding \
  --resource-type=backend-services \
  --member="group:engineering@pricer.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --project=platform-dev-p01

# Revoke access
gcloud iap web remove-iam-policy-binding \
  --resource-type=backend-services \
  --member="user:person@pricer.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --project=platform-dev-p01

# View current access
gcloud iap web get-iam-policy \
  --resource-type=backend-services \
  --project=platform-dev-p01
```

### 7.6 Rollback Procedure

If a deployment breaks the site:

```bash
# 1. List recent revisions
gcloud run revisions list \
  --service=evo-docs \
  --region=europe-north1 \
  --project=platform-dev-p01

# 2. Roll back to the previous revision
gcloud run services update-traffic evo-docs \
  --region=europe-north1 \
  --project=platform-dev-p01 \
  --to-revisions=<REVISION_NAME>=100

# 3. Fix the issue in evo-docs and push
```

---

## 8. Troubleshooting

### 8.1 "sync-repos.sh: Permission denied (publickey)"

**Cause:** GitHub App token not available or expired.

**Fix:**
1. Check that `DOCS_APP_ID` and `DOCS_APP_PRIVATE_KEY` secrets exist in the repo
2. Verify the GitHub App is still installed on PricerAB
3. Regenerate the private key if expired

### 8.2 "Repo not found" for a source repo

**Cause:** Repo renamed, deleted, or made private.

**Fix:**
1. Update or remove the entry in `repos.txt`
2. Check the repo still exists: `gh repo view PricerAB/<repo-name>`

### 8.3 "mkdocs build --strict" fails

**Cause:** Broken links or missing files.

**Fix:**
1. Read the error output — it says exactly which file has a broken link
2. Fix the link in the source repo (not in `evo-docs`)
3. The next build will pick up the fix

### 8.4 "Nav marker not found" in generate-nav.py

**Cause:** The marker comment was removed from `mkdocs.yml`.

**Fix:**
Ensure `mkdocs.yml` has this line exactly:
```yaml
# REST OF NAV IS AUTO-GENERATED FROM _sources/
```

### 8.5 Build succeeds but new docs don't appear

**Cause:** The repo isn't in `repos.txt` or the category isn't in `generate-nav.py`.

**Fix:**
1. Check the repo is in `repos.txt` (one line per repo)
2. Check `scripts/generate-nav.py` → `CATEGORY_MAP` has an entry for the repo
3. Check the build logs — does `sync-repos.sh` show the repo being cloned?

### 8.6 IAP returns 403 for valid @pricer.com users

**Cause:** User not granted `IAP-secured Web App User` role.

**Fix:**
```bash
gcloud iap web add-iam-policy-binding \
  --member="user:person@pricer.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --project=platform-dev-p01
```

### 8.7 Docker build fails with "COPY failed: file not found"

**Cause:** `mkdocs build` didn't produce a `site/` directory (build step failed).

**Fix:**
Run `mkdocs build` locally with `--verbose` to see the real error. Usually a broken link or missing file in one of the cloned source repos.

---

## Appendix A: Quick Reference

### Commands Cheat Sheet

```bash
# Hub repo — local development
cd evo-docs
./scripts/sync-repos.sh        # Clone all source repos
mkdocs serve                    # Local preview at http://localhost:8000
mkdocs build --strict           # Build with link checking

# Hub repo — deploy manually
git push                        # Triggers CI deploy
# OR: GitHub Actions → Build & Deploy Docs → Run workflow

# GCP — check deployment
gcloud run services describe evo-docs \
  --region=europe-north1 \
  --project=platform-dev-p01 \
  --format='value(status.url)'

# GCP — view logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=evo-docs" \
  --project=platform-dev-p01 \
  --limit=10

# Add a new doc-source repo
echo "new-repo" >> repos.txt
# Add to scripts/generate-nav.py CATEGORY_MAP
git add -A && git commit -m "docs: add new-repo" && git push

# Remove a doc-source repo
# Delete the line from repos.txt (or comment with #)
git add repos.txt && git commit -m "docs: remove stale-repo" && git push
```

### Repo States

| Repo Has | Hub Shows | Hub Nav Style |
|----------|-----------|---------------|
| `docs/index.md` only | Single page under repo label | Flat — one link |
| `docs/index.md` + other `.md` files | All pages under repo label | Flat — list of pages |
| `docs/` + `mkdocs.yml` with nav | Pages with custom structure | Nested — follows repo's nav |

---

## Appendix B: Files Checklist

When setting up the platform, create these files in order:

- [ ] GCP: APIs enabled (§1.2)
- [ ] GCP: Artifact Registry repo (§1.3)
- [ ] GCP: Workload Identity Federation (§1.4)
- [ ] GCP: Initial Cloud Run deploy (§1.5)
- [ ] GCP: IAP enabled (§1.6)
- [ ] GitHub: App created and installed (§2.13)
- [ ] GitHub: Secrets added to evo-docs (§2.12)
- [ ] `evo-docs/mkdocs.yml` (§2.2)
- [ ] `evo-docs/docs/index.md` (§2.3)
- [ ] `evo-docs/requirements.txt` (§2.4)
- [ ] `evo-docs/scripts/sync-repos.sh` (§2.5)
- [ ] `evo-docs/scripts/generate-nav.py` (§2.6)
- [ ] `evo-docs/repos.txt` (§2.7)
- [ ] `evo-docs/Dockerfile` (§2.8)
- [ ] `evo-docs/nginx.conf` (§2.9)
- [ ] `evo-docs/.github/workflows/build-and-deploy.yml` (§2.10)
- [ ] `evo-docs/.gitignore` (§2.11)
- [ ] Push evo-docs → verify CI deploy succeeds
- [ ] First source repo added → verify it appears on the site

---

> **Companion docs:** [16 — Docs GitHub Strategy](16-docs-github-strategy.md) · [README](README.md)
