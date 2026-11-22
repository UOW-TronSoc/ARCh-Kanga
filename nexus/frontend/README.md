# Kanga Basestation frontend

React operator workspace for the UOW TronSoc Kanga rover. `npm run dev` is the
demo and uses typed fixtures. The Docker image builds the same UI with
`VITE_NEXUS_DATA_SOURCE=live`, which connects to the NEXUS server in
`../server` instead of the fixtures.

## Commands

```bash
npm install
npm run dev
npm run lint
npm test
npm run build
npm run test:e2e
```

Open `/rover` for the operator workspace or `/login` for the demo entrance.
The mock app starts with drivestop asserted, ODrive idle, and drive input
disabled.

The transport boundary is `src/services/contracts/AppDataService.ts`. The live
implementation is `src/services/live/LiveTelemetryService.ts`. It subscribes to
`/ws/telemetry`, sends ownership and drive commands on `/ws/control`, and does
not replace missing rover data with demo values.

Live drivestop text is shared by the top bar and the drive panel: Unknown,
Asserted, Released, or Stale. Wheel velocities shown without motor controllers
come from joint state and are marked stale when the backend's sample is older
than one second.
