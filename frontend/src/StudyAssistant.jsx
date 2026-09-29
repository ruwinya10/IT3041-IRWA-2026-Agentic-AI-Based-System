import React, { useState } from 'react';

export default function StudyAssistant({ token, API }) {
  const [content, setContent] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState(null);
  const [activeTask, setActiveTask] = React.useState(null);

  async function processTask(task, options = {}) {
    if (!content.trim()) return;
    setLoading(true);
    setActiveTask(task);
    setResult(null);
    try {
      const res = await fetch(`${API}/api/study/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ task, content, options })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setResult(data);
      } else {
        setResult({ error: data.error || data.detail || 'Request failed' });
      }
    } catch (e) {
      setResult({ error: 'Network error communicating with Study Agent.' });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="workspace study-workspace">
      <div className="hero">
        <p className="welcome">Study Assistant</p>
        <h2>Turn academic material into something easier to learn.</h2>
      </div>

      <div className="composer-panel">
        <textarea
          rows="6"
          placeholder="Paste academic text here to analyze, summarize, or turn into study materials..."
          value={content}
          onChange={e => setContent(e.target.value)}
          style={{width: '100%', marginBottom: '16px', padding: '15px', borderRadius: '16px', border: '1px solid #cdd8e8', resize: 'vertical'}}
        />
        <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
          <button className="ghost-button" onClick={() => processTask('explain', {level: 'Simple'})} disabled={loading || !content.trim()}>Explain (Simple)</button>
          <button className="ghost-button" onClick={() => processTask('explain', {level: 'Detailed'})} disabled={loading || !content.trim()}>Explain (Detailed)</button>
          <button className="ghost-button" onClick={() => processTask('summarize', {mode: 'Exam Revision'})} disabled={loading || !content.trim()}>Exam Summary</button>
          <button className="ghost-button" onClick={() => processTask('notes')} disabled={loading || !content.trim()}>Study Notes</button>
          <button className="ghost-button" onClick={() => processTask('quiz', {count: 5, difficulty: 'Medium'})} disabled={loading || !content.trim()}>Generate Quiz</button>
          <button className="ghost-button" onClick={() => processTask('flashcards')} disabled={loading || !content.trim()}>Flashcards</button>
          <button className="ghost-button" onClick={() => processTask('keywords')} disabled={loading || !content.trim()}>Extract Keywords</button>
          <button className="ghost-button" onClick={() => processTask('ner')} disabled={loading || !content.trim()}>Named Entities</button>
        </div>
      </div>

      {loading && <div className="status" style={{marginTop: '20px', textAlign: 'center'}}>Processing task: {activeTask}...</div>}

      {result && (
        <div className="conversation" style={{marginTop: '24px', padding: '24px'}}>
          {result.error ? (
            <p className="error-text">{result.error}</p>
          ) : (
            <div className="answer">
              {result.task === 'explain' && result.data && (
                <>
                  <h3>Explanation</h3>
                  <p>{result.data.explanation}</p>
                  <h4>Key Points</h4>
                  <ul>{result.data.key_points?.map((p, i) => <li key={i}>{p}</li>)}</ul>
                  <h4>Important Concepts</h4>
                  <ul>{result.data.important_concepts?.map((c, i) => <li key={i}>{c}</li>)}</ul>
                  {result.data.examples?.length > 0 && (
                    <>
                      <h4>Examples</h4>
                      <ul>{result.data.examples.map((e, i) => <li key={i}>{e}</li>)}</ul>
                    </>
                  )}
                </>
              )}

              {result.task === 'summarize' && result.data && (
                <>
                  <h3>Summary</h3>
                  <p>{result.data.summary}</p>
                  {result.data.bullet_points?.length > 0 && (
                    <ul>{result.data.bullet_points.map((p, i) => <li key={i}>{p}</li>)}</ul>
                  )}
                </>
              )}

              {result.task === 'notes' && result.data && result.data.notes && (
                <>
                  <h3>Study Notes</h3>
                  {Object.entries(result.data.notes).map(([k, v]) => (
                    <div key={k}>
                      <h4>{k}</h4>
                      {Array.isArray(v) ? <ul>{v.map((item, i) => <li key={i}>{item}</li>)}</ul> : <p>{v}</p>}
                    </div>
                  ))}
                </>
              )}

              {result.task === 'quiz' && result.data && result.data.questions && (
                <>
                  <h3>Quiz</h3>
                  {result.data.questions.map((q, i) => (
                    <div key={i} style={{marginBottom: '20px'}}>
                      <strong>Q{i+1}: {q.question}</strong>
                      <ul style={{listStyleType: 'none', paddingLeft: 0, marginTop: '8px'}}>
                        {q.options?.map((opt, j) => (
                          <li key={j} style={{padding: '6px', border: '1px solid #ccc', marginBottom: '4px', borderRadius: '4px'}}>
                            {opt} {opt === q.correct_answer && <span style={{color: 'green', fontWeight: 'bold'}}>✓ Correct</span>}
                          </li>
                        ))}
                      </ul>
                      <p style={{fontSize: '0.9em', color: '#666'}}><em>Explanation: {q.explanation}</em></p>
                    </div>
                  ))}
                </>
              )}

              {result.task === 'flashcards' && result.data && result.data.flashcards && (
                <>
                  <h3>Flashcards</h3>
                  <div style={{display: 'grid', gap: '16px', gridTemplateColumns: '1fr 1fr'}}>
                    {result.data.flashcards.map((f, i) => (
                      <div key={i} style={{border: '1px solid #ccc', borderRadius: '8px', padding: '16px'}}>
                        <div style={{fontWeight: 'bold', marginBottom: '8px', borderBottom: '1px solid #eee', paddingBottom: '8px'}}>Front: {f.front}</div>
                        <div>Back: {f.back}</div>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {result.task === 'keywords' && result.data && result.data.keywords && (
                <>
                  <h3>Extracted Keywords</h3>
                  <div style={{display: 'flex', flexWrap: 'wrap', gap: '8px'}}>
                    {result.data.keywords.map((k, i) => (
                      <div key={i} style={{border: '1px solid var(--primary)', borderRadius: '8px', padding: '8px 12px', background: 'var(--soft-line)'}}>
                        <strong>{k.term}</strong> <span style={{fontSize: '0.8em', color: 'var(--muted)'}}>({k.importance})</span>
                        {k.definition && <p style={{margin: '4px 0 0 0', fontSize: '0.9em'}}>{k.definition}</p>}
                      </div>
                    ))}
                  </div>
                </>
              )}

              {result.task === 'ner' && result.data && result.data.entities && (
                <>
                  <h3>Named Entities (spaCy)</h3>
                  <div style={{display: 'flex', flexWrap: 'wrap', gap: '8px'}}>
                    {result.data.entities.map((e, i) => (
                      <span key={i} style={{background: '#e0f2fe', color: '#0369a1', padding: '4px 8px', borderRadius: '4px', fontSize: '0.9em'}}>
                        {e.text} <strong>[{e.label}]</strong>
                      </span>
                    ))}
                  </div>
                  {result.data.entities.length === 0 && <p>No entities found.</p>}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </main>
  );
}
