"""Verification Agent regression tests.

These tests isolate the verifier from live LLM calls and focus on the
contract your agent owns: evidence building, strict no-evidence behavior,
LLM JSON normalization, and parse-failure fallback.
"""
import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

llm_stub = types.ModuleType("app.core.llm")
llm_stub.chat = Mock(return_value=json.dumps({
    "supported": True,
    "confidence": "high",
    "summary": "The answer is supported by the supplied evidence.",
    "issues": [],
    "corrections": [],
    "checked_claims": [
        {
            "claim": "Gradient clipping limits large gradients.",
            "supported": True,
            "reason": "The abstract states that clipping limits large gradients."
        }
    ]
}))

with patch.dict(sys.modules, {"app.core.llm": llm_stub}):
    agent = importlib.import_module("app.agents.verification_agent")


def research_payload():
    return {
        "papers": [
            {
                "title": "Gradient clipping for stable training",
                "year": 2024,
                "doi": "10.1234/test",
                "abstract": "Gradient clipping limits large gradients during training.",
                "selection_explanation": "Selected because the title and abstract match gradient clipping.",
                "ranking_explanation": "Ranked highly because matched phrases appear in title and abstract.",
                "relevance_level": "high",
                "relevance_score": 82.5,
                "matched_keywords": ["gradient", "clipping"],
                "matched_phrases": ["gradient clipping"],
                "access_type": "doi"
            }
        ],
        "local_context": [
            {
                "text": "The uploaded notes define clipping as a thresholding step.",
                "metadata": {"filename": "lecture.pdf"}
            }
        ]
    }


class VerificationAgentTests(unittest.TestCase):
    def setUp(self):
        llm_stub.chat.reset_mock()
        llm_stub.chat.return_value = json.dumps({
            "supported": True,
            "confidence": "high",
            "summary": "The answer is supported by the supplied evidence.",
            "issues": [],
            "corrections": [],
            "checked_claims": [
                {
                    "claim": "Gradient clipping limits large gradients.",
                    "supported": True,
                    "reason": "The abstract states that clipping limits large gradients."
                }
            ]
        })
        self.client = TestClient(agent.app)

    def test_health(self):
        self.assertEqual(
            self.client.get("/health").json(),
            {"agent": "verification", "status": "ok"}
        )

    def test_no_evidence_needs_more_evidence_without_llm_call(self):
        response = self.client.post("/verify", json={
            "question": "What is gradient clipping?",
            "answer": "Gradient clipping limits large gradients.",
            "research": {"papers": [], "local_context": []}
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["supported"])
        self.assertEqual(data["confidence"], "low")
        self.assertEqual(data["evidence_count"], 0)
        self.assertEqual(data["verdict"], "Needs more evidence")
        llm_stub.chat.assert_not_called()

    def test_supported_answer_is_verified_against_supplied_evidence(self):
        response = self.client.post("/verify", json={
            "question": "What does gradient clipping do?",
            "answer": "Gradient clipping limits large gradients.",
            "research": research_payload()
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["supported"])
        self.assertEqual(data["confidence"], "high")
        self.assertEqual(data["evidence_count"], 2)
        self.assertEqual(data["verdict"], "Supported")
        self.assertEqual(len(data["checked_claims"]), 1)
        llm_stub.chat.assert_called_once()
        prompt = llm_stub.chat.call_args.args[1]
        self.assertIn("Gradient clipping limits large gradients.", prompt)
        self.assertIn("Gradient clipping for stable training", prompt)
        self.assertIn("Selected because the title and abstract match gradient clipping.", prompt)
        self.assertIn("Retrieval relevance: high (82.5)", prompt)
        self.assertIn("Matched phrases: gradient clipping", prompt)
        self.assertIn("lecture.pdf", prompt)

    def test_partial_result_is_normalized(self):
        llm_stub.chat.return_value = json.dumps({
            "supported": False,
            "confidence": "medium",
            "summary": "",
            "issues": "Only one part of the answer is supported.",
            "corrections": "Mention the evidence limitation.",
            "checked_claims": "not-a-list"
        })

        response = self.client.post("/verify", json={
            "question": "Explain gradient clipping.",
            "answer": "Gradient clipping limits gradients and always improves accuracy.",
            "research": research_payload()
        })

        data = response.json()
        self.assertFalse(data["supported"])
        self.assertEqual(data["confidence"], "medium")
        self.assertEqual(data["verdict"], "Partially supported")
        self.assertEqual(data["issues"], ["Only one part of the answer is supported."])
        self.assertEqual(data["corrections"], ["Mention the evidence limitation."])
        self.assertEqual(data["checked_claims"], [])

    def test_unparseable_llm_output_falls_back_safely(self):
        llm_stub.chat.return_value = "The answer seems fine, but this is not JSON."

        response = self.client.post("/verify", json={
            "question": "What does gradient clipping do?",
            "answer": "Gradient clipping limits large gradients.",
            "research": research_payload()
        })

        data = response.json()
        self.assertFalse(data["supported"])
        self.assertEqual(data["confidence"], "unknown")
        self.assertEqual(data["evidence_count"], 2)
        self.assertEqual(data["verdict"], "Needs more evidence")
        self.assertIn("could not be parsed", data["summary"])


if __name__ == "__main__":
    unittest.main()
