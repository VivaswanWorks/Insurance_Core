"""Customer self-service portal API.

Resolves the logged-in user to an Insurance Client via email and exposes
read/write endpoints scoped to that client only.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime, nowdate


def _current_client():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please log in to access the portal."), frappe.PermissionError)
	email = frappe.db.get_value("User", user, "email") or user
	client = frappe.db.get_value("Insurance Client", {"email": email}, "name")
	if not client:
		# System Manager can pass client for testing via form_dict
		if "System Manager" in frappe.get_roles() and frappe.form_dict.get("client"):
			return frappe.form_dict.get("client")
		frappe.throw(_("No insurance client profile is linked to your account."), frappe.PermissionError)
	return client


def _assert_owns_policy(policy_name, client):
	owner = frappe.db.get_value("Insurance Policy", policy_name, "client")
	if owner != client:
		frappe.throw(_("You do not have access to this policy."), frappe.PermissionError)


def _assert_owns_claim(claim_name, client):
	owner = frappe.db.get_value("Insurance Claim", claim_name, "client")
	if owner != client:
		frappe.throw(_("You do not have access to this claim."), frappe.PermissionError)


@frappe.whitelist(methods=["GET", "POST"])
def portal_me():
	"""Current user + linked insurance client for the app shell."""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please log in to access the portal."), frappe.PermissionError)

	user_doc = frappe.db.get_value(
		"User",
		user,
		["name", "full_name", "email", "user_image", "first_name", "last_name"],
		as_dict=True,
	) or {}

	email = user_doc.get("email") or user
	client_name = frappe.db.get_value("Insurance Client", {"email": email}, "name")
	client = None
	if client_name:
		client = frappe.get_cached_value(
			"Insurance Client",
			client_name,
			["name", "full_name", "email", "phone", "lifecycle_stage"],
			as_dict=True,
		)
	elif "System Manager" in frappe.get_roles() and frappe.form_dict.get("client"):
		client = frappe.get_cached_value(
			"Insurance Client",
			frappe.form_dict.get("client"),
			["name", "full_name", "email", "phone", "lifecycle_stage"],
			as_dict=True,
		)

	return {
		"user": {
			"name": user_doc.get("name") or user,
			"full_name": user_doc.get("full_name") or user,
			"email": email,
			"user_image": user_doc.get("user_image"),
		},
		"client": client,
	}


@frappe.whitelist(methods=["GET", "POST"])
def portal_search(q=None, limit=10):
	"""Search the current client's policies and claims."""
	client = _current_client()
	q = (q or "").strip()
	if not q or len(q) < 2:
		return {"policies": [], "claims": []}

	limit = min(cint(limit) or 10, 25)
	like = f"%{q}%"

	policies = frappe.get_all(
		"Insurance Policy",
		filters={"client": client},
		or_filters=[
			["policy_number", "like", like],
			["name", "like", like],
			["scheme", "like", like],
			["provider", "like", like],
		],
		fields=["name", "policy_number", "status", "scheme", "end_date"],
		order_by="modified desc",
		limit_page_length=limit,
	)
	claims = frappe.get_all(
		"Insurance Claim",
		filters={"client": client},
		or_filters=[
			["claim_number", "like", like],
			["name", "like", like],
			["claim_type", "like", like],
			["policy", "like", like],
		],
		fields=["name", "claim_number", "status", "claim_type", "incident_date", "claimed_amount"],
		order_by="modified desc",
		limit_page_length=limit,
	)
	return {"policies": policies, "claims": claims}


@frappe.whitelist(methods=["GET", "POST"])
def portal_dashboard():
	client = _current_client()
	policies = frappe.get_all(
		"Insurance Policy",
		filters={"client": client},
		fields=["name", "policy_number", "status", "sum_assured", "total_premium", "end_date", "scheme"],
		order_by="modified desc",
	)
	claims = frappe.get_all(
		"Insurance Claim",
		filters={"client": client},
		fields=["name", "claim_number", "status", "claimed_amount", "incident_date", "policy"],
		order_by="modified desc",
		limit=10,
	)
	active = [p for p in policies if p.status in ("Active", "Grace Period")]
	return {
		"client": frappe.get_cached_value(
			"Insurance Client", client, ["name", "full_name", "email", "phone", "lifecycle_stage"], as_dict=True
		),
		"stats": {
			"active_policies": len(active),
			"total_policies": len(policies),
			"open_claims": len([c for c in claims if c.status not in ("Settled", "Closed", "Rejected")]),
		},
		"policies": policies[:5],
		"claims": claims,
	}


@frappe.whitelist(methods=["GET", "POST"])
def portal_list_policies():
	client = _current_client()
	return frappe.get_all(
		"Insurance Policy",
		filters={"client": client},
		fields=[
			"name",
			"policy_number",
			"status",
			"scheme",
			"provider",
			"sum_assured",
			"premium_amount",
			"total_premium",
			"start_date",
			"end_date",
			"payment_status",
			"policy_document",
		],
		order_by="end_date desc",
	)


@frappe.whitelist(methods=["GET", "POST"])
def portal_get_policy(policy):
	client = _current_client()
	_assert_owns_policy(policy, client)
	doc = frappe.get_doc("Insurance Policy", policy)
	return {
		"policy": doc.as_dict(),
		"members": [m.as_dict() for m in doc.get("policy_members") or []],
		"coverages": [c.as_dict() for c in doc.get("policy_coverages") or []],
		"documents": [d.as_dict() for d in doc.get("other_documents") or []],
	}


@frappe.whitelist(methods=["GET", "POST"])
def portal_list_claims():
	client = _current_client()
	return frappe.get_all(
		"Insurance Claim",
		filters={"client": client},
		fields=[
			"name",
			"claim_number",
			"policy",
			"claim_type",
			"status",
			"claimed_amount",
			"approved_amount",
			"incident_date",
			"submission_date",
		],
		order_by="modified desc",
	)


@frappe.whitelist(methods=["GET", "POST"])
def portal_get_claim(claim):
	client = _current_client()
	_assert_owns_claim(claim, client)
	doc = frappe.get_doc("Insurance Claim", claim)
	policy_number = frappe.db.get_value("Insurance Policy", doc.policy, "policy_number") if doc.policy else None
	return {
		"claim": doc.as_dict(),
		"policy_number": policy_number,
		"documents": [d.as_dict() for d in doc.get("claim_documents") or []],
	}


@frappe.whitelist()
def portal_upload_claim_document(claim, document_type, file_url=None):
	"""Append a Claim Document row. Pass file_url from /api/method/upload_file."""
	client = _current_client()
	_assert_owns_claim(claim, client)

	status = frappe.db.get_value("Insurance Claim", claim, "status")
	if status in ("Settled", "Closed", "Rejected"):
		frappe.throw(_("Documents cannot be uploaded on a {0} claim.").format(status))

	document_type = (document_type or "").strip()
	allowed = {
		"Discharge Summary",
		"Bills",
		"Reports",
		"ID Proof",
		"FIR",
		"Estimate",
		"Other",
	}
	if document_type not in allowed:
		frappe.throw(_("Invalid document type."))

	if not file_url:
		frappe.throw(_("Please upload a file."))

	doc = frappe.get_doc("Insurance Claim", claim)
	doc.append(
		"claim_documents",
		{
			"document_type": document_type,
			"attachment": file_url,
			"uploaded_by": frappe.session.user,
			"uploaded_on": now_datetime(),
		},
	)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"name": doc.name,
		"documents": [d.as_dict() for d in doc.get("claim_documents") or []],
	}


@frappe.whitelist()
def portal_intimate_claim(policy, claim_type, incident_date, claimed_amount, description=None, claimant=None):
	client = _current_client()
	_assert_owns_policy(policy, client)
	policy_doc = frappe.get_doc("Insurance Policy", policy)
	if policy_doc.status not in ("Active", "Grace Period", "Claimed"):
		frappe.throw(_("Claims can only be intimated on active policies."), title=_("Invalid Policy"))

	doc = frappe.get_doc(
		{
			"doctype": "Insurance Claim",
			"claim_number": f"P-{frappe.generate_hash(length=8)}",
			"policy": policy,
			"client": client,
			"provider": policy_doc.provider,
			"scheme": policy_doc.scheme,
			"claim_type": claim_type or "Reimbursement",
			"incident_date": incident_date or nowdate(),
			"submission_date": nowdate(),
			"reported_date": nowdate(),
			"claimed_amount": flt(claimed_amount),
			"status": "Submitted",
			"intimation_mode": "Portal",
			"description": description,
			"claimant": claimant,
			"agent": policy_doc.agent,
		}
	)
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "claim_number": doc.claim_number}


@frappe.whitelist()
def portal_request_endorsement(policy, endorsement_type, description, new_value=None, effective_date=None):
	client = _current_client()
	_assert_owns_policy(policy, client)
	doc = frappe.get_doc(
		{
			"doctype": "Policy Endorsement",
			"policy": policy,
			"endorsement_type": endorsement_type,
			"description": description or endorsement_type,
			"new_value": new_value,
			"effective_date": effective_date or nowdate(),
			"status": "Submitted",
		}
	)
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "endorsement_number": doc.endorsement_number, "premium_impact": doc.premium_impact}


@frappe.whitelist(methods=["GET", "POST"])
def portal_policy_print(policy):
	client = _current_client()
	_assert_owns_policy(policy, client)
	from insurance_core.print_formats import get_print_html

	return get_print_html("Insurance Policy", policy)


@frappe.whitelist(methods=["GET", "POST"])
def portal_claim_print(claim, settlement=0):
	client = _current_client()
	_assert_owns_claim(claim, client)
	from insurance_core.print_formats import get_print_html

	key = "claim_settlement" if cint(settlement) else "Insurance Claim"
	return get_print_html("Insurance Claim", claim, template_key=key)


# ---------------------------------------------------------------------------
# Portal chatbot (Frappe Flow agent + optional Knowledge Base)
# ---------------------------------------------------------------------------

PORTAL_CHAT_AGENT_TITLE = "Insurance Portal Assistant"
PORTAL_CHAT_AGENT_INSTRUCTIONS = """You are a helpful insurance assistant for clients of this brokerage.
Answer clearly and accurately about policies, coverages, claims process, documents needed, cashless vs reimbursement, and endorsements.
Use the knowledge base when available. Do not invent policy numbers, claim statuses, or coverage limits.
If the user asks about their specific policy or claim status and you cannot look it up, tell them to open Policies or Claims in the portal, or contact their agent.
Be concise. Prefer bullet lists for document checklists. If unsure, say so and suggest next steps.
Do not discuss internal commissions, reinsurance, or admin-only settings.
"""


def _resolve_portal_agent_name():
	"""Return Flow Agent name for portal chat, or None if Flow is not installed / not configured."""
	if not frappe.db.exists("DocType", "Flow Agent"):
		return None

	# Prefer an agent explicitly titled for the portal
	name = frappe.db.get_value("Flow Agent", {"title": PORTAL_CHAT_AGENT_TITLE}, "name")
	if name:
		return name

	# Fallback: any enabled agent (first by modified)
	name = frappe.db.get_value(
		"Flow Agent",
		{"enabled": 1} if frappe.db.has_column("Flow Agent", "enabled") else {},
		"name",
		order_by="modified desc",
	)
	return name


def _ensure_portal_agent():
	"""Create a minimal Flow Agent for portal chat if none exists. Returns agent name or None."""
	if not frappe.db.exists("DocType", "Flow Agent"):
		return None

	existing = _resolve_portal_agent_name()
	if existing:
		return existing

	# Need at least one Flow Model
	model = frappe.db.get_value("Flow Model", {"enabled": 1}, "name") if frappe.db.exists("DocType", "Flow Model") else None
	if not model:
		model = frappe.db.get_value("Flow Model", {}, "name") if frappe.db.exists("DocType", "Flow Model") else None
	if not model:
		return None

	doc = frappe.get_doc(
		{
			"doctype": "Flow Agent",
			"title": PORTAL_CHAT_AGENT_TITLE,
			"instructions": PORTAL_CHAT_AGENT_INSTRUCTIONS,
			"model": model,
		}
	)
	# Optional fields vary by Flow version
	if frappe.get_meta("Flow Agent").has_field("enabled"):
		doc.enabled = 1
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _run_flow_chat(message: str, session_id: str | None = None) -> dict:
	"""Run one turn against a Flow Agent. Returns {reply, session_id, agent}."""
	agent_name = _ensure_portal_agent()
	if not agent_name:
		return {
			"reply": (
				"The assistant is not configured yet. Please ask a System Manager to install "
				"the Flow app, add a Flow Provider + Model, and create a Flow Agent "
				f"titled “{PORTAL_CHAT_AGENT_TITLE}” (with a Knowledge Base if desired)."
			),
			"session_id": session_id,
			"agent": None,
			"configured": False,
		}

	try:
		from flow import Agent
	except Exception:
		# Older / alternate import path
		try:
			from flow.agent import Agent
		except Exception as e:
			frappe.log_error(title="portal_chat Flow import", message=str(e))
			return {
				"reply": "The AI assistant is temporarily unavailable (Flow library not loaded).",
				"session_id": session_id,
				"agent": agent_name,
				"configured": False,
			}

	try:
		agent = Agent(name=agent_name) if hasattr(Agent, "__init__") else None
		# Prefer document-based session when Flow supports it
		if session_id and frappe.db.exists("DocType", "Flow Session") and frappe.db.exists("Flow Session", session_id):
			# Resume via Flow Session API if available
			try:
				from flow import session as flow_session_mod

				sess = flow_session_mod.get(session_id) if hasattr(flow_session_mod, "get") else None
				if sess and hasattr(sess, "chat"):
					result = sess.chat(message)
					reply = getattr(result, "output", None) or getattr(result, "reply", None) or str(result)
					return {
						"reply": reply,
						"session_id": session_id,
						"agent": agent_name,
						"configured": True,
					}
			except Exception:
				pass

		# Code-first Agent API
		agent_doc = frappe.get_doc("Flow Agent", agent_name)
		model_id = agent_doc.get("model") or agent_doc.get("model_id")
		instructions = agent_doc.get("instructions") or PORTAL_CHAT_AGENT_INSTRUCTIONS

		if agent is None:
			agent = Agent(model=model_id, instructions=instructions)

		if hasattr(agent, "new_session") and not session_id:
			sess = agent.new_session(title=f"Portal · {frappe.session.user}")
			result = sess.chat(message)
			new_sid = getattr(sess, "name", None) or getattr(sess, "id", None) or session_id
			reply = getattr(result, "output", None) or getattr(result, "reply", None) or str(result)
			return {
				"reply": reply,
				"session_id": new_sid,
				"agent": agent_name,
				"configured": True,
			}

		if hasattr(agent, "run"):
			result = agent.run(message)
			reply = getattr(result, "output", None) or getattr(result, "reply", None) or str(result)
			return {
				"reply": reply,
				"session_id": session_id,
				"agent": agent_name,
				"configured": True,
			}

		# Last resort: call a common Flow API method if present
		if frappe.get_attr("flow.api.chat"):
			out = frappe.call("flow.api.chat", agent=agent_name, message=message, session=session_id)
			return {
				"reply": out.get("reply") or out.get("output") or str(out),
				"session_id": out.get("session_id") or session_id,
				"agent": agent_name,
				"configured": True,
			}

		return {
			"reply": "Flow is installed but the chat API shape is not recognized. Please update Flow or contact support.",
			"session_id": session_id,
			"agent": agent_name,
			"configured": False,
		}
	except Exception as e:
		frappe.log_error(title="portal_chat run", message=frappe.get_traceback())
		return {
			"reply": _("Sorry, I could not process that right now. Please try again in a moment."),
			"session_id": session_id,
			"agent": agent_name,
			"configured": True,
			"error": str(e),
		}


@frappe.whitelist(methods=["GET", "POST"])
def portal_chat(message=None, session_id=None):
	"""One turn of portal chatbot. Scoped to logged-in insurance client.

	Args:
	        message: user text
	        session_id: optional Flow Session name to continue conversation

	Returns:
	        {reply, session_id, agent, configured}
	"""
	# Auth + client linkage (same as other portal APIs)
	_current_client()

	message = (message or frappe.form_dict.get("message") or "").strip()
	if not message:
		frappe.throw(_("Please enter a message."))

	session_id = session_id or frappe.form_dict.get("session_id") or None
	if session_id:
		session_id = str(session_id).strip() or None

	# Soft length guard
	if len(message) > 4000:
		frappe.throw(_("Message is too long. Please keep it under 4000 characters."))

	return _run_flow_chat(message, session_id=session_id)


@frappe.whitelist(methods=["GET", "POST"])
def portal_chat_reset():
	"""Clear server-side expectation of session; client should drop sessionStorage too."""
	_current_client()
	return {"ok": True}
