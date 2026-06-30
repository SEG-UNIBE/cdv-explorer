import sys
import types
import unittest
from unittest.mock import patch

if "openai" not in sys.modules:
    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = type("OpenAI", (), {})
    sys.modules["openai"] = fake_openai

from analysis.dependencies.mining import (
    _call_with_rate_limit_retry,
    build_llm_semantic_dependency_manifest_record,
    create_explicit_dependency_targets,
    create_reference_list,
    create_reference_targets,
    llm_extract_implicit_dependencies,
    llm_extract_semantic_dependencies,
    normalize_dependency_output,
    normalize_llm_dependency_output,
    prepare_llm_dependency_text,
)
from analysis.reference_ids import uses_hex_proposal_ids
from ecosystems import ECOSYSTEM_REGISTRY
from pipeline.source_context import SourceContext


class NormalizeDependencyOutputTests(unittest.TestCase):
    def test_recognizes_various_formats_as_same_id(self):
        result = normalize_dependency_output(
            ["BIP 32", "BIP-32", "BIP-0032", "32"], proposal_label="BIP"
        )
        self.assertEqual(result, ["BIP 32"])

    def test_excludes_current_proposal(self):
        result = normalize_dependency_output(
            ["BIP 32", "BIP 39"], proposal_label="BIP", current_proposal_number="32"
        )
        self.assertEqual(result, ["BIP 39"])

    def test_non_list_input_returns_empty(self):
        self.assertEqual(
            normalize_dependency_output("BIP 32", proposal_label="BIP"), []
        )
        self.assertEqual(normalize_dependency_output(None, proposal_label="BIP"), [])

    def test_garbled_items_are_skipped(self):
        result = normalize_dependency_output(
            ["BIP 32", "not a bip", "", "BIP 39"], proposal_label="BIP"
        )
        self.assertEqual(result, ["BIP 32", "BIP 39"])

    def test_output_is_sorted_numerically(self):
        result = normalize_dependency_output(
            ["BIP 200", "BIP 1", "BIP 50"], proposal_label="BIP"
        )
        self.assertEqual(result, ["BIP 1", "BIP 50", "BIP 200"])

    def test_ids_exceeding_ecosystem_max_are_excluded(self):
        result = normalize_dependency_output(
            ["BIP 999", "BIP 1000"], proposal_label="BIP"
        )
        self.assertEqual(result, ["BIP 999"])

    def test_hex_nip_ids_preserve_width_and_exclude_current_proposal(self):
        result = normalize_dependency_output(
            ["NIP 1", "NIP-01", "NIP F4"],
            proposal_label="NIP",
            current_proposal_number="F4",
        )
        self.assertEqual(result, ["NIP 01"])


class CreateReferenceListTests(unittest.TestCase):
    def test_detects_single_inline_reference(self):
        result = create_reference_list("This builds on BIP 32 for key derivation.")
        self.assertIn("BIP 32", result)

    def test_detects_comma_separated_list_syntax(self):
        result = create_reference_list("See BIPs 32 and 39 for details.")
        self.assertIn("BIP 32", result)
        self.assertIn("BIP 39", result)

    def test_empty_text_returns_empty(self):
        self.assertEqual(create_reference_list(""), [])

    def test_text_without_references_returns_empty(self):
        self.assertEqual(create_reference_list("no proposals mentioned here"), [])

    def test_output_is_sorted_numerically(self):
        result = create_reference_list("BIP 100 and BIP 5 are relevant.")
        self.assertLess(result.index("BIP 5"), result.index("BIP 100"))

    def test_detects_hex_nip_references(self):
        result = create_reference_list(
            "This builds on NIP-01 and NIP-F4.",
            proposal_label="NIP",
            reference_pattern=r"\bNIP-([0-9A-Fa-f]{1,3})\b",
        )
        self.assertEqual(result, ["NIP 01", "NIP F4"])

    def test_detects_hex_ids_from_reference_pattern_for_non_nip_sources(self):
        context = SourceContext.from_config(
            {
                "proposal_acronym": "XIP",
                "proposal_term_singular": "Example Improvement Proposal",
                "reference_pattern": r"\bXIP-([0-9A-Fa-f]{1,3})\b",
            },
            source_slug="xips",
        )

        result = create_reference_list(
            "This builds on XIP-0A and XIP-10.",
            proposal_label="XIP",
            reference_pattern=r"\bXIP-([0-9A-Fa-f]{1,3})\b",
            source_context=context,
        )

        self.assertEqual(result, ["XIP 0A", "XIP 10"])

    def test_hex_detection_requires_hex_character_class(self):
        self.assertFalse(uses_hex_proposal_ids("BIP", r"\bBCA-FLAG-(\d+)\b"))
        self.assertTrue(uses_hex_proposal_ids("XIP", r"\bXIP-([0-9A-Fa-f]{1,3})\b"))

    def test_detects_sibling_source_references_from_context(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["slips"],
            ecosystem_slug="bitcoin",
            source_slug="slips",
        )

        result = create_reference_list(
            "SLIP-0132 registers version bytes for BIP-0032 and BIPs 39 and 44.",
            proposal_label="SLIP",
            reference_pattern=r"\bSLIP[-#\s]?(\d+)\b",
            source_context=context,
        )

        self.assertEqual(result, ["BIP 32", "BIP 39", "BIP 44", "SLIP 132"])


class CreateReferenceTargetsTests(unittest.TestCase):
    def test_counts_repeated_regex_references_by_target(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = create_reference_targets(
            "BIP 32 references BIP-32 and BIPs 32 and 39.",
            proposal_label="BIP",
            reference_pattern=r"\bBIP[-#\s]?(\d+)\b",
            source_context=context,
        )

        self.assertEqual(
            result,
            [{"target": "bips:32", "count": 3}, {"target": "bips:39", "count": 1}],
        )

    def test_counts_mixed_bip_reference_syntax_variants(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = create_reference_targets(
            """
            This proposal cites BIP 32, BIP-32, BIP #32, BIP - 32, and BIP32.
            It also references BIPs 33 and 99, BIPs 33/99, and bip-99.
            It points implementers to SLIP-0132 for registered version bytes.
            BIP 1000 is outside the configured BIP range and should be ignored.
            """,
            proposal_label="BIP",
            reference_pattern=r"\bBIP[-#\s]?(\d+)\b",
            source_context=context,
        )

        self.assertEqual(
            result,
            [
                {"target": "bips:32", "count": 5},
                {"target": "bips:33", "count": 2},
                {"target": "bips:99", "count": 3},
                {"target": "slips:132", "count": 1},
            ],
        )

    def test_detects_sibling_source_targets(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["slips"],
            ecosystem_slug="bitcoin",
            source_slug="slips",
        )

        result = create_reference_targets(
            "SLIP-0132 registers version bytes for BIP-0032 and BIPs 39 and 44.",
            proposal_label="SLIP",
            reference_pattern=r"\bSLIP[-#\s]?(\d+)\b",
            source_context=context,
        )

        self.assertEqual(
            result,
            [
                {"target": "bips:32", "count": 1},
                {"target": "bips:39", "count": 1},
                {"target": "bips:44", "count": 1},
                {"target": "slips:132", "count": 1},
            ],
        )


class CreateExplicitDependencyTargetsTests(unittest.TestCase):
    def test_keeps_preamble_dependency_subtypes(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = create_explicit_dependency_targets(
            {"requires": "BIP 32, SLIP-0132", "replaces": "1"},
            proposal_label="BIP",
            source_context=context,
        )

        self.assertEqual(
            result,
            [
                {"target": "bips:32", "type": "requires"},
                {"target": "slips:132", "type": "requires"},
                {"target": "bips:1", "type": "replaces"},
            ],
        )

    def test_uses_source_configured_preamble_interrelation_types(self):
        context = SourceContext.from_config(
            {
                "proposal_acronym": "XIP",
                "reference_pattern": r"\bXIP[-#\s]?(\d+)\b",
                "preamble": {"interrelation_types": ["depends_on"]},
            },
            source_slug="xips",
        )

        result = create_explicit_dependency_targets(
            {"depends_on": "XIP 7", "requires": "XIP 8"},
            proposal_label="XIP",
            source_context=context,
        )

        self.assertEqual(result, [{"target": "xips:7", "type": "depends_on"}])


class PrepareLlmDependencyTextTests(unittest.TestCase):
    def test_strips_leading_pre_block(self):
        raw = "<pre>\nBIP: 1\nTitle: Test\n</pre>\nThis is the body."
        result = prepare_llm_dependency_text(raw)
        self.assertNotIn("<pre>", result)
        self.assertIn("This is the body.", result)

    def test_strips_leading_fenced_code_block(self):
        raw = "```\nBIP: 1\nTitle: Test\n```\nThis is the body."
        result = prepare_llm_dependency_text(raw)
        self.assertNotIn("```", result)
        self.assertIn("This is the body.", result)

    def test_empty_input_returns_empty(self):
        self.assertEqual(prepare_llm_dependency_text(""), "")

    def test_content_without_preamble_block_is_unchanged(self):
        text = "Just plain content with no preamble block."
        self.assertEqual(prepare_llm_dependency_text(text), text)


class LlmModelConfigTests(unittest.TestCase):
    def test_rate_limit_retry_retries_and_uses_retry_after(self):
        attempts = {"count": 0}

        class FakeRateLimitError(Exception):
            def __init__(self, retry_after=None):
                headers = {}
                if retry_after is not None:
                    headers["retry-after"] = str(retry_after)
                self.response = types.SimpleNamespace(headers=headers)

        def flaky_call():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise FakeRateLimitError(retry_after=2.0)
            return "ok"

        with (
            patch("analysis.dependencies.mining.RateLimitError", FakeRateLimitError),
            patch("analysis.dependencies.mining.time.sleep") as sleep,
        ):
            result = _call_with_rate_limit_retry(flaky_call)

        self.assertEqual(result, "ok")
        self.assertEqual(attempts["count"], 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2.0, 2.0])

    def test_manifest_record_preserves_shared_prompt_provenance(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        record = build_llm_semantic_dependency_manifest_record(
            run_id="run-123",
            model="gpt-5.4-mini",
            source_context=context,
            created_at="2026-06-30T12:00:00Z",
            focus=["32", "39"],
        )

        self.assertEqual(record["run_id"], "run-123")
        self.assertEqual(
            record["method_name"], "llm_assisted_semantic_dependency_extraction"
        )
        self.assertEqual(
            record["method_label"], "LLM-Assisted Semantic Dependency Extraction"
        )
        self.assertEqual(record["method_version"], 4)
        self.assertEqual(record["source_context"]["source_slug"], "bips")
        self.assertIn("{proposal_text}", record["user_prompt_template"])
        self.assertIn("{current_proposal_number}", record["user_prompt_template"])
        self.assertIn("Do not use outside knowledge", record["system_prompt"])
        self.assertIn(
            "verbatim contiguous quote copied from the proposal text",
            record["system_prompt"],
        )
        self.assertIn("MAIN_LABEL", record["system_prompt"])
        self.assertIn("main_source", record["system_prompt"])
        self.assertIn(
            "fully implemented with the following changes",
            record["user_prompt_template"],
        )
        self.assertIn(
            "does not require full MAIN_LABEL 70 support",
            record["user_prompt_template"],
        )
        self.assertIn(
            "schemes following MAIN_LABEL 44 should use purpose value 44'",
            record["user_prompt_template"],
        )
        self.assertIn(
            "master node generation from MAIN_LABEL-0032 and SIBLING_LABEL-0010",
            record["user_prompt_template"],
        )

    def test_llm_extraction_requires_configured_model(self):
        context = SourceContext.from_config(
            {
                "proposal_acronym": "BIP",
                "proposal_term_singular": "Bitcoin Improvement Proposal",
                "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
            }
        )

        with self.assertRaisesRegex(RuntimeError, "No LLM model configured"):
            llm_extract_implicit_dependencies(
                "This proposal depends on BIP 32.",
                api_key="test-key",
                source_context=context,
            )

    def test_llm_fallback_json_errors_are_wrapped(self):
        context = SourceContext.from_config(
            {
                "proposal_acronym": "BIP",
                "proposal_term_singular": "Bitcoin Improvement Proposal",
                "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
            },
            source_slug="bips",
        )

        def create_completion(**kwargs):
            if kwargs["response_format"]["type"] == "json_schema":
                raise TypeError("structured outputs unsupported")
            message = types.SimpleNamespace(content="{not json", refusal=None)
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=message)]
            )

        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create_completion)
            )
        )

        with patch("analysis.dependencies.mining.OpenAI", return_value=client):
            with self.assertRaisesRegex(
                RuntimeError, "failed with status `parse_error`"
            ):
                llm_extract_implicit_dependencies(
                    "This proposal depends on BIP 32.",
                    api_key="test-key",
                    model="test-model",
                    source_context=context,
                )

    def test_semantic_extraction_returns_parse_error_status(self):
        context = SourceContext.from_config(
            {
                "proposal_acronym": "BIP",
                "proposal_term_singular": "Bitcoin Improvement Proposal",
                "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
            },
            source_slug="bips",
        )

        def create_completion(**kwargs):
            if kwargs["response_format"]["type"] == "json_schema":
                raise TypeError("structured outputs unsupported")
            message = types.SimpleNamespace(content="{not json", refusal=None)
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=message)]
            )

        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create_completion)
            )
        )

        with patch("analysis.dependencies.mining.OpenAI", return_value=client):
            result = llm_extract_semantic_dependencies(
                "This proposal depends on BIP 32.",
                api_key="test-key",
                model="test-model",
                source_context=context,
            )

        self.assertEqual(result["status"], "parse_error")
        self.assertEqual(result["dependencies"], [])
        self.assertIn("Expecting property name", result["error_message"])

    def test_responses_api_reasoning_path_uses_responses_client_with_default_reasoning(
        self,
    ):
        source_config = {
            "proposal_acronym": "BIP",
            "proposal_term_singular": "Bitcoin Improvement Proposal",
            "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
        }
        ecosystem = {
            "slug": "testcoin",
            "llm": {"model": "reasoning-model", "reasoning_effort": None},
            "sources": {"bips": source_config},
        }
        context = SourceContext.from_config(
            source_config, ecosystem_slug="testcoin", source_slug="bips"
        )
        calls = []

        def create_response(**kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(
                output_text='{"dependencies":[{"target":"bips:32"}]}'
            )

        client = types.SimpleNamespace(
            responses=types.SimpleNamespace(create=create_response)
        )

        with (
            patch.dict(
                "pipeline.source_context.ECOSYSTEM_REGISTRY",
                {"testcoin": ecosystem},
                clear=False,
            ),
            patch("analysis.dependencies.mining.OpenAI", return_value=client),
        ):
            result = llm_extract_implicit_dependencies(
                "This proposal depends on BIP 32.",
                api_key="test-key",
                source_context=context,
            )

        self.assertEqual(result[0]["target"], "bips:32")
        self.assertEqual(calls[0]["model"], "reasoning-model")
        self.assertIn("input", calls[0])
        self.assertIn("text", calls[0])
        self.assertNotIn("reasoning", calls[0])


class NormalizeLlmDependencyOutputTests(unittest.TestCase):
    def test_returns_source_aware_dependency_targets(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = normalize_llm_dependency_output(
            [
                {
                    "target": "BIP 32",
                },
                {
                    "target": "slips:132",
                },
            ],
            proposal_label="BIP",
            current_proposal_number="1",
            source_context=context,
        )

        self.assertEqual(
            [entry["target"] for entry in result], ["bips:32", "slips:132"]
        )
        self.assertTrue(all("_label" not in entry for entry in result))

    def test_excludes_current_proposal_and_deduplicates_targets(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = normalize_llm_dependency_output(
            [
                {"target": "bips:32"},
                {"target": "BIP-39"},
                {"target": "bips:39"},
            ],
            proposal_label="BIP",
            current_proposal_number="32",
            source_context=context,
        )

        self.assertEqual([entry["target"] for entry in result], ["bips:39"])


if __name__ == "__main__":
    unittest.main()
