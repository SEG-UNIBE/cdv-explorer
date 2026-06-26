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
