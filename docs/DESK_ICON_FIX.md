# Insurance Core desk icon fix (v16 Desktop Layout)

## Root cause

On Frappe **v16**, the home desk is driven by **two** sources:

1. **Desktop Icon** — global catalogue of icons (your row exists and is visible in the list).
2. **Desktop Layout** — per-user JSON (`Desktop Layout` DocType, named by user).  
   If this layout was saved *before* Insurance Core existed, the icon never appears on `/app` even when Desktop Icon is correct. Stale layout overrides the live icon list.

The Healthcare “Insurance” tile in the layout is a **different** icon (healthcare submodule), not Insurance Core.

Earlier `install.py` only created/unhid Desktop Icon + Workspace. It never patched Desktop Layout.

## Fix (in artifacts/install.py)

`ensure_desktop_icon()` now:

1. Calls `create_desktop_icons()`.
2. Ensures Desktop Icon `Insurance Core` (Link → Workspace Sidebar, icon=shield, unhidden).
3. **Patches every Desktop Layout**: appends an Insurance Core entry if missing.
4. Clears cache.

## Apply on the site

```bash
# Copy fixed install into the app
cp /path/to/artifacts/install.py apps/insurance_core/insurance_core/install.py

bench --site <site> migrate
bench --site <site> clear-cache
```

Or one-shot from console (no file copy required for an immediate fix):

```bash
bench --site <site> console
```

```python
from insurance_core.install import ensure_module, ensure_workspace, ensure_desktop_icon
ensure_module()
ensure_workspace()
ensure_desktop_icon()
frappe.db.commit()
frappe.clear_cache()
```

If the app still has the **old** install.py without the layout patch, run this instead:

```python
import json
import frappe

label = "Insurance Core"

# 1) Desktop Icon
if frappe.db.exists("Desktop Icon", label):
    doc = frappe.get_doc("Desktop Icon", label)
    doc.hidden = 0
    doc.link_type = "Workspace Sidebar"
    doc.link_to = label
    if hasattr(doc, "icon") and not doc.icon:
        doc.icon = "shield"
    doc.save(ignore_permissions=True)
else:
    frappe.get_doc({
        "doctype": "Desktop Icon",
        "label": label,
        "icon_type": "Link",
        "link_type": "Workspace Sidebar",
        "link_to": label,
        "icon": "shield",
        "standard": 1,
        "hidden": 0,
        "idx": 0,
    }).insert(ignore_permissions=True)

# 2) Patch every Desktop Layout
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
for row in frappe.get_all("Desktop Layout", fields=["name", "user", "layout"]):
    try:
        layout = json.loads(row.layout or "[]")
    except Exception:
        continue
    if not isinstance(layout, list):
        continue
    if any(isinstance(i, dict) and (i.get("label") == label or i.get("name") == label) for i in layout):
        continue
    layout.append(icon_entry)
    doc = frappe.get_doc("Desktop Layout", row.name)
    doc.layout = json.dumps(layout)
    doc.save(ignore_permissions=True)

frappe.db.commit()
frappe.clear_cache()
print("Done — hard-refresh Desk (/app)")
```

## Verify

```python
frappe.db.exists("Workspace", "Insurance Core")
frappe.db.get_value("Workspace", "Insurance Core", ["public", "is_hidden", "icon"])
frappe.db.exists("Desktop Icon", "Insurance Core")
frappe.db.get_value("Desktop Icon", "Insurance Core", ["hidden", "link_type", "link_to", "icon"])

# Layout must list Insurance Core
import json
layout = frappe.db.get_value("Desktop Layout", "Administrator", "layout")
items = json.loads(layout or "[]")
print([i.get("label") for i in items if "Insur" in str(i.get("label", ""))])
```

Then hard-refresh Desk (`/app`). You should see **Insurance Core** as a top-level tile (distinct from Healthcare’s Insurance).

## Optional: reset layout entirely

If the desk is still messy, delete the user’s Desktop Layout so Frappe rebuilds from Desktop Icons:

```python
frappe.delete_doc("Desktop Layout", "Administrator", force=1, ignore_permissions=True)
frappe.db.commit()
frappe.clear_cache()
```

Log out and back in (or hard-refresh).
