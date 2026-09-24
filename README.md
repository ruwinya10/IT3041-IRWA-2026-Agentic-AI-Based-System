# AI Study & Research Assistant

A student-facing multi-agent system for the IT3041 Agentic AI assignment. It combines an LLM, NLP, information retrieval, security, HTTP/JSON agent communication, source verification, and responsible-AI controls.

## Architecture

React UI → FastAPI Coordinator (8000) → Research Agent (8001) → Study/NLP Agent (8002) → Verification Agent (8003)

Supporting services: MySQL (users/documents/chats) and Chroma (vector retrieval). The Research Agent queries OpenAlex for academic works and Chroma for uploaded PDFs.

## Why these technologies

- **React + Vite:** simple responsive student UI.
- **FastAPI:** typed Python APIs and easy independent agent services.
- **MySQL + SQLAlchemy:** relational persistence for accounts, documents and chat history.
- **Chroma:** local vector database for document retrieval; it supports persistent/client-server deployment.
- **Sentence Transformers:** local embeddings for semantic search.
- **scikit-learn:** TF-IDF extractive summarization, giving the NLP agent an explicit classical NLP component.
- **Groq:** fast LLM inference. The default model is `openai/gpt-oss-120b`; change `GROQ_MODEL` if needed.
- **OpenAlex:** academic-work search without building a paper index from scratch.
- **JWT + bcrypt:** authentication and password hashing.
- **HTTP + JSON:** explicit agent-to-agent communication required by the assignment.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker Desktop
- A Groq API key

## Step-by-step setup

### 1. Create the project

Extract this folder and open a terminal in its root.

### 2. Start MySQL and Chroma

```bash
docker compose up -d
```

Check:

```bash
docker ps
```

You should see `study-assistant-mysql` and `study-assistant-chroma`.

### 3. Configure the backend

```bash
cd backend
python -m venv .venv
```

Windows:

```bash
.venv\\Scripts\\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set your Groq key and a long JWT secret.

```env
GROQ_API_KEY=your_real_key
JWT_SECRET=replace_with_a_long_random_secret
```

### 4. Start all FastAPI services

From `backend`:

```bash
python run_agents.py
```

Ports:

- 8000 Coordinator/API
- 8001 Research Agent
- 8002 Study/NLP Agent
- 8003 Verification Agent

Open `http://localhost:8000/docs` to view the API.

### 5. Start React

Open a second terminal:

```bash
cd frontend
npm install
```

Copy `.env.example` to `.env`, then:

```bash
npm run dev
```

Open the URL shown by Vite, normally `http://localhost:5173`.

### 6. Test the complete agent workflow

1. Register a student account.
2. Upload a PDF lecture/research document.
3. Ask a question.
4. Coordinator calls Research Agent.
5. Research Agent searches OpenAlex and the student's Chroma collection.
6. Coordinator sends retrieved evidence to Study/NLP Agent.
7. Study/NLP Agent performs extractive NLP processing and LLM explanation.
8. Coordinator sends the generated answer plus evidence to Verification Agent.
9. Verification Agent returns support status, confidence, issues and corrections.
10. The answer and retrieved academic sources are shown in React.

## Responsible AI implementation

- The system does not silently invent citations; the Study Agent is instructed to use retrieved evidence.
- The Verification Agent checks whether claims are materially supported.
- The UI displays retrieved sources separately from the generated answer.
- Passwords are hashed; passwords are never stored directly.
- JWT authentication protects document and chat endpoints.
- Uploaded PDFs are limited by file type and size.
- User document retrieval is filtered by `user_id` to reduce cross-user data leakage.
- The system should tell students when evidence is insufficient rather than pretending certainty.

## Important assignment mapping

The brief requires at least two interacting intelligent agents and calls for LLMs, NLP, IR, security, defined agent communication protocols, Responsible AI and commercialization. This implementation provides four specialized agents and HTTP/JSON communication. fileciteturn0file0L33-L48

For the final report, document your own test results, limitations, pricing assumptions and deployment plan rather than claiming results not measured by your team.

## Future improvements

- Add DOCX/TXT support.
- Add citation-level claim matching rather than answer-level verification.
- Add conversation history UI.
- Add admin observability and request tracing.
- Add rate limiting and stricter file scanning before production deployment.
- Add a second academic source such as Crossref or Semantic Scholar.
- Add a formal evaluation set with answer-support, retrieval precision, latency and user-satisfaction metrics.
