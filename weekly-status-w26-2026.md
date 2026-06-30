# Replatforming — Architecture & Pipeline Status
> **Week 26, 2026** (June 24)  
> **2026-06-29 correction:** CQS section retitled from "Orchestrator" to "Subscription Fan-Out". Flow descriptions updated to show parallel subscriber model (evaluator + renderer both notified, not sequential CQS→evaluator→renderer).

---

## Pipeline Maturity at a Glance

| Pipeline | Status | What's Missing |
|----------|--------|----------------|
| DTOflow Foundation | ✅ **Live** | Nothing. Spanner, Pub/Sub, gRPC all operational |
| Link Pipeline | ✅ **Live** | Everything deployed. link-registry, link-bfg, link-storeasset-bfg, studio-link-evaluator |
| Rendering Pipeline | ✅ **Live** | studio-renderer, studio-design-library, ecc-renderer all live. 2 new services in review |
| Transmission & Edge Bridge | ✅ **Live** | dtoflow-transmission, ESL registration, transmission integration done |
| CQS Subscription Fan-Out | 🟡 **Nearing completion** | Core CQS running. R3Server client in Test. Services-own-queues building |
| Gateway & Routing | 🟡 **In Progress** | Apigee live for new integrations. PLT-2101 (per-API-path routing) not started |
| Shadow Mode | 🟡 **In Progress** | Data pipe (PLT-2483) in Code Review. CQS client in Test. 5 export tasks defined |
| Item Pipeline | 🔴 **Gated** | 4 of 5 services built. WAITING ON: property validation (PLT-2651) |
| Consumer APIs (Plaza Mobile / Central Manager) | 🟡 **Blocked on Item Pipeline** | Items blocked. Flash, map, display-page stay on R3Server |

---

## Key End-to-End Flows

Three user-observable flows define the platform. Each exercises a different subset of the pipelines below.

### Flow 1: Item Price Change → Label Updates on Shelf

The most common retail operation. A store manager changes a price; the label must update in seconds.

```
ERP / Plaza Mobile → Gateway → item-registry-api → Spanner (storeitemvalues write)
  → Pub/Sub fans out to all subscribers (via CQS) → studio-link-evaluator and studio-renderer both notified in parallel
  → studio-renderer (render new label image)
  → dtoflow-transmission → R3Server (edge) → Basestation → ESL updates
```

**Status:** 🟡 Item-registry API built. Gated by property validation (PLT-2651). Link evaluator, renderer, transmission all live.

### Flow 2: Link Creation → New Label Design on Shelf

A designer in Studio creates a new link between an item and a label design. The rendered label appears on the shelf.

```
Studio/Designer → Apigee → studio-link-evaluator (evaluate link)
  → Pub/Sub → studio-renderer (render design + item data) → Spanner (renderedimage write)
  → Pub/Sub → dtoflow-transmission → R3Server → ESL
```

**Status:** ✅ End-to-end live. studio-link-evaluator, studio-renderer, and dtoflow-transmission all operational. New ecc-link-projector service in Code Review extends coverage.

### Flow 3: Item Deletion → Label Clears from Shelf

An item is removed from the assortment. The label must show "item removed" or clear.

```
ERP/Plaza Mobile → Gateway → item-registry-api → Spanner (storeitemvalues delete/tombstone)
  → Pub/Sub → link-registry (find associated links)
  → studio-link-evaluator (re-evaluate) → studio-renderer (render cleared label)
  → dtoflow-transmission → R3Server → ESL clears
```

**Status:** 🔴 Item DELETE path not yet built. Same gate as Flow 1 (PLT-2651 / PLT-2378). Link lookup and re-render path is live once item-registry accepts the DELETE.

---

## 1. Pipeline Maturity

### DTOflow Foundation
**What it is:** Shared data backbone — Spanner storage, Pub/Sub event bus, gRPC clients, LFS for large files. Every pipeline depends on this.

| Component | Status | Notes |
|-----------|--------|-------|
| Spanner instance `dtoflow` | ✅ Live | 29 DTO tables. Database `item-registry` also live |
| Pub/Sub messaging | ✅ Live | 32 topics. Per-DTO change topics created |
| gRPC clients (Java + Node) | ✅ Live | Auto-generated client libraries available |
| LFS (GCS-backed file storage) | ✅ Live | Large blob storage operational |
| DTOflow PROD-ready (PLT-2118) | 🟡 In Test | Bart De Boer. Final validation before declaring production-ready |

**Missing:** Nothing. Foundation is the most mature layer.

---

### Item Pipeline
**What it does:** Accept item writes from clients, store in Spanner, emit change events for downstream processing.

| Service | Status | Notes |
|---------|--------|-------|
| `item-registry-api` (REST/gRPC endpoint) | 🟡 Partially built | Endpoints and business logic written (PLT-2510), waiting on validation |
| `item-registry` (state machine worker) | 🟡 Partially built | Split into 2 deployments designed (PLT-2512) |
| Store DTOs for multistore requests | 🟡 Partially built | PLT-2526 ready, depends on deployment split |
| GCP infrastructure | ✅ Done | PLT-2511 — Daniel Pettersson. Networking and Cloud Run setup complete |
| Item property validation (PLT-2651) | 🔴 Blocked & Unassigned | Item-registry accepts any custom property without validation. Must be built before APIs can accept data safely. **ROOT BLOCKER for entire pipeline** |
| Populate SICs in registry (PLT-2587) | 🟡 Written, not deployed | Ready for Test. Depends on upstream pipeline |

**End-to-end state:** 4 of 5 services built but waiting on one gate: property validation. Once PLT-2651 (currently **Blocked and Unassigned**) is implemented, the full chain can flow through Test.

---

### Link Pipeline
**What it does:** Manage item-to-label associations. Determine which labels need updating when an item changes.

| Service | Status | Notes |
|---------|--------|-------|
| `link-registry` | ✅ Live | Core link storage and retrieval |
| `link-bfg` (bulk operations) | ✅ Live | Batch link processing |
| `link-storeasset-bfg` | ✅ Live | Store-asset link operations |
| `studio-link-evaluator` | ✅ Live | Evaluates which links are affected by item changes |

**End-to-end state:** ✅ Fully live. Link pipeline is operational.

---

### Rendering Pipeline
**What it does:** Convert item data + design templates into ESL label images.

| Service | Status | Notes |
|---------|--------|-------|
| `studio-renderer` | ✅ Live | Core label image rendering |
| `studio-design-library` | ✅ Live | Design template storage |
| `studio-scenario-library` | ✅ Live | Scenario management |
| `studio-link-evaluator` | ✅ Live | Links evaluation |
| `ecc-renderer` | ✅ Live | ECC label rendering |
| `ecc-link-projector` | ✅ Live | Merged 2026-06-23 (Johan Ekman) |
| `esl-image-merger` | ✅ Live | Merged 2026-06-23 (Johan Ekman) |

**End-to-end state:** ✅ Fully live. Two new services (ecc-link-projector, esl-image-merger) in Code Review — once merged, rendering coverage increases.

---

### CQS — Subscription Fan-Out
**What it does:** Consumes Pub/Sub change events and delivers notifications to subscribed service queues. Services self-configure their subscriptions — CQS has no routing logic of its own.

| Component | Status | Notes |
|-----------|--------|-------|
| ChangeQueueService (PLT-169) | 🟡 In Progress | Johan Ekman. GKE cluster `platform` running |
| Services own CQS queues (PLT-2792) | 🟡 In Progress | Bart De Boer. New pattern — each service manages its own queue |
| CQS client in R3Server (PLT-1870) | 🟡 In Test | Daniel Pettersson. Enables R3Server to receive work from CQS |
| PS↔CQS design (PLT-2478) | 🟡 In Progress | Sreekanth S.U. Integration design between Pricer Server and CQS |

**End-to-end state:** Core CQS running. Client integration (R3Server side) in Test. Services-own-queues pattern being built. Nearing completion.

---

### Transmission & Edge Bridge
**What it does:** Cloud-to-store delivery of rendered images + commands. The seam between cloud and physical ESLs.

| Component | Status | Notes |
|-----------|--------|-------|
| `dtoflow-transmission` (Cloud Run) | ✅ Live | Cloud-side bridge service operational |
| `migration-helper` (Cloud Run) | ✅ Live | Merged 2026-06-23 (Johan Ekman) |
| R3Server transmission engine | ✅ Stays on edge | Not migrating. IR/RF radio control stays in-store |
| ESL registration in cloud (PLT-2577) | ✅ Closed | ESL labels can register via cloud services |
| Transmission integration (PLT-2574) | ✅ Closed | Cloud pipeline connected to on-prem path |

**End-to-end state:** ✅ Cloud-to-edge bridge is live. Transmission path is operational.

---

### Gateway & Routing
**What it does:** Entry points for client traffic. Routes requests to the correct cloud service or back to R3Server.

| Component | Status | Notes |
|-----------|--------|-------|
| Apigee gateway | ✅ Live | Routes newer integrations (Designer, studio, actions) |
| PSC (Private Service Connect) — PLT-2336 | 🟡 In Progress | Sreekanth S.U. Broadening DTOflow accessibility through private networking |
| Per-API-path routing (PLT-2101) | 🔵 Selected | Saikiran Katta. Not yet started (on vacation). This is the mechanism that makes migration incremental — flip one API path to cloud, validate, roll back if needed |

**End-to-end state:** Apigee path live. The incremental routing mechanism (PLT-2101) not yet implemented — without it, migrations are all-or-nothing per store.

---

### Shadow Mode (Cross-Pipeline Validation)
**What it is:** Runs the entire cloud pipeline in parallel without sending data to real ESLs. Proves the system works before any customer impact.

| Component | Status | Notes |
|-----------|--------|-------|
| Realtime storeitemvalues export (PLT-2483) | 🟡 Code Review | Johan Ekman. The data pipe from R3Server → DTOflow |
| Realtime link export (PLT-2496) | 🟡 Code Review | Unassigned. Link data export parallel path |
| CQS client in R3Server (PLT-1870) | 🟡 Test | Daniel Pettersson. R3Server consumes cloud work |
| Consume-ignore-linked mode (PLT-2497) | ✅ Done | R3Server can consume cloud data and ignore links in Shadow Mode |
| Export ECC (PLT-2494, 2495) | 🔵 Defined | Selected but not started |
| Output ESL Status DTO (PLT-2492) | 🔵 Defined | Selected but not started |
| Export itemproperties (PLT-2488, 2714) | 🔵 Defined | Selected but not started |

**End-to-end state:** Shadow Mode has its data pipe in Code Review and CQS client in Test. The 5 "export" sub-tasks are defined but not yet started. One reviewer assignment on PLT-2483 would move the critical path forward.

---

### Consumer APIs (What Clients Call)

| Client | Cloud | R3Server (stays) | Migration Status |
|--------|-------|------------------|------------------|
| **Plaza Mobile** | Items (after PLT-2378), search (item-registry-api) | Flash, map, display-page, link-departments | 🟡 Item blocked on PLT-2651 |
| **Central-Manager** | Multi-store items (after PLT-2378), CSV | Store lifecycle, Store-Host | 🟡 Item blocked same epic |
| **Store UI** | Everything (EVO Store Service) | Nothing | ✅ Already cloud |
| **Plaza Actions** | Everything (Apigee) | Nothing | ✅ Already cloud |

---

## 2. What's Moving This Week

| Item | Stage | Who | What Unlocks |
|------|-------|-----|--------------|
| **PLT-2118** (DTOflow PROD-ready) | Test → Done | Bart De Boer | Foundation certified production-ready |
| **PLT-1870** (CQS client in R3Server) | Test → Done | Daniel Pettersson | R3Server can receive cloud work |
| **PLT-2483** (storeitemvalues export) | Code Review → Test | Needs reviewer | Shadow Mode data pipe |
| **3 new services** (ecc-link-projector, esl-image-merger, migration-helper) | Code Review → Live | Merged 2026-06-23 | All 3 Cloud Run services now live |
| **PLT-2651** (item property validation) | Blocked / Unassigned | Needs implementer | ROOT BLOCKER: Gates entire Item Pipeline |

---

## 3. Completed Since Last Report

| Delivery | Pipeline | Impact |
|----------|----------|--------|
| Tenant-id check on all DTOflow servers (PLT-1996) | Foundation | Cross-tenant isolation enforced |
| ID & alias validation (PLT-2294) | Foundation | Data integrity on all writes |
| ECC sync — on-prem to cloud push (PLT-2573) | Rendering | ECC labels can render in cloud |
| Transmission integration (PLT-2574) | Edge Bridge | Cloud → store delivery path live |
| ESL registration in cloud (PLT-2577) | Edge Bridge | Labels register via cloud |
| Bulk item load for tenant onboarding (PLT-2598) | Item Pipeline | Initial load path exists |
| Consume-ignore-linked mode (PLT-2497) | Shadow Mode | R3Server can run in parallel |
| GCP resources for item-registry (PLT-2511) | Item Pipeline | Infrastructure ready for 4 downstream stories |
| Add eccmodel-id alias on (ecc) link DTO (PLT-2499) | Rendering | Support for ECC models |
| Adapt & Solidify ECC rendering service (PLT-2493) | Rendering | Enhanced ECC rendering |
| Design storeesl + image => Ps => label-status data loop (PLT-2487) | Rendering | Feedback loop designed |
| Design Storeesl Status DTO (PLT-2646) | Edge Bridge | Formalize ESL status communication |
| Define store-itemproperties DTO (PLT-2690) | Item Pipeline | Property definition schema established |

---

## 4. Immediate Priorities

1. **Review PLT-2483** — storeitemvalues export is the Shadow Mode data pipe. Needs a reviewer to move to Test
2. **Implement PLT-2651** — item property validation gates the entire Item Pipeline. Single story, well-scoped
3. **Push PLT-1870 through Test** — CQS client in R3Server. Nearing completion
4. **Push PLT-2118 through Test** — DTOflow production certification
5. **Review 3 new services** — code already written, needs eyes