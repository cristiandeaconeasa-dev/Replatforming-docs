# Replatforming Onboarding Docs — AGENTS.md

> Read by Codebuff, Claude Code, Gemini CLI, and other AI agents at session start.
> Keep under 300 lines. Split into referenced files if it grows.

## Credentials & API Access

Tokens live on disk — never ask the user for them:

```
~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json
```

**Before querying any Atlassian/GitHub/GCP API**, read `../codebuff-mcp-reference.md` for the exact curl/gcloud patterns. Key facts:

| Service | Auth | Base URL | Token Env |
|---------|------|----------|-----------|
| Jira | Basic auth (`email:api_token`, base64) | `pricer-org.atlassian.net/rest/api/3/` | `JIRA_TOKEN` in cline settings |
| Confluence | Same as Jira | `pricer-org.atlassian.net/wiki/rest/api/` | Same token |
| GitHub | Bearer token | `api.github.com` | `GITHUB_PERSONAL_ACCESS_TOKEN` in cline settings |
| GCP | `gcloud` ADC (already logged in) | — | Project: `platform-dev-p01` |

Use the `basher` tool for all API calls. Tokens are in-memory only, per-command.

## Project: Replatforming (Phase 0 → Phase 2)

**Repo:** `https://github.com/cristiandeaconeasa-dev/Replatforming-docs.git`
**Local path:** `/Users/cridea/Projects/AI/Replatforming/onboarding`

### Document Index

| # | Document | Purpose |
|---|----------|---------|
| 01 | `01-systems-architecture.md` | Legacy & target system landscape |
| 02 | `02-tenant-model.md` | PricerServer → cloud tenant model |
| 03 | `03-replatforming-deep-dive.md` | Full replatforming technical deep-dive |
| 04 | `04-target-architecture.md` | Cloud-native target design |
| 05 | `05-core-concepts-deep-dive.md` | DTOs, CQS, evaluators, LFS |
| 06 | `06-agentic-development-workflow.md` | AI-assisted dev workflow |
| 07 | `07-m2m-token-manager-deep-dive.md` | Machine-to-machine auth |
| 08 | `08-dtoflow-deep-dive.md` | DTOflow event-driven architecture |
| 09 | `09-demo-traffic-tracing-template.md` | Shadow Mode tracing template |
| 10 | `10-item-pipeline-deep-dive.md` | Item data pipeline |
| 11 | `11-link-pipeline-deep-dive.md` | Link data pipeline |
| 12 | `12-rendering-pipeline-deep-dive.md` | Rendering pipeline |
| 13 | `13-core-data-flows.md` | End-to-end data flows |
| 14 | `14-tenant-migration.md` | Tenant migration strategy |
| 15 | `15-overall-status-v2.md` | **Primary status doc** — Framework C (Workstream→Capability) |
| 16 | `16-docs-github-strategy.md` | Docs GitHub strategy |
| 17 | `17-phase-1-plan.md` | Phase 1 activity planning |
| 18 | `18-docs-github-implementation.md` | Docs GitHub implementation |
| 19 | `19-dimension-frameworks.md` | Three alternative categorization frameworks |
| — | `README.md` | Onboarding guide & doc index |
| — | `weekly-status-w26-2026.md` | Weekly status report |

### Categorization Framework (Active)

The project uses **Framework C**: a two-level **Workstream → Capability** hierarchy.

**Workstreams (when it ships):**
- **W1: Foundation Enablers** (7 epics) — Spanner, Pub/Sub, CQS, routing, PSC
- **W2: Phase 0 — Shadow Mode** (11 epics) — parallel cloud pipeline validation
- **W3: Phase 1 — Consumer API Cutover** (10 epics) — per-API-path migration
- **W4: Phase 1 — Production Operations** (11 epics) — tenant onboarding, ops readiness
- **W5: Phase 2 — Feature Parity & Scale** (19 epics) — full migration

**Capabilities (what it does):**
- **C1: Distributed Data & Routing Fabric** (11 epics)
- **C2: Item Data Management** (8 epics)
- **C3: Linking & Parallel Rendering** (10 epics)
- **C4: Edge Bridging & Execution** (17 epics)
- **C5: Tenant Isolation & Ops Lifecycle** (12 epics)

Full mapping in `15-overall-status-v2.md` §4 and `19-dimension-frameworks.md` §4.

### Jira Project

- **Project key:** `PLT`
- **Replatforming epics:** ~42 labeled, search with `project = PLT AND issuetype = Epic AND labels = replatforming`
- **Key assignees:** Bart De Boer, Johan Ekman, Sreekanth Singapuram Uppara, Daniel Pettersson, Cristian Deaconeasa, Saikiran Katta

### Confluence

- **Space:** PS (`pricer-org.atlassian.net/wiki/spaces/PS/`)
- **Key pages:** Phase 1 Activity Planning (`/wiki/x/LAD8XwI`, page ID `10198908937`)

## Conventions

- **Status indicators:** ✅ Closed/Done · 🟢 In Progress/Ready · 🟡 Selected/Test · 🔵 Backlog · ⚪ Scope-out
- **Doc format:** All onboarding docs are Markdown with Mermaid diagrams where useful
- **Validation:** Status data validated against live Jira API as of 2026-06-30 unless otherwise noted
- **Git:** Commit and push to `origin main` after any doc changes. Use `git add -A && git commit -m "..." && git push`
- **When updating status:** Always pull fresh Jira data via the REST API before updating epics (see `codebuff-mcp-reference.md`)
