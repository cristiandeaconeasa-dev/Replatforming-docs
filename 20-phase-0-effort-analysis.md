# 20 — Phase 0 Effort Estimation Analysis

> **Scope:** Analysis of time tracking and effort estimates for all 18 Phase 0 epics across M1 (Platform Foundation) and M2 (Shadow Mode Validation). Identifies gaps between current estimates and the mid-August 2026 deadline.
>
> **Deadline:** Mid-August 2026 (~15 August). Today: 1 July 2026. **Remaining: ~32 working days (6.5 weeks) assuming full attendance.** Reduce by 5 days per engineer-week of vacation — July–August is peak holiday season in Sweden.
>
> **Data pulled:** 2026-07-01 — live Jira (`project = PLT`, all Phase 0 epics), including subtask breakdowns and aggregated time tracking.

---

## 1. Raw Data — All Phase 0 Epics

| Epic | Inc | Summary | Status | Assignee | Orig Est | Remaining | Spent | Subtasks |
|------|-----|---------|--------|----------|----------|-----------|-------|----------|
| PLT-2294 | 1.1 | ID & alias validation | ✅ Closed | Bart De Boer | 2w | 2w | — | 0 |
| PLT-169 | 1.1 | ChangeQueueService | 🟡 In Progress | Johan Ekman | 5w | 1w | 4w | 0 |
| PLT-2792 | 1.1 | Services own CQS queues | 🟡 In Progress | Bart De Boer | **Not set** | **Not set** | **Not set** | 9 |
| PLT-2478 | 1.1 | PS ↔ CQS/DTOflow design | 🟡 In Progress | Sreekanth S. | **Not set** | **Not set** | **Not set** | 0 |
| PLT-1870 | 1.2 | CQS client in R3Server | 🟡 Test | Daniel P. | **Not set** | **Not set** | **Not set** | 0 |
| PLT-2336 | 1.3 | DTOflow PSC accessibility | 🟡 In Progress | Sreekanth S. | 1w | 1w | — | 0 |
| PLT-2101 | 1.3 | Per-API-path routing | 🟡 Selected | Saikiran K. | 3d | 2d | 1d | 0 |
| PLT-2118 | 1.3 | DTOflow PROD-ready cert | 🟡 Test | Bart De Boer | 5w | 2d | 4w 3d | 1 |
| PLT-2353 | 2.1 | Pricer Server config export | 🟡 In Progress | Bart De Boer | 1w 1d | 1w 1d | — | 0 |
| PLT-2483 | 2.1 | storeitemvalues export | 🟡 Ready | Johan Ekman | **Not set** | **Not set** | **Not set** | 0 |
| PLT-2496 | 2.1 | Link export | 🟡 Ready | **Unassigned** | **Not set** | **Not set** | **Not set** | 1 |
| PLT-2494 | 2.1 | ECC params/images/models | 🟡 In Progress | Johan Ekman | **Not set** | **Not set** | **Not set** | 0 |
| PLT-2495 | 2.1 | ECC fonts export | 🟡 Selected | **Unassigned** | **Not set** | **Not set** | **Not set** | 0 |
| PLT-2492 | 2.1 | ESL Status DTO export | 🟡 In Progress | Bart De Boer | **Not set** | **Not set** | **Not set** | 3 |
| PLT-2488 | 2.1 | itemproperties export | 🟡 Code Review | **Unassigned** | **Not set** | **Not set** | **Not set** | 2 |
| PLT-2714 | 2.1 | itemproperties startup | 🟡 Selected | **Unassigned** | **Not set** | **Not set** | **Not set** | 0 |
| PLT-2497 | 2.2 | Consume-ignore-linked mode | ✅ Closed | Unassigned | **Not set** | **Not set** | **Not set** | 0 |
| PLT-2354 | 2.2 | Shadow Mode orchestration | 🟡 In Progress | Daniel P. | 1w 2d | 1w 2d | — | 0 |

> **Aggregate time tracking** (sum of epic + all subtask estimates per Jira): PLT-169 has 20w aggregate original (4 subtasks at 5w each), 4w remaining. PLT-2118 has 20w aggregate original, 2d remaining. All other aggregates match the epic-level figure or are not set.

---

## 2. Headline Finding: 11 of 18 Epics Have No Estimates

| Has Estimate | Count | Epics |
|-------------|-------|-------|
| **Estimated** | 7 | PLT-2294, 169, 2336, 2101, 2118, 2353, 2354 |
| **Not set** | 11 | PLT-2792, 2478, 1870, 2483, 2496, 2494, 2495, 2492, 2488, 2714, 2497 |

Of the 11 without estimates:
- **2 are closed or Ready for Deploy** (PLT-2497, 2483, 2496) — low risk, mostly done
- **2 are in Code Review** (PLT-2488) or Selected (PLT-2714) — implementation mostly done, review or assignment remaining
- **2 are In Progress, unestimated** (PLT-2792 with 9 subtasks, PLT-2478) — **high risk**
- **2 are In Progress, unestimated, similar to estimated peers** (PLT-2494, 2492) — medium risk
- **1 is in Test** (PLT-1870) — low risk, mostly done

**Without estimates, sprint planning is blind.** Team capacity cannot be allocated and the lead cannot answer "will Phase 0 close by mid-August" with data.

---

## 3. PLT-2354: The Single Most Critical Estimate Error

**Current estimate:** 1w 2d (7 working days)

**Why this is wrong:** Shadow Mode orchestration is not a feature — it is the integration of every Phase 0 deliverable into one coordinated system. It must:

1. Activate parallel execution across all 8 data pipes simultaneously
2. Capture and compare every `dtoflow-transmission` drop against edge output
3. Validate 100% rendered-image parity across all three Shadow Mode tenants
4. Run continuously for 24+ hours without intervention
5. Handle failure modes: pipe stalls, image mismatches, config drift, event ordering

**Comparable epics for scale reference:**

| Epic | What it built | Actual effort |
|------|---------------|---------------|
| PLT-169 | ChangeQueueService — single service, single domain | 5w |
| PLT-2118 | DTOflow PROD-ready — single domain certification | 5w |

PLT-2354 must coordinate **all domains across all pipes**. It is not a 7-day task. A realistic estimate:

| Phase | Activity | Duration |
|-------|----------|----------|
| Skeleton | Connect orchestrator to all pipes, verify each pipe responds | 1w |
| Parallel run | Run all pipes simultaneously, fix ordering/timing issues | 1.5w |
| Parity validation | Compare images, fix rendering diffs | 1.5w |
| Multi-tenant | Repeat on Evo-Se and Application-Stage | 1w |
| **Total** | | **~5w (25 working days)** |

**Corrected estimate: 5w, not 1w 2d. Delta: +3.5w (+18 days).**

This correction alone consumes most of the remaining 32 working days.

---

## 4. Suggested Estimates for Unestimated Epics

### M1 Inc 1.1 — Core Event Routing

| Epic | Current | Suggested | Rationale |
|------|---------|-----------|-----------|
| PLT-2792 | Not set | **2w** | 9 subtasks (PLT-2793–2801). Services managing their own CQS queues is configuration + testing work across multiple services. Bart De Boer. |
| PLT-2478 | Not set | **1.5w** | PS ↔ CQS/DTOflow integration design. Sreekanth S. |

### M1 Inc 1.2 — Cloud/Edge Bridge

| Epic | Current | Suggested | Rationale |
|------|---------|-----------|-----------|
| PLT-1870 | Not set | **3d remaining** | In Test. Implementation done. Remaining work is test pass + bug fixes. |

### M2 Inc 2.1 — Core Data Tap

| Epic | Current | Suggested | Rationale |
|------|---------|-----------|-----------|
| PLT-2483 | Not set | **1d remaining** | Ready for Deploy. Done or nearly done. |
| PLT-2496 | Not set | **1d remaining** | Ready for Deploy. Done or nearly done. Also unassigned — needs owner. |
| PLT-2494 | Not set | **3d remaining** | In Progress, Johan Ekman. ECC params/images/models. Similar pattern to PLT-2483. |
| PLT-2495 | Not set | **2d** | Selected, unassigned. ECC fonts export only — narrow scope. **Needs owner.** |
| PLT-2492 | Not set | **3d remaining** | In Progress, Bart De Boer. 3 subtasks. ESL Status DTO. |
| PLT-2488 | Not set | **1d remaining** | Code Review. Implementation done. Review + merge only. Unassigned — **needs reviewer assigned.** |
| PLT-2714 | Not set | **1d remaining** | Code Review. Same as PLT-2488. |

---

## 5. Remaining Effort — Corrected Summary

### Known remaining (epics with estimates, corrected)

| Epic | Status | Corrected Remaining | Assignee |
|------|--------|--------------------|----------|
| PLT-169 | In Progress | 1w | Johan Ekman |
| PLT-2792 | In Progress | 2w (suggested) | Bart De Boer |
| PLT-2478 | In Progress | 1.5w (suggested) | Sreekanth S. |
| PLT-1870 | Test | 3d (suggested) | Daniel P. |
| PLT-2336 | In Progress | 1w | Sreekanth S. |
| PLT-2101 | Selected | 2d (+ reassign overhead) | **Saikiran on vacation** |
| PLT-2118 | Test | 2d | Bart De Boer |
| PLT-2353 | In Progress | 1w 1d | Bart De Boer |
| PLT-2483 | Ready | 1d | Johan Ekman |
| PLT-2496 | Ready | 1d | **Unassigned** |
| PLT-2494 | In Progress | 3d | Johan Ekman |
| PLT-2495 | Selected | 2d | **Unassigned** |
| PLT-2492 | In Progress | 3d | Bart De Boer |
| PLT-2488 | Code Review | 1d | **Unassigned** |
| PLT-2714 | Code Review | 1d | **Unassigned** |
| PLT-2354 | In Progress | **5w (corrected from 1w 2d)** | Daniel P. |

### Totals

| Metric | Value |
|--------|-------|
| **Sum of all corrected remaining estimates** (person-days) | **~77 person-days** |
| **Parallelism factor** (5 engineers working concurrently) | ÷ 2–3× |
| **Critical-path elapsed time** (Daniel P. → PLT-2354 dominates) | **~28 working days** |
| Available working days (1 Jul → 15 Aug, full attendance) | **32 working days** |
| **Buffer** | **~4 days** |

> **Methodology:** Raw person-day totals are not useful for deadline assessment because 5 engineers work in parallel. The critical path runs through Daniel Pettersson (PLT-2354 at 5w = 25d, plus PLT-1870 at 3d, plus Inc 2.3 validation gate at ~5d) = ~33 days. With aggressive overlap between PLT-2354 completion and validation start, the realistic elapsed minimum is ~28 days. This leaves ~4 days of buffer — zero margin for error.

---

## 6. Per-Person Capacity Analysis

| Person | Epics | Corrected Remaining | Feasible in 32 days? |
|--------|-------|--------------------|----------------------|
| **Bart De Boer** | PLT-2792 (2w), 2118 (2d), 2353 (1w 1d), 2492 (3d) | ~4.1w (~21d) | **Tight but possible** — if 2488/2714 reviews are handled by others |
| **Johan Ekman** | PLT-169 (1w), 2483 (1d), 2494 (3d) | ~2w (~10d) | **Comfortable** |
| **Daniel Pettersson** | PLT-1870 (3d), 2354 (5w corrected) | ~5.6w (~28d) | **Critical path.** 28 of 32 days consumed by PLT-2354 alone. Zero buffer. |
| **Sreekanth S.** | PLT-2478 (1.5w), 2336 (1w) | ~2.5w (~13d) | **Comfortable** |
| **Saikiran Katta** | PLT-2101 (2d) | 2d + reassign overhead | **On vacation.** PLT-2101 must be reassigned immediately. |
| **Unassigned** | PLT-2496 (1d), 2495 (2d), 2488 (1d), 2714 (1d) | ~5d total | **Needs owners this week.** |

**Bart De Boer has the most load** — 4 epics plus he's building PLT-2359 (Phase 2 ECC parity) in parallel. This workload is unsustainable for one person.

**Daniel Pettersson is on the critical path.** PLT-2354 alone consumes 28 of 32 available days. This leaves zero buffer for bugs, rework, or the 24h validation gate (Inc 2.3).

---

## 7. Can Phase 0 Close by Mid-August?

### Verdict: **High risk. Likely slip of 1–2 weeks without corrective action.**

Three factors make mid-August unlikely with current estimates:

1. **PLT-2354 corrected to 5w** — Daniel Pettersson's critical path extends to late August at best. Even with aggressive parallel work, the 24h multi-tenant validation gate (Inc 2.3) needs at least 3–5 days to execute and can't start before PLT-2354 is code-complete.

2. **Unassigned epics are invisible work.** PLT-2496, 2495, 2488, 2714 — four epics with no owners. Combined they represent ~5 days of work plus review cycles. Until owners are assigned, these don't move.

3. **No buffer for the validation gate.** Inc 2.3 (Multi-Tenant Shadow Validation) has zero epics and isn't tracked in Jira. It requires 24+ hours on each of 3 tenants back-to-back. If image parity fails on any tenant, the clock resets. Realistically, this gate needs 5–7 working days after PLT-2354 is code-complete.

### Realistic timeline with corrections (target end weeks)

| Week | Date | Milestone / Increment Target |
|------|------|------------------------------|
| W27 | Jul 1-4 | Assign owners. Reassign PLT-2101. Set estimates. |
| **W28** | Jul 7-11 | **Inc 2.1 target.** PLT-169 finishes. Export pipes (2483, 2494, 2496, 2495) close. |
| **W29** | Jul 14-18 | **Inc 1.1 + 1.2 target.** PLT-2792, 2478, 2336 close. PLT-2354 skeleton phase. |
| **W30** | Jul 21-25 | **Inc 1.3 + M1 target.** PLT-2354 parallel run + parity validation phase. |
| **W31** | Jul 28-Aug 1 | **Inc 2.2 target.** PLT-2354 multi-tenant phase. Begin Inc 2.3. |
| W32 | Aug 4-8 | Inc 2.3 validation — 3 tenants × 24h. Bug fixes. |
| W33 | Aug 11-15 | Buffer week. Parity re-runs. Final sign-off. |
| **W34** | Aug 17-23 | **Inc 2.3 + M2 + Phase 0 target.** ← REALISTIC |

---

## 8. Immediate Actions Required

### This Week (Week 27)

| # | Action | Owner | Impact |
|---|--------|-------|--------|
| 1 | **Correct PLT-2354 estimate to 5w** in Jira | Daniel P. / Lead | Stops the program from operating on a 1w 2d fiction |
| 2 | **Set estimates on all 11 unestimated epics** | Lead / epic owners | Enables sprint planning. Use the suggestions in §4 as starting points. |
| 3 | **Assign owners to unassigned epics** (PLT-2496, 2495, 2488, 2714) | Lead | 5 days of work sitting idle |
| 4 | **Reassign PLT-2101** — Saikiran is on vacation | Lead | 2d task. Sreekanth S. or someone with ingress/routing familiarity. |
| 5 | **Relieve Bart De Boer** — he owns 4 active epics + Phase 2 work | Lead | Spread PLT-2492 or PLT-2353 to another engineer |
| 6 | **Create a Jira epic or task for Inc 2.3** (Multi-Tenant Shadow Validation) | Lead / Daniel P. | Currently invisible — no Jira artifact exists for the Phase 0 exit gate |

### Before Week 30

| # | Action |
|---|--------|
| 7 | Run first 24h parity check on Replatforming-Dev as soon as PLT-2354 is skeleton-complete. Don't wait for all pipes to be perfect. |
| 8 | Confirm summer vacation schedules for all 5 engineers. Any additional time off in August further compresses the window. |
| 9 | If PLT-2354 is at risk of slipping past Week 31, consider splitting Inc 2.3: validate Replatforming-Dev and Evo-Se in parallel, leave Application-Stage for the buffer week. |

---

## 9. Risks Introduced by Estimate Gaps

| Risk | Severity | Detail |
|------|----------|--------|
| **Deadline set against fictional data** | 🔴 Critical | Mid-August target was agreed with PLT-2354 at 1w 2d. The corrected 5w estimate changes the programme's end date by nearly a month. Stakeholders must be informed. |
| **Bart De Boer overload** | 🟡 High | 6 epics across M1, M2, and M5. No single engineer can sustain this breadth. Risk of burnout + quality degradation. |
| **Invisible validation gate** | 🟡 High | Inc 2.3 has zero Jira epics and zero estimated hours. Without a tracked artifact, it will be forgotten until the last week — at which point there's no time to fix parity failures. |
| **Summer vacation compression** | 🔴 High | July–August is peak vacation season in Sweden. 32 working days assumes 100% attendance — an unrealistic assumption. Each week of vacation for Daniel P. or Bart adds 5 days to the critical path. Confirm vacation schedules immediately and rebaseline the timeline. |
| **No buffer anywhere** | 🟡 Medium | The corrected timeline has zero slack. Any bug, any parity failure, any sick day pushes the deadline. |

---

## 10. Recommendations for Going Forward

1. **Treat PLT-2354 as the programme's heartbeat.** It is not "an epic in M2 Inc 2.2" — it is the integration of everything Phase 0 produces. Give it the visibility and resourcing of a Milestone gate, not a feature ticket.

2. **Make estimates mandatory before sprint planning.** 11 of 18 epics with no estimates is not a data gap — it's a planning failure. Every epic entering a sprint must have an original estimate. Retros should flag unestimated epics as process debt.

3. **Create a Jira epic for Inc 2.3.** The 24h multi-tenant validation gate is the Phase 0 exit criterion. It needs a tracked Jira artifact with subtasks: (a) Replatforming-Dev 24h run, (b) Evo-Se 24h run, (c) Application-Stage 24h run, (d) parity report, (e) sign-off.

4. **Re-baseline the Phase 0 target date.** With corrected estimates, the realistic close is late August (Week 34). Communicate this to stakeholders now, not in the first week of August when the slip is already visible.

5. **Track burndown against corrected estimates.** Once all 18 epics have estimates, create a burndown chart from Week 27 to the target close. Update weekly in the status doc.

---

> **Companion docs:** [15 — Overall Status](15-overall-status.md) (current epic states) · [19 — Delivery Framework](19-dimension-frameworks.md) (Phase → Milestone → Increment → Epic hierarchy) · [17 — Phase 1 Plan](17-phase-1-plan.md) (what Phase 0 gates unlock)
