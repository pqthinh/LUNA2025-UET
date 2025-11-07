import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../state/auth.jsx'

export default function Dashboard(){
  const { API, authHeader } = useAuth()
  const [datasets, setDatasets] = useState({items:[]})
  const [subs, setSubs] = useState({items:[]})

  useEffect(()=>{
    axios.get(`${API}/datasets/`).then(r=>setDatasets(r.data))
    axios.get(`${API}/submissions/`, { headers: authHeader }).then(r=>setSubs(r.data))
  }, [])

  const official = datasets.items.find(d=>d.is_official)

  return (
    <div className="space-y-4">
      <div className="text-2xl font-semibold">Dashboard</div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">Datasets: <b>{datasets.total || 0}</b></div>
        <div className="card">Submissions: <b>{subs.total || 0}</b></div>
        <div className="card">Official dataset: <b>{official?.name || '—'}</b></div>
      </div>
    </div>
  )
}
