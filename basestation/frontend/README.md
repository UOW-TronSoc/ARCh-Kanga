# Kanga Basestation Frontend

React/Vite operator interface for the single Kanga basestation server. The
production build is served by FastAPI on port 8000; Vite is only used for local
development and building static assets.

## Local development

Start the basestation backend from the repository root, then run Vite:

```bash
./scripts/basestation_up.bash
cd basestation/frontend
npm ci
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). The dev server proxies
`/api`, `/health`, and `/ws` to `http://127.0.0.1:8000`.

## Checks and production build

```bash
npm run lint
npm run build
```

From the repository root, `./scripts/build_frontend.bash` performs the supported
production build into `basestation/server/static/`. The same build also runs as
the frontend stage of the basestation Docker image.

## Project structure

- `src/pages/` owns route-level screens.
- `src/components/` owns reusable operator controls and status cards.
- `src/context/` owns shared authentication and telemetry state.
- `src/hooks/` owns control and telemetry WebSocket clients.
- `src/config.js` builds same-origin HTTP and WebSocket URLs.

See the [basestation overview](../README.md) for runtime instructions and the
[commissioning page plan](../COMMISSIONING_PAGE_PLAN.md) for the next operator
feature slice.
