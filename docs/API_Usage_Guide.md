# Insurance Core — API Usage Guide

Practical guide for calling Insurance Core APIs from Postman, scripts, or the customer portal SPA.

Companion docs: [API.md](API.md) (reference) · [Insurance_Core_API.postman_collection.json](Insurance_Core_API.postman_collection.json) (importable collection).

---

## 1. Base URL and paths

| Environment | Example base |
|-------------|--------------|
| Local bench | `http://127.0.0.1:8000` |
| Production | `https://your-site.example.com` |

Method call pattern:

```
{base}/api/method/insurance_core.portal.portal_dashboard
```

Resource pattern:

```
{base}/api/resource/Insurance Policy/POL-00001
```

---

## 2. Authentication

### 2.1 Session login (browser / Postman cookie)

```http
POST /api/method/login
Content-Type: application/x-www-form-urlencoded

usr=user@example.com&pwd=your-password
```

Response sets the `sid` cookie. Subsequent requests send that cookie.

### 2.2 API key (server-to-server)

1. Desk → User → API Access → Generate Keys  
2. Header on every request:

```http
Authorization: token <api_key>:<api_secret>
```

### 2.3 Portal CSRF (SPA only)

The Vue portal must send:

```http
X-Frappe-CSRF-Token: <token>
```

Token is injected into the page context (`csrf_token`) and mirrored to `window.csrf_token` in `frontend/src/main.js`. Without it, POST methods fail CSRF checks.

---

## 3. Portal client linkage

Portal APIs map **User.email → Insurance Client.email**.

If you see:

> No insurance client profile is linked to your account

then either:

- Create / update **Insurance Client** so `email` matches the logged-in User, or  
- As **System Manager**, pass `client=<Insurance Client name>` for testing.

Demo data seeds clients and users consistently; see [demo_data.md](demo_data.md).

---

## 4. Typical portal flows

### 4.1 App shell bootstrap

1. `portal_me` → user + client  
2. `portal_dashboard` → stats and recent rows  
3. Optional: `portal_search?q=...`

### 4.2 Browse policy → download schedule

1. `portal_list_policies`  
2. `portal_get_policy?policy=POL-...` (members, coverages, documents)  
3. `portal_policy_print?policy=POL-...` → HTML (render or print)

### 4.3 Intimate a claim

1. Ensure policy is Active / Grace Period / Claimed  
2. `portal_intimate_claim` with `policy`, `claim_type`, `incident_date`, `claimed_amount`, optional `description` / `claimant`  
3. Upload files via `/api/method/upload_file`  
4. `portal_upload_claim_document` with `claim`, `document_type`, `file_url`

### 4.4 Request endorsement

```http
POST /api/method/insurance_core.portal.portal_request_endorsement
policy=POL-...&endorsement_type=Address Change&description=New address...&effective_date=2026-10-15
```

### 4.5 Chatbot

```http
POST /api/method/insurance_core.portal.portal_chat
message=What documents do I need for a reimbursement claim?&session_id=
```

Requires Flow + agent titled **Insurance Portal Assistant**. If not configured, `configured: false` and a setup message is returned.

---

## 5. Desk / staff APIs

| Task | Method |
|------|--------|
| Run AI triage on a claim | `insurance_core.ai_triage.run_claim_ai_triage` (`claim_name`, optional `apply_status_change=0` for advisory) |
| One-time Flow wiring | `insurance_core.ai_triage.setup_claim_ai_triage` |
| RFQ from opportunity | RFQ extension `create_rfq_from_opportunity` |
| Parse uploaded policy PDF | Policy Upload `parse_policy_pdf` |
| Create policy from parse | Policy Upload `create_client_and_policy` |
| Test insurer connector | Insurance Provider API `test_connection` |

These require roles such as **Insurance Manager**, **System Manager**, or claims roles—not portal client users.

---

## 6. Postman setup

1. Import `docs/Insurance_Core_API.postman_collection.json`.  
2. Collection variables:

| Variable | Example |
|----------|---------|
| `baseUrl` | `http://127.0.0.1:8000` |
| `apiKey` | (optional) |
| `apiSecret` | (optional) |
| `policy` | `POL-...` |
| `claim` | `CLM-...` |

3. **Auth**  
   - Either use the **Login** request and enable cookie jar, or  
   - Set collection Authorization to type **API Key** / raw header `Authorization: token {{apiKey}}:{{apiSecret}}`.

4. Run **Portal** folder requests after login with a user linked to an Insurance Client.

---

## 7. cURL examples

**Login**

```bash
curl -c cookies.txt -X POST "$BASE/api/method/login" \
  -d "usr=client@example.com&pwd=password"
```

**Dashboard**

```bash
curl -b cookies.txt "$BASE/api/method/insurance_core.portal.portal_dashboard"
```

**Intimate claim**

```bash
curl -b cookies.txt -X POST "$BASE/api/method/insurance_core.portal.portal_intimate_claim" \
  -d "policy=POL-00001" \
  -d "claim_type=Reimbursement" \
  -d "incident_date=2026-09-20" \
  -d "claimed_amount=25000" \
  -d "description=Hospitalization"
```

**API key**

```bash
curl -H "Authorization: token $KEY:$SECRET" \
  "$BASE/api/method/insurance_core.portal.portal_list_policies"
```

---

## 8. SPA integration notes

- Portal routes (when frontend is built): `/insurance_core` — Dashboard, Policies, Claims, Intimate.  
- Other sidebar modules open Desk (`/app/...`) in a new tab.  
- Read APIs are whitelisted for GET and POST to simplify CSRF-sensitive environments.  
- File upload uses core `upload_file`; claim document rows store the returned URL.

---

## 9. Permissions checklist

| Caller | Expectation |
|--------|-------------|
| Portal client user | Only own policies/claims via portal methods |
| Insurance User / Adjuster | Desk claim workflow + AI triage |
| Insurance Manager / System Manager | RFQ rules, provider API config, policy upload, setup methods |
| API key user | Same as the User the key belongs to |

Never expose System Manager–only setup endpoints to the public SPA.

---

## 10. Troubleshooting

| Symptom | Check |
|---------|--------|
| 403 / PermissionError on portal | User email ↔ Insurance Client.email; not Guest |
| CSRF failed | `X-Frappe-CSRF-Token` + correct www context (`csrf_token` in page) |
| Empty dashboard | Client has no policies/claims; seed demo data |
| Chat always “not configured” | Install Flow, enable model, create agent titled Insurance Portal Assistant |
| RFQ create fails | Opportunity has Line of Business; matching Insurer RFQ Rules exist |
| PDF parse empty | Policy PDF Layout for that provider; pdfplumber installed |

---

*For endpoint field-level detail, see [API.md](API.md).*
