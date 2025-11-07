import React from 'react'
import { useAuth } from '../state/auth.jsx'

export default function Notebook(){
  const { token } = useAuth()
  const src = `/lite/index.html?token=${encodeURIComponent(token)}&dataset_id=`
  return (
    <div className="space-y-4">
      <div className="text-2xl font-semibold">Notebook (JupyterLite)</div>
      <div className="text-sm text-slate-600">If JupyterLite is deployed at /lite, it will load below. This build provides the iframe hook.</div>
      <div className="h-[75vh]">
        <iframe title="JupyterLite" src={src} className="w-full h-full border rounded" sandbox="allow-scripts allow-same-origin allow-downloads"></iframe>
      </div>
    </div>
  )
}
