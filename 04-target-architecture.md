# 04 — Target Architecture (EVO / DTOflow) and how it still connects to Pricer Server

> **Scope:** The target cloud platform, **how clients reach it** (per‑API‑path routing + Apigee + PSC), the **end‑to‑end flow**, and — most importantly for a leader — **how the cloud still connects back to Pricer Server at the edge** (the hybrid boundary). Concludes with "what moves vs. what stays".
>
> **Validated:** 2026-06-17 against GCP `platform-dev-p01` + live Jira. Builds on [doc 03](03-replatforming-deep-dive.md). **2026-06-30:** Jira statuses and GCP service count refreshed.
>
> **2026-06-29 correction:** End-to-end sequence diagram (section 4) and topology diagram (section 1) corrected. CQS is a subscription-based fan-out layer, not a central orchestrator. Evaluator and renderer subscribe independently and run in parallel — there is no sequential "evaluate → render" pipeline.
>
> **2026-06-23 update:** 3 new Cloud Run services deployed since validation: `migration-helper`, `esl-image-merger`, `changequeue-dashboard`. Pub/Sub topics grew from 23 to **32**. See [08 — DTOflow Deep Dive](08-dtoflow-deep-dive.md).

---

## 1. Target topology

The end state is a **hybrid cloud‑edge** system: a shared multi‑tenant cloud platform for data/APIs/rendering, and a **thin** Pricer Server at each store for radio transmission only.

```mermaid
config:
    layout: elk
flowchart TB
    ERP["Retailer ERP"]
    subgraph clients["Clients"]
        PM["Plaza Mobile (BFF)"]
        CM["Central-Manager"]
        SU["Store UI"]
        PA["Plaza Actions"]
    end

    subgraph entry["Entry / routing"]
        ING["PCS ingress-nginx<br/>per-API-path routing (PLT-2101)"]
        APG["Apigee gateway"]
    end

    subgraph cloud["☁️ EVO / DTOflow (platform-dev-p01, europe-north1)"]
        direction TB
        IR["item-registry(-api)"]
        LR["link-registry / link-bfg"]
        ST["studio-renderer / -link-evaluator /<br/>-design-library / -scenario-library"]
        ECCs["ecc-renderer / ecc-link-projector /<br/>esl-image-merger"]
        ACT["actions-executor / -library"]
        TXC["dtoflow-transmission"]
        SP[("Spanner: dtoflow + item-registry")]
        PS["Pub/Sub (32 topics)"]
        CQS["ChangeQueueService (GKE 'platform')"]
        LFS["LFS (GCS)"]
    end

    subgraph edge["🏬 Edge (per store)"]
        R3["Pricer Server (R3Server) — thin<br/>transmission + basestation control"]
        HW["Basestations → ESL"]
    end

    ERP --> ING
    PM --> ING
    PM --> APG
    CM --> ING
    CM --> APG
    SU --> APG
    PA --> APG
    ING --> IR
    APG --> IR & LR & ST & ECCs & ACT
    IR & LR & ST & ECCs & ACT <--> SP
    IR & LR & ST & ECCs --> PS
    ST --> LFS
    TXC -->|rendered images + commands| R3

    Note["Pub/Sub fans out to CQS, which delivers<br/>to whichever services subscribed to each DTO type.<br/>No central orchestrator — services self-configure."]
    R3 --> HW

    style cloud fill:#fff3e0,stroke:#f57c00,color:#000
    style edge fill:#e8f5e9,stroke:#2e7d32,color:#000
    style clients fill:#e3f2fd,stroke:#1565c0,color:#000
```

---

## 2. How clients reach it — routing & gateway

Two complementary entry points; the key migration mechanism is **per‑API‑path routing**.

### 2.1 Per‑API‑path routing at ingress (PLT‑2101)
The existing **PCS ingress‑nginx** is taught to route by URL path instead of always hitting the Store‑Unit:

```mermaid
config:
    layout: elk
flowchart LR
    REQ["Request to {store}.{pcsInstance}.pcm.pricer-plaza.com/api/..."] --> ING{"ingress-nginx<br/>path match"}
    ING -->|"/api/.../items/*"| CLOUD["Cloud: item-registry-api → DTOflow"]
    ING -->|"/api/.../links/*"| CLOUD2["Cloud: link-registry → DTOflow"]
    ING -->|"/api/private/* (transmission, flash, display-page, map)"| R3["Store-Unit (R3Server)"]
```

This is what makes the migration **incremental and reversible**: flip one path to the cloud, validate, and roll back by flipping it back. No client change required.

### 2.2 Apigee + Private Service Connect (PSC)
**Apigee** is the single managed front door for the newer integrations and external clients (Designer linking, studio, actions, monitoring). It routes to Cloud Run services privately over **PSC** (epic **PLT‑2336** broadens this accessibility). Benefits: one place for auth/rate‑limiting/analytics, and **blue/green** backend swaps without touching frontends.

| Path (illustrative) | Backend Cloud Run service |
|---------------------|---------------------------|
| `/api/designs/*`, `/api/scenarios/*`, `/api/render/*` | `studio-design-library`, `studio-scenario-library`, `studio-renderer` |
| `/api/links/*` | `link-bfg`, `link-storeasset-bfg`, `link-registry` |
| `/api/files/*` | `dtoflow-lfs` |
| `/api/actions/*` | `actions-executor`, `actions-library` |
| item search | `item-registry-api` |

---

## 3. The hybrid boundary — what stays on the edge

**This is the crux of the design and the question a leader is most asked: if items/links/render move to the cloud, why keep Pricer Server at all?**

Because the **physics live in the store**. Driving IR/RF radios and getting a label to change in milliseconds requires code **on the LAN, next to the basestations**. The cloud cannot meet that latency or own that hardware. So R3Server remains as a **thin edge agent**.

```mermaid
config:
    layout: elk
flowchart TB
    subgraph cloudside["☁️ Cloud owns"]
        D1["Item & link storage (Spanner)"]
        D2["Business APIs (item/link registries)"]
        D3["Rendering (studio / ecc renderers)"]
        D4["Work dispatch (CQS)"]
        D5["Gateway/auth (Apigee)"]
    end
    subgraph edgeside["🏬 Edge (R3Server) owns"]
        E1["Transmission engine (IR/RF)"]
        E2["Basestation / transceiver control"]
        E3["Flash & display-page (real-time)"]
        E4["Store map / geo (physical layout)"]
        E5["Local ESL status & ACK handling"]
    end
    cloudside -->|"rendered images + commands<br/>via dtoflow-transmission"| edgeside
    edgeside -->|"label status / ACKs (push up)"| cloudside
```

**Why each edge capability stays (and the matching live epic where relevant):**
- **Transmission / basestation control** — millisecond IR/RF; cannot be remote. (`dtoflow-transmission` is the *cloud→edge bridge*, not a replacement.)
- **Flash & display‑page switch** — tiny real‑time commands; cloud round‑trip would add unacceptable delay.
- **Store map / geo** — tied to physical store layout + basestation positions; source of truth at the edge.
- **Local status/ACKs** — labels ACK to the basestation; R3Server aggregates and pushes status up (Label Status APIs, PLT‑2355).

> **`dtoflow-transmission`** is the seam: a Cloud Run service that takes a finished `renderedimage` (+ `storeesl` target) from DTOflow and delivers it down to the correct store's R3Server, which then performs the actual radio transmit. The cloud decides *what* should be on a label; R3Server makes it *physically happen*.

---

## 4. End‑to‑end in the target (item update → label)

```mermaid
config:
    layout: elk
sequenceDiagram
    participant ERP as ERP / Plaza Mobile
    participant ING as ingress / Apigee
    participant IR as item-registry-api
    participant SP as Spanner
    participant PS as Pub/Sub
    participant EV as studio-link-evaluator
    participant RN as studio-renderer
    participant TX as dtoflow-transmission
    participant R3 as R3Server (edge, thin)
    participant ESL as ESL

    ERP->>ING: PATCH item (new price)
    ING->>IR: route /items/* to cloud
    IR->>SP: write storeitemvalues (t/{tenant}/s/{store}/…)
    IR->>PS: dtoflow-changes-storeitemvalues.v1
    Note over PS,EV: Pub/Sub fans out to ALL subscribers in parallel (via CQS)
    par Evaluator Path
        PS-->>EV: storeitemvalues notification
        EV->>EV: re-evaluate CEL rules; if changed, write studiolink
    and Renderer Path (always runs)
        PS-->>RN: storeitemvalues notification
        RN->>RN: render with current studiolink + new item values
        RN->>SP: write studioeslimage → merger → eslimage
    end
    Note over TX,ESL: eslimage written → pricer-server (subscribes to eslimage.v1)
    TX->>R3: rendered image + target ESL
    R3->>ESL: IR/RF transmit
    ESL-->>R3: ACK
    R3-->>SP: storeeslstatus (pushed up)
```

Compare with the **today** flow in [doc 01 §6](01-systems-architecture.md#6-endtoend-a-price-change-today): the early steps move from one Store‑Unit's MySQL to shared Spanner + Cloud Run; only the final `R3 → ESL` hop is unchanged. The evaluator and renderer **both** subscribe to `storeitemvalues.v1` and run in parallel — there is no sequential "evaluate → render" pipeline. If the evaluator produces a new `studiolink`, the renderer (which also subscribes to `studiolink.v1`) gets a second trigger. In **Shadow Mode** the `TX → R3 → ESL` tail is intentionally **not** executed.

---

## 5. What moves vs. what stays

| Capability | Today | Target | Verdict |
|------------|-------|--------|---------|
| Item storage | per‑store MySQL | Spanner `storeitemvalues` | **Moves** |
| Item/Link APIs | R3Server REST | `item-registry-api`, `link-registry` | **Moves** (PLT‑2378, etc.) |
| Rendering | per‑Store‑Unit CPU | `studio-renderer` / `ecc-renderer` | **Moves** |
| Work dispatch | R3Server internal | CQS subscription fan‑out (GKE) | **Moves** (PLT‑169) |
| Gateway/auth | per‑store endpoints | Apigee + EVO token | **Moves** |
| Store metadata / users | CM + EVO | EVO (already) | **Already cloud** |
| **Transmission engine** | R3Server | R3Server | **Stays (edge)** |
| **Basestation control** | R3Server | R3Server | **Stays (edge)** |
| **Flash / display‑page** | R3Server | R3Server | **Stays (edge)** |
| **Store map / geo** | R3Server | R3Server | **Stays (edge)** |
| **Store‑Host / lifecycle** | Central‑Manager (GKE) | Central‑Manager (GKE) | **Stays** |

---

## 6. What this means for the consumer heads

- **Plaza Mobile** — item GET/PATCH + search move to the cloud (blocked on **PLT‑2378**); flash, map, display‑page, link‑departments keep calling R3Server. Its BFF becomes the place that *fans out* between cloud and edge.
- **Central‑Manager** — multi‑store bulk item update/delete + CSV move to the cloud (same **PLT‑2378**); **Store‑Host and store lifecycle stay**. Config push to cloud is later (PLT‑2353).
- **Store UI** — unchanged; already 100% cloud.
- **Plaza Actions** — already cloud‑native via Apigee/actions services.

---

## 7. Readiness snapshot (2026-06-30)

| Layer | State |
|-------|-------|
| DTOflow foundation (Spanner 29 tables, Pub/Sub **32 topics**, gRPC clients, **21 Cloud Run svcs**) | ✅ Live in `platform-dev-p01` |
| ChangeQueueService (PLT‑169) | 🟡 In Progress (GKE `platform` running) |
| DTOflow prod‑ready (PLT‑2118) | 🟡 Test |
| Accessibility / PSC (PLT‑2336) | 🟡 In Progress |
| Per‑API‑path routing (PLT‑2101) | 🟡 Selected for Dev (not started, Saikiran on vacation) |
| Item property validation (PLT‑2651) | 🔴 **Blocked / Unassigned** — single clearest gate on item pipeline |
| Item Patch APIs (PLT‑2378) | 🔴 **Blocked / Unassigned** |
| storeitemvalues export (PLT‑2483) | 🟡 Ready for Deploy (Johan Ekman) |
| CQS client in R3Server (PLT‑1870) | 🟡 Test (Daniel Pettersson) |
| Shadow Mode (PLT‑2354) | 🟡 **In Progress** |
| First real tenant (PLT‑2601) | 🔴 Backlog (Cristian Deaconeasa) |
| Ops readiness (load/monitoring/DR/cutover) | 🔴 Backlog |

**Bottom line for a new lead:** the *foundation is live*; the *gating work* is (1) unblock **PLT‑2651** (item property validation), (2) unblock & own **PLT‑2378** (Item Patch APIs), (3) land **Shadow Mode** on the Dev tenant (PLT‑2483 Ready for Deploy, PLT‑2354 In Progress), (4) decide the **first real tenant** (PLT‑2601 now in Backlog), then (5) build out **operational readiness** before any customer cutover.

---

### ← Back to [README](README.md) · [01 Architecture](01-systems-architecture.md) · [02 Tenant](02-tenant-model.md) · [03 Replatforming](03-replatforming-deep-dive.md) · [08 Delta Report](08-replatforming-delta-report.md)