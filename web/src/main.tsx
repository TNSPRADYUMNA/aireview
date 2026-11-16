import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

type Finding = { id:string; line:number; title:string; evidence:string; suggestion:string; confidence:string }
type Feedback = { finding_id:string; decision:string; correction:string }
type Report = { id:string; changed_lines:number; findings:Finding[]; feedback?:Feedback[] }

async function request<T>(url:string, options?:RequestInit):Promise<T> {
  const response = await fetch(url, options)
  if (!response.ok) throw new Error('Request failed (' + response.status + ').')
  return response.json()
}

function App() {
  const [before,setBefore] = useState('def collect(items=None):\n    return [] if items is None else items\n')
  const [after,setAfter] = useState('def collect(items=[]):\n    return items\n')
  const [report,setReport] = useState<Report|null>(null)
  const [feedback,setFeedback] = useState<Record<string,string>>({})
  const [notes,setNotes] = useState<Record<string,string>>({})
  const [message,setMessage] = useState('')
  const [busy,setBusy] = useState(false)
  const [draft,setDraft] = useState('')
  function load(data:Report) {
    setReport(data)
    setDraft('')
    setFeedback(Object.fromEntries((data.feedback ?? []).map(item => [item.finding_id,item.decision])))
    setNotes(Object.fromEntries((data.feedback ?? []).map(item => [item.finding_id,item.correction])))
  }
  useEffect(() => {
    const id = new URLSearchParams(location.search).get('review')
    if (id) request<Report>('/api/review/' + encodeURIComponent(id)).then(load).catch(error=>setMessage(error.message))
  }, [])
  async function analyze(event:React.FormEvent) {
    event.preventDefault(); setBusy(true); setMessage('')
    try {
      const data = await request<Report>('/api/review', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({before,after})})
      load(data)
      history.replaceState(null,'','?review=' + data.id)
    } catch(error) { setMessage(String(error)) }
    finally {setBusy(false)}
  }
  async function save(id:string, decision:string) {
    if (!report) return
    try {
      await request('/api/review/' + report.id + '/feedback/' + id, {method:'PUT',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({decision,correction:notes[id] ?? ''})})
      setFeedback(old=>({...old,[id]:decision})); setMessage('Feedback saved.')
    } catch(error) { setMessage(String(error)) }
  }
  return <main>
    <header><a href="/">AIReview</a><a href="/docs">API docs</a></header>
    <section className="hero"><h1>Review a Python change</h1><p>Inspect findings tied to changed lines and record your review decision.</p></section>
    <form onSubmit={analyze}><div className="editors">
      <label>Before<textarea value={before} onChange={e=>setBefore(e.target.value)} /></label>
      <label>After<textarea value={after} onChange={e=>setAfter(e.target.value)} /></label>
    </div><button disabled={busy}>{busy ? 'Reviewing…' : 'Review changes'}</button></form>
    <p role="status">{message}</p>
    {report && <section><h2>{report.findings.length} findings <span>· {report.changed_lines} changed lines</span></h2>
      {report.findings.length > 0 && <button onClick={() => request<{draft:string}>('/api/review/' + report.id + '/draft', {method:'POST'})
        .then(value=>setDraft(value.draft)).catch(error=>setMessage(error.message))}>Draft summary with LLM</button>}
      {draft && <p>{draft}</p>}
      {report.findings.map(f=><details key={f.id}><summary><strong>{f.title}</strong><span>Line {f.line} · {f.confidence}</span></summary>
        <pre>{f.evidence}</pre><p>{f.suggestion}</p>
        <label>Correction<textarea value={notes[f.id] ?? ''} placeholder="Describe a better finding" onChange={e=>setNotes(old=>({...old,[f.id]:e.target.value}))}/></label>
        <div className="actions"><button onClick={()=>save(f.id,'accepted')}>Accept</button><button onClick={()=>save(f.id,'rejected')}>Reject</button>
        <button disabled={!notes[f.id]?.trim()} onClick={()=>save(f.id,'corrected')}>Save correction</button>
        {feedback[f.id] && <span>Saved as {feedback[f.id]}</span>}</div>
      </details>)}
    </section>}
  </main>
}

createRoot(document.getElementById('root')!).render(<App />)
