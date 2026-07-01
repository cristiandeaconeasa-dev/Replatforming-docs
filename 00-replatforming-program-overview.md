# 00 — Replatforming Program Overview

> **The starting point for understanding the Replatforming program.** Explains what we're building, why, how we're structuring the work, and where we are today. Intended for new team members, stakeholders, and anyone needing the full picture in one place.
>
> **Last validated:** 2026-07-01 — against live GCP `platform-dev-p01`, Jira (`project = PLT`, all 42+ Replatforming epics), the `evo-dtoflow-protos` central-documentation branch, and the actual service code (`platform-evaluation-engine`, `platform-image-render-service`).

---

## 1. What Is Replatforming?

Pricer AB sells an **Electronic Shelf Label (ESL)** platform to retail chains. Today, each store runs its own instance of **Pricer Server (R3Server)** — a Java monolith with its own MySQL database, deployed as a Kubernetes "Store-Unit." A retail chain (a *tenant*) is just a collection of these Store-Units.

**The problem:** Per-store instances don't scale. A price change across 200 stores means 200 independent updates. Item data, rendering, and link management are all duplicated. Adding a new feature means deploying to thousands of Store-Units.

**The solution — Replatforming:** Move item storage, link management, rendering, and business APIs off the per-store instances and into a **shared, multi-tenant cloud platform** called **DTOflow** on Google Cloud (Cloud Run + Spanner + Pub/Sub). The only thing that stays on R3Server is what must stay — the radio transmission engine that drives the physical ESL labels via IR/RF.

**One sentence:** Replatforming migrates everything except the transmission engine from per-store monoliths to a shared event-driven cloud platform.

---

## 2. The Three Phases

```
P0 (Prove it)        P1 (Ship it)        P2 (Scale it)
Zero label risk      First real tenant    All tenants, full parity
```

| | P0: Prove It | P1: Ship It | P2: Scale It |
|---|---|---|---|
| **Goal** | Prove the cloud pipeline works without touching real labels | One real, revenue-generating tenant live on the cloud path | All tenants migrated, full feature parity with R3Server |
| **Tenants** | Internal dev tenants (Replatforming-Dev, Evo-Se, Application-Stage) | byPricer → small customer → medium customer | All remaining tenants |
| **Risk** | Zero — Shadow Mode runs in parallel, label transmit is dropped | Controlled — per-API-path routing enables incremental migration and rollback | Managed — each tenant validated before the next |
| **Output** | Cloud pipeline produces 100% identical images to the edge, validated for 24h on 3 tenants | First customer runs on DTOflow. R3Server is thin edge (transmission only). | DTOflow replaces R3Server for all non-transmission functions. |
| **Prerequisites** | DTOflow infrastructure live (Spanner, Pub/Sub, CQS, Cloud Run) | P0 closed. Item APIs + per-API-path routing live. Tenant isolation proven. | P1 closed. All features built. Ops readiness complete. |
| **Target** | **Week 34** (Aug 17-23, 2026) | **W44**: byPricer · **W50**: ops ready · **Q1 2027**: all 3 tenants | **2027** — scoped after P1 closes |

### Phase 0: Prove It

**What we're building:** The cloud infrastructure and proving it can process real data from R3Server without affecting real labels. This is called **Shadow Mode** — the cloud pipeline runs in parallel with the edge, receiving live item/link data, processing it through evaluators and renderers, but **dropping the transmission to labels**. We compare cloud-rendered images against edge-rendered images — they must be 100% identical for 24 continuous hours on three tenants.

**Prerequisites before Phase 0 can close:**
- All export data pipes live (items, links, ECC params, ESL status, itemproperties)
- CQS (ChangeQueueService) operating and services self-subscribing
- Per-API-path routing (PLT-2101) not required for Phase 0, but must be started before Phase 1
- CQS client in R3Server (PLT-1870) live
- 24h image parity on all 3 Shadow Mode tenants

**Acceptance criteria:** 24 continuous hours of 100% rendered-image parity across Replatforming-Dev, Evo-Se, and Application-Stage tenants. Zero label impact.

### Phase 1: Ship It

**What we're building:** The item API surface (PLT-2378, PLT-2651), tenant isolation (PLT-2578), operational readiness (monitoring, load testing, DR, runbooks), and the tenant migration mechanism (per-API-path routing).

**Prerequisites before Phase 1 can start:**
- Phase 0 closed (Shadow Mode parity confirmed)
- Item property validation (PLT-2651) — **the single clearest gate.** 4 of 5 item pipeline services are built; this is the missing piece.
- Item Patch APIs (PLT-2378) — gates Plaza Mobile and Central-Manager item paths
- Per-API-path routing (PLT-2101) — the mechanism that makes migration incremental
- Tenant isolation proven (PLT-2578) — non-negotiable before real customer data enters

**Acceptance criteria:** byPricer (demo tenant) live on DTOflow. Then one small customer (e.g., Landwaart AGF, 2 stores, sub-1000 labels). Then one medium customer (e.g., spar-be, O(10) stores, ~13K labels). Each tenant stable for 2 weeks before the next. R3Server is thin edge (transmission only) for migrated tenants.

### Phase 2: Scale It

**What we're building:** Full feature parity with R3Server — timed item updates, ECC rendering parity, segment labels, auto-unlink, flash APIs, subscription system, webhooks. Plus auto-scaling and SLA support.

**Acceptance criteria:** All remaining tenants migrated. All features built. R3Server is transmission-only for all tenants.

---

## 3. How We're Structuring the Work

Each Phase decomposes into **Milestones** (~6 weeks, a major thematic target), which decompose into **Increments** (2-4 weeks, a demonstrable end-to-end scenario ending in a specific demo), which contain **Epics** (Jira units, assignable and trackable).

```
Phase → Milestone → Increment → Epic
```

| Level | Timescale | Answers | Example |
|-------|-----------|---------|---------|
| **Phase** | 6-12 months | When in the program? | P0: Prove It |
| **Milestone** | ~6 weeks | What major target? | M2: Shadow Mode Validation |
| **Increment** | 2-4 weeks | What can we demo by Friday? | Inc 2.1: Core Data Tap |
| **Epic** | Sprint | What Jira unit is tracked? | PLT-2483: storeitemvalues export |

### The 6 Milestones

| Phase | Milestone | Goal | Status | Target |
|-------|-----------|------|--------|--------|
| P0 | **M1: Platform Foundation** | Core infrastructure live and certified | 🟡 Active | **W30** (Jul 26) |
| P0 | **M2: Shadow Mode Validation** | Cloud pipeline runs in parallel with edge. Zero label risk. | 🟡 Active | **W34** (Aug 23) |
| P1 | **M3: First Tenant Go-Live** | Item and link API traffic cut over to cloud | 🔴 Gated | **W44** (Nov 1) |
| P1 | **M4: Production Hardening** | Monitoring, load testing, DR, runbooks | 🔵 Not started | **W50** (Dec 13) |
| P2 | **M5: Feature Parity** | Timed updates, ECC sync, autoscaling, SLAs | 🔵 Not started | 2027 |
| P2 | **M6: Full Migration** | All tenants migrated | 🔵 Not started | 2027 |

### Phase 0 Increments

| Milestone | Inc | Name | Demo | Status | Target |
|-----------|-----|------|------|--------|--------|
| M1: Platform Foundation | 1.1 | Core Event Routing | Dummy DTO → CQS → Cloud Run queue | 🟡 Active | **W29** (Jul 19) |
| | 1.2 | Cloud/Edge Bridge | R3Server receives from cloud CQS | 🟡 Active | **W29** (Jul 19) |
| | 1.3 | Production Ingress & Security | URL-path routing → PSC → private Cloud Run | 🟡 Not started | **W30** (Jul 26) |
| M2: Shadow Mode Validation | 2.1 | Core Data Tap | Price update in R3 → all DTOs appear in Spanner | 🟡 Active | **W28** (Jul 12) |
| | 2.2 | Shadow Execution & Studio Parity | Item change → cloud render → transmit dropped | 🟡 Active | **W31** (Aug 2) |
| | 2.3 | Multi-Tenant Shadow Validation | 24h parity on 3 tenants | 🔵 Not started | **W34** (Aug 23) |

Every Increment ends with a **named demo scenario** — a specific, verifiable outcome that can be shown in a sprint review.

---

## 4. The Target Architecture

The end state is a **hybrid cloud-edge** system:

```
☁️ Cloud (DTOflow)                     🏬 Edge (R3Server, thin)
┌─────────────────────────┐            ┌──────────────────────┐
│ Item storage (Spanner)  │            │ Transmission engine   │
│ Link management         │            │ Basestation control   │
│ Rendering (Studio/ECC)  │──images──→ │ Flash & display-page  │
│ Work dispatch (CQS)     │            │ Store map / geo       │
│ APIs & Gateway (Apigee) │            │ Local ESL status/ACKs │
└─────────────────────────┘            └──────────────────────┘
```

### What moves to cloud
- **Item storage:** per-store MySQL → Spanner `storeitemvalues`
- **Item/Link APIs:** R3Server REST → `item-registry-api`, `link-registry`
- **Rendering:** per-Store-Unit CPU → `platform-image-render-service` (Studio), `ecc-renderer` (ECC)
- **Design resolution:** `studio-link-evaluator` evaluates CEL rules from CommunicationPacks against item properties
- **Work dispatch:** R3Server internal → CQS subscription fan-out (GKE)

### What stays on R3Server (by design, never migrates)
- **Transmission engine** — millisecond IR/RF to ESLs; cannot be remote
- **Basestation control** — physical radio hardware management
- **Flash & display-page** — real-time commands requiring sub-second latency
- **Store map / geo** — physical store layout, tied to basestation positions

### How migration is incremental

**Per-API-path routing** (PLT-2101) teaches ingress-nginx to route by URL path:
- `/api/.../items/*` → Cloud Run `item-registry-api`
- `/api/.../links/*` → Cloud Run `link-registry`
- `/api/private/*` (transmission, flash, display-page, map) → R3Server Store-Unit

This means individual API paths can be flipped independently — and rolled back by flipping them back. No client change required.

---

## 5. How the Cloud Platform Works

DTOflow is a **decentralized, event-driven** platform. There is no central orchestrator.

### The data backbone

```
Service writes DTO to Spanner
  → Pub/Sub emits dtoflow-changes-<dto>.v1
  → ChangeQueueService (CQS) delivers to all subscribing services
  → Each service dequeues independently, fetches the DTO, processes it
  → May write its own output DTOs → triggers further subscribers
```

### The 5 core data flows

| Flow | What happens | Status |
|------|-------------|--------|
| **Item price change → label update** | `item-registry` writes `storeitemvalues` → evaluator re-evaluates CEL rules in CommunicationPack (may write new `studiolink`) → renderer reads `designerlink`, design from LFS, item properties → renders label via fabric.js → writes `renderedimage` → pricer-server transmits to ESL | 🟡 Partially ready (gated by PLT-2651) |
| **Link creation → render** | `link-registry` writes `link.v2` + `storeesl` → evaluator resolves design (or uses `forced_design_id` directly) → writes `studiolink` → renderer produces image | 🟢 Live |
| **Design publication → mass re-render** | `studio-design-library` writes `design.v1` → renderer finds all affected `designerlink` records via `by_design` alias → re-renders every one | 🟢 Live |
| **CommunicationPack change → mass re-evaluation** | CP scenario tree changes → evaluator reads ALL studio links for the tenant → re-evaluates CEL rules for every link → writes new `studiolink` for any changed design | 🟢 Live |
| **Item deletion → label clear** | `item-registry` tombstones `storeitemvalues` → evaluator detects tombstone → triggers unlink → renderer produces blank label | 🔴 Not built |

### The evaluator: how designs get chosen

The `studio-link-evaluator` (`platform-evaluation-engine`, Java) subscribes via CQS to `storeitemvalues.v1`, `link.v2`, and `communicationpack.v1`. When triggered:

1. **Depth-first traverses** the CommunicationPack scenario tree
2. Each scenario has a `cel_expression` (Google's Common Expression Language)
3. CEL expressions reference `item.Price`, `item.Category`, `link.location`, `device.plType`
4. Expressions from parent scenarios accumulate with `&&`
5. **First matching scenario wins** — its `design_ids` become the resolved designs
6. Designs are filtered by ESL type compatibility
7. If the resolved design differs from the current `studiolink.design_id`, a new `studiolink` is written

If a link has `forced_design_id` set, the evaluator skips rule evaluation entirely — that design is used unconditionally.

### The renderer: how labels get drawn

The `platform-image-render-service` (TypeScript, Node.js) receives Pub/Sub push events for `designerlink.v1`, `storeitemvalues.v1`, `design.v1`, `canvasdesign.v1`, and `storeesl.v1`. When triggered:

1. Reads the `designerlink` DTO → extracts `designId`
2. Reads the `storeitemvalues` DTO → extracts `customProperties` as a key-value map
3. Reads the design DTO → gets `jsonFilePath` in LFS → reads the design JSON from GCS
4. The design JSON contains `svgDesign.svgBase64Encoded` — either an SVG string or Fabric JSON
5. Parses the SVG via **fabric.js** and applies `propertyMappings` — substituting item data (`item.Price`, `item.Name`) into SVG text elements
6. Registers fonts from DTOflow font DTOs
7. Creates a Fabric Canvas, renders to PNG via `canvas.toDataURL()`
8. Applies dithering for e-paper color reduction
9. Writes PNG to LFS: `renderer/t/{tenantId}/eslimages/{sha256}.png`
10. Writes `renderedimage.v1` DTO with id `t/{tenantId}/s/{storeId}/esls/{barcode}/pages/0/renderedimage`

---

## 6. Current Status (2026-07-01)

### What's live

- **21 Cloud Run services** deployed in GCP `platform-dev-p01` (`europe-north1`)
- **Spanner:** instance `dtoflow` (29 DTO tables, 1000 PU) + `item-registry` (1 table)
- **Pub/Sub:** 32 topics
- **Link creation → render → transmit:** end-to-end live
- **Design publication → mass re-render:** live
- **CommunicationPack change → mass re-evaluation:** live
- **ECC rendering:** live (ecc-renderer, ecc-link-projector, esl-image-merger)

### What's blocked (the gates)

| Epic | What | Why it matters |
|------|------|---------------|
| **PLT-2651** | Item property validation | 🔴 Blocked, Unassigned. 4 of 5 item pipeline services built. This is the **single clearest gate** — without it, items can't be validated before Spanner write. |
| **PLT-2378** | Item Patch APIs | 🔴 Blocked, Unassigned. Gates Plaza Mobile `PATCH /items` and Central-Manager bulk item paths. |
| **PLT-2101** | Per-API-path routing | 🟡 Selected, Saikiran on vacation. The mechanism that makes migration incremental. |

### What's on the critical path

- **Daniel Pettersson** owns PLT-2354 (Shadow Mode orchestration, realistically a 5-week task, not the 1w 2d currently estimated) — he is on the critical path
- **Bart De Boer** owns 4 active Phase 0 epics plus early Phase 2 work — overloaded
- **4 export epics** (PLT-2496, 2495, 2488, 2714) are unassigned — invisible work sitting idle
- **PLT-2601** (First Tenant Selection) is in Backlog — a business decision, not engineering

### Timeline projection

| Date | Milestone |
|------|-----------|
| **Week 34** (Aug 17-23, 2026) | Phase 0 close (realistic, assuming PLT-2354 corrected to 5w and summer vacation factored) |
| **Week 44** (Oct 26-Nov 1, 2026) | First Phase 1 tenant (byPricer) live on DTOflow |
| **Week 50** (Dec 7-13, 2026) | M4 closed — ops readiness complete |
| **Q1 2027** | Phase 1 complete — small + medium customer live |
| **2027** | Phase 2 — full feature parity, all tenants migrated |

---

## 7. The Full Epic Map

All Replatforming epics mapped to their Milestone and Increment. See [doc 15](15-overall-status.md) for live status.

### M1: Platform Foundation (P0 — Active)

| Inc | Epics | Target week |
|-----|-------|-------|
| **1.1 Core Event Routing** | PLT-2294 (Closed), PLT-169 (CQS), PLT-2792 (services own queues), PLT-2478 (PS ↔ CQS design) | 29 |
| **1.2 Internal Comm & Security** | PLT-1870 (CQS client in R3Server), PLT-2336 (PSC), PLT-2118 (DTOflow PROD-ready)  | 31 |

**Acceptance criteria**: all deliveries dependeing strictly on the new platform will be delivered to Prod.

### M2: Shadow Mode Validation (P0 — Active)

| Inc | Epics |  |
|-----|-------|-------|
| **2.1 Core Data Tap** | PLT-2353, 2483, 2496, 2494, 2495, 2492, 2488, 2714 (8 export pipes) | 30 |
| **2.2 Shadow Mode Completion** | PLT-2497 (Closed), PLT-2354 (Shadow Mode orchestration), PLT-2359(ECC Rendering Support) | 32 |
| **2.3 API Parity Validation** | Extend API development to cover Basic Functionality | 33 |
| **2.4 Routing** | PLT-2101 (per-API-path routing) | 34 |

### M3: First Tenant Go-Live (P1 — Gated)

| Inc | Epics |
|-----|-------|
| **Inc 1: Item+Link APIs** | PLT-2651 (validation), PLT-2378 (Patch APIs), PLT-2274 (SIC), PLT-171 (SLA), PLT-2658 (LFS protection), PLT-2360/2361/2350/2356/2363/2352 (features) |
| **Inc 2: Security & Isolation** | PLT-2578 (tenant isolation), PLT-170 (write protection) |
| **Inc 3: Tenant Switch** | PLT-2601 (tenant selection), PLT-2572/2575 (store onboarding), PLT-2600 (studio readiness), PLT-2430 (integration tests) |

### M4: Production Hardening (P1 — Not started)

| Inc | Epics |
|-----|-------|
| **Inc 1: Monitoring** | PLT-2579 (dashboards), PLT-2444 (status reporting) |
| **Inc 2: Load Test** | PLT-2576 (load testing), PLT-2369 (auto-scaling) |
| **Inc 3: DR & Runbook** | PLT-2599 (cutover runbook), PLT-2580 (DR), PLT-2581 (operational runbooks) |

### M5: Feature Parity (P2 — Not started)

19 epics including PLT-2359 (ECC Links & Rendering), PLT-2350 (Timed Updates), PLT-2361 (Segment Labels), PLT-2360 (Unified Linking), PLT-2363 (Auto Unlink), PLT-2355 (Label Status APIs), PLT-2428 (Subscription System), PLT-171 (SLA), PLT-170 (Write Protection), PLT-2444 (Status Reporting), PLT-2369 (Auto-scaling).

### M6: Full Migration (P2 — Not started)

Not yet scoped. Will be defined when M5 is underway.

---

## 8. Key Risks

| Risk | Severity | Detail |
|------|----------|--------|
| **PLT-2651 + PLT-2378 unassigned** | 🔴 Critical | Two blocked, unassigned epics gate the entire item pipeline. The single highest-priority action in the program. |
| **PLT-2354 underestimated** | 🔴 High | Shadow Mode orchestration estimated at 1w 2d — realistically 5w. Daniel Pettersson is on the critical path. |
| **Summer vacation season** | 🟡 High | July-August in Sweden. 32 working days to mid-August assumes 100% attendance. |
| **Bart De Boer overloaded** | 🟡 High | 4+ active epics across M1, M2, and M5. Risk of burnout and quality degradation. |
| **Ops readiness entirely in Backlog** | 🟡 Medium | Monitoring, DR, load testing, cutover runbook — all 11 M4 epics are in Backlog. Cannot put a real customer on the platform without these. |

---

## 9. How to Read the Full Doc Set

| Doc | What it covers |
|-----|---------------|
| **00** (this doc) | Program overview — the starting point |
| [01](01-systems-architecture.md) | Current Pricer platform architecture (before Replatforming) |
| [02](02-tenant-model.md) | What a tenant is, isolation model |
| [03](03-replatforming-deep-dive.md) | Deep dive into Replatforming: phases, Shadow Mode, epic backlog |
| [04](04-target-architecture.md) | Target EVO/DTOflow architecture, hybrid boundary |
| [05](05-core-concepts-deep-dive.md) | Core concepts: links, tenants, EVO tokens, PCS |
| [08](08-dtoflow-deep-dive.md) | DTOflow platform: Spanner, Pub/Sub, CQS, service inventory |
| [11](11-link-pipeline-deep-dive.md) | Link pipeline: link-registry, evaluator, link types |
| [12](12-rendering-pipeline-deep-dive.md) | Rendering pipeline: studio-renderer, ecc-renderer, mergers |
| [13](13-core-data-flows.md) | 5 core end-to-end data flows with Mermaid diagrams |
| [14](14-tenant-migration.md) | Tenant migration process, switch procedure |
| [15](15-overall-status.md) | Live status — all 58 epics mapped to Milestones and Increments |
| [17](17-phase-1-plan.md) | Phase 1 plan: feature delivery, gaps, tenant strategy |
| [19](19-dimension-frameworks.md) | Delivery framework evolution (A/B/C → Phase→Milestone→Increment→Epic) |
| [20](20-phase-0-effort-analysis.md) | Phase 0 effort estimation analysis, mid-August deadline assessment |

---

> **Refresh sources:**
> - GCP: `gcloud run services list --region=europe-north1 --project=platform-dev-p01`
> - Jira: `project = PLT AND issuetype = Epic AND labels in ("replatforming-phase-0","replatforming-phase-1","replatforming-phase-2") ORDER BY status ASC`
> - GitHub: `PricerAB/platform-evaluation-engine`, `PricerAB/platform-image-render-service`, `PricerAB/evo-dtoflow-protos`
