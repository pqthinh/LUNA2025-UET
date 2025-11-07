import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../state/auth.jsx'
import { Link } from 'react-router-dom'

export default function Submissions(){
  const { API, authHeader } = useAuth()
  const [datasets, setDatasets] = useState({items:[]})
  const [items, setItems] = useState({items:[]})
  const [datasetId, setDatasetId] = useState('')
  const [file, setFile] = useState(null)
  const [page, setPage] = useState(1)

  const load = ()=>{
    axios.get(`${API}/datasets/`).then(r=>{
      setDatasets(r.data)
      const off = r.data.items.find(x=>x.is_official)
      if (off) setDatasetId(String(off.id))
    })
    axios.get(`${API}/submissions/?page=${page}&page_size=20${datasetId?`&dataset_id=${datasetId}`:''}`, { headers: authHeader })
      .then(r=>setItems(r.data))
  }
  useEffect(()=>{ load() }, [page, datasetId])

  const upload = async (e)=>{
    e.preventDefault()
    const fd = new FormData()
    fd.append('dataset_id', datasetId)
    fd.append('file', file)
    try {
      await axios.post(`${API}/submissions/`, fd, { headers: authHeader })
      load()
    } catch(ex) {
      const msg = ex.response?.data?.detail || 'Upload failed'
      window.alert('Submission upload error: ' + msg)
    }
  }

  const evaluate = async (id)=>{
    try {
      await axios.post(`${API}/submissions/${id}/evaluate`, null, { headers: authHeader })
      load()
    } catch(ex) {
      const msg = ex.response?.data?.detail || 'Evaluate failed'
      window.alert('Evaluate error: ' + msg)
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-2xl font-semibold">Submissions</div>

      <form onSubmit={upload} className="card grid md:grid-cols-3 gap-3 items-end">
        <div>
          <div className="label">Dataset</div>
          <select className="input" value={datasetId} onChange={e=>setDatasetId(e.target.value)}>
            {datasets.items.map(d => <option key={d.id} value={d.id}>{d.name} {d.is_official ? '(Official)' : ''}</option>)}
          </select>
        </div>
        <div>
          <div className="label">Prediction CSV (id,label_pred)</div>
          <input type="file" onChange={e=>setFile(e.target.files[0])} />
        </div>
        <button className="btn">Upload</button>
      </form>

      <div className="grid gap-3">
        {items.items.map(s => (
          <div key={s.id} className="card">
            <div className="flex justify-between items-center">
              <div>
                <div className="font-semibold">Submission #{s.id}</div>
                <div className="text-xs opacity-80">Dataset: {s.dataset_id}</div>
              </div>
              <div className="flex gap-2">
                <button className="btn" onClick={()=>evaluate(s.id)}>Evaluate</button>
                <Link to={`/submissions/${s.id}`} className="btn">Detail</Link>
              </div>
            </div>
            {s.evaluated && s.score_json && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3 text-sm">
                <div>AUC: <b>{s.score_json.AUC?.toFixed?.(4) ?? '—'}</b></div>
                <div>F1: <b>{s.score_json.F1?.toFixed?.(4) ?? '—'}</b></div>
                <div>Accuracy: <b>{s.score_json.Accuracy?.toFixed?.(4) ?? '—'}</b></div>
                <div>Recall: <b>{s.score_json.Recall?.toFixed?.(4) ?? '—'}</b></div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <div className="label">Filter dataset</div>
        <select className="input w-60" value={datasetId} onChange={e=>setDatasetId(e.target.value)}>
          <option value="">All</option>
          {datasets.items.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </div>

      <div className="flex justify-end gap-2">
        <button className="btn" onClick={()=>setPage(Math.max(1,page-1))}>Prev</button>
        <button className="btn" onClick={()=>setPage(page+1)}>Next</button>
      </div>
    </div>
  )
}
