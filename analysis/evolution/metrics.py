from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Mapping

from analysis.classification.preprocess import normalize_classification_fields
from analysis.proposal_schema import get_changes_in_status
from analysis.evolution.mining import extract_status_timeline
from pipeline.source_context import SourceContext


def _normalize_status(status: Any, source_context: SourceContext) -> str:
    text = str(status or "").strip()
    if not text:
        return ""
    normalized = normalize_classification_fields(
        {"status": text}, source_context=source_context
    )
    return str(normalized.get("status") or "").strip()


def _parse_event_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None

    candidate = text[:10]
    try:
        return date.fromisoformat(candidate)
    except ValueError:
        return None


def _normalize_proposal_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.isdigit():
        return str(int(text))
    return text


def _regime_entries(source_context: SourceContext) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for index, raw_entry in enumerate(
        source_context.classification_config.get("regimes", [])
    ):
        if not isinstance(raw_entry, Mapping):
            continue

        standard = str(raw_entry.get("standard") or "").strip()
        if not standard:
            continue

        status_order = [
            str(status).strip()
            for status in raw_entry.get("status_order", [])
            if str(status).strip()
        ]
        label = str(raw_entry.get("label") or "").strip() or standard.upper()
        milestone_label = str(raw_entry.get("milestone_label") or "").strip()
        status_aliases: Dict[str, str] = {}
        for mapping in raw_entry.get("status_aliases") or []:
            if not isinstance(mapping, Mapping):
                continue
            source_status = str(mapping.get("from") or "").strip()
            target_status = str(mapping.get("to") or "").strip()
            if not source_status or not target_status:
                continue
            status_aliases[source_status] = target_status

        transition_status_map: Dict[str, str] = {}
        for mapping in raw_entry.get("transition_status_map") or []:
            if not isinstance(mapping, Mapping):
                continue
            source_status = str(mapping.get("from") or "").strip()
            target_status = str(mapping.get("to") or "").strip()
            if not source_status or not target_status:
                continue
            transition_status_map[source_status] = target_status

        entries.append(
            {
                "index": index,
                "standard": standard,
                "label": label,
                "milestone_label": milestone_label,
                "status_order": status_order,
                "status_aliases": status_aliases,
                "transition_status_map": transition_status_map,
                "valid_from": _parse_event_date(raw_entry.get("valid_from")),
                "valid_until": _parse_event_date(raw_entry.get("valid_until")),
            }
        )

    return entries


def _regime_order(source_context: SourceContext) -> List[str]:
    return [entry["standard"] for entry in _regime_entries(source_context)]


def _regime_label_by_standard(source_context: SourceContext) -> Dict[str, str]:
    return {
        entry["standard"]: entry["label"] for entry in _regime_entries(source_context)
    }


def _status_order_by_standard(source_context: SourceContext) -> Dict[str, List[str]]:
    return {
        entry["standard"]: list(entry["status_order"])
        for entry in _regime_entries(source_context)
    }


def _is_official_status_for_standard(
    status: str,
    standard: str,
    source_context: SourceContext,
) -> bool:
    return status in set(_status_order_by_standard(source_context).get(standard, []))


def _regime_entry_by_standard(
    source_context: SourceContext,
) -> Dict[str, Dict[str, Any]]:
    return {entry["standard"]: entry for entry in _regime_entries(source_context)}


def _build_unique_status_to_standard(source_context: SourceContext) -> Dict[str, str]:
    standards_by_status: Dict[str, set[str]] = defaultdict(set)
    for entry in _regime_entries(source_context):
        for status in entry["status_order"]:
            standards_by_status[status].add(entry["standard"])
    return {
        status: next(iter(standards))
        for status, standards in standards_by_status.items()
        if len(standards) == 1
    }


def _map_status_for_standard(
    status: str,
    target_standard: str,
    source_context: SourceContext,
) -> str:
    regime_entry = _regime_entry_by_standard(source_context).get(target_standard) or {}
    alias_map = regime_entry.get("status_aliases") or {}
    if status in alias_map:
        return str(alias_map[status]).strip()

    transition_map = regime_entry.get("transition_status_map") or {}
    if status in transition_map:
        return str(transition_map[status]).strip()

    valid_statuses = set(regime_entry.get("status_order") or [])
    if status in valid_statuses:
        return status

    return status


def _build_synthetic_regime_transition_event(
    prior_event: Dict[str, Any],
    milestone: Dict[str, Any],
    source_context: SourceContext,
) -> Dict[str, Any] | None:
    target_standard = str(milestone.get("standard") or "").strip()
    if not target_standard:
        return None

    previous_status = str(prior_event.get("status") or "").strip()
    if not previous_status:
        return None

    next_status = _map_status_for_standard(
        previous_status, target_standard, source_context
    )
    if not next_status:
        return None

    transition_date = milestone["date"]
    previous_standard = str(prior_event.get("standard") or "").strip()
    if previous_standard == target_standard and previous_status == next_status:
        return None

    return {
        "proposal_id": prior_event["proposal_id"],
        "date": transition_date,
        "status": next_status,
        "standard": target_standard,
        "commit": "",
        "timestamp": f"{transition_date.isoformat()}T00:00:00Z",
        "author": "",
        "path": "",
        "synthetic": True,
        "transition_label": str(milestone.get("label") or "").strip(),
        "previous_standard": previous_standard,
    }


def _inject_regime_transition_events(
    timeline: List[Dict[str, Any]],
    source_context: SourceContext,
    *,
    anchor_event: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    if not timeline:
        return timeline

    augmented = list(timeline)
    working_timeline = list(timeline)
    if (
        anchor_event is not None
        and anchor_event.get("date") is not None
        and anchor_event["date"] < timeline[0]["date"]
    ):
        working_timeline = [{**anchor_event, "_anchor": True}, *working_timeline]
    milestones = _resolve_regime_milestones(source_context)

    for milestone in milestones:
        activation_date = milestone["date"]
        if any(event["date"] == activation_date for event in working_timeline):
            continue

        prior_index = -1
        for index, event in enumerate(working_timeline):
            if event["date"] < activation_date:
                prior_index = index
                continue
            break

        if prior_index < 0:
            continue

        synthetic_event = _build_synthetic_regime_transition_event(
            working_timeline[prior_index],
            milestone,
            source_context,
        )
        if synthetic_event is None:
            continue

        insert_at = prior_index + 1
        working_timeline.insert(insert_at, synthetic_event)

        visible_insert_at = sum(
            1 for event in working_timeline[:insert_at] if not event.get("_anchor")
        )
        augmented.insert(visible_insert_at, synthetic_event)

    return augmented


def _fallback_timeline(
    proposal: Dict[str, Any],
    id_field: str,
    source_context: SourceContext,
) -> List[Dict[str, Any]]:
    preamble = proposal.get("raw", {}).get("preamble", {})
    proposal_id = _normalize_proposal_id(preamble.get(id_field))
    status = _normalize_status(preamble.get("status"), source_context)
    created_date = _parse_event_date(preamble.get("created"))

    if not proposal_id or not status or created_date is None:
        return []

    standard = _resolve_event_standard(None, created_date, status, source_context)
    if standard:
        status = _map_status_for_standard(status, standard, source_context)

    return [
        {
            "proposal_id": proposal_id,
            "date": created_date,
            "status": status,
            "standard": standard,
            "commit": "",
            "timestamp": created_date.isoformat(),
            "author": "",
            "path": "",
        }
    ]


def _find_proposal_file(
    repo_dir: Path, proposal_id: str, file_prefix: str
) -> Path | None:
    normalized_id = proposal_id.zfill(4) if proposal_id.isdigit() else proposal_id
    for extension in ("md", "mediawiki", "rst"):
        candidate = repo_dir / f"{file_prefix}-{normalized_id}.{extension}"
        if candidate.exists():
            return candidate
    return None


def _timeline_needs_path_rehydration(raw_timeline: Any) -> bool:
    if not isinstance(raw_timeline, list) or not raw_timeline:
        return False

    return any(
        isinstance(event, dict)
        and str(event.get("commit") or "").strip()
        and not str(event.get("path") or "").strip()
        for event in raw_timeline
    )


def _normalize_timeline_event(
    proposal_id: str,
    event: Dict[str, Any],
    source_context: SourceContext,
) -> Dict[str, Any] | None:
    event_date = _parse_event_date(event.get("date") or event.get("timestamp"))
    status = _normalize_status(event.get("status"), source_context)
    if event_date is None or not status or not proposal_id:
        return None

    standard = _resolve_event_standard(
        event.get("standard"),
        event_date,
        status,
        source_context,
    )
    if standard:
        status = _map_status_for_standard(status, standard, source_context)
    return {
        "proposal_id": proposal_id,
        "date": event_date,
        "status": status,
        "standard": standard,
        "commit": str(event.get("commit") or "").strip(),
        "timestamp": str(event.get("timestamp") or "").strip(),
        "author": str(event.get("author") or "").strip(),
        "path": str(event.get("path") or "").strip(),
    }


def _build_created_seed_event(
    proposal: Dict[str, Any],
    source_event: Dict[str, Any] | None,
    snapshot_date: date | None,
    source_context: SourceContext,
) -> Dict[str, Any] | None:
    if source_event is None:
        return None

    created_date = _parse_event_date(
        proposal.get("raw", {}).get("preamble", {}).get("created")
    )
    if created_date is None:
        return None
    if snapshot_date is not None and created_date > snapshot_date:
        return None
    if created_date >= source_event["date"]:
        return None

    status = str(source_event.get("status") or "").strip()
    proposal_id = str(source_event.get("proposal_id") or "").strip()
    if not status or not proposal_id:
        return None

    standard = _resolve_event_standard(None, created_date, status, source_context)
    if standard:
        status = _map_status_for_standard(status, standard, source_context)

    return {
        "proposal_id": proposal_id,
        "date": created_date,
        "status": status,
        "standard": standard,
        "commit": "",
        "timestamp": created_date.isoformat(),
        "author": "",
        "path": "",
    }


def _build_countable_timeline(
    proposal: Dict[str, Any],
    timeline: List[Dict[str, Any]],
    snapshot_date: date | None,
    source_context: SourceContext,
) -> List[Dict[str, Any]]:
    visible_timeline = [
        event
        for event in timeline
        if snapshot_date is None or event["date"] <= snapshot_date
    ]
    created_seed = _build_created_seed_event(
        proposal,
        timeline[0] if timeline else None,
        snapshot_date,
        source_context,
    )

    if created_seed is not None:
        return [created_seed, *visible_timeline]
    return visible_timeline


def _serialize_proposal_timeline(
    proposal: Dict[str, Any],
    timeline: List[Dict[str, Any]],
    snapshot_date: date | None,
    source_context: SourceContext,
) -> Dict[str, Any] | None:
    visible_timeline = [
        event
        for event in timeline
        if snapshot_date is None or event["date"] <= snapshot_date
    ]

    preamble = proposal.get("raw", {}).get("preamble", {})
    proposal_source = (
        visible_timeline[0] if visible_timeline else (timeline[0] if timeline else None)
    )
    if proposal_source is None:
        return None

    proposal_id = proposal_source["proposal_id"]
    created_date = _parse_event_date(preamble.get("created"))
    title = str(preamble.get("title") or "").strip()
    latest_visible_event = visible_timeline[-1] if visible_timeline else None

    creation_event = None
    if (
        created_date is not None
        and (snapshot_date is None or created_date <= snapshot_date)
        and timeline
    ):
        creation_source = timeline[0]
        creation_status = str(creation_source.get("status", "") or "").strip()
        creation_standard = _resolve_event_standard(
            None, created_date, creation_status, source_context
        )
        if creation_standard:
            creation_status = _map_status_for_standard(
                creation_status, creation_standard, source_context
            )
        creation_event = {
            "kind": "creation",
            "label": "Created",
            "date": created_date.isoformat(),
            "timestamp": creation_source.get("timestamp", ""),
            "status": creation_status,
            "standard": creation_standard,
            "commit": creation_source.get("commit", ""),
            "author": creation_source.get("author", ""),
            "path": creation_source.get("path", ""),
            "previous_status": "",
        }

    events: List[Dict[str, Any]] = []
    if creation_event is not None:
        events.append(creation_event)

    prior_status = creation_event["status"] if creation_event is not None else ""
    for index, event in enumerate(visible_timeline):
        if (
            index == 0
            and creation_event is not None
            and created_date is not None
            and event["date"] == created_date
            and event["status"] == creation_event["status"]
        ):
            prior_status = event["status"]
            continue

        previous_status = prior_status or (
            visible_timeline[index - 1]["status"] if index > 0 else ""
        )
        serialized_event = {
            "kind": "regime_transition" if event.get("synthetic") else "status_change",
            "label": event.get("transition_label") or event["status"],
            "date": event["date"].isoformat(),
            "timestamp": event.get("timestamp", ""),
            "status": event["status"],
            "standard": event["standard"],
            "commit": event.get("commit", ""),
            "author": event.get("author", ""),
            "path": event.get("path", ""),
            "previous_status": previous_status,
        }
        if event.get("synthetic"):
            serialized_event["synthetic"] = True
            serialized_event["previous_standard"] = str(
                event.get("previous_standard") or ""
            )
        events.append(serialized_event)
        prior_status = event["status"]

    if not events:
        return None

    current_status = (
        latest_visible_event["status"]
        if latest_visible_event is not None
        else creation_event["status"]
    )
    current_standard = (
        latest_visible_event["standard"]
        if latest_visible_event is not None
        else creation_event["standard"]
    )

    return {
        "proposal_id": proposal_id,
        "title": title,
        "created": created_date.isoformat() if created_date is not None else "",
        "current_status": current_status,
        "current_standard": current_standard,
        "event_count": len(events),
        "events": events,
    }


def _build_status_order(
    categories: List[str], source_context: SourceContext
) -> List[str]:
    configured_order: List[str] = []
    for entry in _regime_entries(source_context):
        for status in entry["status_order"]:
            if status not in configured_order:
                configured_order.append(status)

    remaining = sorted(
        category for category in categories if category not in configured_order
    )
    return [status for status in configured_order if status in categories] + remaining


def _resolve_regime_milestones(source_context: SourceContext) -> List[Dict[str, Any]]:
    milestones: List[Dict[str, Any]] = []
    for entry in _regime_entries(source_context):
        start_date = entry["valid_from"]
        if start_date is None:
            continue

        label = entry["milestone_label"] or f"{entry['label']} Activation"
        milestones.append(
            {
                "standard": entry["standard"],
                "standard_label": entry["label"],
                "date": start_date,
                "label": label,
            }
        )

    milestones.sort(key=lambda item: item["date"])
    return milestones


def _resolve_standard_from_date(
    event_date: date | None, source_context: SourceContext
) -> str | None:
    if event_date is None:
        return None

    for entry in _regime_entries(source_context):
        if entry["valid_from"] is not None and event_date < entry["valid_from"]:
            continue
        if entry["valid_until"] is not None and event_date > entry["valid_until"]:
            continue

        return entry["standard"]

    return None


def _resolve_event_standard(
    raw_standard: Any,
    event_date: date | None,
    status: str,
    source_context: SourceContext,
) -> str:
    by_date = _resolve_standard_from_date(event_date, source_context)
    if by_date:
        return by_date

    standard = str(raw_standard or "").strip()
    if standard:
        return standard

    unique_status_to_standard = _build_unique_status_to_standard(source_context)
    if status in unique_status_to_standard:
        return unique_status_to_standard[status]

    return ""


def _quarter_start(value: date) -> date:
    quarter_month = ((value.month - 1) // 3) * 3 + 1
    return date(value.year, quarter_month, 1)


def _next_quarter(value: date) -> date:
    if value.month == 10:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 3, 1)


def _quarter_end(value: date) -> date:
    if value.month == 1:
        return date(value.year, 3, 31)
    if value.month == 4:
        return date(value.year, 6, 30)
    if value.month == 7:
        return date(value.year, 9, 30)
    return date(value.year, 12, 31)


def _quarter_number(value: date) -> int:
    return ((value.month - 1) // 3) + 1


def _format_quarter_label(value: date) -> str:
    return f"{value.year}-Q{_quarter_number(value)}"


def _build_periods(
    start_date: date,
    end_date: date,
    *,
    milestones: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    periods: List[Dict[str, Any]] = []
    current = _quarter_start(start_date)
    final = _quarter_start(end_date)
    milestone_entries = list(milestones or [])

    while current <= final:
        quarter_end = _quarter_end(current)
        quarter_label = _format_quarter_label(current)
        quarter_milestone = next(
            (
                milestone
                for milestone in milestone_entries
                if current <= milestone["date"] <= quarter_end
            ),
            None,
        )

        if quarter_milestone is not None:
            breakpoint_date = quarter_milestone["date"]
            standard_key = (
                str(quarter_milestone.get("standard") or "").strip() or "milestone"
            )
            pre_breakpoint_end = breakpoint_date - timedelta(days=1)
            if current <= pre_breakpoint_end:
                periods.append(
                    {
                        "key": f"{quarter_label}-pre-{standard_key}",
                        "label": quarter_label,
                        "display_suffix": "a",
                        "start": current,
                        "end": pre_breakpoint_end,
                        "kind": "milestone",
                        "milestone_label": quarter_milestone["label"],
                    }
                )

            remainder_start = breakpoint_date
            if remainder_start <= quarter_end:
                periods.append(
                    {
                        "key": f"{quarter_label}-post-{standard_key}",
                        "label": quarter_label,
                        "display_suffix": "b",
                        "start": remainder_start,
                        "end": quarter_end,
                        "kind": "milestone_remainder",
                        "milestone_label": "",
                    }
                )
        else:
            periods.append(
                {
                    "key": quarter_label,
                    "label": quarter_label,
                    "display_suffix": "",
                    "start": current,
                    "end": quarter_end,
                    "kind": "quarter",
                    "milestone_label": "",
                }
            )

        current = _next_quarter(current)

    return periods


def _build_evolution_series(
    proposal_timelines: List[List[Dict[str, Any]]],
    periods: List[Dict[str, Any]],
    ordered_categories: List[str],
    source_context: SourceContext,
    *,
    standard_filter: str | None = None,
) -> Dict[str, Any]:
    counts_by_period = {period["key"]: Counter() for period in periods}
    bips_by_period = {period["key"]: defaultdict(set) for period in periods}

    for timeline in proposal_timelines:
        event_index = 0
        active_status = None
        active_standard = None
        proposal_id = timeline[0]["proposal_id"]

        for period in periods:
            period_end = period["end"]

            while (
                event_index < len(timeline)
                and timeline[event_index]["date"] <= period_end
            ):
                active_status = timeline[event_index]["status"]
                active_standard = timeline[event_index]["standard"]
                event_index += 1

            if not active_status:
                continue

            effective_standard = active_standard or _resolve_event_standard(
                None,
                period_end,
                active_status,
                source_context,
            )

            if standard_filter is not None and effective_standard != standard_filter:
                continue

            period_key = period["key"]
            counts_by_period[period_key][active_status] += 1
            bips_by_period[period_key][active_status].add(proposal_id)

    rows = []
    for period in periods:
        period_key = period["key"]
        period_label = period["label"]
        values = {
            status: counts_by_period[period_key].get(status, 0)
            for status in ordered_categories
        }
        bips = {
            status: sorted(
                bips_by_period[period_key].get(status, set()),
                key=lambda value: (
                    not value.isdigit(),
                    int(value) if value.isdigit() else value,
                ),
            )
            for status in ordered_categories
        }
        rows.append(
            {
                "period": period_label,
                "period_key": period_key,
                "period_display_suffix": period.get("display_suffix", ""),
                "period_start": period["start"].isoformat(),
                "period_end": period["end"].isoformat(),
                "period_kind": period["kind"],
                "milestone_label": period.get("milestone_label", ""),
                "values": values,
                "bips": bips,
            }
        )

    return {
        "categories": ordered_categories,
        "rows": rows,
    }


def _order_statuses_for_standard(
    statuses: List[str],
    standard: str,
    source_context: SourceContext,
) -> List[str]:
    primary_order = _status_order_by_standard(source_context).get(standard, [])
    remaining = sorted(status for status in statuses if status not in primary_order)
    return [status for status in primary_order if status in statuses] + remaining


def _build_segmented_evolution_series(
    series_by_standard: Dict[str, Dict[str, Any]],
    *,
    standard_order: List[str],
    standard_labels: Dict[str, str],
    source_context: SourceContext,
) -> Dict[str, Any]:
    segment_definitions: List[Dict[str, Any]] = []
    categories: List[str] = []
    ordered_standards = [
        standard for standard in standard_order if standard in series_by_standard
    ]
    ordered_standards.extend(
        standard for standard in series_by_standard if standard not in ordered_standards
    )

    for standard in ordered_standards:
        counter = Counter()
        for row in series_by_standard.get(standard, {}).get("rows", []):
            for status, value in (row.get("values") or {}).items():
                counter[status] += int(value or 0)

        ordered_statuses = _order_statuses_for_standard(
            [status for status, total in counter.items() if total > 0],
            standard,
            source_context,
        )
        for status in ordered_statuses:
            key = f"{standard}:{status}" if standard else status
            categories.append(key)
            segment_definitions.append(
                {
                    "key": key,
                    "status": status,
                    "standard": standard,
                    "standardLabel": standard_labels.get(
                        standard, standard.upper() if standard else ""
                    ),
                    "label": status,
                    "isOfficial": _is_official_status_for_standard(
                        status, standard, source_context
                    ),
                }
            )

    base_rows = []
    for standard in ordered_standards:
        candidate_rows = series_by_standard.get(standard, {}).get("rows") or []
        if candidate_rows:
            base_rows = candidate_rows
            break
    rows = []

    for index, base_row in enumerate(base_rows):
        values = {}
        bips = {}

        for segment in segment_definitions:
            standard = segment["standard"]
            status = segment["status"]
            source_rows = series_by_standard.get(standard, {}).get("rows", [])
            source_row = source_rows[index] if index < len(source_rows) else {}
            values[segment["key"]] = int(
                (source_row.get("values") or {}).get(status, 0) or 0
            )
            bips[segment["key"]] = list((source_row.get("bips") or {}).get(status, []))

        rows.append(
            {
                "period": base_row.get("period"),
                "period_key": base_row.get("period_key"),
                "period_display_suffix": base_row.get("period_display_suffix", ""),
                "period_start": base_row.get("period_start"),
                "period_end": base_row.get("period_end"),
                "period_kind": base_row.get("period_kind"),
                "milestone_label": base_row.get("milestone_label", ""),
                "values": values,
                "bips": bips,
            }
        )

    return {
        "categories": categories,
        "segmentDefinitions": segment_definitions,
        "rows": rows,
    }


def _empty_evolution_payload(source_context: SourceContext) -> Dict[str, Any]:
    standard_keys = _regime_order(source_context)
    return {
        "meta": {
            "proposal_count": 0,
            "timeline_count": 0,
            "first_year": None,
            "last_year": None,
            "first_period": None,
            "last_period": None,
            "milestones": [],
        },
        "status_evolution": {
            "categories": [],
            "rows": [],
        },
        "status_evolution_segmented": {
            "categories": [],
            "segmentDefinitions": [],
            "rows": [],
        },
        "status_evolution_by_standard": {
            standard: {"categories": [], "rows": []} for standard in standard_keys
        },
        "proposal_timelines": [],
    }


def prepare_evolution_payload(
    proposal_data: List[Dict[str, Any]],
    snapshot_label: str | None,
    id_field: str,
    *,
    repo_dir: Path | None = None,
    file_prefix: str = "bip",
    source_context: SourceContext | None = None,
) -> Dict[str, Any]:
    context = source_context or SourceContext.default()
    standard_order = _regime_order(context)
    standard_labels = _regime_label_by_standard(context)
    proposal_timelines: List[List[Dict[str, Any]]] = []
    serialized_timelines: List[Dict[str, Any]] = []
    category_set = set()
    observed_standard_set = set()
    min_date = None
    max_date = None
    snapshot_date = _parse_event_date(snapshot_label)

    for proposal in proposal_data:
        preamble = proposal.get("raw", {}).get("preamble", {})
        proposal_id = _normalize_proposal_id(preamble.get(id_field))
        raw_timeline = get_changes_in_status(proposal)

        if (
            proposal_id
            and repo_dir is not None
            and _timeline_needs_path_rehydration(raw_timeline)
        ):
            proposal_file_path = _find_proposal_file(repo_dir, proposal_id, file_prefix)
            if proposal_file_path is not None:
                raw_timeline = extract_status_timeline(
                    repo_dir, proposal_file_path, source_context=context
                )

        timeline = []
        for event in raw_timeline if isinstance(raw_timeline, list) else []:
            normalized_event = (
                _normalize_timeline_event(proposal_id, event, context)
                if isinstance(event, dict)
                else None
            )
            if normalized_event is not None:
                timeline.append(normalized_event)

        if not timeline:
            timeline = _fallback_timeline(
                proposal, id_field=id_field, source_context=context
            )

        if not timeline:
            continue

        timeline.sort(
            key=lambda entry: (entry["date"], str(entry.get("timestamp") or ""))
        )
        created_anchor = _build_created_seed_event(
            proposal,
            timeline[0] if timeline else None,
            None,
            context,
        )
        timeline = _inject_regime_transition_events(
            timeline,
            context,
            anchor_event=created_anchor,
        )
        countable_timeline = _build_countable_timeline(
            proposal,
            timeline,
            snapshot_date,
            context,
        )
        if countable_timeline:
            proposal_timelines.append(countable_timeline)
        serialized_timeline = _serialize_proposal_timeline(
            proposal,
            timeline,
            snapshot_date,
            context,
        )
        if serialized_timeline is not None:
            serialized_timelines.append(serialized_timeline)

        for event in countable_timeline:
            category_set.add(event["status"])
            observed_standard = str(event.get("standard") or "").strip()
            if observed_standard:
                observed_standard_set.add(observed_standard)
            event_date = event["date"]
            min_date = event_date if min_date is None else min(min_date, event_date)
            max_date = event_date if max_date is None else max(max_date, event_date)

    if snapshot_date is not None:
        max_date = snapshot_date if max_date is None else max(max_date, snapshot_date)

    if min_date is None or max_date is None:
        return _empty_evolution_payload(context)

    milestones = _resolve_regime_milestones(context)
    ordered_categories = _build_status_order(list(category_set), context)
    periods = _build_periods(min_date, max_date, milestones=milestones)
    first_period = periods[0]
    last_period = periods[-1]
    series_standard_keys = standard_order or sorted(observed_standard_set) or [""]
    ordered_categories_by_standard = {
        standard: _order_statuses_for_standard(list(category_set), standard, context)
        for standard in series_standard_keys
    }

    proposal_ids = {
        _normalize_proposal_id(
            proposal.get("raw", {}).get("preamble", {}).get(id_field)
        )
        for proposal in proposal_data
        if proposal.get("raw", {}).get("preamble", {}).get(id_field) is not None
    }

    status_evolution = _build_evolution_series(
        proposal_timelines,
        periods,
        ordered_categories,
        context,
    )
    status_evolution_by_standard = {
        standard: _build_evolution_series(
            proposal_timelines,
            periods,
            ordered_categories_by_standard[standard],
            context,
            standard_filter=standard,
        )
        for standard in series_standard_keys
    }
    serialized_timelines.sort(
        key=lambda entry: (
            not str(entry.get("proposal_id") or "").isdigit(),
            int(entry["proposal_id"])
            if str(entry.get("proposal_id") or "").isdigit()
            else str(entry.get("proposal_id") or ""),
        )
    )

    return {
        "meta": {
            "proposal_count": len(proposal_ids),
            "timeline_count": len(proposal_timelines),
            "first_year": first_period["start"].year,
            "last_year": last_period["end"].year,
            "first_period": first_period["label"],
            "last_period": last_period["label"],
            "milestones": [
                {
                    "date": milestone["date"].isoformat(),
                    "label": milestone["label"],
                    "standard": milestone["standard"],
                    "standard_label": milestone["standard_label"],
                }
                for milestone in milestones
            ],
        },
        "status_evolution": status_evolution,
        "status_evolution_segmented": _build_segmented_evolution_series(
            status_evolution_by_standard,
            standard_order=series_standard_keys,
            standard_labels=standard_labels,
            source_context=context,
        ),
        "status_evolution_by_standard": status_evolution_by_standard,
        "proposal_timelines": serialized_timelines,
    }
