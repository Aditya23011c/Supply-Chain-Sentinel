# n8n setup (about 10 minutes)

The agents decide; n8n **acts**. Three workflows, one per action:

| Workflow file | Webhook path | What it does |
|---|---|---|
| `send-outreach.json` | `/webhook/send-outreach` | Composes the supplier email and delivers it (to the dashboard's supplier inbox) |
| `trigger-budget-review.json` | `/webhook/trigger-budget-review` | Opens a review ticket, asks the Budget Agent's policy service for a decision, returns it |
| `notify-approved-plan.json` | `/webhook/notify-approved-plan` | Builds a purchase order and tells the dashboard |

## 1. Start n8n
n8n supports Node 20.19 - 24.x (you have Node 24, so this works). In a **new terminal**:

    npx n8n

First start downloads it (a minute or two). Open http://localhost:5678 and create the owner account when asked.

## 2. Import the three workflows
In n8n: **Workflows -> (top right) "..." menu -> Import from file** - do this once per file in this folder.

## 3. Publish each workflow  (the step everyone forgets)
Open each workflow and click **Publish** (older versions call it the "Active" toggle).
Only published workflows answer on the production URL `/webhook/...`. An unpublished one gives
`404 ... webhook is not registered`.

## 4. Point the backend at n8n
Edit `.env` (project root):

    N8N_BASE_URL=http://127.0.0.1:5678
    BACKEND_PUBLIC_URL=http://127.0.0.1:8000

Restart the backend. Use `127.0.0.1`, not `localhost` (avoids IPv6 surprises).
If n8n runs in **Docker**, use `BACKEND_PUBLIC_URL=http://host.docker.internal:8000`.

## 5. Test
With the backend running (n8n calls it back), from the project root:

    python -m agents.negotiation.n8n_client

You want `mode=n8n` for all three. Then click any trigger in the dashboard: the header chip says
**n8n connected**, and each workflow run appears in n8n under **Executions**.

## Troubleshooting
- `mode=fallback` + `404` -> workflow not published, or wrong path.
- `mode=fallback` + connection refused -> n8n isn't running / wrong `N8N_BASE_URL`.
- Executions show the HTTP Request node failing -> n8n can't reach the backend; fix `BACKEND_PUBLIC_URL`.
- The demo never breaks if n8n is down: the agents fall back to local logic and the UI says so.

## Make it deliver for real
Each workflow has a sticky note showing where. Add a Gmail / SMTP / Slack / Telegram node after
**Compose email** (fields: `to`, `subject`, `body`) or after **Build purchase order**.
Note: n8n Cloud can't call a backend on your laptop; run n8n locally, or expose the backend with a tunnel.
