import frappe

no_cache = 1
sitemap = 0


def get_context(context):
	"""Portal SPA shell — always emit a real CSRF token for the Vue app."""
	context.no_cache = 1
	# Explicit token so Jinja never leaves the placeholder string in HTML
	try:
		token = frappe.sessions.get_csrf_token()
	except Exception:
		token = getattr(frappe.session, "csrf_token", None) or ""
	context.csrf_token = token or ""
	# Also expose on boot-like shape some frontends expect
	context.boot = {"csrf_token": context.csrf_token}
