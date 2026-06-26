"""Nostr-specific parsing and analysis tests.

Covers: hex NIP ID normalization, verbose git date parsing, first-day author
extraction, preamble backfill, and NIP file tag parsing.
"""

import unittest

from analysis.utils import parse_date_ymd
from analysis.authorship.mining import get_git_authors_on_first_day
from analysis.dependencies.network import normalize_proposal_ids


_NIP_SRC_CONFIG = {
    "classification": {
        "dimensions": {
            "status": {
                "aliases": {
                    "draft": "Draft",
                    "final": "Final",
                    "deprecated": "Deprecated",
                }
            },
            "type": {
                "aliases": {
                    "mandatory": "Mandatory",
                    "optional": "Optional",
                    "unrecommended": "Unrecommended",
                }
            },
            "layer": {
                "aliases": {
                    "relay": "Relay",
                    "client": "Client",
                    "cryptography": "Cryptography",
                }
            },
        }
    }
}


# ---------------------------------------------------------------------------
# parse_date_ymd
# ---------------------------------------------------------------------------


class ParseDateYmdTests(unittest.TestCase):
    def test_iso_short(self):
        self.assertEqual(parse_date_ymd("2024-03-16"), "2024-03-16")

    def test_iso_datetime_prefix(self):
        self.assertEqual(parse_date_ymd("2024-03-16T10:00:00+00:00"), "2024-03-16")

    def test_verbose_git_timestamp(self):
        self.assertEqual(parse_date_ymd("Wed Oct 8 14:59:36 2025 -0700"), "2025-10-08")

    def test_verbose_git_timestamp_positive_offset(self):
        self.assertEqual(parse_date_ymd("Mon Jan 1 00:00:00 2024 +0900"), "2024-01-01")

    def test_empty_returns_none(self):
        self.assertIsNone(parse_date_ymd(""))
        self.assertIsNone(parse_date_ymd(None))

    def test_garbage_returns_none(self):
        self.assertIsNone(parse_date_ymd("not a date"))


# ---------------------------------------------------------------------------
# normalize_proposal_ids — hex NIP IDs
# ---------------------------------------------------------------------------


class NormalizeNipIdsTests(unittest.TestCase):
    def test_plain_hex_id_uppercased(self):
        self.assertEqual(normalize_proposal_ids(["a0"], "NIP"), ["A0"])

    def test_nip_prefix_stripped(self):
        self.assertEqual(normalize_proposal_ids(["NIP-A0"], "NIP"), ["A0"])

    def test_nip_space_prefix_stripped(self):
        self.assertEqual(normalize_proposal_ids(["NIP A0"], "NIP"), ["A0"])

    def test_single_digit_nip_id_padded(self):
        self.assertEqual(normalize_proposal_ids(["NIP 1"], "NIP"), ["01"])

    def test_mixed_hex_and_numeric(self):
        result = normalize_proposal_ids(["NIP-01", "NIP-CC", "NIP-B7"], "NIP")
        self.assertEqual(result, ["01", "CC", "B7"])

    def test_lowercase_hex_normalized_to_upper(self):
        self.assertEqual(normalize_proposal_ids(["cc"], "NIP"), ["CC"])

    def test_garbled_entry_excluded(self):
        result = normalize_proposal_ids(["NIP-01", "not a nip", "NIP-CC"], "NIP")
        self.assertEqual(result, ["01", "CC"])

    def test_empty_input(self):
        self.assertEqual(normalize_proposal_ids([], "NIP"), [])
        self.assertEqual(normalize_proposal_ids(None, "NIP"), [])


# ---------------------------------------------------------------------------
# get_git_authors_on_first_day
# ---------------------------------------------------------------------------


class GetGitAuthorsOnFirstDayTests(unittest.TestCase):
    def _history(self):
        # newest-first, as git log returns
        return [
            ("c4", "2022-05-04T09:00:00+00:00", "Later Author"),
            ("c3", "2022-05-01T15:00:00+00:00", "Second Author"),
            ("c2", "2022-05-01T09:00:00+00:00", "First Author"),
            ("c1", "2022-05-01T08:00:00+00:00", "github-actions[bot]"),
        ]

    def test_returns_first_day_committers_only(self):
        authors = get_git_authors_on_first_day(self._history())
        self.assertIn("First Author", authors)
        self.assertIn("Second Author", authors)
        self.assertNotIn("Later Author", authors)

    def test_bots_excluded(self):
        authors = get_git_authors_on_first_day(self._history())
        self.assertNotIn("github-actions[bot]", authors)

    def test_order_matches_newest_first_git_log(self):
        authors = get_git_authors_on_first_day(self._history())
        # c3 appears before c2 in the newest-first list → Second Author first
        self.assertEqual(authors, ["Second Author", "First Author"])

    def test_verbose_git_dates_handled(self):
        history = [
            ("c2", "Wed Oct 8 14:59:36 2025 -0700", "Author B"),
            ("c1", "Wed Oct 8 09:00:00 2025 +0000", "Author A"),
        ]
        authors = get_git_authors_on_first_day(history)
        self.assertIn("Author A", authors)
        self.assertIn("Author B", authors)

    def test_single_commit_returns_that_author(self):
        history = [("c1", "2022-05-01T08:00:00+00:00", "Solo Author")]
        self.assertEqual(get_git_authors_on_first_day(history), ["Solo Author"])

    def test_empty_history_returns_empty(self):
        self.assertEqual(get_git_authors_on_first_day([]), [])

    def test_duplicate_author_on_same_day_deduplicated(self):
        history = [
            ("c2", "2022-05-01T15:00:00+00:00", "Author A"),
            ("c1", "2022-05-01T08:00:00+00:00", "Author A"),
        ]
        self.assertEqual(get_git_authors_on_first_day(history), ["Author A"])


# ---------------------------------------------------------------------------
# NIP file parsing (_parse_nip_file)
# ---------------------------------------------------------------------------


class ParseNipFileTests(unittest.TestCase):
    def _parse(self, content, filename="01.md"):
        from pipeline.preprocess.nip_tags import _parse_nip_file

        return _parse_nip_file(content, filename, _NIP_SRC_CONFIG)

    def test_setext_heading_with_tag_line(self):
        content = "\n".join(
            [
                "NIP-01",
                "======",
                "",
                "Basic Protocol Flow",
                "-------------------",
                "",
                "`draft` `mandatory` `relay`",
            ]
        )
        p = self._parse(content)
        self.assertEqual(p["nip"], "01")
        self.assertEqual(p["title"], "Basic Protocol Flow")
        self.assertEqual(p["status"], "Draft")
        self.assertEqual(p["type"], "Mandatory")
        self.assertEqual(p["layer"], "Relay")

    def test_hex_nip_id_from_filename(self):
        content = "\n".join(
            [
                "NIP-CC",
                "======",
                "",
                "Commerce",
                "--------",
                "",
                "`draft` `optional`",
            ]
        )
        p = self._parse(content, filename="CC.md")
        self.assertEqual(p["nip"], "CC")

    def test_lowercase_filename_uppercased(self):
        content = "\n".join(
            [
                "NIP-b7",
                "======",
                "",
                "Something",
                "---------",
                "",
                "`final`",
            ]
        )
        p = self._parse(content, filename="b7.md")
        self.assertEqual(p["nip"], "B7")

    def test_unknown_tokens_stored_as_kind(self):
        content = "\n".join(
            [
                "NIP-01",
                "======",
                "",
                "Some NIP",
                "---------",
                "",
                "`draft` `event-kind-1234`",
            ]
        )
        p = self._parse(content)
        self.assertIn("event-kind-1234", p.get("kind", ""))

    def test_no_tag_line_status_defaults_to_unknown(self):
        content = "\n".join(
            [
                "NIP-01",
                "======",
                "",
                "Untitled NIP",
                "------------",
                "",
                "Just body text here, no tags.",
            ]
        )
        p = self._parse(content)
        self.assertEqual(p["status"], "Unknown")

    def test_atx_heading_fallback(self):
        content = "\n".join(
            [
                "# NIP-05",
                "",
                "## Mapping Nostr keys to DNS-based identifiers",
                "",
                "`final` `optional`",
            ]
        )
        p = self._parse(content, filename="05.md")
        self.assertEqual(p["nip"], "05")
        self.assertEqual(p["title"], "Mapping Nostr keys to DNS-based identifiers")
        self.assertEqual(p["status"], "Final")


if __name__ == "__main__":
    unittest.main()
