# 18 — Docs GitHub Implementation Guide

> **Scope:** A concrete, step-by-step implementation guide for the docs-as-code platform described in [doc 16](16-docs-github-strategy.md). Covers: GCP infrastructure setup, hub repo creation, CI/CD pipeline, per-repo docs convention, adopting existing repos, creating new repos with docs, maintenance procedures, and access management. **For Confluence content migration, see [doc 16 §6](16-docs-github-strategy.md#6-migration-plan). This guide covers platform infrastructure only.**
>
> **Audience:** Platform engineer implementing the docs platform. Every command is copy-paste ready. Every YAML file is complete.
>
> **Drafted:** 2026-06-30 — validated against Pricer's existing GCP infrastructure (`platform-dev-p01`, `europe-north1`, Cloud Run, IAP) and the `evo-dtoflow-protos` docs model.
>
> **Last updated:** 2026-07-07 — reconciled with what was actually built. See [§10 Changelog vs. plan](#10-changelog-vs-plan) for the full delta. Companion docs: [26 — Implementation Report](26-platform-docs-hub-implementation-report.md) (build history, 8 issues hit and fixed) and [27 — Operations Guide](27-hub-operations-guide.md) (day-to-day procedures, caching gotchas).

> **⚠️ Status of this guide.** This document still describes the *target* design for the docs hub. Some sections (IAP, custom domain, full CI/CD with Workload Identity Federation, stale-content detection) are not yet implemented — see [§10](#10-changelog-vs-plan) for what is live vs. deferred. The live hub runs at `https://platform-docs-hub-990006507229.europe-north1.run.app` and currently serves 93 pages from 2 source repos.

---

## Table of Contents

1. [Infrastructure Setup](#1-infrastructure-setup) — GCP project, Cloud Run, IAP, DNS
2. [Hub Repo: `platform-docs-hub`](#2-hub-repo-platform-docs-hub) — Complete file-by-file setup
3. [Creating a New Repo with Docs](#3-creating-a-new-repo-with-docs) — Template + conventions
4. [Adopting an Existing Repo](#4-adopting-an-existing-repo) — Step-by-step guide
5. [Adding & Removing Docs from the Hub](#5-adding--removing-docs-from-the-hub)
6. [CI/CD Pipeline Details](#6-cicd-pipeline-details)
7. [Maintenance Procedures](#7-maintenance-procedures)
8. [Troubleshooting](#8-troubleshooting)
9. [Contribution Workflows](#9-contribution-workflows)
10. [Changelog vs. plan](#10-changelog-vs-plan) — what was actually built vs. drafted here

---

## 1. Infrastructure Setup

### 1.1 Prerequisites

- GCP project with billing enabled (`platform-dev-p01` recommended — same as the rest of the platform)
- `gcloud` CLI authenticated
- GitHub repo `PricerAB/platform-docs-hub` (created 2026-07-02, was originally drafted here as `evo-docs`)
- Docker installed locally (for testing the Dockerfile)
- `gh` CLI authenticated (for sourcing the GitHub token used at build time to clone source repos)

### 1.2 Enable Required GCP APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  --project=platform-dev-p01
```

> **Note:** `iap.googleapis.com` and `cloudbuild.googleapis.com` are not yet enabled — the hub currently runs public on Cloud Run (see [§10](#10-changelog-vs-plan)). IAP and Cloud Build will be re-added when we wire up the production CI/CD pipeline and the `docs.pricer-plaza.com` custom domain.

### 1.3 Create Artifact Registry Repository

```bash
gcloud artifacts repositories create evo-images \
  --repository-format=docker \
  --location=europe-west3 \
  --project=platform-dev-p01
```

> **Note:** The registry lives in `europe-west3-docker.pkg.dev` (not `europe-north1-docker`). This was a deliberate choice — Artifact Registry already had an existing `evo-images` repo we reuse for the docs hub image, avoiding creating a new registry just for docs. Cloud Run deploys from `europe-west3` even though the service itself runs in `europe-north1`.

### 1.4 Set Up Workload Identity Federation (for GitHub Actions → GCP)

> **Status: NOT YET IMPLEMENTED.** The current deployment is manual (local `docker build` + `docker push` + `gcloud run deploy`), see [§10](#10-changelog-vs-plan). This section is the *target* design that will be wired up in the next iteration. Skip it for now.

This lets GitHub Actions deploy to Cloud Run without storing long-lived service account keys.

```bash
# Create a service account for the CI pipeline
gcloud iam service-accounts create platform-docs-hub-ci \
  --display-name="platform-docs-hub CI/CD" \
  --project=platform-dev-p01

# Grant required roles
gcloud projects add-iam-policy-binding platform-dev-p01 \
  --member="serviceAccount:platform-docs-hub-ci@platform-dev-p01.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding platform-dev-p01 \
  --member="serviceAccount:platform-docs-hub-ci@platform-dev-p01.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding platform-dev-p01 \
  --member="serviceAccount:platform-docs-hub-ci@platform-dev-p01.iam.gserviceaccount.com" \
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

# Create a provider for the platform-docs-hub repo
gcloud iam workload-identity-pools providers create-oidc "platform-docs-hub-provider" \
  --project="platform-dev-p01" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="platform-docs-hub GitHub Actions" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Allow the platform-docs-hub repo to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding \
  "platform-docs-hub-ci@platform-dev-p01.iam.gserviceaccount.com" \
  --project="platform-dev-p01" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/PricerAB/platform-docs-hub"
```

**Note the WIF provider name** — you'll add it as `WIF_PROVIDER` secret in GitHub. It looks like:
`projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/platform-docs-hub-provider`

### 1.5 Deploy Cloud Run Service (Initial Empty Deploy)

First, we need an initial deploy so IAP can be configured. Use a placeholder container:

```bash
# Create a minimal placeholder
mkdir -p /tmp/platform-docs-hub-placeholder
cat > /tmp/platform-docs-hub-placeholder/Dockerfile << 'EOF'
FROM nginx:alpine
RUN echo '<html><body><h1>Pricer Docs — Coming Soon</h1></body></html>' \
  > /usr/share/nginx/html/index.html
EOF

# Build and push
gcloud builds submit /tmp/platform-docs-hub-placeholder \
  --tag=europe-west3-docker.pkg.dev/platform-dev-p01/evo-images/platform-docs-hub \
  --project=platform-dev-p01

# Deploy
gcloud run deploy platform-docs-hub \
  --image=europe-west3-docker.pkg.dev/platform-dev-p01/evo-images/platform-docs-hub \
  --region=europe-north1 \
  --platform=managed \
  --allow-unauthenticated \
  --memory=256Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --concurrency=80 \
  --project=platform-dev-p01
```

> **Live command actually used.** The deploy flag set above (`--memory=256Mi`, `--cpu=1`, `--min-instances=0`, `--max-instances=3`, `--concurrency=80`) is the current production configuration. See [27 — Operations Guide §1](27-hub-operations-guide.md) for the copy-paste-ready full deploy command.

### 1.6 Configure IAP (Identity-Aware Proxy)

> **Status: NOT YET IMPLEMENTED.** The hub is currently **public** (`--allow-unauthenticated`) — see [§10](#10-changelog-vs-plan). IAP will be re-enabled when we set up the `docs.pricer-plaza.com` custom domain via load balancer. The PricerAB org also disabled GitHub Pages org-wide, which made the originally drafted Pages-based auth approach unworkable.

IAP for Cloud Run requires a **Serverless NEG + external load balancer**. The `gcloud iap web` commands target App Engine/Compute Engine, not Cloud Run directly. Here's the correct approach:

**Step 1: Configure the OAuth consent screen** (one-time per project):
- Go to: https://console.cloud.google.com/apis/credentials/consent
- Set to **"Internal"** (only `@pricer.com` accounts)

**Step 2: Remove unauthenticated access from Cloud Run:**

```bash
gcloud run services update platform-docs-hub \
  --region=europe-north1 \
  --project=platform-dev-p01 \
  --no-allow-unauthenticated
```

**Step 3: Grant IAP service account permission to invoke Cloud Run:**

```bash
# Get the project number
PROJECT_NUMBER=$(gcloud projects describe platform-dev-p01 --format='value(projectNumber)')

# Grant the IAP service agent invoker permission
gcloud run services add-iam-policy-binding platform-docs-hub \
  --region=europe-north1 \
  --project=platform-dev-p01 \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

**Step 4: Set up Serverless NEG + Load Balancer with IAP** (when ready for `docs.pricer-plaza.com` — see §1.7):

For the initial setup, use the Cloud Console: **Cloud Run → platform-docs-hub → Security → "Use Identity-Aware Proxy"** and enable it. Then add the `IAP-secured Web App User` role to `domain:pricer.com`.

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

> **Phase 1 simplification:** The hub currently runs publicly on Cloud Run with no IAP. The internal-only access model is deferred until the custom domain lands. Internal documentation that must stay private lives in Confluence — the docs hub is for content that's safe to share externally.

### 1.7 DNS Configuration (when ready for `docs.pricer-plaza.com`)

```bash
# Create a global external load balancer with IAP
# 1. Reserve a global static IP
gcloud compute addresses create docs-pricer-ip --global

# 2. Create a managed SSL certificate
gcloud compute ssl-certificates create docs-pricer-cert \
  --domains=docs.pricer-plaza.com --global

# 3. Map the IP to Cloud Run via Serverless NEG
gcloud compute network-endpoint-groups create docs-pricer-neg \
  --region=europe-north1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=platform-docs-hub

# 4. Create backend service, URL map, target proxy, forwarding rule
# (Full load balancer setup is ~6 more commands — see GCP docs:
#  https://cloud.google.com/load-balancing/docs/https/setting-up-https-serverless)

# 5. Add CNAME record in Pricer's DNS:
#    docs.pricer-plaza.com → <static-ip-from-step-1>
```

> **For Phase 1, skip DNS** — use the auto-generated Cloud Run URL (`https://platform-docs-hub-990006507229.europe-north1.run.app`). DNS + load balancer can wait until the site has content worth sharing.

---

## 2. Hub Repo: `platform-docs-hub`

This is the complete file-by-file setup for the central documentation hub.

> **Live repo:** `PricerAB/platform-docs-hub` (was originally drafted here as `evo-docs` — renamed when we discovered the org already used `evo-docs` semantically elsewhere). Local working copy: `/Users/cridea/Projects/AI/platform-docs-hub-pricer`.

### 2.1 Repository Structure

```
platform-docs-hub/
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
│       └── build-and-deploy.yml    # ⚠️ Currently broken — still targets Pages
├── repos.txt                  # Source repo registry
├── .gitignore
└── README.md
```

> **Important naming note.** Source repos are cloned into `docs/sources/<repo>/` (NOT `docs/_sources/`). Underscore-prefixed directories are silently 404'd by nginx and most CDNs — see [26 §Attempt 5](26-platform-docs-hub-implementation-report.md) for the full debugging trail.

### 2.2 `mkdocs.yml`

```yaml
site_name: "Pricer Documentation"
site_description: "Pricer AB platform documentation — architecture, services, APIs, and onboarding"
repo_url: https://github.com/PricerAB/platform-docs-hub
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
  # REST OF NAV IS AUTO-GENERATED FROM sources/
```

> **Note:** The marker comment in the live file says `FROM sources/` (not `FROM _sources/`). If you change the marker, update `NAV_MARKER` in `scripts/generate-nav.py` to match — the script fails with "Nav marker not found" if they drift.

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

This script clones all doc-source repos into `sources/` (NOT `_sources/` — underscore-prefixed dirs are blocked by nginx). It's the core of the aggregation approach.

> **Why `sources/` not `_sources/`:** MkDocs is happy to read from either, but the **served HTML** is what matters. nginx treats `_`-prefixed directories as hidden/internal and returns 404 even though the files are on disk. See [26 §Attempt 5](26-platform-docs-hub-implementation-report.md) — this is the single highest-impact gotcha in the whole pipeline.

```bash
#!/bin/bash
# sync-repos.sh — Clone all doc-source repos into sources/
# Run from the platform-docs-hub repo root.
set -euo pipefail

SOURCES_DIR="sources"
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
"""generate-nav.py — Scan sources/ for docs and generate mkdocs nav structure.

For each cloned repo in sources/:
1. If the repo has docs/mkdocs.yml, extract its nav structure.
2. Otherwise, scan docs/ for .md files and create a flat nav.
3. Merge all navs into the hub's mkdocs.yml.
"""

import os
import yaml
from pathlib import Path

SOURCES_DIR = "sources"
MKDOCS_YML = "mkdocs.yml"
NAV_MARKER = "# REST OF NAV IS AUTO-GENERATED FROM sources/"

# Category mapping — which top-level section each repo belongs to
# Add repos to the appropriate category as they're onboarded.
CATEGORY_MAP = {
    # Platform Architecture
    "evo-dtoflow-protos": {
        "section": "Platform Architecture",
        "label": "DTOflow & DTOs",
    },
    "platform-docs-hub": {"section": None},  # hub repo itself — skip

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
        src_path = f"sources/{repo_name}/docs/{rel}"
        title = f.stem.replace("-", " ").replace("_", " ").title()
        if rel == Path("index.md"):
            nav.insert(0, {title: src_path})
        else:
            nav.append({title: src_path})
    return nav


def rewrite_paths(repo_name: str, nav: list) -> list:
    """Rewrite paths in a nav structure to point to sources/.

    Per-repo mkdocs.yml nav entries are written relative to that repo's
    docs_dir. When we hoist them into the hub, we must:
      1. Prepend `sources/<repo>/` (the clone location in the hub).
      2. Prepend `docs/` if the per-repo entry doesn't already include it
         (e.g., when the entry is `00-foo.md` rather than `docs/00-foo.md`).
    """
    result = []
    for item in nav:
        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, str):
                    if not value.startswith("http") and not value.startswith("sources/"):
                        # If path references a file outside docs/ (e.g., ../README.md),
                        # rewrite relative to the repo root, not docs/
                        if value.startswith("../") or not value.startswith("docs/"):
                            value = f"sources/{repo_name}/{value.lstrip('./')}"
                        else:
                            value = f"sources/{repo_name}/{value}"
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
        print("No sources/ directory — skipping nav generation")
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

> **Two non-obvious fixes baked into the live script (vs. the originally drafted version):**
>
> 1. **`SOURCES_DIR = "sources"`** — not `_sources`. See comment at the top of `sync-repos.sh` for why.
> 2. **`rewrite_paths()` prepends `docs/`** when the per-repo nav entry doesn't already start with `docs/`. Without this, `replatforming-onboarding` (whose per-repo `mkdocs.yml` uses entries like `00-replatforming-program-overview.md`) renders 404s because the path becomes `sources/replatforming-onboarding/00-...md` instead of `sources/replatforming-onboarding/docs/00-...md`. See [26 §Attempt 6](26-platform-docs-hub-implementation-report.md) for the full debugging trail.

### 2.7 `repos.txt` (Doc-Source Registry)

One repo per line. This is the canonical list of repos that contribute docs. Add/remove repos here to control what appears on the site.

> **Status as of 2026-07-07.** Only the 2 repos below are *live* on the hub (93 pages total). The remaining 15 entries are the *target adoption backlog* — repos that need `docs/` folders and a per-repo `mkdocs.yml` before they can be uncommented. See [§10](#10-changelog-vs-plan) for the rollout plan.

```
# Pricer Documentation Sources
# One repo per line. Lines starting with # are ignored.
# The sync script clones each repo into sources/<name>/.

# === LIVE (2 repos, 93 pages) ===
evo-dtoflow-protos
replatforming-onboarding

# === ADOPTION BACKLOG (uncomment after adding docs/ + mkdocs.yml) ===

# Platform Core
# evo-dtoflow-protos   ← already live above

# Cloud Run Services
# platform-item-registry-api
# platform-link-service
# platform-evaluation-engine
# platform-image-render-service
# platform-ecc-link-projector
# platform-migration-helper
# platform-scenario-service
# platform-dtoflow-server-spanner
# platform-customer-data

# Consumer Apps
# chain-management-centralization
# plaza-mobile-ui-backend
# plaza-mobile-ui-frontend

# Infrastructure
# cloud-infra-terragrunt-terraform
# platform-gcp-resources
```

To add a repo: create `docs/` and `mkdocs.yml` in the source repo (see [§3](#3-creating-a-new-repo-with-docs) or [§4](#4-adopting-an-existing-repo)), uncomment the line, and add a category entry in `scripts/generate-nav.py` → `CATEGORY_MAP`.

### 2.8 `Dockerfile`

> **Important:** The Dockerfile expects `sources/` to already exist (populated by `scripts/sync-repos.sh`) before `docker build`. In CI, `sync-repos.sh` runs before `docker build`. For local Docker builds, run `sync-repos.sh` first.

> **Two gotchas baked into the live file (vs. the originally drafted version):**
>
> 1. **`apk add --no-cache bash`** — `sync-repos.sh` uses `#!/bin/bash` and bashisms (`[[ ... ]]`). Alpine's base image ships only `ash`, so the script fails with "not found" without this. See [26 §Attempt 3](26-platform-docs-hub-implementation-report.md).
> 2. **`--platform linux/amd64` at build time** — Docker on Apple Silicon builds ARM images by default; Cloud Run requires amd64 and refuses the manifest with HTTP 422 otherwise. See [26 §Attempt 4](26-platform-docs-hub-implementation-report.md). This is *not* a Dockerfile change — it's a `docker build --platform linux/amd64` flag from the host CLI.

```dockerfile
# Stage 1: Build the mkdocs site
FROM python:3.12-alpine AS builder

# bash is required for scripts/sync-repos.sh (bashisms like [[ ]])
RUN apk add --no-cache bash git

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# sources/ must exist (from sync-repos.sh run before docker build)
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

> **⚠️ Status: NOT YET WIRED UP TO CLOUD RUN.** The current file in the hub still deploys to **GitHub Pages**, which is broken because PricerAB org disables Pages creation org-wide (HTTP 422 on `gh api ... pages -X POST`). See [26 §Attempts 1-2](26-platform-docs-hub-implementation-report.md). Until the workflow is updated for Cloud Run + WIF, deploys are done manually via the local one-liner in [27 §7](27-hub-operations-guide.md#7-build-command-one-liner-copy-paste-ready). The draft below is the *target* design.

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
  SERVICE_NAME: platform-docs-hub

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    env:
      REPO: europe-west3-docker.pkg.dev/platform-dev-p01/evo-images/platform-docs-hub

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
        run: gcloud auth configure-docker europe-west3-docker.pkg.dev

      - name: Build and push Docker image
        run: |
          IMAGE_TAG="${REPO}:${GITHUB_SHA::7}"
          docker build --platform linux/amd64 -t "$IMAGE_TAG" .
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
sources/
site/
__pycache__/
*.pyc
.DS_Store
```

### 2.12 GitHub Secrets to Configure

> **Note:** No secrets are configured yet — the current deploy is manual (`gh auth token` sourced at build time from the local machine, not via GitHub Actions). These will be wired up when the Cloud Run CI pipeline in §2.10 lands.

| Secret | Value | Where to Get It |
|--------|-------|----------------|
| `WIF_PROVIDER` | Workload Identity Federation provider string | Output of §1.4 — `projects/.../providers/platform-docs-hub-provider` |
| `GCP_SA` | `platform-docs-hub-ci@platform-dev-p01.iam.gserviceaccount.com` | Created in §1.4 |
| `DOCS_APP_ID` | GitHub App ID | Create a GitHub App (see §2.13) |
| `DOCS_APP_PRIVATE_KEY` | GitHub App private key | From the GitHub App settings |

### 2.13 GitHub App for Cross-Repo Access

The CI pipeline needs read access to all doc-source repos. A GitHub App is the recommended approach.

> **Prerequisite:** Creating a GitHub App in the PricerAB organization requires **organization owner** permissions. If you don't have owner access, coordinate with the PricerAB GitHub admin.

1. **Create a GitHub App:**
   - Go to `https://github.com/organizations/PricerAB/settings/apps/new`
   - Name: `Pricer Docs Aggregator`
   - Homepage URL: `https://github.com/PricerAB/platform-docs-hub`
   - Uncheck "Active" under Webhook (no webhook needed)
   - Permissions: **Repository → Contents → Read-only**
   - Where can this app be installed? **Only on this account**

2. **Generate a private key** and download it.

3. **Install the app** on the PricerAB organization:
   - Go to `https://github.com/organizations/PricerAB/settings/installations`
   - Choose "Install" next to the app
   - Select **All repositories** (or select specific doc-source repos)

4. **Add secrets to platform-docs-hub repo:**
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

\`
``bash
./gradlew quarkusDev   # If Java
npm run dev            # If Node.js
\```

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

Add the repo name to `platform-docs-hub/repos.txt`:

```bash
# In the platform-docs-hub repo:
echo "my-new-service" >> repos.txt

# If the repo needs a custom category label, add it to:
# platform-docs-hub/scripts/generate-nav.py → CATEGORY_MAP
```

Commit and push — the next daily build (or manual trigger) will include the new docs.

#### Step 6: Verify

```bash
# In platform-docs-hub, run locally:
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
git commit -m "docs: add minimal docs for platform-docs-hub"
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
# In platform-docs-hub:
echo "my-existing-repo" >> repos.txt
git add repos.txt
git commit -m "docs: register my-existing-repo in doc hub"
```

#### Step 6: Add to `generate-nav.py`

```python
# In platform-docs-hub/scripts/generate-nav.py, add to CATEGORY_MAP:
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

> **Status: ADOPTED.** This folder was successfully moved into `PricerAB/replatforming-onboarding` and is one of the two live source repos on the hub (24 .md files). Use this procedure as a reference when onboarding the remaining backlog of consumer-app and service repos.

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
2. **Add the repo name to `platform-docs-hub/repos.txt`:**

```bash
cd platform-docs-hub
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

Until the CI pipeline (§6) is wired up to Cloud Run, deploy with the local one-liner from [27 §7](27-hub-operations-guide.md#7-build-command-one-liner-copy-paste-ready).

### 5.2 Removing a Doc-Source Repo

1. **Remove the repo from `platform-docs-hub/repos.txt`** (delete the line or comment it out with `#`)
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

> **For day-to-day operations — caching gotchas (Docker, Artifact Registry, browser), the local build/deploy one-liner, and "I don't see my changes" troubleshooting — see [27 — Operations Guide](27-hub-operations-guide.md).** This section covers the scheduled maintenance procedures.

### 7.1 Daily Maintenance (Automated)

The daily CI build handles:
- **Freshness:** Re-clones all source repos each build — docs are always up to date
- **Broken links:** `mkdocs build --strict` fails the build if any link is broken
- **Missing repos:** `sync-repos.sh` warns but continues if a repo can't be cloned (repo may be deleted or renamed)

If the daily build fails, GitHub Actions sends a notification. Check the logs for the failing step.

> **Note:** As of 2026-07-07 the daily CI build is not yet wired up (§2.10 still targets Pages). Until that's fixed, "freshness" relies on manual rebuilds. Trigger a rebuild with the local one-liner in [27 §7](27-hub-operations-guide.md#7-build-command-one-liner-copy-paste-ready) when you know a source repo has changed.

### 7.2 Weekly Maintenance — Stale Content Detection (Automated)

Add this GitHub Actions workflow to `platform-docs-hub` to automatically flag docs that haven't been updated in 90+ days. It runs every Monday morning and creates an issue if any pages are stale.

> **Note:** Workflow drafted but **not yet added** to the repo. See [26 §Remaining Work](26-platform-docs-hub-implementation-report.md) — listed as "Stale content detection (Low)" priority.

`.github/workflows/detect-stale-docs.yml`:

```yaml
name: Detect Stale Docs
on:
  schedule:
    - cron: '0 9 * * 1'  # Weekly Monday 9am UTC
  workflow_dispatch:        # Manual trigger for ad-hoc checks

jobs:
  stale-detection:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate GitHub App token (for cross-repo clone access)
        id: app-token
        uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ secrets.DOCS_APP_ID }}
          private-key: ${{ secrets.DOCS_APP_PRIVATE_KEY }}

      - name: Sync source repos (need full content to scan)
        run: |
          chmod +x scripts/sync-repos.sh
          ./scripts/sync-repos.sh
        env:
          GITHUB_TOKEN: ${{ steps.app-token.outputs.token }}

      - name: Find stale docs
        run: |
          CUTOFF_DATE=$(date -d '90 days ago' +%s)
          echo "Checking for docs unchanged since $(date -d '90 days ago' '+%Y-%m-%d')..."
          > stale-report.txt

          # Scan sources/ (cloned repos) + docs/ (hub pages)
          for dir in sources docs; do
            find "$dir" -name '*.md' -type f 2>/dev/null | while read file; do
              # Get last Git commit date for this file
              LAST_MODIFIED=$(git log -1 --format=%ct -- "$file" 2>/dev/null)
              if [ -z "$LAST_MODIFIED" ]; then
                # File not tracked by Git yet — skip
                continue
              fi
              if [ "$LAST_MODIFIED" -lt "$CUTOFF_DATE" ]; then
                echo "STALE: $file (last modified $(git log -1 --format=%ci -- "$file"))" >> stale-report.txt
              fi
            done
          done

          STALE_COUNT=$(wc -l < stale-report.txt | tr -d ' ')
          echo "Found $STALE_COUNT stale pages"
          cat stale-report.txt

      - name: Create issue if stale docs found
        if: success()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const staleReport = fs.readFileSync('stale-report.txt', 'utf8').trim();
            if (!staleReport) {
              console.log('No stale docs found — all pages updated within 90 days.');
              return;
            }

            const staleCount = staleReport.split('\n').length;
            await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `📚 ${staleCount} stale doc page(s) detected (${new Date().toISOString().split('T')[0]})`,
              body: `The following pages have not been updated in 90+ days. Please review and either:\n\n- **Update** the content if it's outdated\n- **Add a comment** in the file explaining why the page is still current\n- **Close this issue** if the page is intentionally evergreen (e.g., core architecture principles)\n\n\`\`\`\n${staleReport}\n\`\`\`\n\n> Automated by the [stale doc detection workflow](.github/workflows/detect-stale-docs.yml). Runs every Monday.`,
              labels: ['documentation', 'stale-content']
            });
```

**What it does:**
- Runs every Monday at 9am UTC
- Clones all doc-source repos via `sync-repos.sh`
- Scans every `.md` file under `sources/` and `docs/`
- Flags files whose last Git commit was >90 days ago
- Creates a single GitHub issue listing all stale pages, tagged `stale-content`
- If no stale pages found, exits silently

**Note:** This workflow requires `fetch-depth: 0` if the hub repo uses shallow clones, and the `sync-repos.sh` step must use full clones (not `--depth 1`) for accurate Git history. If shallow clones are preferred for speed, use file modification time (`stat`) instead:

```bash
# Alternative: use file mtime instead of git log (works with shallow clones)
CUTOFF_TIMESTAMP=$(date -d '90 days ago' +%s)
find sources docs -name '*.md' -type f -newermt '90 days ago' -print  # find fresh files
```

### 7.3 Weekly Maintenance (Manual — 5 minutes)

```bash
cd platform-docs-hub

# 1. Check for new repos in the org that might need docs
gh repo list PricerAB --limit 100 --json name --jq '.[].name' > /tmp/all-repos.txt
grep -v -f repos.txt /tmp/all-repos.txt | grep -v "^platform-docs-hub$" > /tmp/missing-from-docs.txt
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
curl -sI "https://platform-docs-hub-990006507229.europe-north1.run.app" | head -1
# Should return: HTTP/2 200
```

### 7.4 Monthly Maintenance (Manual — 15 minutes)

```bash
# 1. Check for mkdocs-material updates
pip install --upgrade mkdocs-material
mkdocs build --strict  # Verify nothing breaks with the new version

# 2. Audit cross-repo links
# Install lychee: brew install lychee
lychee --base docs.pricer-plaza.com site/ 2>&1 | tee link-audit.txt
# Review broken links and fix in source repos

# 3. Review IAP access list (DEFERRED — site is currently public)
# gcloud iap web get-iam-policy \
#   --resource-type=backend-services \
#   --project=platform-dev-p01
# Verify only @pricer.com accounts have access

# 4. Rotate GitHub App private key (every 6 months or per security policy)
# Generate new key in GitHub App settings → update DOCS_APP_PRIVATE_KEY secret
# (DEFERRED until §2.13 GitHub App is created)
```

### 7.4 Updating Dependencies

```bash
cd platform-docs-hub

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

> **Note:** IAP is not yet enabled (the hub runs publicly with `--allow-unauthenticated`). These commands require a Serverless NEG + load balancer to be set up (see §1.7). Once IAP is wired up, manage access here:

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
  --service=platform-docs-hub \
  --region=europe-north1 \
  --project=platform-dev-p01

# 2. Roll back to the previous revision
gcloud run services update-traffic platform-docs-hub \
  --region=europe-north1 \
  --project=platform-dev-p01 \
  --to-revisions=<REVISION_NAME>=100

# 3. Fix the issue in platform-docs-hub and push
```

---

## 9. Contribution Workflows

Three paths for different types of contributors. The principle: no one should need to learn Git to contribute documentation.

### Scenario A: Developer — docs alongside code

1. Developer makes a code change (e.g., adds an API endpoint)
2. In the same branch, updates `docs/api.md` with the new endpoint
3. Runs `mkdocs serve` locally to preview
4. Opens a PR — the PR template ([Appendix C](#appendix-c-pull-request-template)) auto-populates with the doc checklist
5. CI runs `mkdocs build --strict` — fails if links are broken
6. CODEOWNERS auto-assigns the service owner for review
7. After approval → merge. Daily hub rebuild picks up the change.

> **Until CI wires up to Cloud Run:** changes don't auto-deploy. Whoever merges the PR triggers a manual rebuild via the local one-liner in [27 §7](27-hub-operations-guide.md#7-build-command-one-liner-copy-paste-ready).

### Scenario B: Non-technical contributor (PM, designer, support)

Two paths — no Git CLI required for either.

**Path 1 — Quick edit (typo fix, add a paragraph):**

1. Navigate to the `.md` file on GitHub (e.g., `PricerAB/platform-link-service/docs/index.md`)
2. Click the **pencil icon** (✏️) — GitHub opens a web editor
3. Make changes in Markdown. Preview with the "Preview" tab.
4. At the bottom, select **"Create a new branch"** and click **"Propose changes"**
5. GitHub auto-creates a PR. In the description, `@team-platform-core` for review.
6. A platform team member reviews and merges.

No local Git, no clone, no terminal. Just a browser.

**Path 2 — Issue-based (new page, structural change, or unsure about Markdown):**

1. Create a GitHub issue in the appropriate repo with the `documentation` label
2. Describe:
   - What needs to be documented
   - Where it should live (which repo, which section)
   - Any relevant links (code, Slack threads, existing Confluence pages)
3. Tag `@team-platform-core` — they convert the issue into a PR
4. The platform team writes the Markdown, opens a PR, and requests your review before merging

### Scenario C: Brand-new service docs

1. Copy the template from `platform-docs-hub/templates/repo-docs-template/` (to be created in Phase 3 — for now, use the manual steps in [§3.1](#31-step-by-step))
2. Fill in `docs/index.md` (what/why/how — see [§3.1 Step 2](#step-2-write-docsindexmd))
3. Add `mkdocs.yml` with minimal config
4. Commit to `main`
5. Add the repo name to `platform-docs-hub/repos.txt`
6. Add category mapping in `platform-docs-hub/scripts/generate-nav.py` → `CATEGORY_MAP`
7. Next hub rebuild auto-includes the new service

### Quick Reference: Which Path to Use

| Who | What | Path |
|-----|------|------|
| Developer | Doc alongside code change | Scenario A — same branch, same PR |
| PM / Designer | Small fix (typo, paragraph) | Scenario B, Path 1 — GitHub web UI edit |
| PM / Designer | New page or structural change | Scenario B, Path 2 — create issue |
| Anyone | Brand-new service docs | Scenario C — template + registration |

---

## 8. Troubleshooting

> **Day-to-day caching issues** ("I rebuilt but I don't see my changes") are covered in [27 §2](27-hub-operations-guide.md). This section covers the build-pipeline issues from the implementation history and the §1-§7 procedures.

### 8.1 "sync-repos.sh: Permission denied (publickey)"

**Cause:** GitHub App token not available or expired.

**Fix:**
1. Check that `DOCS_APP_ID` and `DOCS_APP_PRIVATE_KEY` secrets exist in the repo
2. Verify the GitHub App is still installed on PricerAB
3. Regenerate the private key if expired

> **Note:** Until the CI pipeline wires up the GitHub App, source clones use `gh auth token` from the local machine (passed via `--build-arg GITHUB_TOKEN`). If a local build fails with permission errors, run `gh auth status` first.

### 8.2 "Repo not found" for a source repo

**Cause:** Repo renamed, deleted, or made private.

**Fix:**
1. Update or remove the entry in `repos.txt`
2. Check the repo still exists: `gh repo view PricerAB/<repo-name>`

### 8.3 "mkdocs build --strict" fails

**Cause:** Broken links or missing files.

**Fix:**
1. Read the error output — it says exactly which file has a broken link
2. Fix the link in the source repo (not in `platform-docs-hub`)
3. The next build will pick up the fix

### 8.4 "Nav marker not found" in generate-nav.py

**Cause:** The marker comment was removed from `mkdocs.yml`, or its text drifted from `NAV_MARKER` in `generate-nav.py`.

**Fix:**
Ensure `mkdocs.yml` has this line exactly:
```yaml
# REST OF NAV IS AUTO-GENERATED FROM sources/
```

And that `NAV_MARKER` in `scripts/generate-nav.py` matches (currently `# REST OF NAV IS AUTO-GENERATED FROM sources/`).

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

> **Note:** IAP is not yet enabled. The hub currently runs with `--allow-unauthenticated`. This section is a forward reference for when IAP is wired up.

### 8.7 Docker build fails with "COPY failed: file not found"

**Cause:** `mkdocs build` didn't produce a `site/` directory (build step failed).

**Fix:**
Run `mkdocs build` locally with `--verbose` to see the real error. Usually a broken link or missing file in one of the cloned source repos.

### 8.8 Docker build fails with "/bin/sh: ./scripts/sync-repos.sh: not found"

**Cause:** Alpine's base image ships only `ash`, not `bash`. `sync-repos.sh` uses `#!/bin/bash` and bashisms (`[[ ... ]]`).

**Fix:** Already fixed in the live `Dockerfile` (§2.8) via `RUN apk add --no-cache bash git`. If you copy the Dockerfile from elsewhere, make sure the `apk add` line is present. See [26 §Attempt 3](26-platform-docs-hub-implementation-report.md).

### 8.9 `gcloud run deploy` fails: "Container manifest type must support amd64/linux"

**Cause:** Docker on Apple Silicon builds ARM64 images by default; Cloud Run requires amd64.

**Fix:** Always pass `--platform linux/amd64` to `docker build`:
```bash
docker build --platform linux/amd64 ...
```
See [26 §Attempt 4](26-platform-docs-hub-implementation-report.md).

### 8.10 Landing page renders but every sidebar link returns 404

**Cause:** Source repos were cloned into `docs/_sources/` (underscore prefix). Web servers including nginx treat underscore-prefixed directories as hidden/internal and refuse to serve files from them — even though the HTML is on disk.

**Fix:** Rename `_sources` → `sources` everywhere: in `sync-repos.sh` (`SOURCES_DIR="sources"`), in `generate-nav.py` (`SOURCES_DIR = "sources"` + nav marker), and in the `mkdocs.yml` marker comment. See [26 §Attempt 5](26-platform-docs-hub-implementation-report.md).

### 8.11 One repo's links work but another's 404 (mixed results)

**Cause:** `rewrite_paths()` in `generate-nav.py` doesn't prepend `docs/` when a per-repo `mkdocs.yml` nav entry uses bare filenames (e.g., `00-foo.md` instead of `docs/00-foo.md`).

**Fix:** Already fixed in the live script — `rewrite_paths()` checks whether the path starts with `docs/` and prepends it if missing. If you regenerate the script, preserve that branch. See [26 §Attempt 6](26-platform-docs-hub-implementation-report.md).

### 8.12 Landing page card links 404 even though the sidebar links work

**Cause:** The landing page (`docs/index.md`) used hardcoded "pretty" paths (`platform/overview/`, `services/index/`) that don't correspond to the actual file structure under `sources/<repo>/docs/`.

**Fix:** Update landing page links to point to actual source paths (e.g., `sources/evo-dtoflow-protos/docs/index.md`). See [26 §Attempt 7](26-platform-docs-hub-implementation-report.md).

### 8.13 A card link 404s because the source repo has no `docs/index.md`

**Cause:** The source repo's docs start at numbered files (`00-foo.md`) — there's no `index.md` for the section to land on.

**Fix:** Either create `docs/index.md` in the source repo with a brief overview, or update the landing page card to link directly to the first numbered file. See [26 §Attempt 8](26-platform-docs-hub-implementation-report.md).

### 8.14 GitHub Pages deploy fails with HTTP 422

**Cause:** The PricerAB GitHub organization has Pages creation **disabled at the org level**. No repo in the org can use GitHub Pages — `gh api repos/PricerAB/<repo>/pages -X POST` returns 422.

**Fix:** Don't use GitHub Pages. Deploy to Cloud Run instead (which is what the live hub does). See [26 §Attempt 2](26-platform-docs-hub-implementation-report.md).

---

## Appendix A: Quick Reference

### Commands Cheat Sheet

```bash
# Hub repo — local development
cd platform-docs-hub
./scripts/sync-repos.sh        # Clone all source repos
mkdocs serve                    # Local preview at http://localhost:8000
mkdocs build --strict           # Build with link checking

# Hub repo — deploy manually (current flow; CI not yet wired)
# Full one-liner in 27 §7; abbreviated:
docker build --no-cache --platform linux/amd64 \
  --build-arg GITHUB_TOKEN="$(gh auth token)" \
  -t europe-west3-docker.pkg.dev/platform-dev-p01/evo-images/platform-docs-hub:latest .
docker push europe-west3-docker.pkg.dev/platform-dev-p01/evo-images/platform-docs-hub:latest
gcloud run deploy platform-docs-hub \
  --image=europe-west3-docker.pkg.dev/platform-dev-p01/evo-images/platform-docs-hub:latest \
  --region=europe-north1 --platform=managed --allow-unauthenticated \
  --memory=256Mi --cpu=1 --min-instances=0 --max-instances=3 --concurrency=80 \
  --project=platform-dev-p01

# GCP — check deployment
gcloud run services describe platform-docs-hub \
  --region=europe-north1 \
  --project=platform-dev-p01 \
  --format='value(status.url)'

# GCP — view logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=platform-docs-hub" \
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
- [ ] GCP: Artifact Registry repo (§1.3) — note `europe-west3` not `europe-north1`
- [ ] GCP: Workload Identity Federation (§1.4) — **DEFERRED until CI pipeline wires up**
- [ ] GCP: Initial Cloud Run deploy (§1.5)
- [ ] GCP: IAP enabled (§1.6) — **DEFERRED until custom domain lands**
- [ ] GitHub: App created and installed (§2.13) — **DEFERRED until CI pipeline wires up**
- [ ] GitHub: Secrets added to platform-docs-hub (§2.12) — **DEFERRED**
- [ ] `platform-docs-hub/mkdocs.yml` (§2.2)
- [ ] `platform-docs-hub/docs/index.md` (§2.3)
- [ ] `platform-docs-hub/requirements.txt` (§2.4)
- [ ] `platform-docs-hub/scripts/sync-repos.sh` (§2.5)
- [ ] `platform-docs-hub/scripts/generate-nav.py` (§2.6)
- [ ] `platform-docs-hub/repos.txt` (§2.7)
- [ ] `platform-docs-hub/Dockerfile` (§2.8) — includes `apk add bash git`
- [ ] `platform-docs-hub/nginx.conf` (§2.9)
- [ ] `platform-docs-hub/.github/workflows/build-and-deploy.yml` (§2.10) — **NOT YET targeting Cloud Run**
- [ ] `platform-docs-hub/.gitignore` (§2.11) — note `sources/` not `_sources/`
- [ ] Push platform-docs-hub → manually deploy via local one-liner
- [ ] First source repo added → verify it appears on the site

---

## 10. Changelog vs. plan

This guide was drafted 2026-06-30 against an idealized design. Reality landed differently in several places. This section is the canonical delta — if you're reading §1-§9 and they don't match what you see in production, **start here**.

### 10.1 What was built vs. what was drafted

| Area | Drafted (§1-§9) | As-built (live 2026-07-07) | Why it changed |
|:---|:---|:---|:---|
| Hub repo name | `PricerAB/evo-docs` | `PricerAB/platform-docs-hub` | Renamed when we discovered `evo-docs` was already used semantically in the org |
| Source dir | `docs/_sources/<repo>/` | `docs/sources/<repo>/` | nginx (and most CDNs) silently 404 underscore-prefixed directories — see [26 §Attempt 5](26-platform-docs-hub-implementation-report.md) |
| Hosting | GitHub Pages + IAP | Cloud Run + public (`--allow-unauthenticated`) | PricerAB org has Pages creation disabled org-wide (HTTP 422); IAP requires Serverless NEG + load balancer — deferred |
| Artifact Registry region | `europe-north1-docker.pkg.dev/.../evo-docs/...` | `europe-west3-docker.pkg.dev/platform-dev-p01/evo-images/...` | Reused existing `evo-images` registry instead of creating a new one |
| Cloud Run service name | `evo-docs` | `platform-docs-hub` | Aligned with the repo rename |
| Cloud Run region | (not specified) | `europe-north1` | Aligned with the rest of the platform |
| Cloud Run URLs | (single URL assumed) | Two URLs: `platform-docs-hub-990006507229.europe-north1.run.app` (primary, current project) + `platform-docs-hub-yrwyrs6axa-lz.a.run.app` (legacy, from previous project) | Service annotation has both; legacy URL still serves the same service |
| Cloud Run deploy flags | (assumed full set) | `--memory=256Mi --cpu=1 --concurrency=80 --timeout=300`; **no** `--min-instances` (defaults to 0) or `--max-instances` (capped at 3 via revision template annotation) | Matched actual `gcloud run services describe` output |
| Cloud Run service account | (not specified) | Default compute SA `990006507229-compute@developer.gserviceaccount.com` | No custom SA created — fine because service is public and uses default compute identity |
| Cloud Run revisions | "4 commits" implied | 14 revisions, active `00014-6nv` | Manual rebuilds over multiple days since the report |
| Image flags | (not specified) | `docker build --platform linux/amd64` | Apple Silicon builds ARM by default; Cloud Run requires amd64 — see [26 §Attempt 4](26-platform-docs-hub-implementation-report.md) |
| Dockerfile `apk add` | (not specified) | `apk add --no-cache git openssh-client bash` | `sync-repos.sh` uses bashisms and `git`; Alpine ships only `ash` — see [26 §Attempt 3](26-platform-docs-hub-implementation-report.md) |
| Dockerfile sync step | Expected `sync-repos.sh` to run *before* `docker build` | Runs **inside** `docker build` (line 14 of live Dockerfile) | Self-contained image — no external dependency at build-host time |
| Theme palette | indigo / indigo | **teal / teal** with Inter (text) + JetBrains Mono (code), custom dark/light icons | Impeccable-inspired branding |
| `repos.txt` format | Bare repo names (`evo-dtoflow-protos`) | Org-prefixed (`PricerAB/evo-dtoflow-protos`) | Should be normalized — `sync-repos.sh` hardcodes `GITHUB_ORG="PricerAB"`; either drop the prefix or remove the hardcoded org |
| `generate-nav.py` path rewrite | Always prepends `sources/<repo>/` | Same, but also prepends `docs/` when missing | Per-repo nav entries like `00-foo.md` need `docs/` prepended or links 404 — see [26 §Attempt 6](26-platform-docs-hub-implementation-report.md) |
| Landing page links | Hardcoded "pretty" paths (`platform/overview/`) | Direct paths to actual `.md` files (`sources/evo-dtoflow-protos/docs/...`) | Hardcoded paths didn't match the cloned structure — see [26 §Attempt 7](26-platform-docs-hub-implementation-report.md) |
| Onboarding `docs/index.md` | Assumed to exist | Created during adoption | Original repo's files started at `00-...md`; no index — see [26 §Attempt 8](26-platform-docs-hub-implementation-report.md) |
| Source repos registered | 17 in `repos.txt` | 2 live (`evo-dtoflow-protos`, `replatforming-onboarding`); 15 still in adoption backlog | Rest need `docs/` + `mkdocs.yml` first; not done yet |
| CI/CD pipeline | GitHub Actions → Cloud Run via WIF + GitHub App | Workflow file present but still targets GitHub Pages (broken) | WIF / GitHub App wiring deferred; deploys currently manual via local `docker build && docker push && gcloud run deploy` |
| Auth | IAP via `domain:pricer.com` | Public, `--allow-unauthenticated` | IAP deferred until custom domain lands |
| WIF / service account | `evo-docs-ci` SA, `evo-docs-provider` WIF | Same names drafted but never created | Deferred with the rest of the CI work |

### 10.2 Status of each section

| Section | Status | Notes |
|:---|:---|:---|
| §1 Infrastructure setup | Partial | GCP project + Artifact Registry + initial Cloud Run deploy work; IAP, DNS, WIF deferred |
| §2 Hub repo files | Live, with one caveat | All files exist and work; CI workflow still targets Pages |
| §3 New repo with docs | Live | Template works, no adoption backlog entries yet |
| §4 Existing repo adoption | 2 of ~17 done | `evo-dtoflow-protos` and `replatforming-onboarding` are live; rest pending |
| §5 Add/remove from hub | Live, manual | Works end-to-end via `repos.txt` + `CATEGORY_MAP`; deploy is local not CI |
| §6 CI/CD pipeline | Drafted only | Workflow file present but broken (still deploys to Pages); manual deploy is the current path |
| §7 Maintenance procedures | Live (some scripts) | Stale-content detection workflow drafted but not added yet; manual checks are described |
| §8 Troubleshooting | Live + extended | Covers the 8 issues from the implementation report |
| §9 Contribution workflows | Live | All three scenarios (developer, non-technical, brand-new service) work today |

### 10.3 Open work, in priority order

| Priority | Item | What's missing |
|:---:|:---|:---|
| High | Fix CI to deploy to Cloud Run | §2.10 workflow file still references Pages. Switch to `google-github-actions/deploy-cloudrun@v2`, wire up WIF (§1.4) and GitHub App (§2.13) |
| High | Stop using `--allow-unauthenticated` before any sensitive content lands | Either keep docs public-safe, or implement IAP (§1.6) |
| Medium | Adopt the 15 backlog repos | See backlog list in §2.7 |
| Medium | Custom domain `docs.pricer-plaza.com` | Load balancer + IAP + DNS (§1.7) |
| Low | Resolve legacy URL `platform-docs-hub-yrwyrs6axa-lz.a.run.app` | Service still serves both URLs; either remove the old domain mapping from the project or document why both are kept |
| Low | Make `--max-instances=3` explicit in deploy command | Currently only enforced via revision template annotation; passing the flag would make the cap visible at deploy time |
| Low | Fix `repos.txt` org prefix | Live file has `PricerAB/evo-dtoflow-protos` but `sync-repos.sh` hardcodes `GITHUB_ORG="PricerAB"`. Either remove the prefix or remove the hardcoded org to avoid confusion |
| Low | Nav title formatting | `Adr 001 Dtoflow...` → `ADR-001: DTOflow...` |
| Low | Versioned docs (`mike` plugin) | For API versioning |
| Low | Stale-content detection workflow | §7.2 drafted but workflow not added |
| Low | Auto-discovery of repos with `docs/` | Replace manual `repos.txt` with GitHub API scan |

### 10.4 Companion documents

- **[26 — Implementation Report](26-platform-docs-hub-implementation-report.md)** — Full build history, 8 issues hit and fixed with debugging trails. **Read this if something breaks.**
- **[27 — Operations Guide](27-hub-operations-guide.md)** — Day-to-day procedures. Caching gotchas (Docker, Artifact Registry, browser), local build & deploy one-liner, troubleshooting. **Read this if you can't see your changes.**

---

## Appendix C: Pull Request Template

> Add this as `.github/pull_request_template.md` in every doc-source repo. It auto-populates every PR description. Doc-specific checklist ensures docs aren't forgotten.

```markdown
## Description

<!-- Brief description of changes. Delete this line when done. -->

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation only
- [ ] Refactor (no behavior change)
- [ ] Infrastructure / CI

## Documentation Checklist

<!-- Required for any PR that changes API, config, or behavior. Delete if docs-only PR. -->

- [ ] `docs/` updated (if API, config, or behavior changed)
- [ ] Ran `mkdocs build --strict` locally — no broken links
- [ ] Cross-references updated (if files moved or renamed)
- [ ] Code examples in docs tested and working
- [ ] New/changed behavior explained in plain language (assume reader is new)

## Testing

- [ ] Tested locally with `mkdocs serve`
- [ ] Verified all internal links resolve
- [ ] If new API endpoint: request/response examples tested with `curl` or similar

## Screenshots (if UI change)

<!-- Drag and drop screenshots here. Delete section if not applicable. -->
```

**Where to add this template:**

| Repo Tier | Action |
|-----------|--------|
| Tier 1 (platform-docs-hub, evo-dtoflow-protos, replatforming-onboarding) | Add `.github/pull_request_template.md` immediately |
| Tier 2 (all Cloud Run services) | Add during Phase 3 rollout |
| Tier 3+ | Optional — add if repo has `docs/` folder |

**How it works:** Once the file exists at `.github/pull_request_template.md`, GitHub automatically fills every new PR description with this template. Contributors fill in the relevant sections and delete the rest. The doc checklist is not enforced by CI (it's a cultural norm), but the `mkdocs build --strict` check in per-repo CI ([§3.1 Step 4](#step-4-add-ci-validation-optional-but-recommended)) catches broken links automatically.

---

> **Companion docs:** [16 — Docs GitHub Strategy](16-docs-github-strategy.md) · [26 — Implementation Report](26-platform-docs-hub-implementation-report.md) · [27 — Operations Guide](27-hub-operations-guide.md)
