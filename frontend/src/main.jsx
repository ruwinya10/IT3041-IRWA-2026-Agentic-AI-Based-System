import React, { useState, useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import logo from './assets/researchmind-logo.png';
import ResearchSources from './ResearchSources';
import './styles.css';
import ThemeToggle from './ThemeToggle';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const QUICK_TOPICS = [
  { icon: '📄', label: 'Summarize PDF', tool: 'summarize', prompt: 'Summarize my uploaded PDF in exam revision mode' },
  { icon: '🔎', label: 'Find papers', tool: 'chat', prompt: 'Find recent research papers about ' },
  { icon: '💡', label: 'Explain concept', tool: 'explain', prompt: 'Explain the concept of ' },
  { icon: '❓', label: 'Generate quiz', tool: 'quiz', prompt: 'Generate practice quiz questions about ' },
  { icon: '🧠', label: 'Study notes', tool: 'notes', prompt: 'Create structured study notes on ' },
  { icon: '✅', label: 'Verify answer', tool: 'chat', prompt: 'Verify this claim with evidence: ' },
];

function verificationScore(verification) {
  if (!verification) return null;
  if (verification.supported) return 90;
  if (verification.confidence === 'high') return 80;
  if (verification.confidence === 'medium') return 60;
  if (verification.confidence === 'low') return 35;
  return 20;
}

function verificationLabel(verification) {
  if (!verification) return 'Not checked';
  if (verification.verdict) return verification.verdict;
  if (verification.supported) return 'Supported';
  if (verification.confidence === 'medium') return 'Partially supported';
  return 'Needs more evidence';
}

function verificationSummary(verification) {
  if (!verification) return '';
  if (verification.summary) return verification.summary;
  if (verification.issues?.length) return verification.issues[0];
  if (verification.supported) return 'The answer is supported by the evidence checked.';
  return 'More supporting evidence is needed before this answer can be treated as verified.';
}

function shouldShowVerification(verification) {
  if (!verification) return false;
  return verification.evidence_count !== 0;
}

/* ============================================================
   Interactive Study Widgets
   ============================================================ */
function InteractiveQuiz({ questions }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState({});
  const [showResult, setShowResult] = useState(false);

  const qList = Array.isArray(questions)
    ? questions
    : Array.isArray(questions?.questions)
    ? questions.questions
    : [];

  if (!qList || !qList.length) {
    return <p className="muted" style={{ padding: '12px' }}>No quiz questions could be generated. Try with a clearer topic or text snippet.</p>;
  }

  function cleanString(str) {
    return String(str || '')
      .trim()
      .toLowerCase()
      .replace(/^[a-d]\s*[:.)-]\s*/, '')
      .replace(/\.$/, '')
      .trim();
  }

  function isMatch(opt, ans) {
    if (!opt || !ans) return false;
    const o = cleanString(opt);
    const a = cleanString(ans);
    return o === a || o.includes(a) || a.includes(o);
  }

  if (showResult) {
    let score = 0;
    qList.forEach((q, idx) => {
      if (isMatch(selectedAnswers[idx], q.correct_answer)) score++;
    });
    const pct = Math.round((score / qList.length) * 100);
    return (
      <div className="quiz-summary-card">
        <div className="study-badge">Quiz Results</div>
        <div className="quiz-summary-score">{pct}%</div>
        <p>You scored <strong>{score}</strong> out of <strong>{qList.length}</strong> ({pct}% correct).</p>
        <button
          type="button"
          className="primary-button"
          style={{ marginTop: '14px' }}
          onClick={() => {
            setSelectedAnswers({});
            setCurrentIndex(0);
            setShowResult(false);
          }}
        >
          Retake Quiz
        </button>
      </div>
    );
  }

  const currentQ = qList[currentIndex];
  if (!currentQ) return null;

  const userAnswer = selectedAnswers[currentIndex];
  const isAnswered = userAnswer !== undefined;
  const isUserCorrect = isAnswered && isMatch(userAnswer, currentQ.correct_answer);

  return (
    <div className="quiz-container">
      <div className="quiz-header">
        <span>Question {currentIndex + 1} of {qList.length}</span>
        <span className="study-badge">Interactive MCQ Quiz</span>
      </div>
      <div className="quiz-question">{currentQ.question}</div>
      <div className="quiz-options-list">
        {currentQ.options?.map((opt, i) => {
          let btnClass = 'quiz-opt-btn';
          if (isAnswered) {
            if (isMatch(opt, currentQ.correct_answer)) btnClass += ' correct';
            else if (opt === userAnswer) btnClass += ' wrong';
          }
          return (
            <button
              key={i}
              type="button"
              className={btnClass}
              disabled={isAnswered}
              onClick={() => setSelectedAnswers(prev => ({ ...prev, [currentIndex]: opt }))}
            >
              {opt}
            </button>
          );
        })}
      </div>

      {isAnswered && (
        <div className={`quiz-explanation-box ${isUserCorrect ? 'correct' : 'wrong'}`}>
          <strong>{isUserCorrect ? '✓ Correct!' : '✗ Incorrect.'}</strong>{' '}
          {currentQ.explanation}
        </div>
      )}

      {isAnswered && (
        <div className="quiz-nav-row">
          <button
            type="button"
            className="primary-button"
            onClick={() => {
              if (currentIndex < qList.length - 1) {
                setCurrentIndex(currentIndex + 1);
              } else {
                setShowResult(true);
              }
            }}
          >
            {currentIndex < qList.length - 1 ? 'Next Question →' : 'View Final Score'}
          </button>
        </div>
      )}
    </div>
  );
}

function InteractiveFlashcards({ flashcards }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [mastered, setMastered] = useState({});

  if (!flashcards || !flashcards.length) return <p>No flashcards generated.</p>;
  const currentCard = flashcards[currentIndex];

  return (
    <div className="flashcard-box">
      <div className="flashcard-header">
        <span>Card {currentIndex + 1} of {flashcards.length}</span>
        <span className="study-badge">Interactive Flashcards</span>
      </div>
      <div
        className="flashcard-card"
        onClick={() => setIsFlipped(!isFlipped)}
        title="Click to flip"
      >
        <span className="flashcard-side-tag">{isFlipped ? 'Back (Explanation / Definition)' : 'Front (Term / Concept)'}</span>
        <div className="flashcard-text">
          {isFlipped ? currentCard.back : currentCard.front}
        </div>
        <span className="flashcard-hint">↻ Click card to flip</span>
      </div>
      <div className="flashcard-controls">
        <button
          type="button"
          className="ghost-button"
          disabled={currentIndex === 0}
          onClick={() => {
            setIsFlipped(false);
            setCurrentIndex(c => Math.max(0, c - 1));
          }}
        >
          ← Previous
        </button>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            type="button"
            className={`opt-pill ${mastered[currentIndex] === 'know' ? 'active' : ''}`}
            onClick={() => setMastered(prev => ({ ...prev, [currentIndex]: 'know' }))}
          >
            ✓ I know this
          </button>
          <button
            type="button"
            className={`opt-pill ${mastered[currentIndex] === 'revise' ? 'active' : ''}`}
            onClick={() => setMastered(prev => ({ ...prev, [currentIndex]: 'revise' }))}
          >
            ↺ Need to revise
          </button>
        </div>
        <button
          type="button"
          className="primary-button"
          disabled={currentIndex === flashcards.length - 1}
          onClick={() => {
            setIsFlipped(false);
            setCurrentIndex(c => Math.min(flashcards.length - 1, c + 1));
          }}
        >
          Next →
        </button>
      </div>
    </div>
  );
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [authErrors, setAuthErrors] = useState({});
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const messagesEndRef = useRef(null);

  // Study tool modes inside the composer
  const [selectedTool, setSelectedTool] = useState('chat'); // 'chat' | 'explain' | 'summarize' | 'quiz' | 'flashcards' | 'notes' | 'keywords' | 'ner'
  const [explainLevel, setExplainLevel] = useState('Normal'); // 'Simple' | 'Normal' | 'Detailed'
  const [summaryMode, setSummaryMode] = useState('Exam Revision'); // 'Quick Summary' | 'Detailed Summary' | 'Bullet Point Summary' | 'Exam Revision'
  const [quizCount, setQuizCount] = useState(5);
  const [quizDifficulty, setQuizDifficulty] = useState('Medium');

  function scrollToTop(behavior = 'smooth') {
    window.scrollTo({ top: 0, behavior });
  }

  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (lastMessage && lastMessage.role === 'assistant') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [messages]);

  useEffect(() => {
    function handleScroll() {
      if (messages.length === 0) {
        setShowScrollTop(false);
        return;
      }
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      setShowScrollTop(scrollTop > 400);
    }

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, [messages.length]);

  async function auth(e) {
    e.preventDefault();
    setStatus('');

    const errors = {};
    const trimmedName = name.trim();
    const trimmedEmail = email.trim().toLowerCase();
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const namePattern = /^[A-Za-z][A-Za-z .'-]{1,148}$/;
    const strongPasswordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,72}$/;

    if (mode === 'register' && !namePattern.test(trimmedName)) {
      errors.name = 'Enter a valid full name.';
    }

    if (!trimmedEmail) {
      errors.email = 'Enter your email address.';
    } else if (!emailPattern.test(trimmedEmail)) {
      errors.email = 'Enter a valid email address.';
    } else if (mode === 'register' && !trimmedEmail.endsWith('@gmail.com')) {
      errors.email = 'Use a valid Gmail address.';
    }

    if (!password) {
      errors.password = 'Enter your password.';
    } else if (mode === 'register' && !strongPasswordPattern.test(password)) {
      errors.password = 'Use 8-72 characters with uppercase, lowercase, number, and special character.';
    } else if (mode === 'login' && password.length > 72) {
      errors.password = 'Password must be 72 characters or fewer.';
    }

    setAuthErrors(errors);

    if (Object.keys(errors).length > 0) {
      return;
    }

    try {
      const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body =
        mode === 'login'
          ? { email: trimmedEmail, password }
          : { email: trimmedEmail, password, full_name: trimmedName };
      const r = await fetch(API + endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const d = await r.json();

      if (!r.ok) {
        setStatus(d.detail || 'Authentication failed');
        return;
      }

      localStorage.setItem('token', d.access_token);
      setToken(d.access_token);
    } catch (error) {
      console.error(error);
      setStatus('Unable to connect to the backend API.');
    }
  }

  async function uploadSelectedFile() {
    setStatus('Uploading and indexing your PDF...');
    const fd = new FormData();
    fd.append('file', file);

    let r;
    try {
      r = await fetch(API + '/api/documents/upload', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + token },
        body: fd,
      });
    } catch (error) {
      throw new Error('Could not upload the PDF. Check that the backend is running.');
    }

    const d = await r.json().catch(() => ({}));

    if (!r.ok) {
      if (r.status === 401 || d.detail === 'Invalid or expired token') {
        handleAuthExpired();
      }
      throw new Error(d.detail || 'Upload failed');
    }

    setStatus(`Indexed ${d.chunks_indexed} chunks from ${d.filename}`);
    setFile(null);
    return d;
  }

  async function executeStudyAction(task, contentToProcess, customOptions = {}, uploadedFile = null) {
    const text = (contentToProcess || '').trim();
    if (!text || isAsking) return;

    const taskLabels = {
      explain: `Explain Concept (${customOptions.level || explainLevel})`,
      summarize: `Summarize (${customOptions.mode || summaryMode})`,
      quiz: `Quiz (${customOptions.count || quizCount} Qs, ${customOptions.difficulty || quizDifficulty})`,
      flashcards: 'Flashcards',
      notes: 'Study Notes',
      keywords: 'Keywords (TF-IDF NLP)',
      ner: 'Named Entity Recognition (spaCy)'
    };

    const userMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: `${taskLabels[task] || task}: "${text.length > 70 ? text.substring(0, 70) + '...' : text}"`,
      attachedFileName: uploadedFile ? uploadedFile.filename : '',
    };
    const pendingMessage = { id: crypto.randomUUID(), role: 'assistant', loading: true };

    setMessages((current) => [...current, userMessage, pendingMessage]);
    setIsAsking(true);
    setStatus(`Study/NLP Agent is processing ${task}...`);

    try {
      const mergedOptions = {
        level: customOptions.level || explainLevel,
        mode: customOptions.mode || summaryMode,
        count: customOptions.count || quizCount,
        difficulty: customOptions.difficulty || quizDifficulty,
        ...customOptions
      };

      const res = await fetch(`${API}/api/study/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + token,
        },
        body: JSON.stringify({
          task,
          content: text,
          options: mergedOptions,
        }),
      });

      const d = await res.json();
      if (!res.ok || !d.success) {
        if (res.status === 401 || d.detail === 'Invalid or expired token') {
          handleAuthExpired();
          return;
        }
        setMessages((current) =>
          current.map((msg) =>
            msg.id === pendingMessage.id
              ? { ...msg, loading: false, error: d.error || d.detail || 'Request failed' }
              : msg
          )
        );
        setStatus(d.error || d.detail || 'Request failed');
        return;
      }

      setMessages((current) =>
        current.map((msg) =>
          msg.id === pendingMessage.id
            ? {
                ...msg,
                loading: false,
                content: d.data?.summary || d.data?.explanation || `Generated ${task} successfully.`,
                rawContent: text,
                studyTask: task,
                studyData: d.data,
                options: mergedOptions,
                route: 'Study/NLP Agent',
                uploadedFile,
              }
            : msg
        )
      );
      setStatus('Completed.');
    } catch (err) {
      console.error(err);
      setMessages((current) =>
        current.map((msg) =>
          msg.id === pendingMessage.id
            ? { ...msg, loading: false, error: 'Could not connect to the Study/NLP Agent.' }
            : msg
        )
      );
      setStatus('Unable to connect.');
    } finally {
      setIsAsking(false);
    }
  }

  async function executeVerifiedResearchFollowup(label, instruction, baseMessage) {
    const baseAnswer = (baseMessage.rawContent || baseMessage.content || '').trim();
    if (!baseAnswer || isAsking) return;

    const userMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: label,
      attachedFileName: baseMessage.uploadedFile?.filename || '',
    };
    const pendingMessage = { id: crypto.randomUUID(), role: 'assistant', loading: true };

    setMessages((current) => [...current, userMessage, pendingMessage]);
    setIsAsking(true);
    setStatus('Coordinator is retrieving research evidence and verification...');

    try {
      const sourceTitles = (baseMessage.sources || [])
        .slice(0, 5)
        .map((source) => source.title)
        .filter(Boolean)
        .join('; ');
      const followupQuestion = [
        `Research follow-up request: ${instruction}`,
        '',
        `Previous answer: ${baseAnswer}`,
        sourceTitles ? `Previously retrieved research sources: ${sourceTitles}` : '',
        '',
        'Use academic research evidence and include verification.'
      ].filter(Boolean).join('\n');

      const r = await fetch(API + '/api/chat/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + token,
        },
        body: JSON.stringify({ question: followupQuestion }),
      });

      const d = await r.json();

      if (!r.ok) {
        if (r.status === 401 || d.detail === 'Invalid or expired token') {
          handleAuthExpired();
          return;
        }

        setMessages((current) =>
          current.map((message) =>
            message.id === pendingMessage.id
              ? { ...message, loading: false, error: d.detail || 'Request failed' }
              : message
          )
        );
        setStatus(d.detail || 'Request failed');
        return;
      }

      const routeText = (d.route || [])
        .map((agent) => {
          const names = {
            coordinator: 'Coordinator',
            research: 'Research',
            study: 'Study/NLP',
            verification: 'Verification',
          };

          return names[agent] || agent;
        })
        .join(' -> ');

      setMessages((current) =>
        current.map((message) =>
          message.id === pendingMessage.id
            ? {
                ...message,
                loading: false,
                content: d.answer,
                rawContent: d.answer,
                sources: d.sources || [],
                verification: d.verification,
                route: routeText,
                uploadedFile: baseMessage.uploadedFile,
              }
            : message
        )
      );
      setStatus('Completed.');
    } catch (error) {
      console.error(error);
      const errorMessage =
        error instanceof Error ? error.message : 'Unable to run verified research follow-up.';
      setMessages((current) =>
        current.map((item) =>
          item.id === pendingMessage.id
            ? { ...item, loading: false, error: errorMessage }
            : item
        )
      );
      setStatus(errorMessage);
    } finally {
      setIsAsking(false);
    }
  }

  function runFollowup(message, task, label, instruction, options = {}) {
    if (message.sources?.length) {
      executeVerifiedResearchFollowup(label, instruction, message);
      return;
    }

    executeStudyAction(task, message.rawContent || message.content, options);
  }

  async function ask() {
    const submittedQuestion = question.trim();
    if ((!submittedQuestion && !file) || isAsking) return;

    let textToSend = submittedQuestion;
    let uploadedFile = null;

    if (file) {
      setIsAsking(true);
      setStatus('Uploading and indexing PDF...');
      try {
        uploadedFile = await uploadSelectedFile();
        if (!textToSend) {
          textToSend = selectedTool === 'summarize'
            ? `Summarize the uploaded PDF document: ${uploadedFile.filename}`
            : selectedTool === 'quiz'
            ? `Generate a practice quiz from the uploaded PDF document: ${uploadedFile.filename}`
            : selectedTool === 'ner'
            ? `Extract named entities from the uploaded PDF document: ${uploadedFile.filename}`
            : selectedTool === 'explain'
            ? `Explain the uploaded PDF document: ${uploadedFile.filename}`
            : selectedTool === 'notes'
            ? `Create study notes from the uploaded PDF document: ${uploadedFile.filename}`
            : selectedTool === 'keywords'
            ? `Extract important keywords from the uploaded PDF document: ${uploadedFile.filename}`
            : selectedTool === 'flashcards'
            ? `Create flashcards from the uploaded PDF document: ${uploadedFile.filename}`
            : `Analyze the uploaded PDF: ${uploadedFile.filename}`;
        } else {
          textToSend = `${textToSend}\n\n[Uploaded Document Context: ${uploadedFile.filename}]`;
        }
      } catch (err) {
        setIsAsking(false);
        setStatus(err.message || 'PDF upload failed.');
        return;
      }
      setIsAsking(false);
    }

    // If a study tool is selected without a PDF, route directly via Study/NLP Agent.
    // Uploaded-PDF tasks go through Coordinator so retrieved document evidence can
    // be passed to Verification Agent.
    if (selectedTool !== 'chat' && !uploadedFile) {
      const toolToRun = selectedTool;
      setQuestion('');
      executeStudyAction(toolToRun, textToSend, {}, uploadedFile);
      return;
    }

    const attachedFileName = uploadedFile?.filename || file?.name || '';
    const userMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: textToSend,
      attachedFileName,
    };
    const pendingMessage = { id: crypto.randomUUID(), role: 'assistant', loading: true };

    setMessages((current) => [...current, userMessage, pendingMessage]);
    setQuestion('');
    setIsAsking(true);
    setStatus('Coordinator is choosing the best agent route...');

    try {
      let apiQuestion = textToSend;
      if (uploadedFile) {
        apiQuestion = `${textToSend}\n\nUse the uploaded PDF/document as the source. Uploaded file: ${uploadedFile.filename}.`;
      }

      setStatus('Coordinator is choosing the best agent route...');

      let r;
      try {
        r = await fetch(API + '/api/chat/ask', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer ' + token,
          },
          body: JSON.stringify({ question: apiQuestion }),
        });
      } catch (error) {
        throw new Error('Could not contact the chat API. Check that backend and all agents are running.');
      }

      const d = await r.json();

      if (!r.ok) {
        if (r.status === 401 || d.detail === 'Invalid or expired token') {
          handleAuthExpired();
          return;
        }

        setMessages((current) =>
          current.map((message) =>
            message.id === pendingMessage.id
              ? { ...message, loading: false, error: d.detail || 'Request failed' }
              : message
          )
        );
        setStatus(d.detail || 'Request failed');
        return;
      }

      const routeText = (d.route || [])
        .map((agent) => {
          const names = {
            coordinator: 'Coordinator',
            research: 'Research',
            study: 'Study/NLP',
            verification: 'Verification',
          };

          return names[agent] || agent;
        })
        .join(' -> ');

      setMessages((current) =>
        current.map((message) =>
          message.id === pendingMessage.id
            ? {
                ...message,
                loading: false,
                content: d.answer,
                rawContent: d.answer,
                sources: d.sources || [],
                verification: d.verification,
                route: routeText,
                uploadedFile,
              }
            : message
        )
      );
      setStatus('Completed.');
    } catch (error) {
      console.error(error);
      const errorMessage =
        error instanceof Error ? error.message : 'Unable to connect to ResearchMind.';
      setMessages((current) =>
        current.map((item) =>
          item.id === pendingMessage.id
            ? { ...item, loading: false, error: errorMessage }
            : item
        )
      );
      setStatus(errorMessage);
    } finally {
      setIsAsking(false);
    }
  }

  function logout() {
    localStorage.removeItem('token');
    setToken('');
  }

  function handleAuthExpired() {
    localStorage.removeItem('token');
    setMessages([]);
    setQuestion('');
    setFile(null);
    setToken('');
    setStatus('Your session expired. Please sign in again.');
  }

  function startNewChat() {
    setMessages([]);
    setQuestion('');
    setStatus('');
    setSelectedTool('chat');
  }

  function removeAttachedFile() {
    setFile(null);
    setStatus('');
  }

  function handleQuickTopicClick(topic) {
    if (topic.tool) {
      setSelectedTool(topic.tool);
    }
    if (topic.prompt) {
      setQuestion(topic.prompt);
    }
  }

  const hasGeneratedAnswer = messages.some(
    (message) => message.role === 'assistant' && !message.loading && Boolean(message.content)
  );

  function getPlaceholder() {
    if (file) return 'Ask about the attached PDF...';
    switch (selectedTool) {
      case 'explain': return `Enter concept to explain (${explainLevel} level)...`;
      case 'summarize': return `Enter topic or paste text to summarize (${summaryMode})...`;
      case 'quiz': return `Enter concept or paste text to generate a ${quizDifficulty} quiz...`;
      case 'flashcards': return 'Enter concept or paste text to generate flashcards...';
      case 'notes': return 'Enter topic or paste content to create structured notes...';
      case 'keywords': return 'Paste text or enter concept to extract NLP keywords...';
      case 'ner': return 'Paste text to run spaCy Named Entity Recognition...';
      default: return 'Ask your question, paste study material, or research a topic...';
    }
  }

  function renderComposer(isCompact = false) {
    return (
      <section className={`composer-panel ${isCompact ? 'compact' : ''}`}>
        {/* Unified Tool Selector inside the composer */}
        <div className="tool-bar">
          <div className="tool-selector">
            <button
              type="button"
              className={`tool-chip ${selectedTool === 'chat' ? 'active' : ''}`}
              onClick={() => setSelectedTool('chat')}
            >
              💬 Ask / Research
            </button>
            <button
              type="button"
              className={`tool-chip ${selectedTool === 'explain' ? 'active' : ''}`}
              onClick={() => setSelectedTool('explain')}
            >
              💡 Explain
            </button>
            <button
              type="button"
              className={`tool-chip ${selectedTool === 'summarize' ? 'active' : ''}`}
              onClick={() => setSelectedTool('summarize')}
            >
              📝 Summarize
            </button>
            <button
              type="button"
              className={`tool-chip ${selectedTool === 'quiz' ? 'active' : ''}`}
              onClick={() => setSelectedTool('quiz')}
            >
              ❓ Quiz
            </button>
            <button
              type="button"
              className={`tool-chip ${selectedTool === 'flashcards' ? 'active' : ''}`}
              onClick={() => setSelectedTool('flashcards')}
            >
              🗂 Flashcards
            </button>
            <button
              type="button"
              className={`tool-chip ${selectedTool === 'notes' ? 'active' : ''}`}
              onClick={() => setSelectedTool('notes')}
            >
              🧠 Notes
            </button>
            <button
              type="button"
              className={`tool-chip ${selectedTool === 'keywords' ? 'active' : ''}`}
              onClick={() => setSelectedTool('keywords')}
            >
              🔑 Keywords
            </button>
          </div>

          {selectedTool === 'explain' && (
            <div className="tool-options">
              <span>Explanation Level:</span>
              {['Simple', 'Normal', 'Detailed'].map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  className={`opt-pill ${explainLevel === lvl ? 'active' : ''}`}
                  onClick={() => setExplainLevel(lvl)}
                >
                  {lvl}
                </button>
              ))}
            </div>
          )}

          {selectedTool === 'summarize' && (
            <div className="tool-options">
              <span>Summary Style:</span>
              {['Quick Summary', 'Detailed Summary', 'Bullet Point Summary', 'Exam Revision'].map((m) => (
                <button
                  key={m}
                  type="button"
                  className={`opt-pill ${summaryMode === m ? 'active' : ''}`}
                  onClick={() => setSummaryMode(m)}
                >
                  {m}
                </button>
              ))}
            </div>
          )}

          {selectedTool === 'quiz' && (
            <div className="tool-options">
              <span>Questions:</span>
              {[5, 10, 15].map((cnt) => (
                <button
                  key={cnt}
                  type="button"
                  className={`opt-pill ${quizCount === cnt ? 'active' : ''}`}
                  onClick={() => setQuizCount(cnt)}
                >
                  {cnt} Qs
                </button>
              ))}
              <span style={{ marginLeft: '10px' }}>Difficulty:</span>
              {['Easy', 'Medium', 'Hard'].map((diff) => (
                <button
                  key={diff}
                  type="button"
                  className={`opt-pill ${quizDifficulty === diff ? 'active' : ''}`}
                  onClick={() => setQuizDifficulty(diff)}
                >
                  {diff}
                </button>
              ))}
            </div>
          )}
        </div>

        {file && (
          <div className="attachment-card">
            <div className="attachment-icon">PDF</div>
            <div>
              <strong>{file.name}</strong>
              <span>{Math.max(1, Math.round(file.size / 1024))} KB ready to send</span>
            </div>
            <button type="button" onClick={removeAttachedFile} aria-label="Remove attached PDF">
              x
            </button>
          </div>
        )}

        <div className="prompt-shell">
          <label className="attach-button" title="Attach PDF">
            +
            <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0])} />
          </label>
          <textarea
            rows="1"
            placeholder={getPlaceholder()}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                ask();
              }
            }}
          />
          <button className="send-button" type="button" onClick={ask} disabled={isAsking} aria-label="Send query">
            {isAsking ? '...' : selectedTool === 'chat' ? 'Send' : 'Run'}
          </button>
        </div>

        <div className="composer-footer">
          <p className="composer-hint">
            {file
              ? 'Send will upload the PDF first, then process with selected tool.'
              : selectedTool === 'chat'
              ? 'Enter to send. Coordinator will route to the best agents.'
              : `Enter to run with ${selectedTool.toUpperCase()} tool. Shift + Enter for newline.`}
          </p>
        </div>

        {status && <p className="status">{status}</p>}
      </section>
    );
  }

  if (!token) {
    return (
      <div className="auth">
        <section className="auth-panel">
          <ThemeToggle />
          <img className="brand-logo" src={logo} alt="ResearchMind logo" />
          <p className="eyebrow">Multi-agent academic assistant</p>
          <h1>ResearchMind</h1>
          <p className="auth-copy">Your AI companion for smarter study & research.</p>

          <form onSubmit={auth} className="auth-form">
            {mode === 'register' && (
              <label>
                <input
                  placeholder="Full name"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    setAuthErrors((current) => ({ ...current, name: '' }));
                  }}
                />
                {authErrors.name && <span className="field-error">{authErrors.name}</span>}
              </label>
            )}
            <label>
              <input
                type="email"
                placeholder="Email address"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setAuthErrors((current) => ({ ...current, email: '' }));
                }}
              />
              {authErrors.email && <span className="field-error">{authErrors.email}</span>}
            </label>
            <label>
              <input
                type="password"
                placeholder="Password (8+ characters)"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setAuthErrors((current) => ({ ...current, password: '' }));
                }}
              />
              {authErrors.password && <span className="field-error">{authErrors.password}</span>}
            </label>
            <button className="primary-button" type="submit">
              {mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <button
            className="text-button"
            type="button"
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login');
              setAuthErrors({});
              setStatus('');
            }}
          >
            {mode === 'login' ? 'Create an account' : 'Back to sign in'}
          </button>

          {status && <p className="status auth-status">{status}</p>}
        </section>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img className="brand-logo" src={logo} alt="ResearchMind logo" />
          <div>
            <h1>ResearchMind</h1>
            <span>Your AI companion for smarter study & research</span>
          </div>
        </div>
        <div className="topbar-actions">
          <ThemeToggle />
          {messages.length > 0 && (
            <button className="ghost-button" type="button" onClick={startNewChat}>
              New chat
            </button>
          )}
          <button className="secondary-button" type="button" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      <main className="workspace">
        {messages.length === 0 ? (
          <section className="home-view">
            <div className="hero">
              <p className="welcome">ResearchMind Workspace</p>
              <h2>Ask, retrieve, explain, and verify academic work.</h2>
              <p>Built for research-heavy study sessions with document upload, academic retrieval, and answer verification.</p>
            </div>

            {renderComposer()}

            <section className="quick-topics" aria-label="ResearchMind features">
              {QUICK_TOPICS.map((topic) => (
                <div
                  className="feature-card"
                  key={topic.label}
                  onClick={() => handleQuickTopicClick(topic)}
                  title={`Click to use: ${topic.label}`}
                >
                  <span className="topic-icon" aria-hidden="true">
                    {topic.icon}
                  </span>
                  <span>{topic.label}</span>
                </div>
              ))}
            </section>
          </section>
        ) : (
          <section className="chat-view">
            {renderComposer(true)}
            
            {hasGeneratedAnswer && (
              <p className="ai-disclaimer" style={{ marginBottom: '20px' }}>
                AI can make mistakes. Please verify important information using reliable sources.
              </p>
            )}

            <section className="conversation" aria-live="polite">
              {[...messages].reverse().map((message, index) => {
                return (
                  <article
                    className={`message ${message.role}`}
                    key={message.id}
                  >
                    <div className="avatar">{message.role === 'user' ? 'You' : 'AI'}</div>
                    <div className="bubble">
                      {message.loading ? (
                            <div className="typing">
                              <span />
                              <span />
                              <span />
                            </div>
                          ) : message.error ? (
                          
                        <p className="error-text">{message.error}</p>
                      ) : message.role === 'user' ? (
                        <>
                          {message.attachedFileName && (
                            <p className="attachment-note">
                              Attached PDF: <strong>{message.attachedFileName}</strong>
                            </p>
                          )}
                          <p>{message.content}</p>
                        </>
                      ) : (
                        <>
                          {message.uploadedFile && (
                            <p className="attachment-note">
                              Used PDF: <strong>{message.uploadedFile.filename}</strong>
                            </p>
                          )}

                          {/* Interactive Study Data Widget */}
                          {message.studyData ? (
                            <div className="study-result-wrapper">
                              {message.studyTask === 'explain' && (
                                <div className="structured-exp">
                                  <div className="study-badge">Academic Explanation ({message.options?.level || 'Normal'})</div>
                                  <div className="exp-section">
                                    <h4>Explanation</h4>
                                    <p>{message.studyData.explanation}</p>
                                  </div>
                                  {message.studyData.key_points?.length > 0 && (
                                    <div className="exp-section">
                                      <h4>Key Points</h4>
                                      <ul>
                                        {message.studyData.key_points.map((pt, i) => (
                                          <li key={i}>{pt}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                  {message.studyData.important_concepts?.length > 0 && (
                                    <div className="exp-section">
                                      <h4>Important Concepts</h4>
                                      <div className="concept-pills">
                                        {message.studyData.important_concepts.map((concept, i) => (
                                          <span key={i} className="concept-pill">{concept}</span>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                  {message.studyData.examples?.length > 0 && (
                                    <div className="exp-section">
                                      <h4>Examples</h4>
                                      <ul>
                                        {message.studyData.examples.map((ex, i) => (
                                          <li key={i}>{ex}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              )}

                              {message.studyTask === 'summarize' && (
                                <div>
                                  <div className="study-badge">Smart Summary ({message.options?.mode || 'Summary'})</div>
                                  <div style={{ lineHeight: 1.7, fontSize: '0.96rem', marginTop: '6px' }}>
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.studyData.summary}</ReactMarkdown>
                                  </div>
                                  {message.studyData.bullet_points?.length > 0 && (
                                    <div style={{ marginTop: '12px' }}>
                                      <strong>Key Takeaways:</strong>
                                      <ul style={{ marginTop: '6px' }}>
                                        {message.studyData.bullet_points.map((pt, i) => (
                                          <li key={i}>{pt}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                  {message.studyData.extractive_summary && (
                                    <details className="evidence-drawer" style={{ marginTop: '12px' }}>
                                      <summary style={{ cursor: 'pointer', color: 'var(--teal)', fontWeight: 700 }}>
                                        Classical NLP Extractive Summary (TF-IDF)
                                      </summary>
                                      <p style={{ marginTop: '8px', fontSize: '0.9rem', color: 'var(--text)', fontStyle: 'italic', lineHeight: 1.5 }}>
                                        {message.studyData.extractive_summary}
                                      </p>
                                    </details>
                                  )}
                                </div>
                              )}

                              {message.studyTask === 'quiz' && (
                                <InteractiveQuiz questions={message.studyData.questions} />
                              )}

                              {message.studyTask === 'flashcards' && (
                                <InteractiveFlashcards flashcards={message.studyData.flashcards} />
                              )}

                              {message.studyTask === 'keywords' && (
                                <div>
                                  <div className="study-badge">TF-IDF Keyword Extraction (NLP)</div>
                                  <div className="keywords-grid">
                                    {message.studyData.keywords?.map((k, i) => (
                                      <div key={i} className="keyword-card">
                                        <div className="keyword-top">
                                          <span className="keyword-term">{k.term}</span>
                                          <span className={`keyword-badge ${k.importance || 'medium'}`}>
                                            {k.importance || 'keyword'}
                                          </span>
                                        </div>
                                        {k.definition && <p className="keyword-def">{k.definition}</p>}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {message.studyTask === 'ner' && (
                                <div className="ner-group">
                                  <div className="study-badge">Named Entity Recognition (spaCy NLP)</div>
                                  <p style={{ margin: '4px 0 10px', fontSize: '0.86rem', color: 'var(--muted)' }}>
                                    Extracted <strong>{message.studyData.entities?.length || 0}</strong> entities using spaCy pipeline + academic technology extraction:
                                  </p>
                                  <div className="ner-badges-container">
                                    {message.studyData.entities?.map((ent, i) => {
                                      const lbl = (ent.label || '').toLowerCase();
                                      let typeClass = 'default';
                                      if (lbl.includes('person')) typeClass = 'person';
                                      else if (lbl.includes('org')) typeClass = 'organization';
                                      else if (lbl.includes('loc') || lbl.includes('gpe')) typeClass = 'location';
                                      else if (lbl.includes('date')) typeClass = 'date';
                                      else if (lbl.includes('tech') || lbl.includes('product')) typeClass = 'technology';

                                      return (
                                        <span key={i} className={`ner-chip ${typeClass}`}>
                                          <strong>{ent.text}</strong>
                                          <span className="ner-type-tag">{ent.label}</span>
                                        </span>
                                      );
                                    })}
                                  </div>
                                  {(!message.studyData.entities || !message.studyData.entities.length) && (
                                    <p className="muted" style={{ marginTop: '8px' }}>No named entities detected. Try pasting a paragraph containing names, organizations, dates, or technologies.</p>
                                  )}
                                </div>
                              )}

                              {message.studyTask === 'notes' && (
                                <div>
                                  <div className="study-badge">Structured Study Notes</div>
                                  {Object.entries(message.studyData.notes || {}).map(([sec, val], i) => (
                                    <div key={i} className="exp-section" style={{ marginTop: '10px' }}>
                                      <h4>{sec}</h4>
                                      {Array.isArray(val) ? (
                                        <ul>{val.map((item, j) => <li key={j}>{item}</li>)}</ul>
                                      ) : (
                                        <p>{val}</p>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="answer">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {message.content}
                              </ReactMarkdown>
                            </div>
                          )}

                          {shouldShowVerification(message.verification) && (
                            <div className="verification-card">
                              <div>
                                <span>Verification</span>
                                <strong>{verificationLabel(message.verification)}</strong>
                              </div>

                              <div className="verification-score">
                                {verificationScore(message.verification)}%
                              </div>

                              <p>
                                Confidence: <b>{message.verification.confidence || 'unknown'}</b>
                                {typeof message.verification.evidence_count === 'number'
                                  ? ` • Evidence checked: ${message.verification.evidence_count}`
                                  : ''}
                              </p>

                              <div className="verification-details">
                                <p>{verificationSummary(message.verification)}</p>

                                {message.verification.issues?.length ? (
                                  <div>
                                    <span>Areas to improve</span>
                                    <ul>
                                      {message.verification.issues.slice(0, 3).map((issue, i) => (
                                        <li key={`${issue}-${i}`}>{issue}</li>
                                      ))}
                                    </ul>
                                  </div>
                                ) : null}

                                {message.verification.corrections?.length ? (
                                  <div>
                                    <span>Suggested fixes</span>
                                    <ul>
                                      {message.verification.corrections.slice(0, 3).map((correction, i) => (
                                        <li key={`${correction}-${i}`}>{correction}</li>
                                      ))}
                                    </ul>
                                  </div>
                                ) : null}
                              </div>
                            </div>
                          )}

                          <ResearchSources sources={message.sources} />

                          

                          {/* Quick Follow-up Study Actions */}
                          <div className="followup-bar">
                            <span className="followup-label">Follow-up Study Actions</span>
                            <div className="followup-chips">
                              <button
                                className="followup-btn"
                                type="button"
                                onClick={() => runFollowup(
                                  message,
                                  'explain',
                                  'Explain the research answer more simply',
                                  'Explain the previous research answer more simply.',
                                  { level: 'Simple' }
                                )}
                              >
                                💡 Explain simpler
                              </button>
                              <button
                                className="followup-btn"
                                type="button"
                                onClick={() => runFollowup(
                                  message,
                                  'explain',
                                  'Explain the research answer in more detail',
                                  'Explain the previous research answer in more detail.',
                                  { level: 'Detailed' }
                                )}
                              >
                                🔍 More detail
                              </button>
                              <button
                                className="followup-btn"
                                type="button"
                                onClick={() => runFollowup(
                                  message,
                                  'summarize',
                                  'Summarize the research answer for exam revision',
                                  'Summarize the previous research answer for exam revision.',
                                  { mode: 'Exam Revision' }
                                )}
                              >
                                📝 Exam summary
                              </button>
                              <button
                                className="followup-btn"
                                type="button"
                                onClick={() => runFollowup(
                                  message,
                                  'quiz',
                                  'Generate a quiz from the research answer',
                                  'Generate a five-question quiz from the previous research answer.',
                                  { count: 5, difficulty: 'Medium' }
                                )}
                              >
                                ❓ Generate quiz
                              </button>
                              <button
                                className="followup-btn"
                                type="button"
                                onClick={() => runFollowup(
                                  message,
                                  'flashcards',
                                  'Create flashcards from the research answer',
                                  'Create flashcards from the previous research answer.',
                                  {}
                                )}
                              >
                                🗂 Flashcards
                              </button>
                              <button
                                className="followup-btn"
                                type="button"
                                onClick={() => runFollowup(
                                  message,
                                  'notes',
                                  'Create study notes from the research answer',
                                  'Create structured study notes from the previous research answer.',
                                  {}
                                )}
                              >
                                🧠 Study notes
                              </button>
                              <button
                                className="followup-btn"
                                type="button"
                                onClick={() => runFollowup(
                                  message,
                                  'keywords',
                                  'Extract keywords from the research answer',
                                  'Extract important keywords from the previous research answer.',
                                  {}
                                )}
                              >
                                🔑 Keywords
                              </button>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
              <div ref={messagesEndRef} />
            </section>

            {showScrollTop && (
              <button
                type="button"
                className="scroll-bottom-btn"
                onClick={() => scrollToTop('smooth')}
                aria-label="Scroll to top"
                title="Scroll to top"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="19" x2="12" y2="5" />
                  <polyline points="5 12 12 5 19 12" />
                </svg>
              </button>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
