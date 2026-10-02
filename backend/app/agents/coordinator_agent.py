import json # Python's built-in JSON module for converting between JSON strings and Python objects
import re  # regular expression module. It can be used for pattern matching
import httpx  # HTTPX for making asynchronous HTTP requests to other agents

from typing import Literal  # can restrict the intent field to specific allowed values
from fastapi import FastAPI, HTTPException, Header # FastAPI for creating the API, HTTPException for returning HTTP errors, and Header for reading HTTP headers such as the Authorization token
from pydantic import BaseModel # for defining and validating request/response data structures

from app.core.config import settings # Imports the application settings such as the URLs of the other agents
from app.core.llm import chat # Imports the chat function used to send prompts to the LLM

app = FastAPI(title="Coordinator Agent") # Creates the FastAPI application and gives it the name "Coordinator Agent".


class AskRequest(BaseModel): # Defines the structure of a request sent to the Coordinator's /ask endpoint
    question: str
    user_id: int


class IntentResult(BaseModel): # Defines the structure of the result returned by the intent classifier
    academic: bool # Indicates whether the question is considered academic/in-scope
    intent: Literal[  # Restricts the intent to one of the predefined intent categories
        "GENERAL_LEARNING",
        "GENERAL_KNOWLEDGE",
        "EXPLANATION",
        "SUMMARIZATION",
        "DOCUMENT_QA",
        "QUIZ_GENERATION",
        "RESEARCH",
        "RESEARCH_ANALYSIS",
        "OUT_OF_SCOPE"
    ]
    route: list[str] # Stores the list of agents that should receive the request


@app.get("/health") # Defines a GET endpoint used to check whether the Coordinator Agent is running.
def health():
    return {"agent": "coordinator", "status": "ok"}


def parse_intent(raw: str) -> IntentResult:  # Defines a function that converts the raw LLM response into an IntentResult object
    """
    Extract the JSON object returned by the LLM
    and validate it using Pydantic.
    """

    start = raw.find("{") # Finds the position of the first opening curly bracket in the LLM response.
    end = raw.rfind("}")  # Finds the position of the last closing curly bracket in the LLM response.

    if start == -1 or end == -1 or end <= start:  # Checks whether a valid JSON object could be found in the response.
        raise ValueError("Coordinator did not return valid JSON.")

    json_text = raw[start:end + 1]  # Extracts only the JSON portion from the LLM response.

    data = json.loads(json_text) # Converts the JSON string into a Python dictionary.

    return IntentResult.model_validate(data)  # # Validates the dictionary against the IntentResult Pydantic model


def looks_like_general_knowledge(question: str) -> bool:  # Defines a function that checks whether a question looks like general knowledge.
    """
    Conservative check for student-style factual questions
    such as capitals, geography, and well-known facts.
    """

    q = question.lower()

    unrelated = [
        "weather",
        "forecast",
        "stock price",
        "buy ",
        "dating",
        "girlfriend",
        "boyfriend",
        "recipe",
        "how are you",
        "tell me a joke",
        "sports score",
        "lottery",
    ]

    if any(word in q for word in unrelated):
        return False

    gk_phrases = [
        "capital of",
        "capital city",
        "currency of",
        "official language",
        "population of",
        "largest city",
        "largest country",
        "smallest country",
        "which country",
        "which city",
        "which planet",
        "who invented",
        "who discovered",
        "who is the president",
        "who is the prime minister",
        "who was the first",
        "where is",
        "located in",
        "national animal",
        "national bird",
        "how many continents",
        "how many planets",
        "how many countries",
    ]

    return any(phrase in q for phrase in gk_phrases)


def fallback_intent(question: str) -> IntentResult:  # Defines a fallback classifier used when the LLM classifier fails.
    """
    Safety fallback if the LLM intent classifier fails.

    The LLM is the primary classifier.
    These rules only prevent the whole system from failing
    when the classifier returns invalid output.
    """

    q = question.lower()

    # Uploaded document / PDF related requests. Defines keywords associated with uploaded documents.
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

    if looks_like_general_knowledge(question):
        return IntentResult(
            academic=False,
            intent="GENERAL_KNOWLEDGE",
            route=["study"]
        )

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

def get_casual_response(question: str) -> str | None:
    """
    Handle simple conversational messages without routing them
    to the academic agents.
    """

    q = question.lower().strip() # strip() removes spaces from both ends.

    greetings = [
        "hi",
        "hello",
        "hey",
        "hii",
        "hiii",
        "good morning",
        "good afternoon",
        "good evening",
    ]

    if q in greetings:
        return (
            "Hi! 👋 How can I help you today? "
            "I'm specially designed for academic learning and research, "
            "so feel free to ask me any academic question."
        )

    thanks = [
        "thank you",
        "thanks",
        "thank u",
        "thanks a lot",
        "thank you so much",
    ]

    if q in thanks:
        return (
            "You're welcome! 😊 If you have any academic questions, "
            "I'd be happy to help. I'm specially designed for academic learning and research."
        )

    emotional = [
        "i feel sad",
        "i am sad",
        "i'm sad",
        "i feel happy",
        "i am happy",
        "i'm happy",
        "i feel bad",
        "i am feeling sad",
        "i'm feeling sad",
        "i feel lonely",
        "i am lonely",
        "i'm lonely",
        "i feel stressed",
        "i am stressed",
        "i'm stressed",
        "i feel tired",
        "i am tired",
        "i'm tired",
    ]

    if any(phrase in q for phrase in emotional):
        return (
            "I understand. Take care of yourself. 😊 "
            "I'm specially designed for academic learning and research, "
            "so if you have an academic question or need help with your studies, "
            "I'm here to help."
        )

    return None

def classify_intent(question: str) -> IntentResult:  # Defines the main LLM-based intent classification function.
    """
    Ask the LLM to determine the user's academic intent.
    """

    q = question.lower()

    document_words = [
        "uploaded file",
        "uploaded document",
        "uploaded pdf",
        "uploaded material",
        "this file",
        "this document",
        "this pdf",
        "pdf",
        "document",
        "lecture",
        "slides"
    ]

    summary_words = [
        "summarize",
        "summarise",
        "summary",
        "main points",
        "key points",
        "overview"
    ]

    if any(word in q for word in summary_words) and not any(  # Checks whether the user wants a summary but is not asking for external research.
        word in q for word in ["research paper", "research papers", "find papers", "external research"]
    ):
        return IntentResult(
            academic=True,
            intent="SUMMARIZATION",
            route=["study", "verification"]
        )

    if any(word in q for word in document_words):
        return IntentResult(
            academic=True,
            intent="DOCUMENT_QA",
            route=["study", "verification"]
        )

    # Creates the prompt that will be sent to the LLM for intent classification.
    prompt = f"""  
You are the intent-classification component of an AI Study and Research Assistant.

Classify the student's question into exactly ONE intent.

Allowed intents:

GENERAL_LEARNING
- General academic learning questions.
- Example: "What is machine learning?"

GENERAL_KNOWLEDGE
- Factual general-knowledge questions a student might ask, such as
  geography, capitals, history facts, civics, or well-known science facts.
- These are NOT research requests and do NOT need academic papers.
- Example: "What is the capital of France?"
- Example: "Who invented the telephone?"

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
  research, uploaded academic material, AND is also not a factual
  general-knowledge question a student might reasonably ask.
- Example: "What is the weather today?"
- Do NOT use OUT_OF_SCOPE for capitals, countries, famous historical
  facts, or similar school-style general knowledge.

Important routing rules:

1. Questions about an uploaded file/document/PDF should NOT be sent to
   the Research Agent unless the student explicitly asks for external
   research papers as well.

2. "What is machine learning?" should go to Study/NLP as GENERAL_LEARNING
   or EXPLANATION. Do not change academic routing for course topics.

3. "What is the capital of France?" should go to Study/NLP as
   GENERAL_KNOWLEDGE. It is in scope.

4. "Explain overfitting" should go to Study/NLP.

5. "Summarize this uploaded PDF" should go to Study/NLP.

6. "What does the uploaded document say about clustering?" should go
   to Study/NLP.

7. "Generate 10 MCQs about data mining" should go to Study/NLP.

8. "Find recent research papers about machine learning" should go to
   Research → Study → Verification.

9. "Find research papers about gradient clipping and compare their
   findings" should go to Research → Study → Verification.

10. An unrelated question such as "What is the weather today?" should
    be OUT_OF_SCOPE.

Routing values must follow these rules:

GENERAL_LEARNING:
["study", "verification"]

GENERAL_KNOWLEDGE:
["study"]

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
            temperature=0  # Controls how much randomness the LLM uses when generating its response
        )

        result = parse_intent(raw)  # Extracts and validates the JSON returned by the LLM.

        academic_only_intents = {
            "SUMMARIZATION",
            "DOCUMENT_QA",
            "QUIZ_GENERATION",
            "RESEARCH",
            "RESEARCH_ANALYSIS",
        }

        if result.intent == "GENERAL_KNOWLEDGE" or (
            looks_like_general_knowledge(question)
            and result.intent not in academic_only_intents
        ):
            return IntentResult(
                academic=False,
                intent="GENERAL_KNOWLEDGE",
                route=["study"]
            )

        return result

    except Exception:
        return fallback_intent(question)  # If the LLM classification fails for any reason, use the fallback classifier.


async def call_agent(  # Defines an asynchronous helper function for communicating with other agents.
    client,  # Receives the HTTPX client used for communication
    url: str,  # Receives the URL of the target agent endpoint
    payload: dict,  # Receives the JSON payload that should be sent
    headers: dict | None = None  # Receives optional HTTP headers such as the Authorization token.
):
    """
    Send a request to another agent and return its JSON response.
    """

    response = await client.post( # Sends an asynchronous POST request to the target agent
    url,
    json=payload,
    headers=headers
    )

    response.raise_for_status() # Raises an exception if the other agent returned an HTTP error.

    return response.json()  # Converts the response JSON into a Python dictionary/object and returns it.
    

@app.post("/ask")  # Defines the POST endpoint used by the frontend/backend to submit a question.
async def ask(  # Defines the asynchronous function that handles incoming questions.
    req: AskRequest,  # Receives and validates the request body using AskRequest
    authorization: str = Header(...) # Reads the Authorization header from the incoming request.
):

    # ---------------------------------------------------------
    # STEP 1 — Determine the user's intent
    # ---------------------------------------------------------
    casual_response = get_casual_response(req.question)

    if casual_response:
        return {
            "answer": casual_response,
            "sources": [],
            "verification": None,
            "intent": "OUT_OF_SCOPE",
            "route": ["coordinator"]
        }
    
    intent_result = classify_intent(req.question)

    # ---------------------------------------------------------
    # STEP 2 — Handle out-of-scope questions immediately
    # ---------------------------------------------------------

    if (
        intent_result.intent == "OUT_OF_SCOPE"
        or (
            not intent_result.academic
            and intent_result.intent != "GENERAL_KNOWLEDGE"
        )
    ):
        return {
            "answer": (
                "I'm designed to help with academic learning, "
                "research, uploaded study materials, explanations, "
                "summaries, quizzes, and general-knowledge questions. "
                "Please ask an academic, study-related, or general-knowledge question."
            ),
            "sources": [],
            "verification": None,
            "intent": intent_result.intent,
            "route": ["coordinator"]
        }

    async with httpx.AsyncClient(timeout=90) as client:  # Creates an asynchronous HTTP client for communicating with the other agents.

        try:

            # -------------------------------------------------
            # STEP 3 — Research Agent
            # -------------------------------------------------

            research = {
                "papers": [],   # Stores research papers returned by the Research Agent.
                "local_context": []  # Stores additional local context if available.
            }

            if "research" in intent_result.route:  # Checks whether the selected route contains the Research Agent.

                research = await call_agent(  # Sends the question to the Research Agent.
                    client,
                    f"{settings.research_agent_url}/research",  # Builds the Research Agent's research endpoint URL.
                    {
                        "question": req.question,
                        "user_id": req.user_id
                    },
                    headers={
                        "Authorization": authorization
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
                verification_research = {  # Combines research information with verification context returned by the Study Agent.
                    **research,  # Copies all existing research fields.
                    **(study.get("verification_context") or {})  # Adds verification context from the Study Agent.
                }

                verification = await call_agent(  # Sends the answer and supporting information to the Verification Agent
                    client,
                    f"{settings.verification_agent_url}/verify",
                    {
                        "question": req.question,
                        "answer": study["answer"],
                        "research": verification_research
                    }
                )

            # -------------------------------------------------
            # STEP 6 — Return final result
            # -------------------------------------------------
            # Returns the final combined response to the caller.
            return {
                "answer": study["answer"] if study else "",
                "sources": research.get("papers", []),
                "verification": verification,
                "intent": intent_result.intent,
                "route": ["coordinator"] + intent_result.route  # Shows the complete route beginning with the Coordinator.
            }

        except httpx.HTTPError as exc: # Handles HTTP communication errors between the Coordinator and other agents.

            raise HTTPException(  # Converts the internal communication error into an HTTP 502 response.
                status_code=502,
                detail=f"Agent communication failed: {exc}"
            ) from exc
