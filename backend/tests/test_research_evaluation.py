"""Small, synthetic labelled retrieval fixture, NOT a benchmark of OpenAlex.

Labels describe topical relevance by construction, independently of the gate.
Precision@5 = relevant returned / 5 (unfilled positions receive no credit).
Returned precision = relevant returned / returned, or 0 for an empty result.
Recall = relevant returned / all labelled relevant candidates in the fixture.
No metric estimates real-world quality, verifies findings, or measures network
retrieval recall. The ensemble fixture deliberately includes a relevant narrow
paper missed by the unchanged gate; that limitation is reported, not relabelled.
The quantum fixture includes a spelling-correction false positive admitted by
the shared phrase "error correction". Labels are not adjusted to hide it.

Run from backend: .venv/Scripts/python.exe tests/test_research_evaluation.py
"""
import json
import unittest
from unittest.mock import AsyncMock, patch

from test_research_relevance import agent, paper, QUESTION, TestClient


CASES = [
    ("gradient_clipping", QUESTION, [
        (True, "Gradient clipping for training stability", None),
        (True, "Adaptive gradient clipping", "Training stability analysis"),
        (False, "Training large models", "Popular training methods"),
        (False, "Probability ratio clipping", "Training generative models"),
        (False, "Related research overview", None),
    ]),
    ("ensemble_learning",
     "Find research papers about ensemble learning, bagging, boosting, stacking, and random forests.", [
        (True, "Ensemble learning with bagging and boosting", None),
        (True, "Random forests and ensemble learning", None),
        (True, "Bagging predictors", "Combining bootstrap predictors"),
        (False, "Learning in classrooms", None),
        (False, "Random sampling in ecology", None),
        (False, "Stacking materials", None),
    ]),
    ("coral_bleaching", "Find papers related to coral bleaching ocean warming", [
        (True, "Coral bleaching under ocean warming", None),
        (True, "Coral bleaching mechanisms", "Ocean warming and coral stress"),
        (False, "Ocean shipping", None),
        (False, "Warming urban houses", None),
        (False, "Bleaching industrial textiles", None),
    ]),
    ("quantum_error_correction", "Rank papers about quantum error correction", [
        (True, "Quantum error correction", None),
        (True, "Fault tolerant devices", "Quantum error correction methods"),
        (False, "Quantum chemistry", None),
        (False, "Error correction in spelling", None),
        (False, "Editorial correction", None),
    ]),
]


def evaluate_cases():
    reports = []
    for domain, question, labels in CASES:
        candidates = [paper(title, abstract, 0 if relevant else 1000000)
                      for relevant, title, abstract in labels]
        relevant_titles = {title for relevant, title, _ in labels if relevant}
        irrelevant_titles = {title for relevant, title, _ in labels if not relevant}
        with patch.object(agent, "search_uploaded_documents", return_value=[]), \
             patch.object(agent, "search_multiple_queries", new=AsyncMock(return_value=candidates)):
            response = TestClient(agent.app).post("/research", json={
                "question": question, "user_id": 1})
        if response.status_code != 200:
            raise AssertionError(response.text)
        selected = response.json()["papers"]
        returned = {p["title"] for p in selected}
        relevant_count = len(returned & relevant_titles)
        reports.append({
            "domain": domain, "returned": len(selected),
            "relevant_returned": relevant_count,
            "irrelevant_rejected": len(irrelevant_titles - returned),
            "irrelevant_total": len(irrelevant_titles),
            "precision_at_5": relevant_count / 5,
            "returned_precision": relevant_count / len(selected) if selected else 0.0,
            "fixture_recall": relevant_count / len(relevant_titles),
            "missed_relevant": sorted(relevant_titles - returned),
            "irrelevant_returned": sorted(irrelevant_titles & returned),
            "results": [{key: p[key] for key in (
                "rank", "title", "relevance_score", "relevance_level", "matched_keywords",
                "matched_phrases", "matched_queries", "cited_by_count", "selection_explanation",
                "ranking_explanation", "keyword_coverage"
            )} for p in selected],
        })
    return reports


class ResearchEvaluationTests(unittest.TestCase):
    def test_controlled_retrieval_evaluation(self):
        for result in evaluate_cases():
            with self.subTest(domain=result["domain"]):
                quantum = result["domain"] == "quantum_error_correction"
                self.assertEqual(result["returned"], 3 if quantum else 2)
                self.assertEqual(result["relevant_returned"], 2)
                self.assertEqual(result["irrelevant_rejected"], result["irrelevant_total"] - int(quantum))
                self.assertEqual(result["precision_at_5"], 0.4)
                self.assertEqual(result["returned_precision"], 2 / 3 if quantum else 1.0)
                expected_missed = ["Bagging predictors"] if result["domain"] == "ensemble_learning" else []
                self.assertEqual(result["missed_relevant"], expected_missed)
                for p in result["results"]:
                    self.assertFalse({"rank", "related", "find", "papers"} & set(p["matched_keywords"]))
                    self.assertTrue(p["matched_phrases"])
                    self.assertIn("not verified" if "No abstract" not in p["selection_explanation"]
                                  else "cannot be verified", p["selection_explanation"])


if __name__ == "__main__":
    print(json.dumps({"scope": "Synthetic controlled fixture, not an OpenAlex benchmark",
                      "evaluation": evaluate_cases()}, indent=2))
