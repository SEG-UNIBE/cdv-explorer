import unittest

from analysis.dependencies.metrics import build_graph, extract_dependency_metrics
from analysis.dependencies.network import (
    build_network_data,
    collapse_network_data_to_llm_model,
)
from analysis.pipeline import combined_source_key, merge_source_network_data
from analysis.validation.ground_truth import (
    load_ground_truth_curated_entries,
    load_ground_truth_ips,
    validate_ground_truth_curated_entries,
    validate_reviewed_ip_entries,
)
from ecosystems import ECOSYSTEM_REGISTRY
from pipeline.source_context import SourceContext
from tests.helpers import proposal as _proposal


class BuildNetworkDataTests(unittest.TestCase):
    def _build(self, proposals, **kwargs):
        kwargs.setdefault("ground_truth_entries", [])
        kwargs.setdefault("reviewed_ips_entries", [])
        return build_network_data(proposals, **kwargs)

    def test_link_created_when_both_nodes_exist(self):
        result = self._build(
            [_proposal("1", regex_refs=["BIP 2"]), _proposal("2")],
            id_field="bip",
            proposal_label="BIP",
        )
        edges = result["dependency_edges"]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["source"], "bips:1")
        self.assertEqual(edges[0]["target"], "bips:2")
        self.assertEqual(edges[0]["extraction_method"], "body_extracted_regex")
        self.assertNotIn("links", result)

    def test_generator_input_still_creates_edges(self):
        proposals = (
            _proposal(value, regex_refs=["BIP 2"] if value == "1" else [])
            for value in ["1", "2"]
        )

        result = self._build(proposals, id_field="bip", proposal_label="BIP")

        self.assertEqual(
            result["dependency_edges"],
            [
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                }
            ],
        )

    def test_dependency_edges_use_source_safe_graph_keys(self):
        source_context = SourceContext.from_config(
            {"classification": {"dimensions": {}}},
            source_slug="bips",
        )
        result = self._build(
            [_proposal("1", regex_refs=["BIP 2"], requires=["BIP 2"]), _proposal("2")],
            id_field="bip",
            proposal_label="BIP",
            source_context=source_context,
        )

        self.assertEqual(result["nodes"][0]["graph_key"], "bips:1")
        self.assertIn(
            {
                "source": "bips:1",
                "target": "bips:2",
                "extraction_method": "body_extracted_regex",
                "relation_type": "reference",
                "value": 1,
            },
            result["dependency_edges"],
        )
        self.assertIn(
            {
                "source": "bips:1",
                "target": "bips:2",
                "extraction_method": "preamble_extracted",
                "relation_type": "requires",
                "value": 1,
            },
            result["dependency_edges"],
        )

    def test_rich_llm_dependencies_create_source_aware_edges(self):
        source_context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )

        result = self._build(
            [
                _proposal(
                    "1",
                    llm_deps=[
                        {
                            "target": "slips:132",
                        }
                    ],
                )
            ],
            id_field="bip",
            proposal_label="BIP",
            source_context=source_context,
            known_proposal_ids_by_source={"slips": {"132"}},
        )

        self.assertTrue(
            any(
                edge.get("source") == "bips:1"
                and edge.get("target") == "slips:132"
                and edge.get("extraction_method") == "body_extracted_llm"
                and edge.get("relation_type") == "references"
                and edge.get("value") == 1
                and edge.get("llm_model") == "test-model"
                for edge in result["dependency_edges"]
            )
        )
        self.assertNotIn("links", result)

    def test_llm_model_variants_are_exposed_per_model(self):
        source_context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )
        configured_model = source_context.llm_model
        self.assertIsNotNone(configured_model)
        proposal = {
            "raw": {"preamble": {"bip": "1", "title": "Proposal 1", "status": "Draft"}},
            "insights": {
                "interrelations": {
                    "body_extracted_regex": [],
                    "body_extracted_llm": [
                        {
                            "model": "gpt-5.4-mini",
                            "timestamp": "2026-06-01T00:00:00Z",
                            "status": "success",
                            "findings": [{"target": "bips:2"}],
                        },
                        {
                            "model": configured_model,
                            "timestamp": "2026-06-02T00:00:00Z",
                            "status": "success",
                            "findings": [],
                        },
                    ],
                    "preamble_extracted": [],
                }
            },
        }

        result = self._build(
            [proposal, _proposal("2")],
            id_field="bip",
            proposal_label="BIP",
            source_context=source_context,
        )

        self.assertEqual(result["llm_models"]["default_model"], configured_model)
        self.assertEqual(
            [entry["model"] for entry in result["llm_models"]["available_models"]],
            sorted([configured_model, "gpt-5.4-mini"]),
        )
        self.assertEqual(
            result["llm_models"]["dependency_edges_by_model"][configured_model], []
        )
        self.assertEqual(
            result["llm_models"]["dependency_edges_by_model"]["gpt-5.4-mini"],
            [
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "body_extracted_llm",
                    "relation_type": "references",
                    "value": 1,
                    "llm_model": "gpt-5.4-mini",
                    "evidence": None,
                    "reason": None,
                    "confidence": None,
                }
            ],
        )

    def test_source_qualified_references_create_cross_source_edges(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["slips"],
            ecosystem_slug="bitcoin",
            source_slug="slips",
        )
        slip_132 = {
            "raw": {
                "preamble": {
                    "slip": "132",
                    "title": "Registered HD version bytes for BIP-0032",
                }
            },
            "insights": {
                "interrelations": {
                    "body_extracted_regex": [
                        {"target": "bips:32", "count": 1},
                        {"target": "slips:32", "count": 1},
                    ],
                    "body_extracted_llm": [],
                    "preamble_extracted": [],
                }
            },
        }
        slip_32 = {
            "raw": {
                "preamble": {
                    "slip": "32",
                    "title": "Extended serialization format for BIP-32 wallets",
                }
            },
            "insights": {
                "interrelations": {
                    "body_extracted_regex": [],
                    "body_extracted_llm": [],
                    "preamble_extracted": [],
                }
            },
        }

        result = self._build(
            [slip_132, slip_32],
            id_field="slip",
            proposal_label="SLIP",
            source_context=context,
            known_proposal_ids_by_source={"bips": {"32"}, "slips": {"32", "132"}},
        )

        self.assertIn(
            {
                "source": "slips:132",
                "target": "bips:32",
                "extraction_method": "body_extracted_regex",
                "relation_type": "reference",
                "value": 1,
            },
            result["dependency_edges"],
        )
        self.assertIn(
            {
                "source": "slips:132",
                "target": "slips:32",
                "extraction_method": "body_extracted_regex",
                "relation_type": "reference",
                "value": 1,
            },
            result["dependency_edges"],
        )

    def test_ground_truth_curated_edges_are_imported_for_matching_source(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )
        result = self._build(
            [_proposal("44"), _proposal("32")],
            id_field="bip",
            proposal_label="BIP",
            source_context=context,
            known_proposal_ids_by_source={"bips": {"44", "32"}, "slips": {"44"}},
            ground_truth_entries=[
                {
                    "source": "bips:44",
                    "target": "bips:32",
                    "relation_type": "depends_on",
                    "confidence": "high",
                    "evidence": "Requires: 32",
                    "note": "Declared in preamble",
                    "reviewer": "rbo",
                    "reviewed_at": "2026-06-22",
                },
                {
                    "source": "slips:44",
                    "target": "bips:44",
                    "relation_type": "references",
                },
            ],
        )

        self.assertIn(
            {
                "source": "bips:44",
                "target": "bips:32",
                "extraction_method": "ground_truth_curated",
                "relation_type": "depends_on",
                "value": 1,
                "confidence": "high",
                "evidence": "Requires: 32",
                "note": "Declared in preamble",
                "reviewer": "rbo",
                "reviewed_at": "2026-06-22",
            },
            result["dependency_edges"],
        )
        self.assertEqual(
            [
                edge
                for edge in result["dependency_edges"]
                if edge["extraction_method"] == "ground_truth_curated"
            ],
            [
                {
                    "source": "bips:44",
                    "target": "bips:32",
                    "extraction_method": "ground_truth_curated",
                    "relation_type": "depends_on",
                    "value": 1,
                    "confidence": "high",
                    "evidence": "Requires: 32",
                    "note": "Declared in preamble",
                    "reviewer": "rbo",
                    "reviewed_at": "2026-06-22",
                }
            ],
        )

    def test_ground_truth_csv_loader_trims_headers_and_skips_comments(self):
        rows = load_ground_truth_curated_entries("bitcoin", strict=False)

        self.assertTrue(rows)
        self.assertEqual(rows[0]["reviewed_at"], "2026-08-07")
        self.assertIn("relation_type", rows[0])
        self.assertNotIn("reviewed_at ", rows[0])

    def test_ground_truth_validation_rejects_duplicates_and_unknown_sources(self):
        errors = validate_ground_truth_curated_entries(
            [
                {
                    "source": "bips:44",
                    "target": "bips:32",
                    "relation_type": "depends_on",
                    "reviewer": "test-reviewer",
                    "__line__": 2,
                },
                {
                    "source": "bips:44",
                    "target": "bips:32",
                    "relation_type": "depends_on",
                    "reviewer": "test-reviewer",
                    "__line__": 3,
                },
                {
                    "source": "bips:44",
                    "target": "bips:32",
                    "relation_type": "supersedes",
                    "reviewer": "test-reviewer",
                    "__line__": 4,
                },
                {
                    "source": "bogus:1",
                    "target": "bips:32",
                    "relation_type": "depends_on",
                    "reviewer": "test-reviewer",
                    "__line__": 5,
                },
            ],
            source_configs_by_slug={
                "bips": {
                    "source_slug": "bips",
                    "proposal_label": "BIP",
                    "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
                    "max_proposal_id": 9999,
                }
            },
        )

        error_text = "\n".join(errors)
        self.assertIn("duplicate curated edge", error_text)
        self.assertIn("conflicting relation types", error_text)
        self.assertIn("unknown source slug `bogus`", error_text)

    def test_ips_loader_trims_headers_and_skips_comments(self):
        rows = load_ground_truth_ips("bitcoin", strict=False)

        self.assertIsInstance(rows, list)

    def test_reviewed_ips_validation_rejects_duplicates_and_bad_dates(self):
        errors = validate_reviewed_ip_entries(
            [
                {
                    "ip": "bips:44",
                    "reviewer": "test-reviewer",
                    "reviewed_at": "2026-06-22",
                    "__line__": 2,
                },
                {
                    "ip": "bips:44",
                    "reviewer": "test-reviewer",
                    "reviewed_at": "2026-06-23",
                    "__line__": 3,
                },
                {
                    "ip": "oops",
                    "reviewer": "test-reviewer",
                    "reviewed_at": "2026-99-99",
                    "__line__": 4,
                },
            ],
            source_configs_by_slug={
                "bips": {
                    "source_slug": "bips",
                    "proposal_label": "BIP",
                    "reference_pattern": r"\bBIP[-#\s]?(\d+)\b",
                    "max_proposal_id": 9999,
                }
            },
        )

        error_text = "\n".join(errors)
        self.assertIn("duplicate reviewed IP", error_text)
        self.assertIn("must use source_slug:id format", error_text)
        self.assertIn("invalid `reviewed_at` date `2026-99-99`", error_text)

    def test_ground_truth_reviewed_ips_are_imported_for_matching_source(self):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["bips"],
            ecosystem_slug="bitcoin",
            source_slug="bips",
        )
        result = self._build(
            [_proposal("44"), _proposal("32")],
            id_field="bip",
            proposal_label="BIP",
            source_context=context,
            reviewed_ips_entries=[
                {
                    "ip": "bips:44",
                    "reviewer": "rbo",
                    "reviewed_at": "2026-06-24",
                    "sampling_strategy": "manual",
                },
                {
                    "ip": "slips:44",
                    "reviewed_at": "2026-06-24",
                },
            ],
        )

        self.assertEqual(
            result["ground_truth_reviewed_ips"],
            [
                {
                    "ip": "bips:44",
                    "proposal_id": "44",
                    "source_slug": "bips",
                    "reviewer": "rbo",
                    "reviewed_at": "2026-06-24",
                    "sampling_strategy": "manual",
                    "sampling_snapshot": None,
                    "sampling_seed": None,
                    "era_bucket": None,
                    "density_bucket": None,
                    "density_basis": None,
                    "created": None,
                    "status": None,
                    "type": None,
                    "layer": None,
                    "title": None,
                    "extracted_target_count": None,
                    "note": None,
                }
            ],
        )

    def test_unknown_cross_source_targets_are_excluded_when_known_ids_are_available(
        self,
    ):
        context = SourceContext.from_config(
            ECOSYSTEM_REGISTRY["bitcoin"]["sources"]["slips"],
            ecosystem_slug="bitcoin",
            source_slug="slips",
        )
        result = self._build(
            [
                {
                    "raw": {
                        "preamble": {
                            "slip": "132",
                            "title": "Registered HD version bytes",
                        }
                    },
                    "insights": {
                        "interrelations": {
                            "body_extracted_regex": [
                                {"target": "bips:999", "count": 1}
                            ],
                            "body_extracted_llm": [],
                            "preamble_extracted": [],
                        }
                    },
                }
            ],
            id_field="slip",
            proposal_label="SLIP",
            source_context=context,
            known_proposal_ids_by_source={"bips": {"32"}, "slips": {"132"}},
        )

        self.assertEqual(result["dependency_edges"], [])

    def test_dependency_metrics_use_canonical_edges_when_present(self):
        network_data = {
            "nodes": [
                {"id": "1", "graph_key": "bips:1", "title": "Proposal 1"},
                {"id": "2", "graph_key": "bips:2", "title": "Proposal 2"},
            ],
            "dependency_edges": [
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "preamble_extracted",
                    "relation_type": "requires",
                    "value": 1,
                }
            ],
        }

        metrics = extract_dependency_metrics(network_data)

        self.assertEqual(
            metrics["by_approach"]["preamble_extracted"]["summary"]["edge_count"], 1
        )
        per_bip_ids = {
            row["id"] for row in metrics["by_approach"]["preamble_extracted"]["per_bip"]
        }
        self.assertEqual(per_bip_ids, {"bips:1", "bips:2"})

    def test_dependency_metrics_precompute_rank_fields(self):
        network_data = {
            "nodes": [
                {"id": "1", "graph_key": "bips:1", "title": "BIP 1"},
                {"id": "2", "graph_key": "bips:2", "title": "BIP 2"},
                {"id": "3", "graph_key": "bips:3", "title": "BIP 3"},
            ],
            "dependency_edges": [
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                },
                {
                    "source": "bips:3",
                    "target": "bips:2",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                },
            ],
        }

        metrics = extract_dependency_metrics(network_data)
        rows = {
            row["id"]: row
            for row in metrics["by_approach"]["body_extracted_regex"]["per_bip"]
        }

        self.assertEqual(rows["bips:2"]["in_degree_rank"], 1)
        self.assertEqual(rows["bips:1"]["in_degree_rank"], 2)
        self.assertEqual(rows["bips:3"]["in_degree_rank"], 2)
        self.assertEqual(rows["bips:1"]["out_degree_rank"], 1)
        self.assertEqual(rows["bips:3"]["out_degree_rank"], 1)
        self.assertEqual(rows["bips:2"]["out_degree_rank"], 3)
        self.assertIn("pagerank_rank", rows["bips:1"])
        self.assertIn("betweenness_rank", rows["bips:1"])
        self.assertIn("weighted_eigenvector_rank", rows["bips:1"])

    def test_dependency_metrics_pairwise_agreement_scores(self):
        network_data = {
            "nodes": [
                {"id": str(i), "graph_key": f"bips:{i}", "title": f"BIP {i}"}
                for i in range(1, 5)
            ],
            "dependency_edges": [
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "preamble_extracted",
                    "relation_type": "requires",
                    "value": 1,
                },
                {
                    "source": "bips:1",
                    "target": "bips:3",
                    "extraction_method": "preamble_extracted",
                    "relation_type": "requires",
                    "value": 1,
                },
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                },
                {
                    "source": "bips:2",
                    "target": "bips:3",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                },
            ],
        }

        metrics = extract_dependency_metrics(network_data)
        summary = metrics["pairwise_comparisons"][
            "body_extracted_regex__vs__preamble_extracted"
        ]["summary"]

        # 4 nodes -> 12 candidate ordered pairs; a=1 shared, b=1, c=1, d=9.
        # p_o = 10/12, p_e = (2*2 + 10*10)/144 -> kappa = 0.4 exactly.
        self.assertEqual(summary["candidate_pairs"], 12)
        self.assertAlmostEqual(summary["kappa"], 0.4)

        diagonal = metrics["pairwise_comparisons"][
            "preamble_extracted__vs__preamble_extracted"
        ]["summary"]
        self.assertAlmostEqual(diagonal["kappa"], 1.0)

        empty = metrics["pairwise_comparisons"][
            "body_extracted_llm__vs__body_extracted_llm"
        ]["summary"]
        self.assertIsNone(empty["kappa"])

    def test_dependency_metrics_pairwise_exact_type_scope_matches_by_canonical_type(self):
        network_data = {
            "nodes": [
                {"id": str(i), "graph_key": f"bips:{i}", "title": f"BIP {i}"}
                for i in range(1, 4)
            ],
            "dependency_edges": [
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "preamble_extracted",
                    "relation_type": "requires",
                    "value": 1,
                },
                {
                    "source": "bips:1",
                    "target": "bips:3",
                    "extraction_method": "preamble_extracted",
                    "relation_type": "replaces",
                    "value": 1,
                },
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "body_extracted_llm",
                    "relation_type": "depends_on",
                    "value": 1,
                },
                {
                    "source": "bips:2",
                    "target": "bips:3",
                    "extraction_method": "body_extracted_llm",
                    "relation_type": "references",
                    "value": 1,
                },
            ],
        }

        metrics = extract_dependency_metrics(network_data)

        # "All types" ignores relation_type: preamble has 2 edges (requires +
        # replaces), LLM has 2 (depends_on + references).
        unscoped = metrics["pairwise_comparisons"][
            "body_extracted_llm__vs__preamble_extracted"
        ]["summary"]
        self.assertEqual(unscoped["approach_total"], 2)
        self.assertEqual(unscoped["baseline_total"], 2)

        # "Exact type" keeps every subtype but tags each with its canonical
        # type (requires->depends_on, replaces->supersedes, LLM depends_on/
        # references pass through unchanged): both approaches keep all their
        # edges, but only the bips:1->2 depends_on-typed edge matches on both
        # sides, since preamble's supersedes-typed edge and the LLM's
        # references-typed edge don't share a canonical type with anything
        # on the other side.
        scoped = metrics["pairwise_comparisons_exact_type"][
            "body_extracted_llm__vs__preamble_extracted"
        ]["summary"]
        self.assertEqual(scoped["approach_total"], 2)
        self.assertEqual(scoped["baseline_total"], 2)
        self.assertEqual(scoped["overlap"], 1)
        self.assertEqual(scoped["approach_only"], 1)
        self.assertEqual(scoped["baseline_only"], 1)

    def test_dependency_metrics_pairwise_exact_type_wildcard_resolves_against_other_side(self):
        network_data = {
            "nodes": [
                {"id": str(i), "graph_key": f"bips:{i}", "title": f"BIP {i}"}
                for i in range(1, 4)
            ],
            "dependency_edges": [
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "preamble_extracted",
                    "relation_type": "requires",
                    "value": 1,
                },
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                },
                {
                    "source": "bips:2",
                    "target": "bips:3",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                },
            ],
        }

        metrics = extract_dependency_metrics(network_data)

        # Regex has no real type signal, so its bips:1->2 hit resolves
        # against whatever canonical type preamble recorded there
        # (requires -> depends_on) and counts as a match. Its bips:2->3 hit
        # has nothing to resolve against on the preamble side, so exact-type
        # comparison expands it to every canonical relation type in the typed
        # (source, target, type) candidate universe.
        scoped = metrics["pairwise_comparisons_exact_type"][
            "body_extracted_regex__vs__preamble_extracted"
        ]["summary"]
        self.assertEqual(scoped["candidate_pairs"], 24)
        self.assertEqual(scoped["approach_total"], 5)
        self.assertEqual(scoped["baseline_total"], 1)
        self.assertEqual(scoped["overlap"], 1)
        self.assertEqual(scoped["approach_only"], 4)
        self.assertEqual(scoped["baseline_only"], 0)
        scoped_edges = metrics["pairwise_comparisons_exact_type"][
            "body_extracted_regex__vs__preamble_extracted"
        ]["edges"]
        self.assertTrue(
            any(
                edge["source"] == "bips:2"
                and edge["target"] == "bips:3"
                and edge["relation_type"] == "references"
                and edge["status"] == "approach_only"
                for edge in scoped_edges
            )
        )

        # Regex compared against itself: both sides are wildcard-only, so the
        # same typed expansion happens on both sides and still agrees with
        # itself perfectly (kappa == 1.0).
        diagonal = metrics["pairwise_comparisons_exact_type"][
            "body_extracted_regex__vs__body_extracted_regex"
        ]["summary"]
        self.assertEqual(diagonal["candidate_pairs"], 24)
        self.assertEqual(diagonal["approach_total"], 8)
        self.assertEqual(diagonal["baseline_total"], 8)
        self.assertEqual(diagonal["overlap"], 8)
        self.assertEqual(diagonal["approach_only"], 0)
        self.assertEqual(diagonal["baseline_only"], 0)
        self.assertAlmostEqual(diagonal["kappa"], 1.0)

    def test_dependency_metrics_preserve_duplicate_ids_across_sources(self):
        network_data = {
            "nodes": [
                {"id": "32", "graph_key": "bips:32", "title": "BIP 32"},
                {"id": "32", "graph_key": "slips:32", "title": "SLIP 32"},
                {"id": "132", "graph_key": "slips:132", "title": "SLIP 132"},
            ],
            "dependency_edges": [
                {
                    "source": "bips:32",
                    "target": "slips:132",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                },
                {
                    "source": "slips:32",
                    "target": "slips:132",
                    "extraction_method": "body_extracted_regex",
                    "relation_type": "reference",
                    "value": 1,
                },
            ],
        }

        metrics = extract_dependency_metrics(network_data)
        per_bip_ids = {
            row["id"]
            for row in metrics["by_approach"]["body_extracted_regex"]["per_bip"]
        }

        self.assertEqual(per_bip_ids, {"bips:32", "slips:32", "slips:132"})

    def test_dependency_metrics_include_llm_model_variants(self):
        network_data = {
            "nodes": [
                {"id": "1", "graph_key": "bips:1", "title": "BIP 1"},
                {"id": "2", "graph_key": "bips:2", "title": "BIP 2"},
            ],
            "dependency_edges": [
                {
                    "source": "bips:1",
                    "target": "bips:2",
                    "extraction_method": "body_extracted_llm",
                    "relation_type": "depends_on",
                    "value": 1,
                    "llm_model": "gpt-5.4-mini",
                },
            ],
            "llm_models": {
                "default_model": "gpt-5.4-mini",
                "available_models": [
                    {"model": "gpt-5.4", "document_count": 1, "edge_count": 0},
                    {"model": "gpt-5.4-mini", "document_count": 1, "edge_count": 1},
                ],
                "dependency_edges_by_model": {
                    "gpt-5.4": [],
                    "gpt-5.4-mini": [
                        {
                            "source": "bips:1",
                            "target": "bips:2",
                            "extraction_method": "body_extracted_llm",
                            "relation_type": "depends_on",
                            "value": 1,
                            "llm_model": "gpt-5.4-mini",
                        }
                    ],
                },
            },
        }

        metrics = extract_dependency_metrics(network_data)

        self.assertEqual(metrics["llm_models"]["default_model"], "gpt-5.4-mini")
        self.assertEqual(
            metrics["llm_models"]["by_model"]["gpt-5.4"]["by_approach"][
                "body_extracted_llm"
            ]["summary"]["edge_count"],
            0,
        )
        self.assertEqual(
            metrics["llm_models"]["by_model"]["gpt-5.4-mini"]["by_approach"][
                "body_extracted_llm"
            ]["summary"]["edge_count"],
            1,
        )

    def test_collapse_network_data_to_published_llm_model(self):
        network_data = {
            "nodes": [
                {"id": "1", "graph_key": "bips:1", "title": "BIP 1"},
                {"id": "2", "graph_key": "bips:2", "title": "BIP 2"},
            ],
            "dependency_edges": [],
            "llm_models": {
                "default_model": "gpt-5.4-mini",
                "available_models": [
                    {"model": "gpt-5.4", "document_count": 1, "edge_count": 0},
                    {"model": "gpt-5.4-mini", "document_count": 1, "edge_count": 1},
                ],
                "dependency_edges_by_model": {
                    "gpt-5.4": [],
                    "gpt-5.4-mini": [
                        {
                            "source": "bips:1",
                            "target": "bips:2",
                            "extraction_method": "body_extracted_llm",
                            "relation_type": "depends_on",
                            "value": 1,
                            "llm_model": "gpt-5.4-mini",
                        }
                    ],
                },
            },
        }

        collapsed = collapse_network_data_to_llm_model(network_data, "gpt-5.4-mini")
        metrics = extract_dependency_metrics(collapsed)

        self.assertEqual(collapsed["llm_model"], "gpt-5.4-mini")
        self.assertNotIn("llm_models", collapsed)
        self.assertEqual(len(collapsed["dependency_edges"]), 1)
        self.assertEqual(metrics["llm_model"], "gpt-5.4-mini")
        self.assertNotIn("llm_models", metrics)
        self.assertEqual(
            metrics["by_approach"]["body_extracted_llm"]["summary"]["edge_count"],
            1,
        )

    def test_merge_source_network_data_preserves_source_scoped_nodes_and_edges(self):
        self.assertEqual(combined_source_key(["slips", "bips"]), "bips+slips")

        merged = merge_source_network_data(
            [
                (
                    "bips",
                    {
                        "nodes": [
                            {"id": "32", "graph_key": "bips:32", "title": "BIP 32"}
                        ],
                        "dependency_edges": [
                            {
                                "source": "bips:32",
                                "target": "slips:132",
                                "extraction_method": "body_extracted_regex",
                                "relation_type": "reference",
                                "value": 1,
                            }
                        ],
                    },
                ),
                (
                    "slips",
                    {
                        "nodes": [
                            {"id": "32", "graph_key": "slips:32", "title": "SLIP 32"},
                            {
                                "id": "132",
                                "graph_key": "slips:132",
                                "title": "SLIP 132",
                            },
                        ],
                        "dependency_edges": [],
                    },
                ),
            ]
        )

        self.assertEqual(
            {node["graph_key"] for node in merged["nodes"]},
            {"bips:32", "slips:32", "slips:132"},
        )
        self.assertEqual(merged["meta"]["combination_key"], "bips+slips")
        self.assertEqual(merged["dependency_edges"][0]["source"], "bips:32")
        self.assertEqual(merged["dependency_edges"][0]["target"], "slips:132")

    def test_merge_source_network_data_requires_one_shared_published_llm_model(self):
        merged = merge_source_network_data(
            [
                (
                    "bips",
                    {
                        "nodes": [{"id": "1", "graph_key": "bips:1", "title": "BIP 1"}],
                        "dependency_edges": [],
                        "llm_model": "gpt-5.4-mini",
                    },
                ),
                (
                    "slips",
                    {
                        "nodes": [
                            {"id": "2", "graph_key": "slips:2", "title": "SLIP 2"}
                        ],
                        "dependency_edges": [],
                        "llm_model": "gpt-5.4-mini",
                    },
                ),
            ]
        )

        self.assertEqual(merged["llm_model"], "gpt-5.4-mini")

    def test_merge_source_network_data_omits_ambiguous_llm_model_label(self):
        # Each source's dependency edges are already resolved per-IP, so sources
        # publishing different default-model labels is expected (not an error) -
        # the combined artifact simply drops the label rather than picking one.
        combined = merge_source_network_data(
            [
                (
                    "bips",
                    {
                        "nodes": [
                            {"id": "1", "graph_key": "bips:1", "title": "BIP 1"}
                        ],
                        "dependency_edges": [],
                        "llm_model": "gpt-5.4-mini",
                    },
                ),
                (
                    "slips",
                    {
                        "nodes": [
                            {"id": "2", "graph_key": "slips:2", "title": "SLIP 2"}
                        ],
                        "dependency_edges": [],
                        "llm_model": "gpt-5.4",
                    },
                ),
            ]
        )

        self.assertNotIn("llm_model", combined)
        self.assertEqual(len(combined["nodes"]), 2)

    def test_dependency_metrics_can_filter_custom_preamble_relation_type(self):
        network_data = {
            "nodes": [
                {"id": "1", "graph_key": "xips:1", "title": "Proposal 1"},
                {"id": "2", "graph_key": "xips:2", "title": "Proposal 2"},
            ],
            "dependency_edges": [
                {
                    "source": "xips:1",
                    "target": "xips:2",
                    "extraction_method": "preamble_extracted",
                    "relation_type": "depends_on",
                    "value": 1,
                }
            ],
        }

        graph = build_graph(network_data, link_type="depends_on")

        self.assertEqual(list(graph.edges()), [("xips:1", "xips:2")])

    def test_link_to_unknown_node_excluded(self):
        result = self._build(
            [_proposal("1", regex_refs=["BIP 99"])],
            id_field="bip",
            proposal_label="BIP",
        )
        self.assertEqual(result["dependency_edges"], [])

    def test_llm_link_to_unknown_node_excluded(self):
        result = self._build(
            [_proposal("1", llm_deps=["BIP 99"])], id_field="bip", proposal_label="BIP"
        )
        self.assertEqual(result["dependency_edges"], [])

    def test_duplicate_proposal_ids_deduplicated(self):
        result = self._build(
            [_proposal("1"), _proposal("1")], id_field="bip", proposal_label="BIP"
        )
        self.assertEqual(len(result["nodes"]), 1)

    def test_first_day_git_committers_drive_network_author_fallback(self):
        history = [
            ("c4", "2022-05-04T09:00:00+00:00", "Later Author", "later@example.com"),
            ("c3", "2022-05-01T15:00:00+00:00", "First Day B", "b@example.com"),
            ("c2", "2022-05-01T09:00:00+00:00", "First Day A", "a@example.com"),
            ("c1", "2022-05-01T08:00:00+00:00", "GitHub", "noreply@github.com"),
        ]
        proposal = {
            "raw": {
                "preamble": {"nip": "01", "title": "Proposal 01", "status": "Draft"}
            },
            "meta": {"git_history": history},
            "insights": {
                "formal_compliance": {},
                "interrelations": {
                    "body_extracted_regex": [],
                    "body_extracted_llm": [],
                    "preamble_extracted": [],
                },
            },
        }

        result = self._build([proposal], id_field="nip", proposal_label="NIP")

        self.assertEqual(result["nodes"][0]["author"], ["First Day B", "First Day A"])


if __name__ == "__main__":
    unittest.main()
