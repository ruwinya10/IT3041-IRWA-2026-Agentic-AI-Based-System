"""Research-only regression tests; never initialize or write Chroma."""
import copy
import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
vector_stub = types.ModuleType("app.rag.vector_store")
vector_stub.search = Mock(return_value=[])
with patch.dict(sys.modules, {"app.rag.vector_store": vector_stub}):
    agent = importlib.import_module("app.agents.research_agent")


QUESTION = "Can you rank the papers related to gradient clipping improving training stability?"


def paper(title, abstract=None, citations=0):
    return {
        "title": title, "abstract": abstract, "cited_by_count": citations,
        "matched_queries": ["fixture"], "year": 2024,
    }


def ranked(question, candidates):
    plan = agent.generate_search_queries(question)
    return agent.rank_papers(copy.deepcopy(candidates), plan["keywords"],
                             plan["topic_phrases"], len(plan["queries"]))


class ResearchRelevanceTests(unittest.TestCase):
    def test_question_concepts(self):
        plan = agent.generate_search_queries(QUESTION)
        self.assertEqual(plan["keywords"], ["gradient", "clipping", "training", "stability"])
        self.assertIn("gradient clipping", plan["topic_phrases"])
        self.assertIn("training stability", plan["topic_phrases"])
        self.assertNotIn("clipping training", plan["topic_phrases"])
        self.assertNotIn("related", " ".join(plan["queries"]))

    def test_popularity_cannot_rescue_weak_matches(self):
        weak = paper("Improving GAN Training with Probability Ratio Clipping and Sample Reweighting",
                     "Related training methods", 1000000)
        weak.update(is_open_access=True, pdf_url="https://example.org/paper.pdf",
                    matched_queries=["a", "b", "c", "d"])
        candidates = [weak, paper("Training with gradient methods", citations=1000000),
                      paper("Gradient clipping", citations=0)]
        result = ranked(QUESTION, candidates)
        self.assertEqual([p["title"] for p in result], ["Gradient clipping"])

    def test_unrelated_domains(self):
        for question, strong, weak in [
            ("Find papers related to coral bleaching ocean warming",
             "Coral bleaching under ocean warming", "Ocean observations"),
            ("Rank papers about quantum error correction",
             "Quantum error correction", "Error analysis"),
        ]:
            with self.subTest(question=question):
                result = ranked(question, [paper(weak, citations=1000000), paper(strong)])
                self.assertEqual([p["title"] for p in result], [strong])

    def test_short_queries_and_abstract_evidence(self):
        for question in ["photosynthesis", "AI", "quantum entanglement"]:
            with self.subTest(question=question):
                self.assertEqual(len(ranked(question, [paper("An analysis", question)])), 1)
        self.assertEqual(ranked("rank papers", [paper("Popular research", citations=1000000)]), [])

    def test_phrase_boundaries(self):
        self.assertEqual(agent.calculate_phrase_coverage(["error correction"],
                         "error correctional methods")["matches"], [])
        self.assertNotIn("coral warming", agent.extract_topic_phrases("coral, warming"))

    def test_topical_evidence_precedes_bonus(self):
        result = ranked("quantum error correction", [
            paper("Quantum error correction", citations=1000000),
            paper("Quantum error correction", "Quantum error correction", 0),
        ])
        self.assertEqual(result[0]["cited_by_count"], 0)

    def test_endpoint_gate_before_diversification_and_document_id(self):
        candidates = [paper("Gradient clipping"), paper("Gradient clipping methods")]
        candidates += [paper(f"Training survey {i}", citations=1000000) for i in range(8)]
        with patch.object(agent, "search_uploaded_documents", return_value=[]) as local, \
             patch.object(agent, "search_multiple_queries", new=AsyncMock(return_value=candidates)):
            response = TestClient(agent.app).post("/research", json={
                "question": QUESTION, "user_id": 7, "document_id": 12,
            })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["papers"]), 2)
        self.assertEqual([p["rank"] for p in data["papers"]], [1, 2])
        local.assert_called_once_with(user_id=7, query=QUESTION, n_results=3, document_id=12)
        for p in data["papers"]:
            self.assertTrue(set(["rank", "title", "relevance_score", "relevance_level",
                                 "matched_keywords", "matched_phrases", "matched_queries",
                                 "cited_by_count"]).issubset(p))
        print("Endpoint fixture results:", json.dumps(data["papers"], indent=2))

    def test_final_limit_and_filters(self):
        candidates = [paper(f"Quantum error correction approach {i}") for i in range(8)]
        result = agent.diversify_ranked_papers(ranked("quantum error correction", candidates),
                                              max_results=agent.MAX_FINAL_CANDIDATES)
        self.assertEqual(len(result), 5)
        self.assertEqual([p["rank"] for p in result], [1, 2, 3, 4, 5])
        filters = agent.extract_academic_filters("open access papers after 2022 with pdf")
        candidates[0].update(is_open_access=True, pdf_url="https://example.org/a.pdf")
        self.assertEqual(agent.apply_academic_filters(candidates, filters), [candidates[0]])


if __name__ == "__main__":
    unittest.main()
