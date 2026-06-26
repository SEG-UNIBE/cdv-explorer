import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.preprocess.rfc_preamble import extract


_BIP_CONFIG = {
    "document_prefix": "bip",
    "primary_id_field": "bip",
    "document_file_pattern": r"^bip-\d{4}\.(mediawiki|md|rst)$",
    "compliance_checker": "bip",
    "preamble": {
        "required_fields": [
            "bip",
            "title",
            "author",
            "comments_uri",
            "status",
            "type",
            "created",
            "license",
        ],
        "optional_fields": ["layer", "requires"],
        "field_aliases": {"authors": "author"},
        "expected_headlines": {
            "abstract": 2,
            "motivation": 2,
            "specification": 2,
            "copyright": 2,
        },
        "list_valued_fields": ["author", "license"],
    },
}


def _bip_content(number="379"):
    return "\n".join(
        [
            "<pre>",
            f"BIP: {number}",
            "Title: Test Markdown BIP",
            "Author: Alice Example",
            "Comments-URI: https://example.com/bip",
            "Status: Draft",
            "Type: Standards Track",
            "Created: 2026-01-01",
            "License: BSD-2-Clause",
            "</pre>",
            "",
            "==Abstract==",
            "A concise abstract.",
            "",
            "==Motivation==",
            "A concise motivation.",
            "",
            "==Specification==",
            "A concise specification.",
            "",
            "==Copyright==",
            "A concise copyright section.",
        ]
    )


class BipExtractionTests(unittest.TestCase):
    def test_extracts_mediawiki_preamble_and_normalizes_numeric_id(self):
        with TemporaryDirectory() as tmp:
            harvest_dir = Path(tmp) / "harvest"
            output_dir = Path(tmp) / "out"
            harvest_dir.mkdir()
            (harvest_dir / "bip-0002.mediawiki").write_text(
                _bip_content("0002"), encoding="utf-8"
            )

            extract(_BIP_CONFIG, harvest_dir, output_dir)

            output = json.loads(
                (output_dir / "bip-0002.json").read_text(encoding="utf-8")
            )

        self.assertEqual("2", output["raw"]["preamble"]["bip"])
        self.assertEqual(["Alice Example"], output["raw"]["preamble"]["author"])
        self.assertIn("bip2", output["insights"]["formal_compliance"])

    def test_extracts_markdown_bip_files_and_skips_non_matching_markdown(self):
        with TemporaryDirectory() as tmp:
            harvest_dir = Path(tmp) / "harvest"
            output_dir = Path(tmp) / "out"
            harvest_dir.mkdir()
            (harvest_dir / "README.md").write_text("# BIPs\n", encoding="utf-8")
            (harvest_dir / "bip-0379.md").write_text(
                _bip_content("0379"), encoding="utf-8"
            )

            extract(_BIP_CONFIG, harvest_dir, output_dir)

            output_files = sorted(path.name for path in output_dir.iterdir())
            output = json.loads(
                (output_dir / "bip-0379.json").read_text(encoding="utf-8")
            )

        self.assertEqual(["bip-0379.json"], output_files)
        self.assertEqual("379", output["raw"]["preamble"]["bip"])

    def test_prunes_stale_bip_json_after_extracting_current_files(self):
        with TemporaryDirectory() as tmp:
            harvest_dir = Path(tmp) / "harvest"
            output_dir = Path(tmp) / "out"
            harvest_dir.mkdir()
            output_dir.mkdir()
            (harvest_dir / "bip-0002.mediawiki").write_text(
                _bip_content("2"), encoding="utf-8"
            )
            (output_dir / "bip-9999.json").write_text("{}", encoding="utf-8")

            extract(_BIP_CONFIG, harvest_dir, output_dir)

            output_files = sorted(path.name for path in output_dir.iterdir())

        self.assertEqual(["bip-0002.json"], output_files)


if __name__ == "__main__":
    unittest.main()
