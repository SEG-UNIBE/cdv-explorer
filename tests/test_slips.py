import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.preprocess.rfc_preamble import extract


_SLIP_CONFIG = {
    "document_prefix": "slip",
    "primary_id_field": "slip",
    "document_file_pattern": r"^slip-\d{4}\.md$",
    "compliance_checker": "slip",
    "preamble": {
        "required_fields": ["slip", "title", "author", "status", "type", "created"],
        "optional_fields": [],
        "field_aliases": {"number": "slip", "authors": "author"},
        "expected_headlines": {"abstract": 2},
        "list_valued_fields": ["author"],
    },
}


class SlipExtractionTests(unittest.TestCase):
    def test_extracts_fenced_preamble_after_title_and_normalizes_number(self):
        content = "\n".join(
            [
                "# SLIP-0010 : Universal private key derivation",
                "",
                "```",
                "Number: SLIP-0010",
                "Title: Universal private key derivation",
                "Type: Standard",
                "Status: Final",
                "Authors: Jochen Hoenicke",
                "    Pavol Rusnak",
                "Created: 2016-04-26",
                "```",
                "",
                "## Abstract",
                "A concise abstract.",
            ]
        )

        with TemporaryDirectory() as tmp:
            harvest_dir = Path(tmp) / "harvest"
            output_dir = Path(tmp) / "out"
            harvest_dir.mkdir()
            (harvest_dir / "slip-0010.md").write_text(content, encoding="utf-8")

            extract(_SLIP_CONFIG, harvest_dir, output_dir)

            output = json.loads(
                (output_dir / "slip-0010.json").read_text(encoding="utf-8")
            )

        preamble = output["raw"]["preamble"]
        self.assertEqual("10", preamble["slip"])
        self.assertEqual(["Jochen Hoenicke", "Pavol Rusnak"], preamble["author"])
        self.assertNotIn("authors", preamble)
        self.assertIn("slip", output["insights"]["formal_compliance"])

    def test_skips_non_proposal_markdown_files(self):
        content = "\n".join(
            [
                "# SLIP-0010 : Universal private key derivation",
                "",
                "```",
                "Number: SLIP-0010",
                "Title: Universal private key derivation",
                "Type: Standard",
                "Status: Final",
                "Authors: Jochen Hoenicke",
                "Created: 2016-04-26",
                "```",
                "",
                "## Abstract",
                "A concise abstract.",
            ]
        )

        with TemporaryDirectory() as tmp:
            harvest_dir = Path(tmp) / "harvest"
            output_dir = Path(tmp) / "out"
            harvest_dir.mkdir()
            (harvest_dir / "README.md").write_text("# SLIPs\n", encoding="utf-8")
            (harvest_dir / "slip-0010.md").write_text(content, encoding="utf-8")

            extract(_SLIP_CONFIG, harvest_dir, output_dir)

            output_files = [path.name for path in output_dir.iterdir()]
            output = json.loads(
                (output_dir / "slip-0010.json").read_text(encoding="utf-8")
            )

        self.assertEqual(["slip-0010.json"], output_files)
        self.assertEqual("10", output["raw"]["preamble"]["slip"])

    def test_prefers_earliest_header_block_over_later_pre_blocks(self):
        content = "\n".join(
            [
                "# SLIP-0032 : Extended serialization format for BIP-32 wallets",
                "",
                "```",
                "Number: SLIP-0032",
                "Title: Extended serialization format for BIP-32 wallets",
                "Type: Standard",
                "Status: Draft",
                "Authors: Pavol Rusnak",
                "Created: 2017-09-06",
                "```",
                "",
                "## Abstract",
                "A concise abstract.",
                "",
                "<pre>",
                "mnemonic = abandon abandon abandon about",
                "</pre>",
            ]
        )

        with TemporaryDirectory() as tmp:
            harvest_dir = Path(tmp) / "harvest"
            output_dir = Path(tmp) / "out"
            harvest_dir.mkdir()
            (harvest_dir / "slip-0032.md").write_text(content, encoding="utf-8")

            extract(_SLIP_CONFIG, harvest_dir, output_dir)

            output_files = [path.name for path in output_dir.iterdir()]
            output = json.loads(
                (output_dir / "slip-0032.json").read_text(encoding="utf-8")
            )

        self.assertEqual(["slip-0032.json"], output_files)
        self.assertEqual("32", output["raw"]["preamble"]["slip"])

    def test_prunes_stale_source_json_after_extracting_current_files(self):
        content = "\n".join(
            [
                "# SLIP-0010 : Universal private key derivation",
                "",
                "```",
                "Number: SLIP-0010",
                "Title: Universal private key derivation",
                "Type: Standard",
                "Status: Final",
                "Authors: Jochen Hoenicke",
                "Created: 2016-04-26",
                "```",
                "",
                "## Abstract",
                "A concise abstract.",
            ]
        )

        with TemporaryDirectory() as tmp:
            harvest_dir = Path(tmp) / "harvest"
            output_dir = Path(tmp) / "out"
            harvest_dir.mkdir()
            output_dir.mkdir()
            (harvest_dir / "slip-0010.md").write_text(content, encoding="utf-8")
            (output_dir / "slip-unknown_slip.json").write_text("{}", encoding="utf-8")

            extract(_SLIP_CONFIG, harvest_dir, output_dir)

            output_files = [path.name for path in output_dir.iterdir()]

        self.assertEqual(["slip-0010.json"], output_files)


if __name__ == "__main__":
    unittest.main()
