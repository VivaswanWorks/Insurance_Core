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

# DocTypes to surface on the Insurance Core workspace (must exist to be linked).
WORKSPACE_SHORTCUTS = [
	("Insurance Policy", "DocType"),
	("Insurance Claim", "DocType"),
	("Insurance Client", "DocType"),
	("Insurance Scheme", "DocType"),
	("Insurance Agent", "DocType"),
	("Insurance Settings", "DocType"),
]

WORKSPACE_LINKS = [
	# Catalog
	{"type": "Card Break", "label": "Catalog"},
	{"type": "Link", "label": "Insurance Provider", "link_type": "DocType", "link_to": "Insurance Provider"},
	{"type": "Link", "label": "Insurance Scheme", "link_type": "DocType", "link_to": "Insurance Scheme"},
	{"type": "Link", "label": "Network Hospital", "link_type": "DocType", "link_to": "Network Hospital"},
	# Policies
	{"type": "Card Break", "label": "Policies"},
	{"type": "Link", "label": "Insurance Policy", "link_type": "DocType", "link_to": "Insurance Policy"},
	{"type": "Link", "label": "Insurance Client", "link_type": "DocType", "link_to": "Insurance Client"},
	{"type": "Link", "label": "Insurance Agent", "link_type": "DocType", "link_to": "Insurance Agent"},
	{"type": "Link", "label": "Insurance Quotation", "link_type": "DocType", "link_to": "Insurance Quotation"},
	{"type": "Link", "label": "Insurance Opportunity", "link_type": "DocType", "link_to": "Insurance Opportunity"},
	{"type": "Link", "label": "Policy Endorsement", "link_type": "DocType", "link_to": "Policy Endorsement"},
	# Claims
	{"type": "Card Break", "label": "Claims"},
	{"type": "Link", "label": "Insurance Claim", "link_type": "DocType", "link_to": "Insurance Claim"},
	{"type": "Link", "label": "Cashless Authorization", "link_type": "DocType", "link_to": "Cashless Authorization"},
	{"type": "Link", "label": "Claim Recovery", "link_type": "DocType", "link_to": "Claim Recovery"},
	# Operations
	{"type": "Card Break", "label": "Operations"},
	{"type": "Link", "label": "Commission Payout", "link_type": "DocType", "link_to": "Commission Payout"},
	{"type": "Link", "label": "Commission Rule", "link_type": "DocType", "link_to": "Commission Rule"},
	{"type": "Link", "label": "Insurance Grievance", "link_type": "DocType", "link_to": "Insurance Grievance"},
	{"type": "Link", "label": "Reinsurance Treaty", "link_type": "DocType", "link_to": "Reinsurance Treaty"},
	{"type": "Link", "label": "Insurance Settings", "link_type": "DocType", "link_to": "Insurance Settings"},
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
	"""Ensure Engineering LOB is on Select options + optional sample schemes.

	Source JSON already lists Engineering; this forces Property Setter / DocField
	updates on existing sites where migrate alone does not refresh Select options.
	"""
	try:
		from insurance_core.add_engineering_vertical import setup as eng_setup
		# seed_schemes=True is idempotent; only inserts if demo providers exist
		eng_setup(seed_schemes=True)
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


def _workspace_links_and_shortcuts():
	"""Build Workspace links / shortcuts from doctypes that exist on this site."""
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
		for i, s in enumerate(shortcuts[:6]):
			content_blocks.append({
				"id": f"ic_sc_{i}",
				"type": "shortcut",
				"data": {"shortcut_name": s["label"], "col": 3},
			})
	return links, shortcuts, content_blocks


def ensure_workspace():
	"""Create or repair a public Workspace so Insurance Core appears on the Desk.

	Modern Frappe (v14+) shows modules via Workspace, not Module Def alone.
	- Inserts when missing
	- If present but hidden / not public, forces public + visible (does not wipe custom links)
	"""
	if not frappe.db.exists("DocType", "Workspace"):
		return

	links, shortcuts, content_blocks = _workspace_links_and_shortcuts()
	name = "Insurance Core"

	if frappe.db.exists("Workspace", name):
		# Repair visibility only — keep user customisations of links/content
		try:
			ws = frappe.get_doc("Workspace", name)
			changed = False
			if hasattr(ws, "is_hidden") and ws.is_hidden:
				ws.is_hidden = 0
				changed = True
			if hasattr(ws, "public") and not ws.public:
				ws.public = 1
				changed = True
			if hasattr(ws, "module") and not ws.module:
				ws.module = "Insurance Core"
				changed = True
			if hasattr(ws, "icon") and not ws.icon:
				ws.icon = "shield"
				changed = True
			if changed:
				ws.save(ignore_permissions=True)
				frappe.db.commit()  # nosemgrep
		except Exception as e:
			try:
				frappe.logger("insurance_core").warning(f"Workspace repair skipped: {e}")
			except Exception:
				pass
		return

	doc = frappe.get_doc({
		"doctype": "Workspace",
		"label": name,
		"title": name,
		"module": "Insurance Core",
		"public": 1,
		"is_hidden": 0,
		"icon": "shield",
		"content": json.dumps(content_blocks),
		"links": links,
		"shortcuts": shortcuts,
	})
	if "standard" in [df.fieldname for df in frappe.get_meta("Workspace").fields]:
		doc.standard = 0
	try:
		doc.insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep
	except Exception as e:
		try:
			frappe.logger("insurance_core").warning(f"Workspace insert skipped: {e}")
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

	def _insert_icon(values: dict) -> bool:
		"""Insert or unhide Desktop Icon with only fields that exist on this site."""
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
				# Keep link target correct if someone renamed workspace
				if getattr(doc, "link_to", None) and doc.link_to != label:
					doc.link_to = label
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

	# 1) Workspace tile (primary for Desk home / sidebar)
	_insert_icon({
		"label": label,
		"icon_type": "Link",
		"link_type": "Workspace Sidebar",
		"link_to": label,
		"icon": "shield",
		"standard": 1,
		"hidden": 0,
		"idx": 0,
		"parent_icon": None,
	})

	# 2) App tile only if no row exists yet (logo for Apps page)
	if not frappe.db.exists("Desktop Icon", label):
		_insert_icon({
			"label": label,
			"icon_type": "App",
			"link_type": "External",
			"app": "insurance_core",
			"link": "/app/insurance-core",
			"logo_url": "/assets/insurance_core/images/insurance.svg",
			"standard": 1,
			"hidden": 0,
			"idx": 0,
		})

	# 3) Per-user Desktop Layout (v16): stale JSON hides new icons
	_ensure_desktop_layout_includes_icon(label)

	try:
		frappe.clear_cache()
	except Exception:
		pass


def _ensure_desktop_layout_includes_icon(label: str = "Insurance Core"):
	"""Append Insurance Core to every Desktop Layout that does not already list it.

	Desktop Layout is named by user (autoname field:user). Its ``layout`` field is
	a JSON list of icon dicts. If the list was saved before our icon existed, the
	desk never shows it even when Desktop Icon is correct.
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
		"bg_color": None,
		"logo_url": None,
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

		# Already present (by label or name)?
		if any(
			(isinstance(item, dict) and (item.get("label") == label or item.get("name") == label))
			for item in layout
		):
			continue

		layout.append(icon_entry)
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
