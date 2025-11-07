import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../state/auth.jsx'

export default function ApiTest(){
  const { API, authHeader, user } = useAuth()
  const [url, setUrl] = useState('https://httpbin.org/post')
  const [samples, setSamples] = useState([])
  const [sample, setSample] = useState('')
  const [result, setResult] = useState(null)
  const [err, setErr] = useState('')

  useEffect(()=>{
    axios.get(`${API}/apitest/samples`).then(r=>{
      setSamples(r.data)
      if (r.data[0]) setSample(r.data[0].name)
    })
  }, [])

  const callApi = async ()=>{
    setErr(''); setResult(null)
    try{
      const fd = new FormData()
      fd.append('url', url)
      fd.append('sample_name', sample)
      const r = await axios.post(`${API}/apitest/call`, fd, { headers: authHeader })
      setResult(r.data)
    }catch(ex){
      setErr(ex.response?.data?.detail || 'Call failed')
    }
  }

  if (user?.role !== 'admin') return <div className="card">Admin only.</div>

  return (
    <div className="space-y-4">
      <div className="text-2xl font-semibold">API Test (send sample file as multipart)</div>
      <div className="card grid md:grid-cols-3 gap-3 items-end">
        <div>
          <div className="label">Model API URL</div>
          <input className="input" value={url} onChange={e=>setUrl(e.target.value)} />
        </div>
        <div>
          <div className="label">Sample file</div>
          <select className="input" value={sample} onChange={e=>setSample(e.target.value)}>
            {samples.map(x => <option key={x.name} value={x.name}>{x.name}</option>)}
          </select>
        </div>
        <button className="btn" onClick={callApi}>Call API</button>
      </div>
      {err && <div className="text-red-600">{err}</div>}
      {result && (
        <div className="card text-sm">
          <div>Status: <b>{result.status_code}</b> — Latency: <b>{result.latency_ms.toFixed(1)} ms</b></div>
          <pre className="mt-2 overflow-auto whitespace-pre-wrap break-words">{result.preview}</pre>
        </div>
      )}
    </div>
  )
}
