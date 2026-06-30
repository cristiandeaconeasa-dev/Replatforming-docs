# DTOflow — Deep Dive
> **The cloud data backbone of the Replatforming platform**
> **2026-06-29 correction:** CQS descriptions corrected throughout — it is a subscription-based fan-out layer with no routing logic of its own. Services self-configure their subscriptions. Architecture and section 8 diagrams updated to remove arrows that implied CQS routes to specific services.
>
> **2026-06-30 validation:** Jira statuses refreshed against live PLT project. PLT-2483 now **Ready for Deploy** (Johan Ekman). PLT-1870 in **Test** (Daniel Pettersson). PLT-2354 moved to **In Progress**.

---

## Architecture Overview

DTOflow is a **typed data platform** built on GCP. Services write typed DTOs to Spanner, changes are published as typed events on Pub/Sub, and the ChangeQueueService (CQS) delivers events to subscribing services. The pattern is **state → event → react**: services own their state, communicate through events, and downstream services react asynchronously.

```mermaid
flowchart TB
    subgraph clients["Writers / Readers"]
        IR["item-registry-api"]
        LR["link-registry"]
        ST["studio-* services"]
        ACT["actions-* services"]
    end

    subgraph storage["DTOflow Storage Layer"]
        SP[("Spanner 'dtoflow'<br/>29 DTO tables")]
        LFS["LFS (GCS)<br/>Large file storage"]
        IRS[("Spanner 'item-registry'<br/>ItemRequest table")]
    end

    subgraph events["Event Layer"]
        PS["Pub/Sub<br/>32 topics"]
        CQS["ChangeQueueService<br/>(GKE cluster 'platform')"]
    end

    subgraph edge["Edge Bridge"]
        TX["dtoflow-transmission"]
        R3["R3Server (per store)"]
    end

    clients -->|write/read DTOs| storage
    clients -->|publish changes| PS
    PS --> CQS

    Note["CQS notifies all subscribed services.<br/>Services self-configure subscriptions —<br/>no central routing logic."]
```

---

## 1. Storage Layer — Spanner Tables

The `dtoflow` database has 29 tables. Each table follows the same schema pattern:

| Column | Type | Purpose |
|--------|------|---------|
| `dto_type` | STRING(MAX) | Namespace/partition key (e.g., "storeitemvalues") |
| `id` | STRING(MAX) | Unique record ID within the type |
| `DATA` | BYTES(MAX) | Protobuf-serialized DTO payload |
| `checksum` | INT64 | Integrity verification |

**Primary key:** `(dto_type, id)` — allows efficient partitioning by type.

### Table Inventory by Domain

#### Item Domain
| Table | Purpose | Status |
|-------|---------|--------|
| `storeitemvalues` | Current price/properties per store per item | ✅ Live |
| `itemproperties` | Item property definitions (what properties are valid per store) | ✅ Live |
| `itemprocessingparameters` | Item processing configuration | ✅ Live |

#### Link Domain
| Table | Purpose | Status |
|-------|---------|--------|
| `link` | Core item-to-label associations | ✅ Live |
| `designerlink` | Designer/Canvas link records | ✅ Live |
| `ecclink` | Legacy ECC link records | ✅ Live |
| `studiolink` | Studio link records | ✅ Live |

#### ESL / Label Domain
| Table | Purpose | Status |
|-------|---------|--------|
| `storeesl` | ESL labels in a store (physical label inventory) | ✅ Live |
| `storeeslstatus` | ESL status reports (last ACK, battery, etc.) | ✅ Live |
| `esltype` | ESL type definitions (form factor, resolution) | ✅ Live |
| `esldriver` | ESL driver/hardware configuration | ✅ Live |

#### Rendering / Image Domain
| Table | Purpose | Status |
|-------|---------|--------|
| `renderedimage` | Rendered label images (output of studio/ecc renderers) | ✅ Live |
| `eslimage` | ESL image variants | ✅ Live |
| `studioeslimage` | Studio-generated ESL images | ✅ Live |
| `ecceslimage` | ECC-generated ESL images | ✅ Live |
| `eccimage` | ECC base images | ✅ Live |
| `designimage` | Design image assets | ✅ Live |

#### Design / Template Domain
| Table | Purpose | Status |
|-------|---------|--------|
| `design` | Design definitions (label layouts) | ✅ Live |
| `canvasdesign` | Canvas-based designs | ✅ Live |
| `canvastype` | Canvas type definitions | ✅ Live |
| `palette` | Color palette definitions | ✅ Live |
| `font` | Font definitions | ✅ Live |
| `eccfont` | ECC-specific fonts | ✅ Live |

#### ECC Model Domain
| Table | Purpose | Status |
|-------|---------|--------|
| `eccmodel` | ECC model definitions (label templates) | ✅ Live |
| `eccparameters` | ECC parameter configurations | ✅ Live |

#### Store / Configuration Domain
| Table | Purpose | Status |
|-------|---------|--------|
| `store` | Store metadata | ✅ Live |
| `communicationpack` | Communication pack configurations | ✅ Live |
| `taskdefinition` | Action task definitions | ✅ Live |
| `aliases` | ID alias mappings (dto_type → alias) | ✅ Live |

### Item-Registry Database (separate)

| Table | Columns | Purpose |
|-------|---------|---------|
| `ItemRequest` | tenantId, storeId, requestId, receivedTime, processedTime, type, status | Tracks item patch/delete requests through processing |

**1 table.** Used by item-registry-api to manage async item operations.

---

## 2. Event Layer — Pub/Sub Topics

**32 topics** in project `platform-dev-p01`. The naming convention is:

```
dtoflow-changes-<dto-type>.v1
```

Each DTO type gets its own change topic. When a record is written or updated in Spanner, the writing service publishes a change event to the corresponding topic.

### Known Topics by Domain

| Topic Pattern | Consumers |
|---------------|-----------|
| `dtoflow-changes-storeitemvalues.v1` | CQS → link-evaluator, renderer |
| `dtoflow-changes-link.v1` → migrated to `link.v2` | CQS → renderer |
| `dtoflow-changes-renderedimage.v1` | CQS → transmission |
| `dtoflow-changes-storeesl.v1` | CQS → status tracking |
| `dtoflow-changes-storeeslstatus.v1` | Status monitoring |
| `dtoflow-changes-ecclink.v1` | CQS → ECC rendering |
| `dtoflow-changes-designerlink.v1` | CQS → studio rendering |
| DLQ topics | Dead letter queues for failed events |
| Sync job topics | Periodic sync triggers |

> **Note:** 32 topics total. The full list can be retrieved via `gcloud pubsub topics list --project=platform-dev-p01`.

---

## 3. ChangeQueueService (CQS) — Subscription Fan-Out

CQS is the **subscription-based fan-out layer** that bridges Pub/Sub events to downstream service reactions. CQS has **no routing logic of its own** — each service declares its own subscriptions at startup via `CreateOrConfigureQueue`. CQS simply delivers notifications to whichever queues subscribed to a given DTO type.

```mermaid
flowchart LR
    subgraph input["Input"]
        PS[("Pub/Sub<br/>Change Events")]
    end

    subgraph cqs["ChangeQueueService (GKE)"]
        Q["Per-service Queues"]
        SORT["Priority Sort<br/>(by SLA timestamp)"]
    end

    subgraph workers["Worker Services"]
        EV["studio-link-evaluator<br/>(subs: commpack, link.v2, storeitemvalues)"]
        RN["studio-renderer<br/>(subs: studiolink, storeitemvalues, design, storeesl, canvasdesign)"]
        ECC["ecc-image-render-service<br/>(subs: ecclink, storeitemvalues, eccfont, eccmodel, eccparameters)"]
        TX["pricer-server<br/>(subs: eslimage, storeesl)"]
    end

    PS -->|drain topics| Q
    Q --> SORT
    SORT -->|notify| EV
    SORT -->|notify| RN
    SORT -->|notify| ECC
    SORT -->|notify| TX
```

**Status:** 🟡 In Progress (Johan Ekman, PLT-169). GKE cluster `platform` is running. CQS client integration in R3Server (PLT-1870, Daniel Pettersson) is in **Test**.

### Architecture Pattern

```
Service declares subscriptions at startup → DTO is written → Pub/Sub event → CQS delivers to every subscribed queue → each service dequeues independently
```

Each service **owns its own CQS queue** (PLT-2792, Bart De Boer — In Progress) and declares which DTO types it subscribes to. This means multiple services can subscribe to the same DTO type and all receive notifications in parallel — there is no sequential "dispatcher" or "orchestrator."

---

## 4. Service Inventory & Dependency Graph

All 21 Cloud Run services in `europe-north1`:

```mermaid
flowchart TB
    subgraph legend["Legend"]
        L1["🟢 Live"]
        L2["🟡 Code Review"]
        L3["🔵 In Progress / Test"]
    end

    subgraph storage_grp["Storage Layer"]
        DS["dtoflow-spanner 🟢"]
        LFS["dtoflow-lfs 🟢"]
    end

    subgraph item_grp["Item Pipeline"]
        IRA["item-registry-api 🟢"]
        IRW["item-registry 🟢"]
    end

    subgraph link_grp["Link Pipeline"]
        LKR["link-registry 🟢"]
        LKB["link-bfg 🟢"]
        LKS["link-storeasset-bfg 🟢"]
    end

    subgraph studio_grp["Studio / Rendering"]
        SR["studio-renderer 🟢"]
        SLE["studio-link-evaluator 🟢"]
        SDL["studio-design-library 🟢"]
        SSL["studio-scenario-library 🟢"]
        ECCR["ecc-renderer 🟢"]
        ECCLP["ecc-link-projector 🟢"]
        EIM["esl-image-merger 🟢"]
    end

    subgraph actions_grp["Actions"]
        AE["actions-executor 🟢"]
        AL["actions-library 🟢"]
    end

    subgraph edge_grp["Edge"]
        DT["dtoflow-transmission 🟢"]
        MH["migration-helper 🟢"]
        DCD["dtoflow-changequeue-dashboard 🟢"]
    end

    subgraph delivery_grp["Delivery"]
        DSS["delivery-sync-service 🟢"]
        DD["delivery-dashboard 🟢"]
    end

    DS --- LFS
    IRA --> IRW
    IRA --> DS
    IRW --> DS
    LKR --> DS
    LKB --> DS
    LKS --> DS
    SR --> DS
    SR --> LFS
    SLE --> SR
    ECCR --> DS
    ECCLP --> ECCR
    EIM --> ECCR
    DT --> DS
    DSS --> DS
    IRA -.->|"write events"| PS((Pub/Sub))
    LKR -.->|"write events"| PS
    SR -.->|"write events"| PS
```

### Service Maturity

| Service | Status | Notes |
|---------|--------|-------|
| dtoflow-spanner | ✅ Live | Core Spanner access service |
| dtoflow-lfs | ✅ Live | Large file storage (GCS-backed) |
| item-registry-api | ✅ Live | REST/gRPC item CRUD endpoint |
| item-registry | ✅ Live | Item state machine worker |
| link-registry | ✅ Live | Link CRUD |
| link-bfg | ✅ Live | Bulk link operations |
| link-storeasset-bfg | ✅ Live | Store-asset link operations |
| studio-renderer | ✅ Live | Label image rendering |
| studio-link-evaluator | ✅ Live | Link-to-design evaluation |
| studio-design-library | ✅ Live | Design template storage |
| studio-scenario-library | ✅ Live | Scenario management |
| ecc-renderer | ✅ Live | ECC rendering |
| ecc-link-projector | 🟢 Live | ECC link projection — Johan Ekman (merged 2026-06-23) |
| esl-image-merger | 🟢 Live | Image merging — Johan Ekman (merged 2026-06-23) |
| migration-helper | 🟢 Live | Migration support — Johan Ekman (merged 2026-06-23) |
| actions-executor | ✅ Live | Plaza Actions flash task executor |
| actions-library | ✅ Live | Plaza Actions task library |
| dtoflow-transmission | ✅ Live | Cloud→edge bridge |
| dtoflow-changequeue-dashboard | ✅ Live | CQS monitoring UI |
| delivery-sync-service | ✅ Live | Delivery sync |
| delivery-dashboard | ✅ Live | Delivery progress dashboard |

---

## 5. gRPC Client Libraries

DTOflow exposes auto-generated **gRPC clients** for type-safe access:

| Client | Language | Repository |
|--------|----------|------------|
| `evo-dtoflow-protos` | Protobuf | `PricerAB/evo-dtoflow-protos` |
| `evo-dtoflow-grpc-clients-java` | Java | `PricerAB/evo-dtoflow-grpc-clients-java` |
| `evo-dtoflow-grpc-clients-node` | Node.js | `PricerAB/evo-dtoflow-grpc-clients-node` |

These clients abstract the DTO serialization/deserialization and provide type-safe methods for reading and writing each DTO type. The root source of truth for all DTO schemas is the `evo-dtoflow-protos` repository.

---

## 6. Key Data Flow: Item Update End-to-End

This is the flow that exercises the most DTOflow components:

```mermaid
sequenceDiagram
    participant Client as Client (ERP/Plaza Mobile)
    participant IRA as item-registry-api
    participant SP as Spanner
    participant PS as Pub/Sub
    participant SLE as studio-link-evaluator
    participant SR as studio-renderer
    participant EIM as esl-image-merger
    participant R3 as R3Server (edge)
    participant ESL as ESL

    Client->>IRA: PATCH item (new price)
    IRA->>IRA: Validate properties (PLT-2651)
    IRA->>SP: Write storeitemvalues DTO
    IRA->>PS: Publish dtoflow-changes-storeitemvalues.v1
    Note over PS,SLE: Fan-out to ALL subscribers in parallel
    par Evaluator Path
        PS-->>SLE: storeitemvalues changed notification
        SLE->>SP: Read link.v2 (by_item alias), communicationpack
        SLE->>SLE: Re-evaluate CEL rules
        alt changed
            SLE->>SP: Write new studiolink DTO
            SLE->>PS: Emit dtoflow-changes-studiolink.v1
        else unchanged
            Note over SLE: No write — path ends
        end
    and Renderer Path (always runs)
        PS-->>SR: storeitemvalues changed notification
        SR->>SP: Read studiolink, design, storeitemvalues, storeesl
        SR->>SP: Write studioeslimage DTO
        SR->>PS: Emit dtoflow-changes-studioeslimage.v1
    end
    opt Evaluator produced new studiolink
        PS-->>SR: studiolink changed (2nd trigger)
        SR->>SP: Re-render with new design, write studioeslimage
    end
    PS-->>EIM: studioeslimage changed
    EIM->>SP: Merge with ecceslimage (if any), write eslimage
    EIM->>PS: Emit dtoflow-changes-eslimage.v1
    PS-->>R3: eslimage changed (pricer-server subscribed)
    R3->>ESL: IR/RF transmit to label
    ESL-->>R3: ACK
    R3->>SP: Write storeeslstatus → OK
```

---

## 7. DTOflow Spanner Table Relationships (Entity Model)

```mermaid
erDiagram
    storeitemvalues ||--o{ link : "item has links"
    link ||--o{ designerlink : "can be designer link"
    link ||--o{ ecclink : "can be ECC link"
    link ||--o{ studiolink : "can be studio link"
    storeitemvalues ||--o{ studioeslimage : "item used in studio render"
    storeitemvalues ||--o{ ecceslimage : "item used in ecc render"
    studioeslimage ||--|{ eslimage : "merged into"
    ecceslimage ||--|{ eslimage : "merged into"
    design ||--o{ studioeslimage : "design used for rendering"
    esltype ||--o{ storeesl : "esl type defines label"
    storeesl ||--o{ storeeslstatus : "esl has status"
    storeesl ||--o{ eslimage : "esl displays rendered image"
    store ||--o{ storeesl : "store has esls"
    store ||--o{ storeitemvalues : "store has items"
    eccmodel ||--o{ ecclink : "ecc model used in ecc links"
    eccmodel ||--o{ eccparameters : "ecc model has parameters"
    design ||--o{ designimage : "design has images"
    itemproperties ||--o{ storeitemvalues : "properties define valid values"
    taskdefinition ||--o{ actions_executor : "tasks executed by actions"
```

---

## 8. Pub/Sub Event-Driven Topology

```mermaid
flowchart LR
    subgraph producers["Event Producers"]
        IRA["item-registry-api"]
        LKR["link-registry"]
        SR["studio-renderer"]
        EIM["esl-image-merger"]
    end

    subgraph topics["Pub/Sub Topics (32)"]
        SIV["storeitemvalues.v1"]
        LNK["link.v2"]
        RDI["studioeslimage.v1<br/>ecceslimage.v1"]
        ESI["eslimage.v1"]
        ECC["ecclink.v1"]
        DLQ["DLQ topics"]
    end

    subgraph consumers["Event Consumers"]
        CQS["ChangeQueueService"]
    end

    subgraph workers["CQS Workers"]
        EV["link-evaluators"]
        RN["renderers"]
        MRG["merger"]
        TX["transmission"]
    end

    IRA --> SIV
    LKR --> LNK
    SR --> RDI
    EIM --> ESI
    LKR --> ECC

    SIV --> CQS
    LNK --> CQS
    RDI --> CQS
    ESI --> CQS
    ECC --> CQS

    SIV -.->|"dead letter"| DLQ
    LNK -.->|"dead letter"| DLQ
```

---

## 9. Current Status Summary

| Component | Count/Version | Status |
|-----------|--------------|--------|
| Cloud Run services | 21 (21 live) | ✅ |
| Spanner tables (`dtoflow`) | 29 DTO tables | ✅ |
| Spanner tables (`item-registry`) | 1 table (ItemRequest) | ✅ |
| Pub/Sub topics | 32 | ✅ |
| gRPC clients (Java) | `evo-dtoflow-grpc-clients-java` | ✅ |
| gRPC clients (Node) | `evo-dtoflow-grpc-clients-node` | ✅ |
| CQS (GKE) | Running on `platform` cluster | 🟡 In Progress |
| CQS client in R3Server (PLT-1870) | Test (Daniel Pettersson) | 🟡 |
| storeitemvalues export (PLT-2483) | Ready for Deploy (Johan Ekman) | 🟡 |
| DTOflow PROD-ready (PLT-2118) | In Test | 🟡 |
| Services own CQS queues (PLT-2792) | In Progress | 🟡 |
| Per-API-path routing (PLT-2101) | Not started | 🔴 |