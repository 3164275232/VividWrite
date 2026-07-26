import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from next_sentence import summarize_flowchart
from structure_feedback_agents import (
    OPTION_C_NODE_TYPES,
    StructureAnalysisRequest,
    StructureFeedbackOrchestrator,
    extract_nodes,
)


OPTION_C_FLOWCHART = {
    "nodes": [
        {
            "id": node_type,
            "type": node_type,
            "title": node_type.replace("_", " ").title(),
        }
        for node_type in OPTION_C_NODE_TYPES
    ],
    "edges": [],
}

COMPLETE_ESSAY = (
    "The line graph compares bus and rail passenger numbers between 2010 and 2020.\n\n"
    "Overall, rail use rose substantially, while bus use ended lower than it began.\n\n"
    "In 2010, buses carried 1.8 million passengers, compared with 1.1 million by rail.\n\n"
    "By 2020, rail had climbed to 2.2 million, whereas the bus figure fell to 1.3 million."
)


class StructureFeedbackAgentTests(unittest.TestCase):
    def analyze(self, text=COMPLETE_ESSAY, flowchart=OPTION_C_FLOWCHART):
        return StructureFeedbackOrchestrator(use_llm=False).analyze(
            StructureAnalysisRequest(
                current_text=text,
                flowchart=flowchart,
                chart_type="line",
                deplot_text="Year | Bus | Rail",
            )
        )

    def test_option_c_default_nodes_and_frontend_order(self):
        nodes = extract_nodes(None)
        self.assertEqual([node.type for node in nodes], OPTION_C_NODE_TYPES)

        frontend = (
            Path(__file__).resolve().parents[2] / "frontend" / "src" / "Flowchart.jsx"
        ).read_text(encoding="utf-8")
        positions = [
            frontend.index(f"id: '{node_type}'") for node_type in OPTION_C_NODE_TYPES
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn(
            "from: 'key_details_b', to: 'optional_commentary'",
            frontend,
        )

    def test_paragraph_and_sentence_mapping_uses_option_c(self):
        response = self.analyze()

        self.assertEqual(len(response.paragraphs), 4)
        self.assertEqual(
            [mapping.primary_node for mapping in response.paragraph_mappings],
            ["introduction", "overview", "key_details_a", "key_details_b"],
        )
        for paragraph in response.paragraphs:
            self.assertEqual(
                COMPLETE_ESSAY[paragraph.start : paragraph.end],
                paragraph.text,
            )
        self.assertTrue(all(sentence.end > sentence.start for sentence in response.sentences))

    def test_single_newlines_are_preserved_as_paragraph_boundaries(self):
        text = COMPLETE_ESSAY.replace("\n\n", "\n")
        response = self.analyze(text=text)

        self.assertEqual(len(response.paragraphs), 4)
        self.assertEqual(
            [mapping.primary_node for mapping in response.paragraph_mappings],
            ["introduction", "overview", "key_details_a", "key_details_b"],
        )

    def test_optional_commentary_is_not_required_for_completeness(self):
        response = self.analyze()

        self.assertTrue(response.structure_feedback.is_complete)
        self.assertEqual(response.missing_nodes, [])
        self.assertEqual(
            response.structure_feedback.summary,
            "Your essay includes all required Task 1 sections.",
        )
        self.assertNotIn("Option C", response.model_dump_json())
        self.assertNotIn(
            "optional_commentary",
            response.structure_feedback.missing_nodes,
        )

    def test_missing_overview_is_reported(self):
        text = (
            "The bar chart compares recycling rates in four cities.\n\n"
            "Bristol rose from 42% to 55%, while Leeds increased from 35% to 48%.\n\n"
            "Cardiff reached 60% in 2020, whereas London remained lower at 40%."
        )
        response = self.analyze(text=text)

        self.assertFalse(response.structure_feedback.is_complete)
        self.assertIn("overview", response.structure_feedback.missing_nodes)
        self.assertEqual([node.id for node in response.missing_nodes], ["overview"])

    def test_legacy_node_types_are_normalized(self):
        legacy = {
            "nodes": [
                {"id": "old-background", "type": "background"},
                {"id": "old-presentation", "type": "presentation"},
                {"id": "old-summary", "type": "summary"},
                {"id": "old-results", "type": "results"},
                {"id": "old-reference", "type": "reference_explanation"},
                {"id": "old-comment", "type": "comment"},
            ],
            "edges": [],
        }
        response = self.analyze(flowchart=legacy)
        normalized = {node.original_type: node.type for node in response.nodes}

        self.assertEqual(normalized["background"], "introduction")
        self.assertEqual(normalized["summary"], "overview")
        self.assertEqual(normalized["results"], "key_details_a")
        self.assertEqual(normalized["reference_explanation"], "key_details_b")
        self.assertEqual(normalized["comment"], "optional_commentary")
        self.assertEqual(
            response.paragraph_mappings[0].primary_node,
            "old-background",
        )
        summary = summarize_flowchart(legacy)
        self.assertIn("Introduction / Orient the Visual", summary)
        self.assertIn("Overview / Highlight Key Patterns", summary)
        self.assertNotIn("Presentation of Visual", summary)

    def test_invalid_agent_json_falls_back_without_failing(self):
        orchestrator = StructureFeedbackOrchestrator(
            llm_caller=lambda *_args: "this is not JSON"
        )
        response = orchestrator.analyze(
            StructureAnalysisRequest(
                current_text=COMPLETE_ESSAY,
                flowchart=OPTION_C_FLOWCHART,
            )
        )

        self.assertIsNone(response.error)
        self.assertTrue(response.structure_feedback.is_complete)
        self.assertEqual(len(response.agent_trace), 5)
        self.assertTrue(all(item.status == "fallback" for item in response.agent_trace))

    def test_custom_node_can_be_mapped_by_its_renamed_title(self):
        flowchart = {
            "nodes": OPTION_C_FLOWCHART["nodes"]
            + [
                {
                    "id": "custom-extremes",
                    "type": "custom",
                    "title": "Extreme values",
                }
            ],
            "edges": [],
        }
        text = COMPLETE_ESSAY.replace(
            "By 2020, rail had climbed",
            "The extreme values show that by 2020, rail had climbed",
        )
        response = self.analyze(text=text, flowchart=flowchart)

        custom_mapping = next(
            item
            for item in response.paragraph_mappings
            if item.paragraph_index == 3
        )
        self.assertEqual(custom_mapping.primary_node, "custom-extremes")
        self.assertNotIn(
            "custom-extremes",
            [item.id for item in response.missing_nodes],
        )

    def test_legacy_api_keeps_old_fields_and_adds_new_fields(self):
        client = TestClient(app)
        with patch(
            "structure_feedback_agents.get_deepseek_api_key",
            return_value=None,
        ):
            response = client.post(
                "/api/map-sentences",
                json={
                    "current_text": COMPLETE_ESSAY,
                    "flowchart": OPTION_C_FLOWCHART,
                    "chart_type": "line",
                    "deplot_text": "Year | Bus | Rail",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for old_field in ("sentences", "nodes", "mappings", "missing_nodes"):
            self.assertIn(old_field, payload)
        for new_field in (
            "paragraphs",
            "paragraph_mappings",
            "structure_feedback",
            "agent_trace",
        ):
            self.assertIn(new_field, payload)

    def test_analyze_structure_route_is_registered(self):
        client = TestClient(app)
        with patch(
            "structure_feedback_agents.get_deepseek_api_key",
            return_value=None,
        ):
            response = client.post(
                "/api/analyze-structure",
                json={
                    "current_text": COMPLETE_ESSAY,
                    "flowchart": OPTION_C_FLOWCHART,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["debug"]["orchestrator"],
            "StructureFeedbackOrchestrator",
        )


if __name__ == "__main__":
    unittest.main()
