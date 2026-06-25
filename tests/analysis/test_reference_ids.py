import unittest

from analysis.reference_ids import (
    normalize_reference_id,
    normalize_reference_id_for_config,
    uses_hex_proposal_ids,
)


class ReferenceIdTests(unittest.TestCase):
    def test_uses_hex_proposal_ids_requires_real_hex_character_class(self) -> None:
        self.assertFalse(uses_hex_proposal_ids("BIP", r"\bBCA-FLAG-(\d+)\b"))
        self.assertTrue(uses_hex_proposal_ids("NIP", r"\bNIP[-#\s]?(\d+)\b"))
        self.assertTrue(uses_hex_proposal_ids("XIP", r"\bXIP-([0-9A-Fa-f]{1,3})\b"))

    def test_normalize_reference_id_decimal(self) -> None:
        self.assertEqual(
            normalize_reference_id("0032", proposal_label="BIP", reference_pattern=r"\bBIP[-#\s]?(\d+)\b"),
            "32",
        )

    def test_normalize_reference_id_decimal_rejects_negative_and_non_numeric(self) -> None:
        self.assertIsNone(normalize_reference_id("-1", proposal_label="BIP", reference_pattern=r"\bBIP[-#\s]?(\d+)\b"))
        self.assertIsNone(normalize_reference_id("BIP 32", proposal_label="BIP", reference_pattern=r"\bBIP[-#\s]?(\d+)\b"))

    def test_normalize_reference_id_decimal_respects_max(self) -> None:
        self.assertEqual(
            normalize_reference_id("999", proposal_label="BIP", reference_pattern=r"\bBIP[-#\s]?(\d+)\b", max_proposal_id=999),
            "999",
        )
        self.assertIsNone(
            normalize_reference_id("1000", proposal_label="BIP", reference_pattern=r"\bBIP[-#\s]?(\d+)\b", max_proposal_id=999),
        )

    def test_normalize_reference_id_hex_uppercases_and_zero_pads(self) -> None:
        self.assertEqual(
            normalize_reference_id("a", proposal_label="NIP", reference_pattern=r"\bNIP-([0-9A-Fa-f]{1,3})\b"),
            "0A",
        )
        self.assertEqual(
            normalize_reference_id("f4", proposal_label="NIP", reference_pattern=r"\bNIP-([0-9A-Fa-f]{1,3})\b"),
            "F4",
        )

    def test_normalize_reference_id_hex_respects_max(self) -> None:
        self.assertEqual(
            normalize_reference_id("F4", proposal_label="NIP", reference_pattern=r"\bNIP-([0-9A-Fa-f]{1,3})\b", max_proposal_id=0xF4),
            "F4",
        )
        self.assertIsNone(
            normalize_reference_id("F5", proposal_label="NIP", reference_pattern=r"\bNIP-([0-9A-Fa-f]{1,3})\b", max_proposal_id=0xF4),
        )

    def test_normalize_reference_id_for_config_decimal(self) -> None:
        config = {
            "proposal_label": "BIP",
            "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
            "max_proposal_id": 9999,
        }
        self.assertEqual(normalize_reference_id_for_config("0044", config), "44")

    def test_normalize_reference_id_for_config_hex(self) -> None:
        config = {
            "proposal_label": "XIP",
            "reference_pattern": r"\bXIP-([0-9A-Fa-f]{1,3})\b",
            "max_proposal_id": 0xFFF,
        }
        self.assertEqual(normalize_reference_id_for_config("0a", config), "0A")
        self.assertIsNone(normalize_reference_id_for_config("XYZ", config))


if __name__ == "__main__":
    unittest.main()
