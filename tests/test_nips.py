import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.preprocess.nip_tags import extract


_NIP_CONFIG = {
    "document_prefix": "nip",
    "primary_id_field": "nip",
    "document_file_pattern": r"^[0-9A-Fa-f]{2,3}\.md$",
    "compliance_checker": "nip",
    "preamble": {
        "required_fields": ["nip", "title", "status"],
        "optional_fields": ["author", "type", "layer", "kind"],
        "expected_headlines": {},
    },
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
    },
}


def _nip_content(
    identifier="01", title="Basic Protocol Flow", tags="`draft` `mandatory` `relay`"
):
    return "\n".join(
        [
            f"NIP-{identifier}",
            "======",
            "",
            title,
            "-" * len(title),
            "",
            tags,
        ]
    )


class NipExtractionTests(unittest.TestCase):
    def test_extracts_setext_metadata_to_json(self):
        with TemporaryDirectory() as tmp:
            harvest_dir = Path(tmp) / "harvest"
            output_dir = Path(tmp) / "out"
            harvest_dir.mkdir()
            (harvest_dir / "01.md").write_text(_nip_content(), encoding="utf-8")

            extract(_NIP_CONFIG, harvest_dir, output_dir)

            output = json.loads(
                (output_dir / "nip-01.json").read_text(encoding="utf-8")
            )

        self.assertEqual("01", output["raw"]["preamble"]["nip"])
        self.assertEqual("Basic Protocol Flow", output["raw"]["preamble"]["title"])
        self.assertIsNone(output["raw"]["preamble"]["author"])
        self.assertEqual("Draft", output["raw"]["preamble"]["status"])
        self.assertEqual("Mandatory", output["raw"]["preamble"]["type"])
        self.assertEqual("Relay", output["raw"]["preamble"]["layer"])

    def test_extracts_hex_nip_ids_and_skips_non_matching_markdown(self):
        with TemporaryDirectory() as tmp:
            harvest_dir = Path(tmp) / "harvest"
            output_dir = Path(tmp) / "out"
            harvest_dir.mkdir()
            (harvest_dir / "README.md").write_text("# NIPs\n", encoding="utf-8")
            (harvest_dir / "F4.md").write_text(
                _nip_content("F4", "Private Direct Messages", "`draft` `optional`"),
                encoding="utf-8",
            )

            extract(_NIP_CONFIG, harvest_dir, output_dir)

            output_files = sorted(path.name for path in output_dir.iterdir())
            output = json.loads(
                (output_dir / "nip-F4.json").read_text(encoding="utf-8")
            )

        self.assertEqual(["nip-F4.json"], output_files)
        self.assertEqual("F4", output["raw"]["preamble"]["nip"])
        self.assertEqual("Optional", output["raw"]["preamble"]["type"])

    def test_prunes_stale_nip_json_after_extracting_current_files(self):
        with TemporaryDirectory() as tmp:
            harvest_dir = Path(tmp) / "harvest"
            output_dir = Path(tmp) / "out"
            harvest_dir.mkdir()
            output_dir.mkdir()
            (harvest_dir / "01.md").write_text(_nip_content(), encoding="utf-8")
            (output_dir / "nip-FF.json").write_text("{}", encoding="utf-8")

            extract(_NIP_CONFIG, harvest_dir, output_dir)

            output_files = sorted(path.name for path in output_dir.iterdir())

        self.assertEqual(["nip-01.json"], output_files)


if __name__ == "__main__":
    unittest.main()
