# NEXUS frontend import

This tree is the complete NEXUS frontend working tree, copied into
`nexus/frontend/`. It is the baseline for later ARCh integration commits.

| | |
|---|---|
| Source repository | https://github.com/Hunter-dJ03/nexus-basestation |
| Source commit | `94906f99bc2763031406e5128d9168a07b7a4c54` |
| Source subject | Refine rover telemetry panels and camera defaults |
| Working tree | That commit plus the uncommitted frontend edits below |

`nexus/frontend.sha256` lists every imported file. From `nexus/`:

```bash
sha256sum -c frontend.sha256
```

A mismatch means the imported tree no longer matches this baseline. The
original checkout at `nexus-basestation/` and the interrupted
`.worktrees/nexus-pr1` worktree were left in place as references.

## Working-tree delta against the source commit

Tracked edits that are part of this import:

```text
 M frontend/README.md
 M frontend/src/features/drive-control/DriveDock.module.css
 M frontend/src/features/drive-control/DriveDock.tsx
 D frontend/src/features/telemetry/FixtureSelector.module.css
 D frontend/src/features/telemetry/FixtureSelector.tsx
 M frontend/src/fixtures/index.ts
 M frontend/src/hooks/index.ts
 M frontend/src/layouts/OperatorShell/OperatorShell.module.css
 M frontend/src/layouts/OperatorShell/OperatorShell.tsx
 M frontend/src/pages/RoverPage/RoverPage.module.css
 M frontend/src/pages/RoverPage/RoverPage.tsx
 M frontend/src/services/contracts/AppDataService.ts
 M frontend/src/services/mock/MockAppDataService.ts
 M frontend/src/test/ui.test.tsx
 M frontend/src/types/index.ts
 M frontend/tests/e2e/rover.spec.ts
```

Untracked files included in the import:

```text
frontend/src/features/operator-input/
frontend/src/services/mock/MockAppDataService.test.ts
frontend/src/test/snapshotBuilders.ts
frontend/src/types/controlFocus.ts
```

`FixtureSelector` is absent on purpose. `node_modules/` and `dist/` were not
imported.

The source checkout also had uncommitted edits to `README.md` and
`docs/plans/04-drive-control-and-safety.md`. Those are not part of the
frontend application and were not copied.

Diff stat of those tracked frontend edits: 16 files changed, 214 insertions,
198 deletions. The source checkout's full diff is 18 files, 239 insertions,
and 209 deletions. The remainder is the two documentation files left behind.
