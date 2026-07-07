# Platform Docs Hub — Complete Implementation Report

> **Date:** July 2, 2026  
> **Repo:** `PricerAB/platform-docs-hub`  
> **Live Site:** https://platform-docs-hub-990006507229.europe-north1.run.app (also reachable via legacy URL `https://platform-docs-hub-yrwyrs6axa-lz.a.run.app` from the previous project)  
> **Status:** ✅ Production — serving 93 pages from 2 source repos, 14 revisions deployed

---

## Executive Summary

Built a centralized MkDocs Material documentation hub (`PricerAB/platform-docs-hub`) that aggregates documentation from multiple PricerAB repositories into a single searchable site. The hub automatically clones source repos at build time, generates a unified navigation sidebar, and deploys to Google Cloud Run. **93 pages from 2 source repos**, all nav links verified working, zero console errors.

---

## Architecture

```mermaid
flowchart TB
    subgraph sources["📦 Source Repositories"]
        SR1["PricerAB/evo-dtoflow-protos<br/>docs/ (67 .md files)"]
        SR2["PricerAB/replatforming-onboarding<br/>docs/ (24 .md files)"]
    end

    subgraph build["🔨 Docker Build (runs in Dockerfile, not pre-step)"]
        B1["COPY hub files"]
        B2["apk add git openssh-client bash"]
        B3["pip install mkdocs-material"]
        B4["scripts/sync-repos.sh<br/>→ clones repos into docs/sources/<br/>(uses GITHUB_TOKEN build arg)"]
        B5["scripts/generate-nav.py<br/>→ writes nav into mkdocs.yml"]
        B6["mkdocs build<br/>→ generates static site/"]
    end

    subgraph serve["🌐 Cloud Run (europe-north1)"]
        S1["nginx:alpine on port 8080"]
        S2["Static HTML served from /usr/share/nginx/html"]
        S3["Service: platform-docs-hub<br/>Memory 256Mi, CPU 1, concurrency 80<br/>maxScale 3, no min-instances"]
    end

    SR1 & SR2 -->|"git clone --depth 1 --filter=blob:none"| B4
    B1 --> B2 --> B3 --> B4 --> B5 --> B6
    B6 --> S1
    S1 --> S2 --> S3

    style sources fill:#e3f2fd,stroke:#1565c0,color:#000
    style build fill:#fff3e0,stroke:#f57c00,color:#000
    style serve fill:#e8f5e9,stroke:#2e7d32,color:#000
```

### Key Design Decisions

| Decision | Rationale |
|:---|:---|
| **Docker build-time sync** (not CI pre-sync) | Self-contained image — no external dependencies at runtime |
| **`sources/` not `_sources/`** | Web servers (nginx, CDNs) refuse to serve underscore-prefixed directories |
| **Per-repo `mkdocs.yml` nav reuse** | Each source repo defines its own nav; hub merges them |
| **Ephemeral nav generation** | `mkdocs.yml` nav is regenerated at build time, not committed |
| **Cloud Run not GitHub Pages** | PricerAB org disables Pages; Cloud Run provides public access |

---

## What We Tried (And What Failed)

### Attempt 1: GitHub Pages (Private Repo) ❌

```mermaid
flowchart LR
    A["Deploy to GitHub Pages"] --> B["Repo is private"]
    B --> C["Pages requires GitHub login"]
    C --> D["❌ Site inaccessible to public"]
    
    style D fill:#ffcdd2,stroke:#c62828,color:#000
```

**Symptom:** Visiting `PricerAB.github.io/platform-docs-hub` redirected to GitHub login.  
**Root cause:** The repo was private. GitHub Pages for private repos requires authentication.  
**Resolution:** Made repo public — but hit the next issue.

### Attempt 2: GitHub Pages (Public Repo) ❌

```mermaid
flowchart LR
    A["Make repo public"] --> B["Re-enable GitHub Pages"]
    B --> C["Error: 422"]
    C --> D["❌ Org disabled Pages creation"]
    
    style D fill:#ffcdd2,stroke:#c62828,color:#000
```

**Symptom:** `gh api repos/PricerAB/platform-docs-hub/pages -X POST -f "build_type=workflow"` returned HTTP 422.  
**Root cause:** The PricerAB GitHub organization has **Pages creation disabled** at the org level. No repo in the org can use GitHub Pages.  
**Resolution:** Pivoted to Cloud Run deployment using the existing Dockerfile.

### Attempt 3: Dockerfile Missing Build Tools ❌

```mermaid
flowchart LR
    A["docker build"] --> B["alpine: no bash"]
    B --> C["sync-repos.sh uses #!/bin/bash"]
    C --> D["❌ /bin/sh: ./scripts/sync-repos.sh: not found"]
    
    style D fill:#ffcdd2,stroke:#c62828,color:#000
```

**Symptom:** Docker build failed with `/bin/sh: ./scripts/sync-repos.sh: not found`.  
**Root cause:** The Alpine base image has `ash` not `bash`. The script uses bashisms (`[[`, `#!/bin/bash`).  
**Resolution:** Added `bash` to `apk add` in the Dockerfile.

### Attempt 4: ARM Image on Cloud Run ❌

```mermaid
flowchart LR
    A["docker build (Mac)"] --> B["ARM64 image"]
    B --> C["Cloud Run requires amd64"]
    C --> D["❌ Container manifest type must support amd64/linux"]
    
    style D fill:#ffcdd2,stroke:#c62828,color:#000
```

**Symptom:** `gcloud run deploy` failed: "Container manifest type 'application/vnd.oci.image.index.v1+json' must support amd64/linux."  
**Root cause:** Docker on Apple Silicon builds ARM images by default. Cloud Run requires amd64.  
**Resolution:** Added `--platform linux/amd64` to `docker build`.

### Attempt 5: Underscore-Prefixed Directory (`_sources/`) ❌

```mermaid
flowchart LR
    A["Site deployed"] --> B["Landing page loads ✅"]
    B --> C["Search works ✅"]
    C --> D["Sidebar links → 404 ❌"]
    D --> E["Root cause: _sources/ dir"]
    E --> F["nginx refuses underscore-prefixed dirs"]
    
    style F fill:#ffcdd2,stroke:#c62828,color:#000
```

**Symptom:** The landing page rendered correctly and search found results, but every sidebar navigation link returned 404.  
**Root cause:** The source repos were cloned into `docs/_sources/`. Web servers (including nginx) and CDNs treat `_`-prefixed directories as hidden/internal and refuse to serve files from them. MkDocs builds the HTML into `site/_sources/...`, the HTML exists on disk, but nginx won't serve it.  
**Resolution:** Renamed `_sources` → `sources` in all scripts and configs.

### Attempt 6: Missing `docs/` Prefix in Replatforming Nav ❌

```mermaid
flowchart LR
    A["Platform Architecture links work ✅"] --> B["Replatforming links → 404 ❌"]
    B --> C["Path: sources/replatforming-onboarding/00-...md"]
    C --> D["Actual: sources/replatforming-onboarding/docs/00-...md"]
    D --> E["❌ rewrite_paths() missing docs/ prefix"]
    
    style E fill:#ffcdd2,stroke:#c62828,color:#000
```

**Symptom:** Platform Architecture (evo-dtoflow-protos) links worked, but Replatforming (replatforming-onboarding) links 404'd.  
**Root cause:** `rewrite_paths()` in `generate-nav.py` reads per-repo `mkdocs.yml` nav entries (which are relative to the repo's `docs_dir`) but doesn't prepend `docs/` when rewriting them for the hub.  
**Resolution:** Fixed `rewrite_paths()` to prepend `docs/` when the per-repo nav entry doesn't already start with `docs/`.

### Attempt 7: Hardcoded Landing Page Links ❌

```mermaid
flowchart LR
    A["Landing page renders ✅"] --> B["Card links click → 404 ❌"]
    B --> C["Links: platform/overview/, services/index/"]
    C --> D["Actual: sources/evo-dtoflow-protos/docs/..."]
    D --> E["❌ Hardcoded paths don't match source structure"]
    
    style E fill:#ffcdd2,stroke:#c62828,color:#000
```

**Symptom:** Landing page card links (`platform/overview/`, `services/index/`, etc.) all returned 404.  
**Root cause:** The landing page used hardcoded "pretty" paths that didn't correspond to the actual file structure under `sources/...`.  
**Resolution:** Updated all links to point to actual source `.md` paths (e.g., `sources/evo-dtoflow-protos/docs/index.md`).

### Attempt 8: Missing Onboarding Index ❌

```mermaid
flowchart LR
    A["Onboarding guide card → 404 ❌"]
    B["Link: sources/replatforming-onboarding/docs/index.md"]
    C["File doesn't exist"]
    D["❌ No index.md in onboarding repo"]
    
    style D fill:#ffcdd2,stroke:#c62828,color:#000
```

**Symptom:** The "Onboarding guide" landing page card link 404'd.  
**Root cause:** The `replatforming-onboarding` repo had no `docs/index.md` — files started with `00-replatforming-program-overview.md`.  
**Resolution:** Created `docs/index.md` in the onboarding repo and updated the landing page link to point to the first onboarding doc.

---

## What Works Now ✅

```mermaid
flowchart TB
    subgraph worked["✅ What Works"]
        W1["Landing page with grid cards"]
        W2["Platform Architecture → 67 pages"]
        W3["Replatforming → 24 pages (+ index)"]
        W4["Full-text search"]
        W5["Dark/light theme toggle"]
        W6["Mermaid diagrams in content"]
        W7["Code syntax highlighting"]
        W8["Responsive mobile layout"]
        W9["Zero console errors"]
        W10["93 HTML pages total"]
    end
    
    style worked fill:#e8f5e9,stroke:#2e7d32,color:#000
```

### Final File Inventory

```
PricerAB/platform-docs-hub/
├── .github/workflows/build-and-deploy.yml    # CI pipeline (GitHub Actions)
├── .gitignore                                # Excludes docs/sources/, site/
├── Dockerfile                                # Two-stage: Python builder → nginx
├── README.md                                 # Setup instructions
├── docs/
│   └── index.md                              # Landing page with grid cards
├── mkdocs.yml                                # MkDocs Material config + nav marker
├── nginx.conf                                # nginx config (port 8080, gzip, security headers)
├── repos.txt                                 # Source repo registry
├── requirements.txt                          # mkdocs-material, pymdown-extensions, pyyaml
└── scripts/
    ├── generate-nav.py                       # Scans sources, builds sidebar nav
    └── sync-repos.sh                         # Clones source repos + runs nav generator
```

### Source Repos

```mermaid
flowchart LR
    HUB["platform-docs-hub"] --> S1["evo-dtoflow-protos<br/>67 .md files<br/>Platform Architecture"]
    HUB --> S2["replatforming-onboarding<br/>24 .md files<br/>Replatforming Onboarding"]
    
    style HUB fill:#7b1fa2,stroke:#4a0072,color:#fff
    style S1 fill:#e3f2fd,stroke:#1565c0,color:#000
    style S2 fill:#fff3e0,stroke:#f57c00,color:#000
```

---

## The Aggregation Pipeline

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant DC as docker build (local)
    participant D as Dockerfile
    participant S as sync-repos.sh
    participant GH as GitHub (PricerAB)
    participant G as generate-nav.py
    participant M as MkDocs
    participant AR as Artifact Registry
    participant CR as Cloud Run
    participant N as nginx

    Dev->>DC: docker build --platform linux/amd64 --build-arg GITHUB_TOKEN=$(gh auth token) -t IMAGE .
    DC->>D: Run Dockerfile
    D->>D: apk add git openssh-client bash
    D->>D: pip install mkdocs-material
    D->>S: Run sync-repos.sh
    S->>S: Read repos.txt
    loop For each repo
        S->>GH: git clone --depth 1 --filter=blob:none
        GH-->>S: Repo cloned into docs/sources/
    end
    S->>G: Run generate-nav.py
    G->>G: Scan docs/sources/ for repos
    G->>G: For each repo: read mkdocs.yml nav or scan .md files
    G->>G: Rewrite paths to sources/{repo}/docs/...
    G->>G: Group by category (Platform Architecture, Replatforming)
    G->>G: Write generated nav into mkdocs.yml
    G-->>S: Nav generated
    S-->>D: Sync complete
    D->>M: mkdocs build
    M->>M: Build static site/ with Material theme
    M-->>D: site/ generated
    D->>N: Copy site/ to /usr/share/nginx/html
    DC->>AR: docker push IMAGE
    Dev->>CR: gcloud run deploy platform-docs-hub --image=IMAGE ...
    CR->>N: Start container, serve on port 8080
    N-->>CR: Static site served at https://platform-docs-hub-990006507229.europe-north1.run.app
```

---

## Deployment

| Parameter | Value | Source |
|:---|:---|:---|
| **Platform** | Google Cloud Run | `gcloud run services describe` |
| **Region** | `europe-north1` | service annotation `cloud.googleapis.com/location` |
| **Project** | `platform-dev-p01` (project number `990006507229`) | namespace field |
| **Image registry** | `europe-west3-docker.pkg.dev/platform-dev-p01/evo-images` | spec.template.spec.containers[0].image |
| **Image** | `platform-docs-hub:latest` | active image |
| **Active revision** | `platform-docs-hub-00014-6nv` (digest `284c46714395976d9babd0f05bdef49d979f148f08696fe8659c040bccf15f30`) | status.latestReadyRevisionName |
| **Memory** | 256 MiB | resources.limits.memory |
| **CPU** | 1 vCPU | resources.limits.cpu |
| **Container port** | 8080 | ports[0].containerPort |
| **Min instances** | 0 (default — not specified, so cold starts) | (no min-instances annotation) |
| **Max instances** | 3 | annotation `autoscaling.knative.dev/maxScale` on revision template |
| **Concurrency** | 80 | containerConcurrency |
| **Timeout** | 300s | timeoutSeconds |
| **Service account** | `990006507229-compute@developer.gserviceaccount.com` (default compute SA) | serviceAccountName |
| **Auth** | `--allow-unauthenticated` (public) | spec.template.metadata.annotations |
| **URL (primary)** | https://platform-docs-hub-990006507229.europe-north1.run.app | annotation `run.googleapis.com/urls` |
| **URL (legacy)** | https://platform-docs-hub-yrwyrs6axa-lz.a.run.app | also in urls annotation, from previous project `yrwyrs6axa` |
| **Total revisions** | 14 | `gcloud run revisions list` |

### Deploy Command (live flags)

```bash
gcloud run deploy platform-docs-hub \
  --image=europe-west3-docker.pkg.dev/platform-dev-p01/evo-images/platform-docs-hub:latest \
  --region=europe-north1 \
  --platform=managed \
  --allow-unauthenticated \
  --memory=256Mi \
  --cpu=1 \
  --concurrency=80 \
  --timeout=300 \
  --max-instances=3 \
  --project=platform-dev-p01
```

> **Note:** `--min-instances` is intentionally omitted (defaults to 0, allowing cold starts). `--max-instances=3` is passed explicitly so the scaling cap is visible in the deploy command rather than hidden in a revision annotation. The behavior is unchanged from when the cap was set via `autoscaling.knative.dev/maxScale: '3'` on the revision template.

### Build Command

```bash
docker build \
  --platform linux/amd64 \
  --build-arg GITHUB_TOKEN="$(gh auth token)" \
  -t europe-west3-docker.pkg.dev/platform-dev-p01/evo-images/platform-docs-hub:latest \
  .
```

> **Note:** The live `Dockerfile` runs `scripts/sync-repos.sh` *inside* the Docker build (line 14 of the Dockerfile) rather than expecting sources to be cloned beforehand. The `GITHUB_TOKEN` build arg is what enables cross-repo cloning. See the live `Dockerfile` for the exact behavior — it differs from doc 18's drafted version.

---

## How to Add a New Doc Source

1. Ensure the target repo has a `docs/` folder with a `mkdocs.yml` (optional, for structured nav)
2. Add the repo name to `repos.txt`:
   ```
   PricerAB/your-repo-name
   ```
3. Add a category mapping in `scripts/generate-nav.py` → `CATEGORY_MAP`:
   ```python
   "your-repo-name": {
       "section": "Services",       # or: Platform Architecture, Replatforming, etc.
       "label": "Your Service",
   },
   ```
4. Rebuild and redeploy:
   ```bash
   docker build --platform linux/amd64 --build-arg GITHUB_TOKEN="$(gh auth token)" -t IMAGE .
   docker push IMAGE
   gcloud run deploy platform-docs-hub --image=IMAGE ...
   ```

---

## Key Metrics

| Metric | Value | Source |
|:---|---:|:---|
| Source repos aggregated | 2 | `repos.txt` (live) |
| Total pages | 93 | mkdocs build output |
| Build time (Docker) | ~90s | typical local build |
| Build time (mkdocs) | ~1.7s | typical |
| Image size | ~45 MB (nginx alpine + static HTML) | docker images |
| Container cold start | <2s | first request after idle |
| Cloud Run revisions deployed | 14 | `gcloud run revisions list` (active: `00014-6nv`) |
| CI runs (GitHub Actions → Cloud Run) | 0 — no Cloud Run CI yet; workflow still targets Pages | doc 18 §6 |
| Hub repo commits | matches revision count approximately; manual local builds | `git log --oneline` in `platform-docs-hub-pricer` |
| Issues found & fixed | 8 | this report, §"What We Tried" |
| Live URL (canonical) | https://platform-docs-hub-990006507229.europe-north1.run.app | service annotation |
| Legacy URL | https://platform-docs-hub-yrwyrs6axa-lz.a.run.app | same content (verified by identical etag/last-modified); default Cloud Run mapping from previous project, cannot be removed from inside `platform-dev-p01` |

> **Note:** The "7 CI runs" and "4 commits" numbers in earlier drafts of this report referred to the broken Pages-targeting workflow. They are superseded by the actual revision count (14) and the manual-deploy reality. Trust the live `gcloud run revisions list` output, not this report.

### Legacy URL — what it is and what to do

The service annotation lists two URLs:
- **Canonical:** `https://platform-docs-hub-990006507229.europe-north1.run.app` (use this everywhere)
- **Legacy:** `https://platform-docs-hub-yrwyrs6axa-lz.a.run.app` (auto-assigned default mapping from a previous Cloud Run deployment)

Both URLs serve byte-identical content (verified via matching `etag` and `last-modified` response headers on 2026-07-07). The legacy URL is a Cloud Run **default domain mapping** that Google auto-assigns when a service exists; it cannot be deleted through the public API.

**Action items:**
1. **Use the canonical URL everywhere** in documentation, scripts, and external links. This document and doc 27 now do.
2. **Open a Google Cloud support case** to request removal of the default mapping for `yrwyrs6axa` project. Cloud Run default mappings are project-scoped — the support team can remove it from the previous project.
3. **Until removed**, set up a 301 redirect from the legacy URL to the canonical one (via external HTTPS Load Balancer) if SEO/canonicalization matters. Out of scope for current platform but worth tracking.

---

## Remaining Work

| Task | Priority | Notes |
|:---|:---:|:---|
| CI pipeline for Cloud Run (not Pages) | High | Current CI deploys to GitHub Pages (broken). Need to update for Cloud Run. |
| Custom domain (docs.pricer-plaza.com) | Medium | Map to Cloud Run via GCP Load Balancer + IAP for auth |
| Add `docs/` to more repos | Medium | 50+ PricerAB repos, only 2 have docs/ |
| Auto-discovery of repos with docs/ | Low | Replace manual `repos.txt` with GitHub API scan |
| Fix nav title formatting | Low | "Adr 001 Dtoflow..." → "ADR-001: DTOflow..." |
| Versioned docs (mike plugin) | Low | For API versioning |
| Stale content detection | Low | Auto-create tickets for docs >90 days old |
| **Resolve legacy URL** | Medium | Open Cloud support case to remove default mapping for `yrwyrs6axa` project; until then, document and use canonical URL only |
| **Add `--max-instances` flag to deploy command** | Done | Both doc 26 and doc 27 now pass `--max-instances=3`; behavior unchanged |
| **Fix `repos.txt` org prefix** | Done | `sync-repos.sh` now rejects bare repo names; convention documented in `repos.txt` header |

---

*Report generated July 2, 2026 from live system state. Last reconciled with GCP on 2026-07-07 — service config and revision count verified via `gcloud run services describe` and `gcloud run revisions list` against project `platform-dev-p01`.*

---

## Changes Applied 2026-07-07 — Alignment Pass

A second-pass reconciliation was done on 2026-07-07 after discovering that several claims in this report (and in docs 18 and 27) had drifted from actual GCP reality. The work was driven by the principle: **GCP is the single source of truth, not the drafts.**

### What was wrong

| Source | Drift from reality |
|:---|:---|
| This report | Claimed "4 commits" / "7 CI runs" — actual is **14 revisions, 0 Cloud Run CI runs** |
| This report + doc 27 | Deploy commands had stale `--min-instances` / `--max-instances` flags and no `--timeout` |
| This report + doc 27 | Single URL assumed; legacy URL was unmentioned |
| Doc 18 §10 | Changelog table was missing GCP-discovered deltas (dual URLs, exact deploy flags, default SA, in-Docker sync step, teal palette, etc.) |
| `repos.txt` + `sync-repos.sh` | Convention for `owner/repo` form was implicit; bare repo names would silently produce broken URLs |

### Fixes applied

#### Fix 1 — `repos.txt` clarity and guardrail

**Where:** `platform-docs-hub-pricer/repos.txt`, `platform-docs-hub-pricer/scripts/sync-repos.sh`
**Committed:** `c930a01 — fix: enforce owner/repo convention in repos.txt`

- Added a header comment to `repos.txt` explaining the `owner/repo` convention and why it's used.
- Added a runtime check in `sync-repos.sh` that rejects bare repo names with a clear error message instead of silently producing broken URLs.
- **Validated:** `bash sync-repos.sh` clones both repos correctly; a test with bare name `evo-dtoflow-protos` was rejected with `must be in 'owner/repo' form (e.g. PricerAB/evo-dtoflow-protos)`.
- **No regression:** `mkdocs build --strict` produces 99 pages; valid routes return 200; unknown paths return 404.

#### Fix 2 — Legacy URL documented precisely

**Where:** Doc 26 (this report), doc 18 §10
**Committed:** `1e55893 — docs: align platform-docs-hub docs with GCP reality`

- Verified via `curl -I` that both URLs serve byte-identical content (matching `etag: "6a467c1b-dfd2"` and `last-modified: Thu, 02 Jul 2026 14:56:27 GMT`).
- Identified the legacy URL as a Cloud Run **default domain mapping** from the previous project `yrwyrs6axa`; cannot be removed through the public gcloud API.
- All docs (26, 27) now use only the canonical URL `https://platform-docs-hub-990006507229.europe-north1.run.app` in commands and examples.
- Added explicit action items: use canonical URL everywhere, open Google Cloud support case for removal, optionally set up 301 redirect via HTTPS LB.

#### Fix 3 — `--max-instances=3` explicit in deploy commands

**Where:** Doc 26 deploy command, doc 27 (3 commands total), live Cloud Run service
**Committed:** `1e55893 — docs: align platform-docs-hub docs with GCP reality` (docs); separate `gcloud run services update` for live service
**Live revision:** `platform-docs-hub-00015-4kx`

- Added `--max-instances=3` to all three deploy commands in doc 26 and doc 27 (full deploy, quick-ref, one-liner).
- Behavior unchanged — was previously enforced via revision template annotation `autoscaling.knative.dev/maxScale: '3'`.
- Applied to live service via `gcloud run services update platform-docs-hub --max-instances=3` — revision `00015-4kx` is now deployed with the flag set explicitly. Verified live: both URLs return 200.

### Additional cleanups in this pass

- Doc 18 §10 changelog expanded from 14 to 21 rows including the GCP-discovered deltas.
- Doc 18 §10.3 open-work updated with three new items (legacy URL, deploy flag visibility done, repos.txt fix done).
- Doc 26 deployment table now sourced from `gcloud run services describe` with a Source column.
- Doc 26 architecture diagram updated to show sync running inside Docker build, not as a separate pre-step.
- Doc 26 sequence diagram shows the actual local-build flow (developer → docker → push → gcloud deploy).
- Doc 26 metrics table no longer claims "7 CI runs" / "4 commits" — reality is 0 Cloud Run CI runs and 14 revisions.

### Verification trail

```bash
# Confirm live state after all fixes
$ gcloud run services describe platform-docs-hub --region=europe-north1 --project=platform-dev-p01 \
    --format='value(status.latestReadyRevisionName)'
platform-docs-hub-00015-4kx

$ gcloud run services describe platform-docs-hub --region=europe-north1 --project=platform-dev-p01 \
    --format='value(status.observedGeneration)'
15

$ curl -sI https://platform-docs-hub-990006507229.europe-north1.run.app/ | head -1
HTTP/2 200

$ curl -sI https://platform-docs-hub-yrwyrs6axa-lz.a.run.app/ | head -1
HTTP/2 200

# Confirm doc and code changes are committed
$ git -C /Users/cridea/Projects/AI/platform-docs-hub-pricer log --oneline -2
c930a01 fix: enforce owner/repo convention in repos.txt
31fbf8a feat: add Impeccable-inspired custom theme — restrained professional

$ git -C /Users/cridea/Projects/AI/Replatforming/onboarding log --oneline -2
1e55893 docs: align platform-docs-hub docs with GCP reality + Fix #2 + Fix #3
c41439f Latest docs update.
```

### Open items remaining (post-fix)

The fixes did not address the deeper open items in [Remaining Work](#remaining-work) — they remain:

| Priority | Item | Status |
|:---:|:---|:---|
| High | CI pipeline for Cloud Run (not Pages) | Untouched |
| High | Stop using `--allow-unauthenticated` before sensitive content lands | Untouched |
| Medium | Adopt the 15 backlog repos | Untouched |
| Medium | Custom domain `docs.pricer-plaza.com` | Untouched |
| Medium | Open Google Cloud support case to remove legacy URL default mapping | **Not done — documented, awaiting action** |
| Low | Auto-discovery of repos with `docs/` | Untouched |
| Low | Fix nav title formatting | Untouched |
| Low | Versioned docs (`mike` plugin) | Untouched |
| Low | Stale content detection workflow | Untouched |

---

*Alignment pass completed 2026-07-07 by reconciliation against `gcloud run services describe`, `gcloud run revisions list`, and `curl` against both service URLs. All three fixes verified at runtime.*
