# Demo Data — Insurance Core

Indian-context seed data for client demos and local development.

## How to install

| Method | Command / action |
|--------|------------------|
| Fresh install (CLI) | During `bench --site <site> install-app insurance_core`, answer **Yes** to the demo-data prompt |
| Later (CLI) | `bench --site <site> execute insurance_core.demo_data.install_demo_data` |
| Desk | **Insurance Settings** → **Install Demo Data** |

All inserts are **idempotent** (unique keys are skipped if already present).

Non-interactive / CI installs skip the prompt and do **not** load demo data unless you run `install_demo_data` explicitly.

---

## Sample users (password for all: `admin`)

Created automatically when demo data is installed (via `create_sample_users`).

| Email | Name | Roles | Access |
|-------|------|-------|--------|
| `manager@insurance.demo` | Priya Sharma | Insurance Manager, System Manager | Full desk — policies, claims, RFQ, settings, reports |
| `agent@insurance.demo` | Rahul Mehta | Insurance Agent | Field / sales — clients, opportunities, quotations, policies |
| `claims@insurance.demo` | Ananya Patel | Claims Adjuster | Claims desk — intake, triage, settlement, cashless |
| `compliance@insurance.demo` | Vikram Singh | Compliance Officer | KYC, compliance records, grievances |
| `user@insurance.demo` | Neha Gupta | Insurance User | Limited operational — view policies & claims |
| `client@insurance.demo` | Arjun Kapoor | Customer (Website User) | Portal only — `/portal` |

**Password:** `admin` (same for every account above)

### Login URLs

- Desk: `/app` or `/login`
- Portal (client user): `/portal`

### Manual / reset

```bash
# Create (or skip if already present)
bench --site <site> execute insurance_core.create_sample_users.create_sample_users

# Force-reset password to admin on existing sample users
bench --site <site> execute insurance_core.create_sample_users.update_sample_user_passwords
```

---

## Volumes (defaults)

| Entity | Approx. count | Notes / ID pattern |
|--------|---------------|--------------------|
| Insurance Providers | ~8–12 | Indian insurers (Star Health, etc.) |
| Insurance Schemes | ~20 | 2–4 per underwriting provider; includes Engineering LOB |
| Agents | 25 | |
| Network Hospitals | 30 | TPA / cashless network |
| Clients | 800 | `CLT-DEMO-0001` … |
| Policies | 600 | `POL-DEMO-2024-0001` … (~75% of clients) |
| Claims | 150 | `CLM-DEMO-2025-0001` … |
| Flow AI triage showcase claims | 6 | `CLM-FLOW-DEMO-01` … `06` (see below) |
| Opportunities / Quotations | 200 | `OPP-DEMO-` / `QUO-DEMO-` |
| Grievances | 50 | |
| Cashless Authorizations | 40 | |
| Policy Endorsements | 60 | |
| Claim Recoveries | 25 | |
| Commission Payouts | 80 | |
| Communications | 100 | |
| Client KYC | 120 | |
| Compliance Records | 30 | |
| Insurer RFQ Rules | panel rules | Vertical / LOB / sum-insured criteria |
| Sample users | 6 | See table above |

Context is India-focused (cities, names, IRDAI-style provider numbers, INR amounts).

---

## Flow AI triage showcase claims

Curated claims kept in intake/review so you can demo **Frappe Flow Claim Triage** immediately after install.

| Claim | Expected triage outcome | Narrative |
|-------|-------------------------|-----------|
| `CLM-FLOW-DEMO-01` | process | Strong, well-documented hospitalisation |
| `CLM-FLOW-DEMO-02` | reject | Waiting period / pre-existing condition |
| `CLM-FLOW-DEMO-03` | pending | Missing documents, vague narrative |
| `CLM-FLOW-DEMO-04` | pending | High amount — specialist review |
| `CLM-FLOW-DEMO-05` | process | Clean cashless discharge, network hospital |
| `CLM-FLOW-DEMO-06` | reject | Excluded cosmetic / non-medical treatment |

### How to demo triage

1. Install and configure **Flow** (see [Flow_integration.md](Flow_integration.md)).
2. Open any Insurance Claim → **AI** → **Setup Flow Agent** (once).
3. Open `CLM-FLOW-DEMO-0x` → **AI** → **AI Triage (advisory)** or **AI Triage (apply)**.

---

## What is *not* seeded

- Pure child tables / logs without a parent demo path
- Policy Upload PDF layouts (use Desk to configure provider layouts)
- Insurance RFQ Detail rows that depend on live ERPNext RFQ documents (rules are seeded; full RFQ cycle is manual)

---

## Source modules

| Module | Role |
|--------|------|
| `insurance_core/demo_data.py` | Main seed orchestration (`install_demo_data`) |
| `insurance_core/create_sample_users.py` | Sample users + password helper |
| `insurance_core/install.py` | `after_install` → interactive demo prompt |

---

## Security note

Demo accounts use a shared weak password (`admin`) for showcase convenience only.  
Do **not** enable these users on production sites. Disable or delete them after the demo, or change passwords.
