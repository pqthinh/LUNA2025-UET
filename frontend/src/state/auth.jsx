import React, { createContext, useContext, useEffect, useState } from 'react'
import axios from 'axios'

const API = import.meta.env.VITE_API || 'http://localhost:8000'

const AuthCtx = createContext(null)

export function AuthProvider({children}) {
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [user, setUser] = useState(null)

  useEffect(() => {
    if (token) {
      axios.get(`${API}/users/me`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => setUser(r.data))
        .catch(() => { setUser(null); setToken(''); localStorage.removeItem('token'); })
    }
  }, [token])

  const login = async (username, password) => {
    const data = new URLSearchParams()
    data.append('username', username)
    data.append('password', password)
    const r = await axios.post(`${API}/auth/login`, data)
    setToken(r.data.access_token)
    localStorage.setItem('token', r.data.access_token)
  }

  const logout = () => {
    setToken(''); setUser(null); localStorage.removeItem('token')
  }

  const authHeader = token ? { Authorization: `Bearer ${token}` } : {}

  const value = { token, user, login, logout, API, authHeader }
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}

export function useAuth(){ return useContext(AuthCtx) }
