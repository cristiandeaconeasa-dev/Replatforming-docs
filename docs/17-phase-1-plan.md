# 17 — Phase 1 Plan: First Real Tenant on DTOflow

> **Scope:** A plan for Phase 1 of the Replatforming initiative — organized around the six activity areas defined by the Replatforming architect in the [Phase 1 Activity Planning](https://pricer-org.atlassian.net/wiki/x/LAD8XwI) Confluence page (PS space, page ID 10198908937). This doc integrates the architect's scope framework with detailed gap analysis, proposed solutions, migration sequencing, and risk assessment.
>
> **Audience:** Replatforming engineering lead and team. This is a *planning document* — it identifies what needs to happen and why. Solutions proposed for gaps are realistic starting points to be validated, not final designs.
>
> **Validated:** 2026-06-30 — against live Jira (`project = PLT`, all critical epics), GCP `platform-dev-p01`, the onboarding doc set (docs 01–16), the Confluence Architecture Pipeline Status page, and the architect's Phase 1 Activity Planning Confluence page.
>
> **Companion docs:** [03 — Replatforming Deep Dive](03-replatforming-deep-dive.md) (epic backlog, Shadow Mode, phase model) · [04 — Target Architecture](04-target-architecture.md) (topology, hybrid boundary) · [13 — Core Data Flows](13-core-data-flows.md) (event-driven flows) · [14 — Tenant Migration](14-tenant-migration.md) (switch procedure) · [15 — Overall Status](15-overall-status.md) (Phase → Milestone → Increment → Epic hierarchy) · [19 — Delivery Framework](19-dimension-frameworks.md).

---

## 1. Executive Summary

**Phase 1 is the first time a real, revenue-generating customer runs on the DTOflow cloud platform.** It follows Phase 0 (internal Shadow Mode validation) and precedes Phase 2 (full feature parity, many tenants).

```mermaid
---
config:
    layout: elk
---
flowchart LR
    P0["Phase 0<br/>Internal tenants<br/>Shadow Mode<br/>Zero label risk"] --> P1["Phase 1<br/>First real tenant<br/>Feature delivery + ops<br/>Controlled risk"]
    P1 --> P2["Phase 2<br/>Scale<br/>Full feature parity<br/>All tenants"]

    P0 --- P0D["Prove the pipeline works"]
    P1 --- P1D["Prove it works for a customer"]
    P2 --- P2D["Prove it works at scale"]

    style P0 fill:#e8f5e9,stroke:#2e7d32,color:#000
    style P1 fill:#fff3e0,stroke:#f57c00,color:#000
    style P2 fill:#ffebee,stroke:#c62828,color:#000
```

**The current state (2026-06-30):** The DTOflow foundation is solid — 21 Cloud Run services deployed, link and rendering pipelines live, transmission operational. But Phase 1 is **gated on two blocked epics** (PLT-2651 item property validation, PLT-2378 Item Patch APIs — both Blocked and Unassigned) and **one unstarted mechanism** (PLT-2101 per-API-path routing). The first tenant hasn't been formally selected (PLT-2601 in Backlog).

**This document answers:** What exactly constitutes "Phase 1 done," organised around six activity areas defined by the architect — DTOflow Platform Maturity, Feature Delivery, Security & Tenant Isolation, Operational Readiness, Validation & Go-Live Confidence, and Migration of PROD Tenants.

---

## 2. What Phase 1 Is — and Isn't

### Phase 1 definition

| Dimension | Phase 1 |
|-----------|---------|
| **Goal** | One real, revenue-generating tenant live on the DTOflow cloud path with the feature set required for that tenant |
| **Risk posture** | Controlled — the tenant is carefully selected, features are scoped to essentials, and the switch procedure (doc 14) is rehearsed on Phase 0 first |
| **Delivery model** | Per-API-path migration. Not a big bang. The tenant's R3Server keeps running (thin edge) for transmission, flash, and store map |
| **Tenants** | byPricer → one small customer (e.g., Landwaart AGF) → one medium customer (e.g., spar-be) |
| **What "done" looks like** | The tenant's item updates, link changes, and rendering flow entirely through DTOflow. R3Server does transmission only. Monitoring, switch runbook, and ops are in place. |

### What Phase 1 is NOT

- **Not** full feature parity with today's R3Server (that's Phase 2)
- **Not** a multi-tenant roll-out (one tenant at a time, validated between)
- **Not** a rewrite of the on-prem transmission or basestation layer (those stay on R3Server)
- **Not** an all-or-nothing switch — the per-API-path routing means individual APIs can be flipped and rolled back independently

---

## 3. Phase 0 Prerequisites — What Must Close Before Phase 1 Begins

Phase 1 cannot start until Phase 0 crosses these gates.

### 3.1 The Three Critical Unblockers

| Epic | What It Is | Current | Action Needed |
|------|-----------|---------|---------------|
| **PLT-2651** | Item property validation in item-registry | 🔴 **Blocked / Unassigned** | Assign owner, implement JSON schema validation or CEL-based rules in `item-registry`. This is the **single clearest gate** on item-driven migration — 4 of 5 item pipeline services are built but can't validate properties end-to-end. |
| **PLT-2378** | Item Patch APIs — Core | 🔴 **Blocked / Unassigned** | Assign owner. This gates Plaza Mobile (`PATCH/DELETE /api/public/core/v1/items`) and Central-Manager (`PATCH/DELETE /api/public/multi-store/v2/multi-store-requests/items[.csv]`). Both consumer paths are blocked without it. |
| **PLT-2274** | SIC Support | 🔴 **Blocked** (Daniel Pettersson) | Depends on PLT-2378. SIC lets items be found by the customer's own Store Item Code. If the Phase 1 tenant's ERP identifies items by SIC, this is mandatory for item lookup. **Needs scoping** — some tenants may use Pricer item IDs exclusively; verify during tenant selection (PLT-2601). |

> **Why these are the highest-priority actions in the entire Replatforming program right now:** Without them, no real tenant item data flows through DTOflow. The link and render pipelines already work — but they have nothing to process if items can't be validated and written. SIC is tenant-dependent but must be assessed before committing to a Phase 1 target. **Assigning owners to PLT-2651 and PLT-2378 is the single most leveraged action a lead can take this week.**
>
> These prerequisites close **M1 (Platform Foundation)** and **M2 (Shadow Mode Validation)** in [doc 15](15-overall-status.md). Once M2 is complete, Phase 1 work on M3 and M4 begins.

### 3.2 Shadow Mode Gate (PLT-2354)

| Prerequisite | Status | Owner | Notes |
|-------------|--------|-------|-------|
| storeitemvalues export data pipe (PLT-2483) | 🟡 **Ready for Deploy** | Johan Ekman | The R3Server → DTOflow item data pipe |
| CQS client in R3Server (PLT-1870) | 🟡 **Test** | Daniel Pettersson | R3Server can receive cloud work |
| Consume-ignore-linked mode (PLT-2497) | ✅ Done | — | R3Server can shadow-consume without affecting labels |
| 5 export sub-tasks (PLT-2494, 2495, 2492, 2488, 2714) | 🔵 Defined, unassigned | **Unassigned** | ECC params/images/fonts export, ESL status export, itemproperties export |
| Replatforming-Dev tenant shadow run | Not started | — | 24+ hour run with 100% rendered-image parity |
| Evo-Se shadow run | Not started | — | Dev team's own tenant validated |
| Application-Stage shadow run | Not started | — | Product validation tenant |

**Gate criteria:** All 5 export sub-tasks assigned and completed. Store config (`store` DTO from PLT-2572/2575; runtime config via PLT-2353 or covered by export sub-tasks — assess overlap). Then `Replatforming-Dev` runs Shadow Mode for 24+ hours with 100% image parity → `Evo-Se` and `Application-Stage` validated.

### 3.3 Foundation & Routing Prerequisites

| Prerequisite | Status | Owner | Notes |
|-------------|--------|-------|-------|
| DTOflow PROD-ready (PLT-2118) | 🟡 Test | Bart De Boer | Formal production certification of the foundation |
| CQS core (PLT-169) | 🟡 In Progress | Johan Ekman | Must be deployed and stable |
| Services own CQS queues (PLT-2792) | 🟡 In Progress | Bart De Boer | Each service manages its own queue — prevents fan-out congestion |
| Link v1 DTO refactor (PLT-2484) | 🟡 In Progress | Bart De Boer | Separates ECC single case from link v1; needed for link pipeline correctness |
| DTOflow broader accessibility / PSC (PLT-2336) | 🟡 In Progress | Sreekanth S.U. | Private Service Connect for secure cloud access |
| **Per-API-path routing (PLT-2101)** | 🔵 Selected for Dev | Saikiran Katta (on vacation) | **Reassign immediately.** This is the mechanism that makes migration incremental. Without it, migration is all-or-nothing per store. |
| Tenant isolation verification (PLT-2578) | 🔴 Backlog | Unassigned | Must be proven before any real tenant data enters the platform |
| PS ↔ CQS/DTOflow design (PLT-2478) | 🟡 In Progress | Sreekanth S.U. | Integration design for how pricer-server talks to CQS |
| Config export to DTOflow (PLT-2353) | 🔴 Backlog | Unassigned | Pricer Server configuration available in cloud. This is distinct from store onboarding (PLT-2572) — config export pushes R3Server runtime configuration (not just store metadata) to DTOflow. May be partially covered by Shadow Mode sub-tasks (PLT-2488 itemproperties export); assess overlap during sprint planning. |

### 3.4 Organizational Prerequisites

| Item | Action |
|------|--------|
| **Review bottleneck** | 6+ items waiting for Johan Ekman's review. Distribute review load across the team. |
| **Saikiran vacation** | PLT-2101 (API routing) not started. Complete hand-over planning or reassign. |
| **Bus factor** | Bart De Boer, Johan Ekman, Daniel Pettersson, and Sreekanth S.U. own most critical epics. Spread ownership. |
| **Shadow Mode sub-tasks** | 5 export tasks (PLT-2494/2495/2492/2488/2714) need owners assigned before next sprint. |

---

## 4. Phase 1 Activity Areas

> **Source:** These six areas and their acceptance criteria are defined by the Replatforming architect in the [Phase 1 Activity Planning](https://pricer-org.atlassian.net/wiki/x/LAD8XwI) Confluence page (2026-06-30). The gap analysis, proposed solutions, and migration sequencing in subsequent sections are derived from the onboarding doc set and live Jira/GCP data.

```mermaid
---
config:
    layout: elk
---
flowchart TB
    A1["1. DTOflow Platform Maturity<br/>Hardening core infrastructure"]
    A2["2. Feature Delivery<br/>API parity with on-prem"]
    A3["3. Security & Tenant Isolation<br/>M2M, cross-tenant boundaries"]
    A4["4. Operational Readiness<br/>Monitoring, DR, runbooks"]
    A5["5. Validation & Go-Live<br/>Load testing, integration tests"]
    A6["6. Migration of PROD Tenants<br/>byPricer → small → medium"]

    A1 --> A2
    A1 --> A3
    A2 --> A5
    A3 --> A4
    A4 --> A5
    A5 --> A6

    style A1 fill:#e3f2fd,stroke:#1565c0,color:#000
    style A2 fill:#e8f5e9,stroke:#2e7d32,color:#000
    style A3 fill:#fce4ec,stroke:#c62828,color:#000
    style A4 fill:#fff3e0,stroke:#f57c00,color:#000
    style A5 fill:#f3e5f5,stroke:#7b1fa2,color:#000
    style A6 fill:#e8f5e9,stroke:#2e7d32,color:#000
```

### Area 1: DTOflow Platform Maturity

**Focus:** Hardening core shared data infrastructure — the Spanner DTO store, CQS change queue, and LFS binary store — so they are production-grade for tenant workloads.

| Activity | Epic | Acceptance Criteria |
|----------|------|---------------------|
| LFS overwrite protection | PLT-2658 | 🟡 Selected for Development · Unassigned | GCS API usage aligned; overwrites prevented for published binaries |
| Auto-scaling background services | PLT-2369 | Cloud Run instances scale based on CQS queue depth, not just request rate |
| SLA & trackingId support | PLT-171 | Priority timestamps on all CQS events; interactive operations beat bulk imports |
| Status reporting API | PLT-2444 | Public API for item update metrics — how many processed, at what latency |

**Gap analysis:** PLT-171 (SLA/trackingId) is in Backlog, Unassigned. PLT-2369 (auto-scaling) is in Backlog — Cloud Run's built-in scaling may suffice for Phase 1 volumes, but CQS-driven proactive scaling should be validated during load testing (Area 5). PLT-2658 (LFS overwrite protection) is 🟡 Selected for Development, Unassigned — needs an owner. PLT-2444 (status reporting) is in Backlog.

### Area 2: Feature Delivery

**Focus:** API capabilities for functional parity with on-prem Pricer Server. The architect identifies six feature epics needed for Phase 1.

| Activity | Epic | Acceptance Criteria |
|----------|------|---------------------|
| Unified Linking API | PLT-2360 | Single API surface for Designer and ECC link operations |
| Segment Label Support | PLT-2361 | 7-segment calculator-style labels supported in render pipeline |
| Timed Item Updates | PLT-2350 | Scheduled future price changes; items update at specified times |
| Flash Promotion Triggers | PLT-2356 | Real-time sub-second flash promotions *triggered* from cloud; actual sub-second transmission still executes on R3Server edge. The cloud originates the flash event (e.g., a price change triggers immediate flash) — the edge handles the latency-sensitive execution. |
| Auto Unlink Support | PLT-2363 | Audited auto-unlink events when items are deleted |
| Advanced Ingest/Link Status | PLT-2352 | `requestId`-based status tracking for ingest and link operations |

> **Note on scope breadth:** The architect's view includes several features (PLT-2350 timed updates, PLT-2361 segment labels, PLT-2360 unified linking, PLT-2363 auto-unlink, PLT-2356 flash APIs, PLT-2352 advanced status) that would be considered Phase 2 in a "basic features for a simple tenant" scoping approach. The first Phase 1 tenant (byPricer, a demo tenant) may not need all of these. **Treat this as the full Phase 1 backlog** — the actual subset activated per tenant depends on the tenant's feature profile, assessed during tenant selection (PLT-2601 in Area 6).
>
> **Epics not in the architect's 6 areas:** The following epics from the wider Replatforming backlog are not explicitly included in the architect's Phase 1 scope. They are either tenant-dependent (assess during PLT-2601) or deferred to Phase 2:
>
> | Epic | Status | Why Not in Phase 1 Scope |
> |------|--------|--------------------------|
> | PLT-2357 — Linked Item APIs (Items) | 🟡 Selected · Unassigned | Tenant-dependent. Does Plaza Mobile need to list items? Assess during tenant profiling. |
> | PLT-2358 — Linked Item APIs (Devices) | 🟡 Selected · Unassigned | Tenant-dependent. Does Central-Manager need to list labels? May be covered by monitoring dashboards. |
> | PLT-2355 — Label Status APIs | 🟡 Selected · Bart De Boer | Tenant-dependent. Consumer-facing label health queries. May be covered by ESL status export (PLT-2492) + monitoring. |
> | PLT-2351 — Item Ingest Status (Extended) | 🔵 Backlog · Unassigned | Deferred to Phase 2. Basic status via trackingId (PLT-2352) is sufficient for Phase 1. |
> | PLT-2362 — GeoPos Support | 🔵 Backlog | Deferred to Phase 2. Label positions not needed for basic operations. |
> | PLT-2440 — Webhook Events | 🔵 Backlog | Deferred to Phase 2. External system notifications. |
> | PLT-2428 — Subscription/License System | 🔵 Backlog | Deferred to Phase 2. Entitlement enforcement. |

**Gap analysis:** All six epics in this area are currently in Backlog or unassigned. They represent significant implementation effort. Prioritize based on the first tenant's feature profile:
- **byPricer (demo):** Minimally needs item ingest/write path (PLT-2651, PLT-2378). Link creation/deletion already works. Timed updates and segment labels can wait.
- **Landwaart (small retailer):** May need timed updates if they use scheduled price changes. Unlikely to need segment labels.
- **Spar-be (medium retailer, ~13K ESLs):** Likely needs the full feature set.

### Area 3: Security & Tenant Isolation

**Focus:** Strict isolation of tenant data with M2M credential enforcement. Non-negotiable before any real customer data enters the platform.

| Activity | Epic | Acceptance Criteria |
|----------|------|---------------------|
| Tenant Security Isolation Validation | PLT-2578 | Automated validation of cross-tenant isolation; no data leaks between tenants |
| Write Protection | PLT-170 | Explicit M2M write permissions per tenant; separate read permissions; security sign-off |

**Gap analysis:** PLT-2578 is in Backlog, Unassigned — **this is non-negotiable.** Must be proven before any real tenant data enters the platform. Build a test suite that provisions two tenants, writes data for both, then attempts cross-tenant reads through every Cloud Run service. Add a Spanner IAM condition or row-level check: every query must include `t/{tenantId}` prefix. Add an integration test that runs in CI on every PR.

PLT-170 (Write Protection / Auth0 JWT) provides fine-grained write authorization on top of the tenant isolation boundary. The architect includes it in Phase 1 scope. Currently in Backlog, Unassigned.

### Area 4: Operational Readiness

**Focus:** Production observability and recoverability — what separates "it works in dev" from "it works in production."

| Activity | Epic | Acceptance Criteria |
|----------|------|---------------------|
| Monitoring & Alerting | PLT-2579 | Comprehensive on-call dashboards; automated alerting with runbooks; CQS queue depth, Spanner latency, Cloud Run error rates, transmission success rates |
| DR & Backup | PLT-2580 | RPO < 1hr / RTO < 4hr; verified DR drills; Spanner scheduled backups with documented restore procedure |
| Cutover & Rollback Runbook | PLT-2599 | Per-store cutover/rollback runbooks; the 7-step switch procedure (doc 14) tested and rehearsed |
| Studio Services Readiness | PLT-2600 | Determination of `studio-design-library`, `studio-scenario-library`, `studio-renderer` production readiness |

**Gap analysis:** All four epics are in Backlog. You cannot put a real customer on the platform without these. Start with monitoring (PLT-2579) — it can begin immediately and doesn't depend on any blocker. For DR (PLT-2580), Phase 1 scope is Spanner scheduled backups + documented restore procedure; full multi-region failover is Phase 2.

### Area 5: Validation & Go-Live Confidence

**Focus:** Performance and load testing at production volume to prove the system handles real tenant workloads.

| Activity | Epic | Acceptance Criteria |
|----------|------|---------------------|
| Production Scale Testing | PLT-2576 | Successful load tests at 2–3× peak tenant volume; p99 latency parity with R3Server under stress; automated scaling performance validated |
| TA2 Integration Testing | PLT-2430 | All Phase 1 APIs passing TA2 integration tests; end-to-end item-update → render → transmission chain verified |

**Gap analysis:** PLT-2576 in Backlog. Use the tenant's historical update volume from R3Server logs as the baseline. Replay at 2× peak for Landwaart, 3× peak for Spar-be. PLT-2430 in Backlog — integration tests exercise the full chain and must pass before any tenant switch.

### Area 6: Migration of PROD Tenants

**Focus:** Live migration of three tenants of different sizes, sequenced by risk profile.

| Order | Tenant | Type | ESLs | Rationale |
|-------|--------|------|------|-----------|
| **1st** | **byPricer** | Demo / Pricer-internal | Small | Zero revenue risk. Exercises the exact switch runbook without business impact. |
| **2nd** | **Small customer** (e.g., Landwaart AGF) | Real — produce retailer | 2 stores, sub-1000 labels | First real customer. Simple stack. Low ESL count limits blast radius. |
| **3rd** | **Medium customer** (e.g., spar-be) | Real — large format | O(10) stores, 10k+ labels | Scale validation bridge to Phase 2. Do not migrate until the small customer runs flawlessly for 2 weeks. |

**Acceptance criteria:**
- byPricer migrated — demo tenant fully on DTOflow cloud path
- One small customer (2 stores, sub-1000 labels) migrated
- One medium customer (O(10) stores, 10k+ labels) migrated

---

## 5. Phase 1 Feature Summary — What the First Tenant Gets

Based on the architect's six areas, mapped to M3 (First Tenant Go-Live) and M4 (Production Hardening), with `[C1]`–`[C5]` capability tags:

| Feature | Cloud Path | Phase 1 Area | Jira Status |
|---------|-----------|-------------|-------------|
| **Item price change → label update** | `item-registry-api` → Spanner → CQS → evaluator + renderer → merger → transmission → R3Server → ESL | Area 1, 2 | 🔴 Gated on PLT-2651 + PLT-2378 |
| **Item deletion → label clear** | `item-registry-api` → tombstone → evaluator → unlink → render blank → transmission | Area 2 | 🔴 Not yet built |
| **Link creation → label design** | `link-registry` → link.v2 → evaluator → renderer → merger → transmission | Area 2 | 🟢 Already live |
| **Link deletion → label revert** | `link-registry` → delete → evaluator → re-render → transmission | Area 2 | 🟢 Already live |
| **Design publication → mass re-render** | `studio-design-library` → design.v1 → renderer + evaluator → merger → transmission | Area 2 | 🟢 Already live |
| **Timed item updates** | `item-registry-api` → scheduled write → CQS → downstream | Area 2 | 🔵 Backlog (PLT-2350) |
| **Flash promotions** | Cloud-originated trigger → sub-second execution on R3Server edge | Area 2 | 🟡 Cloud trigger only; actual flash stays on R3Server edge |
| **Segment label support** | Evaluator + renderer support for 7-segment labels | Area 2 | 🔵 Backlog (PLT-2361) |
| **Tenant isolation (security)** | Cross-tenant read prevention; M2M write enforcement | Area 3 | 🔵 Backlog (PLT-2578, PLT-170) |
| **Monitoring & alerting** | CQS queue depth, Spanner latency, error rates dashboards | Area 4 | 🔵 Backlog (PLT-2579) |
| **DR & backup** | Spanner scheduled backups + restore procedure | Area 4 | 🔵 Backlog (PLT-2580) |
| **Cutover runbook** | 7-step switch procedure + rollback | Area 4 | 🔵 Backlog (PLT-2599) |
| **Load testing** | 2–3× peak volume replay | Area 5 | 🔵 Backlog (PLT-2576) |
| **Integration tests** | E2E item → render → transmission chain | Area 5 | 🔵 Backlog (PLT-2430) |
| **Auto-scaling** | CQS-driven proactive Cloud Run scaling | Area 1 | 🔵 Backlog (PLT-2369) |
| **Status reporting API** | Item update metrics API | Area 1 | 🔵 Backlog (PLT-2444) |

**What stays on R3Server (by design, never migrates):** Transmission engine, basestation control, flash (sub-second latency), display-page, store map/geo, local ESL status ACK handling.

---

## 6. End-to-End Data Flows — What Must Work for Phase 1

Three user-observable flows define the Phase 1 deliverable. Here's their current status and what's missing.

### Flow 1: Item Price Change → Label Update

```
ERP / Plaza Mobile → Apigee/ingress → item-registry-api
  → SP: write storeitemvalues (validated, tenanted)
  → PS: dtoflow-changes-storeitemvalues.v1
  → CQS fans out in parallel:
      ├── studio-link-evaluator: re-evaluate CEL rules → may write studiolink
      └── studio-renderer: render with current studiolink + new item values
  → eslimage → dtoflow-transmission → R3Server (thin) → Basestation → ESL
```

| Component | Status | Gap |
|-----------|--------|-----|
| item-registry-api accepts PATCH | 🔴 Gated on PLT-2378 | Item Patch APIs unbuilt |
| Item property validation | 🔴 Gated on PLT-2651 | No validation before Spanner write |
| storeitemvalues → evaluator + renderer | 🟢 Live | — |
| evaluator re-evaluates CEL rules | 🟢 Live | — |
| renderer produces studioeslimage | 🟢 Live | — |
| esl-image-merger → eslimage | 🟢 Live | — |
| dtoflow-transmission → R3Server | 🟢 Live | — |
| R3Server → ESL transmit | 🟢 Live (stays on edge) | — |

**What's needed to close this flow:** PLT-2651 + PLT-2378 (Area 1/2). SIC support (PLT-2274, Area 2 — Feature Delivery) may also be needed if the tenant uses Store Item Codes.

### Flow 2: Link Creation → Label Design

```
Studio/Designer → Apigee → link-registry
  → SP: write storeesl + link.v2
  → PS: dtoflow-changes-link.v2
  → CQS → studio-link-evaluator: resolve design, write studiolink
  → CQS → studio-renderer: render with design + item data
  → esl-image-merger → eslimage → transmission → R3Server → ESL
```

| Component | Status | Gap |
|-----------|--------|-----|
| Entire flow | 🟢 **Live** | **None.** This is the strongest proof point. Link creation/deletion flows end-to-end through DTOflow today. |

### Flow 3: Item Deletion → Label Clear

```
ERP / Plaza Mobile → Apigee/ingress → item-registry-api
  → SP: tombstone storeitemvalues (soft delete)
  → PS: dtoflow-changes-storeitemvalues.v1 (tombstone event)
  → CQS → studio-link-evaluator: detect tombstone, trigger unlink
  → CQS → studio-renderer: render blank/cleared label
  → eslimage → transmission → R3Server → ESL clears
```

| Component | Status | Gap |
|-----------|--------|-----|
| DELETE endpoint | 🔴 Gated on PLT-2378 | Same as Flow 1 |
| Tombstone logic in item-registry | 🔴 Not built | **Gap.** Need soft-delete (tombstone) on `storeitemvalues` so downstream services can react |
| Evaluator reacts to tombstone | 🔴 Not built | **Gap.** `studio-link-evaluator` must detect a tombstoned `storeitemvalues` and trigger unlink logic |
| Renderer produces blank label | 🔴 Not built | **Gap.** `studio-renderer` must render a default/blank template when the link is cleared |
| Transmission → ESL clear | 🟢 Live | The transmission path is the same regardless of image content |

**What's needed to close this flow:** PLT-2378 (DELETE endpoint) + tombstone logic in item-registry + evaluator tombstone handling + renderer blank-label support. Maps to Area 2 (Feature Delivery).

---

## 7. User Flows & Consumer Impact

### 7.1 Plaza Mobile (Store Associate App)

| API Surface | Today | Phase 1 | Impact |
|------------|-------|---------|--------|
| `GET/PATCH /api/.../items` | R3Server | **Cloud** (item-registry-api) | Faster for multi-store queries. Transparent to the user. |
| Item search | R3Server | **Cloud** (item-registry-api) | Spanner-backed search, cross-store capable. |
| Flash | R3Server | **R3Server** (unchanged) | Stays on edge for sub-second latency. No visible change. |
| Display-page switch | R3Server | **R3Server** (unchanged) | Stays on edge. No visible change. |
| Store map / geo | R3Server | **R3Server** (unchanged) | Stays on edge (physical layout). No visible change. |
| Link departments | R3Server → link-registry | **Cloud** (link-registry) | Already partially cloud-native. |

**Net impact:** The associate's daily workflow (flash, display-page, map) is unchanged. Item updates and searches become faster and cross-store capable. **No app update needed** — the routing change happens at the ingress layer.

### 7.2 Central-Manager (HQ Operations)

| API Surface | Today | Phase 1 | Impact |
|------------|-------|---------|--------|
| Multi-store item update | R3Server (per store) | **Cloud** (single call) | Dramatically faster. One API call instead of N store calls. |
| CSV item import | R3Server | **Cloud** (item-registry-api) | Bulk import through Spanner, horizontally scalable. |
| Store lifecycle | Central-Manager → R3Server | **Central-Manager → R3Server** (unchanged) | Store-Host management stays. No visible change. |

**Net impact:** Multi-store operations become significantly faster. CSV imports are no longer bottlenecked by per-store MySQL.

### 7.3 Store UI & Plaza Actions

| Client | Phase 1 | Impact |
|--------|---------|--------|
| Store UI | Already 100% cloud (EVO Store Service) | **Transparent.** No change. |
| Plaza Actions | Already 100% cloud (Apigee → actions services) | **Transparent.** No change. |

---

## 8. Gaps & Proposed Solutions

These are the identified gaps between current state and Phase 1 readiness, organised by the architect's six activity areas. Each includes a realistic starting-point solution — to be validated, not treated as final design.

### 8.1 Area 1 Gap: Item Pipeline Blocked (PLT-2651 + PLT-2378)

**What's missing:** Item property validation and Item Patch APIs are both Blocked and Unassigned. 4 of 5 item pipeline services are built; the last mile is unowned.

**Proposed solution:**
- **PLT-2651:** Implement a JSON schema validation layer in `item-registry`. Define allowed properties per tenant in `itemproperties` DTO. Reject writes with unknown or malformed properties before Spanner persistence. This is a well-scoped, single-developer task (estimated 1–2 sprints).
- **PLT-2378:** Wire up `PATCH/DELETE /api/public/core/v1/items[/{id}]` in `item-registry-api` to write `storeitemvalues` to Spanner. For Central-Manager, wire up `PATCH/DELETE /api/public/multi-store/v2/multi-store-requests/items[.csv]`. Depends on PLT-2651 completing first (validation must exist before accepting writes).

**Justification:** Without these two, Phase 1 cannot start. They are the highest-priority items in the program.

### 8.2 Area 1 Gap: Platform Hardening (PLT-171, PLT-2369, PLT-2658, PLT-2444)

**What's missing:** The architect identifies four platform maturity epics (SLA/trackingId, auto-scaling, LFS overwrite protection, status reporting). All are in Backlog.

**Proposed solution:**
- **PLT-171 (SLA/trackingId):** Priority timestamps on CQS events so interactive operations beat bulk imports. This is critical for production — without it, a bulk CSV upload could starve a store manager's single price change. Estimated 1 sprint.
- **PLT-2369 (auto-scaling):** For Phase 1, Cloud Run's built-in scaling may suffice. Validate this assumption during load testing (Area 5). If Cloud Run scaling proves insufficient, implement CQS-driven proactive scaling.
- **PLT-2658 (LFS overwrite protection):** Align LFS GCS API usage to prevent overwrites of published binaries. Scope to be determined — verify Jira status.
- **PLT-2444 (status reporting API):** Public API for item update metrics. Can be deferred to after the first tenant is live if monitoring dashboards (Area 4) provide sufficient visibility.

### 8.3 Area 2 Gap: Item Deletion Flow Not Built

**What's missing:** No DELETE endpoint exists, no tombstone logic in `storeitemvalues`, no downstream tombstone handling in evaluator or renderer.

**Proposed solution (3-part) — to be validated:**
1. **item-registry:** Implement soft-delete — add a `deleted_at` timestamp or `is_deleted` flag to `storeitemvalues` DTO. The DELETE endpoint sets this; the DTO is not physically removed from Spanner.
2. **Link handling (design question):** When an item is deleted, the associated links must be cleaned up. Per [doc 13](13-core-data-flows.md), `link-registry` owns link DTOs, not the evaluator. Two approaches: (A) `studio-link-evaluator` detects the tombstone and triggers link cleanup via `link-registry`, or (B) `item-registry` emits a tombstone that `link-registry` consumes directly (it already subscribes to link-related topics). Approach B is architecturally cleaner since it respects DTO ownership boundaries. **Validate with the team.**
3. **studio-renderer:** When a `studiolink` is deleted or an item has no active link, render a blank/default template instead of a priced label. The blank `eslimage` flows through transmission normally.

**Justification:** Item deletion is a basic retail operation. Without it, removed products will show stale prices — a visible customer-facing defect. Maps to Area 2 (Feature Delivery) and the auto-unlink epic (PLT-2363).

### 8.4 Area 3 Gap: Tenant Isolation Not Verified (PLT-2578)

**What's missing:** No automated proof that tenant A cannot see tenant B's data in Spanner or through any API.

**Proposed solution:**
- Build a test suite that provisions two tenants, writes data for both, then attempts cross-tenant reads through every Cloud Run service.
- Add a Spanner IAM condition or row-level check: every query must include `t/{tenantId}` prefix.
- Add an integration test that runs in CI on every PR.

**Justification:** Tenant isolation is a non-negotiable security requirement. Without proven isolation, no real customer data can enter the platform.

### 8.5 Area 4 Gap: Per-API-Path Routing Not Started (PLT-2101)

**What's missing:** The mechanism that makes migration incremental. Currently, traffic is either all-cloud or all-R3Server. PLT-2101 teaches ingress-nginx to route by URL path.

**Proposed solution:**
- Reassign to Sreekanth S.U. (already handling Apigee/PSC) or another available engineer since Saikiran is on vacation.
- Configure `ingress-nginx` with regex-based path routing:
  - `/api/public/core/v1/items/*` → Cloud Run `item-registry-api`
  - `/api/private/*` (transmission, flash, display-page, map) → R3Server Store-Unit
- Store the routing table per tenant+store so individual stores can be flipped independently.

**Justification:** Without per-API-path routing, migration is all-or-nothing per store. This makes rollback nearly impossible and creates unacceptable risk for a real tenant.

### 8.6 Area 4 Gap: Shadow Mode Export Sub-Tasks Unassigned

**What's missing:** 5 export sub-tasks (ECC params/images/fonts, ESL status, itemproperties) are defined in Jira but have no owners.

**Proposed solution:**
- **PLT-2494/2495** (ECC export): Assign to Bart De Boer (already working on ECC-related epics PLT-2484, PLT-2792).
- **PLT-2492** (ESL status export): Assign to Daniel Pettersson (already working on PLT-1870 CQS client, PLT-2354 Shadow Mode).
- **PLT-2488/2714** (itemproperties export): Assign to Johan Ekman (already did PLT-2483 storeitemvalues export, which follows the same pattern).

**Justification:** Shadow Mode cannot go live without these export pipes. The data needs to be in DTOflow before the cloud pipeline can process it.

### 8.7 Area 4 Gap: Review Bottleneck (Johan Ekman)

**What's missing:** 6+ items waiting for Johan Ekman's review. He owns CQS, 3 new services, and storeitemvalues export.

**Proposed solution:**
- Distribute review load: Daniel Pettersson and Bart De Boer can review Quarkus Java services; Sreekanth can review infrastructure/PSC changes.
- Establish a rotating PR review schedule — no single person should be the only reviewer for any service area.
- Document CQS subscription architecture so reviews don't require deep CQS expertise for every PR.

**Justification:** A single-reviewer bottleneck slows the entire program. With 21 services, review must be a team responsibility.

### 8.8 Area 4/5 Gap: Ops Readiness Entirely in Backlog

**What's missing:** Monitoring (PLT-2579), load testing (PLT-2576), cutover runbook (PLT-2599), and disaster recovery (PLT-2580) are all in Backlog. You cannot put a real customer on the platform without these.

**Proposed solution:**
- **Monitoring (PLT-2579):** Start with Cloud Run built-in metrics + Cloud Monitoring dashboards. Minimum: CQS queue depth per service, Spanner read/write latency P50/P99, transmission success rate, item-registry error rate.
- **Load testing (PLT-2576):** Use the tenant's historical update volume from R3Server logs. Replay at 2× peak to validate headroom.
- **Cutover runbook (PLT-2599):** Write the 7-step procedure from [doc 14](14-tenant-migration.md) as a runbook with exact commands, expected outputs, and rollback steps. Rehearse on Replatforming-Dev before touching a real tenant.
- **DR (PLT-2580):** Phase 1 scope: Spanner scheduled backups + documented restore procedure. Full multi-region failover is Phase 2.

**Justification:** Ops readiness is what separates "it works in dev" from "it works in production." Without monitoring, you're blind. Without a runbook, you're guessing. Without load testing, you're hoping.

### 8.9 Area 6 Gap: First Tenant Not Selected (PLT-2601)

**What's missing:** PLT-2601 is in Backlog. Without a selection, Phase 1 has no concrete target.

**Proposed solution:**
- Drive a decision within 2 weeks using a scorecard: feature profile (which DTO types does the tenant use?), ESL count, update volume, integration complexity (PCS? EVO tokens? custom auth?), business risk (revenue impact of downtime).
- Architect-recommended sequence: byPricer → small customer (Landwaart AGF) → medium customer (spar-be).

**Justification:** Phase 1 scope depends on which tenant goes first. A simple tenant (byPricer, demo) needs fewer features. A medium tenant (spar-be) needs more. Select first, then finalize scope.

---

## 9. Migration Sequence & Tenant Strategy

### 9.1 Architect-Recommended Sequence

| Order | Tenant | Type | ESLs | Why This Order |
|-------|--------|------|------|----------------|
| **1st** | **byPricer** | Demo / Pricer-internal | Small | Zero revenue risk. Internal-facing demo data. Exercises the exact Phase 1 switch runbook without business impact. |
| **2nd** | **Small customer** (e.g., Landwaart AGF B.V.) | Real — produce retailer, Holland | 2 stores, sub-1000 labels | First real customer. Simple stack (EVO tokens, no PCS). Low ESL count limits blast radius. |
| **3rd** | **Medium customer** (e.g., Spar-be) | Real — large format, Belgium | O(10) stores, ~13K labels | Scale validation bridge to Phase 2. Do not migrate until the small customer runs flawlessly for 2 weeks. |

### 9.2 Per-Tenant Gates

| Gate | byPricer | Small Customer | Medium Customer |
|------|----------|----------------|-----------------|
| Shadow Mode validated (Phase 0 tenants) | ✅ Required | ✅ Required | ✅ Required |
| PLT-2651 + PLT-2378 implemented | ✅ Required | ✅ Required | ✅ Required |
| Per-API-path routing (PLT-2101) | ✅ Required | ✅ Required | ✅ Required |
| Tenant isolation proven (PLT-2578) | ✅ Required | ✅ Required | ✅ Required |
| Store onboarding (PLT-2572) | ✅ Required | ✅ Required | ✅ Required |
| Monitoring (PLT-2579) | Basic | Full | Full |
| Load testing (PLT-2576) | Light | At 2× peak | At 3× peak |
| Cutover runbook rehearsed (PLT-2599) | On Replatforming-Dev | On byPricer | On small customer |
| Previous tenant stable for 2 weeks | N/A | ✅ Required | ✅ Required |

---

## 10. Key Activities & Milestones

Phase 1 maps to two Milestones — **M3: First Tenant Go-Live** and **M4: Production Hardening** — each with three Increments. These supersede the five Workstreams from earlier versions of this plan.

```mermaid
---
config:
    layout: elk
---
flowchart TB
    subgraph M3["M3: First Tenant Go-Live"]
        direction LR
        I31["Inc 1<br/>Item+Link APIs<br/>(Areas 1, 2)"]
        I32["Inc 2<br/>Security & Isolation<br/>(Area 3)"]
        I33["Inc 3<br/>Tenant Switch<br/>(Areas 5, 6)"]
    end

    subgraph M4["M4: Production Hardening"]
        direction LR
        I41["Inc 1<br/>Monitoring<br/>(Area 4)"]
        I42["Inc 2<br/>Load Test<br/>(Area 5)"]
        I43["Inc 3<br/>DR + Runbook<br/>(Area 4)"]
    end

    I31 --> I32
    I32 --> I33
    I33 --> I41
    I41 --> I42
    I42 --> I43

    style M3 fill:#fff3e0,stroke:#f57c00,color:#000
    style M4 fill:#e3f2fd,stroke:#1565c0,color:#000
```

> Activities that close Phase 0 gates (Shadow Mode completion, per-API-path routing, tenant isolation proofs) are prerequisites to M3 and are covered in the Phase 0 status doc ([15](15-overall-status.md)). This section focuses on work that starts once M2 (Shadow Mode Validation) closes.

### M3 Inc 1: Item & Link APIs Live (Architect Areas 1, 2) — Target W36 (Sep 6)

| Step | What | Epic | Target |
|------|------|------|--------|
| 1a | Assign and unblock item validation | PLT-2651 | Owner assigned this sprint |
| 1b | Implement item property validation | PLT-2651 | All item writes validated before Spanner persistence |
| 1c | Assign and implement Item Patch APIs | PLT-2378 | `PATCH/DELETE /api/.../items` live on Cloud Run |
| 1d | Assess SIC requirement | PLT-2274 | Determined during tenant selection (PLT-2601) |
| 1e | Platform hardening: SLA/trackingId | PLT-171 | Priority timestamps on CQS events |
| 1f | Platform hardening: LFS overwrite protection | PLT-2658 | GCS API usage aligned |
| 1g | Feature delivery scoped to tenant profile | PLT-2360, 2361, 2350, 2356, 2363, 2352 | Feature subset activated per tenant assessment |

**Demo:** Write an item via PATCH → item passes validation → `storeitemvalues` appears in Spanner → CQS fans out → evaluator + renderer process it → `eslimage` written.

### M3 Inc 2: Security & Isolation (Architect Area 3) — Target W37 (Sep 13)

| Step | What | Epic | Target |
|------|------|------|--------|
| 2a | Prove tenant isolation | PLT-2578 | Automated cross-tenant read tests pass; `t/{tenantId}` prefix enforced |
| 2b | Write protection | PLT-170 | Auth0 JWT-based M2M write permissions per tenant |

**Demo:** Provision two tenants. Write data for both. Attempt cross-tenant reads through every Cloud Run service. All rejected.

### M3 Inc 3: Tenant Switch (Architect Areas 5, 6) — Target W38 (Sep 20, byPricer go-live)

| Step | What | Epic | Target |
|------|------|------|--------|
| 3a | Select first tenant | PLT-2601 | Decision within 2 weeks; scorecard based |
| 3b | Store onboarding built | PLT-2572, 2575 | Repeatable store provisioning in Spanner |
| 3c | Studio production readiness | PLT-2600 | Tenant designs hardened in studio services |
| 3d | Integration tests passing | PLT-2430 | All Phase 1 APIs passing TA2 E2E suite |
| 3e | Per-tenant Shadow Mode | — | Enable Shadow Mode for the Phase 1 tenant. 24+ hour image parity confirmed. Config → items → links pushed in dependency order. |
| 3f | Execute 7-step switch — byPricer | — | Switch procedure from [doc 14](14-tenant-migration.md), rehearsed on Phase 0 tenant first |

**Demo:** byPricer tenant live on DTOflow. Item updates flow through cloud path. R3Server is thin edge (transmission only). Done by W38.

### M4 Inc 1: Monitoring (Architect Area 4) — Target W41 (Oct 11)

| Step | What | Epic | Target |
|------|------|------|--------|
| 1a | Production monitoring dashboards | PLT-2579 | CQS queue depth, Spanner latency, Cloud Run error rates, transmission success rates |
| 1b | Status reporting API | PLT-2444 | Item update metrics API |

**Demo:** Live dashboard showing pipeline health for the cut-over tenant. Done by W41.

### M4 Inc 2: Load Test (Architect Area 5) — Target W42 (Oct 18)

| Step | What | Epic | Target |
|------|------|------|--------|
| 2a | Production-scale load testing | PLT-2576 | 2–3× peak tenant volume replayed; p99 latency parity confirmed |
| 2b | Auto-scaling validated | PLT-2369 | CQS-driven scaling or Cloud Run built-in confirmed sufficient |

**Demo:** Replay the tenant's historical update volume at 2× peak. All pipelines stay within latency thresholds. Done by W42.

### M4 Inc 3: DR & Runbook (Architect Area 4) — Target W44 (Nov 1)

| Step | What | Epic | Target |
|------|------|------|--------|
| 3a | Cutover & rollback runbook | PLT-2599 | 7-step procedure written, reviewed, rehearsed on byPricer |
| 3b | Disaster recovery | PLT-2580 | Spanner scheduled backups; documented restore procedure; DR drill passed |
| 3c | Operational runbooks | PLT-2581 | Per-service runbooks for common failure scenarios |

**Demo:** Execute the full switch + rollback on byPricer. Execute DR restore from backup. Both complete within recovery windows. Done by W44.

### Post-Cutover: Hypercare

After a tenant switches, a 2-week hypercare period applies before the next tenant:

| Step | Action | Owner |
|------|--------|-------|
| HC1 | Monitor CQS queue depth, transmission latency, image parity continuously | Platform |
| HC2 | Be ready to execute the rollback procedure if needed | Infrastructure |
| HC3 | Review all alerts and incidents before clearing the next tenant to switch | Engineering lead |

---

### How the old Workstreams map to M3/M4

For readers familiar with the earlier 5-Workstream structure:

| Old Workstream | New Home |
|---------------|----------|
| WS1: Close Phase 0 & Foundation | Phase 0 (M1/M2) prerequisites + M3 Inc 1 |
| WS2: Ops Foundation | M4 Inc 1 + M4 Inc 3 |
| WS3: Tenant Onboarding | M3 Inc 3 |
| WS4: Feature Delivery & Validation | M3 Inc 1 + M3 Inc 3 |
| WS5: The Switch | M3 Inc 3 |

---

## 11. Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **PLT-2651 + PLT-2378 remain unassigned** | 🔴 Critical | Medium | The single biggest risk. Assign owners this week. Both are well-scoped; the blocker is ownership, not technical complexity. |
| **CQS fan-out congestion under real load** | 🟡 High | Medium | Renderer and evaluator hit Spanner simultaneously during bulk updates. PLT-2792 (services own queues) provides per-service rate limiting. Load testing (PLT-2576) must include bulk update scenarios. |
| **Image parity fails during Shadow Mode** | 🟡 High | Medium | If rendered images don't match, investigate diff. Could be rendering engine differences, font/metrics, or data drift. Mitigation: start Shadow Mode early (weeks before switch, not days). |
| **Rollback fails during switch** | 🟡 High | Low | The switch drops R3Server's item and link tables. Rehearse the full rollback on Replatforming-Dev. Keep the MySQL backup as the safety net. |
| **Event ordering issues in Shadow Mode** | 🟡 Medium | Medium | Config must be pushed before items. Enforce dependency order in the export pipe. |
| **Review bottleneck blocks progress** | 🟡 Medium | High | 6+ items waiting. Distribute review load, document CQS architecture, establish rotation. |
| **Bus factor — key people own too much** | 🟡 Medium | High | Bart (4+ epics), Johan (3+ epics + all reviews), Daniel (3 epics), Sreekanth (3 epics). Spread ownership, pair on critical components, document architecture. |
| **Saikiran vacation delays PLT-2101** | 🟡 Medium | Certain | Reassign or plan handover now. API routing is on the critical path. |
| **Summer vacation season** | 🟢 Low | Certain | Plan around it. June–August is slow. Front-load critical path items. |
| **Scope creep — Feature Delivery area broader than "basic features for simple tenant"** | 🟡 Medium | Medium | The architect's Area 2 includes features (timed updates, segment labels, flash) that may not be needed for the first tenant. Gate features per tenant based on the tenant's feature profile (PLT-2601). byPricer needs minimal features; Spar-be needs most. |

---

## 12. Rough Timeline

> **Caveat:** This is a planning estimate, not a commitment. Actual velocity depends on team capacity (summer vacations, review bottleneck) and how quickly PLT-2651/2378 get assigned. **This timeline assumes no further blockers are discovered and full team availability — both optimistic assumptions.** Realistically, Q4 2026 for the first Phase 1 tenant (byPricer, W44) is achievable; completing all three tenants may extend into Q1 2027, especially given summer vacation impact on Q3 velocity.

| Phase | Activities | Duration | Target | Depends On |
|-------|-----------|----------|--------|------------|
| **Pre-Phase 1** (W27-29) | Unblock PLT-2651 + PLT-2378. Assign Shadow Mode sub-tasks. Reassign PLT-2101. | 2–3 weeks | **W29** (Jul 19) | — |
| **M3 Inc 1** (W30-36) | Implement PLT-2651, PLT-2378. Complete Shadow Mode on Phase 0 tenants. PLT-2101 routing. Tenant isolation (PLT-2578). | 4–6 weeks (overlaps with P0 tail) | **W36** (Sep 6) | Pre-Phase 1 |
| **M3 Inc 2** (W35-37) | PLT-2578 (tenant isolation), PLT-170 (write protection). Security proofs for multi-tenancy. | 2–3 weeks | **W37** (Sep 13) | M3 Inc 1 |
| **M4 Inc 1** (W38-41) | PLT-171 (SLA/trackingId), PLT-2579 (monitoring dashboards), PLT-2444 (status reporting). | 3–4 weeks | **W41** (Oct 11) | — |
| **M3 Inc 3** (W35-38) | PLT-2601 (select tenant), PLT-2572/2575 (onboarding), PLT-2600 (studio readiness). Shadow Mode + switch for byPricer. | 4–6 weeks | **W38** (Sep 20) | M3 Inc 1 + M3 Inc 2 gates |
| **M4 Inc 2** (W39-42) | Load testing (PLT-2576), auto-scaling validation (PLT-2369). | 2–3 weeks | **W42** (Oct 18) | byPricer live (W38) |
| **M4 Inc 3** (W42-44) | Cutover runbook (PLT-2599), DR (PLT-2580), operational runbooks (PLT-2581). | 2–3 weeks | **W44** (Nov 1) | Load test complete |
| **Remaining tenants** (W44+) | Small customer Switch → hypercare (2w) → medium customer Switch → hypercare (2w). | 4–6 weeks per tenant | **Q1 2027** | M4 closed |

---

## 13. What Success Looks Like

Phase 1 is complete when:

1. ✅ **byPricer** is live on DTOflow — items, links, and rendering all flow through the cloud path. R3Server is thin edge (transmission only).
2. ✅ **One small customer** (e.g., Landwaart AGF — 2 stores, sub-1000 labels) is live on DTOflow — a real, revenue-generating customer with R3Server thin edge.
3. ✅ **One medium customer** (e.g., Spar-be — ~13K ESLs) is live on DTOflow — the system handles real scale.
4. ✅ **Monitoring dashboards** show healthy pipelines — CQS queue depth, Spanner latency, transmission success rate all within thresholds.
5. ✅ **The switch runbook** has been rehearsed 3+ times across different tenants and works reliably.
6. ✅ **Rollback** has been tested and works within the defined recovery window.
7. ✅ **2-week hypercare** completed for each tenant with zero critical incidents.
8. ✅ **Phase 2 scope** is defined based on real operational data from Phase 1.

---

## 14. Immediate Next Actions (This Week)

These are the concrete steps a lead can take right now, ranked by impact:

| # | Action | Area | Impact |
|---|--------|------|--------|
| 1 | **Assign an owner to PLT-2651** (item property validation) | Area 1 | Unblocks the Item Pipeline — the single clearest gate |
| 2 | **Assign an owner to PLT-2378** (Item Patch APIs) | Area 1/2 | Unblocks Plaza Mobile + Central-Manager consumer paths |
| 3 | **Reassign PLT-2101** (API routing) — Saikiran is on vacation | Area 4 | Unblocks the incremental migration mechanism |
| 4 | **Assign the 5 Shadow Mode export sub-tasks** | Area 4 | Completes the Phase 0 data pipes |
| 5 | **Start PLT-2601** (first tenant selection) — drive decision within 2 weeks | Area 6 | Gives Phase 1 a concrete target |
| 6 | **Distribute review load** — 6+ items waiting on Johan | Area 4 | Unblocks the review bottleneck |
| 7 | **Start PLT-2579** (monitoring dashboards) — can begin immediately | Area 4 | Ops foundation that doesn't depend on any blocker |

---

> **Source:** Phase 1 activity areas, acceptance criteria, and tenant sequence from the Replatforming architect's [Phase 1 Activity Planning](https://pricer-org.atlassian.net/wiki/x/LAD8XwI) Confluence page (PS space, page ID 10198908937).
>
> **Companion docs:** [03 — Replatforming Deep Dive](03-replatforming-deep-dive.md) · [04 — Target Architecture](04-target-architecture.md) · [13 — Core Data Flows](13-core-data-flows.md) · [14 — Tenant Migration](14-tenant-migration.md) · [15 — Overall Status](15-overall-status.md) · [19 — Delivery Framework](19-dimension-frameworks.md)
