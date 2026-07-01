# 19 — Delivery Framework: How We Structure the Replatforming Program

> **Audience:** PMO, CTO, engineering leads. This doc defines the delivery hierarchy used to plan, track, and report the Replatforming program.
>
> **Status:** Approved. Replaces the earlier Frameworks A, B, and C — which are now retired.

---

## 1. The Problem We Solved

The Replatforming program started with 42 Jira epics and no consistent way to group them. Three attempts failed:

| Attempt | Structure | Why It Failed |
|---------|-----------|---------------|
| **Original 10 "Dimensions"** | Arbitrary categories (DTOflow Foundation, Link Pipeline, Shadow Mode, CQS, etc.) | Mixed abstraction levels — infrastructure components sat alongside project phases. No one could name them consistently. |
| **Framework A: Workstreams** | W1-W5 by project milestone | Too coarse. "Foundation" (7 epics) sat "In Progress" for months with no intermediate checkpoints. Hides architecture. |
| **Framework B: Capabilities** | C1-C5 by system layer | Hides timeline. Can't tell if a capability is Phase 0 or Phase 2. Ops gets lumped into a catch-all bucket. |
| **Framework C: Workstream → Capability** | Two-level hierarchy merging A and B | Collapsed to 1:1 — W1 mapped only to C1, W2 mapped only to C4. Two labels for the same buckets. |

The root cause: all three frameworks were designed **top-down** — categorising epics that already existed into buckets that felt right on a slide. None of them answered the question a team needs every sprint: **"What are we building right now, and how do we prove it works?"**

---

## 2. The New Framework: Phase → Milestone → Increment → Epic

Four levels. Each answers a different question. None of them collapse into each other.

| Level | Question Answered | Timebox | Audience |
|-------|------------------|---------|----------|
| **Phase** | When in the program lifecycle? | Program duration | CTO, board |
| **Milestone** | What major outcome are we driving toward? | ~6 weeks | PMO, product owner |
| **Increment** | What can we demo at the end of this sprint cycle? | 2-4 weeks | Engineering team, stakeholders |
| **Epic** | What is the Jira unit of delivery? | Sprint | Scrum master, developers |

### Why This Works

1. **Every Increment ends with a named demo.** The team rehearses a specific, disprovable scenario — "Publish a dummy DTO to Pub/Sub and watch CQS fan it out to a Cloud Run queue." This defines what to build before work starts. It prevents the backward-building problem: implementation beginning before the outcome is clear.

2. **Dependencies are physically enforced.** You cannot demo Increment 2.2 (Shadow Execution) without Increment 2.1 (Data Tap) being live. The demo dependency chain prevents work from starting in the wrong order — even accidentally.

3. **Sprint-sized deliverables.** No more "Foundation" sitting In Progress for months. Each Increment is 2-4 epics — completable in 2-4 weeks with a verifiable result.

4. **Milestones survive Phase 0.** All 6 Milestones across all 3 Phases are defined upfront. When Phase 0 closes, the framework doesn't collapse — M3 is already named and scoped.

---

## 3. What We Discarded

### Flows (F1-F7)

We evaluated adding named end-to-end data paths (Item Ingest Flow, Render & Merge Flow, Edge Export Flow) as a mandatory delivery layer between Milestone and Increment. This was rejected: it added a fifth level without proportional value. "Which Flow am I in?" is an architecture question, not a delivery question. Flows survive as optional Jira labels on epics for filtering during architecture reviews.

### Capabilities (C1-C5)

The 5 Capabilities from Framework B — C1 Data Fabric, C2 Item Management, C3 Linking & Rendering, C4 Edge Bridging, C5 Ops Lifecycle — are retained as **reference tags** on every epic. They appear as a `[C2]` column in epic mapping tables. Architects read that column to understand system-layer impact. Delivery management ignores it. It does not appear in the delivery hierarchy.

---

## 4. The Full Milestone Plan

Six Milestones across three Phases. Defined upfront so the framework doesn't collapse when Phase 0 closes.

| Phase | Milestone | Goal | Increments |
|-------|-----------|------|-------------|
| **P0: Prove It** | M1: Platform Foundation | Core infrastructure operational — Spanner, Pub/Sub, CQS, ingress routing all live and certified | 3 |
| | M2: Shadow Mode Validation | Cloud pipeline runs in parallel with edge. Zero label risk. 24h parity confirmed. | 3 |
| **P1: Ship It** | M3: First Tenant Go-Live | Item and link API traffic cut over from R3Server to cloud. One real tenant live for basic flows. | 3 |
| | M4: Production Hardening | Monitoring, load testing, DR, cutover runbooks. All ops gates passed. | 3 |
| **P2: Scale It** | M5: Feature Parity | Timed updates, ECC sync, autoscaling, SLAs, segment labels, webhooks. | TBD |
| | M6: Full Migration | All tenants migrated. Feature parity with legacy R3Server achieved. | TBD |

---

## 5. Phase 0 Increment Breakdown

### M1: Platform Foundation

| Inc | Name | Epics | Demo |
|-----|------|-------|------|
| **1.1** | Core Event Routing | PLT-2294, PLT-169, PLT-2792, PLT-2478 | Publish a dummy DTO to Pub/Sub → CQS on GKE fans it out → a Cloud Run service dequeues it successfully |
| **1.2** | Cloud/Edge Bridge | PLT-1870 | R3Server (edge) receives and acknowledges a message from the cloud CQS queue |
| **1.3** | Production Ingress & Security | PLT-2336, PLT-2101, PLT-2118 | Hit a public ingress endpoint by URL path → correctly routed over PSC → hits a private Cloud Run backend |

### M2: Shadow Mode Validation

| Inc | Name | Epics | Demo |
|-----|------|-------|------|
| **2.1** | Core Data Tap | PLT-2353, PLT-2483, PLT-2496, PLT-2494, PLT-2495, PLT-2492, PLT-2488, PLT-2714 | Update a price in R3Server → all DTOs (storeitemvalues, link.v2, ECC params, ESL status, itemproperties) appear in Cloud Spanner within seconds |
| **2.2** | Shadow Execution & Studio Parity | PLT-2497, PLT-2354 | Same price change triggers cloud evaluator + renderer → eslimage written to Spanner. `consume-ignore-linked` drops the transmission command. Zero labels touched. |
| **2.3** | Multi-Tenant Shadow Validation | — | Run Replatforming-Dev → Evo-Se → Application-Stage back-to-back. 24 hours of continuous parity. Phase 1 gate cleared. |

---

## 6. Capability Reference Tags

Every epic carries one of these tags in the epic mapping tables. Used for architecture filtering — not a delivery level.

| Tag | Capability | Services |
|-----|-----------|----------|
| `[C1]` | Data & Routing Fabric | Spanner, Pub/Sub, CQS (GKE), Apigee, ingress-nginx, PSC |
| `[C2]` | Item Data Management | `item-registry-api`, `item-registry` |
| `[C3]` | Linking & Rendering | `link-registry`, `link-bfg`, `studio-link-evaluator`, `studio-renderer`, `ecc-link-projector`, `ecc-renderer`, `esl-image-merger` |
| `[C4]` | Edge Bridging | `dtoflow-transmission`, R3Server (thin edge) |
| `[C5]` | Ops Lifecycle | Monitoring, load testing, DR, cutover runbooks, tenant isolation |

---

## 7. Implementation

1. **Every Increment gets a Jira label or Fix Version.** Increments map directly to Jira: use `fixVersion = "M1.1"` or labels `m1-inc-1`.
2. **Sprint planning starts from Increments, not Epics.** The question is "what does Inc 1.3 need to demo?" — not "which epics are in W1?"
3. **Milestone gates are go/no-go.** M1 gate: all three Increment demos pass. M2 gate: 24h parity on three tenants. No partial credit.
4. **The full epic map lives in doc 15.** This doc defines the structure. [Doc 15](15-overall-status.md) contains the live status of every epic mapped to its Milestone, Increment, and Capability tag.

---

> **Status legend:** ✅ Closed = done · 🟢 Live = deployed · 🟡 In Progress / Test / Selected / Ready for Deploy = active · 🔴 Blocked = gated · 🔵 Backlog = not started
