"""Research-only regression tests; never initialize or write Chroma."""
import copy
import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
vector_stub = types.ModuleType("app.rag.vector_store")
vector_stub.search = Mock(return_value=[])
config_stub = types.ModuleType("app.core.config")
config_stub.settings = types.SimpleNamespace(openalex_email="research-tests@example.invalid")
with patch.dict(sys.modules, {"app.rag.vector_store": vector_stub, "app.core.config": config_stub}):
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
        self.assertIn("ranking_explanation", data["papers"][0])
        self.assertIn("evidence_basis", data["papers"][0])

    def test_final_limit_and_filters(self):
        candidates = [paper(f"Quantum error correction approach {i}") for i in range(8)]
        result = agent.diversify_ranked_papers(ranked("quantum error correction", candidates),
                                              max_results=agent.MAX_FINAL_CANDIDATES)
        self.assertEqual(len(result), 5)
        self.assertEqual([p["rank"] for p in result], [1, 2, 3, 4, 5])
        filters = agent.extract_academic_filters("open access papers after 2022 with pdf")
        candidates[0].update(is_open_access=True, pdf_url="https://example.org/a.pdf")
        self.assertEqual(agent.apply_academic_filters(candidates, filters), [candidates[0]])

    def test_evidence_is_field_specific_and_limited(self):
        result = ranked(QUESTION, [paper("Gradient clipping", "Training stability")])[0]
        basis = result["evidence_basis"]
        self.assertEqual(basis["title"]["matched_phrases"], ["gradient clipping"])
        self.assertEqual(basis["abstract"]["matched_phrases"], ["training stability"])
        self.assertFalse(basis["full_text_reviewed"])
        explanation = agent.build_selection_explanation(result)
        self.assertIn("the title matches query phrases: gradient clipping", explanation)
        self.assertIn("the abstract contains 2 query keywords: training, stability", explanation)
        self.assertIn("full-paper findings were not verified", explanation)
        for absent in ["authors prove", "experiments show", "accuracy", "recommended"]:
            self.assertNotIn(absent, explanation)

    def test_missing_abstract_and_legacy_phrase_field(self):
        result = ranked(QUESTION, [paper("Gradient clipping")])[0]
        self.assertFalse(result["evidence_basis"]["abstract"]["available"])
        self.assertIn("No abstract is available", agent.build_selection_explanation(result))
        self.assertIn("gradient clipping", agent.build_selection_explanation({
            "matched_phrases": ["gradient clipping"]}))
        self.assertIn("coral bleaching", agent.build_selection_explanation({
            "matched_topic_phrases": ["coral bleaching"]}))

    def test_explanation_agrees_with_unchanged_score(self):
        result = ranked(QUESTION, [paper("Gradient clipping")])[0]
        self.assertEqual(result["relevance_score"], 25.83)
        self.assertEqual(result["relevance_level"], "low")
        self.assertEqual(result["keyword_coverage"], 0.5)
        explanation = agent.build_ranking_explanation(result)
        self.assertIn("primary (22.50 points)", explanation)
        self.assertIn("coverage is 50.0%", explanation)
        self.assertIn("search matches 3.33", explanation)
        self.assertIn("citations 0.00", explanation)
        self.assertIn("cannot bypass the gate", explanation)
        self.assertIn("diversification", explanation)

    def test_source_metadata_and_old_request_shape(self):
        raw = {
            "id": "https://openalex.org/W123", "display_name": "Quantum error correction",
            "doi": "https://doi.org/10.1234/test", "publication_year": 2024,
            "abstract_inverted_index": {"Quantum": [0], "error": [1], "correction": [2]},
            "cited_by_count": 3,
            "primary_location": {"landing_page_url": "https://example.org/landing",
                                 "source": {"display_name": "Fixture Journal", "type": "journal"}},
            "best_oa_location": {"pdf_url": "https://example.org/paper.pdf"},
            "open_access": {"is_oa": True, "oa_status": "gold", "oa_url": "https://example.org/oa"},
        }
        candidate = agent.format_openalex_work(raw, "quantum error correction")
        with patch.object(agent, "search_uploaded_documents", return_value=[]) as local, \
             patch.object(agent, "search_multiple_queries", new=AsyncMock(return_value=[candidate])):
            response = TestClient(agent.app).post("/research", json={
                "question": "quantum error correction", "user_id": 7})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(set(data), {"papers", "local_context", "local_context_summary",
                                     "research_plan", "access_summary"})
        local.assert_called_once_with(user_id=7, query="quantum error correction", n_results=3, document_id=None)
        result = data["papers"][0]
        for key, value in agent.format_openalex_work(raw, "quantum error correction").items():
            self.assertEqual(result[key], value, key)
        self.assertEqual(result["doi"], "10.1234/test")
        self.assertEqual(result["access_type"], "direct_pdf")
        self.assertEqual(result["best_access_url"], "https://example.org/paper.pdf")
        self.assertEqual(result["access_info"]["best_access_url"], result["url"])
        self.assertEqual(result["abstract"], "Quantum error correction")
        self.assertTrue(result["evidence_basis"]["abstract"]["available"])

    def test_local_retrieval_forwards_user_and_document_filters(self):
        vector_stub.search.reset_mock()
        agent.search_uploaded_documents(user_id=7, query="quantum", n_results=3, document_id=12)
        vector_stub.search.assert_called_once_with(user_id=7, query="quantum", n_results=3, document_id=12)

    def test_access_fallback_order(self):
        args = dict(pdf_url="pdf", oa_url="oa", landing_page_url="landing",
                    doi_url="doi", openalex_url="openalex", is_open_access=True)
        for field, expected_type in [("pdf_url", "direct_pdf"), ("oa_url", "open_access_page"),
                                     ("landing_page_url", "landing_page"), ("doi_url", "doi"),
                                     ("openalex_url", "openalex")]:
            result = agent.determine_access_info(**args)
            self.assertEqual(result["access_type"], expected_type)
            self.assertEqual(result["best_access_url"], args[field])
            args[field] = None
        self.assertEqual(agent.determine_access_info(**args)["access_type"], "unavailable")

    def test_queries_health_and_empty_question(self):
        client = TestClient(agent.app)
        self.assertEqual(client.get("/health").json()["status"], "ok")
        response = client.post("/research/queries", json={"question": QUESTION, "user_id": 7})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"original_question", "keywords", "topic_phrases", "search_queries"})
        for route in ["/research", "/research/queries"]:
            self.assertEqual(client.post(route, json={"question": " ", "user_id": 7}).status_code, 400)

    def test_sequential_search_failure_isolation_and_deduplication(self):
        events = []
        async def search(query, **kwargs):
            events.append(("start", query))
            await asyncio.sleep(0)
            events.append(("end", query))
            if query == "limited":
                raise agent.HTTPException(status_code=502, detail="fixture rate limit")
            candidate = paper("Quantum error correction")
            candidate.update(openalex_id="W123", matched_queries=[query])
            return [candidate]
        with patch.object(agent, "openalex_search", side_effect=search):
            result = asyncio.run(agent.search_multiple_queries(["first", "limited", "last"]))
        self.assertEqual(events, [(phase, query) for query in ["first", "limited", "last"]
                                  for phase in ["start", "end"]])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["matched_queries"], ["first", "last"])

    def test_openalex_429_and_filter_forwarding(self):
        import httpx
        request = httpx.Request("GET", "https://api.openalex.org/works")
        response = httpx.Response(429, request=request)
        client = AsyncMock()
        client.get.return_value = response
        with patch.object(agent.httpx, "AsyncClient") as factory:
            factory.return_value.__aenter__.return_value = client
            with self.assertRaises(agent.HTTPException) as caught:
                asyncio.run(agent.openalex_search("quantum", academic_filters={
                    "year_from": 2020, "year_to": 2024, "open_access_only": True}))
        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(client.get.call_args.kwargs["params"]["filter"],
                         "from_publication_date:2020-01-01,to_publication_date:2024-12-31,is_oa:true")


if __name__ == "__main__":
    unittest.main()
