import json
import re
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.core.llm import chat

app = FastAPI(title="Verification Agent")


class VerifyRequest(BaseModel):
    question: str
    answer: str
    research: dict = Field(default_factory=dict)


@app.get("/health")
def health():
    return {"agent": "verification", "status": "ok"}


def fallback_result(confidence: str, issue: str, correction: str = ""):
    corrections = [correction] if correction else []
    return {
        "supported": False,
        "confidence": confidence,
        "issues": [issue],
        "corrections": corrections,
        "evidence_count": 0,
        "checked_claims": [],
        "verdict": "Needs more evidence"
    }


def extract_json_object(text: str):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def normalize_result(data: dict[str, Any], evidence_count: int):
    supported = bool(data.get("supported", False))
    confidence = str(data.get("confidence", "unknown")).lower()

    if confidence not in {"high", "medium", "low", "unknown"}:
        confidence = "unknown"

    issues = data.get("issues", [])
    corrections = data.get("corrections", [])
    checked_claims = data.get("checked_claims", [])

    if not isinstance(issues, list):
        issues = [str(issues)]
    if not isinstance(corrections, list):
        corrections = [str(corrections)]
    if not isinstance(checked_claims, list):
        checked_claims = []

    if supported:
        verdict = "Supported"
    elif confidence == "medium":
        verdict = "Partially supported"
    else:
        verdict = "Needs more evidence"

    return {
        "supported": supported,
        "confidence": confidence,
        "issues": [str(item) for item in issues],
        "corrections": [str(item) for item in corrections],
        "evidence_count": evidence_count,
        "checked_claims": checked_claims,
        "verdict": verdict
    }


def build_evidence(research: dict):
    evidence = []

    for paper in research.get("papers", []):
        title = paper.get("title") or "Untitled paper"
        year = paper.get("year") or "n.d."
        doi = paper.get("doi") or paper.get("url") or "no DOI/URL"
        abstract = paper.get("abstract") or paper.get("summary") or ""
        evidence.append(
            f"Academic source: {title} ({year}), DOI/URL: {doi}\n"
            f"Available details: {abstract}"
        )

    for item in research.get("local_context", []):
        text = (item.get("text") or "").strip()
        metadata = item.get("metadata") or {}
        filename = metadata.get("filename") or "uploaded document"

        if text:
            evidence.append(f"Uploaded document evidence from {filename}:\n{text}")

    return evidence


def parse_verification(raw: str, evidence_count: int):
    data = extract_json_object(raw)

    if data is None:
        result = fallback_result(
            "unknown",
            "Verifier returned output that could not be parsed as JSON.",
            "Review the answer manually or rerun verification."
        )
        result["evidence_count"] = evidence_count
        return result

    return normalize_result(data, evidence_count)


@app.post("/verify")
def verify(req: VerifyRequest):
    answer = req.answer.strip()

    if not answer:
        return fallback_result(
            "low",
            "No answer was provided for verification.",
            "Generate an answer before running verification."
        )

    evidence = build_evidence(req.research or {})
    evidence_count = len(evidence)

    if evidence_count == 0:
        return {
            "supported": False,
            "confidence": "low",
            "issues": [
                "No retrieved evidence was provided to verify the answer."
            ],
            "corrections": [
                "Retrieve uploaded-document context or academic sources before treating the answer as verified."
            ],
            "evidence_count": 0,
            "checked_claims": [],
            "verdict": "Needs more evidence"
        }

    prompt = f"""
Question:
{req.question}

Answer to verify:
{answer}

Retrieved evidence:
{chr(10).join(f"[Evidence {index + 1}] {item}" for index, item in enumerate(evidence))}

Verification task:
1. Identify the main factual claims in the answer.
2. Check whether each claim is supported by the retrieved evidence.
3. Mark supported=true only if the important claims are materially supported.
4. Do not treat a title, DOI, or filename alone as evidence for a detailed claim.
5. If evidence is incomplete, say so clearly in issues and corrections.

Return ONLY valid JSON using exactly this shape:
{{
  "supported": false,
  "confidence": "high | medium | low",
  "issues": ["issue 1"],
  "corrections": ["correction 1"],
  "checked_claims": [
    {{
      "claim": "short claim",
      "supported": true,
      "reason": "brief reason"
    }}
  ]
}}
"""

    raw = chat(
        "You are a strict academic source-verification agent. "
        "You verify answers only against supplied evidence and return valid JSON.",
        prompt,
        temperature=0
    )

    return parse_verification(raw, evidence_count)
