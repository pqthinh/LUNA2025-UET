import React, { useState } from 'react'
import { useAuth } from '../state/auth.jsx'
import { Navigate } from 'react-router-dom'

export default function LoginPage(){
  const { login, token } = useAuth()
  const [u, setU] = useState('admin')
  const [p, setP] = useState('admin123')
  const [err, setErr] = useState('')

  if (token) return <Navigate to="/" />

  const onSubmit = async (e)=>{
    e.preventDefault()
    try{
      await login(u,p)
    }catch(ex){
      setErr(ex.response?.data?.detail || 'Login failed')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <form onSubmit={onSubmit} className="card w-full max-w-sm space-y-4">
        <div className="text-2xl font-semibold">Login</div>
        {err && <div className="text-red-600 text-sm">{err}</div>}
        <div>
          <div className="label">Username</div>
          <input className="input" value={u} onChange={e=>setU(e.target.value)} />
        </div>
        <div>
          <div className="label">Password</div>
          <input type="password" className="input" value={p} onChange={e=>setP(e.target.value)} />
        </div>
        <button className="btn w-full" type="submit">Sign in</button>
      </form>
    </div>
  )
}
