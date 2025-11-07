import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom'
import './index.css'
import LoginPage from './pages/LoginPage.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Datasets from './pages/Datasets.jsx'
import Submissions from './pages/Submissions.jsx'
import SubmissionDetail from './pages/SubmissionDetail.jsx'
import Leaderboard from './pages/Leaderboard.jsx'
import ApiTest from './pages/ApiTest.jsx'
import Notebook from './pages/Notebook.jsx'
import { useAuth, AuthProvider } from './state/auth.jsx'

function AppShell() {
  const { token, user, logout } = useAuth()
  if (!token) return <Navigate to="/login" />

  return (
    <div className="min-h-screen flex">
      <aside className="w-64 bg-slate-800 text-white p-4 space-y-3">
        <div className="text-xl font-semibold">LUNA25</div>
        <nav className="flex flex-col space-y-2">
          <Link to="/" className="hover:underline">Dashboard</Link>
          <Link to="/datasets" className="hover:underline">Datasets</Link>
          <Link to="/submissions" className="hover:underline">Submissions</Link>
          <Link to="/leaderboard" className="hover:underline">Leaderboard</Link>
          <Link to="/apitest" className="hover:underline">API Test</Link>
          <Link to="/notebook" className="hover:underline">Notebook</Link>
        </nav>
        <div className="pt-10 text-sm opacity-80">
          {user ? <>User: <b>{user.username}</b> ({user.role})</> : null}
        </div>
        <button className="btn mt-4" onClick={logout}>Logout</button>
      </aside>
      <main className="flex-1 p-6 space-y-6">
        <Routes>
          <Route path="/" element={<Dashboard/>} />
          <Route path="/datasets" element={<Datasets/>} />
          <Route path="/submissions" element={<Submissions/>} />
          <Route path="/submissions/:id" element={<SubmissionDetail/>} />
          <Route path="/leaderboard" element={<Leaderboard/>} />
          <Route path="/apitest" element={<ApiTest/>} />
          <Route path="/notebook" element={<Notebook/>} />
        </Routes>
      </main>
    </div>
  )
}

function Root() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage/>} />
          <Route path="/*" element={<AppShell/>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(<Root/>)
