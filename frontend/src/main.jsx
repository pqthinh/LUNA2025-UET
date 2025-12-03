import React, {useEffect} from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, NavLink, useLocation, useNavigate } from 'react-router-dom'
import './index.css'
import LoginPage from './pages/LoginPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Datasets from './pages/Datasets.jsx'
import Submissions from './pages/Submissions.jsx'
import SubmissionDetail from './pages/SubmissionDetail.jsx'
import Leaderboard from './pages/Leaderboard.jsx'
import ApiTest from './pages/ApiTest.jsx'
import Notebook from './pages/Notebook.jsx'
import { useAuth, AuthProvider } from './state/auth.jsx'
import Users from './pages/Users.jsx'

function RoleRoute({roles, children}) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" />
  if (!roles.includes(user.role)) {
    return <div className="card m-10">Permission denied (role: {user.role})</div>
  }
  return children;
}

function usePageTitle() {
  const mapping = {
    "/": "Dashboard",
    "/register": "Register",
    "/datasets": "Datasets",
    "/submissions": "Submissions",
    "/leaderboard": "Leaderboard",
    "/apitest": "API Test",
    "/notebook": "Notebook",
    "/users": "Users"
  }
  const path = window.location.pathname.replace(/\/\d+$/,"");
  return mapping[path] || "";
}

function AppShell() {
  const { token, user, logout } = useAuth()
  if (!token) return <Navigate to="/login" />
  
  const [pageTitle, setPageTitle] = React.useState(usePageTitle());

  const [q, setQ] = React.useState('')

  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    setPageTitle(usePageTitle());
  }, [location]);

  const pathBase = location.pathname.replace(/\/\d+$/,'');
  const isSearchEnabled = pathBase === '/datasets' || pathBase.startsWith('/submissions');

  const onSearchKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (!isSearchEnabled) return;
      const dest = pathBase === '/datasets' ? '/datasets' : '/submissions';
      navigate(`${dest}?q=${encodeURIComponent(q || '')}`);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Fixed Sidebar */}
      <aside className="sidebar-fixed">
        <div className="p-6">
          <div className="flex items-center gap-3 mb-8 pb-4 border-b border-slate-200">
            <span className="text-2xl font-bold bg-gradient-to-r from-brand-500 to-brand-600 bg-clip-text text-transparent font-display">
              LUNA25UET
            </span>
          </div>
          <nav className="flex flex-col space-y-2">
            <NavLink to="/" className={({isActive})=> isActive ? 'nav-link nav-link-active' : 'nav-link'}>
              <span className="text-lg mr-2">🏠</span> Dashboard
            </NavLink>
            <NavLink to="/datasets" className={({isActive})=> isActive ? 'nav-link nav-link-active' : 'nav-link'}>
              <span className="text-lg mr-2">📚</span> Datasets
            </NavLink>
            <NavLink to="/submissions" className={({isActive})=> isActive ? 'nav-link nav-link-active' : 'nav-link'}>
              <span className="text-lg mr-2">📤</span> Submissions
            </NavLink>
            <NavLink to="/leaderboard" className={({isActive})=> isActive ? 'nav-link nav-link-active' : 'nav-link'}>
              <span className="text-lg mr-2">🏆</span> Leaderboard
            </NavLink>
            {user?.role === "admin" && (
              <NavLink to="/apitest" className={({isActive})=> isActive ? 'nav-link nav-link-active' : 'nav-link'}>
                <span className="text-lg mr-2">🧪</span> API Test
              </NavLink>
            )}
            <NavLink to="/notebook" className={({isActive})=> isActive ? 'nav-link nav-link-active' : 'nav-link'}>
              <span className="text-lg mr-2">📔</span> Notebook
            </NavLink>
            {user ? (
              <NavLink to="/users" className={({isActive})=> isActive ? 'nav-link nav-link-active' : 'nav-link'}>
                <span className="text-lg mr-2">👥</span> Users
              </NavLink>
            ) : null}
          </nav>
        </div>
        
        {/* User info at bottom */}
        <div className="absolute bottom-0 left-0 right-0 p-6 border-t border-slate-200 bg-white">
          {user ? (
            <div className="flex flex-col gap-3 p-3 bg-slate-50 rounded-xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-r from-brand-500 to-brand-600 flex items-center justify-center text-white font-semibold">
                  {user?.username?.charAt(0).toUpperCase() || 'U'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-navy-700 truncate">{user.full_name || user.username}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="badge text-xs">{user.role}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
          <button 
            className="btn mt-3 w-full bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700" 
            onClick={logout}
          >
            <span className="mr-2">🚪</span> Logout
          </button>
        </div>
      </aside>
      
      {/* Main Content Area */}
      <div className="main-content">
        <header className="topbar">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-brand-500 to-brand-600 bg-clip-text text-transparent font-display">
              {pageTitle || 'LUNA25UET'}
            </h1>
            {isSearchEnabled ? (
              <div className="relative">
                <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400">🔍</span>
                <input 
                  value={q} 
                  onChange={e=>setQ(e.target.value)} 
                  onKeyDown={onSearchKeyDown}
                  placeholder={pathBase === '/datasets' ? 'Search datasets by name or uploader...' : 'Search submissions by uploader or dataset...'} 
                  className="input w-full max-w-4xl !pl-10 bg-slate-50/50 border-slate-200"
                  aria-label="Search"
                />
              </div>
            ) : null}
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-brand-50 to-indigo-50 rounded-xl border border-brand-200">
              <div className="w-8 h-8 rounded-full bg-gradient-to-r from-brand-500 to-brand-600 flex items-center justify-center text-white font-semibold text-sm">
                {user?.username?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="text-sm font-medium text-navy-700">{user?.username}</div>
            </div>
          </div>
        </header>
        <main className="p-8 space-y-6">
          <Routes>
            <Route path="/" element={<Dashboard/>} />
            <Route path="/datasets" element={<Datasets/>} />
            <Route path="/submissions" element={<Submissions/>} />
            <Route path="/submissions/:id" element={<SubmissionDetail/>} />
            <Route path="/leaderboard" element={<Leaderboard/>} />
            <Route path="/apitest" element={
              <RoleRoute roles={["admin"]}>
                <ApiTest/>
              </RoleRoute>
            } />
            <Route path="/notebook" element={<Notebook/>} />
            <Route path="/users" element={<Users />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

function Root() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage/>} />
          <Route path="/register" element={<RegisterPage/>} />
          <Route path="/*" element={<AppShell/>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(<Root/>)
