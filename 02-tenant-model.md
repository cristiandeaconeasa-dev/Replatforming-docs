# 02 — The Tenant Model

> **Scope:** What a *tenant* is at Pricer, its characteristics, what it depends on, how isolation is enforced **today** vs. in the **target** cloud, and the special `Replatforming-Dev` tenant used for Shadow Mode.
>
> **Validated:** 2026-06-17. Builds on [doc 01](01-systems-architecture.md).

---

## 1. What a tenant is

> A **tenant is a Pricer customer — a retail chain** (e.g. a grocery group). It is the **top‑level isolation boundary**: every store, item, label, link and configuration belongs to exactly one tenant, and one tenant can never see another's data.

A tenant is **not** a GCP project, a Kubernetes namespace, or a single server. It is a **first‑class business entity** identified by a **`tenantUuid`**, owned by the **Tenant Service** (an EVO cloud service), and realized differently in each layer of the stack.

```mermaid
config:
    layout: elk
flowchart TD
    T["Tenant (retail chain)<br/>tenantUuid"] --> S1["Store A"]
    T --> S2["Store B"]
    T --> S3["Store …N"]
    S1 --> SU1["Store-Unit pod<br/>(R3Server + MySQL)"]
    S2 --> SU2["Store-Unit pod"]
    SU1 --> I1["Items / Labels / Links<br/>(scoped to the store)"]
    SU2 --> I2["Items / Labels / Links"]

    style T fill:#ede7f6,stroke:#5e35b1,color:#000
```

**One sentence:** *tenant → many stores → each store is a Store‑Unit → each Store‑Unit holds that store's items, labels and links.*

---

## 2. Characteristics

| Characteristic | Description |
|----------------|-------------|
| **Identity** | A stable `tenantUuid` (e.g. `cb5ebe26-…`) issued by the Tenant Service. Carried as a claim in the **EVO auth token** on API calls. |
| **Isolation** | Hard. Tenant A's stores/items/links are invisible to Tenant B. Enforced structurally (today: separate Store‑Units/DBs; target: row‑key prefix). |
| **Owns stores** | One tenant has many stores; each store has a UUID and a resolvable address. |
| **Maps to a PCS instance** | `tenant → pcsInstance → {store}.{pcsInstance}.pcm.pricer-plaza.com` — how a client finds the right R3Server. |
| **Feature profile** | Which capabilities the tenant uses (ECC‑only vs Designer, segment labels, flash, ERP integration type). This drives **which Replatforming features a tenant actually needs** — central to the Phase‑1 gate epic **PLT‑2601**. |
| **Scale profile** | #stores, items/store, #labels, ESL types, update volume — feeds load testing (PLT‑2576). |
| **Lifecycle** | Created/managed via Central‑Manager + Store‑Host; provisioning to the cloud is itself replatforming work (PLT‑2572 store onboarding, PLT‑2575 store DTO bootstrapping). |

---

## 3. What a tenant depends on

```mermaid
config:
    layout: elk
flowchart LR
    subgraph identity["Identity & resolution"]
        TS["Tenant Service (EVO)"] --> TUUID["tenantUuid"]
        TUUID --> PCS["pcsInstance mapping"]
        TUUID --> TOKEN["EVO token claim"]
    end
    subgraph mgmt["Management plane"]
        CM["Central-Manager<br/>(MySQL: stores, groups, users)"]
        SH["Store-Host (K8s)"]
    end
    subgraph runtime["Runtime plane"]
        SU["Store-Units (R3Server + MySQL)"]
        HELM["Helm values:<br/>tenantUuid, customerName"]
    end
    TOKEN --> CM
    PCS --> SU
    CM --> SH --> SU
    HELM --> SU

    style identity fill:#fff3e0,stroke:#f57c00,color:#000
    style mgmt fill:#e3f2fd,stroke:#1565c0,color:#000
    style runtime fill:#e8f5e9,stroke:#2e7d32,color:#000
```

1. **Tenant Service (EVO)** — the source of truth for tenant identity and the `tenant → pcsInstance` resolution that lets Plaza Mobile/ERP reach the right store backend.
2. **EVO auth token** — every API request carries the tenant claim; services authorize against it.
3. **Central‑Manager** — stores the tenant's stores, groups, users and roles in its own MySQL; orchestrates store lifecycle.
4. **Store‑Host + GKE** — turns tenant/store records into running Store‑Units. Helm `values.yaml` per deployment carries `tenantUuid` and `customerName`.
5. **Per‑store MySQL** — today, the actual item/label/link data lives here, one DB per store.

---

## 4. How isolation works **today** (PCS/EVO)

Tenancy is achieved by **physical separation**: each store is its own Store‑Unit with its own database, addressed by a tenant‑specific hostname.

```mermaid
config:
    layout: elk
flowchart TB
    REQ["Client request + EVO token (tenant claim)"] --> RES["Resolve tenant → pcsInstance → store host"]
    RES --> ING["ingress-nginx (TLS SNI)"]
    ING --> SU["Store-Unit for that store only"]
    SU --> DB[("That store's MySQL")]
```

- **Pros:** dead‑simple isolation (different process, different DB), blast radius of one store.
- **Cons:** no data sharing/aggregation across stores, N copies of the rendering engine, expensive at scale (thousands of Store‑Units), every store is an independently reachable endpoint to secure.

These cons are precisely what Replatforming addresses ([doc 03](03-replatforming-deep-dive.md)).

---

## 5. How isolation works in the **target** (DTOflow)

In the cloud, there are **no per‑store databases**. All tenants share one **Spanner** instance; isolation is enforced by a **row‑key prefix** baked into every DTO id (AIP‑122 style):

```
t/{tenantId}/s/{storeId}/{dtoType}/{id}
```

Example: `t/abc-123-uuid/s/store-456/storeitemvalues/item-789`.

```mermaid
config:
    layout: elk
flowchart TB
    subgraph spanner["Spanner 'dtoflow' (shared, 1000 PU)"]
        A["t/tenantA/s/store1/storeitemvalues/…"]
        B["t/tenantA/s/store2/link/…"]
        C["t/tenantB/s/store9/renderedimage/…"]
    end
    note["Same instance, same tables.<br/>Tenant boundary = key prefix t/{tenantId}/…"]
    spanner --- note
```

- **Multiple tenants share the same tables**; the `t/{tenantId}/…` prefix scopes every read/write.
- Isolation must therefore be **enforced in software** — validated by epic **PLT‑2578 (Tenant Security Isolation Validation)** and id/alias validation (PLT‑2294, now closed). This is a *higher‑stakes* model than physical separation: a missing prefix check is a cross‑tenant leak. Treat it as a top security concern.
- The 29 DTO tables in Spanner (`storeitemvalues`, `link`, `designerlink`, `ecclink`, `storeesl`, `storeeslstatus`, `renderedimage`, `esltype`, `design`, `canvasdesign`, …) all follow this keying.

---

## 6. The `Replatforming-Dev` tenant (Shadow Mode)

To validate the cloud pipeline **without risking a real customer**, the program uses an internal tenant:

- **It is a real tenant** in the Tenant Service (a `tenantUuid`), with the same isolation model — **not** a mock. Created by SRE (≈ March 2026); its PCS environment has been running for months.
- It has **no real stores/labels at risk**, making it safe to run **Shadow Mode**: R3Server exports item data to DTOflow and the full cloud chain processes it **without transmitting to any ESL**.
- Success criterion: a price update flows R3Server → DTOflow → CQS → evaluator → renderer and the rendered output **matches** what R3Server would have produced — proving the cloud path is correct before any customer is moved.

> **Phase 1 nuance (from the live backlog):** the *first real* tenant has **not** been selected yet — that decision is epic **PLT‑2601 "First Tenant Selection Criteria & Decision (Phase 1 gate)"**, currently assigned to the project lead and in Backlog (Critical). The June 15 weekly note suggests starting Phase‑0 validation with the Dev tenant and choosing a small, simple (ECC‑only, low‑volume, cooperative) customer as the first real tenant. Picking it is a prerequisite to finalizing Phase‑1 scope, because the tenant's **feature profile** determines which Phase‑1 epics are actually required.

---

## 7. Tenant ↔ entities cheat‑sheet

| Level | Identifier | Lives in (today) | Lives in (target) |
|-------|-----------|------------------|-------------------|
| Tenant | `tenantUuid` | Tenant Service + CM MySQL + Helm values | Tenant Service + Spanner key prefix |
| Store | store UUID | CM MySQL + Store‑Unit | `s/{storeId}` segment |
| Item | item id / **SIC** | per‑store MySQL | `…/storeitemvalues/{id}` |
| Label | PLID | per‑store MySQL (`pricerlabel`) | `…/storeesl/{id}` |
| Link | (item,label) | per‑store MySQL (`eclink`) | `…/link` or `…/designerlink` |

---

### Next: [03 — Replatforming Deep Dive →](03-replatforming-deep-dive.md)
