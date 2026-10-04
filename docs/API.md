# Insurance Core — API Documentation

This document describes the HTTP APIs exposed by the **Insurance Core** Frappe app (`insurance_core`).

All custom endpoints are Frappe **RPC methods** under:

```
POST|GET /api/method/<dotted.path>
```

Example (portal dashboard):

```
GET /api/method/insurance_core.portal.portal_dashboard
```

Standard Frappe resource APIs (`/api/resource/<DocType>`, `/api/resource/<DocType>/<name>`) also work for DocTypes that the caller has permission to read/write. Prefer the scoped portal methods for customer-facing integrations.

---

## Table of contents

1. [Authentication](#1-authentication)
2. [Conventions](#2-conventions)
3. [Portal (customer self-service)](#3-portal-customer-self-service)
4. [AI claim triage](#4-ai-claim-triage)
5. [Broker RFQ / quotation](#5-broker-rfq--quotation)
6. [Provider API (insurer integrations)](#6-provider-api-insurer-integrations)
7. [Policy PDF upload](#7-policy-pdf-upload)
8. [Standard DocType resources](#8-standard-doctype-resources)
9. [Error handling](#9-error-handling)
10. [Related docs](#10-related-docs)

---

## 1. Authentication

| Method | How |
|--------|-----|
| **Session (browser / SPA)** | Log in via `/api/method/login` (or Desk). Cookie `sid` is sent automatically. Portal SPA also needs CSRF (`X-Frappe-CSRF-Token`). |
| **API key** | Header: `Authorization: token <api_key>:<api_secret>` |
| **OAuth** | `Authorization: Bearer <access_token>` |

**Portal methods** require a logged-in user whose **User.email** matches an **Insurance Client.email**. System Managers may pass `client=<Insurance Client name>` for testing.

**Guest access** is not enabled on these endpoints.

---

## 2. Conventions

| Item | Detail |
|------|--------|
| Content type | `application/x-www-form-urlencoded`, `multipart/form-data`, or JSON body (Frappe accepts form + JSON) |
| Response envelope | Success: `{ "message": <payload> }`. Errors: `{ "exc_type", "exception", "_server_messages", ... }` |
| Dates | `YYYY-MM-DD` |
| Money | Numeric (INR assumed in demo/seed data) |
| Names | DocType primary keys (e.g. `POL-0001`, `CLM-0001`) |
| Whitelist | Only `@frappe.whitelist()` methods are callable |

---

## 3. Portal (customer self-service)

**Module:** `insurance_core.portal`

All portal methods resolve the current user → Insurance Client and **scope every query/write to that client**. Unauthorized access to another client’s policy/claim raises `PermissionError`.

### 3.1 `portal_me`

Current user + linked client (app shell).

| | |
|--|--|
| **Path** | `insurance_core.portal.portal_me` |
| **Methods** | GET, POST |
| **Auth** | Logged-in user |

**Response (`message`):**

```json
{
  "user": {
    "name": "user@example.com",
    "full_name": "Jane Doe",
    "email": "user@example.com",
    "user_image": null
  },
  "client": {
    "name": "CLI-0001",
    "full_name": "Jane Doe",
    "email": "user@example.com",
    "phone": "+91...",
    "lifecycle_stage": "Policyholder"
  }
}
```

`client` is `null` if no Insurance Client is linked (except System Manager override).

---

### 3.2 `portal_search`

Search the client’s policies and claims.

| | |
|--|--|
| **Path** | `insurance_core.portal.portal_search` |
| **Methods** | GET, POST |
| **Params** | `q` (string, min 2 chars), `limit` (int, default 10, max 25) |

**Response:**

```json
{
  "policies": [
    { "name": "POL-...", "policy_number": "...", "status": "Active", "scheme": "...", "end_date": "2027-01-01" }
  ],
  "claims": [
    { "name": "CLM-...", "claim_number": "...", "status": "Submitted", "claim_type": "Reimbursement", "incident_date": "...", "claimed_amount": 10000 }
  ]
}
```

---

### 3.3 `portal_dashboard`

Summary stats + recent policies/claims.

| | |
|--|--|
| **Path** | `insurance_core.portal.portal_dashboard` |
| **Methods** | GET, POST |

**Response:**

```json
{
  "client": { "name": "...", "full_name": "...", "email": "...", "phone": "...", "lifecycle_stage": "..." },
  "stats": {
    "active_policies": 2,
    "total_policies": 5,
    "open_claims": 1
  },
  "policies": [ /* up to 5 */ ],
  "claims": [ /* up to 10 */ ]
}
```

---

### 3.4 `portal_list_policies`

| | |
|--|--|
| **Path** | `insurance_core.portal.portal_list_policies` |
| **Methods** | GET, POST |

Returns list of policies for the client (fields include `name`, `policy_number`, `status`, `scheme`, `provider`, `sum_assured`, `premium_amount`, `total_premium`, `start_date`, `end_date`, `payment_status`, `policy_document`).

---

### 3.5 `portal_get_policy`

| | |
|--|--|
| **Path** | `insurance_core.portal.portal_get_policy` |
| **Methods** | GET, POST |
| **Params** | `policy` (required) — Insurance Policy name |

**Response:**

```json
{
  "policy": { /* full as_dict */ },
  "members": [ /* policy_members */ ],
  "coverages": [ /* policy_coverages */ ],
  "documents": [ /* other_documents */ ]
}
```

---

### 3.6 `portal_list_claims`

| | |
|--|--|
| **Path** | `insurance_core.portal.portal_list_claims` |
| **Methods** | GET, POST |

Fields: `name`, `claim_number`, `policy`, `claim_type`, `status`, `claimed_amount`, `approved_amount`, `incident_date`, `submission_date`.

---

### 3.7 `portal_get_claim`

| | |
|--|--|
| **Path** | `insurance_core.portal.portal_get_claim` |
| **Methods** | GET, POST |
| **Params** | `claim` (required) |

**Response:**

```json
{
  "claim": { /* full as_dict */ },
  "policy_number": "POL-NUM-...",
  "documents": [ /* claim_documents child table */ ]
}
```

---

### 3.8 `portal_upload_claim_document`

Append a document to an open claim. Upload the file first via `/api/method/upload_file`, then pass the returned `file_url`.

| | |
|--|--|
| **Path** | `insurance_core.portal.portal_upload_claim_document` |
| **Methods** | POST (default whitelist) |
| **Params** | `claim`, `document_type`, `file_url` |

**Allowed `document_type`:**  
`Discharge Summary`, `Bills`, `Reports`, `ID Proof`, `FIR`, `Estimate`, `Other`

Fails if claim status is Settled / Closed / Rejected.

---

### 3.9 `portal_intimate_claim`

Create a new claim from the portal.

| | |
|--|--|
| **Path** | `insurance_core.portal.portal_intimate_claim` |
| **Methods** | POST |
| **Params** | `policy` (required), `claim_type`, `incident_date`, `claimed_amount`, `description`, `claimant` |

Policy must be Active, Grace Period, or Claimed.

**Response:** `{ "name": "CLM-...", "claim_number": "P-..." }`

---

### 3.10 `portal_request_endorsement`

| | |
|--|--|
| **Path** | `insurance_core.portal.portal_request_endorsement` |
| **Methods** | POST |
| **Params** | `policy`, `endorsement_type`, `description`, `new_value` (optional), `effective_date` (optional) |

**Response:** `{ "name": "...", "endorsement_number": "...", "premium_impact": ... }`

---

### 3.11 `portal_policy_print` / `portal_claim_print`

Return rendered HTML for policy schedule or claim / settlement letter.

| | |
|--|--|
| **Paths** | `insurance_core.portal.portal_policy_print`, `insurance_core.portal.portal_claim_print` |
| **Methods** | GET, POST |
| **Params** | `policy` **or** `claim`; for claim print: `settlement=1` for settlement letter |

---

### 3.12 `portal_chat` / `portal_chat_reset`

Optional AI assistant (requires Frappe Flow + configured Flow Agent titled **Insurance Portal Assistant**).

| | |
|--|--|
| **Path** | `insurance_core.portal.portal_chat` |
| **Params** | `message` (required, max 4000 chars), `session_id` (optional) |
| **Response** | `{ "reply", "session_id", "agent", "configured" }` |

`portal_chat_reset` → `{ "ok": true }` (client should clear local session).

---

## 4. AI claim triage

**Module:** `insurance_core.ai_triage`  
Requires **Frappe Flow** (`required_apps` includes `flow`). See [Flow_integration.md](Flow_integration.md).

### 4.1 `run_claim_ai_triage`

| | |
|--|--|
| **Path** | `insurance_core.ai_triage.run_claim_ai_triage` |
| **Params** | `claim_name` (required), `apply_status_change` (0/1, default 1) |

Runs eligibility tools + Flow Agent; may set claim status (process / reject / pending) and AI fields (`ai_success_probability`, `ai_recommended_action`, etc.).

### 4.2 `setup_claim_ai_triage`

| | |
|--|--|
| **Path** | `insurance_core.ai_triage.setup_claim_ai_triage` |

Idempotent: creates Flow Tools, Claim Triage Agent, optional trigger, and custom fields.

**Internal Flow tools** (not typically called directly over HTTP):  
`get_claim_eligibility`, `get_claim_context`, `apply_triage_decision`.

---

## 5. Broker RFQ / quotation

**Module:** `insurance_core.rfq` (package under `rfq_extension`; import path may be `insurance_core.rfq` or as installed).

ERPNext **Request for Quotation** and **Supplier Quotation** are left untouched. Extra data lives in **Insurance RFQ Detail** and **Insurance RFQ Insurer**.

### 5.1 `create_rfq_from_opportunity`

| | |
|--|--|
| **Path** | (as installed) `…rfq.create_rfq_from_opportunity` |
| **Params** | `opportunity` (Insurance Opportunity name), `max_insurers` (default 5) |

Creates ERPNext RFQ + Insurance RFQ Detail, runs **Insurer RFQ Rule** matching, populates suppliers / insurer child rows.

**Response:** `{ "rfq": "<ERPNext RFQ name>", "detail": "<Insurance RFQ Detail name>" }`

### 5.2 `select_insurers_on_detail`

Re-run rule engine on an existing Insurance RFQ Detail: `detail_name`, `max_insurers`.

### 5.3 `select_winning_quote`

| **Params** | `insurance_quotation` |

Marks the chosen quote path for conversion / policy issuance workflow.

**Supporting master:** **Insurer RFQ Rule** (LOB, sum insured bands, age, client type, etc.).  
**Provider link:** `Insurance Provider.erpnext_supplier` → ERPNext Supplier.

---

## 6. Provider API (insurer integrations)

**DocType:** Insurance Provider API  
**Module:** controller methods on that DocType.

### 6.1 `test_connection`

| **Path** | `insurance_core...insurance_provider_api.test_connection` (or `run_doc_method`) |
| **Params** | `name` — Insurance Provider API document name |

Validates credentials / OAuth / headers against the configured endpoint.

### 6.2 `fetch_quote`

Calls the remote insurer API with mapped request template and returns mapped response fields for quoting.

Configuration is per-provider (auth type, URL templates, JSON path mapping). Prefer Desk setup over ad-hoc HTTP to the insurer.

---

## 7. Policy PDF upload

**DocType:** Policy Upload  
**Module:** `policy_upload` controller.

### 7.1 `parse_policy_pdf`

| **Params** | `name` — Policy Upload document name |

Uses **Policy PDF Layout** (regex / section rules) + pdfplumber to extract policy number, provider, scheme, dates, sum assured, premium, insured name, terms, exclusions, etc. Sets status to **Parsed**.

### 7.2 `create_client_and_policy`

After review of extracted fields: creates or links **Insurance Client**, then creates **Insurance Policy**. Requires mapped provider/scheme and extracted core fields.

---

## 8. Standard DocType resources

Use Frappe REST for CRUD when the caller has Desk/API permissions:

```
GET    /api/resource/Insurance Policy
GET    /api/resource/Insurance Policy/<name>
POST   /api/resource/Insurance Policy
PUT    /api/resource/Insurance Policy/<name>
DELETE /api/resource/Insurance Policy/<name>
```

Common DocTypes: Insurance Client, Insurance Policy, Insurance Claim, Policy Endorsement, Insurance Scheme, Insurance Provider, Network Hospital, Cashless Authorization, Commission Payout, Insurance Opportunity, Insurance RFQ Detail, Policy Upload, etc.

**Filters example:**

```
GET /api/resource/Insurance Claim?filters=[["status","=","Submitted"]]&fields=["name","claim_number","claimed_amount"]&limit_page_length=20
```

---

## 9. Error handling

| Situation | Behaviour |
|-----------|-----------|
| Guest / no client link | `PermissionError` — “Please log in…” / “No insurance client profile…” |
| Wrong policy/claim owner | `PermissionError` — “You do not have access…” |
| Validation | `frappe.throw` with message (invalid document type, inactive policy, etc.) |
| HTTP | Typically 200 with exception payload, or 403/417 depending on Frappe version and `Accept` headers |

Always inspect `message` on success and `_server_messages` / `exc` on failure.

---

## 10. Related docs

| File | Topic |
|------|--------|
| [API_Usage_Guide.md](API_Usage_Guide.md) | Practical usage, Postman, SPA, CSRF |
| [Flow_integration.md](Flow_integration.md) | AI triage + Flow setup |
| [demo_data.md](demo_data.md) | Seed volumes and showcase records |
| Root `README.md` | Features, install, portal build |

**Postman collection:** [Insurance_Core_API.postman_collection.json](Insurance_Core_API.postman_collection.json)

---

*Insurance Core — broker platform APIs. Generated for VivaswanWorks/Insurance_Core.*
