import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis.evolution.metrics import prepare_evolution_payload
from analysis.evolution.mining import extract_status_timeline
from pipeline.source_context import SourceContext


class EvolutionStatusTests(unittest.TestCase):
    def test_extract_status_timeline_parses_nip_tag_history_without_affecting_bitcoin_path(self) -> None:
        log_stdout = "\n".join(
            [
                "__COMMIT__newcommit|2025-12-11T14:54:19+01:00|JeffG",
                "M\tEE.md",
                "__COMMIT__oldcommit|2025-08-27T16:03:06+00:00|Jeff Gardner",
                "A\tEE.md",
            ]
        )
        current_content = "\n".join(
            [
                "NIP-EE",
                "======",
                "",
                "E2EE Messaging using the Messaging Layer Security (MLS) Protocol",
                "----------------------------------------------------------------",
                "",
                "`final` `unrecommended` `optional`",
                "",
                "Body.",
            ]
        )
        old_content = current_content.replace("`final` `unrecommended` `optional`", "`draft` `optional`")
        new_content = current_content
        show_stdout_by_spec = {
            "oldcommit:EE.md": old_content,
            "newcommit:EE.md": new_content,
        }

        def fake_run(args, **kwargs):
            if "log" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout=log_stdout)
            if "show" in args:
                spec = args[-1]
                stdout = show_stdout_by_spec.get(spec)
                if stdout is None:
                    raise AssertionError(f"Unexpected git show spec: {spec}")
                return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout)
            raise AssertionError(f"Unexpected subprocess invocation: {args}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir)
            file_path = repo_dir / "EE.md"
            file_path.write_text(current_content, encoding="utf-8")

            source_context = SourceContext.from_config(
                {
                    "preprocessor": "nip_tags",
                    "document_prefix": "nip",
                    "primary_id_field": "nip",
                    "preamble": {"field_aliases": {"optionality": "type"}},
                    "classification": {
                        "dimensions": {
                            "status": {"aliases": {"draft": "Draft", "final": "Final"}},
                            "type": {"aliases": {"mandatory": "Mandatory", "optional": "Optional"}},
                            "layer": {"aliases": {"relay": "Relay"}},
                        },
                        "regimes": [],
                    },
                }
            )
            with patch("analysis.evolution.mining.subprocess.run", side_effect=fake_run):
                timeline = extract_status_timeline(
                    repo_dir=repo_dir,
                    file_path=file_path,
                    source_context=source_context,
                )

        self.assertEqual(
            timeline,
            [
                {
                    "commit": "oldcommit",
                    "timestamp": "2025-08-27T16:03:06+00:00",
                    "date": "2025-08-27",
                    "author": "Jeff Gardner",
                    "path": "EE.md",
                    "status": "Draft",
                    "standard": "",
                },
                {
                    "commit": "newcommit",
                    "timestamp": "2025-12-11T14:54:19+01:00",
                    "date": "2025-12-11",
                    "author": "JeffG",
                    "path": "EE.md",
                    "status": "Final",
                    "standard": "",
                },
            ],
        )

    def test_extract_status_timeline_uses_committer_dates_and_keeps_standard_transitions(self) -> None:
        log_stdout = "\n".join(
            [
                "__COMMIT__newcommit|2026-01-12T14:22:25-08:00|Murch",
                "M\tbip-0001.mediawiki",
                "__COMMIT__oldcommit|2025-10-01T10:00:00+00:00|Alice",
                "M\tbip-0001.mediawiki",
            ]
        )
        show_stdout = "<pre>\nStatus: Draft\n</pre>\n"

        def fake_run(args, **kwargs):
            if "log" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout=log_stdout)
            if "show" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout=show_stdout)
            raise AssertionError(f"Unexpected subprocess invocation: {args}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir)
            file_path = repo_dir / "bip-0001.mediawiki"
            file_path.write_text(show_stdout, encoding="utf-8")

            with patch("analysis.evolution.mining.subprocess.run", side_effect=fake_run):
                timeline = extract_status_timeline(
                    repo_dir=repo_dir,
                    file_path=file_path,
                )

        self.assertEqual(
            timeline,
            [
                {
                    "commit": "oldcommit",
                    "timestamp": "2025-10-01T10:00:00+00:00",
                    "date": "2025-10-01",
                    "author": "Alice",
                    "path": "bip-0001.mediawiki",
                    "status": "Draft",
                    "standard": "bip2",
                },
                {
                    "commit": "newcommit",
                    "timestamp": "2026-01-12T14:22:25-08:00",
                    "date": "2026-01-12",
                    "author": "Murch",
                    "path": "bip-0001.mediawiki",
                    "status": "Draft",
                    "standard": "bip3",
                },
            ],
        )

    def test_extract_status_timeline_keeps_pre_assignment_history_with_placeholder_id(self) -> None:
        log_stdout = "\n".join(
            [
                "__COMMIT__assigncommit|2016-01-08T17:56:02+00:00|Luke Dashjr",
                "R099\tbip-segwitaddress.mediawiki\tbip-0142.mediawiki",
                "__COMMIT__createcommit|2015-12-24T21:45:11+08:00|Johnson Lau",
                "A\tbip-segwitaddress.mediawiki",
            ]
        )

        current_content = """<pre>
  BIP: 142
  Title: Address Format for Segregated Witness
  Author: Johnson Lau <jl2012@xbt.hk>
  Status: Draft
  Created: 2015-12-24
</pre>
"""
        initial_content = """<pre>
  BIP: x
  Title: Address Format for Witness Program
  Author: Johnson Lau <jl2012@xbt.hk>
  Status: Draft
  Created: 2015-12-24
</pre>
"""
        show_stdout_by_spec = {
            "assigncommit:bip-0142.mediawiki": current_content,
            "createcommit:bip-segwitaddress.mediawiki": initial_content,
        }

        def fake_run(args, **kwargs):
            if "log" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout=log_stdout)
            if "show" in args:
                spec = args[-1]
                stdout = show_stdout_by_spec.get(spec)
                if stdout is None:
                    raise AssertionError(f"Unexpected git show spec: {spec}")
                return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout)
            raise AssertionError(f"Unexpected subprocess invocation: {args}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir)
            file_path = repo_dir / "bip-0142.mediawiki"
            file_path.write_text(current_content, encoding="utf-8")

            with patch("analysis.evolution.mining.subprocess.run", side_effect=fake_run):
                timeline = extract_status_timeline(
                    repo_dir=repo_dir,
                    file_path=file_path,
                )

        self.assertEqual(
            timeline,
            [
                {
                    "commit": "createcommit",
                    "timestamp": "2015-12-24T21:45:11+08:00",
                    "date": "2015-12-24",
                    "author": "Johnson Lau",
                    "path": "bip-segwitaddress.mediawiki",
                    "status": "Draft",
                    "standard": "bip2",
                }
            ],
        )

    def test_prepare_evolution_payload_splits_bip3_cutover_period(self) -> None:
        proposal_data = [
            {
                "raw": {"preamble": {"bip": "1"}},
                "insights": {
                    "changes_in_status": [
                        {"date": "2025-10-01", "status": "Draft", "standard": "bip2"},
                        {"date": "2026-01-12", "status": "Draft", "standard": "bip3"},
                    ]
                },
            },
            {
                "raw": {"preamble": {"bip": "2"}},
                "insights": {
                    "changes_in_status": [
                        {"date": "2025-10-01", "status": "Final", "standard": "bip2"},
                        {"date": "2026-01-12", "status": "Deployed", "standard": "bip3"},
                    ]
                },
            },
            {
                "raw": {"preamble": {"bip": "3"}},
                "insights": {
                    "changes_in_status": [
                        {"date": "2025-10-01", "status": "Proposed", "standard": "bip2"},
                        {"date": "2026-01-12", "status": "Complete", "standard": "bip3"},
                    ]
                },
            },
        ]

        payload = prepare_evolution_payload(
            proposal_data=proposal_data,
            snapshot_label="2026-03-16",
            id_field="bip",
        )

        self.assertEqual(
            [row["period"] for row in payload["status_evolution"]["rows"]],
            ["2025-Q4", "2026-Q1", "2026-Q1"],
        )
        self.assertEqual(
            [row["period_key"] for row in payload["status_evolution"]["rows"]],
            ["2025-Q4", "2026-Q1-pre-bip3", "2026-Q1-post-bip3"],
        )
        self.assertEqual(payload["meta"]["first_period"], "2025-Q4")
        self.assertEqual(payload["meta"]["last_period"], "2026-Q1")
        self.assertEqual(payload["meta"]["milestones"], [{"date": "2026-01-12", "label": "BIP3 Activation"}])

        segmented_rows = {
            row["period_key"]: row for row in payload["status_evolution_segmented"]["rows"]
        }

        self.assertEqual(segmented_rows["2025-Q4"]["values"]["bip2:Draft"], 1)
        self.assertEqual(segmented_rows["2025-Q4"]["values"]["bip2:Final"], 1)
        self.assertEqual(segmented_rows["2025-Q4"]["values"]["bip2:Proposed"], 1)
        self.assertEqual(segmented_rows["2026-Q1-pre-bip3"]["period_end"], "2026-01-11")
        self.assertEqual(segmented_rows["2026-Q1-pre-bip3"]["values"]["bip2:Draft"], 1)
        self.assertEqual(segmented_rows["2026-Q1-pre-bip3"]["values"]["bip2:Final"], 1)
        self.assertEqual(segmented_rows["2026-Q1-pre-bip3"]["values"]["bip2:Proposed"], 1)
        self.assertEqual(segmented_rows["2026-Q1-pre-bip3"]["values"]["bip3:Draft"], 0)
        self.assertEqual(segmented_rows["2026-Q1-pre-bip3"]["values"]["bip3:Deployed"], 0)
        self.assertEqual(segmented_rows["2026-Q1-pre-bip3"]["values"]["bip3:Complete"], 0)
        self.assertEqual(segmented_rows["2026-Q1-post-bip3"]["period_start"], "2026-01-12")
        self.assertEqual(segmented_rows["2026-Q1-post-bip3"]["values"]["bip3:Draft"], 1)
        self.assertEqual(segmented_rows["2026-Q1-post-bip3"]["values"]["bip3:Deployed"], 1)
        self.assertEqual(segmented_rows["2026-Q1-post-bip3"]["values"]["bip3:Complete"], 1)

    def test_prepare_evolution_payload_does_not_project_bip3_before_harvested_transition(self) -> None:
        proposal_data = [
            {
                "raw": {"preamble": {"bip": "1"}},
                "insights": {
                    "changes_in_status": [
                        {"date": "2025-10-01", "status": "Draft", "standard": "bip2"},
                        {"date": "2026-01-15", "status": "Draft", "standard": "bip3"},
                    ]
                },
            }
        ]

        payload = prepare_evolution_payload(
            proposal_data=proposal_data,
            snapshot_label="2026-03-16",
            id_field="bip",
        )

        segmented_rows = {
            row["period_key"]: row for row in payload["status_evolution_segmented"]["rows"]
        }

        self.assertEqual(segmented_rows["2025-Q4"]["values"]["bip2:Draft"], 1)
        self.assertEqual(segmented_rows["2026-Q1-pre-bip3"]["values"]["bip2:Draft"], 1)
        self.assertEqual(segmented_rows["2026-Q1-pre-bip3"]["values"]["bip3:Draft"], 0)
        self.assertEqual(segmented_rows["2026-Q1-post-bip3"]["values"]["bip3:Draft"], 1)

    def test_prepare_evolution_payload_resolves_ambiguous_draft_by_event_date_when_standard_is_missing(self) -> None:
        proposal_data = [
            {
                "raw": {"preamble": {"bip": "1"}},
                "insights": {
                    "changes_in_status": [
                        {"date": "2025-10-01", "status": "Draft"},
                        {"date": "2026-01-15", "status": "Draft"},
                    ]
                },
            }
        ]

        payload = prepare_evolution_payload(
            proposal_data=proposal_data,
            snapshot_label="2026-03-16",
            id_field="bip",
        )

        segmented_rows = {
            row["period_key"]: row for row in payload["status_evolution_segmented"]["rows"]
        }

        self.assertEqual(segmented_rows["2025-Q4"]["values"]["bip2:Draft"], 1)
        self.assertEqual(segmented_rows["2026-Q1-pre-bip3"]["values"]["bip2:Draft"], 1)
        self.assertEqual(segmented_rows["2026-Q1-post-bip3"]["values"]["bip3:Draft"], 1)

    def test_prepare_evolution_payload_serializes_per_proposal_event_timelines(self) -> None:
        proposal_data = [
            {
                "raw": {
                    "preamble": {
                        "bip": "1",
                        "title": "Example Proposal",
                        "created": "2025-09-15",
                    }
                },
                "insights": {
                    "changes_in_status": [
                        {
                            "date": "2025-10-01",
                            "timestamp": "2025-10-01T10:00:00+00:00",
                            "status": "Draft",
                            "standard": "bip2",
                            "commit": "draftcommit",
                            "author": "Alice",
                            "path": "bip-0001.mediawiki",
                        },
                        {
                            "date": "2026-01-15",
                            "timestamp": "2026-01-15T10:00:00+00:00",
                            "status": "Draft",
                            "standard": "bip3",
                            "commit": "bip3commit",
                            "author": "Bob",
                            "path": "bip-0001.mediawiki",
                        },
                    ]
                },
            }
        ]

        payload = prepare_evolution_payload(
            proposal_data=proposal_data,
            snapshot_label="2025-12-31",
            id_field="bip",
        )

        self.assertEqual(len(payload["proposal_timelines"]), 1)
        proposal_timeline = payload["proposal_timelines"][0]
        self.assertEqual(proposal_timeline["proposal_id"], "1")
        self.assertEqual(proposal_timeline["title"], "Example Proposal")
        self.assertEqual(proposal_timeline["current_status"], "Draft")
        self.assertEqual(proposal_timeline["current_standard"], "bip2")
        self.assertEqual(
            proposal_timeline["events"],
            [
                {
                    "kind": "creation",
                    "label": "Created",
                    "date": "2025-09-15",
                    "timestamp": "2025-10-01T10:00:00+00:00",
                    "status": "Draft",
                    "standard": "bip2",
                    "commit": "draftcommit",
                    "author": "Alice",
                    "path": "bip-0001.mediawiki",
                    "previous_status": "",
                },
                {
                    "kind": "status_change",
                    "label": "Draft",
                    "date": "2025-10-01",
                    "timestamp": "2025-10-01T10:00:00+00:00",
                    "status": "Draft",
                    "standard": "bip2",
                    "commit": "draftcommit",
                    "author": "Alice",
                    "path": "bip-0001.mediawiki",
                    "previous_status": "Draft",
                },
            ],
        )

    def test_prepare_evolution_payload_counts_from_created_date_before_first_observed_status(self) -> None:
        proposal_data = [
            {
                "raw": {
                    "preamble": {
                        "bip": "431",
                        "title": "Topology Restrictions for Pinning",
                        "created": "2024-01-10",
                    }
                },
                "insights": {
                    "changes_in_status": [
                        {
                            "date": "2024-05-23",
                            "timestamp": "2024-05-23T16:33:00+01:00",
                            "status": "Draft",
                            "standard": "bip2",
                            "commit": "draftcommit",
                            "author": "glozow",
                            "path": "bip-0431.mediawiki",
                        }
                    ]
                },
            }
        ]

        payload = prepare_evolution_payload(
            proposal_data=proposal_data,
            snapshot_label="2024-03-31",
            id_field="bip",
        )

        self.assertEqual(payload["meta"]["first_period"], "2024-Q1")
        self.assertEqual(payload["meta"]["last_period"], "2024-Q1")
        self.assertEqual(payload["status_evolution"]["rows"][0]["values"]["Draft"], 1)
        self.assertEqual(payload["status_evolution_segmented"]["rows"][0]["values"]["bip2:Draft"], 1)
        self.assertEqual(payload["proposal_timelines"][0]["current_status"], "Draft")
        self.assertEqual(payload["proposal_timelines"][0]["current_standard"], "bip2")
        self.assertEqual(
            payload["proposal_timelines"][0]["events"],
            [
                {
                    "kind": "creation",
                    "label": "Created",
                    "date": "2024-01-10",
                    "timestamp": "2024-05-23T16:33:00+01:00",
                    "status": "Draft",
                    "standard": "bip2",
                    "commit": "draftcommit",
                    "author": "glozow",
                    "path": "bip-0431.mediawiki",
                    "previous_status": "",
                }
            ],
        )

    def test_prepare_evolution_payload_truncates_status_series_for_any_snapshot(self) -> None:
        proposal_data = [
            {
                "raw": {"preamble": {"bip": "1", "created": "2020-09-15"}},
                "insights": {
                    "changes_in_status": [
                        {"date": "2020-10-01", "status": "Draft", "standard": "bip2"},
                        {"date": "2022-01-15", "status": "Final", "standard": "bip2"},
                    ]
                },
            }
        ]

        expectations = {
            "2021-01-01": {
                "last_period": "2021-Q1",
                "period_keys": ["2020-Q3", "2020-Q4", "2021-Q1"],
                "categories": ["Draft"],
                "current_status": "Draft",
            },
            "2025-01-01": {
                "last_period": "2025-Q1",
                "period_keys": [
                    "2020-Q3",
                    "2020-Q4",
                    "2021-Q1",
                    "2021-Q2",
                    "2021-Q3",
                    "2021-Q4",
                    "2022-Q1",
                    "2022-Q2",
                    "2022-Q3",
                    "2022-Q4",
                    "2023-Q1",
                    "2023-Q2",
                    "2023-Q3",
                    "2023-Q4",
                    "2024-Q1",
                    "2024-Q2",
                    "2024-Q3",
                    "2024-Q4",
                    "2025-Q1",
                ],
                "categories": ["Draft", "Final"],
                "current_status": "Final",
            },
        }

        for snapshot_label, expected in expectations.items():
            payload = prepare_evolution_payload(
                proposal_data=proposal_data,
                snapshot_label=snapshot_label,
                id_field="bip",
            )

            self.assertEqual(payload["meta"]["last_period"], expected["last_period"])
            self.assertEqual(
                [row["period_key"] for row in payload["status_evolution"]["rows"]],
                expected["period_keys"],
            )
            self.assertEqual(payload["status_evolution"]["categories"], expected["categories"])
            self.assertEqual(payload["proposal_timelines"][0]["current_status"], expected["current_status"])

    def test_extract_status_timeline_ignores_reused_placeholder_history_from_other_proposals(self) -> None:
        log_stdout = "\n".join(
            [
                "__COMMIT__finalcommit|2025-09-01T09:08:50-06:00|Jon Atack",
                "M\tbip-0155.mediawiki",
                "__COMMIT__renamecommit|2019-07-18T00:17:55+02:00|Wladimir J. van der Laan",
                "R099\tbip-XXXX.mediawiki\tbip-0155.mediawiki",
                "__COMMIT__wrongplaceholder|2019-03-02T14:50:23-08:00|cgilliard",
                "M\tbip-XXXX.mediawiki",
                "__COMMIT__rightplaceholder|2019-02-27T10:28:34+01:00|Wladimir J. van der Laan",
                "M\tbip-XXXX.mediawiki",
            ]
        )

        current_content = """<pre>
  BIP: 155
  Title: addrv2 message
  Author: Wladimir J. van der Laan <laanwj@gmail.com>
  Status: Deployed
  Created: 2019-02-27
</pre>
"""
        right_placeholder_content = """<pre>
  BIP: ???
  Title: addrv2 message
  Author: Wladimir J. van der Laan <laanwj@gmail.com>
  Status: Draft
  Created: 2019-02-27
</pre>
"""
        wrong_placeholder_content = """<pre>
  BIP: ???
  Title: Signatures of Messages using Bitcoin Private Keys
  Author: Christopher Gilliard <christopher.gilliard@gmail.com>
  Status: Proposal
  Created: 2019-02-16
</pre>
"""
        final_content = """<pre>
  BIP: 155
  Title: addrv2 message
  Author: Wladimir J. van der Laan <laanwj@gmail.com>
  Status: Final
  Created: 2019-02-27
</pre>
"""

        show_stdout_by_spec = {
            "finalcommit:bip-0155.mediawiki": final_content,
            "renamecommit:bip-0155.mediawiki": right_placeholder_content,
            "wrongplaceholder:bip-XXXX.mediawiki": wrong_placeholder_content,
            "rightplaceholder:bip-XXXX.mediawiki": right_placeholder_content,
        }

        def fake_run(args, **kwargs):
            if "log" in args:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout=log_stdout)
            if "show" in args:
                spec = args[-1]
                stdout = show_stdout_by_spec.get(spec)
                if stdout is None:
                    raise AssertionError(f"Unexpected git show spec: {spec}")
                return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout)
            raise AssertionError(f"Unexpected subprocess invocation: {args}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir)
            file_path = repo_dir / "bip-0155.mediawiki"
            file_path.write_text(current_content, encoding="utf-8")

            with patch("analysis.evolution.mining.subprocess.run", side_effect=fake_run):
                timeline = extract_status_timeline(
                    repo_dir=repo_dir,
                    file_path=file_path,
                )

        self.assertEqual(
            timeline,
            [
                {
                    "commit": "rightplaceholder",
                    "timestamp": "2019-02-27T10:28:34+01:00",
                    "date": "2019-02-27",
                    "author": "Wladimir J. van der Laan",
                    "path": "bip-XXXX.mediawiki",
                    "status": "Draft",
                    "standard": "bip2",
                },
                {
                    "commit": "finalcommit",
                    "timestamp": "2025-09-01T09:08:50-06:00",
                    "date": "2025-09-01",
                    "author": "Jon Atack",
                    "path": "bip-0155.mediawiki",
                    "status": "Final",
                    "standard": "bip2",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
