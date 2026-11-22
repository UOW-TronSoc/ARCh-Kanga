# Kanga Basestation frontend

Visual-first React workspace for the UOW TronSoc Kanga rover basestation. The current slice uses typed deterministic fixtures and does not communicate with the rover or backend.

## Commands

```bash
npm install
npm run dev
npm run lint
npm test
npm run build
npm run test:e2e
```

Open `/rover` for the operator workspace or `/login` for the visual authentication placeholder. The mock app starts with drivestop asserted, ODrive idle, and drive input disabled.

The transport boundary is `src/services/contracts/AppDataService.ts`. Future live REST and WebSocket services should implement that interface rather than changing page or presentational components.
