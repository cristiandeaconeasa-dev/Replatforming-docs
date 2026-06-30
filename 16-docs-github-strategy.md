# 16 — Docs GitHub Strategy: Pricer Documentation as Code

> **Scope:** A strategy to move all Pricer documentation from Confluence and local folders into GitHub repositories, establishing a "docs-as-code" culture where docs live alongside code, and a centralized frontend (similar to Backstage TechDocs) to browse everything.
>
> **Drafted:** 2026-06-30 — based on the Backstage TechDocs architecture, `evo-dtoflow-protos` existing docs structure (64+ files), PricerAB org inventory (~50 repos), and Pricer's existing Cloud Run + IAP infrastructure.

---

## 1. Vision

```
Every PricerAB repository has a docs/ folder.
A single mkdocs site aggregates them all.
Documentation is built, versioned, and deployed alongside code.
```

**The goal:** Replace Confluence pages and scattered local markdown files with a single, discoverable, version-controlled documentation site — built from the same repos the code lives in.

---

## 2. Current State

### What exists today

| Source | What's there | Problem |
|--------|-------------|---------|
| **Confluence** (`pricer-org.atlassian.net`) | Architecture docs, pipeline status, onboarding, weekly planning | Not versioned alongside code; siloed from dev workflow; requires Atlassian license to browse |
| **`evo-dtoflow-protos/docs/`** | The gold standard — services, DTOs, flows, platform, ADRs (64+ files, 5 subdirectories) | Only one repo has docs; the branch location needs verification (central-documentation returned 404 from gh CLI on 2026-06-30 — may already be merged or renamed) |
| **`Replatforming/onboarding/`** (local) | 15 comprehensive onboarding docs | Not in any repo; only accessible on one machine |
| **`evo-docs` repo** | Exists but empty — described as "Landing page for evo team documentation" | Never populated |
| **48 other repos** | README.md at best, nothing at worst | No consistent docs presence |

### The `evo-dtoflow-protos` model

This is the reference structure to replicate. On the `central-documentation` branch:

```
docs/
├── index.md                  # Platform orientation
├── architecture.md           # Two-layer model explanation
├── decisions/                # 9 ADRs (ADR-001 through ADR-009)
│   ├── ADR-001-*.md
│   └── ...
├── dtos/                     # DTO reference pages (8 files)
│   ├── link.md
│   ├── storeitemvalues.md
│   └── ...
├── flows/                    # End-to-end flow docs (6 files)
│   ├── item-update.md
│   ├── item-esl-linking.md
│   └── ...
├── platform/                 # Platform layer docs (4 files)
│   ├── overview.md
│   ├── cqs.md
│   └── ...
└── services/                 # Service detail pages (13 files)
    ├── link-registry.md
    ├── studio-renderer.md
    └── ...
```

---

## 3. Proposed Approach: **MkDocs Material + CI Aggregation**

### Why not Backstage itself?

Backstage TechDocs is the inspiration, but running a full Backstage instance requires:
- A Kubernetes cluster or dedicated server
- A PostgreSQL database
- Auth integration
- Ongoing maintenance of the Backstage software catalog
- React/Node.js expertise (Pricer's stack is heavily Java/Quarkus)

For Pricer's scale, this is overkill. Backstage TechDocs uses **MkDocs** under the hood — we can use vanilla MkDocs with a CI aggregation script and get 95% of the value with 5% of the infrastructure. No beta plugins, no extra servers.

### Why MkDocs Material?

| Feature | Why it matters for Pricer |
|---------|--------------------------|
| **Mermaid diagram support** (built-in) | Every flow diagram in our docs uses Mermaid — renders natively |
| **Search** (built-in) | Full-text search across all repos |
| **Dark/light mode** | Pricer devs work late |
| **Navigation nesting** | Matches our existing docs structure (services, flows, DTOs, ADRs) |
| **Cloud Run + IAP deployment** | Pricer already uses this stack; built-in Google auth for internal docs |

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  docs.pricer.com                         │
│              (Cloud Run + IAP auth)                      │
│                   Static HTML site                       │
└──────────────────────┬───────────────────────────────────┘
                       │ built & deployed by
                       ▼
┌──────────────────────────────────────────────────────────┐
│               evo-docs (doc hub repo)                    │
│  ┌──────────────────────────────────────────────────┐    │
│  │  mkdocs.yml  ←  defines nav, theme, plugins     │    │
│  │  docs/                                          │    │
│  │    index.md           "Pricer Documentation"    │    │
│  │    _sources/          (cloned by CI script)     │    │
│  │      evo-dtoflow-protos/docs/                    │    │
│  │      replatforming-onboarding/docs/              │    │
│  │      platform-item-registry-api/docs/            │    │
│  │      ... (one dir per doc-source repo)           │    │
│  └──────────────────────────────────────────────────┘
│                                                         │
│  scripts/sync-repos.sh                                  │
│    → clones all doc-source repos into _sources/         │
│  Dockerfile                                             │
│    → nginx serving the mkdocs build output              │
│  .github/workflows/build-and-deploy.yml                 │
│    → sync repos → mkdocs build → deploy to Cloud Run    │
└──────────────────────────────────────────────────────────┘
                       ▲
                       │ docs/ folders sourced from
         ┌─────────────┼─────────────┬──────────────┐
         ▼             ▼             ▼              ▼
┌─────────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐
│ evo-dtoflow-│ │ platform- │ │ plaza-    │ │ chain-    │
│ protos      │ │ *-*       │ │ mobile-*  │ │ management│
│   docs/ ✅  │ │   docs/   │ │   docs/   │ │   docs/   │
└─────────────┘ └───────────┘ └───────────┘ └───────────┘
```

---

## 4. Per-Repo Standard: `docs/` Convention

Every repo that owns documentation gets a standard structure:

### Required files

```
repo-root/
├── docs/
│   ├── index.md            # "What this service/repo does"
│   ├── architecture.md     # (optional) internal architecture
│   └── ...                 # additional pages as needed
├── mkdocs.yml              # minimal config for standalone builds
└── README.md               # brief pointer to docs.pricer.com
```

### Minimal `mkdocs.yml` (per repo)

```yaml
site_name: "<Service Name>"
docs_dir: docs
theme:
  name: material
  features:
    - navigation.sections
    - content.code.copy

nav:
  - Home: index.md
```

### Why per-repo `mkdocs.yml`?

- **Standalone builds:** Any dev can run `mkdocs serve` in their repo and browse docs locally
- **CI validation:** `mkdocs build --strict` catches broken links in PRs
- **Hub auto-discovery:** The hub repo reads each repo's `mkdocs.yml` nav to build the global nav

---

## 5. Doc Hub: `evo-docs` Repo

The existing `evo-docs` repo becomes the central documentation site. It uses a **CI clone-script** approach — no beta plugins needed:

1. `scripts/sync-repos.sh` clones all doc-source repos into `_sources/`
2. `mkdocs.yml` references the `_sources/` paths directly in its `nav:`
3. `mkdocs build` generates the static site
4. The site is deployed to Cloud Run behind IAP

### Structure

```
evo-docs/
├── mkdocs.yml                 # Nav references _sources/ paths
├── docs/
│   └── index.md               # Landing page: "Pricer Documentation"
├── scripts/
│   └── sync-repos.sh          # Clones all doc-source repos into _sources/
├── Dockerfile                 # nginx serving mkdocs site/ output
├── .github/
│   └── workflows/
│       └── build-and-deploy.yml  # CI/CD pipeline
└── README.md
```

### `mkdocs.yml` for the hub

Vanilla mkdocs — no plugins beyond `search`. The CI script clones repos into `_sources/`, so the `nav:` section references those paths directly:

```yaml
site_name: Pricer Documentation
site_url: https://docs.pricer.com
repo_url: https://github.com/PricerAB/evo-docs
theme:
  name: material
  features:
    - navigation.sections
    - navigation.indexes
    - search.suggest
    - search.highlight
    - content.code.copy
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
    - media: "(prefers-color-scheme: dark)"
      scheme: slate

plugins:
  - search

# Global navigation — paths point to _sources/ (cloned by sync-repos.sh)
nav:
  - Home: docs/index.md
  - Platform Architecture:
      - Overview: _sources/evo-dtoflow-protos/docs/index.md
      - Architecture: _sources/evo-dtoflow-protos/docs/architecture.md
  - Services:
      - Link Registry: _sources/platform-link-service/docs/
      - Item Registry API: _sources/platform-item-registry-api/docs/
      # ... auto-generated from repo inventory
  - Replatforming:
      - Systems Architecture: _sources/replatforming-onboarding/docs/01-systems-architecture.md
      # ...
  - ADRs: _sources/evo-dtoflow-protos/docs/decisions/
```

### CI/CD Pipeline (GitHub Actions)

```yaml
name: Build & Deploy Docs
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 6 * * *'  # daily rebuild at 6am
  workflow_dispatch:       # manual trigger

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Sync source repos
        run: ./scripts/sync-repos.sh
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install mkdocs
        run: pip install mkdocs-material
      
      - name: Build
        run: mkdocs build --strict
      
      - name: Auth to GCP
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.GCP_SA }}
      
      - name: Deploy to Cloud Run
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: evo-docs
          region: europe-north1
          source: ./
```

> **Note on the `_sources/` path:** The CI `sync-repos.sh` script clones each doc-source repo into `_sources/<repo-name>/` before the build. The `nav:` section references those paths. When docs move between repos or repo names change, only the `sync-repos.sh` config needs updating.

### Auto-discovery script (`scripts/sync-repos.sh`)

Instead of manually updating `mkdocs.yml` when repos are added/removed, the CI pipeline runs a script that:

1. Queries the PricerAB GitHub org for repos with a `docs/` folder
2. Clones each into `_sources/<repo-name>/`
3. Generates the `nav:` section of `mkdocs.yml` from each repo's `mkdocs.yml` nav
4. Falls back to listing all `*.md` files in `docs/` if no `mkdocs.yml` exists
5. Exits with error if no doc-source repos are found (catches misconfiguration)

### Authentication: Cloud Run + IAP

Pricer architectural docs are internal — they should not be public. The deployment uses **Cloud Run + Identity-Aware Proxy (IAP)** which Pricer already runs for other services:

| Layer | What it does |
|-------|-------------|
| **Cloud Run** | Serves the static HTML site from an nginx container |
| **IAP** | Requires Google authentication — only `@pricer.com` accounts can access |
| **Workload Identity Federation** | CI pipeline authenticates to GCP without long-lived secrets |

**Why not GitHub Pages?** GitHub Pages requires the repo to be public (free tier) or GitHub Enterprise (paid). Pricer's docs contain architectural details that should stay internal. Cloud Run + IAP is already in Pricer's stack (`platform-dev-p01`), costs near-zero for a static site, and provides built-in Google auth.

### Dockerfile

```dockerfile
FROM nginx:alpine
COPY site/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/nginx.conf
```

Minimal — just serve the static mkdocs output.

---

## 6. Migration Plan

> **Cross-reference note:** The onboarding docs in `Replatforming/onboarding/` use relative links like `[doc 03](03-replatforming-deep-dive.md)`. When these are moved into mkdocs (which expects absolute paths from the `docs/` root), all cross-references must be updated to use mkdocs-compatible paths (e.g., `[doc 03](../replatforming/03-replatforming-deep-dive.md)`). Automate this during the migration — don't fix links manually.

### Phase 1 — Foundation (Week 1-2)

| Task | Details |
|------|---------|
| **Merge docs branch → `main`** on `evo-dtoflow-protos` | The docs are already written — locate the correct branch (central-documentation returned 404 on 2026-06-30; find where the docs currently live) and get them on `main` |
| **Set up `evo-docs` hub repo** | Create `mkdocs.yml`, CI pipeline, auto-discovery script |
| **Deploy to Cloud Run** | First build: just `evo-dtoflow-protos` docs, behind IAP |
| **Add `docs/` to 3 pilot repos** | `platform-item-registry-api`, `platform-link-service`, `chain-management-centralization` — add minimal `docs/index.md` + `mkdocs.yml` |

### Phase 2 — Confluence Migration (Week 2-4)

| Source | Destination |
|--------|-------------|
| Confluence "Replatforming Status" page | `replatforming-onboarding/docs/15-overall-status.md` (already exists locally) |
| Confluence "Architecture & Pipeline Status" | `evo-dtoflow-protos/docs/platform/status.md` |
| Confluence onboarding pages | `replatforming-onboarding/docs/` (already done) |
| Confluence weekly planning pages | `replatforming-onboarding/docs/weekly/` — archive format |

### Phase 3 — Full Rollout (Week 4-8)

| Task | Scope |
|------|-------|
| **`docs/` audit for all 50 repos** | Identify repos that need docs vs. readme-only is fine |
| **Add `docs/` to all active platform repos** | Every Cloud Run service gets a `docs/index.md` |
| **Add `docs/` to consumer apps** | Plaza Mobile, Central-Manager, Store UI, Plaza Actions |
| **Create `replatforming-onboarding` repo** | Move local `Replatforming/onboarding/` docs into a tracked GitHub repo |
| **Auto-discovery script** | Full org-scanning: any repo with `docs/` is auto-included |
| **Connect to DNS** | `docs.pricer.com` → Cloud Run (via PSC or external load balancer with IAP) |

### Phase 4 — Living Documentation (Ongoing)

| Practice | Mechanism |
|----------|-----------|
| **Docs PRs alongside code PRs** | "If you change an API, update the docs in the same PR" |
| **Broken link prevention** | `mkdocs build --strict` in CI on every PR |
| **Versioned docs** | `mike` plugin for versioned documentation (v1, v2, etc.) |
| **Confluence read-only** | Move all remaining pages; Confluence becomes archive reference |

---

## 7. Repo Prioritization

Not all 50 repos need full docs. Priority tiers:

### Tier 1 — Must have docs (platform core)

| Repo | Docs content | Priority |
|------|-------------|----------|
| `evo-dtoflow-protos` | DTO schemas, services, flows, ADRs | 🔴 Already done (merge to main) |
| `evo-docs` | Doc hub itself | 🔴 Set up immediately |
| `replatforming-onboarding` | All 15+ onboarding docs | 🔴 Move from local folder |

### Tier 2 — Should have docs (active Cloud Run services)

| Repo | Docs content |
|------|-------------|
| `platform-item-registry-api` | API reference, request flow, item validation |
| `platform-link-service` | Link CRUD, bulk operations, store asset ops |
| `platform-evaluation-engine` | Studio link evaluator — CEL rule evaluation |
| `platform-image-render-service` | Rendering pipeline, image formats |
| `platform-ecc-link-projector` | ECC link projection |
| `platform-migration-helper` | Migration bridge (v1↔v2) |
| `platform-scenario-service` | Communication packs |
| `platform-dtoflow-server-spanner` | DTOflow Spanner server gRPC API |
| `platform-dtoflow-testserver` | Testing guide |
| `platform-customer-data` | Tenant/store data model |

### Tier 3 — Nice to have (consumer apps + infra)

| Repo | Docs content |
|------|-------------|
| `chain-management-centralization` | Central-Manager architecture, Store-Host lifecycle |
| `plaza-mobile-ui-frontend` | App architecture, BFF contracts |
| `plaza-mobile-ui-backend` | BFF API reference |
| `pricer-server-r3server` | R3Server thin-edge architecture |
| `pricer-server-on-prem` | Legacy on-prem docs |
| `evo-apigee-proxies` | Apigee proxy configuration |
| `cloud-infra-terragrunt-terraform` | Infrastructure architecture |
| `platform-gcp-resources` | GCP resource inventory |
| `platform-scripts` | Utility script reference |

### Tier 4 — README-only (tools, legacy, infra)

Everything else. A good README.md is sufficient — no need for a full `docs/` folder.

---

## 8. Doc Template for New Repos

Every new repo (or existing repo being documented) starts with this:

```
docs/
└── index.md      # Required: what this service does, how to use it

Optional, add as needed:
docs/
├── architecture.md    # Internal design decisions
├── api.md            # API reference (if it exposes APIs)
├── operations.md     # How to deploy, monitor, debug
└── changelog.md      # Major changes
```

### `docs/index.md` template

```markdown
# <Service Name>

> **Repo:** `github.com/PricerAB/<repo-name>`
> **Tech:** <Java 21 / Node.js / React Native / ...>
> **Deployed:** Cloud Run `europe-north1` / GKE / ...

## What it does

One paragraph explaining this service's role in the Pricer platform.

## DTOs owned / APIs exposed

- Owns `storeitemvalues`, `itemproperties`, `itemprocessingparameters`
- Subscribes to `link.v2`, `studiolink.v1`

## How to run locally

```bash
./gradlew quarkusDev  # or npm run dev
```

## Related docs

- [DTOflow Architecture](https://docs.pricer.com/platform/)
- [Onboarding guide](https://docs.pricer.com/replatforming/)
```

---

## 9. Comparison: Confluence vs. GitHub Docs

| Concern | Confluence today | GitHub Docs target |
|---------|-----------------|-------------------|
| **Versioned with code?** | No | Yes — docs PR in same repo as code change |
| **Discoverable by devs?** | Must know URL | `docs.pricer.com` — one URL |
| **Search** | Confluence search | MkDocs full-text search |
| **Diagrams** | Gliffy / images | Mermaid (native, version-controlled) |
| **Access** | Atlassian license required | `@pricer.com` Google auth (IAP) |
| **CI validation** | None | `mkdocs build --strict` catches broken links |
| **Review process** | Confluence comments | Standard GitHub PR review |
| **Offline** | No | `mkdocs serve` works locally |
| **Cost** | Atlassian license per user | Near-zero (Cloud Run static site) |

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Devs don't update docs** | Make docs part of the PR template: "Did you update docs?" |
| **Broken links between repos** | `mkdocs build --strict` in CI; daily rebuild catches breakage |
| **Docs diverge from reality** | Daily CI rebuild from source repos; stale docs = broken build |
| **Confluence has useful comments/attachments** | Export relevant content during migration; link to archive |
| **Docs contain internal architecture details** | Deploy behind Cloud Run + IAP — only `@pricer.com` Google accounts can access |
| **CI clone-script fails on private repos** | Use a GitHub App or deploy key with read access to all doc-source repos |

---

## 11. Immediate Next Steps (First Week)

1. **Locate and merge the docs branch → `main`** on `evo-dtoflow-protos` — the central-documentation branch returned 404 on 2026-06-30; find where the 64+ docs currently live
2. **Populate `evo-docs`** — create `mkdocs.yml`, CI pipeline, Dockerfile, deploy to Cloud Run behind IAP
3. **Move `Replatforming/onboarding/` → new `replatforming-onboarding` repo** under `PricerAB` — update cross-reference links to mkdocs-compatible paths
4. **Add `docs/index.md` to 3 pilot repos** — `platform-item-registry-api`, `platform-link-service`, `chain-management-centralization`
5. **Wire them into the hub** — confirm all 4 doc sources appear on the deployed site

---

### Next: Back to [README](README.md)
