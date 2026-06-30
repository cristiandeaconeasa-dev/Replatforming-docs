# 07 — M2M Token Manager Deep Dive (Central-Manager)

> **Scope:** The machine-to-machine (M2M) token manager in Central-Manager — what it is, how it works, where it's used, and how it relates to the user EVO token.
>
> **Validated:** 2026-06-17 against `chain-management-centralization/central-manager` source (`SharedStoreUnitEvoTokenServiceImpl.java`, `SharedStoreUnitEvoTokenType.java`, `CentralManagerProperties.java`) and `helm/pricer-central-solution/values.yaml`.
>
> **Accuracy note — corrected version** of the earlier `M2M-Token-Manager-Deep-Dive.md` draft. The draft was largely accurate; fixes: the additional-audiences field is actually **`serverAllowedAudiences`** (not `m2mClientAdditionalAudiences`), the dev default audience values, and a stale Jira reference. Flagged inline ✏️. Pairs with [05 — Core Concepts → EVO Token](05-core-concepts-deep-dive.md#4-evo-token).

---

## 1. What it is ✅
An **M2M token manager** obtains **service-level JWTs** from Auth0 with **no human in the loop**, using the OAuth2 **`client_credentials`** grant (client id + client secret → access token).

```
Human users → EVO tokens via login (password / SSO)
Services    → M2M tokens via client_credentials (client_id + client_secret)
```
In Pricer it is implemented as the Spring `@Service` **`SharedStoreUnitEvoTokenServiceImpl`** (package `se.pricer.centralmanager.security`). ✅

---

## 2. Why Central-Manager needs it ✅
When a **human** calls CM, the user's EVO token is forwarded. When CM acts **on its own behalf** (background jobs, forwarding to Store-Units, calling external renderer / DMS), there is no user token — so it mints a service token.

```mermaid
config:
    layout: elk
flowchart TB
    subgraph Human["👤 Human flow"]
        H1["login → EVO JWT"] --> H2["BFF/CM forwards user token → R3Server"]
    end
    subgraph M2M["🤖 M2M flow"]
        M1["CM needs to call a service"] --> M2["SharedStoreUnitEvoTokenService"]
        M2 --> M3["client_credentials → Auth0"]
        M3 --> M4["cache (Guava, 7h)"]
        M4 --> M5["call downstream with service token"]
    end
    style Human fill:#e3f2fd,stroke:#1565c0,color:#000
    style M2M fill:#e8f5e9,stroke:#2e7d32,color:#000
```

---

## 3. Implementation ✅ *verified line-by-line*

### 3.1 Service & token types
[`SharedStoreUnitEvoTokenType.java`](../../chain-management-centralization/central-manager/src/main/java/se/pricer/centralmanager/security/SharedStoreUnitEvoTokenType.java):
```java
// TODO: When building the integration towards tenant configurator we agreed with the core team to
// have only one M2M token per system, not one per integration. So for now we re-use the DMS token
// for the tenant configurator integration. Ideally it should be renamed into something more generic.
public enum SharedStoreUnitEvoTokenType {
  EXTERNAL_RENDERER,
  DMS,
}
```
> ✅ Both the enum values and that TODO are verbatim in the code.

### 3.2 Token caching config ✏️ *field name corrected*
[`CentralManagerProperties.java`](../../chain-management-centralization/central-manager/src/main/java/se/pricer/centralmanager/CentralManagerProperties.java) (Auth0 → EVO block):
```java
private String clientAudience    = "https://dev.pricer-plaza.com";          // line 202
private String m2mClientAudience = "https://internal.m2m.dev.pricer-plaza.com"; // line 203
private List<String> serverAllowedAudiences = List.of(                       // line 204 ✏️
    "https://m2m.dev.pricer-plaza.com",
    "https://internal.m2m.dev.pricer-plaza.com");
private String dmsClientId;                                                  // line 215
private int m2mTokenCacheExpiryInSeconds = 60 * 60 * 7;                      // line 216 = 25200 (7h)
```
> ✏️ The earlier draft called the list `m2mClientAdditionalAudiences`. The real field is **`serverAllowedAudiences`** (the resource-server's accepted audiences). There is also `externalRendererClientId` / `dmsClientId` for the two token types.

### 3.3 Token fetch flow ✅
```mermaid
config:
    layout: elk
sequenceDiagram
    participant CM as Central-Manager
    participant Cache as Guava LoadingCache
    participant SM as GCP Secret Manager
    participant Auth0
    CM->>Cache: getSharedMachineToMachineToken(EXTERNAL_RENDERER)
    alt cached & fresh
        Cache-->>CM: cached JWT
    else miss/expired
        Cache->>CM: load → fetchEvoToken(type)
        CM->>SM: getSecretString("auth0-" + clientId)
        SM-->>CM: client_secret
        CM->>Auth0: authenticateEvoM2m("client_credentials", audience, clientId, secret, tenantUuid)
        Auth0-->>CM: { access_token, ... }
        CM->>CM: expiresAt = jwt.decode(access_token).getExpiresAt()
        CM->>Cache: store (expireAfterWrite 25200s)
    end
```

Key code in [`SharedStoreUnitEvoTokenServiceImpl.java`](../../chain-management-centralization/central-manager/src/main/java/se/pricer/centralmanager/security/SharedStoreUnitEvoTokenServiceImpl.java):
```java
public static final String EVO_AUTH_0_CLIENT_SECRET_PREFIX = "auth0-";   // line 27

private SharedStoreUnitEvoToken fetchEvoToken(SharedStoreUnitEvoTokenType evoTokenType) {
    String clientId = switch (evoTokenType) {
        case EXTERNAL_RENDERER -> props.getAuth0().getEvo().getExternalRendererClientId();
        case DMS               -> props.getAuth0().getEvo().getDmsClientId();
    };
    String clientSecret =
        secretManagerTemplate.getSecretString(EVO_AUTH_0_CLIENT_SECRET_PREFIX + clientId);
    var response = auth0Retrofit.authenticateEvoM2m(
        "client_credentials",
        props.getAuth0().getEvo().getM2mClientAudience(),
        clientId, clientSecret,
        props.getTenantUuid()).execute();
    if (response.isSuccessful()) {
        String accessToken = response.body().getAccessToken();
        Instant expiresAt  = evoJwtDecoder.decode(accessToken).getExpiresAt();
        return new SharedStoreUnitEvoToken(accessToken, expiresAt);
    }
}
```

### 3.4 Cache (Guava) ✅
```java
this.evoTokenCache = CacheBuilder.newBuilder()
    .expireAfterWrite(props.getAuth0().getEvo().getM2mTokenCacheExpiryInSeconds(), TimeUnit.SECONDS)
    .build(CacheLoader.from(this::fetchEvoToken));               // line 43-46

public SharedStoreUnitEvoToken getSharedMachineToMachineToken(SharedStoreUnitEvoTokenType type)
        throws ExecutionException { return evoTokenCache.get(type); }   // line 53
```
The cache is keyed by `SharedStoreUnitEvoTokenType` and reloads via `fetchEvoToken` on miss/expiry. ✅

---

## 4. Helm configuration ✏️ *field name corrected*
[`helm/pricer-central-solution/values.yaml`](../../chain-management-centralization/helm/pricer-central-solution/values.yaml) (`auth0.evo` block):
```yaml
auth0:
  evo:
    clientAudience: https://pricer-plaza.com            # (dev: https://dev.pricer-plaza.com)
    m2mClientAudience: https://pricer-plaza.com
    serverAllowedAudiences:                              # ✏️ not 'm2mClientAdditionalAudiences'
      - https://pricer-plaza.com
      - https://m2m.pricer-plaza.com
      - https://internal.m2m.pricer-plaza.com
    domain: auth.iam.pricer-plaza.com                    # Auth0/EVO domain
    externalRendererClientId:
    dmsClientId:
    # 25200 = 7 hours (evo m2m tokens expire in 8 hours)
    m2mTokenCacheExpiryInSeconds: 25200
```
> ✅ The "tokens expire in 8 hours, cache 7 hours" relationship is documented in the values.yaml comment — the cache deliberately refreshes ~1h before Auth0 expiry to avoid races.

Environment is wired in `central-manager-deployment.yaml` (Spring relaxed-binding names, e.g. `PRICER_CM_AUTH0_EVO_M2M_CLIENT_AUDIENCE`, `PRICER_CM_AUTH0_EVO_M2M_TOKEN_CACHE_EXPIRY_IN_SECONDS`).

---

## 5. M2M token vs EVO user token ✅
| Aspect | EVO user token | M2M service token |
|--------|----------------|-------------------|
| Who | a human (associate/admin) | Central-Manager itself |
| Grant | login (auth code / SSO) | `client_credentials` |
| Identity | user (sub/role/tags) | service (`client_id`) |
| Tenant | from Auth0 claim | passed explicitly (`props.getTenantUuid()`) |
| Secret | user password | client secret in **GCP Secret Manager** (`auth0-<clientId>`) |
| Cache | none | Guava `LoadingCache`, 7h |
| Lifetime | per session | ~8h (cache refreshes at 7h) |
| Usage | BFF/CM forwards user token → R3Server | CM → external renderer / DMS / Store-Units |

```mermaid
config:
    layout: elk
flowchart LR
    subgraph U["👤 EVO user token"]
        U1["login → JWT (sub/tenant/role/tags)"]
    end
    subgraph M["🤖 M2M service token"]
        M1["client_credentials → JWT (client_id, tenantUuid)"]
        M2["Guava cache 7h"]
    end
    style U fill:#e3f2fd,stroke:#1565c0,color:#000
    style M fill:#e8f5e9,stroke:#2e7d32,color:#000
```

---

## 6. Where M2M tokens are used ✏️ *Jira status refreshed*
CM mints M2M tokens to call services on its own behalf. The two concrete token types in code are:
- **`EXTERNAL_RENDERER`** — calls to the external rendering service.
- **`DMS`** — Device Management Service integration (and, per the TODO, **re-used for the tenant-configurator** integration — one token per system, not per integration).

Other CM-initiated, server-to-server scenarios that rely on service auth include multi-store item operations forwarded to each Store-Unit's R3Server, and configuration/ECC data movement.
> ✏️ The earlier draft tied this to **PLT-2573 "ECC Sync — On-Prem to Cloud Data Push"**, which is **Closed** as of 2026-06-17 (verify in Jira before citing it as active), and **PLT-2353 "Pricer Server config export to DTOflow"** (Backlog). Treat those epic links as status-dependent.

---

## 7. Summary ✅
`SharedStoreUnitEvoTokenServiceImpl` lets Central-Manager authenticate as a **trusted service**:
1. **Fetches** a JWT from Auth0 via `client_credentials`.
2. **Caches** it in a Guava `LoadingCache` for **7h** (Auth0 token lives ~8h).
3. **Reads secrets** from **GCP Secret Manager** (`auth0-<clientId>`), never from config/env.
4. **Two token types** today — `EXTERNAL_RENDERER`, `DMS` (intended to be unified).
5. **Tenant-scoped** by passing `tenantUuid` to Auth0.

---

### Related: [05 Core Concepts (EVO Token)](05-core-concepts-deep-dive.md#4-evo-token) · [02 Tenant Model](02-tenant-model.md)
