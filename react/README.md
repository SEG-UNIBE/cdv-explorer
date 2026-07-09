# Frontend Notes

This directory contains the CDV-Explorer React frontend.

The main project documentation lives in the root [README.md](../README.md). This file only keeps frontend-local notes.

## Tooling

- Build and dev server: `Vite`
- Test runner: `Vitest`
- UI stack: `React`, `PrimeReact`, `D3`

## Common Commands

Run these from the `react/` directory:

```bash
npm install
npm run dev
npm test -- --run
npm run build
```

## Notes

- `npm run dev` starts the local Vite dev server.
- `npm test -- --run` executes the Vitest suite once.
- `npm run build` writes the production bundle to `react/build/`.
- Build-time indexes are generated automatically by the npm lifecycle scripts.
- The lifecycle scripts also run `scripts/syncPublicData.js`, which copies only the
  Stage IV frontend payloads (the six per-snapshot JSON files under
  `04_postprocess/`, loaded by `src/data.js`) from `../ip_data` into
  `public/ip_data`. The other pipeline stages (`01_harvest`, `02_preprocess`,
  `03_analysis`) are never published. After regenerating pipeline artifacts,
  rerun `npm run generate:indexes` (or simply `npm run dev`) to refresh the
  synced copy — `public/ip_data` is gitignored.
- The dashboard fetches payloads in two phases: `network_data.json`,
  `authorship_payload.json`, and `classification_payload.json` load up front
  (proposal nodes feed every section), while `dependency_metrics.json`,
  `evolution_payload.json`, and `conformity_metrics.json` are fetched only when
  their dashboard section scrolls into view (`src/dashboard/useSectionDataLoader.js`).
