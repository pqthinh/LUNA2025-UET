import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../state/auth.jsx'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function Leaderboard(){
  const { API } = useAuth()
  const [items, setItems] = useState([])
  const [datasets, setDatasets] = useState({items:[]})
  const [datasetId, setDatasetId] = useState('')
  const [history, setHistory] = useState([])
  const [selectedGroup, setSelectedGroup] = useState('')

  const load = ()=>{
    axios.get(`${API}/datasets/`).then(r=>setDatasets(r.data))
    axios.get(`${API}/leaderboard/${datasetId ? `?dataset_id=${datasetId}` : ''}`).then(r=>setItems(r.data))
  }
  useEffect(()=>{ load() }, [datasetId])

  const loadHistory = async (group, dsid)=>{
    setSelectedGroup(group)
    const r = await axios.get(`${API}/leaderboard/history?group_name=${encodeURIComponent(group)}&dataset_id=${dsid}`)
    setHistory(r.data.map((x,i)=>({i, auc:x.auc})))
  }

  return (
    <div className="space-y-4">
      <div className="text-2xl font-semibold">Leaderboard (best per group by AUC)</div>

      <div className="flex gap-3 items-center">
        <div className="label">Dataset</div>
        <select className="input w-60" value={datasetId} onChange={e=>setDatasetId(e.target.value)}>
          <option value="">All</option>
          {datasets.items.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </div>

      <div className="card overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left border-b">
              <th className="p-2">#</th>
              <th className="p-2">Group</th>
              <th className="p-2">Dataset</th>
              <th className="p-2">AUC</th>
              <th className="p-2">F1</th>
              <th className="p-2">Sparkline</th>
            </tr>
          </thead>
          <tbody>
            {items.map((x, i)=> (
              <tr key={i} className="border-b">
                <td className="p-2">{i+1}</td>
                <td className="p-2">{x.group_name}</td>
                <td className="p-2">{x.dataset_id}</td>
                <td className="p-2">{x.auc?.toFixed?.(4)}</td>
                <td className="p-2">{x.f1?.toFixed?.(4)}</td>
                <td className="p-2">
                  <button className="btn" onClick={()=>loadHistory(x.group_name, x.dataset_id)}>View</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {history.length>0 && (
        <div className="card">
          <div className="font-semibold mb-2">AUC over time — {selectedGroup}</div>
          <div style={{width:'100%', height:200}}>
            <ResponsiveContainer>
              <LineChart data={history}>
                <XAxis dataKey="i" />
                <YAxis domain={['auto','auto']} />
                <Tooltip />
                <Line type="monotone" dataKey="auc" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
