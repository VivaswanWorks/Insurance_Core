import json
import os
import subprocess
from pathlib import Path

import frappe


ROLES = [
	"Insurance Manager",
	"Insurance Agent",
	"Claims Adjuster",
	"Compliance Officer",
	"Insurance User",
]

# DocTypes to surface as shortcuts on the Home workspace (top-level only; no child tables).
WORKSPACE_SHORTCUTS = [
	("Insurance Policy", "DocType"),
	("Insurance Claim", "DocType"),
	("Insurance Client", "DocType"),
	("Insurance Scheme", "DocType"),
	("Insurance Agent", "DocType"),
	("Insurance Opportunity", "DocType"),
	("Insurance Quotation", "DocType"),
	("Policy Endorsement", "DocType"),
	("Cashless Authorization", "DocType"),
	("Commission Payout", "DocType"),
	("Insurance Settings", "DocType"),
]

# Home workspace link cards — top-level DocTypes only, segregated by section.
# (Child tables / nested docs are intentionally excluded.)
WORKSPACE_LINKS = [
	# Catalog
	{"type": "Card Break", "label": "Catalog"},
	{"type": "Link", "label": "Insurance Providers", "link_type": "DocType", "link_to": "Insurance Provider"},
	{"type": "Link", "label": "Insurance Schemes", "link_type": "DocType", "link_to": "Insurance Scheme"},
	# Policies
	{"type": "Card Break", "label": "Policies"},
	{"type": "Link", "label": "Policies", "link_type": "DocType", "link_to": "Insurance Policy"},
	{"type": "Link", "label": "Clients", "link_type": "DocType", "link_to": "Insurance Client"},
	{"type": "Link", "label": "Agents", "link_type": "DocType", "link_to": "Insurance Agent"},
	{"type": "Link", "label": "Quotations", "link_type": "DocType", "link_to": "Insurance Quotation"},
	{"type": "Link", "label": "Opportunities", "link_type": "DocType", "link_to": "Insurance Opportunity"},
	{"type": "Link", "label": "Endorsements", "link_type": "DocType", "link_to": "Policy Endorsement"},
	# Claims
	{"type": "Card Break", "label": "Claims"},
	{"type": "Link", "label": "Claims", "link_type": "DocType", "link_to": "Insurance Claim"},
	{"type": "Link", "label": "Cashless Auth", "link_type": "DocType", "link_to": "Cashless Authorization"},
	{"type": "Link", "label": "Network Hospitals", "link_type": "DocType", "link_to": "Network Hospital"},
	{"type": "Link", "label": "Claim Recoveries", "link_type": "DocType", "link_to": "Claim Recovery"},
	# Operations
	{"type": "Card Break", "label": "Operations"},
	{"type": "Link", "label": "Communications", "link_type": "DocType", "link_to": "Insurance Communication"},
	{"type": "Link", "label": "Grievances", "link_type": "DocType", "link_to": "Insurance Grievance"},
	{"type": "Link", "label": "Compliance", "link_type": "DocType", "link_to": "Compliance Record"},
	{"type": "Link", "label": "Commissions", "link_type": "DocType", "link_to": "Commission Payout"},
	# System (broker default: Settings only; Reinsurance is optional / not in nav)
	{"type": "Card Break", "label": "System"},
	{"type": "Link", "label": "Settings", "link_type": "DocType", "link_to": "Insurance Settings"},
]

# Number Cards seeded for the Dashboard workspace (DocType count KPIs).
# Filters use JSON string form expected by Number Card.
DASHBOARD_NUMBER_CARDS = [
	{
		"name": "IC Active Policies",
		"label": "Active Policies",
		"document_type": "Insurance Policy",
		"function": "Count",
		"filters_json": '[["Insurance Policy","status","=","Active"]]',
		"color": "#2490ef",
	},
	{
		"name": "IC Open Claims",
		"label": "Open Claims",
		"document_type": "Insurance Claim",
		"function": "Count",
		"filters_json": '[["Insurance Claim","status","not in",["Settled","Rejected","Closed","Cancelled"]]]',
		"color": "#e24c4c",
	},
	{
		"name": "IC Total Clients",
		"label": "Clients",
		"document_type": "Insurance Client",
		"function": "Count",
		"filters_json": "[]",
		"color": "#28a745",
	},
	{
		"name": "IC Open Opportunities",
		"label": "Open Opportunities",
		"document_type": "Insurance Opportunity",
		"function": "Count",
		"filters_json": '[["Insurance Opportunity","status","not in",["Won","Lost","Closed","Cancelled"]]]',
		"color": "#f6c343",
	},
	{
		"name": "IC Pending Endorsements",
		"label": "Pending Endorsements",
		"document_type": "Policy Endorsement",
		"function": "Count",
		"filters_json": '[["Policy Endorsement","status","in",["Draft","Submitted","Approved"]]]',
		"color": "#7c5cbf",
	},
	{
		"name": "IC Cashless Pending",
		"label": "Cashless Pending",
		"document_type": "Cashless Authorization",
		"function": "Count",
		"filters_json": '[["Cashless Authorization","status","in",["Requested","Under Review","Query"]]]',
		"color": "#17a2b8",
	},
]

# Dashboard Charts seeded for the Dashboard workspace (simple Count-by-field).
DASHBOARD_CHARTS = [
	{
		"name": "IC Claims by Status",
		"chart_name": "IC Claims by Status",
		"chart_type": "Group By",
		"document_type": "Insurance Claim",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"number_of_groups": 8,
		"type": "Donut",
		"is_public": 1,
	},
	{
		"name": "IC Policies by Status",
		"chart_name": "IC Policies by Status",
		"chart_type": "Group By",
		"document_type": "Insurance Policy",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"number_of_groups": 8,
		"type": "Bar",
		"is_public": 1,
	},
	{
		"name": "IC Opportunities by Status",
		"chart_name": "IC Opportunities by Status",
		"chart_type": "Group By",
		"document_type": "Insurance Opportunity",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"number_of_groups": 8,
		"type": "Pie",
		"is_public": 1,
	},
]

# Left sidebar (v15/v16 Workspace Sidebar).
# Desk nesting rule (ERPNext selling.json / Workspace Sidebar Item):
#   - top-level Links (Home, Dashboard): child=0
#   - Section Break: child=0, collapsible=1, indent=1
#   - Links under a Section Break: child=1  ← required or Desk flattens the list
# type: Section Break | Link | Spacer | Sidebar Item Group
# link_type: DocType | Page | Report | Workspace | Dashboard | URL
WORKSPACE_SIDEBAR_ITEMS = [
	# Top-level workspaces (not nested)
	{"type": "Link", "label": "Home", "link_type": "Workspace", "link_to": "Insurance Home", "icon": "home", "child": 0},
	{"type": "Link", "label": "Dashboard", "link_type": "Workspace", "link_to": "Insurance Dashboard", "icon": "dashboard", "child": 0},
	# Catalog
	{"type": "Section Break", "label": "Catalog", "icon": "organization", "child": 0, "collapsible": 1, "indent": 1, "keep_closed": 0},
	{"type": "Link", "label": "Insurance Providers", "link_type": "DocType", "link_to": "Insurance Provider", "icon": "organization", "child": 1},
	{"type": "Link", "label": "Insurance Schemes", "link_type": "DocType", "link_to": "Insurance Scheme", "icon": "file", "child": 1},
	# Policies
	{"type": "Section Break", "label": "Policies", "icon": "file-text", "child": 0, "collapsible": 1, "indent": 1, "keep_closed": 0},
	{"type": "Link", "label": "Policies", "link_type": "DocType", "link_to": "Insurance Policy", "icon": "file-text", "child": 1},
	{"type": "Link", "label": "Clients", "link_type": "DocType", "link_to": "Insurance Client", "icon": "users", "child": 1},
	{"type": "Link", "label": "Agents", "link_type": "DocType", "link_to": "Insurance Agent", "icon": "user", "child": 1},
	{"type": "Link", "label": "Quotations", "link_type": "DocType", "link_to": "Insurance Quotation", "icon": "file", "child": 1},
	{"type": "Link", "label": "Opportunities", "link_type": "DocType", "link_to": "Insurance Opportunity", "icon": "opportunity", "child": 1},
	{"type": "Link", "label": "Endorsements", "link_type": "DocType", "link_to": "Policy Endorsement", "icon": "edit", "child": 1},
	# Claims
	{"type": "Section Break", "label": "Claims", "icon": "file", "child": 0, "collapsible": 1, "indent": 1, "keep_closed": 0},
	{"type": "Link", "label": "Claims", "link_type": "DocType", "link_to": "Insurance Claim", "icon": "file", "child": 1},
	{"type": "Link", "label": "Cashless Auth", "link_type": "DocType", "link_to": "Cashless Authorization", "icon": "quality", "child": 1},
	{"type": "Link", "label": "Network Hospitals", "link_type": "DocType", "link_to": "Network Hospital", "icon": "healthcare", "child": 1},
	{"type": "Link", "label": "Claim Recoveries", "link_type": "DocType", "link_to": "Claim Recovery", "icon": "income", "child": 1},
	# Operations
	{"type": "Section Break", "label": "Operations", "icon": "tool", "child": 0, "collapsible": 1, "indent": 1, "keep_closed": 0},
	{"type": "Link", "label": "Communications", "link_type": "DocType", "link_to": "Insurance Communication", "icon": "mail", "child": 1},
	{"type": "Link", "label": "Grievances", "link_type": "DocType", "link_to": "Insurance Grievance", "icon": "message-circle", "child": 1},
	{"type": "Link", "label": "Compliance", "link_type": "DocType", "link_to": "Compliance Record", "icon": "shield", "child": 1},
	{"type": "Link", "label": "Commissions", "link_type": "DocType", "link_to": "Commission Payout", "icon": "money-coins-1", "child": 1},
	# System
	{"type": "Section Break", "label": "System", "icon": "setting", "child": 0, "collapsible": 1, "indent": 1, "keep_closed": 0},
	{"type": "Link", "label": "Settings", "link_type": "DocType", "link_to": "Insurance Settings", "icon": "setting", "child": 1},
	# Reinsurance Treaty intentionally omitted from default broker sidebar.
	# DocType + claim cession recovery remain available via Awesome Bar / search.
]

FLOW_APP = "flow"
FLOW_GIT = "https://github.com/frappe/flow_client.git"

def setup_rfq_extension():
	"""Idempotent Broker RFQ fields, client scripts, sample rules."""
	try:
		from insurance_core.rfq_extension.install_rfq_extension import setup_for_hooks
		setup_for_hooks()
	except Exception as e:
		try:
			frappe.logger("insurance_core").warning(f"RFQ extension setup skipped: {e}")
		except Exception:
			pass


def setup_engineering_vertical():
	"""Ensure Engineering LOB is on Select options (structural only).

	Source JSON already lists Engineering; this forces Property Setter / DocField
	updates on existing sites where migrate alone does not refresh Select options.

	Do NOT seed Engineering schemes here — that needs Insurance Providers, which
	only exist after demo data (or manual provider create). Scheme seeding runs
	inside demo_data.install_demo_data / add_engineering_vertical with seed_schemes=True.
	"""
	try:
		from insurance_core.add_engineering_vertical import setup as eng_setup
		# Hooks path: LOB options only. Avoid "Seeded 0 …" / provider warnings
		# before the interactive demo-data prompt.
		eng_setup(seed_schemes=False, quiet=True)
	except Exception as e:
		try:
			frappe.logger("insurance_core").warning(f"Engineering vertical setup skipped: {e}")
		except Exception:
			pass


def setup_policy_upload():
	"""Idempotent Policy Upload fields, client script, default PDF layout."""
	try:
		from insurance_core.policy_upload.install_policy_upload import setup_for_hooks
		setup_for_hooks()
	except Exception as e:
		try:
			frappe.logger("insurance_core").warning(f"Policy upload setup skipped: {e}")
		except Exception:
			pass


def ensure_pdfplumber() -> bool:
	"""Ensure pdfplumber is importable for Policy PDF Upload text extraction.

	Tries import first; if missing, runs ``pip install pdfplumber`` into the
	current environment (bench env). Non-fatal on failure — parser falls back
	to pypdf / PyPDF2.
	"""
	try:
		import pdfplumber  # noqa: F401
		return True
	except ImportError:
		pass

	import subprocess
	import sys

	try:
		subprocess.check_call(
			[sys.executable, "-m", "pip", "install", "pdfplumber>=0.11.0"],
			stdout=subprocess.DEVNULL,
			stderr=subprocess.STDOUT,
		)
		import pdfplumber  # noqa: F401
		try:
			frappe.logger("insurance_core").info("Installed pdfplumber for Policy PDF parsing")
		except Exception:
			pass
		return True
	except Exception as e:
		try:
			frappe.logger("insurance_core").warning(
				f"pdfplumber not available (Policy PDF parse will use pypdf fallback): {e}"
			)
		except Exception:
			pass
		return False


def after_install():
	ensure_flow_app()
	ensure_roles()
	ensure_admin_privileges()
	ensure_module()
	ensure_workspace()
	ensure_home_workspace()
	ensure_dashboard_artifacts()
	ensure_dashboard_workspace()
	ensure_workspace_sidebar()
	ensure_desktop_icon()
	seed_eligibility_criteria()
	setup_ai_triage()
	setup_rfq_extension()
	setup_engineering_vertical()
	ensure_pdfplumber()
	setup_policy_upload()
	# Optional interactive demo data (CLI prompt)
	prompt_demo_data()


def after_migrate():
	ensure_flow_app()
	ensure_roles()
	ensure_admin_privileges()
	ensure_module()
	ensure_workspace()
	ensure_home_workspace()
	ensure_dashboard_artifacts()
	ensure_dashboard_workspace()
	ensure_workspace_sidebar()
	ensure_desktop_icon()
	seed_eligibility_criteria()
	setup_ai_triage()
	setup_rfq_extension()
	setup_engineering_vertical()
	ensure_pdfplumber()
	setup_policy_upload()


def ensure_flow_app(fetch_if_missing: bool = False) -> dict:
	"""Ensure Frappe Flow is installed on the current site.

	Flow is listed in ``required_apps``. Preferred path:

	1. ``bench get-app flow`` (or ``bench get-app <insurance_core> --resolve-deps``)
	2. ``bench --site <site> install-app flow``
	3. ``bench --site <site> install-app insurance_core``

	This helper runs at install/migrate time:

	- If ``flow`` is already installed on the site → no-op.
	- If ``flow`` exists under ``apps/`` but is not on the site → install it on the site.
	- If ``fetch_if_missing`` and the app is absent from the bench → try
	  ``bench get-app`` then install (best-effort; needs network + bench CLI).

	Returns a small status dict for logging / desk callers.
	"""
	status = {"app": FLOW_APP, "installed": False, "action": None, "error": None}

	try:
		installed = set(frappe.get_installed_apps() or [])
	except Exception:
		installed = set()

	if FLOW_APP in installed:
		status["installed"] = True
		status["action"] = "already_installed"
		return status

	# App present on bench?
	bench_has_app = False
	try:
		from frappe.utils import get_bench_path

		bench_path = Path(get_bench_path())
		bench_has_app = (bench_path / "apps" / FLOW_APP).is_dir()
	except Exception:
		try:
			import frappe as _f

			bench_has_app = FLOW_APP in (_f.get_all_apps() or [])
		except Exception:
			bench_has_app = False

	if not bench_has_app and fetch_if_missing:
		fetch_result = _bench_get_app_flow()
		status["action"] = "get_app"
		if not fetch_result.get("ok"):
			status["error"] = fetch_result.get("error") or "bench get-app flow failed"
			_log_flow_warning(status["error"])
			return status
		bench_has_app = True

	if not bench_has_app:
		status["action"] = "missing_on_bench"
		status["error"] = (
			"Frappe Flow is not on this bench. Run: "
			"bench get-app flow && bench --site <site> install-app flow"
		)
		_log_flow_warning(status["error"])
		return status

	# Install on current site
	try:
		from frappe.installer import install_app

		install_app(FLOW_APP, verbose=False, set_as_patched=True)
		frappe.db.commit()  # nosemgrep
		status["installed"] = True
		status["action"] = "installed_on_site"
		try:
			frappe.logger("insurance_core").info("Installed app 'flow' on site")
		except Exception:
			pass
	except Exception as e:
		status["action"] = "install_failed"
		status["error"] = str(e)
		_log_flow_warning(f"Could not install flow on site: {e}")

	return status


def _bench_get_app_flow() -> dict:
	"""Best-effort ``bench get-app flow`` when the app is missing from the bench."""
	try:
		from frappe.utils import get_bench_path

		bench_path = str(get_bench_path())
	except Exception as e:
		return {"ok": False, "error": f"Cannot resolve bench path: {e}"}

	cmd = ["bench", "get-app", FLOW_GIT, "--branch", "develop"]
	# Prefer short name when bench knows it
	try:
		cmd_short = ["bench", "get-app", FLOW_APP]
		proc = subprocess.run(
			cmd_short,
			cwd=bench_path,
			capture_output=True,
			text=True,
			timeout=600,
		)
		if proc.returncode == 0:
			return {"ok": True, "via": "short_name"}
	except Exception:
		pass

	try:
		proc = subprocess.run(
			cmd,
			cwd=bench_path,
			capture_output=True,
			text=True,
			timeout=600,
		)
		if proc.returncode == 0:
			return {"ok": True, "via": "git_url"}
		err = (proc.stderr or proc.stdout or "").strip()[-500:]
		return {"ok": False, "error": err or f"exit {proc.returncode}"}
	except Exception as e:
		return {"ok": False, "error": str(e)}


def _log_flow_warning(msg: str) -> None:
	try:
		frappe.logger("insurance_core").warning(msg)
	except Exception:
		pass


def ensure_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			doc = frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1})
			doc.insert(ignore_permissions=True)


def ensure_admin_privileges():
	"""Give Administrator (and System Manager) full Insurance Manager-level access.

	- Assigns every insurance role (Insurance Manager and below) to the
	  Administrator *user* so role checks (frappe.only_for, eligibility override,
	  workspace filters, etc.) pass.
	- Ensures DocType permission rows exist for Administrator, System Manager,
	  and Insurance Manager on every DocType in module "Insurance Core"
	  (full CRUD + report/export/print/email/share/import where applicable).

	Idempotent; safe on every migrate.
	"""
	# 1) Roles on the Administrator user
	try:
		if frappe.db.exists("User", "Administrator"):
			user = frappe.get_doc("User", "Administrator")
			existing = {r.role for r in (user.roles or [])}
			changed = False
			for role in ROLES:
				if role not in existing:
					user.append("roles", {"role": role})
					changed = True
			# Also ensure System Manager is present (normally already is)
			if "System Manager" not in existing:
				user.append("roles", {"role": "System Manager"})
				changed = True
			if changed:
				user.flags.ignore_permissions = True
				user.save(ignore_permissions=True)
				frappe.db.commit()  # nosemgrep
	except Exception as e:
		try:
			frappe.logger("insurance_core").warning(f"Admin role assignment skipped: {e}")
		except Exception:
			pass

	# 2) Full DocPerm on all Insurance Core DocTypes
	try:
		doctypes = frappe.get_all(
			"DocType",
			filters={"module": "Insurance Core"},
			pluck="name",
		)
	except Exception:
		doctypes = []

	perm_roles = ("Administrator", "System Manager", "Insurance Manager")
	# Full privilege set matching Insurance Manager ceiling
	full_flags = {
		"read": 1,
		"write": 1,
		"create": 1,
		"delete": 1,
		"report": 1,
		"export": 1,
		"import": 1,
		"print": 1,
		"email": 1,
		"share": 1,
	}

	for dt in doctypes:
		if not frappe.db.exists("DocType", dt):
			continue
		for role in perm_roles:
			try:
				_ensure_doctype_permission(dt, role, full_flags)
			except Exception as e:
				try:
					frappe.logger("insurance_core").warning(
						f"Admin perm for {dt}/{role} skipped: {e}"
					)
				except Exception:
					pass

	try:
		frappe.db.commit()  # nosemgrep
		frappe.clear_cache()
	except Exception:
		pass


def _ensure_doctype_permission(doctype: str, role: str, flags: dict) -> None:
	"""Ensure a Custom DocPerm (or update existing DocPerm) grants *flags* to *role*."""
	# Prefer Custom DocPerm so we do not rewrite standard DocType JSON
	exists = frappe.db.exists(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0},
	)
	if exists:
		# Upgrade any missing flags
		cdp = frappe.get_doc("Custom DocPerm", exists)
		changed = False
		for k, v in flags.items():
			if hasattr(cdp, k) and not getattr(cdp, k):
				setattr(cdp, k, v)
				changed = True
		if changed:
			cdp.save(ignore_permissions=True)
		return

	# No Custom DocPerm — check native DocPerm on the DocType
	native = frappe.db.exists(
		"DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0},
	)
	if native:
		# Native row exists; leave it (migrate / fixtures own it). Optionally
		# ensure flags via Custom DocPerm override only when something is missing.
		row = frappe.db.get_value(
			"DocPerm",
			native,
			list(flags.keys()),
			as_dict=True,
		) or {}
		missing = any(not row.get(k) for k in flags)
		if not missing:
			return
		# Create Custom DocPerm that grants the full set (overrides native)
		pass  # fall through to insert

	# Insert Custom DocPerm
	doc = frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": 0,
			**flags,
		}
	)
	doc.insert(ignore_permissions=True)


def ensure_module():
	if not frappe.db.exists("Module Def", "Insurance Core"):
		frappe.get_doc({
			"doctype": "Module Def",
			"module_name": "Insurance Core",
			"app_name": "insurance_core",
		}).insert(ignore_permissions=True)


def _doctype_exists(name: str) -> bool:
	return bool(frappe.db.exists("DocType", name))


def _workspace_exists(name: str) -> bool:
	return bool(frappe.db.exists("Workspace", name))


def _workspace_links_and_shortcuts(max_shortcuts: int = 12):
	"""Build Workspace links / shortcuts from top-level doctypes that exist on this site."""
	links = []
	for row in WORKSPACE_LINKS:
		if row["type"] == "Link" and not _doctype_exists(row["link_to"]):
			continue
		entry = {
			"type": row["type"],
			"label": row["label"],
			"hidden": 0,
			"onboard": 0,
			"is_query_report": 0,
			"link_count": 0,
		}
		if row["type"] == "Link":
			entry["link_type"] = row["link_type"]
			entry["link_to"] = row["link_to"]
		links.append(entry)

	# Drop card breaks that have no following links before the next break
	filtered = []
	for i, row in enumerate(links):
		if row["type"] == "Card Break":
			has_child = False
			for r in links[i + 1 :]:
				if r["type"] == "Card Break":
					break
				has_child = True
				break
			if not has_child:
				continue
		filtered.append(row)
	links = filtered

	shortcuts = []
	for name, link_type in WORKSPACE_SHORTCUTS:
		if not _doctype_exists(name):
			continue
		shortcuts.append({
			"label": name,
			"link_to": name,
			"type": link_type,
			"doc_view": "List",
		})

	content_blocks = []
	if shortcuts:
		content_blocks.append({
			"id": "ic_hdr_shortcuts",
			"type": "header",
			"data": {"text": '<span class="h4"><b>Shortcuts</b></span>', "col": 12},
		})
		for i, s in enumerate(shortcuts[:max_shortcuts]):
			content_blocks.append({
				"id": f"ic_sc_{i}",
				"type": "shortcut",
				"data": {"shortcut_name": s["label"], "col": 3},
			})
	# Card layout for sectioned links
	if links:
		content_blocks.append({
			"id": "ic_hdr_links",
			"type": "header",
			"data": {"text": '<span class="h4"><b>Modules</b></span>', "col": 12},
		})
		card_idx = 0
		for row in links:
			if row["type"] == "Card Break":
				content_blocks.append({
					"id": f"ic_card_{card_idx}",
					"type": "card",
					"data": {"card_name": row["label"], "col": 4},
				})
				card_idx += 1
	return links, shortcuts, content_blocks


def _upsert_workspace(
	name: str,
	*,
	icon: str,
	title: str | None = None,
	links=None,
	shortcuts=None,
	content_blocks=None,
	charts=None,
	number_cards=None,
	sequence_id: float | None = None,
):
	"""Insert or fully refresh a public Insurance Core workspace (idempotent)."""
	if not frappe.db.exists("DocType", "Workspace"):
		return

	title = title or name
	payload = {
		"doctype": "Workspace",
		"label": name,
		"title": title,
		"module": "Insurance Core",
		"public": 1,
		"is_hidden": 0,
		"icon": icon,
		"content": json.dumps(content_blocks or []),
		"links": links or [],
		"shortcuts": shortcuts or [],
	}
	if charts is not None:
		payload["charts"] = charts
	if number_cards is not None:
		payload["number_cards"] = number_cards
	if sequence_id is not None:
		payload["sequence_id"] = sequence_id

	ws_meta_fields = {df.fieldname for df in frappe.get_meta("Workspace").fields}
	if "standard" in ws_meta_fields:
		payload["standard"] = 0
	if "type" in ws_meta_fields:
		payload["type"] = "Workspace"

	try:
		if frappe.db.exists("Workspace", name):
			ws = frappe.get_doc("Workspace", name)
			ws.title = title
			ws.module = "Insurance Core"
			ws.public = 1
			ws.is_hidden = 0
			ws.icon = icon
			ws.content = json.dumps(content_blocks or [])
			ws.set("links", [])
			for row in links or []:
				ws.append("links", row)
			ws.set("shortcuts", [])
			for row in shortcuts or []:
				ws.append("shortcuts", row)
			if charts is not None and "charts" in ws_meta_fields:
				ws.set("charts", [])
				for row in charts:
					ws.append("charts", row)
			if number_cards is not None and "number_cards" in ws_meta_fields:
				ws.set("number_cards", [])
				for row in number_cards:
					ws.append("number_cards", row)
			if sequence_id is not None and "sequence_id" in ws_meta_fields:
				ws.sequence_id = sequence_id
			ws.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc(payload)
			doc.insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep
	except Exception as e:
		try:
			frappe.logger("insurance_core").warning(f"Workspace upsert skipped ({name}): {e}")
		except Exception:
			pass


def ensure_workspace():
	"""Create or repair the module Workspace (Insurance Core).

	Kept for Desktop Icon / module discovery. Primary navigation is now
	Insurance Home + Insurance Dashboard + sectioned sidebar links.
	"""
	if not frappe.db.exists("DocType", "Workspace"):
		return

	links, shortcuts, content_blocks = _workspace_links_and_shortcuts(max_shortcuts=6)
	_upsert_workspace(
		"Insurance Core",
		icon="shield",
		links=links,
		shortcuts=shortcuts,
		content_blocks=content_blocks,
		sequence_id=3.0,
	)


def ensure_home_workspace():
	"""Public Home workspace: shortcuts + sectioned top-level DocType cards.

	Pinned at the top of the Insurance Core left sidebar. Excludes child tables.
	"""
	if not frappe.db.exists("DocType", "Workspace"):
		return

	links, shortcuts, content_blocks = _workspace_links_and_shortcuts(max_shortcuts=12)
	_upsert_workspace(
		"Insurance Home",
		title="Home",
		icon="home",
		links=links,
		shortcuts=shortcuts,
		content_blocks=content_blocks,
		sequence_id=1.0,
	)


def ensure_dashboard_artifacts():
	"""Seed Number Cards and Dashboard Charts used by the Dashboard workspace."""
	# --- Number Cards ---
	if frappe.db.exists("DocType", "Number Card"):
		nc_fields = {df.fieldname for df in frappe.get_meta("Number Card").fields}
		for spec in DASHBOARD_NUMBER_CARDS:
			dt = spec["document_type"]
			if not _doctype_exists(dt):
				continue
			try:
				if frappe.db.exists("Number Card", spec["name"]):
					continue
				payload = {
					"doctype": "Number Card",
					"name": spec["name"],
					"label": spec["label"],
					"document_type": dt,
					"function": spec.get("function", "Count"),
					"is_public": 1,
					"is_standard": 0,
					"module": "Insurance Core",
				}
				if "filters_json" in nc_fields:
					payload["filters_json"] = spec.get("filters_json") or "[]"
				if "color" in nc_fields and spec.get("color"):
					payload["color"] = spec["color"]
				if "type" in nc_fields:
					payload["type"] = "Document Type"
				# Strip unknown fields
				payload = {k: v for k, v in payload.items() if k in nc_fields or k in ("doctype", "name")}
				doc = frappe.get_doc(payload)
				doc.insert(ignore_permissions=True)
				frappe.db.commit()  # nosemgrep
			except Exception as e:
				try:
					frappe.logger("insurance_core").warning(
						f"Number Card seed skipped ({spec['name']}): {e}"
					)
				except Exception:
					pass

	# --- Dashboard Charts ---
	if frappe.db.exists("DocType", "Dashboard Chart"):
		ch_fields = {df.fieldname for df in frappe.get_meta("Dashboard Chart").fields}
		for spec in DASHBOARD_CHARTS:
			dt = spec["document_type"]
			if not _doctype_exists(dt):
				continue
			try:
				if frappe.db.exists("Dashboard Chart", spec["name"]):
					continue
				payload = {
					"doctype": "Dashboard Chart",
					"name": spec["name"],
					"chart_name": spec.get("chart_name") or spec["name"],
					"chart_type": spec.get("chart_type", "Group By"),
					"document_type": dt,
					"group_by_type": spec.get("group_by_type", "Count"),
					"group_by_based_on": spec.get("group_by_based_on", "status"),
					"number_of_groups": spec.get("number_of_groups", 8),
					"type": spec.get("type", "Bar"),
					"is_public": 1,
					"is_standard": 0,
					"module": "Insurance Core",
					"timeseries": 0,
				}
				payload = {k: v for k, v in payload.items() if k in ch_fields or k in ("doctype", "name")}
				doc = frappe.get_doc(payload)
				doc.insert(ignore_permissions=True)
				frappe.db.commit()  # nosemgrep
			except Exception as e:
				try:
					frappe.logger("insurance_core").warning(
						f"Dashboard Chart seed skipped ({spec['name']}): {e}"
					)
				except Exception:
					pass


def ensure_dashboard_workspace():
	"""Public Dashboard workspace: number cards + charts for high-level stats.

	Pinned second in the Insurance Core left sidebar.
	"""
	if not frappe.db.exists("DocType", "Workspace"):
		return

	number_cards = []
	for spec in DASHBOARD_NUMBER_CARDS:
		if frappe.db.exists("Number Card", spec["name"]):
			number_cards.append({
				"label": spec["label"],
				"number_card_name": spec["name"],
			})

	charts = []
	for spec in DASHBOARD_CHARTS:
		if frappe.db.exists("Dashboard Chart", spec["name"]):
			charts.append({
				"label": spec.get("chart_name") or spec["name"],
				"chart_name": spec["name"],
			})

	content_blocks = []
	if number_cards:
		content_blocks.append({
			"id": "ic_dash_hdr_kpis",
			"type": "header",
			"data": {"text": '<span class="h4"><b>Key Metrics</b></span>', "col": 12},
		})
		for i, nc in enumerate(number_cards):
			content_blocks.append({
				"id": f"ic_dash_nc_{i}",
				"type": "number_card",
				"data": {"number_card_name": nc["number_card_name"], "col": 4},
			})
	if charts:
		content_blocks.append({
			"id": "ic_dash_hdr_charts",
			"type": "header",
			"data": {"text": '<span class="h4"><b>Analytics</b></span>', "col": 12},
		})
		for i, ch in enumerate(charts):
			content_blocks.append({
				"id": f"ic_dash_ch_{i}",
				"type": "chart",
				"data": {"chart_name": ch["chart_name"], "col": 6 if len(charts) > 1 else 12},
			})

	# Fallback header when no cards/charts could be seeded (missing DocTypes)
	if not content_blocks:
		content_blocks.append({
			"id": "ic_dash_empty",
			"type": "header",
			"data": {
				"text": (
					'<span class="h4"><b>Dashboard</b></span>'
					'<p class="text-muted">Number cards and charts will appear after '
					"Insurance DocTypes are installed and data is available.</p>"
				),
				"col": 12,
			},
		})

	_upsert_workspace(
		"Insurance Dashboard",
		title="Dashboard",
		icon="dashboard",
		content_blocks=content_blocks,
		charts=charts,
		number_cards=number_cards,
		sequence_id=2.0,
	)


def ensure_workspace_sidebar():
	"""Create or repair Workspace Sidebar so desk left nav matches portal sidebar.

	v15/v16 left sidebar is driven by DocType **Workspace Sidebar** (items table).
	Desktop Icon links to this by title ("Insurance Core").

	Order: Home + Dashboard workspaces first, then module groups
	(Catalog → Policies → Claims → Operations → System) matching portal navGroups.

	Vue/Vite SPA is optional — desk works fully without the frontend build.
	"""
	if not frappe.db.exists("DocType", "Workspace Sidebar"):
		return

	title = "Insurance Core"
	meta = frappe.get_meta("Workspace Sidebar")
	item_meta = None
	if frappe.db.exists("DocType", "Workspace Sidebar Item"):
		item_meta = frappe.get_meta("Workspace Sidebar Item")
	item_fields = {df.fieldname for df in (item_meta.fields if item_meta else [])}

	def _item_row(spec: dict) -> dict | None:
		row = {"type": spec["type"], "label": spec.get("label") or ""}
		if spec["type"] == "Link":
			link_to = spec.get("link_to")
			link_type = spec.get("link_type", "DocType")
			# Validate target exists for the given link_type
			if link_to:
				if link_type == "DocType" and not _doctype_exists(link_to):
					return None
				if link_type == "Workspace" and not _workspace_exists(link_to):
					return None
			row["link_type"] = link_type
			row["link_to"] = link_to
		if "icon" in item_fields and spec.get("icon"):
			row["icon"] = spec["icon"]
		# Nesting / section display (v15/v16 Workspace Sidebar Item)
		# child=1 under a Section Break is required for Desk to group items.
		for flag in ("child", "collapsible", "indent", "keep_closed", "show_arrow"):
			if flag in item_fields and flag in spec:
				row[flag] = 1 if spec[flag] else 0
		# Only pass fields that exist on this Frappe version
		allowed = item_fields | {"type", "label", "link_type", "link_to"}
		return {k: v for k, v in row.items() if k in allowed}

	items = []
	for spec in WORKSPACE_SIDEBAR_ITEMS:
		row = _item_row(spec)
		if row:
			items.append(row)

	# Drop section breaks that would be empty (no following child Links)
	filtered = []
	for i, row in enumerate(items):
		if row.get("type") == "Section Break":
			has_child = False
			for r in items[i + 1 :]:
				if r.get("type") == "Section Break":
					break
				# Prefer explicit child=1; fall back to any non-section row
				if r.get("child") or r.get("type") == "Link":
					has_child = True
					break
			if not has_child:
				continue
		filtered.append(row)
	items = filtered

	try:
		if frappe.db.exists("Workspace Sidebar", title):
			doc = frappe.get_doc("Workspace Sidebar", title)
			# Rebuild items so migrate keeps desk nav in sync with portal
			doc.set("items", [])
			for row in items:
				doc.append("items", row)
			if hasattr(doc, "desktop_icon") and not doc.desktop_icon:
				if frappe.db.exists("Desktop Icon", title):
					doc.desktop_icon = title
			doc.save(ignore_permissions=True)
			frappe.db.commit()  # nosemgrep
			return

		payload = {
			"doctype": "Workspace Sidebar",
			"title": title,
			"items": items,
		}
		# Some versions use name = title; others link desktop_icon
		if "desktop_icon" in {df.fieldname for df in meta.fields}:
			if frappe.db.exists("Desktop Icon", title):
				payload["desktop_icon"] = title
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep
	except Exception as e:
		try:
			frappe.logger("insurance_core").warning(f"Workspace Sidebar ensure skipped: {e}")
		except Exception:
			pass


def ensure_desktop_icon():
	"""Seed Desktop Icon(s) and inject into per-user Desktop Layout.

	v15/v16: Desktop Icon rows alone are not enough — the home desk is driven by
	per-user **Desktop Layout** JSON. If that layout was saved before Insurance Core
	existed, the icon stays invisible even when Desktop Icon is correct.

	Steps:
	1. create_desktop_icons() from public workspaces
	2. Ensure an explicit Desktop Icon row (Link → Workspace Sidebar)
	3. Patch every Desktop Layout so "Insurance Core" is present (top-level)
	"""
	try:
		from frappe.desk.doctype.desktop_icon.desktop_icon import create_desktop_icons

		create_desktop_icons()
		frappe.db.commit()  # nosemgrep
	except ImportError:
		pass
	except Exception as e:
		try:
			frappe.logger("insurance_core").warning(f"Desktop icon seed skipped: {e}")
		except Exception:
			pass

	if not frappe.db.exists("DocType", "Desktop Icon"):
		return

	label = "Insurance Core"
	meta_fields = {df.fieldname for df in frappe.get_meta("Desktop Icon").fields}

	logo_url = "/assets/insurance_core/images/insurance.svg"

	def _insert_icon(values: dict) -> bool:
		"""Insert or repair Desktop Icon with only fields that exist on this site.

		Always force-set icon + logo_url on existing rows. Without logo_url the
		v16 desk falls back to a letter avatar (first letter of the label).
		"""
		payload = {"doctype": "Desktop Icon"}
		for k, v in values.items():
			if k in meta_fields or k in ("doctype",):
				payload[k] = v
		payload["label"] = values.get("label", label)
		try:
			if frappe.db.exists("Desktop Icon", payload["label"]):
				doc = frappe.get_doc("Desktop Icon", payload["label"])
				changed = False
				if getattr(doc, "hidden", 0):
					doc.hidden = 0
					changed = True
				if getattr(doc, "link_to", None) and doc.link_to != label:
					doc.link_to = label
					changed = True
				# Force visual fields so letter-avatar is replaced by logo/icon
				for field, expected in (
					("icon", values.get("icon")),
					("logo_url", values.get("logo_url")),
					("bg_color", values.get("bg_color")),
					("icon_type", values.get("icon_type")),
					("link_type", values.get("link_type")),
					("app", values.get("app")),
				):
					if expected is None or field not in meta_fields:
						continue
					if getattr(doc, field, None) != expected:
						setattr(doc, field, expected)
						changed = True
				if changed:
					doc.save(ignore_permissions=True)
					frappe.db.commit()  # nosemgrep
				return True
			frappe.get_doc(payload).insert(ignore_permissions=True)
			frappe.db.commit()  # nosemgrep
			return True
		except Exception as e:
			try:
				frappe.logger("insurance_core").warning(
					f"Desktop Icon insert skipped ({payload.get('icon_type')}): {e}"
				)
			except Exception:
				pass
			return False

	# Primary tile: Workspace Sidebar + logo (logo_url avoids letter-avatar fallback)
	_insert_icon({
		"label": label,
		"icon_type": "Link",
		"link_type": "Workspace Sidebar",
		"link_to": label,
		"icon": "shield",
		"logo_url": logo_url,
		"bg_color": "blue",
		"app": "insurance_core",
		"standard": 1,
		"hidden": 0,
		"idx": 0,
		"parent_icon": None,
	})

	# 2) Per-user Desktop Layout (v16): inject or repair logo on existing entry
	_ensure_desktop_layout_includes_icon(label, logo_url=logo_url)

	try:
		frappe.clear_cache()
	except Exception:
		pass


def _ensure_desktop_layout_includes_icon(
	label: str = "Insurance Core",
	logo_url: str = "/assets/insurance_core/images/insurance.svg",
):
	"""Append or repair Insurance Core in every Desktop Layout.

	Desktop Layout is named by user (autoname field:user). Its ``layout`` field is
	a JSON list of icon dicts. Missing logo_url makes the desk show a letter avatar
	(e.g. gray \"I\") instead of the app logo.
	"""
	if not frappe.db.exists("DocType", "Desktop Layout"):
		return

	icon_entry = {
		"label": label,
		"name": label,
		"icon_type": "Link",
		"link_type": "Workspace Sidebar",
		"link_to": label,
		"icon": "shield",
		"app": "insurance_core",
		"standard": 1,
		"hidden": 0,
		"idx": 20,
		"parent_icon": None,
		"bg_color": "blue",
		"logo_url": logo_url,
		"icon_image": None,
		"restrict_removal": 0,
		"child_icons": [],
	}

	try:
		layouts = frappe.get_all("Desktop Layout", fields=["name", "user", "layout"])
	except Exception:
		return

	for row in layouts:
		raw = row.get("layout") or "[]"
		try:
			layout = json.loads(raw) if isinstance(raw, str) else (raw or [])
		except Exception:
			continue
		if not isinstance(layout, list):
			continue

		changed = False
		found = False
		for item in layout:
			if not isinstance(item, dict):
				continue
			if item.get("label") != label and item.get("name") != label:
				continue
			found = True
			# Repair letter-avatar: ensure logo_url / icon / bg_color
			if item.get("logo_url") != logo_url:
				item["logo_url"] = logo_url
				changed = True
			if item.get("icon") != "shield":
				item["icon"] = "shield"
				changed = True
			if not item.get("bg_color"):
				item["bg_color"] = "blue"
				changed = True
			if item.get("icon_type") != "Link":
				item["icon_type"] = "Link"
				changed = True
			if item.get("link_type") != "Workspace Sidebar":
				item["link_type"] = "Workspace Sidebar"
				changed = True
			if item.get("link_to") != label:
				item["link_to"] = label
				changed = True
			break

		if not found:
			layout.append(dict(icon_entry))
			changed = True

		if not changed:
			continue

		try:
			doc = frappe.get_doc("Desktop Layout", row["name"])
			doc.layout = json.dumps(layout)
			doc.save(ignore_permissions=True)
			frappe.db.commit()  # nosemgrep
		except Exception as e:
			try:
				frappe.logger("insurance_core").warning(
					f"Desktop Layout patch skipped for {row.get('user')}: {e}"
				)
			except Exception:
				pass


def seed_eligibility_criteria():
	"""Seed system eligibility rules. Idempotent: skips existing criteria_code / criteria_name."""
	if not frappe.db.exists("DocType", "Client Eligibility Criteria"):
		return
	# Keep seed data outside fixtures/ so Frappe sync_fixtures does not force-import it
	path = frappe.get_app_path("insurance_core", "data", "client_eligibility_criteria.json")
	if not os.path.exists(path):
		# Backward-compatible fallback if site still has old layout
		path = frappe.get_app_path("insurance_core", "fixtures", "client_eligibility_criteria.json")
	if not os.path.exists(path):
		return
	with open(path) as handle:
		rows = json.load(handle)
	for row in rows:
		code = row.get("criteria_code")
		if not code:
			continue
		# Skip if already present under any name (naming-series or criteria_code)
		if frappe.db.exists("Client Eligibility Criteria", {"criteria_code": code}):
			continue
		criteria_name = row.get("criteria_name")
		if criteria_name and frappe.db.exists(
			"Client Eligibility Criteria", {"criteria_name": criteria_name}
		):
			continue
		# Prefer stable name = criteria_code for system rows
		row = dict(row)
		row.setdefault("name", code)
		row["doctype"] = "Client Eligibility Criteria"
		doc = frappe.get_doc(row)
		doc.insert(ignore_permissions=True)


def setup_ai_triage():
	"""Create Flow tools/agent/trigger and AI custom fields when Flow is available."""
	try:
		from insurance_core.ai_triage import ensure_flow_triage_setup

		ensure_flow_triage_setup()
	except Exception as e:
		# Non-fatal during migrate when Flow is not yet installed
		try:
			frappe.logger("insurance_core").warning(f"AI triage setup skipped: {e}")
		except Exception:
			pass


def prompt_demo_data():
	"""Ask (CLI) whether to install bulky Indian-context demo data."""
	try:
		from insurance_core.demo_data import maybe_prompt_and_install

		maybe_prompt_and_install()
	except Exception as e:
		try:
			frappe.logger("insurance_core").warning(f"Demo data prompt skipped: {e}")
		except Exception:
			pass
