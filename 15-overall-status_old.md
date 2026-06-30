# 15 — Overall Status: Replatforming Architecture & Pipeline

> **Scope:** Executive-level status of the entire Replatforming program — Cloud Run services, key end-to-end flows, epic backlog, blockers, and next milestones.
>
> **Validated:** 2026-06-30 — against live GCP (`platform-dev-p01`, `europe-north1`), GitHub (`PricerAB` org), Jira (`project = PLT`), the `evo-dtoflow-protos` central-documentation branch, and the [Confluence Architecture & Pipeline Status page](https://pricer-org.atlassian.net/wiki/spaces/~71202026d6e29fd7314f1e915ad8754239598a/pages/10187767809/Replatforming+Architecture+Pipeline+Status) (last updated 2026-06-25).
>
> **2026-06-30 delta vs Confluence:** The three "in review" services on the Confluence page (ecc-link-projector, esl-image-merger, migration-helper) were actually merged on June 23, before the page was last updated — the page was slightly behind. All three are now confirmed deployed to Cloud Run.

---

## 1. Executive Summary

**The DTOflow cloud platform is largely live.** Link processing, rendering, and transmission are operational end-to-end. The primary delivery risk is concentrated in the **Item Pipeline**, where property validation (PLT-2651) blocks item-driven flows, directly impacting Plaza Mobile and Central-Manager migrations.

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

### 1.1 Dimension → Epic Mapping

> Every PLT epic that contributes to each dimension, with live Jira status and assignee (pulled 2026-06-30). Epics may appear in multiple dimensions where they deliver cross-cutting value.

| Dimension | Epic | Status | Assignee | Summary |
|-----------|------|--------|----------|---------|
| **DTOflow Foundation** | PLT-2294 | ✅ Closed | Bart De Boer | id & alias validation in DTOflow servers |
| | PLT-2771 | ✅ Closed | Unassigned | ESL Image Merger |
| | PLT-2773 | ✅ Closed | Johan Ekman | ECC Link Projector |
| | PLT-2118 | 🟡 Test | Bart De Boer | Make DTOflow PROD-ready for Task & Scenario |
| | PLT-2336 | 🟡 In Progress | Sreekanth Singapuram Uppara | Make DTOflow more broadly accessible (PSC) |
| | PLT-2478 | 🟡 In Progress | Sreekanth Singapuram Uppara | PS↔CQS/DTOflow design |
| | PLT-171 | 🟡 Selected | Unassigned | SLA and trackingId support |
| | PLT-170 | 🔵 Backlog | Unassigned | DTOflow — Write Protection |
| | PLT-2444 | 🔵 Backlog | Unassigned | Status Reporting |
| | PLT-2369 | 🔵 Backlog | Unassigned | Auto-scaling |
| | PLT-2428 | 🔵 Backlog | Unassigned | Subscription System |
| | — (infra) | 🟢 Live | — | Spanner `dtoflow` (29 tables, 1000 PU), Pub/Sub (32 topics), gRPC, GCS/LFS, `dtoflow-spanner`, `dtoflow-lfs` |
| **Link Pipeline** | PLT-2773 | ✅ Closed | Johan Ekman | ECC Link Projector service |
| | PLT-2771 | ✅ Closed | Unassigned | ESL Image Merger |
| | PLT-2577 | ✅ Closed | Unassigned | ESL registration in cloud |
| | PLT-2497 | ✅ Closed | Unassigned | consume-ignore-linked mode |
| | PLT-2484 | 🟡 In Progress | Bart De Boer | Link v1 DTO refactor |
| | PLT-2359 | 🟡 In Progress | Bart De Boer | ECC Links & Rendering |
| | PLT-2357 | 🟡 Selected | Unassigned | Linked Item APIs — Items |
| | PLT-2358 | 🟡 Selected | Unassigned | Linked Item APIs — Devices |
| | PLT-2355 | 🟡 Selected | Bart De Boer | Label Status APIs |
| | PLT-2360 | 🔵 Backlog | Unassigned | Unified Linking API |
| | PLT-2363 | 🔵 Backlog | Unassigned | Auto Unlink |
| **Rendering Pipeline** | PLT-2771 | ✅ Closed | Unassigned | ESL Image Merger |
| | PLT-2773 | ✅ Closed | Johan Ekman | ECC Link Projector |
| | PLT-2573 | ✅ Closed | Unassigned | ECC Sync push (scope-out) |
| | PLT-2359 | 🟡 In Progress | Bart De Boer | ECC Links & Rendering |
| | PLT-2361 | 🔵 Backlog | Unassigned | Segment Labels |
| **Transmission & Edge Bridge** | PLT-2574 | ✅ Closed | Unassigned | Transmission service integration (scope-out) |
| | PLT-2577 | ✅ Closed | Unassigned | ESL registration in cloud |
| | PLT-2573 | ✅ Closed | Unassigned | ECC Sync push (scope-out) |
| | PLT-2478 | 🟡 In Progress | Sreekanth Singapuram Uppara | PS↔CQS/DTOflow design |
| | PLT-2353 | 🟡 In Progress | Bart De Boer | Pricer Server config export to DTOflow |
| **CQS (ChangeQueueService)** | PLT-169 | 🟡 In Progress | Johan Ekman | DTOflow — Create ChangeQueueService |
| | PLT-2792 | 🟡 In Progress | Bart De Boer | Services own CQS queues |
| | PLT-2478 | 🟡 In Progress | Sreekanth Singapuram Uppara | PS↔CQS/DTOflow design |
| | PLT-1870 | 🟡 Test | Daniel Pettersson | Make Pricer Server a CQS client |
| | PLT-2369 | 🔵 Backlog | Unassigned | Auto-scaling |
| | — (infra) | 🟢 Live | — | GKE cluster `platform` (runs CQS), `dtoflow-changequeue-dashboard` |
| **Gateway & Routing** | PLT-2336 | 🟡 In Progress | Sreekanth Singapuram Uppara | Make DTOflow more broadly accessible (PSC) |
| | PLT-2101 | 🟡 Selected | Saikiran Katta | API Request routing (on vacation) |
| | PLT-171 | 🟡 Selected | Unassigned | SLA and trackingId support |
| | — (infra) | 🟢 Live | — | Apigee API gateway, PCS ingress-nginx |
| **Shadow Mode** | PLT-2354 | 🟡 In Progress | Daniel Pettersson | Pricer Server & Replatforming Shadow Mode (orchestration) |
| | PLT-2483 | 🟡 Ready for Deploy | Johan Ekman | storeitemvalues export (data pipe) |
| | PLT-2496 | 🟡 Ready for Deploy | Unassigned | link export (data pipe) |
| | PLT-2494 | 🟡 In Progress | Johan Ekman | ECC params/images/models export (data pipe) |
| | PLT-2495 | 🟡 Selected | Unassigned | ECC fonts export (data pipe) |
| | PLT-2492 | 🟡 Selected | Unassigned | ESL Status DTO export (data pipe) |
| | PLT-2488 | 🟡 Selected | Unassigned | itemproperties export (data pipe — needs owner) |
| | PLT-2714 | 🟡 Selected | Unassigned | itemproperties startup export (data pipe — needs owner) |
| | PLT-1870 | 🟡 Test | Daniel Pettersson | CQS client in R3Server (enabler) |
| | PLT-2353 | 🟡 In Progress | Bart De Boer | Pricer Server config export (enabler) |
| | PLT-2497 | ✅ Closed | Unassigned | consume-ignore-linked mode (enabler) |
| **Item Pipeline** | PLT-2651 | 🔴 Blocked | Unassigned | Item property validation — **single clearest gate** |
| | PLT-2378 | 🔴 Blocked | Unassigned | Item Patch APIs — Core (gates Plaza Mobile + CM) |
| | PLT-2274 | 🔴 Blocked | Daniel Pettersson | SIC Support (depends on PLT-2378) |
| | PLT-2598 | ✅ Closed | Unassigned | Initial Bulk Item Load (scope-out) |
| | PLT-2587 | 🟡 Selected | Unassigned | Populate SICs in Item Registry (child story) |
| | PLT-2350 | 🔵 Backlog | Unassigned | Timed Item Updates |
| | PLT-2351 | 🔵 Backlog | Unassigned | Item Ingest Status — Extended |
| | PLT-2352 | 🔵 Backlog | Unassigned | Item Ingest Status — Advanced |
| | PLT-2436 | 🔵 Backlog | Unassigned | Item/Link via PFI |
| | — (infra) | 🟢 Live | — | `item-registry-api`, `item-registry` (4 of 5 services built) |
| **Consumer APIs** | PLT-2378 | 🔴 Blocked | Unassigned | Item Patch APIs (gates Plaza Mobile `PATCH/DELETE /api/public/core/v1/items` + CM `PATCH/DELETE /api/public/multi-store/v2/multi-store-requests/items`) |
| | PLT-2357 | 🟡 Selected | Unassigned | Linked Item APIs — Items |
| | PLT-2358 | 🟡 Selected | Unassigned | Linked Item APIs — Devices |
| | PLT-2355 | 🟡 Selected | Bart De Boer | Label Status APIs |
| | PLT-2356 | 🔵 Backlog | Unassigned | Item Flash APIs (stays on R3Server edge by design) |
| | — (infra) | 🟢 Live | — | Store UI (EVO Store Service), Plaza Actions (Apigee → actions) already 100% cloud-native |
| **First tenant migration** | PLT-2601 | 🔵 Backlog | Cristian Deaconeasa | First Tenant Selection (gate decision) |
| | PLT-2572 | 🔵 Backlog | Unassigned | Store Onboarding |
| | PLT-2575 | 🔵 Backlog | Unassigned | Store DTO Schema |
| | PLT-2578 | 🔵 Backlog | Unassigned | Tenant Isolation Validation |
| | PLT-2576 | 🔵 Backlog | Unassigned | Load Testing |
| | PLT-2579 | 🔵 Backlog | Unassigned | Monitoring & Dashboards |
| | PLT-2580 | 🔵 Backlog | Unassigned | Disaster Recovery |
| | PLT-2599 | 🔵 Backlog | Unassigned | Cutover & Rollback Runbook |
| | PLT-2581 | 🔵 Backlog | Unassigned | Runbooks |
| | PLT-2430 | 🔵 Backlog | Unassigned | Integration Tests Delivery 1 |
| | PLT-2600 | 🔵 Backlog | Unassigned | Studio Services Prod-Readiness |
| | PLT-2353 | 🟡 In Progress | Bart De Boer | Pricer Server config export (shared with Shadow Mode) |

> **Status legend:** ✅ Closed = done · 🟢 Live = deployed · 🟡 In Progress/Test/Selected/Ready for Deploy = active · 🔴 Blocked = gated · 🔵 Backlog = not started
>
> **Note:** Some epics appear in multiple dimensions (e.g., PLT-2478 spans DTOflow Foundation, Transmission, CQS, and Gateway). The table reflects where each epic delivers value — this is not double-counting.

---

## 2. Cloud Run Services — Full Inventory

All 21 services are deployed in `platform-dev-p01` (`europe-north1`), verified live 2026-06-30.

### Item Path

| Service | Tech | Status | Owns |
|---------|------|--------|------|
| `item-registry-api` | Quarkus Java | 🟢 Live | API gateway for items |
| `item-registry` | Quarkus Java | 🟢 Live | `storeitemvalues`, `itemproperties`, `itemprocessingparameters` |

### Link Path

| Service | Tech | Status | Owns |
|---------|------|--------|------|
| `link-registry` | Quarkus Java 21 | 🟢 Live | `storeesl`, `link.v2`, `store` |
| `link-bfg` | Quarkus Java | 🟢 Live | Bulk link operations |
| `link-storeasset-bfg` | Quarkus Java | 🟢 Live | Store asset bulk operations |

### Rendering Path (Studio)

| Service | Tech | Status | Owns |
|---------|------|--------|------|
| `studio-link-evaluator` | Quarkus GraalVM native | 🟢 Live | `studiolink` |
| `studio-renderer` | Node.js | 🟢 Live | `studioeslimage` |
| `studio-design-library` | Quarkus Java 21 | 🟢 Live | `design`, `canvasdesign`, `font`, `palette`, `esltype` |
| `studio-scenario-library` | Quarkus GraalVM native | 🟢 Live | `communicationpack` |

### Rendering Path (ECC — Legacy)

| Service | Tech | Status | Owns |
|---------|------|--------|------|
| `ecc-link-projector` | Quarkus Java | 🟢 Live | `ecclink` |
| `ecc-renderer` | Quarkus Java | 🟢 Live | `ecceslimage` |

### Image Merger

| Service | Tech | Status | Owns |
|---------|------|--------|------|
| `esl-image-merger` | Quarkus Java | 🟢 Live | `eslimage` |

### Edge Bridge

| Service | Tech | Status | Owns |
|---------|------|--------|------|
| `dtoflow-transmission` | Quarkus Java | 🟢 Live | Transmission to R3Server |

### Actions

| Service | Tech | Status | Owns |
|---------|------|--------|------|
| `actions-executor` | Quarkus Java | 🟢 Live | Task execution |
| `actions-library` | Quarkus Java | 🟢 Live | `taskdefinition` |

### Operations & Migration

| Service | Tech | Status | Owns |
|---------|------|--------|------|
| `delivery-sync-service` | Quarkus Java | 🟢 Live | Delivery synchronization |
| `delivery-dashboard` | Quarkus Java | 🟢 Live | Delivery monitoring UI |
| `dtoflow-changequeue-dashboard` | Quarkus Java | 🟢 Live | CQS monitoring UI |
| `migration-helper` | Quarkus Java | 🟢 Live | `link.v1↔v2` bridge, `designerlink↔studiolink` bridge |
| `dtoflow-spanner` | Quarkus Java | 🟢 Live | Spanner DTO read/write server |
| `dtoflow-lfs` | Quarkus Java | 🟢 Live | Large File System (GCS-backed) |

---

## 3. Key End-to-End Flows

From the Confluence status page (2026-06-25), three flows summarise the overall state:

| # | Flow | Status | Detail |
|---|------|--------|--------|
| 1 | **Item Price Change** | 🟡 Partially ready | Gated by item property validation (PLT-2651). Item update → evaluator + renderer → merger chain partially operational; item writes don't yet validate properties end-to-end. |
| 2 | **Link Creation** | 🟢 Live | The strongest proof point. Link creation/deletion flows through link-registry → evaluator → renderer → merger → transmission. Multiple services operational end-to-end. |
| 3 | **Item Deletion** | 🔴 Not ready | Path not yet built. Item deletion doesn't flow through DTOflow. |

> **Additional flows** (Design Publication, ESL Lifecycle, Flash/Display Page, ECC paths) are covered in detail in [13 — Core Data Flows](13-core-data-flows.md). Their statuses range from 🟢 (ECC link path, design publication path) to 🟡 (ESL lifecycle partial, Flash requires edge hardware).

---

## 4. Epic Status Summary

> Pulled from live Jira (`project = PLT`), 2026-06-30. Trust Jira over this table — it's a snapshot.

### Blockers

| Epic | Summary | Status | Owner | Why It Matters |
|------|---------|--------|-------|----------------|
| **PLT-2651** | Item property validation | 🔴 Gating | — | **Single clearest gate** on item-driven migration. 4 of 5 item pipeline services built; blocked by property validation. |
| **PLT-2378** | Item Patch APIs | 🔴 Blocked | **Unassigned** | Gates Plaza Mobile + Central-Manager item paths |
| **PLT-2274** | SIC Support | 🔴 Blocked | Daniel Pettersson | Depends on PLT-2378 |

### In Progress

| Epic | Summary | Status | Owner |
|------|---------|--------|-------|
| PLT-169 | ChangeQueueService | 🟡 In Progress | Johan Ekman |
| PLT-2354 | Shadow Mode | 🟡 In Progress | Daniel Pettersson |
| PLT-2336 | DTOflow broader accessibility (PSC) | 🟡 In Progress | Sreekanth S. Uppara |
| PLT-2478 | PS ↔ CQS/DTOflow design | 🟡 In Progress | Sreekanth S. Uppara |
| PLT-2792 | Services own CQS queues | 🟡 In Progress | Bart De Boer |
| PLT-2484 | Link v1 DTO refactor | 🟡 In Progress | Bart De Boer |

### In Test / Code Review

| Epic | Summary | Owner | Detail |
|------|---------|-------|--------|
| 🟡 PLT-2118 | DTOflow PROD-ready (Task & Scenario) | Bart De Boer | Foundation certification |
| 🟡 PLT-2483 | storeitemvalues export | Johan Ekman | Shadow Mode data pipe — **Ready for Deploy** |
| 🟡 PLT-1870 | CQS client in R3Server | Daniel Pettersson | R3Server side of work dispatch — in Test |

### Selected for Development

| Epic | Summary | Owner |
|------|---------|-------|
| PLT-2101 | API request routing | Saikiran Katta |
| PLT-171 | SLA & trackingId support | Unassigned |

### Recently Closed (6 epics)

PLT-2294 (id/alias validation), PLT-2598 (initial bulk item load), PLT-2577 (ESL registration in cloud), PLT-2574 (transmission service integration), PLT-2573 (ECC sync push). **Note:** some closures are scope-outs, not completions — re-read before assuming a capability exists.

### Recently Deployed (since Confluence page, 2026-06-25)

The Confluence page listed three services as "ready for review." All three have since been **merged and deployed** to Cloud Run:

| Service | PR | Merged |
|---------|-----|--------|
| `ecc-link-projector` | #15 feat(PLT-2773) | 2026-06-23 |
| `esl-image-merger` | #16 feat(PLT-2771) | 2026-06-23 |
| `migration-helper` | #15 feat/cqs-network-config | 2026-06-23 |

---

## 5. Migration Roadmap

| Phase | Target | Key Milestone | Timeline |
|-------|--------|---------------|----------|
| **Phase 0** | Internal tenants only | Shadow Mode demo works (PLT-2354) | Target July 2026 |
| **Phase 0** | Replatforming-Dev | First tenant fully migrated | After Shadow Mode validated |
| **Phase 0** | Evo-Se | Dev team on DTOflow | After Replatforming-Dev |
| **Phase 0** | Application-Stage | Product validation on DTOflow | After Evo-Se |
| **Phase 1** | byPricer (demo) | First production tenant | Q3 2026 |
| **Phase 1** | Landwaart AGF B.V | Active update patterns, no PCS | Q3 2026 |
| **Phase 1** | Spar-be (~13K ESLs) | Large-scale validation | Q3-Q4 2026 |
| **Phase 2** | Scale | More tenants, full feature parity | Q4 2026+ |

> See [14 — Tenant Migration Guide](14-tenant-migration.md) for the detailed per-store migration procedure.

---

## 6. Risks & Open Items

| Risk | Severity | Mitigation |
|------|----------|------------|
| **PLT-2651 — Item property validation** | 🔴 Critical | The single clearest gate on item-driven migration; blocks Item Pipeline (4 of 5 services built) |
| **PLT-2378 unassigned** | 🔴 Critical | Assign an owner; blocks consumer API cutover |
| **Shadow Mode sub-tasks unassigned** | 🟡 High | PLT-2494, 2495, 2492, 2488, 2714 need owners |
| **Bart De Boer owns 4+ critical epics** | 🟡 High | Spread ownership; bus factor risk |
| **PLT-2601 slipped to Backlog** | 🟡 Medium | First tenant selection moved from Selected for Dev to Backlog; drive to decision |
| **API routing not started** | 🟡 Medium | PLT-2101 — Saikiran on vacation; plan handover |
| **Review bottleneck** | 🟡 Medium | 6+ items waiting for Johan Ekman's review |
| **Ops readiness not started** | 🟡 Medium | Cutover (PLT-2599), monitoring (PLT-2579), DR (PLT-2580), runbooks (PLT-2581) all in backlog |

---

## 7. Infrastructure Health

| Component | Details | Status |
|-----------|---------|--------|
| **Spanner** | Instance `dtoflow`, 1000 PU, 29 DTO tables + `item-registry` | 🟢 Healthy |
| **Pub/Sub** | 32 topics (`dtoflow-changes-*`, DLQ, sync, item-registry-requests) | 🟢 Healthy |
| **GKE** | Cluster `platform` (runs CQS) | 🟢 Healthy |
| **Cloud Run** | 21 services, `europe-north1` | 🟢 All deployed |
| **GCS/LFS** | `dtoflow-lfs` — content-addressed SHA-256 storage | 🟢 Healthy |
| **Apigee** | API gateway — front door to Cloud Run | 🟡 PSC setup in progress (PLT-2336) |

---

## 8. What's Next (Priority Order — from Confluence)

1. **PLT-2651 — Item property validation** — the single clearest gate on item-driven migration. Unblocking this enables the item pipeline for Plaza Mobile and Central-Manager.
2. **PLT-2483 — storeitemvalues export** — needed for the Shadow Mode data pipe; **Ready for Deploy** (Johan Ekman).
3. **PLT-1870 — CQS client in R3Server** — finish the R3Server side of work dispatch; in **Test** (Daniel Pettersson).
4. **PLT-2118 — DTOflow PROD-ready** — formally certify the foundation for production use.
5. **PLT-2378 — Item Patch APIs** — still critical for consumer cutover; needs owner assignment.
6. **PLT-2101 — API routing** — needed for the switch procedure; Saikiran on vacation, plan handover.

> The three "in review" services from the Confluence page have all been deployed since the page was written — this item is cleared.

---

> **Refresh sources:**
> - GCP: `gcloud run services list --region=europe-north1 --project=platform-dev-p01`
> - Jira: `project = PLT AND issuetype = Epic ORDER BY status ASC`
> - Confluence: [Replatforming Architecture Pipeline Status](https://pricer-org.atlassian.net/wiki/spaces/~71202026d6e29fd7314f1e915ad8754239598a/pages/10187767809/Replatforming+Architecture+Pipeline+Status)

---

### Previous: [14 — Tenant Migration Guide](14-tenant-migration.md)
