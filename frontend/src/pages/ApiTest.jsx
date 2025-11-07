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
      const msg = ex.response?.data?.detail || 'Call failed'
      setErr(msg)
      window.alert('API Error: ' + msg)
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
        <div className="card text-sm space-y-3">
          <div>Status: <b>{result.status_code}</b> — Latency: <b>{result.latency_ms?.toFixed?.(1) ?? ''} ms</b></div>

          {/* Render ảnh nếu có */}
          {result.image_base64 && (
            <img src={`data:image/png;base64,${result.image_base64}`} alt="Result" className="max-w-xs border rounded" />
          )}
          {result.image_url && (
            <img src={result.image_url} alt="Result" className="max-w-xs border rounded" />
          )}
          {/* Nếu không có các trường trên, thử parse preview là JSON */}
          {(() => {
            let parsed;
            try { parsed = typeof result.preview === 'string' ? JSON.parse(result.preview) : null; } catch(e) { parsed = null }
            if (!parsed) return null;
            return <>
              {parsed.image_base64 && (<img src={`data:image/png;base64,${parsed.image_base64}`} alt="Result" className="max-w-xs border rounded" />)}
              {parsed.image_url && (<img src={parsed.image_url} alt="Result" className="max-w-xs border rounded" />)}
              {parsed.coords && (
                <div>
                  <b>Tọa độ tổn thương:</b>
                  <ul>
                    <li>X: {parsed.coords.CoordX}</li>
                    <li>Y: {parsed.coords.CoordY}</li>
                    <li>Z: {parsed.coords.CoordZ}</li>
                    <li>LesionID: {parsed.coords.LesionID}</li>
                  </ul>
                </div>)}
              {parsed.info && (
                <div>
                  <b>Thông tin bệnh nhân:</b>
                  <ul>
                    <li>PatientID: {parsed.info.PatientID}</li>
                    <li>Tuổi: {parsed.info.Age_at_St}</li>
                    <li>Giới tính: {parsed.info.Gender}</li>
                  </ul>
                </div>)}
            </>;
          })()}

          {/* Render trực tiếp output fields (coords, info) nếu có */}
          {result.coords && (
            <div>
              <b>Tọa độ tổn thương:</b>
              <ul>
                <li>X: {result.coords.CoordX}</li>
                <li>Y: {result.coords.CoordY}</li>
                <li>Z: {result.coords.CoordZ}</li>
                <li>LesionID: {result.coords.LesionID}</li>
              </ul>
            </div>
          )}
          {result.info && (
            <div>
              <b>Thông tin bệnh nhân:</b>
              <ul>
                <li>PatientID: {result.info.PatientID}</li>
                <li>Tuổi: {result.info.Age_at_St}</li>
                <li>Giới tính: {result.info.Gender}</li>
              </ul>
            </div>
          )}

          <pre className="mt-2 overflow-auto whitespace-pre-wrap break-words">{typeof result.preview === 'object' ? JSON.stringify(result.preview,null,2) : result.preview}</pre>
        </div>
      )}
    </div>
  )
}
