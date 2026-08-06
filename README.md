# OptiRoute

Route planning app for drivers delivering liquor to liquor stores. Interactable map (MapLibre GL + OpenStreetMap-based vector tiles), a stub route optimizer, and a wired-up (but not yet behaviorally implemented) Claude agent endpoint.

## Stack

- **Frontend**: React + TypeScript + Vite, MapLibre GL JS for the map
- **Backend**: Python (FastAPI) — hosts the route optimizer and the Claude agent plumbing

## Getting started

### Backend

```sh
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
copy .env.example .env       # then fill in ANTHROPIC_API_KEY if you'll use the /api/agent/ask endpoint
uvicorn app.main:app --reload --port 8000
```

Requires Python 3.10+.

### Frontend

```sh
cd frontend
npm install
copy .env.example .env
npm run dev
```

Opens at http://localhost:5173, talking to the backend at http://localhost:8000.

## What's stubbed vs. real

- **Map**: fully interactive — MapLibre GL JS rendering [OpenFreeMap](https://openfreemap.org/) vector tiles (free, no API key, built on OpenStreetMap data). Swap the `style` URL in `frontend/src/components/Map.tsx` for MapTiler/Stadia Maps/a self-hosted tile server if you need production-grade uptime guarantees.
- **Route lines**: drawn as straight lines between stops, not road-snapped. Wire up a routing engine (OSRM, GraphHopper, Mapbox Directions) to get real turn-by-turn polylines.
- **Optimizer** (`backend/app/optimizer.py`): a naive round-robin + nearest-neighbor stub. It ignores time windows, traffic, and proper multi-constraint bin packing. Replace with a real Vehicle Routing Problem solver — [Google OR-Tools](https://developers.google.com/optimization/routing) is the standard choice and has first-class Python support.
- **Agent** (`backend/app/agent/dispatch_agent.py`): plumbing only. One trivial tool (`get_fleet_status`) demonstrates the Anthropic SDK's tool-use loop end-to-end (`POST /api/agent/ask`). No real dispatch reasoning yet — add tools that call the optimizer, check live traffic, or let a dispatcher edit a route in natural language.
- **Data**: in-memory mock stores/drivers in `backend/app/data.py`. Swap for a real database when ready.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/stores` | List liquor stores (mock data) |
| GET | `/api/drivers` | List drivers (mock data) |
| POST | `/api/optimize` | Assigns stores to drivers and orders each driver's stops |
| POST | `/api/agent/ask` | Ask the (stubbed) dispatch agent a question |
| GET | `/api/imports/pending` | List pending imports awaiting review (from OCR uploads or QuickBooks) |
| POST | `/api/imports/{id}/confirm` | Confirm a pending import into a `Store` |
| GET | `/api/quickbooks/status` | Whether a QuickBooks company is currently connected |
| GET | `/api/quickbooks/connect` | Starts the QuickBooks OAuth flow (redirects to Intuit) |
| GET | `/api/quickbooks/callback` | OAuth redirect target — exchanges the auth code for tokens |
| POST | `/api/quickbooks/webhook` | Intuit invoice webhook receiver — pushes new/updated invoices into the pending-import pipeline |

### QuickBooks invoice import

Connecting a QuickBooks Online company lets its invoices flow straight into the same review queue the OCR upload path uses (`ImportOrdersModal`) — no scanning required, since QuickBooks gives structured data directly.

1. Create an app at [developer.intuit.com](https://developer.intuit.com), fill in `QBO_CLIENT_ID`/`QBO_CLIENT_SECRET`/`QBO_REDIRECT_URI` in `backend/.env`.
2. Point the app's **Webhooks** subscription (Invoice entity) at `{your public backend URL}/api/quickbooks/webhook`, and copy its **Verifier Token** into `QBO_WEBHOOK_VERIFIER_TOKEN`. Webhooks require a public HTTPS URL, so use a tunnel (e.g. `ngrok http 8000`) for local dev.
3. Visit `/api/quickbooks/connect` in a browser once to authorize the company (also reachable via the "Connect QuickBooks" link in the Import Orders modal).
4. Creating/updating an invoice in QuickBooks now lands it in the pending-imports list, pre-filled with invoice #, customer name, ship-to address (geocoded), and a case count estimated from line-item quantities — ready to review and confirm.
