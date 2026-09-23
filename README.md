# Insurance Core – Overview & Features

## Core Modules
1. **Insurance Provider** – Master data for insurers, TPAs, brokers
2. **Insurance Scheme** – Product / plan definitions
3. **Policy Management** – Issuance, endorsements, renewals, status
4. **Claims Management** – Full claims lifecycle
5. **Client Lifecycle Management** – Prospect → Policyholder → Renewal / Lapse
6. **Compliance Tracking** – Regulatory, audit, document control
7. **Automated Communications** – Reminders, status updates, multi-channel

## Additional Features

### A. Quotation / Proposal Engine
- Generate personalized quotes from Scheme + client details (age, sum insured, members, loadings)
- Versioned proposals, convert to Policy with one click
- Comparison of multiple schemes side-by-side

### B. Premium Calculation Engine
- Central service / method that all modules call (`insurance_core.premium.calculate_premium`)
- Supports age-band, sum-insured slabs, family floater, loadings, discounts, taxes
- Audit log of every calculation (`Premium Calculation Log`)

### C. Endorsement Management
- DocType **Policy Endorsement** with workflow: Draft → Submitted → Approved → Applied / Rejected
- Types: Member Addition/Deletion, Sum Insured Change, Address Change, Nominee Change, Correction, Cancellation
- Auto estimate of premium impact; apply updates the parent policy
- Desk buttons: Approve, Reject, Apply, Estimate Premium Impact
- Portal: clients can request endorsements from policy detail

### D. Reinsurance (optional)
Broker platforms do not need reinsurance as a primary workflow. The module is **available but not in the default sidebar**.

- **Reinsurance Treaty** master (code, type Treaty/Facultative, reinsurer, default cession %, retention limit, validity)
- Policy fields: reinsurance type, treaty link, reinsurer, cession %
- Selecting a treaty copies type / % / reinsurer when empty
- On claim Approve / Settle: auto **Claim Recovery** (type Reinsurance) for the cession share
- Desk: open via Awesome Bar / search (“Reinsurance Treaty”); Preview Cession / Create Recovery on claim
- To surface in nav: add a Workspace Sidebar item when your process places facultative cover

### E. Commission & Agency Management
- **Commission Rule** (scheme / provider / event + rate and/or fixed amount)
- Auto accrual of **Commission Payout**:
  - **Issue / Renewal** when policy becomes Active
  - **Collection** when `payment_status` becomes Paid
  - Positive premium impact on applied endorsements
- Approve → Mark Paid workflow; Agent Commission summary API

### F. TPA / Cashless / Network Hospital
- **Network Hospital** with TPA link, cashless flag, empanelment dates, specialties
- **Cashless Authorization** workflow: Requested → Under Review / Query → Approved / Rejected → Utilized
- Cashless claims require an active cashless network hospital
- Auto TPA resolution from hospital (or provider type TPA)
- Auto-create authorization when cashless claim is Submitted
- Desk buttons on claim: Request / Open Authorization; on authorization: Approve / Reject / Mark Utilized

### G. Document Generation
- Jinja templates under `insurance_core/templates/print_formats/`:
  - Policy Schedule
  - Claim Form
  - Settlement Letter
- API: `insurance_core.api.get_print_html` / portal download

### H. Portal / Customer Self-Service (optional)
- **Vue SPA is optional.** Desk works fully without Vite/frontend build.
- When built: SPA at `/insurance_core` (Dashboard, Policies, Claims, Intimate Claim)
- Left sidebar groups match Desk **Workspace Sidebar** (Catalog → Policies → Claims → Operations → System)
- Download policy schedule; download settlement letter for settled claims
- API module: `insurance_core.portal` (scoped by client email ↔ logged-in user)

### I. Analytics & MIS
- Agent Commission summary
- Further Insights dashboards planned (see `specs/08_Integration.md`)

### J. AI Claim Triage (Frappe Flow)
- Deterministic eligibility score + LLM judgment via [Frappe Flow](https://github.com/frappe/flow_client)
- Desk buttons: **AI Triage**, **AI Triage (advisory only)**, **Setup Flow Agent**
- Actions: process (Under Review), reject, or pending with suggestion document
- See [docs/Flow_integration.md](docs/Flow_integration.md) for install, config, and usage

## Installation

This repository is a Frappe app. Place it under `frappe-bench/apps/insurance_core`, then:

```bash
# Install / migrate the app on a site (Desk + Workspace Sidebar — no frontend required)
bench --site <site> install-app insurance_core
# or after pull:
bench --site <site> migrate
bench --site <site> clear-cache
```

Optional customer portal (Vue SPA):

```bash
cd frontend && yarn && yarn build
# Dev: yarn dev
```

SPA route: `/insurance_core`. Built assets: `/assets/insurance_core/frontend/`.
Desk left nav is seeded by `ensure_workspace_sidebar()` and matches portal groups.

**Python deps:** `pdfplumber` (Policy PDF Upload) is installed automatically on
`after_install` / `after_migrate` via `ensure_pdfplumber()`. Prefer also listing
it in the app root `pyproject.toml` / `requirements.txt` so `bench get-app` pulls
it up front:

```text
pdfplumber>=0.11.0
```

For AI claim triage, also install and configure **Flow** — see [docs/Flow_integration.md](docs/Flow_integration.md).

## Usage

### Endorsements (Desk)
1. Create **Policy Endorsement** linked to a policy.
2. Optionally click **Estimate Premium Impact**.
3. **Approve** (Insurance Manager), then **Apply to Policy**.

### Commissions
1. Define **Commission Rule** rows (event Issue / Renewal / Collection; rate and/or fixed amount).
2. Ensure the policy `agent` matches an **Insurance Agent** (code or name).
3. When policy status becomes **Active**, a **Commission Payout** is accrued (Issue/Renewal).
4. When `payment_status` becomes **Paid**, a Collection payout is accrued.
5. Approve and Mark Paid from the payout form.

### Reinsurance
1. Create **Insurance Provider** with type Reinsurer (optional).
2. Create **Reinsurance Treaty** (cession %, reinsurer, Active).
3. On large policies set **Reinsurance Type**, **Treaty**, and/or **Cession %**.
4. On claim settlement, a **Claim Recovery** (Reinsurance) is created automatically.
5. Use claim buttons **Preview Cession** / **Create Recovery** as needed.

### Cashless / TPA
1. Maintain **Network Hospital** rows (cashless enabled, linked TPA).
2. Create claim with type **Cashless** and select the hospital.
3. On Submit, a **Cashless Authorization** is created and TPA is resolved.
4. Approve authorization (sets auth code + approved amount), then **Mark Utilized** after treatment.

### AI Claim Triage
1. Install Flow and configure a model (see [docs/Flow_integration.md](docs/Flow_integration.md)).
2. On an **Insurance Claim**, use **AI → Setup Flow Agent** once.
3. Run **AI Triage (advisory only)** to preview, or **AI Triage** to apply process / reject / pending.

### Print formats
```python
frappe.call("insurance_core.api.get_print_html", doctype="Insurance Policy", name="POL-…")
frappe.call("insurance_core.api.get_print_html", doctype="Insurance Claim", name="CLM-…", template_key="claim_settlement")
```

### Customer portal
1. Link the client’s email to a Frappe User.
2. Open `/insurance_core` while logged in as that user.
3. View policies, download schedule, intimate claims, request endorsements, download settlement letters.

## Resources

- [Vue 3](https://v3.vuejs.org/guide/introduction.html)
- [Vue Router](https://next.router.vuejs.org/guide/)
- [Frappe UI](https://github.com/frappe/frappe-ui)
- [TailwindCSS](https://tailwindcss.com/docs/utility-first)
- [Vite](https://vitejs.dev/guide/)
- [Frappe Flow](https://github.com/frappe/flow_client) — native AI agents, tools, and triggers (used for claim triage; see [docs/Flow_integration.md](docs/Flow_integration.md))

## Credits

Core development by **dinesh-samant**.

The following features were developed with assistance from **Grok** (xAI):

- Portal SPA shell (collapsible module sidebar, top search, profile menu)
- Policy Detail (coverages + documents)
- Claim Detail page + document upload
- Reinsurance Treaty integration and Claim Recovery
- TPA / Cashless Authorization workflow and Network Hospital enhancements
- Related print formats and portal APIs
- AI claim triage (Flow tools, agent, trigger, desk buttons)

Future collaborative commits carry the trailer `Co-authored-by: Grok <grok@x.ai>`.
