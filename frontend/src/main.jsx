import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import logo from './assets/researchmind-logo.png';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const QUICK_TOPICS = [
  { icon: '📄', label: 'Summarize PDF', prompt: 'Summarize my uploaded PDF' },
  { icon: '🔎', label: 'Find papers', prompt: 'Find research papers about this topic' },
  { icon: '💡', label: 'Explain concept', prompt: 'Explain this concept with examples' },
  { icon: '⚖️', label: 'Compare theories', prompt: 'Compare these theories clearly' },
  { icon: '🧠', label: 'Study notes', prompt: 'Turn this into study notes' },
  { icon: '✅', label: 'Verify answer', prompt: 'Verify this answer with evidence' },
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

  async function auth(e) {
    e.preventDefault();
    setStatus('');

    const errors = {};
    const trimmedName = name.trim();
    const trimmedEmail = email.trim();
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (mode === 'register' && trimmedName.length < 2) {
      errors.name = 'Enter your full name.';
    }

    if (!trimmedEmail) {
      errors.email = 'Enter your email address.';
    } else if (!emailPattern.test(trimmedEmail)) {
      errors.email = 'Enter a valid email address.';
    }

    if (!password) {
      errors.password = 'Enter your password.';
    } else if (password.length < 8) {
      errors.password = 'Password must be at least 8 characters.';
    } else if (password.length > 72) {
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

  async function upload() {
    if (!file) {
      setStatus('Choose a PDF before uploading.');
      return;
    }

    try {
      await uploadSelectedFile();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Upload failed';
      setStatus(errorMessage);
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

  async function ask() {
    const submittedQuestion = question.trim();
    if (!submittedQuestion || isAsking) return;

    const attachedFileName = file?.name || '';
    const userMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: submittedQuestion,
      attachedFileName,
    };
    const pendingMessage = { id: crypto.randomUUID(), role: 'assistant', loading: true };

    setMessages((current) => [...current, userMessage, pendingMessage]);
    setQuestion('');
    setIsAsking(true);
    setStatus(file ? 'Uploading PDF, then asking ResearchMind...' : 'Coordinator is choosing the best agent route...');

    try {
      let uploadedFile = null;
      let apiQuestion = submittedQuestion;
      if (file) {
        uploadedFile = await uploadSelectedFile();
        apiQuestion = `${submittedQuestion}\n\nUse the uploaded PDF/document as the source. Uploaded file: ${uploadedFile.filename}.`;
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
  }

  function removeAttachedFile() {
    setFile(null);
    setStatus('');
  }

  function renderComposer(isCompact = false) {
    return (
      <section className={`composer-panel ${isCompact ? 'compact' : ''}`}>
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
            placeholder={file ? 'Ask about the attached PDF...' : 'Ask your question...'}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                ask();
              }
            }}
          />
          <button className="send-button" type="button" onClick={ask} disabled={isAsking} aria-label="Ask ResearchMind">
            {isAsking ? '...' : 'Send'}
          </button>
        </div>

        <div className="composer-footer">
          <p className="composer-hint">
            {file ? 'Send will upload the PDF first, then ask your question.' : 'Enter to send. Shift + Enter for a new line.'}
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
                <div className="feature-card" key={topic.label}>
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
            <section className="conversation" aria-live="polite">
              {messages.map((message) => (
                <article className={`message ${message.role}`} key={message.id}>
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
                        <div className="answer">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                        </div>

                        {message.verification && (
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
                          </div>
                        )}

                        {message.sources?.length ? (
                          <details className="evidence-drawer">
                            <summary>Sources</summary>
                            {message.sources.map((s, i) => (
                              <div className="source" key={`${s.title}-${i}`}>
                                <b>{s.title}</b> ({s.year || 'n.d.'})
                                <br />
                                {s.doi || s.url ? (
                                  <a href={s.doi || s.url} target="_blank" rel="noopener noreferrer">
                                    {s.doi || s.url}
                                  </a>
                                ) : (
                                  <span>No DOI/URL returned</span>
                                )}
                              </div>
                            ))}
                          </details>
                        ) : null}
                      </>
                    )}
                  </div>
                </article>
              ))}
            </section>

            {renderComposer(true)}
          </section>
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
