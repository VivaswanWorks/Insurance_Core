"""
Create sample users for client demo / showcase.

Roles (from insurance_core.install.ROLES):
  - Insurance Manager
  - Insurance Agent
  - Claims Adjuster
  - Compliance Officer
  - Insurance User

All passwords: admin

Run on site:
  bench --site <site> execute insurance_core.create_sample_users.create_sample_users

Or from bench console:
  from insurance_core.create_sample_users import create_sample_users
  create_sample_users()

Idempotent: skips users that already exist (by email).
  To reset password on existing users, call update_sample_user_passwords().
"""

from __future__ import annotations

import frappe

PASSWORD = "admin"

# email, first_name, last_name, roles, user_type, description
SAMPLE_USERS = [
	{
		"email": "manager@insurance.demo",
		"first_name": "Priya",
		"last_name": "Sharma",
		"roles": ["Insurance Manager", "System Manager"],
		"user_type": "System User",
		"description": "Full desk access – policies, claims, RFQ, settings, reports",
	},
	{
		"email": "agent@insurance.demo",
		"first_name": "Rahul",
		"last_name": "Mehta",
		"roles": ["Insurance Agent"],
		"user_type": "System User",
		"description": "Field / sales agent – clients, opportunities, quotations, policies",
	},
	{
		"email": "claims@insurance.demo",
		"first_name": "Ananya",
		"last_name": "Patel",
		"roles": ["Claims Adjuster"],
		"user_type": "System User",
		"description": "Claims desk – claim intake, triage, settlement, cashless",
	},
	{
		"email": "compliance@insurance.demo",
		"first_name": "Vikram",
		"last_name": "Singh",
		"roles": ["Compliance Officer"],
		"user_type": "System User",
		"description": "Compliance & grievances – KYC, compliance records, grievances",
	},
	{
		"email": "user@insurance.demo",
		"first_name": "Neha",
		"last_name": "Gupta",
		"roles": ["Insurance User"],
		"user_type": "System User",
		"description": "Read / limited operational user – view policies & claims",
	},
	{
		"email": "client@insurance.demo",
		"first_name": "Arjun",
		"last_name": "Kapoor",
		"roles": ["Customer"],  # portal / website; desk_access typically 0
		"user_type": "Website User",
		"description": "Portal client – policies, claims, intimation via /portal",
	},
]


def _ensure_role(role_name: str, desk_access: int = 1) -> None:
	if not frappe.db.exists("Role", role_name):
		doc = frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": desk_access,
			}
		)
		doc.insert(ignore_permissions=True)


def create_sample_users() -> list[dict]:
	"""Create sample showcase users. Returns list of created / existing summaries."""
	results = []
	for spec in SAMPLE_USERS:
		email = spec["email"]
		if frappe.db.exists("User", email):
			results.append(
				{
					"email": email,
					"status": "exists",
					"roles": spec["roles"],
					"description": spec["description"],
				}
			)
			continue

		# Ensure roles exist (Customer may already exist from ERPNext)
		for role in spec["roles"]:
			desk = 0 if role == "Customer" else 1
			_ensure_role(role, desk_access=desk)

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": spec["first_name"],
				"last_name": spec["last_name"],
				"enabled": 1,
				"send_welcome_email": 0,
				"user_type": spec["user_type"],
				"new_password": PASSWORD,
			}
		)
		user.flags.ignore_permissions = True
		user.insert(ignore_permissions=True)

		# Assign roles
		for role in spec["roles"]:
			user.add_roles(role)

		# Force password again after roles (some versions clear it)
		user.reload()
		user.new_password = PASSWORD
		user.save(ignore_permissions=True)

		results.append(
			{
				"email": email,
				"status": "created",
				"roles": spec["roles"],
				"password": PASSWORD,
				"description": spec["description"],
			}
		)

	frappe.db.commit()  # nosemgrep
	return results


def update_sample_user_passwords() -> list[dict]:
	"""Reset password to PASSWORD for every sample user that already exists."""
	results = []
	for spec in SAMPLE_USERS:
		email = spec["email"]
		if not frappe.db.exists("User", email):
			results.append({"email": email, "status": "missing"})
			continue
		user = frappe.get_doc("User", email)
		user.new_password = PASSWORD
		user.flags.ignore_permissions = True
		user.save(ignore_permissions=True)
		results.append({"email": email, "status": "password_updated", "password": PASSWORD})
	frappe.db.commit()  # nosemgrep
	return results


def print_login_card() -> None:
	"""Pretty-print credentials for the client demo."""
	print()
	print("=" * 72)
	print("  SAMPLE USERS FOR CLIENT SHOWCASE")
	print("  Password for ALL users:  admin")
	print("=" * 72)
	for s in SAMPLE_USERS:
		print(f"  {s['email']:<28}  roles: {', '.join(s['roles'])}")
		print(f"    → {s['description']}")
	print("=" * 72)
	print("  Desk login:  /app  (or /login)")
	print("  Portal:      /portal  (client@insurance.demo)")
	print("=" * 72)
	print()


if __name__ == "__main__":
	# Allow: python -m ... when run under bench
	create_sample_users()
	print_login_card()
