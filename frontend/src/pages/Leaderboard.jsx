import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../state/auth.jsx'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

// Format date to Vietnamese locale (Asia/Ho_Chi_Minh)
const toVietnameseTime = (dateStr) => {
  if (!dateStr) return ""
  try {
    return new Date(dateStr).toLocaleString("vi-VN", {
      timeZone: "Asia/Ho_Chi_Minh",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    })
  } catch {
    return new Date(dateStr).toLocaleString()
  }
}

export default function Leaderboard(){
  const { API, token } = useAuth()
  const [items, setItems] = useState([])
  const [datasets, setDatasets] = useState([]) // API may return array or {items:[]}
  const [selectedDatasetId, setSelectedDatasetId] = useState('')
  const [history, setHistory] = useState([])
  const [selectedGroup, setSelectedGroup] = useState('')
  const [metric, setMetric] = useState('AUC')

  const authHeaders = token ? { Authorization: `Bearer ${token}` } : null

  const load = async ()=>{
    try {
      const opts = authHeaders ? { headers: authHeaders } : undefined
      const dsResp = await axios.get(`${API}/datasets/`, opts)
      const dsData = dsResp.data
      setDatasets(Array.isArray(dsData) ? dsData : (dsData && dsData.items) ? dsData.items : [])

      const params = new URLSearchParams()
      if (metric) params.append('metric', metric)
      if (selectedDatasetId) params.append('dataset_id', selectedDatasetId)
      const lbResp = await axios.get(`${API}/leaderboard/?${params.toString()}`, opts)
      const lbData = lbResp.data
      setItems(Array.isArray(lbData) ? lbData : (lbData && lbData.items) ? lbData.items : [])
    } catch (err) {
      // keep UI responsive; log for debugging
      // eslint-disable-next-line no-console
      console.warn('Leaderboard load error', err?.response?.status, err?.message)
      setDatasets([])
      setItems([])
    }
  }
  useEffect(()=>{ load() }, [metric, selectedDatasetId])

  const loadHistory = async (group, dsid)=>{
    setSelectedGroup(group)
    try {
      const opts = authHeaders ? { headers: authHeaders } : undefined
      const r = await axios.get(
        `${API}/leaderboard/history?group_name=${encodeURIComponent(group)}&dataset_id=${dsid}`,
        opts
      )
      setHistory(r.data.map((x,i)=>({i, auc:x.auc})))
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn('History load error', err?.response?.status, err?.message)
      setHistory([])
    }
  }

  const getDatasetName = (id)=>{
    if (id === null || id === undefined) return '-'
    const d = datasets.find(ds => String(ds.id) === String(id))
    return d ? (d.name ?? `Dataset ${d.id}`) : `Dataset ${id}`
  }

  // Get medal emoji for top 3
  const getMedal = (rank) => {
    if (rank === 1) return '🥇'
    if (rank === 2) return '🥈'
    if (rank === 3) return '🥉'
    return rank
  }

  const _looksLikeAutoUser = (v) => {
    if (!v) return false
    return /^user[_-]?\d+$/i.test(String(v))
  }

  const getGroupDisplay = (x) => {
    if (x?.group_name && !_looksLikeAutoUser(x.group_name)) return x.group_name
    if (x?.gr && !_looksLikeAutoUser(x.gr)) return x.gr
    return '-'
  }

  const getUploaderDisplay = (x) => {
    if (x?.uploader_username) return x.uploader_username
    if (x?.uploader_full_name) return x.uploader_full_name
    if (x?.gr && !_looksLikeAutoUser(x.gr)) return x.gr
    if (x?.uploader_id != null) return String(x.uploader_id)
    return '-'
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-brand-500 to-brand-600 bg-clip-text text-transparent">
            Leaderboard
          </h1>
          <p className="text-navy-600 mt-2">Track team performance and rankings</p>
        </div>
      </div>

      <div className="card">
        <div className="flex gap-4 items-center flex-wrap">
            <div>
              <div className="label">Dataset</div>
              <select className="input w-64" value={selectedDatasetId} onChange={e=>setSelectedDatasetId(e.target.value)}>
                <option value="">(All datasets)</option>
                {datasets.map(ds=> (
                  <option key={ds.id} value={ds.id}>{ds.name ?? `Dataset ${ds.id}`}</option>
                ))}
              </select>
            </div>
          <div>
            <div className="label">Sort by Metric</div>
            <select className="input w-48" value={metric} onChange={e=>setMetric(e.target.value)}>
              <option value="AUC">AUC</option>
              <option value="F1">F1 Score</option>
              <option value="PRECISION">Precision</option>
              <option value="RECALL">Recall</option>
              <option value="ACC">Accuracy</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr>
              <th className="text-center w-16">Rank</th>
              <th>Team/Group</th>
              <th>Uploader</th>
              <th>Dataset</th>
              <th className={`cursor-pointer ${metric==='AUC' ? 'text-brand-600' : ''}`} onClick={()=>setMetric('AUC')}>
                AUC {metric==='AUC' && '↓'}
              </th>
              <th className={`cursor-pointer ${metric==='F1' ? 'text-brand-600' : ''}`} onClick={()=>setMetric('F1')}>
                F1 {metric==='F1' && '↓'}
              </th>
              <th className={`cursor-pointer ${metric==='PRECISION' ? 'text-brand-600' : ''}`} onClick={()=>setMetric('PRECISION')}>
                Precision {metric==='PRECISION' && '↓'}
              </th>
              <th className={`cursor-pointer ${metric==='ACC' ? 'text-brand-600' : ''}`} onClick={()=>setMetric('ACC')}>
                Accuracy {metric==='ACC' && '↓'}
              </th>
              <th className={`cursor-pointer ${metric==='RECALL' ? 'text-brand-600' : ''}`} onClick={()=>setMetric('RECALL')}>
                Recall {metric==='RECALL' && '↓'}
              </th>
              <th className="text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((x, i)=> (
              <tr key={x.submission_id || i} className={i < 3 ? 'bg-brand-50/30' : ''}>
                <td className="text-center font-bold text-lg">
                  {typeof getMedal(i+1) === 'string' ? getMedal(i+1) : (
                    <span className="text-navy-700">{i+1}</span>
                  )}
                </td>
                <td className="font-semibold text-navy-700">{getGroupDisplay(x)}</td>
                <td className="text-navy-600">{getUploaderDisplay(x)}</td>
                <td className="text-navy-600">{getDatasetName(x.dataset_id)}</td>
                <td className={metric==='AUC' ? 'font-bold text-brand-600' : ''}>
                  {(x.auc!=null) ? x.auc.toFixed?.(4) ?? x.auc : '-'}
                </td>
                <td className={metric==='F1' ? 'font-bold text-brand-600' : ''}>
                  {(x.f1!=null) ? x.f1.toFixed?.(4) ?? x.f1 : '-'}
                </td>
                <td className={metric==='PRECISION' ? 'font-bold text-brand-600' : ''}>
                  {(x.precision!=null) ? x.precision.toFixed?.(4) ?? x.precision : '-'}
                </td>
                <td className={metric==='ACC' ? 'font-bold text-brand-600' : ''}>
                  {(x.acc!=null) ? x.acc.toFixed?.(4) ?? x.acc : '-'}
                </td>
                <td className={metric==='RECALL' ? 'font-bold text-brand-600' : ''}>
                  {(x.recall!=null) ? x.recall.toFixed?.(4) ?? x.recall : '-'}
                </td>
                <td className="text-center">
                  <button 
                    className="btn text-sm px-3 py-1.5" 
                    onClick={()=>loadHistory(getGroupDisplay(x), x.dataset_id)}
                  >
                    View History
                  </button>
                </td>
              </tr>
            ))}
            {items.length===0 && (
              <tr>
                <td className="p-8 text-center text-slate-500" colSpan={10}>
                  No submissions found for the selected dataset/metric.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {history.length>0 && (
        <div className="card">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-navy-700">
            <span className="text-2xl">📈</span>
            AUC Performance Over Time — <span className="text-brand-600">{selectedGroup}</span>
          </h2>
          <div style={{width:'100%', height:300}}>
            <ResponsiveContainer>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis 
                  dataKey="i" 
                  label={{ value: 'Submission #', position: 'insideBottom', offset: -5 }}
                  tick={{ fill: '#64748B', fontSize: 12 }}
                />
                <YAxis 
                  domain={['auto','auto']} 
                  tick={{ fill: '#64748B', fontSize: 12 }}
                  label={{ value: 'AUC Score', angle: -90, position: 'insideLeft' }}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#FFF', 
                    border: '1px solid #E2E8F0',
                    borderRadius: '12px',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
                  }}
                />
                <Line 
                  type="monotone" 
                  dataKey="auc" 
                  stroke="#4318FF" 
                  strokeWidth={3}
                  dot={{ fill: '#4318FF', r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
