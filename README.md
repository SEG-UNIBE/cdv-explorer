# **CDV-Explorer**

_Modern decentralized software ecosystems evolve through crowdsourced improvement proposals (IPs) that are continuously shaped and autonomously implemented by independent actors. As a result, these ecosystems exhibit so-called **Community-Driven Variability (CDV)** [^1], a novel paradigm that extends beyond traditional variability-intensive systems. This tool allows to explore the proposal space of such ecosystems by providing interactive visualizations and insights about their evolution, authorship, classification, conformity, and inter-proposal relationships._


<div align="center">
  <a href="https://seg-unibe.github.io/cdv-explorer/#/">
    <img width="100%" src="./assets/thumb.png" alt="CDV-Explorer" />
  </a>
</div>

</br>

<div align="center">
  <strong>
    👋 <a href="#introduction">Introduction</a> &nbsp;|&nbsp;
    🚀 <a href="#setup">Setup</a> &nbsp;|&nbsp;
    🛠️ <a href="#developer-notes">Developer Notes</a> &nbsp;|&nbsp;
    🧹 <a href="#cleanup">Cleanup</a>
  </strong>
</div>

</br>

<div align="center">
  <a href="https://github.com/SEG-UNIBE/cdv-explorer/actions/workflows/deploy-react-pages.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/SEG-UNIBE/cdv-explorer/deploy-react-pages.yml?style=flat&label=deploy&logo=githubactions&logoColor=white" alt="Deploy" />
  </a>
  <a href="https://seg-unibe.github.io/cdv-explorer/#/">
    <img src="https://img.shields.io/badge/GitHub%20Pages-live-brightgreen?style=flat&logo=githubpages&logoColor=white" alt="Live Demo" />
  </a>
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/License-GPL--3.0-red?style=flat" alt="GPL-3.0" />
  </a>
</div>

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/React-18-3776AB?style=flat&logo=react&logoColor=white" alt="React 18" />
  <img src="https://img.shields.io/badge/Node.js-22%2B-3776AB?style=flat&logo=nodedotjs&logoColor=white" alt="Node.js 22+" />
  <img src="https://img.shields.io/badge/D3.js-v7-3776AB?style=flat&logo=d3dotjs&logoColor=white" alt="D3.js" />
  <a href="https://youtu.be/-YdBPHsyymU"><img src="https://img.shields.io/badge/Demo-Video-red.svg?logo=youtube&logoColor=white" alt="Demo Video" /></a>
</div>

</br>
</br>

## Introduction

CDV-Explorer is an ecosystem-agnostic pipeline for mining and analysing improvement proposals (IPs).
As of now, two CDV-exhibiting ecosystems are integrated:

| Ecosystem | Proposals | Source repository |
|-----------|-----------|-------------------|
| **Bitcoin** | Bitcoin Improvement Proposals (BIPs) | [bitcoin/bips](https://github.com/bitcoin/bips) |
| **Nostr** | Nostr Implementation Possibilities (NIPs) | [nostr-protocol/nips](https://github.com/nostr-protocol/nips) |

The live site is available at [seg-unibe.github.io/cdv-explorer](https://seg-unibe.github.io/cdv-explorer/#/), with a demo video on [YouTube](https://youtu.be/-YdBPHsyymU).
CDV-Explorer was applied in an empirical study of the Bitcoin ecosystem, which has been accepted for publication [^2].

</br>

## Setup

### Requirements

| Tool | Version | macOS using [`brew`](https://brew.sh) | Linux | Windows using [`winget`](https://learn.microsoft.com/windows/package-manager/winget/) |
|------|---------|-------|-------|---------|
| **Python** | 3.12+ | `brew install python` | `sudo apt install python3` | `winget install Python.Python.3` |
| **Node.js** | 22+ (npm bundled) | `brew install node` | `sudo apt install nodejs npm` | `winget install OpenJS.NodeJS` |
| **Git** | any | `brew install git` | `sudo apt install git` | `winget install Git.Git` |

### 1 - Clone the repository

```bash
git clone https://github.com/SEG-UNIBE/cdv-explorer.git
cd cdv-explorer
```

### 2 - Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3 - Install dependencies

```bash
pip install -r requirements.txt
```

### 4 - Run the pipeline

The `run` command clones/updates the source repository, extracts and enriches proposal data, builds analysis artifacts, and produces React-ready exports -- all in one step.

**Bitcoin (BIPs):**

```bash
python main.py run -e bitcoin -s 2026-03-16 --skipllm
```

**Nostr (NIPs):**

```bash
python main.py run -e nostr -s 2026-03-16 --skipllm
```

> [!NOTE]
> Omit `--skipllm` to also run the OpenAI-based inter-proposal relation extraction. Provide the API key via the `OPENAI_API_KEY` environment variable, or by creating a file named `apikey.secret` in the project root containing only the key. The pipeline picks up the file automatically when the environment variable is not set.

> **Snapshot date:** `-s` is required. The pipeline resolves to the last commit whose committer timestamp falls on or before `YYYY-MM-DD 23:59:59` and checks out the repository at that point.

### 5 - Start the React app

```bash
cd react
npm install
npm start        # dev server at http://localhost:3000
```

`npm start` also regenerates the proposal link indexes (BIP and NIP) automatically before launching the dev server.

For a production build:

```bash
npm run build
```

</br>

## CLI Reference

CDV-Explorer is driven by a [Typer](https://typer.tiangolo.com/) CLI.
Run `python main.py --help` for a full overview.

### `run` - execute the full pipeline

```bash
python main.py run [OPTIONS]

Options:
  -e, --ecosystem TEXT   Ecosystem slug (default: first registered)
      --source TEXT      Source slug (default: all sources for that ecosystem)
  -s, --snapshot TEXT    Snapshot date YYYY-MM-DD  [required]
      --skipllm          Skip LLM-based extraction
```

### `snapshots` - list available snapshots

```bash
python main.py snapshots
python main.py snapshots -e bitcoin
```

### `ecosystems` - manage ecosystem configs

```bash
python main.py ecosystems list                # show all registered ecosystems
python main.py ecosystems show bitcoin        # dump full YAML config as JSON
python main.py ecosystems add                 # scaffold a new ecosystem YAML (interactive)
python main.py ecosystems add-source bitcoin  # add a second IP catalog to an ecosystem
```

</br>

## Developer Notes

### Pipeline architecture

The pipeline transforms raw IP corpora into versioned, frontend-ready datasets in four stages: **Harvest** → **Preprocess** → **Analysis** → **Postprocess**.
Ecosystem-specific logic is confined to the first two stages, keeping the analysis and frontend layers fully reusable across ecosystems.

![CDV-Explorer pipeline](./assets/architecture_mining_pipeline_ext.png)

### Project structure

```bash
.
├── ecosystems/              # ecosystem configs (YAML) — one file per ecosystem
├── pipeline/
│   ├── harvest/             # Stage I  — ecosystem-specific: clone & snapshot checkout
│   └── preprocess/          # Stage II — ecosystem-specific: preamble extraction & enrichment
├── analysis/                # Stage III/IV — ecosystem-agnostic analysis modules & postprocess
│   ├── authorship/
│   ├── classification/
│   ├── conformity/
│   ├── dependencies/
│   ├── evolution/
│   └── wordcloud/
├── react/                   # interactive frontend (D3, PrimeReact)
└── ip_data/
    └── <ecosystem>/
        ├── 01_harvest/      # raw IP documents             [gitignored]
        ├── 02_preprocess/   # IP object model (JSON)       ← Stage II output
        ├── 03_analysis/     # analysis artifacts           ← Stage III output
        └── 04_postprocess/  # frontend payloads            ← Stage IV output
```

### Preprocess schema

Each proposal is stored as a JSON file under `02_preprocess/<snapshot>/`.
The schema has three top-level blocks: **`raw`** (verbatim preamble), **`meta`** (Git-derived history and timestamps), and **`insights`** (compliance checks, word list, status history, inter-proposal relations).

```json
{
  "raw": {
    "preamble": [dict]
  },
  "meta": {
    "last_commit": [datetime],
    "total_commits": [int],
    "git_history": [/* ... */]
  },
  "insights": {
    "formal_compliance": [/* ... */],
    "word_list": [dict],
    "changes_in_status": [/* ... */],
    "interrelations": {
      "preamble_extracted":   [set of IPs],
      "body_extracted_regex": [set of IPs],
      "body_extracted_llm":   [set of IPs]
    }
  }
}
```

Concrete examples: [`bip-0340.json`](ip_data/bitcoin/02_preprocess/2026-03-16/bip-0340.json) (Schnorr Signatures) · [`nip-10.json`](ip_data/nostr/nips/02_preprocess/2026-05-30/nip-10.json) (Text Notes and Threads)

### Adding a new ecosystem

1. Run `python main.py ecosystems add` and answer the prompts — a scaffolded `ecosystems/<slug>.yml` is created.
2. Edit the YAML to fill in classification dimensions, conformity standards, preamble field rules, and any other config.
3. Implement the ecosystem-specific **Stage I & II** logic in `pipeline/`:
   - `harvest/` — a harvester that clones or fetches the IP source and checks out a snapshot
   - `preprocess/` — an extractor that parses raw documents into the canonical IP object model, and a compliance checker under `preprocess/checkers/`
4. Add a corresponding adapter under `react/src/ecosystems/<slug>/` (copy `bitcoin/` or `nostr/` as a template).
5. Run `python main.py run -e <slug> -s <date> --skipllm` to verify the pipeline end-to-end.

### Deployment

The app is deployed to GitHub Pages via [`.github/workflows/deploy-react-pages.yml`](.github/workflows/deploy-react-pages.yml) on every push to `main` that touches `react/` or `ip_data/`.
To enable Pages on a fork, go to `Settings > Pages` and set the source to `GitHub Actions`.

</br>

## Cleanup

Deactivate the virtual environment:

```bash
deactivate
```

Optionally remove individual artifacts without deleting the repository:

```bash
rm -rf .venv
rm -rf ip_data/**/01_harvest           # harvested source repos (gitignored, can be large)
rm -rf react/node_modules react/build
```

Or remove everything at once:

```bash
cd .. && rm -rf cdv-explorer
```

</br>
</br>

[^1]: Bögli, R. et al. _Community-driven variability: characterizing a new software variability paradigm._ Autom Softw Eng **33**, 67 (2026). [10.1007/s10515-026-00594-0](https://doi.org/10.1007/s10515-026-00594-0)

[^2]: Bögli, R., Boll, A., Kehrer, T. _Exploring Crowdsourced Feature Specifications: The Bitcoin Case._ VARIABILITY (2026). Accepted for publication. [Preprint](https://romanboegli.ch/assets/pdf/xxxxxxxxx.pdf)
