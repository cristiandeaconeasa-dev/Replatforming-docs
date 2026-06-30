# 15 — Overall Status: Replatforming Program (v2)

> **Scope:** Complete status of the Pricer Replatforming program — organised by the Workstream → Capability framework, with every Jira epic mapped to its delivery workstream and system capability.
>
> **Validated:** 2026-06-30 — against live GCP (`platform-dev-p01`, `europe-north1`), GitHub (`PricerAB` org), Jira (`project = PLT`), and the `evo-dtoflow-protos` central-documentation branch.
>
> **Status legend:**  
✅ Closed = done ·   
🟢 Live = deployed ·   
🟡 In Progress / Test / Selected / Ready for Deploy = active ·  
🔴 Blocked = gated ·  
🔵 Backlog = not started

---

## 1. How We Organise the Work

The Replatforming program spans 42 epics across 5 workstreams, 5 system capabilities, and 3 delivery phases. To make sense of this, we use a two-level hierarchy:

```mermaid
config:
    layout: elk

flowchart TB
    subgraph phases["Three Delivery Phases"]
        direction LR
        P0["Phase 0<br/>Internal validation<br/>Zero label risk"]
        P1["Phase 1<br/>First real tenant<br/>Controlled risk"]
        P2["Phase 2<br/>Scale & parity<br/>Full migration"]
    end

    subgraph workstreams["Five Workstreams — when it ships"]
        direction LR
        W1["W1: Foundation<br/>Enablers"]
        W2["W2: Shadow<br/>Mode"]
        W3["W3: Consumer<br/>API Cutover"]
        W4["W4: Production<br/>Operations"]
        W5["W5: Feature<br/>Parity & Scale"]
    end

    subgraph capabilities["Five Capabilities — what it does"]
        direction LR
        C1["C1: Data &<br/>Routing Fabric"]
        C2["C2: Item Data<br/>Management"]
        C3["C3: Linking &<br/>Parallel Rendering"]
        C4["C4: Edge Bridging<br/>& Execution"]
        C5["C5: Tenant Isolation<br/>& Ops Lifecycle"]
    end

    P0 --> W1 & W2
    P1 --> W3 & W4
    P2 --> W5

    W1 --> C1
    W2 --> C4
    W3 --> C2 & C3 & C4
    W4 --> C3 & C5
    W5 --> C1 & C2 & C3 & C4 & C5

    subgraph epics["Jira Epics — 42 epics, each mapped to one Workstream + one Capability pair"]
    end

    capabilities --> epics

    classDef green fill:#A9DFBF,stroke:#1E8449,color:#1a1a1a
    classDef yellow fill:#F9E79F,stroke:#D4AC0D,color:#1a1a1a
    classDef blue fill:#AED6F1,stroke:#2E86C1,color:#1a1a1a
    class P0,W1,W2,C1,C4 green
    class P1,W3,W4,C2,C3,C5 yellow
    class P2,W5 blue
```

**Why this structure:**

- **Phase** tells you when in the program lifecycle the work belongs (0 = prove it works, 1 = first real customer, 2 = everyone else).
- **Workstream** tells you what business milestone it delivers and what gates it. The CTO and PMO read this level.
- **Capability** tells you what part of the system it builds. Engineers and architects read this level.
- **Epic** is the Jira unit of delivery — the thing that gets assigned, estimated, and tracked.

A single table (the two-level epic mapping in §4) combines all three dimensions so every audience can read the same document at their preferred depth.

---

## 2. The Workstreams

| Workstream | Phase | Definition | Completion Gate | Epics |
|-----------|-------|------------|-----------------|-------|
| **W1: Foundation Enablers** | Phase 0 | Core infrastructure (Spanner, Pub/Sub, CQS, routing, PSC) that must exist before any traffic moves to the cloud | All Foundation services live + PROD-ready certified + per-API-path routing operational | 7 |
| **W2: Shadow Mode** | Phase 0 | Run the cloud pipeline in parallel with the edge, validating correctness without touching a single label | 24+ hrs on `Replatforming-Dev` with 100% rendered-image parity | 11 |
| **W3: Consumer API Cutover** | Phase 1 | Migrate item and link API traffic from R3Server to cloud services, one API path at a time | First real tenant (byPricer) live on cloud for basic item/link/rendering flows | 10 |
| **W4: Production Operations** | Phase 1 | Operational readiness: tenant selection, store onboarding, load testing, monitoring, DR, cutover runbooks | All ops gates passed; cutover procedure tested; tenant isolation validated | 11 |
| **W5: Feature Parity & Scale** | Phase 2 | Remaining features for full migration: timed updates, ECC sync, autoscaling, SLAs, webhooks, segment labels | All tenants migrated; feature parity with legacy R3Server achieved | 19 |

### Workstream Sequencing

```mermaid
config:
    layout: elk
flowchart LR
    W1["W1: Foundation<br/>Enablers"] --> W2["W2: Shadow<br/>Mode"]
    W2 --> W3["W3: Consumer<br/>API Cutover"]
    W3 --> W4["W4: Production<br/>Operations"]
    W4 --> LIVE["🏬 First real<br/>tenant live"]
    W4 --> W5["W5: Feature<br/>Parity & Scale"]
    W5 --> ALL["All tenants<br/>migrated"]

    classDef active fill:#F9E79F,stroke:#D4AC0D,color:#1a1a1a
    classDef future fill:#E5E7EB,stroke:#9CA3AF,color:#1a1a1a
    class W1,W2 active
    class W3,W4,W5 future
```

**Current state:** W1 and W2 are actively in progress. W3 is gated by two blocked epics (PLT-2651, PLT-2378). W4 and W5 are entirely in backlog — no work has started.

---

## 3. The Capabilities

| Capability | Definition | Services Involved | Epic Count |
|-----------|------------|-------------------|------------|
| **C1: Distributed Data & Routing Fabric** | Infrastructure that everything else depends on: Spanner storage, Pub/Sub messaging, CQS event fan-out, ingress routing, PSC networking, auth, scaling | `dtoflow-spanner`, `dtoflow-lfs`, CQS (GKE `platform`), Apigee, ingress-nginx | 11 |
| **C2: Item Data Management** | Ingesting, validating, patching, and storing ERP item/price data as `storeitemvalues` DTOs | `item-registry-api`, `item-registry` | 8 |
| **C3: Linking & Parallel Rendering** | Core business logic: mapping items to ESLs, evaluating CEL rules, rendering label images, merging Studio + ECC outputs | `link-registry`, `link-bfg`, `studio-link-evaluator`, `studio-renderer`, `studio-design-library`, `studio-scenario-library`, `ecc-renderer`, `ecc-link-projector`, `esl-image-merger` | 10 |
| **C4: Edge Bridging & Execution** | Cloud-to-device communication: image transmission, real-time flash, label status reporting, config synchronisation, Shadow Mode data pipes | `dtoflow-transmission`, R3Server (thin edge, stays on-prem) | 17 |
| **C5: Tenant Isolation & Ops Lifecycle** | Provisioning, onboarding, security boundaries, load testing, monitoring, disaster recovery, cutover runbooks | N/A — operational processes | 12 |



The capabilities are ordered by **architectural dependency layer** (bottom-to-top), not by business priority or delivery sequence:

- **C1 (Data & Routing Fabric)** — The foundation layer. Spanner, Pub/Sub, CQS, routing, PSC. Everything else depends on this existing first.
- **C2 (Item Data Management)** — Ingests, validates, patches item/price data. Depends on C1 for storage and messaging.
- **C3 (Linking & Parallel Rendering)** — Core business logic (mapping items to ESLs, CEL rules, rendering). Depends on C1 for data routing and C2 for item data.
- **C4 (Edge Bridging & Execution)** — Cloud-to-device communication. Depends on C1 for transmission infrastructure. Separately needed early for Shadow Mode.
- **C5 (Tenant Isolation & Ops Lifecycle)** — Operational processes (onboarding, monitoring, DR). Depends on all others existing before it's meaningful.

**Why Phase 0 = C1 + C4, not C1 + C2:**

Phase 0 is about **proving the infrastructure works without touching a single real label** (zero label risk). This requires two things:
1. **C1** — The platform must exist (Spanner, Pub/Sub, CQS, routing).
2. **C4** — The edge bridge must exist so the cloud pipeline can run in parallel with R3Server and output can be compared (Shadow Mode). This is the "consume-ignore-linked" mode and data export pipes.

C2 (Item Data Management) feeds **real** tenant data — you don't need real item validation, patching, or SIC support when you're just proving the pipeline architecture works. That comes in Phase 1 when you cut over the first tenant's traffic.

In short: **C1 and C4 are the scaffolding needed to prove the architecture**. C2 and C3 are the business capabilities that consume that scaffolding with real tenant data in Phase 1. C5 is the operational wrapping that only matters once tenants exist.

### Capability-to-Workstream Matrix

This shows which capabilities each workstream delivers. A capability appearing in multiple workstreams means it's built incrementally across phases.

| Capability | W1 Foundation | W2 Shadow Mode | W3 API Cutover | W4 Prod Ops | W5 Feature Parity |
|-----------|:---:|:---:|:---:|:---:|:---:|
| **C1: Data & Routing Fabric** | ✅ 7 epics | — | — | — | 4 epics |
| **C2: Item Data Management** | — | — | ✅ 4 epics | — | 4 epics |
| **C3: Linking & Parallel Rendering** | — | — | ✅ 5 epics | ✅ 1 epic | 4 epics |
| **C4: Edge Bridging & Execution** | — | ✅ 11 epics | ✅ 1 epic | — | 5 epics |
| **C5: Tenant Isolation & Ops Lifecycle** | — | — | — | ✅ 10 epics | 2 epics |

---

## 4. Two-Level Epic Mapping

> Every epic mapped to its Workstream (when it ships) and Capability (what system layer it builds).
>
> **Reading guide:** **Bold** = Workstream header · *Italic* = Capability sub-header · Plain rows = Jira epics.
>
> **Data source:** Live Jira (`project = PLT`), pulled 2026-06-30.

| Workstream / Capability | Epic | Status | Assignee | Summary |
|-------------------------|------|--------|----------|---------|
| **W1: Foundation Enablers** | | | | |
| *C1: Data & Routing Fabric* | — (infra) | 🟢 Live | — | Spanner `dtoflow` (29 tables, 1000 PU), Pub/Sub (32 topics), gRPC client libraries (Java + Node), GCS/LFS, `dtoflow-spanner`, `dtoflow-lfs`, GKE `platform` |
| | PLT-2294 | ✅ Closed | Bart De Boer | ID & alias validation in DTOflow servers |
| | PLT-2118 | 🟡 Test | Bart De Boer | DTOflow PROD-ready certification for Task & Scenario |
| | PLT-169 | 🟡 In Progress | Johan Ekman | ChangeQueueService — subscription-based event fan-out |
| | PLT-2336 | 🟡 In Progress | Sreekanth S. Uppara | DTOflow broadly accessible via Private Service Connect |
| | PLT-2478 | 🟡 In Progress | Sreekanth S. Uppara | Pricer Server ↔ CQS / DTOflow integration design |
| | PLT-2792 | 🟡 In Progress | Bart De Boer | Services own their CQS queues (self-service subscription) |
| | PLT-2101 | 🟡 Selected | Saikiran Katta | Per-API-path routing at ingress — the incremental migration mechanism |
| **W2: Phase 0 — Shadow Mode** | | | | |
| *C4: Edge Bridging & Execution* | PLT-2497 | ✅ Closed | Unassigned | consume-ignore-linked mode (Shadow Mode enabler) |
| | PLT-2354 | 🟡 In Progress | Daniel Pettersson | Shadow Mode orchestration — parallel cloud pipeline, zero label risk |
| | PLT-2353 | 🟡 In Progress | Bart De Boer | Pricer Server config export to DTOflow (enabler) |
| | PLT-2483 | 🟡 Ready for Deploy | Johan Ekman | `storeitemvalues` export — real-time item data pipe |
| | PLT-2496 | 🟡 Ready for Deploy | Unassigned | Link export — real-time link data pipe |
| | PLT-2494 | 🟡 In Progress | Johan Ekman | ECC params / images / models export (data pipe) |
| | PLT-2495 | 🟡 Selected | Unassigned | ECC fonts export (data pipe) |
| | PLT-2492 | 🟡 Selected | Unassigned | ESL Status DTO export (data pipe) |
| | PLT-2488 | 🟡 Selected | Unassigned | `itemproperties` export (data pipe) |
| | PLT-2714 | 🟡 Selected | Unassigned | `itemproperties` startup export (data pipe) |
| | PLT-1870 | 🟡 Test | Daniel Pettersson | CQS client in R3Server — edge-side work dispatch |
| **W3: Phase 1 — Consumer API Cutover** | | | | |
| *C2: Item Data Management* | PLT-2598 | ✅ Closed | Unassigned | Initial Bulk Item Load (scope-out) |
| | PLT-2651 | 🔴 Blocked | Unassigned | Item property validation — **single clearest gate on item-driven migration** |
| | PLT-2378 | 🔴 Blocked | Unassigned | Item Patch APIs — Core (gates Plaza Mobile + Central-Manager) |
| | PLT-2274 | 🔴 Blocked | Daniel Pettersson | SIC Support — items findable by Store Item Code |
| *C3: Linking & Parallel Rendering* | PLT-2773 | ✅ Closed | Johan Ekman | ECC Link Projector service |
| | PLT-2771 | ✅ Closed | Unassigned | ESL Image Merger |
| | PLT-2484 | 🟡 In Progress | Bart De Boer | Link v1 DTO refactor |
| | PLT-2357 | 🟡 Selected | Unassigned | Linked Item APIs — Items |
| | PLT-2358 | 🟡 Selected | Unassigned | Linked Item APIs — Devices |
| *C4: Edge Bridging & Execution* | PLT-2577 | ✅ Closed | Unassigned | ESL registration in cloud |
| **W4: Phase 1 — Production Operations** | | | | |
| *C3: Linking & Parallel Rendering* | PLT-2600 | 🔵 Backlog | Unassigned | Studio Services Prod-Readiness certification |
| *C5: Tenant Isolation & Ops Lifecycle* | PLT-2601 | 🔵 Backlog | Cristian Deaconeasa | First Tenant Selection — **gate decision for Phase 1 scope** |
| | PLT-2572 | 🔵 Backlog | Unassigned | Store Onboarding — repeatable store provisioning |
| | PLT-2575 | 🔵 Backlog | Unassigned | Store DTO Schema — store metadata in cloud |
| | PLT-2578 | 🔵 Backlog | Unassigned | Tenant Isolation Validation — proven: tenant A cannot see tenant B's data |
| | PLT-2576 | 🔵 Backlog | Unassigned | Performance & Load Testing — 652M items scale |
| | PLT-2579 | 🔵 Backlog | Unassigned | Monitoring & Dashboards |
| | PLT-2580 | 🔵 Backlog | Unassigned | Disaster Recovery — backups, restore, DR drills |
| | PLT-2599 | 🔵 Backlog | Unassigned | Cutover & Rollback Runbook — per-store traffic switch |
| | PLT-2581 | 🔵 Backlog | Unassigned | Operational Runbooks |
| | PLT-2430 | 🔵 Backlog | Unassigned | Integration Tests Delivery 1 — automated E2E suite |
| **W5: Phase 2 — Feature Parity & Scale** | | | | |
| *C1: Data & Routing Fabric* | PLT-171 | 🟡 Selected | Unassigned | SLA & `trackingId` support — priority timestamps |
| | PLT-2444 | 🔵 Backlog | Unassigned | Status Reporting — "how many items processed, how fast" |
| | PLT-2369 | 🔵 Backlog | Unassigned | Auto-scaling — CQS-driven, proactive |
| | PLT-170 | 🔵 Backlog | Unassigned | Write Protection — Auth0 JWT-based access control |
| *C2: Item Data Management* | PLT-2350 | 🔵 Backlog | Unassigned | Timed Item Updates — scheduled price changes |
| | PLT-2351 | 🔵 Backlog | Unassigned | Item Ingest Status — Extended |
| | PLT-2352 | 🔵 Backlog | Unassigned | Item Ingest Status — Advanced |
| | PLT-2436 | 🔵 Backlog | Unassigned | Item / Link via PFI (Pricer File Interface) |
| *C3: Linking & Parallel Rendering* | PLT-2359 | 🟡 In Progress | Bart De Boer | ECC Links & Rendering — legacy ECC parity (building early) |
| | PLT-2361 | 🔵 Backlog | Unassigned | Segment Labels — 7-segment calculator-style labels |
| | PLT-2360 | 🔵 Backlog | Unassigned | Unified Linking API |
| | PLT-2363 | 🔵 Backlog | Unassigned | Auto Unlink — labels auto-unlink when items deleted |
| *C4: Edge Bridging & Execution* | PLT-2573 | ✅ Closed | Unassigned | ECC Sync push (scope-out) |
| | PLT-2574 | ✅ Closed | Unassigned | Transmission service integration (scope-out — won't do; `dtoflow-transmission` covers this) |
| | PLT-2355 | 🟡 Selected | Bart De Boer | Label Status APIs — "how many labels OK/error/updating?" |
| | PLT-2356 | 🔵 Backlog | Unassigned | Item Flash APIs — sub-second label blink (stays on R3Server edge) |
| | PLT-2362 | 🔵 Backlog | Unassigned | GeoPos Support — label positions in cloud |
| *C5: Tenant Isolation & Ops Lifecycle* | PLT-2428 | 🔵 Backlog | Unassigned | Subscription System — license / entitlement enforcement |
| | PLT-2440 | 🔵 Backlog | Unassigned | Webhook Events — external system notifications |

> **Note on PLT-2359:** Marked "In Progress" in W5 (Phase 2). Bart De Boer is building ECC parity in parallel with Phase 0/1 work, but ECC rendering is explicitly scoped to Phase 2 — the first real tenant will use Studio rendering only. Read this as "early progress on a Phase 2 capability" — not "Phase 2 work blocking Phase 1."
>
> **Coverage:** 42 of 42 labeled Replatforming epics are covered. Five Phase 2 placeholder epics are intentionally omitted because their scope is not yet defined by the PMO — they will be added when scoped: PLT-2429 (Prometheus Metrics), PLT-2431 (Integration Tests Delivery 2), PLT-2364 (Jasper Reports), PLT-2365 (Timeline Support), PLT-2427 (Configuration Management).

---

## 5. Infrastructure Health

All services deployed in GCP project `platform-dev-p01`, region `europe-north1`.

| Component | Details | Status |
|-----------|---------|--------|
| **Spanner** | Instance `dtoflow`, 1000 PU, 29 DTO tables + `item-registry` (1 table) | 🟢 Healthy |
| **Pub/Sub** | 32 topics (`dtoflow-changes-*`, DLQ, sync, `item-registry-requests`) | 🟢 Healthy |
| **Cloud Run** | 21 services deployed | 🟢 All live |
| **GKE** | Cluster `platform` — runs ChangeQueueService | 🟢 Healthy |
| **GCS / LFS** | `dtoflow-lfs` — content-addressed SHA-256 storage | 🟢 Healthy |
| **Apigee** | API gateway — front door to Cloud Run | 🟡 PSC setup in progress (PLT-2336) |
| **Ingress** | PCS ingress-nginx — per-API-path routing (PLT-2101 not started) | 🟡 Selected for Dev |

### Cloud Run Service Inventory

All 21 services deployed and verified live.

| Domain | Services |
|--------|----------|
| **Item** | `item-registry-api`, `item-registry` |
| **Link** | `link-registry`, `link-bfg`, `link-storeasset-bfg` |
| **Studio Rendering** | `studio-link-evaluator`, `studio-renderer`, `studio-design-library`, `studio-scenario-library` |
| **ECC Rendering** | `ecc-link-projector`, `ecc-renderer`, `esl-image-merger` |
| **Edge Bridge** | `dtoflow-transmission` |
| **Actions** | `actions-executor`, `actions-library` |
| **Operations** | `delivery-sync-service`, `delivery-dashboard`, `dtoflow-changequeue-dashboard`, `migration-helper` |
| **Storage** | `dtoflow-spanner`, `dtoflow-lfs` |

---

## 6. Executive Summary

**The DTOflow cloud platform is largely live.** Link processing, rendering, and transmission are operational end-to-end across 21 Cloud Run services. The primary delivery risk is concentrated in **W3 (Consumer API Cutover)**, where two blocked epics — PLT-2651 (Item property validation) and PLT-2378 (Item Patch APIs) — gate all item-driven flows.

**Current program state at a glance:**

| Workstream | Status | Key Signal |
|-----------|--------|------------|
| **W1: Foundation Enablers** | 🟡 Active | CQS (PLT-169) In Progress; PROD-ready cert (PLT-2118) in Test; routing (PLT-2101) not started |
| **W2: Shadow Mode** | 🟡 Active | Core orchestration (PLT-2354) In Progress; 2 data pipes Ready for Deploy; 5 sub-tasks need owners |
| **W3: Consumer API Cutover** | 🔴 Gated | 2 blocked & unassigned epics (PLT-2651, PLT-2378) — the highest-priority action in the program |
| **W4: Production Operations** | 🔵 Not started | All 11 epics in Backlog; gated on W2 completion + W3 progress |
| **W5: Feature Parity & Scale** | 🔵 Not started | All 19 epics in Backlog; one (PLT-2359) with early progress |

### Closed Issues Summary

| Issue Type | Closed | Done (not Closed) | Total |
|-----------|:------:|:-----------------:|:-----:|
| **Epics** | 5 | — | 5 |
| **Stories** | 5 | — | 5 |
| **Tasks** | 5 | — | 5 |
| **Sub-tasks** | 7 | 2 | 9 |
| **Total** | **22** | **2** | **24** |

> **Jira source:** `project = PLT AND labels in ("replatforming-phase-0","replatforming-phase-1","replatforming-phase-2") AND (status = Closed OR status = Done)` — pulled 2026-06-30.
>
> The 2 "Done" items (PLT-2709, PLT-2710) are sub-tasks pending the final Closed transition. No epics or stories are in "Done" without being Closed.

### DTOflow cloud platform

```mermaid
config:
    layout: elk
flowchart LR
    DTOflow["DTOflow Foundation"] --> Link["Link Pipeline"]
    DTOflow --> Render["Rendering Pipeline"]
    DTOflow --> Edge["Transmission & Edge Bridge"]
    Link --> CQS["CQS (nearing completion)"]
    Render --> CQS
    CQS --> Gateway["Gateway & Routing"]
    Gateway --> Shadow["Shadow Mode"]
    DTOflow --> Item["Item Pipeline"]
    Item --> Consumer["Consumer APIs"]
    
    classDef live fill:#A9DFBF,stroke:#1E8449,color:#1a1a1a
    classDef yellow fill:#F9E79F,stroke:#D4AC0D,color:#1a1a1a
    classDef red fill:#F5B7B1,stroke:#C0392B,color:#1a1a1a
    class DTOflow,Link,Render,Edge live
    class CQS,Gateway,Shadow,Consumer yellow
    class Item red
```

| Dimension | Status | Detail |
|-----------|--------|--------|
| **DTOflow Foundation** | 🟢 Live | Spanner, Pub/Sub (32 topics), gRPC, GCS/LFS — all operational |
| **Link Pipeline** | 🟢 Live | Fully deployed; link-registry + studio-link-evaluator + ecc-link-projector all live |
| **Rendering Pipeline** | 🟢 Live | Core path live; studio-renderer + ecc-renderer + esl-image-merger deployed |
| **Transmission & Edge Bridge** | 🟢 Live | dtoflow-transmission functional; cloud-to-edge bridge operational |
| **CQS (ChangeQueueService)** | 🟡 Nearing completion | R3Server client (PLT-1870, Daniel Pettersson) in Test; service-own-queues (PLT-2792) in progress |
| **Gateway & Routing** | 🟡 In progress | Apigee live; per-API-path routing (PLT-2101) not started |
| **Shadow Mode** | 🟡 In progress | PLT-2354 In Progress; data pipe PLT-2483 Ready for Deploy (Johan Ekman) |
| **Item Pipeline** | 🔴 Gated | 4 of 5 services built; blocked by item property validation (PLT-2651) |
| **Consumer APIs** | 🟡 Blocked | Items blocked; Plaza Mobile + Central-Manager still rely on R3Server |
| **First tenant migration** | 🟡 Not started | PLT-2601 in Backlog (Cristian Deaconeasa); candidates identified in [doc 14](14-tenant-migration.md) |

### Key End-to-End Flows

| Flow | Status | Detail |
|------|--------|--------|
| **Link Creation → Render → Transmit** | 🟢 Live | Strongest proof point. `link-registry` → evaluator + renderer (parallel) → merger → `dtoflow-transmission` → R3Server → ESL. |
| **Item Price Change → Render** | 🟡 Partially ready | Evaluator + renderer chain operational; gated by item property validation (PLT-2651) — item writes don't validate properties end-to-end. |
| **Item Deletion** | 🔴 Not built | Path not yet implemented. Item deletion doesn't flow through DTOflow. |

---

## 7. Risks & Immediate Actions

### Critical Blockers

| Risk | Epic | Severity | Action |
|------|------|----------|--------|
| **Item property validation** | PLT-2651 | 🔴 Critical | Unblock. 4 of 5 item pipeline services built; validation is the single clearest gate. |
| **Item Patch APIs unassigned** | PLT-2378 | 🔴 Critical | Assign an owner. Blocks both Plaza Mobile and Central-Manager item cutover. |

### High-Priority Risks

| Risk | Severity | Action |
|------|----------|--------|
| **Shadow Mode sub-tasks unassigned** — PLT-2495, 2492, 2488, 2714 need owners | 🟡 High | Assign before next sprint |
| **Bart De Boer owns 4+ critical epics** across W1, W2, W3, W5 | 🟡 High | Spread ownership; bus factor risk |
| **API routing not started** — PLT-2101, Saikiran on vacation | 🟡 Medium | Plan handover; this is the incremental migration mechanism |
| **First tenant selection in Backlog** — PLT-2601 slipped from Selected | 🟡 Medium | Drive criteria → decision; Phase 1 scope depends on it |
| **Review bottleneck** — 6+ items waiting for Johan Ekman | 🟡 Medium | Distribute review load |
| **Ops readiness entirely in Backlog** — W4 has 11 epics, none started | 🟡 Medium | Begin sequencing before any tenant cutover |

---

## 8. What's Next

In priority order:

1. **Unblock PLT-2651** (Item property validation) — the single clearest gate on item-driven migration.
2. **Assign an owner to PLT-2378** (Item Patch APIs) — gates both consumer API cutovers.
3. **Land PLT-2483** (storeitemvalues export) — Ready for Deploy; unblocks the Shadow Mode data pipe.
4. **Finish PLT-1870** (CQS client in R3Server) — in Test; completes the edge side of Shadow Mode.
5. **Certify PLT-2118** (DTOflow PROD-ready) — formal foundation certification.
6. **Drive PLT-2601** (First Tenant Selection) — from Backlog to decision; unlocks Phase 1 scope.

---

> **Refresh sources:**
> - GCP: `gcloud run services list --region=europe-north1 --project=platform-dev-p01`
> - Jira: `project = PLT AND issuetype = Epic AND labels in ("replatforming-phase-0","replatforming-phase-1","replatforming-phase-2") ORDER BY status ASC`
> - Confluence: [Replatforming Architecture Pipeline Status](https://pricer-org.atlassian.net/wiki/spaces/~71202026d6e29fd7314f1e915ad8754239598a/pages/10187767809/Replatforming+Architecture+Pipeline+Status)

---

### Related docs

- [14 — Tenant Migration Guide](14-tenant-migration.md)
- [19 — Dimension Frameworks](19-dimension-frameworks.md) — the analysis that produced this structure
- [17 — Phase 1 Plan](17-phase-1-plan.md)
