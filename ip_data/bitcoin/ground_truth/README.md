# Ground-Truth Interrelations — Bitcoin

Manually curated interrelation edges for the Bitcoin ecosystem (BIPs + SLIPs).
Used as the canonical reference against which `llm`, `preamble`, and `regex` extraction methods are evaluated.

## File layout

- Editable workbook: [`ground_truth.xlsx`](./ground_truth.xlsx) with two sheets: `ips` and `interrelations`.
- Generated pending sampled IP rows: [`ips_append.xlsx`](./ips_append.xlsx).
- Generated reviewed source-IP scope: [`ips.csv`](./ips.csv).
- Generated curated edges: [`interrelations.csv`](./interrelations.csv).
- Inter-source edges (e.g. `bips:N → slips:M`) live in the same file.
- The workbook is the primary editable source. Python tooling reads from it directly when present.
- The CSV files remain pipeline-friendly exports. They should be treated as derived artifacts and are synced from the workbook during explicit rebuild/sync steps rather than on every read.
- The `ground-truth sample-ips` CLI command never edits `ground_truth.xlsx`. It writes new candidate rows to `ips_append.xlsx`, which can then be copied into the `ips` sheet manually.
- Lines starting with `#` are treated as comments and skipped during import when editing the CSVs directly.

## Schema

| Column          | Description                                                                                                                            |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `source`        | Proposal that holds the relation, in `graph_key` format (e.g. `bips:32`, `slips:44`).                                                  |
| `target`        | Proposal being related to (`graph_key` format).                                                                                        |
| `relation_type` | One of `depends_on`, `references`, `supersedes`, `superseded_by` — see [vocabulary](#relation-type-vocabulary).                        |
| `confidence`    | One of `low`, `medium`, `high`.                                                                                                        |
| `evidence`      | Short anchor backing the claim — URL fragment, section name, or direct quote. **Wrap in quotes if it contains commas.**                |
| `note`          | Optional free-text rationale. **Wrap in quotes if it contains commas.**                                                                |
| `reviewer`      | Reviewer initials or handle.                                                                                                           |
| `reviewed_at`   | ISO date of review (`YYYY-MM-DD`). Snapshot context can be triangulated from this against the latest snapshot at review time.          |

## Relation-type vocabulary

| Value         | Meaning                                                                          |
| ------------- | -------------------------------------------------------------------------------- |
| `depends_on`  | `source` is functionally dependent on `target` (cannot work without it).         |
| `references`  | `source` cites or mentions `target` without a functional dependency.             |
| `supersedes`  | `source` obsoletes or replaces `target`.                                         |
| `superseded_by` | `source` is marked as having a later successor `target`.                       |

## Confidence levels

| Value    | When to use                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------------ |
| `high`   | The curated `source -> target` relation is very clear and well supported. There is little ambiguity about the intended target or the relation claim. |
| `medium` | The relation is credible, but some interpretation is involved. The target match or the exact relation is not fully explicit. |
| `low`    | The relation is only weakly supported or somewhat ambiguous. The row records a plausible reading, but confidence in that specific link is limited. |

## Example

```csv
source,target,relation_type,confidence,evidence,note,reviewer,reviewed_at
bips:44,bips:32,depends_on,high,"Requires: 32 [...] based on an algorithm described in BIP-0032","Dependency noted in BIP44 preamble.",rbo,2026-06-22
bips:321,bips:21,supersedes,high,"This BIP is a modification and intended replacement of BIP 0021.",,rbo,2026-06-22
```
