# Ground-Truth Interrelations — Bitcoin

Manually curated interrelation edges for the Bitcoin ecosystem (BIPs + SLIPs).
Used as the canonical reference against which `llm`, `preamble`, and `regex` extraction methods are evaluated.

## File layout

- Editable workbook: [`ground_truth.xlsx`](./ground_truth.xlsx) with two sheets: `ips` and `interrelations`.
- Generated reviewed source-IP scope: [`ips.csv`](./ips.csv).
- Generated curated edges: [`interrelations.csv`](./interrelations.csv).
- Inter-source edges (e.g. `bips:N → slips:M`) live in the same file.
- The CSV files remain pipeline inputs for validation and artifact generation, but they are regenerated from the workbook whenever ground-truth data is loaded.
- Lines starting with `#` are treated as comments and skipped during import when editing the CSVs directly.

## Schema

| Column          | Description                                                                                                                            |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `source`        | Proposal that holds the relation, in `graph_key` format (e.g. `bips:32`, `slips:44`).                                                  |
| `target`        | Proposal being related to (`graph_key` format).                                                                                        |
| `relation_type` | One of `depends_on`, `references`, `supersedes` — see [vocabulary](#relation-type-vocabulary).                                         |
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

## Confidence levels

| Value    | When to use                                                                                          |
| -------- | ---------------------------------------------------------------------------------------------------- |
| `high`   | Declared in the source's preamble (e.g. `Requires:`, `Replaces:`) or unambiguous body statement.     |
| `medium` | Strong body-text evidence but not declared in the preamble, or some interpretation involved.         |
| `low`    | Plausible but circumstantial — worth recording for follow-up review.                                 |

## Example

```csv
source,target,relation_type,confidence,evidence,note,reviewer,reviewed_at
bips:44,bips:32,depends_on,high,"Requires: 32 [...] based on an algorithm described in BIP-0032","Dependency noted in BIP44 preamble.",rbo,2026-06-22
bips:321,bips:21,supersedes,high,"This BIP is a modification and intended replacement of BIP 0021.",,rbo,2026-06-22
```
