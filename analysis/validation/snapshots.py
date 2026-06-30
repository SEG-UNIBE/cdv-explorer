from __future__ import annotations

import json
import re
from datetime import date
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping

from analysis.dependencies.constants import (
    BODY_EXTRACTED_LLM,
    BODY_EXTRACTED_REGEX,
    PREAMBLE_EXTRACTED,
)
from analysis.proposal_schema import LLM_RUN_STATUSES, LLM_RUN_STATUS_SUCCESS
from analysis.validation.ground_truth import (
    ground_truth_workbook_path,
    load_ground_truth_ips,
    load_ground_truth_curated_entries,
    validate_reviewed_ip_policy,
    validate_ground_truth_curated_entries,
    validate_reviewed_ip_entries,
)
from analysis.reference_ids import normalize_reference_id_for_config
from analysis.utils import parse_date_ymd
from ecosystems import ECOSYSTEM_REGISTRY
from pipeline.source_context import SourceContext


ANALYSIS_REQUIRED_FILES: dict[str, list[str]] = {
    "dependencies/network_data.json": ["nodes", "dependency_edges"],
    "dependencies/dependency_metrics.json": ["by_approach", "pairwise_comparisons"],
    "authorship/authorship_payload.json": [
        "meta",
        "top_authors",
        "bips_per_year",
        "top_10_share",
    ],
    "classification/classification_payload.json": [
        "meta",
        "sankey_grouped",
        "status_over_time",
    ],
    "evolution/evolution_payload.json": [
        "meta",
        "status_evolution",
        "proposal_timelines",
    ],
    "conformity/conformity_metrics.json": ["per_proposal"],
}

ANALYSIS_COLUMN_LABELS: dict[str, str] = {
    "dependencies/network_data.json": "network",
    "dependencies/dependency_metrics.json": "dep_metrics",
    "authorship/authorship_payload.json": "authorship",
    "classification/classification_payload.json": "classification",
    "evolution/evolution_payload.json": "evolution",
    "conformity/conformity_metrics.json": "conformity",
}

REACT_GENERATED_INDEXES = (
    "ecosystems.json",
    "snapshotIndex.json",
    "proposalLinkIndex.json",
)

TARGET_RE = re.compile(r"^(?P<source>[A-Za-z0-9_-]+):(?P<id>[^:\s]+)$")
SNAPSHOT_LABEL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class SnapshotValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    file_status: dict[str, str] = field(default_factory=dict)

    def fail(self, message: str) -> None:
        self.ok = False
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def merge(self, other: "SnapshotValidationResult") -> None:
        self.ok = self.ok and other.ok
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.stats.update(other.stats)
        self.file_status.update(other.file_status)


def _load_json_file(
    path: Path, result: SnapshotValidationResult, rel_path: str
) -> Any | None:
    if not path.exists():
        result.fail(f"`{rel_path}` is missing")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.fail(f"`{rel_path}` is not valid JSON: {exc}")
        return None


def _known_source_configs(
    ecosystem_slug: str,
    source_slug: str,
    source_config: Mapping[str, Any],
    ecosystem_config: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    sources = (ecosystem_config or {}).get("sources", {})
    if isinstance(sources, Mapping) and sources:
        return {
            str(slug): config
            for slug, config in sources.items()
            if isinstance(config, Mapping)
        }
    return {source_slug: source_config}


def _ground_truth_source_configs(
    ecosystem_slug: str,
    ecosystem_config: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    config = ecosystem_config or ECOSYSTEM_REGISTRY.get(ecosystem_slug) or {}
    sources = config.get("sources", {}) if isinstance(config, Mapping) else {}
    return {
        str(source_slug): {
            "source_slug": str(source_slug),
            "proposal_label": source_config.get("proposal_acronym") or "IP",
            "reference_pattern": source_config.get("reference_pattern") or "",
            "max_proposal_id": source_config.get("max_proposal_id"),
        }
        for source_slug, source_config in sources.items()
        if isinstance(source_config, Mapping)
    }


def _normalize_iso_date(text: Any) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def _latest_source_proposal_metadata(
    ecosystem_slug: str,
    ecosystem_config: Mapping[str, Any] | None,
) -> dict[str, dict[str, str]]:
    config = ecosystem_config or ECOSYSTEM_REGISTRY.get(ecosystem_slug) or {}
    sources = config.get("sources", {}) if isinstance(config, Mapping) else {}
    proposal_metadata: dict[str, dict[str, str]] = {}

    for source_slug, source_config in sources.items():
        if not isinstance(source_config, Mapping):
            continue
        preprocess_root = Path(str(source_config.get("preprocess", "")))
        id_field = str(source_config.get("primary_id_field") or "").strip()
        snapshots = _snapshot_labels(preprocess_root)
        if not snapshots:
            continue
        preprocess_dir = preprocess_root / snapshots[0]
        if not preprocess_dir.is_dir() or not id_field:
            continue
        for json_path in sorted(preprocess_dir.glob("*.json")):
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, Mapping):
                continue
            preamble = payload.get("raw", {}).get("preamble", {})
            if not isinstance(preamble, Mapping):
                continue
            proposal_id = str(preamble.get(id_field) or "").strip()
            if not proposal_id:
                continue
            graph_key = f"{source_slug}:{proposal_id}"
            last_commit = parse_date_ymd(
                str(payload.get("meta", {}).get("last_commit") or "").strip()
            )
            proposal_metadata[graph_key] = {
                "created": str(preamble.get("created") or "").strip(),
                "title": str(preamble.get("title") or "").strip(),
                "last_commit": last_commit or "",
            }
    return proposal_metadata


def _validate_ground_truth_dataset_consistency(
    curated_entries: list[Mapping[str, Any]],
    reviewed_entries: list[Mapping[str, Any]],
    *,
    proposal_metadata: Mapping[str, Mapping[str, str]],
) -> list[str]:
    errors: list[str] = []
    reviewed_by_ip = {
        str(entry.get("ip") or "").strip(): entry
        for entry in reviewed_entries
        if isinstance(entry, Mapping) and str(entry.get("ip") or "").strip()
    }

    for index, entry in enumerate(curated_entries):
        row_label = (
            f"row {entry.get('__line__')}"
            if isinstance(entry, Mapping) and entry.get("__line__")
            else f"row {index + 2}"
        )
        source = str(entry.get("source") or "").strip()
        target = str(entry.get("target") or "").strip()
        if not source or not target:
            continue

        reviewed_source = reviewed_by_ip.get(source)
        if reviewed_source is None:
            errors.append(
                f"{row_label}: curated source `{source}` must also appear in `ips.csv`"
            )
            continue

        source_reviewed_at = _normalize_iso_date(reviewed_source.get("reviewed_at"))
        edge_reviewed_at = _normalize_iso_date(entry.get("reviewed_at"))
        if (
            source_reviewed_at
            and edge_reviewed_at
            and source_reviewed_at < edge_reviewed_at
        ):
            errors.append(
                f"{row_label}: `ips.csv` reviewed_at for `{source}` ({source_reviewed_at}) "
                f"must be on or after the curated edge reviewed_at ({edge_reviewed_at})"
            )

        source_last_commit = _normalize_iso_date(
            proposal_metadata.get(source, {}).get("last_commit")
        )
        target_created = _normalize_iso_date(
            reviewed_by_ip.get(target, {}).get("created")
            or proposal_metadata.get(target, {}).get("created")
        )
        if (
            source_last_commit
            and target_created
            and target_created > source_last_commit
        ):
            errors.append(
                f"{row_label}: target `{target}` was created on {target_created}, which is newer than "
                f"the latest known commit date of source `{source}` ({source_last_commit})"
            )

    return errors


def _snapshot_labels(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(
        [
            path.name
            for path in root.iterdir()
            if path.is_dir() and SNAPSHOT_LABEL_RE.match(path.name)
        ],
        reverse=True,
    )


def combined_source_key(source_slugs: list[str] | tuple[str, ...]) -> str:
    return "+".join(sorted(str(source_slug) for source_slug in source_slugs))


def expected_combined_snapshot_targets(
    ecosystem_slug: str,
    ecosystem_config: Mapping[str, Any] | None = None,
) -> list[tuple[str, str]]:
    config = ecosystem_config or ECOSYSTEM_REGISTRY.get(ecosystem_slug) or {}
    sources = config.get("sources", {}) if isinstance(config, Mapping) else {}
    source_configs = {
        str(source_slug): source_config
        for source_slug, source_config in sources.items()
        if isinstance(source_config, Mapping)
    }
    source_slugs = sorted(source_configs)
    if len(source_slugs) < 2:
        return []

    snapshot_sets = {
        source_slug: set(_snapshot_labels(Path(str(source_config.get("analysis", "")))))
        for source_slug, source_config in source_configs.items()
    }

    targets: list[tuple[str, str]] = []
    for size in range(2, len(source_slugs) + 1):
        for combo in combinations(source_slugs, size):
            common_snapshots = set.intersection(
                *(snapshot_sets[source_slug] for source_slug in combo)
            )
            for snapshot in sorted(common_snapshots, reverse=True):
                targets.append((combined_source_key(combo), snapshot))

    return targets


def _target_error(
    target: Any,
    *,
    source_configs: Mapping[str, Mapping[str, Any]],
    active_source_slug: str,
) -> str | None:
    if not isinstance(target, str) or not target.strip():
        return "target must be a non-empty source_slug:id string"

    match = TARGET_RE.match(target.strip())
    if not match:
        return f"target `{target}` must use source_slug:id format"

    target_source = match.group("source")
    target_id = match.group("id")
    target_config = source_configs.get(target_source)
    if target_config is None:
        known = ", ".join(sorted(source_configs)) or active_source_slug
        return f"target `{target}` uses unknown source slug `{target_source}`; known sources: {known}"

    normalized = normalize_reference_id_for_config(
        target_id,
        {
            "source_slug": target_source,
            "proposal_label": target_config.get("proposal_acronym") or "IP",
            "reference_pattern": target_config.get("reference_pattern") or "",
            "max_proposal_id": target_config.get("max_proposal_id"),
        },
    )
    if normalized is None:
        return (
            f"target `{target}` has an invalid proposal id for source `{target_source}`"
        )

    return None


def _validate_target_entry(
    entry: Any,
    *,
    path: str,
    result: SnapshotValidationResult,
    source_configs: Mapping[str, Mapping[str, Any]],
    active_source_slug: str,
    require_count: bool = False,
) -> None:
    if not isinstance(entry, Mapping):
        result.fail(f"{path} must be an object")
        return

    if "target" not in entry:
        result.fail(f"{path} missing `target`")
        return

    target_error = _target_error(
        entry.get("target"),
        source_configs=source_configs,
        active_source_slug=active_source_slug,
    )
    if target_error:
        result.fail(f"{path}: {target_error}")

    if require_count:
        count = entry.get("count")
        if not isinstance(count, int) or count < 1:
            result.fail(f"{path} missing positive integer `count`")


def _validate_preamble_interrelations(
    value: Any,
    *,
    result: SnapshotValidationResult,
    proposal_path: str,
    context: SourceContext,
    source_configs: Mapping[str, Mapping[str, Any]],
) -> None:
    if not isinstance(value, list):
        result.fail(f"{proposal_path}.{PREAMBLE_EXTRACTED} must be a list")
        return

    allowed_types = set(context.preamble_interrelation_types)
    for index, entry in enumerate(value):
        path = f"{proposal_path}.{PREAMBLE_EXTRACTED}[{index}]"
        _validate_target_entry(
            entry,
            path=path,
            result=result,
            source_configs=source_configs,
            active_source_slug=str(context.source_slug or ""),
        )
        if not isinstance(entry, Mapping):
            continue
        relation_type = entry.get("type")
        if not isinstance(relation_type, str) or not relation_type.strip():
            result.fail(f"{path} missing `type`")
        elif relation_type not in allowed_types:
            allowed = ", ".join(sorted(allowed_types)) or "none configured"
            result.fail(
                f"{path} has unknown relation type `{relation_type}`; allowed: {allowed}"
            )


def _validate_regex_interrelations(
    value: Any,
    *,
    result: SnapshotValidationResult,
    proposal_path: str,
    context: SourceContext,
    source_configs: Mapping[str, Mapping[str, Any]],
) -> None:
    if not isinstance(value, list):
        result.fail(f"{proposal_path}.{BODY_EXTRACTED_REGEX} must be a list")
        return

    for index, entry in enumerate(value):
        _validate_target_entry(
            entry,
            path=f"{proposal_path}.{BODY_EXTRACTED_REGEX}[{index}]",
            result=result,
            source_configs=source_configs,
            active_source_slug=str(context.source_slug or ""),
            require_count=True,
        )


def _validate_llm_interrelations(
    value: Any,
    *,
    result: SnapshotValidationResult,
    proposal_path: str,
    context: SourceContext,
    source_configs: Mapping[str, Mapping[str, Any]],
) -> None:
    if not isinstance(value, list):
        result.fail(f"{proposal_path}.{BODY_EXTRACTED_LLM} must be a list")
        return

    for run_index, run in enumerate(value):
        run_path = f"{proposal_path}.{BODY_EXTRACTED_LLM}[{run_index}]"
        if not isinstance(run, Mapping):
            result.fail(f"{run_path} must be an LLM run object")
            continue
        if not str(run.get("run_id") or "").strip():
            result.fail(f"{run_path} missing non-empty `run_id`")
        if not str(run.get("model") or "").strip():
            result.fail(f"{run_path} missing non-empty `model`")
        if not str(run.get("timestamp") or "").strip():
            result.fail(f"{run_path} missing non-empty `timestamp`")
        status = str(run.get("status") or "").strip().lower()
        if not status:
            result.fail(f"{run_path} missing non-empty `status`")
        elif status not in LLM_RUN_STATUSES:
            allowed = ", ".join(sorted(LLM_RUN_STATUSES))
            result.fail(
                f"{run_path} has invalid `status` `{status}`; allowed: {allowed}"
            )
        dependencies = run.get("dependencies")
        if not isinstance(dependencies, list):
            result.fail(f"{run_path}.dependencies must be a list")
            continue
        if status and status != LLM_RUN_STATUS_SUCCESS and dependencies:
            result.fail(
                f"{run_path}.dependencies must be empty when status is `{status}`"
            )
        if status and status != LLM_RUN_STATUS_SUCCESS:
            if not str(run.get("error_message") or "").strip():
                result.fail(
                    f"{run_path} missing non-empty `error_message` for failed run"
                )
        for dep_index, dependency in enumerate(dependencies):
            _validate_target_entry(
                dependency,
                path=f"{run_path}.dependencies[{dep_index}]",
                result=result,
                source_configs=source_configs,
                active_source_slug=str(context.source_slug or ""),
            )


def validate_preprocess_snapshot(
    preprocess_dir: Path,
    *,
    ecosystem_slug: str,
    source_slug: str,
    source_config: Mapping[str, Any],
    ecosystem_config: Mapping[str, Any] | None = None,
) -> SnapshotValidationResult:
    result = SnapshotValidationResult()
    if not preprocess_dir.is_dir():
        result.file_status["preprocess"] = "❌ missing"
        result.fail(f"`{preprocess_dir}` is missing")
        return result

    json_files = sorted(preprocess_dir.glob("*.json"))
    if not json_files:
        result.file_status["preprocess"] = "❌ empty"
        result.fail(f"`{preprocess_dir}` contains no proposal JSON files")
        return result

    context = SourceContext.from_config(
        source_config, ecosystem_slug=ecosystem_slug, source_slug=source_slug
    )
    source_configs = _known_source_configs(
        ecosystem_slug, source_slug, source_config, ecosystem_config
    )
    result.stats["proposal_json"] = len(json_files)

    for file_path in json_files:
        rel_name = str(file_path)
        proposal = _load_json_file(file_path, result, rel_name)
        if proposal is None:
            continue
        if not isinstance(proposal, Mapping):
            result.fail(f"`{rel_name}` must contain a JSON object")
            continue

        interrelations = (
            proposal.get("insights", {})
            if isinstance(proposal.get("insights"), Mapping)
            else {}
        ).get("interrelations")
        if not isinstance(interrelations, Mapping):
            result.fail(f"`{rel_name}` missing `insights.interrelations` object")
            continue

        proposal_path = f"`{rel_name}`.insights.interrelations"
        _validate_preamble_interrelations(
            interrelations.get(PREAMBLE_EXTRACTED),
            result=result,
            proposal_path=proposal_path,
            context=context,
            source_configs=source_configs,
        )
        _validate_regex_interrelations(
            interrelations.get(BODY_EXTRACTED_REGEX),
            result=result,
            proposal_path=proposal_path,
            context=context,
            source_configs=source_configs,
        )
        _validate_llm_interrelations(
            interrelations.get(BODY_EXTRACTED_LLM),
            result=result,
            proposal_path=proposal_path,
            context=context,
            source_configs=source_configs,
        )

    if result.ok:
        result.file_status["preprocess"] = "✅"
    elif "preprocess" not in result.file_status:
        result.file_status["preprocess"] = "❌ schema"
    return result


def validate_analysis_snapshot(snapshot_dir: Path) -> SnapshotValidationResult:
    result = SnapshotValidationResult()

    for rel_path, required_keys in ANALYSIS_REQUIRED_FILES.items():
        label = ANALYSIS_COLUMN_LABELS[rel_path]
        file_path = snapshot_dir / rel_path

        if not file_path.exists():
            result.file_status[label] = "❌ missing"
            result.fail(f"`{rel_path}` is missing")
            continue

        data = _load_json_file(file_path, result, rel_path)
        if data is None:
            result.file_status[label] = "❌ bad JSON"
            continue
        if not isinstance(data, Mapping):
            result.file_status[label] = "❌ shape"
            result.fail(f"`{rel_path}` must contain a JSON object")
            continue

        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            result.file_status[label] = "❌ keys"
            result.fail(f"`{rel_path}` missing top-level keys: {missing_keys}")
            continue

        result.file_status[label] = "✅"

        if rel_path == "dependencies/network_data.json":
            result.stats["proposals"] = len(data.get("nodes", []))
            result.stats["llm"] = sum(
                1
                for edge in data.get("dependency_edges", [])
                if isinstance(edge, Mapping)
                and edge.get("extraction_method") == BODY_EXTRACTED_LLM
            )

    return result


def validate_ground_truth_curated_file(
    ecosystem_slug: str,
    ecosystem_config: Mapping[str, Any] | None = None,
) -> SnapshotValidationResult:
    result = SnapshotValidationResult()
    csv_path = Path("ip_data") / ecosystem_slug / "ground_truth" / "interrelations.csv"
    if (
        not csv_path.exists()
        and not ground_truth_workbook_path(ecosystem_slug).exists()
    ):
        result.file_status["ground_truth"] = "—"
        return result

    try:
        entries = load_ground_truth_curated_entries(ecosystem_slug, strict=False)
    except ValueError as exc:
        result.file_status["ground_truth"] = "❌ bad CSV"
        result.fail(str(exc))
        return result

    errors = validate_ground_truth_curated_entries(
        entries,
        source_configs_by_slug=_ground_truth_source_configs(
            ecosystem_slug, ecosystem_config
        ),
    )
    if errors:
        result.file_status["ground_truth"] = "❌ schema"
        for error in errors:
            result.fail(f"`{csv_path}` {error}")
        return result

    reviewed_entries = load_ground_truth_ips(ecosystem_slug, strict=False)
    consistency_errors = _validate_ground_truth_dataset_consistency(
        entries,
        reviewed_entries,
        proposal_metadata=_latest_source_proposal_metadata(
            ecosystem_slug, ecosystem_config
        ),
    )
    if consistency_errors:
        result.file_status["ground_truth"] = "❌ consistency"
        for error in consistency_errors:
            result.fail(f"`{csv_path}` {error}")
        return result

    result.stats["ground_truth_edges"] = len(entries)
    result.file_status["ground_truth"] = "✅"
    return result


def validate_ground_truth_ips_file(
    ecosystem_slug: str,
    ecosystem_config: Mapping[str, Any] | None = None,
) -> SnapshotValidationResult:
    result = SnapshotValidationResult()
    csv_path = Path("ip_data") / ecosystem_slug / "ground_truth" / "ips.csv"
    if (
        not csv_path.exists()
        and not ground_truth_workbook_path(ecosystem_slug).exists()
    ):
        result.file_status["reviewed_ips"] = "⚠️ missing"
        return result

    try:
        entries = load_ground_truth_ips(ecosystem_slug, strict=False)
    except ValueError as exc:
        result.file_status["reviewed_ips"] = "❌ bad CSV"
        result.fail(str(exc))
        return result

    errors = validate_reviewed_ip_entries(
        entries,
        source_configs_by_slug=_ground_truth_source_configs(
            ecosystem_slug, ecosystem_config
        ),
    )
    if errors:
        result.file_status["reviewed_ips"] = "❌ schema"
        for error in errors:
            result.fail(f"`{csv_path}` {error}")
        return result

    result.stats["reviewed_ips"] = len(entries)
    result.stats["completed_reviewed_ips"] = sum(
        1
        for entry in entries
        if isinstance(entry, Mapping) and str(entry.get("reviewed_at") or "").strip()
    )
    policy_warnings = validate_reviewed_ip_policy(
        entries, ecosystem_slug=ecosystem_slug
    )
    if policy_warnings:
        result.file_status["reviewed_ips"] = "⚠️ policy"
        for warning in policy_warnings:
            result.warn(f"`{csv_path}` {warning}")
        result.stats["reviewed_ip_policy_warnings"] = len(policy_warnings)
    else:
        result.file_status["reviewed_ips"] = "✅"
    return result


def validate_react_snapshot_exports(react_dir: Path) -> SnapshotValidationResult:
    result = SnapshotValidationResult()
    index_path = react_dir / "dataset_index.json"
    index = _load_json_file(index_path, result, str(index_path))
    if index is None:
        result.file_status["react"] = "❌ missing"
        return result
    if not isinstance(index, Mapping):
        result.file_status["react"] = "❌ shape"
        result.fail(f"`{index_path}` must contain a JSON object")
        return result

    files = index.get("files")
    if not isinstance(files, Mapping) or not files:
        result.file_status["react"] = "❌ index"
        result.fail(f"`{index_path}` missing non-empty `files` object")
        return result

    missing = [
        str(react_dir / str(filename))
        for filename in files.values()
        if not (react_dir / str(filename)).exists()
    ]
    if missing:
        result.file_status["react"] = "❌ files"
        result.fail(f"`{index_path}` references missing files: {', '.join(missing)}")
        return result

    result.file_status["react"] = "✅"
    return result


def validate_source_snapshot(
    *,
    ecosystem_slug: str,
    source_slug: str,
    source_config: Mapping[str, Any],
    ecosystem_config: Mapping[str, Any] | None,
    snapshot: str,
) -> SnapshotValidationResult:
    result = SnapshotValidationResult()
    result.merge(validate_ground_truth_curated_file(ecosystem_slug, ecosystem_config))
    result.merge(validate_ground_truth_ips_file(ecosystem_slug, ecosystem_config))
    result.merge(
        validate_preprocess_snapshot(
            Path(str(source_config["preprocess"])) / snapshot,
            ecosystem_slug=ecosystem_slug,
            source_slug=source_slug,
            source_config=source_config,
            ecosystem_config=ecosystem_config,
        )
    )
    result.merge(
        validate_analysis_snapshot(Path(str(source_config["analysis"])) / snapshot)
    )
    result.merge(
        validate_react_snapshot_exports(
            Path(str(source_config["postprocess"])) / snapshot / "react"
        )
    )
    return result


def validate_combined_snapshot(
    *, ecosystem_slug: str, combo_key: str, snapshot: str
) -> SnapshotValidationResult:
    combo_root = Path("ip_data") / ecosystem_slug / "_combined" / combo_key
    result = SnapshotValidationResult()
    result.merge(validate_ground_truth_curated_file(ecosystem_slug))
    result.merge(validate_ground_truth_ips_file(ecosystem_slug))
    result.merge(validate_analysis_snapshot(combo_root / "03_analysis" / snapshot))
    result.merge(
        validate_react_snapshot_exports(
            combo_root / "04_postprocess" / snapshot / "react"
        )
    )
    return result


def validate_react_generated_indexes(
    generated_dir: Path = Path("react/src/generated"),
) -> SnapshotValidationResult:
    result = SnapshotValidationResult()
    missing: list[str] = []
    invalid: list[str] = []

    for filename in REACT_GENERATED_INDEXES:
        file_path = generated_dir / filename
        if not file_path.exists():
            missing.append(str(file_path))
            continue
        try:
            json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            invalid.append(f"{file_path}: {exc}")

    if missing:
        result.fail(f"Missing generated React indexes: {', '.join(missing)}")
    if invalid:
        result.fail(f"Generated React indexes with invalid JSON: {'; '.join(invalid)}")

    result.file_status["react_generated"] = "✅" if result.ok else "❌"
    return result
