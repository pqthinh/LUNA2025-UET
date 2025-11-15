import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useParams } from 'react-router-dom'
import { useAuth } from '../state/auth.jsx'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function SubmissionDetail(){
  const { id } = useParams()
  const { API, authHeader } = useAuth()
  const [data, setData] = useState(null)

  useEffect(()=>{
    axios.get(`${API}/submissions/${id}`, { headers: authHeader }).then(r=>setData(r.data))
  }, [id])

  if (!data) return <div>Loading...</div>
  const metrics = data.score_json ?? {}
  const getMetric = (key) => {
    const normalized = key.toLowerCase()
    const variants = [
      normalized,
      normalized.toUpperCase(),
      normalized.charAt(0).toUpperCase() + normalized.slice(1),
    ]
    for (const variant of variants) {
      if (metrics[variant] !== undefined) {
        return metrics[variant]
      }
    }
    return undefined
  }
  const roc = metrics.ROC || {fpr:[], tpr:[]}
  const pr = metrics.PR || {precision:[], recall:[]}
  const rocPoints = roc.fpr.map((x,i)=>({x, y: roc.tpr[i]}))
  const prPoints = pr.precision.map((x,i)=>({x, y: pr.recall[i]}))

  return (
    <div className="space-y-4">
      <div className="text-2xl font-semibold">Submission #{data.id}</div>
      {data.evaluated ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm card">
          <div>AUC: <b>{getMetric("auc")?.toFixed?.(4) ?? '—'}</b></div>
          <div>F1: <b>{getMetric("f1")?.toFixed?.(4) ?? '—'}</b></div>
          <div>Accuracy: <b>{getMetric("acc")?.toFixed?.(4) ?? '—'}</b></div>
          <div>Recall: <b>{getMetric("recall")?.toFixed?.(4) ?? '—'}</b></div>
          <div className="col-span-2">Samples: <b>{data.score_json?.n_samples ?? 0}</b></div>
        </div>
      ) : <div className="card">Not evaluated yet.</div>}

      <div className="card">
        <div className="font-semibold mb-2">ROC Curve</div>
        <div style={{width:'100%', height:300}}>
          <ResponsiveContainer>
            <LineChart data={rocPoints}>
              <XAxis dataKey="x" type="number" domain={[0,1]} />
              <YAxis dataKey="y" type="number" domain={[0,1]} />
              <Tooltip />
              <Line type="monotone" dataKey="y" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <div className="font-semibold mb-2">Precision-Recall Curve</div>
        <div style={{width:'100%', height:300}}>
          <ResponsiveContainer>
            <LineChart data={prPoints}>
              <XAxis dataKey="x" type="number" domain={[0,1]} />
              <YAxis dataKey="y" type="number" domain={[0,1]} />
              <Tooltip />
              <Line type="monotone" dataKey="y" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
