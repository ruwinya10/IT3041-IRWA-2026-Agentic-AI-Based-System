<div align="center">
  <img width="170" height="170" alt="image" src="https://github.com/user-attachments/assets/863e705e-3a49-4ba0-a922-a6a46a20a6f3" />
</div>
<div align="center">

  <h1>🧠 ResearchMind - AI Study & Research Assistant</h1>

  <p>
    <strong>Research Smarter. Learn Better. Get Evidence-Based Answers.</strong>
  </p>

  <p>
    A Multi-Agent AI System for Academic Research, Document Analysis, and Student Learning
  </p>

  <p>
    <img src="https://img.shields.io/badge/React-19.x-61DAFB?style=flat-square&logo=react&logoColor=white" />
    <img src="https://img.shields.io/badge/Vite-8.x-646CFF?style=flat-square&logo=vite&logoColor=white" />
    <img src="https://img.shields.io/badge/FastAPI-0.x-009688?style=flat-square&logo=fastapi&logoColor=white" />
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" />
    <img src="https://img.shields.io/badge/MySQL-8.x-4479A1?style=flat-square&logo=mysql&logoColor=white" />
    <img src="https://img.shields.io/badge/Chroma-Vector%20DB-FF6F61?style=flat-square" />
    <img src="https://img.shields.io/badge/Groq-LLM%20Inference-F55036?style=flat-square" />
    <img src="https://img.shields.io/badge/OpenAlex-Academic%20Search-4B5563?style=flat-square" />
  </p>

</div>

---

## 📚 **About the Project**

**AI Study & Research Assistant** is a web-based multi-agent AI system designed to support university students with academic learning and research.

Students often need to search across multiple sources, understand difficult concepts, analyze lengthy documents, summarize research papers, and verify whether information is supported by reliable sources. The system brings these activities together into a single intelligent platform.

The system uses a **Coordinator Agent**, **Research Agent**, **Study/NLP Agent**, and **Verification Agent** that communicate through HTTP-based REST APIs using structured JSON messages.

The architecture combines:

* 🤖 Large Language Models
* 🧠 Natural Language Processing
* 🔎 Information Retrieval
* 📄 Document and PDF Analysis
* ✅ Source Verification
* 🔐 Authentication and Security
* 🗄️ Persistent Data Storage
* 🧩 Multi-Agent Communication
* ⚖️ Responsible AI principles

The project is developed for the **IT3041 – Information Retrieval and Web Analytics Agentic AI-Based System** assignment, which requires a multi-agent system integrating LLMs, NLP, Information Retrieval, security, agent communication protocols, Responsible AI, and a commercialization strategy.

---

# 🚀 **Core Features**

<div align="center" style="margin-bottom: 16px;">
  <img src="https://img.shields.io/badge/Features-Multi--Agent%20Academic%20Assistant-blue?style=for-the-badge" />
</div>

<table>
<tr>
<td width="50%" valign="top">

### 🎓 **Academic Study Assistance**

* **Academic Question Answering**: Ask questions about academic and educational topics
* **Concept Explanation**: Receive simplified explanations of complex concepts
* **Learning Support**: Get structured educational responses
* **Context-Aware Responses**: Uses retrieved information when available
* **Academic-Focused Interaction**: Designed specifically for learning and research

</td>
<td width="50%" valign="top">

### 🔎 **Academic Research**

* **Research Query Processing**: Identify queries requiring external academic information
* **OpenAlex Search**: Retrieve relevant academic works
* **Academic Source Retrieval**: Provide research sources alongside generated responses
* **Relevant Information Retrieval**: Retrieve information related to the user's query
* **Source-Based Answers**: Ground responses using retrieved evidence

</td>
</tr>

<tr>
<td width="50%" valign="top">

### 📄 **Document & PDF Analysis**

* **PDF Upload**: Upload lecture notes, research papers, and learning materials
* **Document Processing**: Extract and process uploaded document content
* **User-Specific Retrieval**: Documents are associated with the authenticated user
* **Semantic Retrieval**: Search uploaded content using vector representations
* **Document Question Answering**: Ask questions based on uploaded materials

</td>
<td width="50%" valign="top">

### 🧠 **NLP & Summarization**

* **Text Preprocessing**: Process retrieved academic content
* **Keyword Processing**: Identify important terms and concepts
* **TF-IDF Summarization**: Classical NLP-based extractive summarization
* **LLM Explanation**: Generate student-friendly explanations
* **Content Processing**: Convert retrieved information into useful learning material

</td>
</tr>

<tr>
<td width="50%" valign="top">

### 🤖 **Multi-Agent Architecture**

* **Coordinator Agent**: Manages the complete workflow
* **Research Agent**: Handles academic Information Retrieval
* **Study/NLP Agent**: Performs NLP processing and educational response generation
* **Verification Agent**: Checks whether generated claims are supported
* **Agent Collaboration**: Agents work together to complete user requests

</td>
<td width="50%" valign="top">

### 🔄 **Intelligent Workflow**

* **Intent Identification**: Determines the type of academic request
* **Task Delegation**: Sends tasks to appropriate specialized agents
* **Evidence Retrieval**: Obtains relevant academic information
* **Response Generation**: Produces an answer using retrieved information
* **Verification**: Checks important claims before the response reaches the user

</td>
</tr>

<tr>
<td width="50%" valign="top">

### 🔐 **Security & Authentication**

* **JWT Authentication**: Secure token-based authentication
* **Password Hashing**: bcrypt-based password protection
* **Input Validation**: Validate user inputs before processing
* **File Validation**: Restrict uploaded file types and sizes
* **User Data Isolation**: Retrieval filtered using `user_id`
* **Protected API Endpoints**: Authentication required for protected operations

</td>
<td width="50%" valign="top">

### ⚖️ **Responsible AI**

* **Source Grounding**: Use retrieved evidence for research-based responses
* **Answer Verification**: Verification Agent checks generated claims
* **Source Transparency**: Retrieved sources are displayed separately
* **Uncertainty Handling**: System can indicate when sufficient evidence is unavailable
* **Privacy Protection**: User documents and account information are protected
* **Academic Misuse Awareness**: Designed to support learning rather than replace student work

</td>
</tr>
</table>

---

# 🏗️ **System Architecture**

<div align="center">

```text
                         ┌─────────────────────┐
                         │      React UI       │
                         │    Port: 5173       │
                         └──────────┬──────────┘
                                    │
                                    │ HTTP / JSON
                                    ▼
                    ┌──────────────────────────────┐
                    │      Coordinator Agent       │
                    │         Port: 8004           │
                    │                              │
                    │ • Intent Understanding       │
                    │ • Task Delegation            │
                    │ • Workflow Coordination      │
                    │ • Final Response             │
                    └──────────────┬───────────────┘
                                   │
                 ┌─────────────────┼─────────────────┐
                 │                 │                 │
                 ▼                 ▼                 ▼
       ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
       │ Research Agent │ │  Study / NLP   │ │ Verification   │
       │    Port 8001   │ │     Agent      │ │     Agent      │
       │                │ │    Port 8002   │ │    Port 8003   │
       │ • OpenAlex     │ │ • NLP          │ │ • Claim Check  │
       │ • Chroma       │ │ • TF-IDF       │ │ • Evidence     │
       │ • IR           │ │ • LLM          │ │ • Confidence   │
       └───────┬────────┘ └────────────────┘ └────────────────┘
               │
       ┌───────┴──────────┐
       ▼                  ▼
┌───────────────┐  ┌───────────────┐
│   OpenAlex    │  │    Chroma     │
│ Academic Data │  │ Vector Store  │
└───────────────┘  └───────────────┘

               ┌───────────────────┐
               │       MySQL       │
               │                   │
               │ • Users           │
               │ • Documents       │
               │ • Chat History    │
               └───────────────────┘
```

</div>

### 🔄 **Agent Communication Flow**

```text
User
 │
 ▼
React Frontend
 │
 ▼
Coordinator Agent
 │
 ├──► Research Agent
 │       │
 │       ├──► OpenAlex
 │       │
 │       └──► Chroma
 │
 ├──► Study/NLP Agent
 │       │
 │       ├──► NLP Processing
 │       ├──► TF-IDF
 │       └──► Groq LLM
 │
 └──► Verification Agent
         │
         └──► Evidence / Claim Verification
                 │
                 ▼
          Coordinator Agent
                 │
                 ▼
            Final Response
                 │
                 ▼
             React UI
```

The system uses HTTP-based REST APIs and structured JSON messages for agent-to-agent communication. This satisfies the assignment requirement for defined communication between interacting intelligent agents.

---

# 🤖 **Intelligent Agents**

<table>
<tr>
<td width="25%" valign="top">

### 🎯 Coordinator Agent

**Port:** `8004`

The Coordinator Agent manages the overall system workflow.

* Receives user requests
* Identifies the required tasks
* Delegates work to specialized agents
* Collects agent responses
* Coordinates the final answer
* Handles the overall request flow

</td>

<td width="25%" valign="top">

### 🔎 Research Agent

**Port:** `8001`

The Research Agent handles Information Retrieval.

* Processes research queries
* Searches OpenAlex
* Searches uploaded documents
* Uses Chroma for vector retrieval
* Returns relevant evidence
* Provides academic sources

</td>

<td width="25%" valign="top">

### 📖 Study/NLP Agent

**Port:** `8002`

The Study/NLP Agent transforms retrieved information into useful educational content.

* NLP processing
* TF-IDF summarization
* Content processing
* LLM-based explanations
* Student-friendly responses

</td>

<td width="25%" valign="top">

### ✅ Verification Agent

**Port:** `8003`

The Verification Agent evaluates the generated response against retrieved evidence.

* Claim checking
* Evidence comparison
* Support status
* Confidence assessment
* Identification of unsupported information

</td>
</tr>
</table>

---

### 🤖 LLM

The system uses the **Groq API** for fast LLM inference.

Default model:

```env
GROQ_MODEL=openai/gpt-oss-120b
```

The model can be changed through the `GROQ_MODEL` environment variable when required.

---

# ⚙️ **Technology Stack**

<div align="center" style="margin-bottom: 16px;">
  <img src="https://img.shields.io/badge/Stack-Multi--Agent%20AI%20%2B%20IR%20%2B%20NLP-blue?style=for-the-badge" />
</div>

<table>
<tr>
<td width="50%" valign="top">

### 🎨 **Frontend Technologies**

<div align="center">

![React](https://img.shields.io/badge/React-19.x-61DAFB?style=flat-square\&logo=react\&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-8.x-646CFF?style=flat-square\&logo=vite\&logoColor=white)

</div>

* **React** – Web user interface
* **Vite** – Frontend build tool and development server
* **JavaScript** – Frontend application logic
* **HTTP APIs** – Communication with the Coordinator API
* **Responsive UI** – Student-focused interface

</td>

<td width="50%" valign="top">

### ⚙️ **Backend Technologies**

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square\&logo=python\&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.x-009688?style=flat-square\&logo=fastapi\&logoColor=white)

</div>

* **Python** – Backend and AI services
* **FastAPI** – REST APIs and independent agent services
* **Uvicorn** – ASGI server
* **Pydantic** – Request and response validation
* **HTTP/JSON** – Agent communication

</td>
</tr>

<tr>
<td width="50%" valign="top">

### 🧠 **AI, NLP & IR**

<div align="center">

![Groq](https://img.shields.io/badge/Groq-LLM-F55036?style=flat-square)
![Chroma](https://img.shields.io/badge/Chroma-Vector%20DB-FF6F61?style=flat-square)

</div>

* **Groq** – LLM inference
* **OpenAI GPT-OSS 120B** – Default LLM model
* **Sentence Transformers** – Text embeddings
* **scikit-learn** – TF-IDF processing and summarization
* **Chroma** – Vector database
* **OpenAlex** – Academic Information Retrieval

</td>

<td width="50%" valign="top">

### 🗄️ **Database & Security**

<div align="center">

![MySQL](https://img.shields.io/badge/MySQL-8.x-4479A1?style=flat-square\&logo=mysql\&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-Authentication-000000?style=flat-square\&logo=jsonwebtokens\&logoColor=white)

</div>

* **MySQL** – Users, documents and chat persistence
* **SQLAlchemy** – Database ORM
* **JWT** – Authentication
* **bcrypt** – Password hashing
* **Input Validation** – Request validation
* **File Validation** – Upload restrictions
* **User-Level Access Control** – Document isolation

</td>
</tr>
</table>

---

# 🌐 **Access the Application**

<table>
<tr>
<td width="50%" valign="top">

### 🎨 **Frontend Application**

* **URL:** `http://localhost:5173`
* **Framework:** React + Vite
* **Purpose:** Student-facing interface
* **Authentication:** JWT-based authentication
* **Features:** Questions, document uploads, answers and sources

</td>

<td width="50%" valign="top">

### 🎯 **Coordinator API**

* **URL:** `http://localhost:8004`
* **Framework:** FastAPI
* **Purpose:** Main application API and workflow coordinator
* **Communication:** HTTP/JSON

</td>
</tr>

<tr>
<td width="50%" valign="top">

### 🔎 **Research Agent**

* **URL:** `http://localhost:8001`
* **Purpose:** Information Retrieval
* **Sources:** OpenAlex + Chroma
* **Role:** Academic research and document retrieval

</td>

<td width="50%" valign="top">

### 📖 **Study/NLP Agent**

* **URL:** `http://localhost:8002`
* **Purpose:** NLP and educational processing
* **Role:** Summarization, processing and explanation

</td>
</tr>

<tr>
<td width="50%" valign="top">

### ✅ **Verification Agent**

* **URL:** `http://localhost:8003`
* **Purpose:** Response verification
* **Role:** Evidence and claim support checking

</td>

<td width="50%" valign="top">

### 🗄️ **Supporting Services**

* **MySQL:** Database persistence
* **Chroma:** Vector retrieval
* **Docker:** Supporting service deployment

</td>
</tr>
</table>

---

# 📸 **Visuals**

<div align="center">
  <img src="https://img.shields.io/badge/Visual%20Preview-AI%20Study%20Assistant-blue?style=for-the-badge" />
</div>

### 🏠 **Application Interface**

<table>
<tr>
<td width="50%" valign="top">

<strong>Registration</strong>

<img width="599" height="854" alt="Screenshot (897)" src="https://github.com/user-attachments/assets/e624d34b-6208-4f73-9218-ea8d189e0c60" />

<em>Secure student authentication with JWT-based access control.</em>

</td>

<td width="50%" valign="top">

<strong>Login</strong>

<img width="595" height="858" alt="Screenshot (896)" src="https://github.com/user-attachments/assets/160c3fbf-7439-4667-a649-ed9afafbba47" />

<em>Secure student authentication with JWT-based access control.</em>

</td>
</tr>

<tr>
<td colspan="2" valign="top">

<strong>Main Dashboard</strong>

<img width="1920" height="860" alt="Main Dashboard" src="https://github.com/user-attachments/assets/3514096d-fba2-4a78-a11a-b65da32a851a" />

<em>Student-facing interface for interacting with the AI Study & Research Assistant.</em>

</td>
</tr>
</table>

### 📄 **Document Analysis**

<table>
<tr>
<td width="50%" valign="top">

**PDF Upload**

<img width="1920" height="865" alt="Screenshot (901)" src="https://github.com/user-attachments/assets/f7a81e03-d35d-4ab1-8268-1513494174ce" />

*Upload lecture materials and academic documents for analysis.*

</td>

</tr>
</table>

### 🔎 **Research & Retrieval**

<table>
<tr>
<td width="50%" valign="top">

**Academic Research**

<img width="1920" height="861" alt="Screenshot (898)" src="https://github.com/user-attachments/assets/dfa7fe90-0409-4742-8228-86904a462675" />

*Retrieve relevant academic works through the Research Agent.*

</td>
</tr>

<tr>
<td width="50%" valign="top">

**Retrieved Sources**

<img width="1920" height="860" alt="Screenshot (900)" src="https://github.com/user-attachments/assets/fa52a5d3-7276-4232-bd32-898cf99d9412" />

*Display academic evidence used during response generation.*

</td>
</tr>
</table>

### 🛡️ **Verification**

<table>
<tr>
<td width="50%" valign="top">

**Verification Result**

<img width="1920" height="866" alt="Screenshot (899)" src="https://github.com/user-attachments/assets/5a77bce0-3ce0-4edb-a464-2797d04de073" />

*Verification Agent checks whether generated claims are supported by retrieved evidence.*

</td>

</tr>
</table>

---

# 📡 **API Documentation**

The backend exposes FastAPI documentation through Swagger UI.

```text
POST /api/auth/register
POST /api/auth/login
GET /health
GET  /api/research
POST /api/chat/ask
POST /ask
POST /api/study
POST /api/verify
POST api/study/process
```

The chat endpoint receives an authenticated student's question and passes it through the multi-agent workflow.

---

# 🔐 **Security Features**

Security is incorporated into the system to protect student accounts, documents and API interactions.

### Authentication & Authorization

* **JWT Authentication** – token-based user authentication
* **Password Hashing** – bcrypt password hashing
* **Protected Endpoints** – authentication required for protected operations
* **User-Level Access Control** – users can access only their own documents

### Input & File Security

* **Input Validation** – validates incoming API data
* **File Type Validation** – restricts uploaded file types
* **File Size Limits** – limits uploaded PDF size
* **Request Validation** – Pydantic-based API validation

### Data Protection

* User documents are associated with authenticated users
* Document retrieval uses `user_id` filtering
* Passwords are not stored as plaintext
* Database persistence is separated from AI processing

---

# ⚖️ **Responsible AI**

Responsible AI is incorporated into the design of the system to reduce risks associated with AI-generated academic information.

### 🎯 Hallucination Reduction

The system does not rely only on the LLM's internal knowledge.

```text
User Question
      ↓
Information Retrieval
      ↓
Retrieved Evidence
      ↓
LLM Response Generation
      ↓
Verification Agent
      ↓
Final Response
```

The Verification Agent checks whether important claims are supported by retrieved evidence.

### 🔎 Transparency

The interface displays retrieved sources separately from the generated response so that students can identify the information used by the system.

### 🔐 Privacy

* Authentication protects user accounts
* User-specific document filtering reduces cross-user access
* Passwords are hashed
* Unnecessary exposure of user documents is avoided

### 📚 Academic Misuse

The system is intended to support learning and research rather than replace student work. Features such as explanations, document analysis, summarization and research guidance are intended to assist students in understanding academic content.

---

# 🛠️ **Installation & Setup**

## 📋 Prerequisites

Make sure the following are installed:

* **Python 3.11+**
* **Node.js 20+**
* **Git**
* **Groq API Key**

---

## 1️⃣ **Clone / Extract the Project**

Extract or clone the repository and open a terminal in the project root.

```bash
cd ai_study_research_assistant
```

---

## 2️⃣ **Start MySQL**


You should see the project database running.

---

## 3️⃣ **Configure the Backend**

Navigate to the backend:

```bash
cd backend
```

Create a Python virtual environment:

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

---

## 4️⃣ **Configure Environment Variables**

```text
.env
```

Configure the required values:

```env
GROQ_API_KEY=your_real_groq_api_key
JWT_SECRET=your_long_random_secret
MYSQL_URL=your_mysql_url
```

---

## 5️⃣ **Start the FastAPI Agents**

From the `backend` directory:

```bash
python run_agents.py
```

The system will start the four FastAPI services:

---

## 6️⃣ **Start the React Frontend**

Open a second terminal.

Navigate to:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Then start the development server:

```bash
npm run dev
```

Open the Vite URL, normally:

```text
http://localhost:5173
```

---

# 🧩 **Project Structure**

```text
ai_study_research_assistant/
│
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── coordinator/
│   │   │   ├── research/
│   │   │   ├── study/
│   │   │   └── verification/
│   │   │
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   └── services/
│   │
│   ├── uploads/
│   ├── requirements.txt
│   ├── run_agents.py
│   ├── .env.example
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── assets/
│   ├── package.json
│   └── .env.example
│
├── chroma_data/
│
├── sql/
│
├── docker-compose.yml
│
├── uploads/
│
├── .gitignore
│
└── README.md
```

---

# 💼 **Commercialization Strategy**

The system can be developed into a subscription-based academic assistance platform.

### 🎯 Target Market

**Primary users:**

* University students
* Researchers
* Lecturers
* Postgraduate students

**Potential future users:**

* Educational institutions

### 💎 Value Proposition

The system brings academic research, document understanding, summarization and study assistance into one platform.

Students can ask questions, retrieve academic sources and analyze their learning materials without switching between multiple tools.

### 💰 Pricing Model

A proposed **freemium model** can be used:

| Plan                | Example Features                                                      |
| ------------------- | --------------------------------------------------------------------- |
| **Free**            | Limited study questions and basic document analysis                   |
| **Student Premium** | Higher usage limits, advanced document analysis and research features |
| **Institutional**   | University-level access with customized features and user limits      |

A proposed student premium price can be considered around **Rs. 999/month**, while institutional pricing can be customized based on user numbers and required features.

> Pricing figures are proposed project assumptions and are not presented as validated market research.

---

# 📜 **License**

This project was developed as an academic project for the **IT3041 – Information Retrieval and Web Analytics** module.

---

<div align="center">

# 🧠 ResearchMind - AI Study & Research Assistant

**Research Smarter. Learn Better. Get Evidence-Based Answers.**

<br>

### 🤝 **Multi-Agent Academic Intelligence**

**Coordinator Agent • Research Agent • Study/NLP Agent • Verification Agent**

<br>

<img src="https://img.shields.io/badge/LLM-Groq-F55036?style=flat-square" />
<img src="https://img.shields.io/badge/NLP-TF--IDF-3776AB?style=flat-square" />
<img src="https://img.shields.io/badge/IR-OpenAlex%20%2B%20Chroma-4B5563?style=flat-square" />
<img src="https://img.shields.io/badge/Communication-HTTP%20%2B%20JSON-009688?style=flat-square" />
<img src="https://img.shields.io/badge/Security-JWT%20%2B%20bcrypt-000000?style=flat-square" />

<br><br>

**IT3041 – Information Retrieval and Web Analytics**

**Agentic AI-Based System Development**

</div>
