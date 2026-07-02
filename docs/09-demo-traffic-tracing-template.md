# 11 — Reusable Prompt Template: Trace Any Demo Flow in GCP

> **Purpose:** A generic prompt you can reuse after any demo or test run to:
> 1. Validate which services received traffic (proving the flow works)
> 2. Trace the exact data path each request took through the architecture
> 3. Identify errors, bottlenecks, and missing pieces
> 4. Deepen your understanding of service contracts and dependencies
>
> **How to use:** Copy the template below, fill in the `[PARAMETERS]` section with your demo details, and run it against the GCP MCP toolset. The template works with the `gcp-infra` MCP server (`gcp_get_monitoring_metrics` tool).
>
> **Prerequisite:** The GCP MCP server (`gcp-infra`) must be connected and authenticated to `platform-dev-p01`.

---

## Template Instructions

Everything in `[SQUARE BRACKETS]` is a parameter you fill in for your specific demo. Everything else stays as-is.

### Parameters You Set

| Parameter | What to put | Example |
|-----------|-------------|---------|
| `[DEMO_NAME]` | Short name for this test | "Link Creation + Item Edit Demo 2" |
| `[DATE]` | Date of the demo | 2026-06-23 |
| `[HOURS_BACK]` | How many hours back to search (cover the demo window) | 2 or 6 or 24 |
| `[EXPECTED_USER_FLOW]` | What the operator did, step by step | "StoreUI → link creation → item add → item edit → verify in cloud" |
| `[SERVICES_IN_FLOW]` | Comma-separated list of expected Cloud Run services | "item-registry-api, item-registry, studio-link-evaluator, studio-renderer, studio-design-library, dtoflow-transmission, link-bfg" |
| `[EXPECTED_CHAIN]` | The expected sequence of services (→ separated) | "item-registry-api → item-registry → studio-link-evaluator & studio-renderer (parallel) → eslimage → dtoflow-transmission → R3Server" |
| `[EDGE_SERVICE]` | Did this flow involve the edge (R3Server)? | "Yes, but R3Server is not observable from Cloud Run metrics" or "No, cloud-only" |

---

## The Prompt Template

Copy everything between the `---` markers as the body of your query.

```
---
## Demo Traffic Analysis Request

### Parameters
- **Demo name:** [DEMO_NAME]
- **Date:** [DATE]
- **Lookback window:** [HOURS_BACK] hours
- **User flow:** [EXPECTED_USER_FLOW]
- **Services in flow:** [SERVICES_IN_FLOW]
- **Expected chain:** [EXPECTED_CHAIN]
- **Edge service involved?:** [EDGE_SERVICE]

### Step 1: Discover Which Services Have Traffic

For each service in the expected flow, query Cloud Monitoring metrics:
- Metric: `run.googleapis.com/request_count`
- Filter: `resource.labels.service_name="[SERVICE_NAME]"`
- Hours back: [HOURS_BACK]

Create a table like this for each service:

| Service | HTTP 2xx | HTTP 4xx | HTTP 5xx | Has Traffic? |
|---------|----------|----------|----------|-------------|
| item-registry-api | 0 | 15.5 | 0 | ✅ |
| studio-link-evaluator | 0.5 | 0 | 0 | ✅ |

Also query any OTHER Cloud Run services that might have been touched indirectly (check all 24 services). This reveals unexpected dependencies.

### Step 2: Trace the Data Flow Chronologically

Order all services by their first traffic timestamp. This reveals the actual sequence of calls:

1. [First service with traffic] → [timestamp] → [response codes]
2. [Second service with traffic] → [timestamp] → [response codes]
3. ...

Compare this with the EXPECTED_CHAIN. If the actual order doesn't match, that's a finding.

### Step 3: Identify Error Patterns

For each service with HTTP 5xx or high 4xx:
- What's the error rate (5xx / total)?
- Is it bursty (all at the start, then recovers) or persistent?
- Does the error pattern correlate with another service's success pattern?

### Step 4: Map the Observed Architecture

Create a mermaid diagram showing:
- Which services received traffic (color: green for 200-only, yellow for mixed, red for errors)
- Which services had NO traffic (mark as "not exercised")
- The actual data flow arrows between services
- The edge boundary

### Step 5: Extract Architecture Insights

Based on the live traffic data:
1. **Service contracts** — Which services call which? (inferred from traffic order + response patterns)
2. **Dependencies** — Do error rates in one service correlate with another?
3. **Latency hints** — Are there gaps between service timestamps that suggest queuing or retries?
4. **Scope gaps** — Were any EXPECTED services NOT touched? This tells you the flow is incomplete.
5. **Unexpected services** — Were any services touched that you didn't expect? This reveals hidden dependencies.

### Step 6: Recommendations

Based on the data:
- What's confirmed working? (200 OK, traffic observed)
- What needs investigation? (5xx errors, unexpected gaps)
- What's missing? (services with 0 traffic that should have been touched)
- What should the next demo test?

---

## Example Output (from 2026-06-23 Demo)

### Step 1: Traffic Discovery

| Service | HTTP 2xx | HTTP 4xx | HTTP 5xx | Has Traffic? |
|---------|----------|----------|----------|-------------|
| item-registry-api | 0 | 15.5 | 0 | ✅ |
| item-registry | 0 | 5.67 | 0 | ✅ |
| studio-link-evaluator | 0.9 | 0 | 0 | ✅ |
| studio-renderer | 1.0 | 0 | 0 | ✅ |
| studio-design-library | 3.6 | 0.4 | 0 | ✅ |
| dtoflow-transmission | 1.0 | 0 | 4.7 | ✅ |
| link-bfg | 1.4 | 0 | 2.1 | ✅ |
| link-registry | 0 | 0 | 0 | ❌ Not touched |
| ecc-renderer | 0 | 0 | 0 | ❌ Not touched |
| ecc-link-projector | 0 | 0 | 0 | ❌ Not touched |
| actions-executor | 0 | 0 | 0 | ❌ Not touched |
| esl-image-merger | 0 | 0 | 0 | ❌ Not touched |

### Step 2: Data Flow Chronology

1. **item-registry-api** (15:xx CET) — First traffic. StoreUI hitting the gateway.
2. **item-registry** (15:xx CET) — DTO writes. 4xx + 3xx (writes returning redirects, reads returning not-found).
3. **studio-link-evaluator** (15:xx CET) — First 200 OK. Link evaluation successful.
4. **studio-renderer** (15:xx CET) — 200 OK × 3. Image rendering successful.
5. **studio-design-library** (15:xx CET) — 200 OK. Design assets fetched.
6. **link-bfg** (15:xx CET) — 200 + 503. Bulk flow partially working.
7. **dtoflow-transmission** (15:xx CET) — 200 + 500. Edge delivery partially working.

**Finding:** The actual order confirms the expected chain. The cloud path (1→2→3→4→5) works. The edge path (6→7) has reliability issues.

### Step 3: Error Patterns

- **dtoflow-transmission:** 500 errors across a 2-hour window. Persistent, not transient. Suggests a systematic configuration or connectivity issue with R3Server.
- **link-bfg:** 503 errors at ~60% rate. Suggests service not scaled or backend dependency timing out.

### Step 4: Architecture Map

[See rendered mermaid diagram — shows green for evaluator/renderer/design-library, yellow for transmission/link-bfg, red for edge]

### Step 5: Architecture Insights

1. **Confirmed contract:** item-registry-api → item-registry → (Pub/Sub) → studio-link-evaluator & studio-renderer (parallel subscribers) → (Pub/Sub) → link-bfg/dtoflow-transmission
2. **Dependency discovered:** studio-renderer depends on studio-design-library for design assets
3. **Service not yet in flow:** link-registry, ecc-*, actions-*, esl-image-merger — not part of this demo
4. **Missing sink:** R3Server is the intended edge destination, but not observable from Cloud Run metrics

### Step 6: Recommendations

1. Investigate dtoflow-transmission 500 errors (network? auth? R3Server reachability?)
2. Fix link-bfg 503 errors (scaling? Spanner latency?)
3. Next demo should test: item → ECC link → ECC render path, and actions-executor for flash operations
---
```

## Quick Reference: All Available GCP Metric Sources

### Cloud Run Metrics (used today)

| GCP Metric Type | What It Reveals | Example Filter | Used Today? |
|-----------------|-----------------|----------------|-------------|
| `run.googleapis.com/request_count` | Request volume per service per response code | `resource.labels.service_name="studio-renderer"` | ✅ Yes |
| `run.googleapis.com/request_latencies` | Latency distribution (p50/p95/p99) | `resource.labels.service_name="studio-link-evaluator"` | ❌ No — add next time |
| `run.googleapis.com/container.cpu.utilizations` | CPU usage per revision | `resource.labels.service_name="studio-renderer"` | ❌ No — useful for renderer |
| `run.googleapis.com/container.memory.utilizations` | Memory usage per revision | `resource.labels.service_name="dtoflow-spanner"` | ❌ No |
| `run.googleapis.com/container/startup_latencies` | Cold start duration | `resource.labels.service_name="studio-renderer"` | ❌ No |

### Pub/Sub Metrics (not yet queried)

| GCP Metric Type | What It Reveals | Example Filter | Used Today? |
|-----------------|-----------------|----------------|-------------|
| `pubsub.googleapis.com/topic/send_request_count` | Messages published per topic | `resource.labels.topic_id="dtoflow-changes-storeitemvalues.v1"` | ❌ No — would confirm event chain |
| `pubsub.googleapis.com/subscription/ack_message_count` | Messages consumed by subscribers | `resource.labels.subscription_id="*"` | ❌ No — would confirm CQS consumption |

### Spanner Metrics (not yet queried)

| GCP Metric Type | What It Reveals | Example Filter | Used Today? |
|-----------------|-----------------|----------------|-------------|
| `spanner.googleapis.com/api/request_count` | Read/write ops per database | `resource.labels.database="dtoflow"` | ❌ No — would confirm DTO table access |

### GKE Metrics — ✅ CONFIRMED WORKING (2026-06-23)

| GCP Metric Type | What It Reveals | Example Filter | Used Today? |
|-----------------|-----------------|----------------|-------------|
| `kubernetes.io/container/memory/used_bytes` | **Memory per container in GKE** | `resource.labels.cluster_name="platform"` | ✅ **Yes — 148 time series returned** |
| `kubernetes.io/container/cpu/core_usage_time` | CPU core usage per GKE container | `resource.labels.cluster_name="platform"` (cumulative — needs delta) | ❌ Partial — metric exists, aggregation needs attention |

**How to filter GKE metrics to a specific namespace or workload:**
```
# Filter for containers with "changequeue" in their name:
gcp_get_monitoring_metrics(metricType="kubernetes.io/container/memory/used_bytes", filter="resource.labels.cluster_name="platform" AND resource.labels.container_name=@changequeue", hoursBack=2)
```

**Known limitation:** GKE metrics don't map directly by service name like Cloud Run. You need to know the Kubernetes namespace, pod name, or container name pattern. CQS runs as a deployment on the `platform` GKE cluster, so filtering by `container_name` or `namespace_id` on the `platform` cluster should work.

### Cloud Logging (not yet queried)

| GCP Metric Type | What It Reveals | Example Filter | Used Today? |
|-----------------|-----------------|----------------|-------------|
| `logging.googleapis.com/byte_count` | Log volume per service | `resource.labels.service_name="dtoflow-transmission"` | ❌ No — would help find error details |

## Quick Reference: All Cloud Run Services

```
studio-renderer
studio-link-evaluator
studio-design-library
studio-scenario-library
link-registry
link-bfg
link-storeasset-bfg
item-registry-api
item-registry
dtoflow-spanner
dtoflow-lfs
dtoflow-transmission
dtoflow-changequeue-dashboard
ecc-renderer
ecc-link-projector
esl-image-merger
migration-helper
actions-executor
actions-library
delivery-sync-service
delivery-dashboard
```

## Quick Reference: GKE Platform Cluster Workloads

The `platform` GKE cluster (`europe-north1-a`, 2 nodes) hosts:
- **ChangeQueueService (CQS)** — the main workload we need to trace
- Any other workloads deployed via Helm to the `platform` cluster

GKE metrics require filtering by `cluster_name="platform"` plus additional labels like `namespace_id`, `pod_name`, or `container_name` to isolate specific workloads.

## Step-by-Step: How to Run This Prompt

1. Open a new Claude Code session (or the current one)
2. Ensure the `gcp-infra` MCP server is connected
3. Fill in the `[PARAMETERS]` at the top of this template
4. **For Cloud Run services**, run:
   ```
   gcp_get_monitoring_metrics(metricType=run.googleapis.com/request_count, filter=resource.labels.service_name="[SERVICE]", hoursBack=[HOURS_BACK])
   ```
5. **For GKE workloads (CQS)**, run:
   ```
   gcp_get_monitoring_metrics(metricType=kubernetes.io/container/memory/used_bytes, filter=resource.labels.cluster_name="platform", hoursBack=[HOURS_BACK])
   ```
6. Collect all results into a traffic table
7. Order by first traffic timestamp → that's your actual data flow
8. Compare actual vs. expected → those are your findings
9. For any service with 5xx errors, check: is the error correlated with another service? Is it bursty or persistent?

## Integration with the Existing Prompts

This template is designed to be the "validation" step after a demo. It complements:
- **prompt-01-health-dashboard.md** — For ongoing health checks (not demo-specific)
- **prompt-05-code-traceability.md** — For tracing code paths (not runtime)
- **prompt-07-architecture-validation.md** — For validating architecture decisions

The key difference: this template is **data-driven from actual runtime traffic**, not from code analysis or Jira data.