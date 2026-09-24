from fastapi import FastAPI
from pydantic import BaseModel

from app.core.llm import chat
from app.nlp.summarizer import extractive_summary
from app.rag.vector_store import search

app = FastAPI(title="Study/NLP Agent")


class StudyRequest(BaseModel):
    question: str
    user_id: int
    intent: str
    research: dict = {}


@app.get("/health")
def health():
    return {"agent": "study", "status": "ok"}


@app.post("/study")
def study(req: StudyRequest):

    # ---------------------------------------------------------
    # STEP 1 — Get research data passed by Coordinator
    # ---------------------------------------------------------

    research = req.research or {}

    local_context = research.get("local_context", [])
    papers = research.get("papers", [])

    # ---------------------------------------------------------
    # STEP 2 — For document-related requests, retrieve the
    # uploaded user's document context directly.
    #
    # This is important because document questions and
    # summarization should NOT depend on OpenAlex.
    # ---------------------------------------------------------

    if req.intent in ["SUMMARIZATION", "DOCUMENT_QA"]:

        local_context = search(
            req.user_id,
            req.question,
            8
        )

    # ---------------------------------------------------------
    # STEP 3 — Prepare uploaded-document context
    # ---------------------------------------------------------

    local_text = "\n\n".join(
        x.get("text", "")
        for x in local_context
    )

    local_summary = (
        extractive_summary(local_text)
        if local_text
        else "No uploaded-document context was retrieved."
    )

    # ---------------------------------------------------------
    # STEP 4 — Prepare external research context
    # ---------------------------------------------------------

    paper_text = "\n".join(
        f"- {p.get('title')} "
        f"({p.get('year')}) "
        f"DOI: {p.get('doi')}"
        for p in papers
    )

    if not paper_text:
        paper_text = "No external academic papers were retrieved."

    # ---------------------------------------------------------
    # STEP 5 — Create an intent-specific instruction
    # ---------------------------------------------------------

    if req.intent == "SUMMARIZATION":

        task_instruction = """
The student wants a summary of the uploaded material.

Summarize the retrieved uploaded material accurately.

Do not introduce information that is not supported by the
uploaded material.

If the student requests a specific number of main points,
follow that number.

Keep the summary clear and concise.
"""

    elif req.intent == "DOCUMENT_QA":

        task_instruction = """
The student is asking a question about uploaded study material.

Answer primarily using the uploaded material.

Do not invent information that is not supported by the
uploaded material.

If the uploaded material does not contain enough information,
clearly state that.
"""

    elif req.intent == "QUIZ_GENERATION":

        task_instruction = """
Generate a useful academic quiz based on the student's request.

Use the uploaded material or retrieved research when available.

Make the questions academically meaningful.

If the student asks for MCQs, provide answer choices and clearly
identify the correct answer.

Do not invent facts that contradict the supplied material.
"""

    elif req.intent == "RESEARCH":

        task_instruction = """
Use the retrieved academic research to answer the student's
research-related question.

Clearly distinguish retrieved research information from general
explanation.

Do not invent citations or research findings.
"""

    elif req.intent == "RESEARCH_ANALYSIS":

        task_instruction = """
Analyze and synthesize the retrieved academic research.

Compare findings where appropriate.

Do not claim that a paper says something unless the retrieved
information supports the claim.

Do not invent citations or research findings.
"""

    elif req.intent == "EXPLANATION":

        task_instruction = """
Explain the academic concept clearly and simply.

Use examples when helpful.

If uploaded or research material is available, use it as supporting
evidence.
"""

    else:

        task_instruction = """
Help the student understand the academic topic clearly.

Give an accurate educational explanation appropriate for a student.
"""

    # ---------------------------------------------------------
    # STEP 6 — Build final LLM prompt
    # ---------------------------------------------------------

    prompt = f"""
Student question:

{req.question}

Detected intent:

{req.intent}

Uploaded material context:

{local_summary}

External academic research:

{paper_text}

Task instructions:

{task_instruction}

Answer the student directly.

Use the supplied evidence where relevant.

Do not invent citations, research papers, or information from the
uploaded material.

At the end, provide a short "Key points" section when appropriate.
"""

    # ---------------------------------------------------------
    # STEP 7 — Generate answer
    # ---------------------------------------------------------

    answer = chat(
        "You are the Study/NLP Agent of an academic AI assistant. "
        "Your role is to explain, summarize, answer document questions, "
        "generate quizzes, and synthesize academic research accurately.",
        prompt
    )

    return {
        "answer": answer,
        "extractive_summary": local_summary
    }