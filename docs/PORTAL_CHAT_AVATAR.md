# Portal floating avatar chatbot

## What was added

### Frontend (`App.vue` / `frontend_App.vue`)
- Fixed bottom-right **avatar button** (real image, not emoji/icon)
- Chat panel: message list, suggestion chips, send form
- Calls `insurance_core.portal.portal_chat`
- Session id kept in `sessionStorage` for multi-turn continuity
- Fallback SVG portrait if `/assets/insurance_core/images/assistant-avatar.png` is missing

### Backend (`portal.py`)
- `portal_chat(message, session_id=None)` — authenticated, client-scoped
- `portal_chat_reset()` — optional client reset helper
- Resolves or creates Flow Agent titled **Insurance Portal Assistant**
- Graceful messages if Flow / model is not installed yet

## Deploy steps (on your bench)

1. **Copy files into the app**
   ```bash
   # from artifacts into your app tree
   cp artifacts/App.vue apps/insurance_core/frontend/src/App.vue
   # or wherever your Vue entry lives
   cp artifacts/portal.py apps/insurance_core/insurance_core/portal.py
   ```

2. **Avatar image** (recommended)
   ```bash
   mkdir -p apps/insurance_core/insurance_core/public/images
   # place a 256×256+ PNG/WebP portrait:
   # apps/insurance_core/insurance_core/public/images/assistant-avatar.png
   ```
   Served as: `/assets/insurance_core/images/assistant-avatar.png`

3. **Build frontend**
   ```bash
   cd apps/insurance_core/frontend && yarn build
   # or your usual build path
   bench build --app insurance_core
   ```

4. **Migrate / clear cache**
   ```bash
   bench --site <site> clear-cache
   bench --site <site> migrate   # if hooks/doctypes changed
   ```

5. **Flow setup (required for real answers)**
   - Install Flow: `bench get-app flow && bench --site <site> install-app flow`
   - Create **Flow Provider** (API key) + **Flow Model**
   - Optionally create **Flow Knowledge Base**, add sources, bind to agent
   - Agent titled `Insurance Portal Assistant` is auto-created on first chat if missing
   - Or create the agent manually in Desk and attach the KB

## API contract

`POST /api/method/insurance_core.portal.portal_chat`

```json
{ "message": "What documents for a motor claim?", "session_id": null }
```

Response:

```json
{
  "message": {
    "reply": "...",
    "session_id": "FLOW-SESS-...",
    "agent": "Insurance Portal Assistant",
    "configured": true
  }
}
```

## Notes
- Portal chat is separate from Desk **Cmd+I**
- Permissions: same as other portal methods (logged-in user linked to Insurance Client)
- Flow API shapes vary slightly by version; `_run_flow_chat` tries several paths and logs errors to Error Log
