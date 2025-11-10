import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../state/auth.jsx'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function Leaderboard(){
  const { API, token } = useAuth()
  const [items, setItems] = useState([])
  const [datasets, setDatasets] = useState([]) // API may return array or {items:[]}
  const [datasetId, setDatasetId] = useState('')
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
      if (datasetId) params.append('dataset_id', datasetId)
      if (metric) params.append('metric', metric)
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
  useEffect(()=>{ load() }, [datasetId, metric])

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

  return (
    <div className="space-y-4">
      <div className="text-2xl font-semibold">Leaderboard (submissions)</div>

      <div className="flex gap-3 items-center">
        <div className="label">Dataset</div>
        <select className="input w-60" value={datasetId} onChange={e=>setDatasetId(e.target.value)}>
          <option value="">All</option>
          {datasets.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </div>

      <div className="card overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left border-b">
              <th className="p-2">#</th>
              <th className="p-2">Group</th>
              <th className="p-2">Uploader</th>
              <th className="p-2">Dataset</th>

              {/* clickable metric headers: click to sort by that metric */}
              <th className={`p-2 cursor-pointer ${metric==='AUC' ? 'font-semibold' : ''}`} onClick={()=>setMetric('AUC')}>AUC</th>
              <th className={`p-2 cursor-pointer ${metric==='F1' ? 'font-semibold' : ''}`} onClick={()=>setMetric('F1')}>F1</th>
              <th className={`p-2 cursor-pointer ${metric==='PRECISION' ? 'font-semibold' : ''}`} onClick={()=>setMetric('PRECISION')}>PRECISION</th>
              <th className={`p-2 cursor-pointer ${metric==='ACC' ? 'font-semibold' : ''}`} onClick={()=>setMetric('ACC')}>ACC</th>

              <th className="p-2">Sparkline</th>
            </tr>
          </thead>
          <tbody>
            {items.map((x, i)=> (
              <tr key={x.submission_id || i} className="border-b">
                <td className="p-2">{i+1}</td>
                <td className="p-2">{x.group_name}</td>
                <td className="p-2">{x.gr ?? x.uploader_username ?? x.uploader_id ?? '-'}</td>
                <td className="p-2">{getDatasetName(x.dataset_id)}</td>
                <td className="p-2">{(x.auc!=null) ? x.auc.toFixed?.(4) ?? x.auc : '-'}</td>
                <td className="p-2">{(x.f1!=null) ? x.f1.toFixed?.(4) ?? x.f1 : '-'}</td>
                <td className="p-2">{(x.precision!=null) ? x.precision.toFixed?.(4) ?? x.precision : '-'}</td>
                <td className="p-2">{(x.acc!=null) ? x.acc.toFixed?.(4) ?? x.acc : '-'}</td>
                <td className="p-2">
                  <button className="btn" onClick={()=>loadHistory(x.group_name, x.dataset_id)}>View</button>
                </td>
              </tr>
            ))}
            {items.length===0 && (
              <tr><td className="p-4" colSpan={9}>No submissions found for the selected dataset/metric.</td></tr>
            )}
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
