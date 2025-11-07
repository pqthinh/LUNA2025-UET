import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../state/auth.jsx'

export default function Datasets(){
  const { API, authHeader, user } = useAuth()
  const [page, setPage] = useState(1)
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [name, setName] = useState('LUNA25 Test')
  const [desc, setDesc] = useState('')
  const [dataFile, setDataFile] = useState(null)
  const [gtFile, setGtFile] = useState(null)
  const [msg, setMsg] = useState('')

  const load = async ()=> {
    const r = await axios.get(`${API}/datasets/?page=${page}&page_size=20`)
    setItems(r.data.items); setTotal(r.data.total)
  }
  useEffect(()=>{ load() }, [page])

  const upload = async (e)=>{
    e.preventDefault()
    if (!gtFile) { setMsg('Ground truth CSV required'); return }
    const fd = new FormData()
    fd.append('name', name)
    fd.append('description', desc)
    if (dataFile) fd.append('data_file', dataFile)
    fd.append('groundtruth_csv', gtFile)
    await axios.post(`${API}/datasets/`, fd, { headers: authHeader })
    setMsg('Uploaded'); setDataFile(null); setGtFile(null); load()
  }

  const markOfficial = async (id)=>{
    await axios.post(`${API}/datasets/${id}/mark_official`, null, { headers: authHeader })
    load()
  }

  const analyze = async (id)=>{
    await axios.post(`${API}/datasets/${id}/analyze`, null, { headers: authHeader })
    load()
  }

  return (
    <div className="space-y-6">
      <div className="text-2xl font-semibold">Datasets</div>
      {user?.role === 'admin' && (
        <form onSubmit={upload} className="card grid gap-3">
          <div className="grid md:grid-cols-2 gap-3">
            <div>
              <div className="label">Name</div>
              <input className="input" value={name} onChange={e=>setName(e.target.value)} />
            </div>
            <div>
              <div className="label">Description</div>
              <input className="input" value={desc} onChange={e=>setDesc(e.target.value)} />
            </div>
            <div>
              <div className="label">Data file (optional)</div>
              <input type="file" onChange={e=>setDataFile(e.target.files[0])} />
            </div>
            <div>
              <div className="label">Ground truth CSV (id,label)</div>
              <input type="file" required onChange={e=>setGtFile(e.target.files[0])} />
            </div>
          </div>
          <button className="btn w-fit">Upload dataset</button>
          {msg && <div className="text-green-700 text-sm">{msg}</div>}
        </form>
      )}

      <div className="grid gap-3">
        {items.map(d=> (
          <div key={d.id} className="card">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold">{d.name} {d.is_official ? <span className="badge ml-2">Official</span> : null}</div>
                <div className="text-sm opacity-80">{d.description}</div>
              </div>
              {user?.role === 'admin' && (
                <div className="flex gap-2">
                  <button className="btn" onClick={()=>analyze(d.id)}>Analyze</button>
                  <button className="btn" onClick={()=>markOfficial(d.id)}>Mark official</button>
                </div>
              )}
            </div>
            {d.stats_json && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3 text-sm">
                <div>Total: <b>{d.stats_json.total_rows}</b></div>
                <div>Dup IDs: <b>{d.stats_json.duplicate_id}</b></div>
                <div>Null label: <b>{d.stats_json.null_label}</b></div>
                <div>Labels: <b>{Object.entries(d.stats_json.label_distribution || {}).map(([k,v])=>`${k}:${v}`).join(', ')}</b></div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-2">
        <button className="btn" onClick={()=>setPage(Math.max(1,page-1))}>Prev</button>
        <button className="btn" onClick={()=>setPage(page+1)}>Next</button>
      </div>
    </div>
  )
}
