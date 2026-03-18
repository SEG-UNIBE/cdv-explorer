# CDV Explorer

## Overview

CDV Explorer is an ecosystem-agnostic proposal analysis pipeline.

Bitcoin is the first implemented adapter, using the BIP repository as source.
The same architecture is intended to support additional ecosystems later.

The project produces:

- preprocessed proposal JSON snapshots by snapshot date
- analysis artifacts for dependencies, authorship, classification, and conformity
- postprocessed React-ready datasets for the frontend and publication workflows

## Repository Layout

### Core scripts

- `main.py`: runs the full pipeline for a selected snapshot
- `download.py`: clones or updates the source repository and checks out a snapshot
- `preamble_extraction.py`: extracts proposal preambles into JSON
- `ip_processing.py`: enriches JSON with metadata and insights
- `ecosystem_config.py`: active ecosystem configuration

### Analysis module

- `analysis/dependencies`
- `analysis/authorship`
- `analysis/classification`
- `analysis/conformity`
- `analysis/pipeline.py`: orchestrates analysis and postprocess exports

### Data outputs

All outputs are written under:

- `ip_data/<ecosystem>/01_harvest`
- `ip_data/<ecosystem>/02_preprocess/<SNAPSHOT>`
- `ip_data/<ecosystem>/03_analysis/<SNAPSHOT>/<submodule>`
- `ip_data/<ecosystem>/04_postprocess/<SNAPSHOT>/react`

### Frontend

- `react/`: React app consuming snapshot and analysis outputs

## Requirements

- Python 3.10+
- Git
- Node.js 20+ (for frontend)
- npm

Optional:

- OpenAI API key (`OPENAI_API_KEY` or `apikey.secret`) for LLM dependency extraction

## Pipeline Usage

Run the full pipeline for a specific snapshot:

```bash
python main.py --snapshot 2025-12-31
```

What this does:

1. prepares Python dependencies
2. fetches the source proposal repository at the snapshot date
3. extracts preamble data to preprocess JSON
4. enriches metadata and insights
5. builds analysis artifacts in `03_analysis`
6. builds React-ready exports in `04_postprocess`

## Analysis Submodule Commands

You can run submodules directly if needed.

Build dependency network artifacts:

```bash
python -m analysis.dependencies.build_snapshot --snapshot 2025-12-31
```

Generate dependency plots:

```bash
python -m analysis.dependencies.plotting --snapshot 2025-12-31
```

Prepare authorship payload:

```bash
python -m analysis.authorship.prepare --snapshot 2025-12-31
```

Prepare classification payload:

```bash
python -m analysis.classification.prepare --snapshot 2025-12-31
```

## React App

Install dependencies:

```bash
cd react
npm install
```

Start dev server:

```bash
npm start
```

Create production build:

```bash
npm run build
```

The app supports snapshot selection by snapshot date and consumes generated
analysis artifacts for:

- dependency network
- authorship
- classification
- conformity

## GitHub Pages Deployment

Deployment is configured in:

- `.github/workflows/deploy-react-pages.yml`

On push to `main` or `master`, GitHub Actions:

1. installs dependencies in `react/`
2. builds the app
3. publishes to GitHub Pages

Workflow trigger paths include:

- `react/**`
- `ip_data/**/01_harvest/**`
- `ip_data/**/02_preprocess/**`
- `ip_data/**/03_analysis/**`
- `ip_data/**/04_postprocess/**`

To enable Pages:

1. open repository settings
2. go to `Settings > Pages`
3. set source to `GitHub Actions`

