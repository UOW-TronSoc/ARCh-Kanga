# NEXUS on ARCh-Kanga

The frontend in `frontend/` is the imported NEXUS application. This directory's
server and the `docker/Dockerfile.nexus` image serve it on port **8001**. The
existing ARCh basestation on port 8000 is a separate service.

`npm run dev` is the explicit demo and does not join ROS. The container image sets `VITE_NEXUS_DATA_SOURCE=live`, so a lost socket is never filled with demo values. In that build, drivestop is read-only and unwired readings stay unavailable.

```bash
cd nexus/frontend
npm ci
npm test
npm run dev
```

Open <http://localhost:5173/rover>. Routes: `/login`, `/rover`, `/launch`,
`/cameras`, `/mapping`, `/systems`.

The container launch uses the workspace overlay, `basestation/fastdds_profile.xml`,
and the same host-network selection as `scripts/basestation_up.bash`:

```bash
./scripts/nexus_up.bash
```

`GET /health` reports `backend: available` whenever the process answered.
`ros.initialized` is true only after the ROS client inside that process starts.

The rover model is Git LFS. Run `git lfs pull` on a clean checkout before
building the image.
