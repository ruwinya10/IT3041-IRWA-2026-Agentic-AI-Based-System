import json
import re
import httpx

from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.llm import chat

app = FastAPI(title="Coordinator Agent")


class AskRequest(BaseModel):
    question: str
    user_id: int


class IntentResult(BaseModel):
    academic: bool
    intent: Literal[
        "GENERAL_LEARNING",
        "EXPLANATION",
        "SUMMARIZATION",
        "DOCUMENT_QA",
        "QUIZ_GENERATION",
        "RESEARCH",
        "RESEARCH_ANALYSIS",
        "OUT_OF_SCOPE"
    ]
    route: list[str]


@app.get("/health")
def health():
    return {"agent": "coordinator", "status": "ok"}


def parse_intent(raw: str) -> IntentResult:
    """
    Extract the JSON object returned by the LLM
    and validate it using Pydantic.
    """

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("Coordinator did not return valid JSON.")

    json_text = raw[start:end + 1]

    data = json.loads(json_text)

    return IntentResult.model_validate(data)


def fallback_intent(question: str) -> IntentResult:
    """
    Safety fallback if the LLM intent classifier fails.

    The LLM is the primary classifier.
    These rules only prevent the whole system from failing
    when the classifier returns invalid output.
    """

    q = question.lower()

    # Uploaded document / PDF related requests
    document_words = [
        "uploaded file",
        "uploaded document",
        "uploaded pdf",
        "this file",
        "this document",
        "this pdf",
        "pdf",
        "document"
    ]

    summary_words = [
        "summarize",
        "summarise",
        "summary",
        "main points",
        "key points",
        "summarize this",
        "summarise this"
    ]

    if any(word in q for word in document_words):

        if any(word in q for word in summary_words):
            return IntentResult(
                academic=True,
                intent="SUMMARIZATION",
                route=["study", "verification"]
            )

        return IntentResult(
            academic=True,
            intent="DOCUMENT_QA",
            route=["study", "verification"]
        )

    # Research requests
    research_words = [
        "research paper",
        "research papers",
        "recent research",
        "recent papers",
        "academic papers",
        "academic research",
        "literature review",
        "find papers",
        "find research",
        "research on"
    ]

    if any(word in q for word in research_words):
        return IntentResult(
            academic=True,
            intent="RESEARCH",
            route=["research", "study", "verification"]
        )

    # Quiz requests
    quiz_words = [
        "quiz",
        "mcq",
        "multiple choice",
        "questions for practice",
        "test me"
    ]

    if any(word in q for word in quiz_words):
        return IntentResult(
            academic=True,
            intent="QUIZ_GENERATION",
            route=["study", "verification"]
        )

    # General academic questions
    academic_words = [
        "explain",
        "what is",
        "what are",
        "how does",
        "how do",
        "why does",
        "why is",
        "machine learning",
        "data mining",
        "artificial intelligence",
        "programming",
        "database",
        "algorithm",
        "computer science",
        "data science"
    ]

    if any(word in q for word in academic_words):
        return IntentResult(
            academic=True,
            intent="EXPLANATION",
            route=["study", "verification"]
        )

    # Safe default:
    # treat unknown questions as general learning questions.
    return IntentResult(
        academic=True,
        intent="GENERAL_LEARNING",
        route=["study", "verification"]
    )


def classify_intent(question: str) -> IntentResult:
    """
    Ask the LLM to determine the user's academic intent.
    """

    prompt = f"""
You are the intent-classification component of an AI Study and Research Assistant.

Classify the student's question into exactly ONE intent.

Allowed intents:

GENERAL_LEARNING
- General academic learning questions.
- Example: "What is machine learning?"

EXPLANATION
- The student wants a concept explained clearly.
- Example: "Explain overfitting with an example."

SUMMARIZATION
- The student wants an uploaded document/file/PDF summarized.
- Example: "Summarize this uploaded file in 5 main points."

DOCUMENT_QA
- The student asks a question specifically about an uploaded document/file/PDF.
- Example: "According to the uploaded PDF, what is hierarchical clustering?"

QUIZ_GENERATION
- The student wants a quiz, MCQs, practice questions, or a test.

RESEARCH
- The student explicitly wants academic research papers, recent research,
  literature, or external scholarly information.
- Example: "Find recent research papers about gradient clipping."

RESEARCH_ANALYSIS
- The student wants research papers AND analysis/comparison/synthesis of
  the research.

OUT_OF_SCOPE
- The question is unrelated to education, academic learning, studying,
  research, or the uploaded academic material.

Important routing rules:

1. Questions about an uploaded file/document/PDF should NOT be sent to
   the Research Agent unless the student explicitly asks for external
   research papers as well.

2. "What is machine learning?" should go to Study/NLP.

3. "Explain overfitting" should go to Study/NLP.

4. "Summarize this uploaded PDF" should go to Study/NLP.

5. "What does the uploaded document say about clustering?" should go
   to Study/NLP.

6. "Generate 10 MCQs about data mining" should go to Study/NLP.

7. "Find recent research papers about machine learning" should go to
   Research → Study → Verification.

8. "Find research papers about gradient clipping and compare their
   findings" should go to Research → Study → Verification.

9. An unrelated question such as "What is the weather today?" should
   be OUT_OF_SCOPE.

Routing values must follow these rules:

GENERAL_LEARNING:
["study", "verification"]

EXPLANATION:
["study", "verification"]

SUMMARIZATION:
["study", "verification"]

DOCUMENT_QA:
["study", "verification"]

QUIZ_GENERATION:
["study", "verification"]

RESEARCH:
["research", "study", "verification"]

RESEARCH_ANALYSIS:
["research", "study", "verification"]

OUT_OF_SCOPE:
[]

Return ONLY valid JSON.

Required format:

{{
    "academic": true,
    "intent": "EXPLANATION",
    "route": ["study", "verification"]
}}

Student question:

{question}
"""

    try:
        raw = chat(
            "You are the Coordinator Agent responsible for routing student requests.",
            prompt,
            temperature=0
        )

        return parse_intent(raw)

    except Exception:
        return fallback_intent(question)


async def call_agent(client, url: str, payload: dict):
    """
    Send a request to another agent and return its JSON response.
    """

    response = await client.post(
        url,
        json=payload
    )

    response.raise_for_status()

    return response.json()


@app.post("/ask")
async def ask(req: AskRequest):

    # ---------------------------------------------------------
    # STEP 1 — Determine the user's intent
    # ---------------------------------------------------------

    intent_result = classify_intent(req.question)

    # ---------------------------------------------------------
    # STEP 2 — Handle out-of-scope questions immediately
    # ---------------------------------------------------------

    if not intent_result.academic:
        return {
            "answer": (
                "I'm designed to help with academic learning, "
                "research, uploaded study materials, explanations, "
                "summaries, and quizzes. "
                "Please ask an academic or study-related question."
            ),
            "sources": [],
            "verification": None,
            "intent": intent_result.intent,
            "route": ["coordinator"]
        }

    async with httpx.AsyncClient(timeout=90) as client:

        try:

            # -------------------------------------------------
            # STEP 3 — Research Agent
            # -------------------------------------------------

            research = {
                "papers": [],
                "local_context": []
            }

            if "research" in intent_result.route:

                research = await call_agent(
                    client,
                    f"{settings.research_agent_url}/research",
                    {
                        "question": req.question,
                        "user_id": req.user_id
                    }
                )

            # -------------------------------------------------
            # STEP 4 — Study/NLP Agent
            # -------------------------------------------------

            study = None

            if "study" in intent_result.route:

                study = await call_agent(
                    client,
                    f"{settings.study_agent_url}/study",
                    {
                        "question": req.question,
                        "user_id": req.user_id,
                        "intent": intent_result.intent,
                        "research": research
                    }
                )

            # -------------------------------------------------
            # STEP 5 — Verification Agent
            # -------------------------------------------------

            verification = None

            if "verification" in intent_result.route:

                verification = await call_agent(
                    client,
                    f"{settings.verification_agent_url}/verify",
                    {
                        "question": req.question,
                        "answer": study["answer"],
                        "research": research
                    }
                )

            # -------------------------------------------------
            # STEP 6 — Return final result
            # -------------------------------------------------

            return {
                "answer": study["answer"] if study else "",
                "sources": research.get("papers", []),
                "verification": verification,
                "intent": intent_result.intent,
                "route": ["coordinator"] + intent_result.route
            }

        except httpx.HTTPError as exc:

            raise HTTPException(
                status_code=502,
                detail=f"Agent communication failed: {exc}"
            ) from exc