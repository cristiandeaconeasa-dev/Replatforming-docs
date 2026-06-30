# 19 — Dimension Frameworks: Rethinking How We Categorize the Replatforming Program

> **Scope:** The current 10 "Dimensions" in the Executive Summary ([doc 15](15-overall-status.md)) conflate infrastructure layers, data pipelines, operational processes, and consumer endpoints. This doc proposes three alternative frameworks, each from a different perspective, for CTO/PMO review.
>
> **Goal:** Evaluate the three frameworks — then pick one as the primary Executive Summary view and use the others for specialized audiences.

---

## 1. The Problem: Why "Dimensions" Don't Work Today

The current Executive Summary table has these 10 categories:

| # | Current "Dimension" | What it actually is |
|---|---------------------|---------------------|
| 1 | DTOflow Foundation | Infrastructure/platform layer |
| 2 | Link Pipeline | Functional data-flow pipeline |
| 3 | Rendering Pipeline | Functional data-flow pipeline |
| 4 | Transmission & Edge Bridge | Functional data-flow pipeline |
| 5 | CQS (ChangeQueueService) | Infrastructure/plumbing component |
| 6 | Gateway & Routing | Infrastructure/plumbing component |
| 7 | Shadow Mode | Operational cutover process / Phase 0 gate |
| 8 | Item Pipeline | Functional data-flow pipeline |
| 9 | Consumer APIs | Consumer/API endpoint layer |
| 10 | First tenant migration | Project/program phase gate |

**Three problems:**

1. **Mixed abstraction levels.** Some are architecture layers (Foundation, Gateway), some are data flows (Link Pipeline, Rendering Pipeline), some are project phases (Shadow Mode, First tenant migration). This makes it impossible to talk about them consistently.

2. **No one knows what to call them.** "Is it a layer? A domain? A capability?" Engineers, the CTO, and the PMO all use different mental models, so the same table means different things to different people.

3. **CQS is a single service, not a dimension.** It shouldn't sit alongside "Link Pipeline" (which spans 7 services and 11 epics). The table treats a plumbing component and an end-to-end value stream as equals.

**What we need:** A consistent organizing principle — a *perspective* — that groups epics by something meaningful and stable. Below are two candidates.

---

## 2. Framework A: "Delivery Workstreams" View

> **Perspective:** *What needs to be built & shipped* — organized by project milestone and business value delivery.
>
> **Best for:** CTO, PMO, Product Owners, anyone asking "what are we shipping next?"

### Why this works

- Aligns engineering work directly with business milestones (Phase 0 → Phase 1 → Phase 2).
- Makes blockers immediately obvious: "Foundation Enablers" not done → Phase 0 can't start. "Phase 0" not validated → Phase 1 blocked.
- Each category has a clear **completion gate** — you know when it's done.
- Speaks the language of roadmaps, sprint reviews, and executive briefings.

### What this hides

- The runtime architecture. You cannot look at this and understand how data flows through Spanner → Pub/Sub → CQS → services.
- Service dependencies within a workstream (e.g., that `item-registry` and `link-registry` share DTOflow infrastructure but are built by different teams).

### The Workstreams

| Workstream | Definition | Completion Gate | Epic Count |
|-----------|------------|-----------------|------------|
| **W1: Foundation Enablers** | Core infrastructure (Spanner, Pub/Sub, CQS, routing, PSC) that must exist before any traffic moves to the cloud | All Foundation services live + PROD-ready certified + per-API-path routing operational | 7 |
| **W2: Phase 0 — Shadow Mode** | All work to run the cloud pipeline in parallel with the edge, validating correctness without touching a single label | 24+ hrs on `Replatforming-Dev` with 100% rendered-image parity | 11 |
| **W3: Phase 1 — Consumer API Cutover** | Migrating item and link API traffic from R3Server to cloud services, one API path at a time | First real tenant (byPricer) live on cloud for basic item/link/rendering flows | 10 |
| **W4: Phase 1 — Production Operations** | Operational readiness: tenant selection, store onboarding, load testing, monitoring, DR, cutover runbooks | All ops gates passed; cutover procedure tested; tenant isolation validated | 11 |
| **W5: Phase 2 — Feature Parity & Scale** | Remaining features needed for full migration: timed updates, ECC sync, autoscaling, SLAs, webhooks, segment labels | All tenants migrated; feature parity with legacy R3Server achieved | 19 |

### Epic-to-Workstream Mapping

> Statuses from live Jira, 2026-06-30. ✅ = Closed, 🟢 = Deployed, 🟡 = In Progress/Test/Selected/Ready, 🔴 = Blocked, 🔵 = Backlog.

| Workstream | Epic | Status | Assignee | Summary |
|-----------|------|--------|----------|---------|
| **W1: Foundation Enablers** | PLT-2118 | 🟡 Test | Bart De Boer | DTOflow PROD-ready for Task & Scenario |
| | PLT-169 | 🟡 In Progress | Johan Ekman | ChangeQueueService |
| | PLT-2336 | 🟡 In Progress | Sreekanth Singapuram Uppara | DTOflow broadly accessible (PSC) |
| | PLT-2478 | 🟡 In Progress | Sreekanth Singapuram Uppara | PS↔CQS/DTOflow design |
| | PLT-2792 | 🟡 In Progress | Bart De Boer | Services own CQS queues |
| | PLT-2101 | 🟡 Selected | Saikiran Katta | Per-API-path routing |
| | PLT-2294 | ✅ Closed | Bart De Boer | ID & alias validation |
| | — (infra) | 🟢 Live | — | Spanner (29 tables), Pub/Sub (32 topics), gRPC, GCS/LFS, GKE `platform` |
| **W2: Phase 0 — Shadow Mode** | PLT-2354 | 🟡 In Progress | Daniel Pettersson | Shadow Mode orchestration |
| | PLT-1870 | 🟡 Test | Daniel Pettersson | CQS client in R3Server |
| | PLT-2483 | 🟡 Ready for Deploy | Johan Ekman | storeitemvalues export |
| | PLT-2496 | 🟡 Ready for Deploy | Unassigned | link export |
| | PLT-2494 | 🟡 In Progress | Johan Ekman | ECC params/images/models export |
| | PLT-2495 | 🟡 Selected | Unassigned | ECC fonts export |
| | PLT-2492 | 🟡 Selected | Unassigned | ESL Status DTO export |
| | PLT-2488 | 🟡 Selected | Unassigned | itemproperties export |
| | PLT-2714 | 🟡 Selected | Unassigned | itemproperties startup export |
| | PLT-2497 | ✅ Closed | Unassigned | consume-ignore-linked mode |
| | PLT-2353 | 🟡 In Progress | Bart De Boer | Pricer Server config export |
| **W3: Phase 1 — Consumer API Cutover** | PLT-2651 | 🔴 Blocked | Unassigned | Item property validation |
| | PLT-2378 | 🔴 Blocked | Unassigned | Item Patch APIs — Core |
| | PLT-2274 | 🔴 Blocked | Daniel Pettersson | SIC Support |
| | PLT-2598 | ✅ Closed | Unassigned | Initial Bulk Item Load (scope-out) |
| | PLT-2484 | 🟡 In Progress | Bart De Boer | Link v1 DTO refactor |
| | PLT-2773 | ✅ Closed | Johan Ekman | ECC Link Projector |
| | PLT-2771 | ✅ Closed | Unassigned | ESL Image Merger |
| | PLT-2577 | ✅ Closed | Unassigned | ESL registration in cloud |
| | PLT-2357 | 🟡 Selected | Unassigned | Linked Item APIs — Items |
| | PLT-2358 | 🟡 Selected | Unassigned | Linked Item APIs — Devices |
| **W4: Phase 1 — Production Operations** | PLT-2601 | 🔵 Backlog | Cristian Deaconeasa | First Tenant Selection |
| | PLT-2572 | 🔵 Backlog | Unassigned | Store Onboarding |
| | PLT-2575 | 🔵 Backlog | Unassigned | Store DTO Schema |
| | PLT-2578 | 🔵 Backlog | Unassigned | Tenant Isolation Validation |
| | PLT-2600 | 🔵 Backlog | Unassigned | Studio Services Prod-Readiness |
| | PLT-2576 | 🔵 Backlog | Unassigned | Performance & Load Testing |
| | PLT-2579 | 🔵 Backlog | Unassigned | Monitoring & Dashboards |
| | PLT-2580 | 🔵 Backlog | Unassigned | Disaster Recovery |
| | PLT-2599 | 🔵 Backlog | Unassigned | Cutover & Rollback Runbook |
| | PLT-2581 | 🔵 Backlog | Unassigned | Operational Runbooks |
| | PLT-2430 | 🔵 Backlog | Unassigned | Integration Tests Delivery 1 |
| **W5: Phase 2 — Feature Parity** | PLT-2350 | 🔵 Backlog | Unassigned | Timed Item Updates |
| | PLT-2351 | 🔵 Backlog | Unassigned | Item Ingest Status — Extended |
| | PLT-2352 | 🔵 Backlog | Unassigned | Item Ingest Status — Advanced |
| | PLT-2436 | 🔵 Backlog | Unassigned | Item/Link via PFI |
| | PLT-2359 | 🟡 In Progress | Bart De Boer | ECC Links & Rendering |
| | PLT-2361 | 🔵 Backlog | Unassigned | Segment Labels |
| | PLT-2360 | 🔵 Backlog | Unassigned | Unified Linking API |
| | PLT-2363 | 🔵 Backlog | Unassigned | Auto Unlink |
| | PLT-2573 | ✅ Closed | Unassigned | ECC Sync push (scope-out) |
| | PLT-2574 | ✅ Closed | Unassigned | Transmission service integration (scope-out — won't do; existing `dtoflow-transmission` covers this) |
| | PLT-2355 | 🟡 Selected | Bart De Boer | Label Status APIs |
| | PLT-2356 | 🔵 Backlog | Unassigned | Item Flash APIs |
| | PLT-171 | 🟡 Selected | Unassigned | SLA & trackingId support |
| | PLT-2444 | 🔵 Backlog | Unassigned | Status Reporting |
| | PLT-2369 | 🔵 Backlog | Unassigned | Auto-scaling |
| | PLT-170 | 🔵 Backlog | Unassigned | Write Protection |
| | PLT-2428 | 🔵 Backlog | Unassigned | Subscription System |
| | PLT-2440 | 🔵 Backlog | Unassigned | Webhook Events |
| | PLT-2362 | 🔵 Backlog | Unassigned | GeoPos Support |

> **Note:** PLT-2359 (ECC Links & Rendering) is marked "In Progress" but placed in W5 (Phase 2). This is intentional: Bart De Boer is building ECC parity in parallel with Phase 0/1 work, but ECC rendering is explicitly scoped to Phase 2 — the first real tenant will use Studio rendering only. The CTO should read this as "early progress on a Phase 2 capability," not "Phase 2 work blocking Phase 1."

---

## 3. Framework B: "System Capability" View

> **Perspective:** *What the system does* — organized by data value streams through the event-driven architecture.
>
> **Best for:** Lead Engineers, Architects, integration teams, anyone asking "how does the data flow?"

### Why this works

- Maps directly to the DTOflow event-driven model: Item → Link → Render → Transmit.
- Groups services that share Pub/Sub subscriptions and DTO types (e.g., evaluator and renderer both subscribe to `storeitemvalues.v1`).
- Separates the "input" (Item Management), the "processing" (Linking & Rendering), and the "output" (Edge Bridging).
- Makes it easy to spot gaps in a data value stream: "Item Management" is gated → everything downstream is blocked.

### What this hides

- Timeline and project phases. You cannot tell from this view if a capability is needed for Phase 0, Phase 1, or Phase 2.
- Operational readiness gets lumped into a catch-all "Ops Lifecycle" bucket that doesn't reflect its critical gating role before any tenant cutover.

### The Capabilities

| Capability | Definition | Services Involved | Epic Count |
|-----------|------------|-------------------|------------|
| **C1: Distributed Data & Routing Fabric** | Infrastructure that everything else depends on: Spanner, Pub/Sub, CQS, ingress, PSC, auth, scaling | `dtoflow-spanner`, `dtoflow-lfs`, CQS (GKE), Apigee, ingress-nginx | 11 |
| **C2: Item Data Management** | Ingesting, validating, patching, and storing ERP item/price data as `storeitemvalues` DTOs | `item-registry-api`, `item-registry` | 8 |
| **C3: Linking & Parallel Rendering** | Core business logic: mapping items to ESLs, evaluating CEL rules, rendering images, merging Studio+ECC outputs | `link-registry`, `link-bfg`, `studio-link-evaluator`, `studio-renderer`, `studio-design-library`, `ecc-renderer`, `ecc-link-projector`, `esl-image-merger` | 10 |
| **C4: Edge Bridging & Execution** | Cloud-to-device communication: transmission, real-time flash, label status, config sync, Shadow Mode data pipes | `dtoflow-transmission`, R3Server (thin edge) | 17 |
| **C5: Tenant Isolation & Ops Lifecycle** | Provisioning, onboarding, security boundaries, load testing, monitoring, DR, cutover runbooks | N/A (operational) | 12 |

### Epic-to-Capability Mapping

| Capability | Epic | Status | Assignee | Summary |
|-----------|------|--------|----------|---------|
| **C1: Data & Routing Fabric** | PLT-2118 | 🟡 Test | Bart De Boer | DTOflow PROD-ready |
| | PLT-169 | 🟡 In Progress | Johan Ekman | ChangeQueueService |
| | PLT-2336 | 🟡 In Progress | Sreekanth Singapuram Uppara | DTOflow broadly accessible (PSC) |
| | PLT-2294 | ✅ Closed | Bart De Boer | ID & alias validation |
| | PLT-171 | 🟡 Selected | Unassigned | SLA & trackingId support |
| | PLT-170 | 🔵 Backlog | Unassigned | Write Protection |
| | PLT-2444 | 🔵 Backlog | Unassigned | Status Reporting |
| | PLT-2369 | 🔵 Backlog | Unassigned | Auto-scaling |
| | PLT-2101 | 🟡 Selected | Saikiran Katta | Per-API-path routing |
| | PLT-2478 | 🟡 In Progress | Sreekanth Singapuram Uppara | PS↔CQS/DTOflow design |
| | PLT-2792 | 🟡 In Progress | Bart De Boer | Services own CQS queues |
| | — (infra) | 🟢 Live | — | Spanner (29 tables), Pub/Sub (32 topics), GCS/LFS, GKE, Apigee, ingress |
| **C2: Item Data Management** | PLT-2378 | 🔴 Blocked | Unassigned | Item Patch APIs — Core |
| | PLT-2651 | 🔴 Blocked | Unassigned | Item property validation |
| | PLT-2274 | 🔴 Blocked | Daniel Pettersson | SIC Support |
| | PLT-2598 | ✅ Closed | Unassigned | Initial Bulk Item Load (scope-out) |
| | PLT-2350 | 🔵 Backlog | Unassigned | Timed Item Updates |
| | PLT-2351 | 🔵 Backlog | Unassigned | Item Ingest Status — Extended |
| | PLT-2352 | 🔵 Backlog | Unassigned | Item Ingest Status — Advanced |
| | PLT-2436 | 🔵 Backlog | Unassigned | Item/Link via PFI |
| | — (infra) | 🟢 Live | — | `item-registry-api`, `item-registry` (4 of 5 built) |
| **C3: Linking & Rendering** | PLT-2484 | 🟡 In Progress | Bart De Boer | Link v1 DTO refactor |
| | PLT-2359 | 🟡 In Progress | Bart De Boer | ECC Links & Rendering |
| | PLT-2361 | 🔵 Backlog | Unassigned | Segment Labels |
| | PLT-2360 | 🔵 Backlog | Unassigned | Unified Linking API |
| | PLT-2363 | 🔵 Backlog | Unassigned | Auto Unlink |
| | PLT-2771 | ✅ Closed | Unassigned | ESL Image Merger |
| | PLT-2773 | ✅ Closed | Johan Ekman | ECC Link Projector |
| | PLT-2357 | 🟡 Selected | Unassigned | Linked Item APIs — Items |
| | PLT-2358 | 🟡 Selected | Unassigned | Linked Item APIs — Devices |
| | PLT-2600 | 🔵 Backlog | Unassigned | Studio Services Prod-Readiness |
| | — (infra) | 🟢 Live | — | `link-registry`, `link-bfg`, `studio-renderer`, `studio-link-evaluator`, `studio-design-library`, `studio-scenario-library`, `ecc-renderer`, `ecc-link-projector`, `esl-image-merger` |
| **C4: Edge Bridging & Execution** | PLT-1870 | 🟡 Test | Daniel Pettersson | CQS client in R3Server |
| | PLT-2354 | 🟡 In Progress | Daniel Pettersson | Shadow Mode orchestration |
| | PLT-2353 | 🟡 In Progress | Bart De Boer | Pricer Server config export |
| | PLT-2573 | ✅ Closed | Unassigned | ECC Sync push (scope-out) |
| | PLT-2577 | ✅ Closed | Unassigned | ESL registration in cloud |
| | PLT-2574 | ✅ Closed | Unassigned | Transmission service integration (scope-out — won't do) |
| | PLT-2356 | 🔵 Backlog | Unassigned | Item Flash APIs |
| | PLT-2362 | 🔵 Backlog | Unassigned | GeoPos Support |
| | PLT-2355 | 🟡 Selected | Bart De Boer | Label Status APIs |
| | PLT-2483 | 🟡 Ready for Deploy | Johan Ekman | storeitemvalues export (Shadow Mode pipe) |
| | PLT-2496 | 🟡 Ready for Deploy | Unassigned | link export (Shadow Mode pipe) |
| | PLT-2494 | 🟡 In Progress | Johan Ekman | ECC params export (Shadow Mode pipe) |
| | PLT-2495 | 🟡 Selected | Unassigned | ECC fonts export (Shadow Mode pipe) |
| | PLT-2492 | 🟡 Selected | Unassigned | ESL Status export (Shadow Mode pipe) |
| | PLT-2488 | 🟡 Selected | Unassigned | itemproperties export (Shadow Mode pipe) |
| | PLT-2714 | 🟡 Selected | Unassigned | itemproperties startup export (Shadow Mode pipe) |
| | PLT-2497 | ✅ Closed | Unassigned | consume-ignore-linked mode |
| | — (infra) | 🟢 Live | — | `dtoflow-transmission`, R3Server (thin edge, stays on-prem) |
| **C5: Ops Lifecycle** | PLT-2601 | 🔵 Backlog | Cristian Deaconeasa | First Tenant Selection |
| | PLT-2572 | 🔵 Backlog | Unassigned | Store Onboarding |
| | PLT-2575 | 🔵 Backlog | Unassigned | Store DTO Schema |
| | PLT-2578 | 🔵 Backlog | Unassigned | Tenant Isolation Validation |
| | PLT-2576 | 🔵 Backlog | Unassigned | Performance & Load Testing |
| | PLT-2579 | 🔵 Backlog | Unassigned | Monitoring & Dashboards |
| | PLT-2580 | 🔵 Backlog | Unassigned | Disaster Recovery |
| | PLT-2599 | 🔵 Backlog | Unassigned | Cutover & Rollback Runbook |
| | PLT-2581 | 🔵 Backlog | Unassigned | Operational Runbooks |
| | PLT-2430 | 🔵 Backlog | Unassigned | Integration Tests Delivery 1 |
| | PLT-2428 | 🔵 Backlog | Unassigned | Subscription System |
| | PLT-2440 | 🔵 Backlog | Unassigned | Webhook Events |

---

## 4. Framework C: "Hierarchical Workstream → Capability" View

> **Perspective:** *A two-level hierarchy combining when it ships (Workstream) with what it does (Capability).*
>
> **Best for:** All audiences — the CTO scans the Workstream level; engineers drill into the Capability level; the PMO tracks both. This is the single view that replaces Frameworks A and B.

### Why this works

Framework A answers "when" but hides architecture. Framework B answers "what" but hides timeline. Framework C merges them:

- **Level 1 (Workstream):** Shows sequencing and gates — W1 must finish before W2, W2 gates W3, etc.
- **Level 2 (Capability):** Shows what system layer each epic contributes to — C1 (Fabric), C2 (Items), C3 (Linking/Rendering), C4 (Edge), C5 (Ops).
- A CTO can read the bold workstream headers and get the timeline. An engineer can scan the capability sub-headers and understand the architecture impact.
- Cross-cutting relationships become visible: C4 (Edge Bridging) appears in W2, W3, and W5 — you can see the Edge story evolving across phases.

### What this hides

- Nothing material that Frameworks A and B didn't already hide individually. The tradeoff is that the table is longer — but the hierarchical structure makes it scannable.

### The Hierarchy

| Workstream | Capabilities Delivered | Epic Count |
|-----------|----------------------|------------|
| **W1: Foundation Enablers** | C1 (Data & Routing Fabric) | 7 |
| **W2: Phase 0 — Shadow Mode** | C4 (Edge Bridging & Execution) | 11 |
| **W3: Phase 1 — Consumer API Cutover** | C2 (Item Data Management), C3 (Linking & Rendering), C4 (Edge Bridging) | 10 |
| **W4: Phase 1 — Production Operations** | C3 (Linking & Rendering — Studio prod-readiness certification), C5 (Ops Lifecycle) | 11 |
| **W5: Phase 2 — Feature Parity & Scale** | C1, C2, C3, C4, C5 (all capabilities) | 19 |

### Two-Level Epic Mapping

> Statuses from live Jira, 2026-06-30. ✅ = Closed, 🟢 = Deployed, 🟡 = In Progress/Test/Selected/Ready, 🔴 = Blocked, 🔵 = Backlog.
>
> **Reading guide:** **Bold** = Workstream header (when it ships). *Italic* = Capability sub-header (what system layer). Plain rows = epics.

| Workstream / Capability | Epic | Status | Assignee | Summary |
|-------------------------|------|--------|----------|---------|
| **W1: Foundation Enablers** | | | | |
| *C1: Data & Routing Fabric* | PLT-2118 | 🟡 Test | Bart De Boer | DTOflow PROD-ready for Task & Scenario |
| | PLT-169 | 🟡 In Progress | Johan Ekman | ChangeQueueService |
| | PLT-2336 | 🟡 In Progress | Sreekanth Singapuram Uppara | DTOflow broadly accessible (PSC) |
| | PLT-2478 | 🟡 In Progress | Sreekanth Singapuram Uppara | PS↔CQS/DTOflow design |
| | PLT-2792 | 🟡 In Progress | Bart De Boer | Services own CQS queues |
| | PLT-2101 | 🟡 Selected | Saikiran Katta | Per-API-path routing |
| | PLT-2294 | ✅ Closed | Bart De Boer | ID & alias validation |
| | — (infra) | 🟢 Live | — | Spanner (29 tables), Pub/Sub (32 topics), gRPC, GCS/LFS, GKE `platform` |
| **W2: Phase 0 — Shadow Mode** | | | | |
| *C4: Edge Bridging & Execution* | PLT-2354 | 🟡 In Progress | Daniel Pettersson | Shadow Mode orchestration |
| | PLT-1870 | 🟡 Test | Daniel Pettersson | CQS client in R3Server |
| | PLT-2483 | 🟡 Ready for Deploy | Johan Ekman | storeitemvalues export (data pipe) |
| | PLT-2496 | 🟡 Ready for Deploy | Unassigned | link export (data pipe) |
| | PLT-2494 | 🟡 In Progress | Johan Ekman | ECC params/images/models export (data pipe) |
| | PLT-2495 | 🟡 Selected | Unassigned | ECC fonts export (data pipe) |
| | PLT-2492 | 🟡 Selected | Unassigned | ESL Status DTO export (data pipe) |
| | PLT-2488 | 🟡 Selected | Unassigned | itemproperties export (data pipe) |
| | PLT-2714 | 🟡 Selected | Unassigned | itemproperties startup export (data pipe) |
| | PLT-2497 | ✅ Closed | Unassigned | consume-ignore-linked mode (enabler) |
| | PLT-2353 | 🟡 In Progress | Bart De Boer | Pricer Server config export (enabler) |
| **W3: Phase 1 — Consumer API Cutover** | | | | |
| *C2: Item Data Management* | PLT-2651 | 🔴 Blocked | Unassigned | Item property validation |
| | PLT-2378 | 🔴 Blocked | Unassigned | Item Patch APIs — Core |
| | PLT-2274 | 🔴 Blocked | Daniel Pettersson | SIC Support |
| | PLT-2598 | ✅ Closed | Unassigned | Initial Bulk Item Load (scope-out) |
| *C3: Linking & Parallel Rendering* | PLT-2484 | 🟡 In Progress | Bart De Boer | Link v1 DTO refactor |
| | PLT-2773 | ✅ Closed | Johan Ekman | ECC Link Projector |
| | PLT-2771 | ✅ Closed | Unassigned | ESL Image Merger |
| | PLT-2357 | 🟡 Selected | Unassigned | Linked Item APIs — Items |
| | PLT-2358 | 🟡 Selected | Unassigned | Linked Item APIs — Devices |
| *C4: Edge Bridging & Execution* | PLT-2577 | ✅ Closed | Unassigned | ESL registration in cloud |
| **W4: Phase 1 — Production Operations** | | | | |
| *C3: Linking & Parallel Rendering* | PLT-2600 | 🔵 Backlog | Unassigned | Studio Services Prod-Readiness |
| *C5: Tenant Isolation & Ops Lifecycle* | PLT-2601 | 🔵 Backlog | Cristian Deaconeasa | First Tenant Selection |
| | PLT-2572 | 🔵 Backlog | Unassigned | Store Onboarding |
| | PLT-2575 | 🔵 Backlog | Unassigned | Store DTO Schema |
| | PLT-2578 | 🔵 Backlog | Unassigned | Tenant Isolation Validation |
| | PLT-2576 | 🔵 Backlog | Unassigned | Performance & Load Testing |
| | PLT-2579 | 🔵 Backlog | Unassigned | Monitoring & Dashboards |
| | PLT-2580 | 🔵 Backlog | Unassigned | Disaster Recovery |
| | PLT-2599 | 🔵 Backlog | Unassigned | Cutover & Rollback Runbook |
| | PLT-2581 | 🔵 Backlog | Unassigned | Operational Runbooks |
| | PLT-2430 | 🔵 Backlog | Unassigned | Integration Tests Delivery 1 |
| **W5: Phase 2 — Feature Parity & Scale** | | | | |
| *C1: Data & Routing Fabric* | PLT-171 | 🟡 Selected | Unassigned | SLA & trackingId support |
| | PLT-2444 | 🔵 Backlog | Unassigned | Status Reporting |
| | PLT-2369 | 🔵 Backlog | Unassigned | Auto-scaling |
| | PLT-170 | 🔵 Backlog | Unassigned | Write Protection |
| *C2: Item Data Management* | PLT-2350 | 🔵 Backlog | Unassigned | Timed Item Updates |
| | PLT-2351 | 🔵 Backlog | Unassigned | Item Ingest Status — Extended |
| | PLT-2352 | 🔵 Backlog | Unassigned | Item Ingest Status — Advanced |
| | PLT-2436 | 🔵 Backlog | Unassigned | Item/Link via PFI |
| *C3: Linking & Parallel Rendering* | PLT-2359 | 🟡 In Progress | Bart De Boer | ECC Links & Rendering |
| | PLT-2361 | 🔵 Backlog | Unassigned | Segment Labels |
| | PLT-2360 | 🔵 Backlog | Unassigned | Unified Linking API |
| | PLT-2363 | 🔵 Backlog | Unassigned | Auto Unlink |
| *C4: Edge Bridging & Execution* | PLT-2573 | ✅ Closed | Unassigned | ECC Sync push (scope-out) |
| | PLT-2574 | ✅ Closed | Unassigned | Transmission service integration (scope-out — won't do) |
| | PLT-2355 | 🟡 Selected | Bart De Boer | Label Status APIs |
| | PLT-2356 | 🔵 Backlog | Unassigned | Item Flash APIs |
| | PLT-2362 | 🔵 Backlog | Unassigned | GeoPos Support |
| *C5: Tenant Isolation & Ops Lifecycle* | PLT-2428 | 🔵 Backlog | Unassigned | Subscription System |
| | PLT-2440 | 🔵 Backlog | Unassigned | Webhook Events |

> **Note:** PLT-2359 (ECC Links & Rendering) is marked "In Progress" in W5 (Phase 2). Bart De Boer is building ECC parity early, but ECC rendering is explicitly scoped to Phase 2 — the first real tenant will use Studio rendering only. The CTO should read this as "early progress on a Phase 2 capability," not "Phase 2 work blocking Phase 1."

---

## 5. Comparison: Which Framework When

| Question | Framework A (Workstreams) | Framework B (Capabilities) | Framework C (Hierarchical) |
|----------|---------------------------|----------------------------|----------------------------|
| "What ships next?" | ✅ Clear — W1 → W2 → W3 | ❌ Cannot tell phase | ✅ Workstream headers give timeline |
| "What blocks Phase 1?" | ✅ W3 blockers are red | ❌ Blocks spread across C2/C3/C4 | ✅ W3 blockers are red, C2 sub-header adds context |
| "How does data flow?" | ❌ Hides architecture | ✅ Maps to Spanner → Pub/Sub → CQS | ✅ Capability sub-headers show architecture |
| "Which services share dependencies?" | ❌ Grouped by milestone | ✅ C2/C3/C4 map to DTO subscriptions | ✅ Same as B, with workstream context |
| "Are we ready for a tenant?" | ✅ W4 is the ops gate | ❌ Ops is one equal bucket | ✅ W4 header + C5 sub-header = ops gate visible |
| **Best for** | CTO, PMO, roadmap reviews | Engineers, architects, onboarding | **All audiences — the single source of truth** |

---

## 6. Recommendation

**Use Framework C (Hierarchical Workstream → Capability) as the primary Executive Summary view.**

Rationale:
- Framework C is not a third choice — it is the unification of A and B. It's what Framework A should have been: workstream-organized, but with the architectural clarity of Framework B baked into the drill-down.
- The CTO scans the bold workstream headers and sees the timeline. An engineer scans the italic capability sub-headers and sees system impact. The PMO tracks both. No one needs to switch frameworks.
- Frameworks A and B remain useful as simplified standalone views for specific audiences (roadmap-only for the board, architecture-only for an integration workshop). But the Executive Summary deserves the full picture.
- The current mixed-bag dimensions fail because they have neither a timeline nor an architecture — they're just a list of things. Framework C fixes both problems at once.

**If Framework C is too rich for an executive summary slide, Framework A is the best simplified fallback. Framework B should be used in the architecture deep-dive docs ([doc 13](13-core-data-flows.md), [doc 08](08-dtoflow-deep-dive.md)).**

**Next step:** Present all three to the CTO. If Framework C is approved, update [doc 15](15-overall-status.md) to use the Hierarchical Workstream → Capability view as the primary Executive Summary table.

---

> **Coverage:** 42 of 42 labeled Replatforming epics are covered across the three frameworks. The following Phase 2 placeholder epics (from the Epics Grouped Overview) are intentionally omitted from both frameworks because their scope is not yet defined by the PMO — they should be added when scoped: PLT-2429 (Prometheus Metrics), PLT-2431 (Integration Tests Delivery 2), PLT-2364 (Jasper Reports), PLT-2365 (Timeline Support), PLT-2427 (Configuration Management).
>
> **Status legend:** ✅ Closed = done · 🟢 Live = deployed · 🟡 In Progress/Test/Selected/Ready for Deploy = active · 🔴 Blocked = gated · 🔵 Backlog = not started
