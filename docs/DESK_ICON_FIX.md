# Insurance Core desk icon fix (v16 Desktop Layout + logo)

## Symptoms

1. **Icon missing on home desk** even though Desktop Icon list has "Insurance Core".
2. **Icon shows as gray letter "I"** instead of the shield / app logo.

## Root causes

### Missing from Desktop Layout
On Frappe **v16**, the home desk is driven by per-user **Desktop Layout** JSON, not only **Desktop Icon**. If the layout was saved before Insurance Core existed, the icon never appears.

### Letter avatar ("I" on gray)
The desk tile template uses `logo_url` when set; otherwise it falls back to a letter avatar from the label (first letter → **"I"** for Insurance Core). Setting only `icon: "shield"` is not enough on the home grid.

The Healthcare "Insurance" tile is a different icon (healthcare submodule).

## Fix (in artifacts/install.py)

`ensure_desktop_icon()` now:

1. Creates/repairs Desktop Icon with `icon=shield`, **`logo_url=/assets/insurance_core/images/insurance.svg`**, `bg_color=blue`.
2. Appends **or repairs** Insurance Core in every Desktop Layout (sets `logo_url` on existing entries so the letter avatar is replaced).
3. Clears cache.

## One-shot console fix (run now)

```bash
bench --site <site> console
```

```python
import json
import frappe

label = "Insurance Core"
logo_url = "/assets/insurance_core/images/insurance.svg"

# 1) Desktop Icon — force logo so letter avatar goes away
if frappe.db.exists("Desktop Icon", label):
    doc = frappe.get_doc("Desktop Icon", label)
    doc.hidden = 0
    doc.icon_type = "Link"
    doc.link_type = "Workspace Sidebar"
    doc.link_to = label
    doc.icon = "shield"
    doc.logo_url = logo_url
    doc.bg_color = "blue"
    if hasattr(doc, "app"):
        doc.app = "insurance_core"
    doc.save(ignore_permissions=True)
else:
    frappe.get_doc({
        "doctype": "Desktop Icon",
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
    }).insert(ignore_permissions=True)

# 2) Patch every Desktop Layout (inject or repair logo_url)
for row in frappe.get_all("Desktop Layout", fields=["name", "user", "layout"]):
    try:
        layout = json.loads(row.layout or "[]")
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
        if item.get("logo_url") != logo_url:
            item["logo_url"] = logo_url
            changed = True
        if item.get("icon") != "shield":
            item["icon"] = "shield"
            changed = True
        if not item.get("bg_color"):
            item["bg_color"] = "blue"
            changed = True
        break
    if not found:
        layout.append({
            "label": label,
            "name": label,
            "icon_type": "Link",
            "link_type": "Workspace Sidebar",
            "link_to": label,
            "icon": "shield",
            "logo_url": logo_url,
            "bg_color": "blue",
            "app": "insurance_core",
            "standard": 1,
            "hidden": 0,
            "idx": 20,
            "parent_icon": None,
            "icon_image": None,
            "restrict_removal": 0,
            "child_icons": [],
        })
        changed = True
    if changed:
        doc = frappe.get_doc("Desktop Layout", row.name)
        doc.layout = json.dumps(layout)
        doc.save(ignore_permissions=True)

frappe.db.commit()
frappe.clear_cache()
print("Done — hard-refresh /app (Ctrl+Shift+R)")
```

## Verify

```python
print(frappe.db.get_value("Desktop Icon", "Insurance Core",
      ["logo_url", "icon", "bg_color", "hidden"], as_dict=1))

import json
layout = frappe.db.get_value("Desktop Layout", "Administrator", "layout")
for i in json.loads(layout or "[]"):
    if i.get("label") == "Insurance Core":
        print(i.get("logo_url"), i.get("icon"), i.get("bg_color"))
```

Expect:

- `logo_url` = `/assets/insurance_core/images/insurance.svg`
- `icon` = `shield`
- `bg_color` = `blue`

Hard-refresh Desk. You should see the Insurance Core logo (not the letter **I**).

## Permanent

```bash
cp artifacts/install.py apps/insurance_core/insurance_core/install.py
bench --site <site> migrate
bench --site <site> clear-cache
```

## Optional: reset layout

```python
frappe.delete_doc("Desktop Layout", "Administrator", force=1, ignore_permissions=True)
frappe.db.commit()
frappe.clear_cache()
```

Then log out/in so the layout rebuilds from Desktop Icons (which now have `logo_url`).
