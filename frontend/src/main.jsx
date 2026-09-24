import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App(){
 const [token,setToken]=useState(localStorage.getItem('token')||'');
 const [mode,setMode]=useState('login'); const [email,setEmail]=useState(''); const [password,setPassword]=useState(''); const [name,setName]=useState('');
 const [question,setQuestion]=useState(''); const [answer,setAnswer]=useState(''); const [sources,setSources]=useState([]); const [verification,setVerification]=useState(null); const [file,setFile]=useState(null); const [status,setStatus]=useState('');
 async function auth(e){e.preventDefault(); setStatus(''); const endpoint=mode==='login'?'/api/auth/login':'/api/auth/register'; const body=mode==='login'?{email,password}:{email,password,full_name:name}; const r=await fetch(API+endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); const d=await r.json(); if(!r.ok){setStatus(d.detail||'Authentication failed');return;} localStorage.setItem('token',d.access_token);setToken(d.access_token);}
 async function upload(){if(!file)return;setStatus('Uploading and indexing...');const fd=new FormData();fd.append('file',file);const r=await fetch(API+'/api/documents/upload',{method:'POST',headers:{Authorization:'Bearer '+token},body:fd});const d=await r.json();setStatus(r.ok?`Indexed ${d.chunks_indexed} chunks from ${d.filename}`:(d.detail||'Upload failed'));}
 async function ask(){
  if(!question.trim()) return;

  setStatus('Coordinator is determining the best route...');
  setAnswer('');
  setSources([]);
  setVerification(null);

  try {
    const r = await fetch(
      API + '/api/chat/ask',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + token
        },
        body: JSON.stringify({ question })
      }
    );

    const d = await r.json();

    if(!r.ok){
      setStatus(d.detail || 'Request failed');
      return;
    }

    setAnswer(d.answer);
    setSources(d.sources || []);
    setVerification(d.verification);

    // Show the actual agent route selected by the Coordinator.
    const routeText = (d.route || [])
      .map(agent => {
        const names = {
          coordinator: 'Coordinator',
          research: 'Research',
          study: 'Study/NLP',
          verification: 'Verification'
        };

        return names[agent] || agent;
      })
      .join(' → ');

    if(routeText){
      setStatus(`Completed. Route: ${routeText}`);
    } else {
      setStatus('Completed.');
    }

  } catch(error) {
    console.error(error);
    setStatus('Unable to connect to the AI Study & Research Assistant.');
  }
}

 if(!token)return <div className="auth"><div className="card"><h1>StudyAI</h1><p>AI Study & Research Assistant</p><form onSubmit={auth}>{mode==='register'&&<input placeholder="Full name" value={name} onChange={e=>setName(e.target.value)}/>}<input type="email" placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)} required/><input type="password" placeholder="Password (8+ chars)" value={password} onChange={e=>setPassword(e.target.value)} required/><button>{mode==='login'?'Sign in':'Create account'}</button></form><button className="link" onClick={()=>setMode(mode==='login'?'register':'login')}>{mode==='login'?'Create an account':'Back to sign in'}</button>{status&&<small>{status}</small>}</div></div>
 return <div className="app"><header><div><h1>StudyAI</h1><span>Multi-Agent Academic Assistant</span></div><button onClick={()=>{localStorage.removeItem('token');setToken('')}}>Logout</button></header><main><section className="card"><h2>Ask an academic question</h2><textarea rows="5" placeholder="e.g. Explain overfitting and give an example." value={question} onChange={e=>setQuestion(e.target.value)}/><button onClick={ask}>Ask StudyAI</button><div className="upload"><input type="file" accept="application/pdf" onChange={e=>setFile(e.target.files[0])}/><button onClick={upload}>Upload PDF</button></div><p className="status">{status}</p></section>{answer&&<section className="card"><h2>Answer</h2><div className="answer">
  <ReactMarkdown remarkPlugins={[remarkGfm]}>
    {answer}
  </ReactMarkdown>
</div>
<h3>Retrieved academic sources</h3>{sources.map((s,i)=><div className="source" key={i}>
  <b>{s.title}</b> ({s.year || 'n.d.'})
  <br />

  {s.doi || s.url ? (
    <a
      href={s.doi || s.url}
      target="_blank"
      rel="noopener noreferrer"
    >
      {s.doi || s.url}
    </a>
  ) : (
    <span>No DOI/URL returned</span>
  )}
</div>)}<h3>Verification</h3><pre>{JSON.stringify(verification,null,2)}</pre></section>}</main></div>
}
createRoot(document.getElementById('root')).render(<App/>);
