import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useAuth } from '../state/auth.jsx'
import { 
  LineChart, Line, BarChart, Bar, 
  XAxis, YAxis, Tooltip, ResponsiveContainer, 
  CartesianGrid, Legend, PieChart, Pie, Cell 
} from 'recharts'

export default function Dashboard(){
  const { API, authHeader, token } = useAuth()
  const [datasets, setDatasets] = useState({items:[]})
  const [subs, setSubs] = useState({items:[]})
  const [loading, setLoading] = useState(true)

  useEffect(()=>{
    if(!token) return
    setLoading(true)
    Promise.all([
      axios.get(`${API}/datasets/`, { headers: authHeader }).then(r=>setDatasets(r.data)),
      axios.get(`${API}/submissions/`, { headers: authHeader }).then(r=>setSubs(r.data))
    ])
      .catch(() => {
        setDatasets({ items: [] })
        setSubs({ items: [] })
      })
      .finally(() => setLoading(false))
  }, [API, token])

  const official = datasets.items?.find(d=>d.is_official)
  
  // Prepare chart data from submissions
  const submissionsOverTime = React.useMemo(() => {
    if (!subs.items || subs.items.length === 0) return []
    
    // Group by date
    const grouped = {}
    subs.items.forEach(sub => {
      const date = sub.uploaded_at || sub.created_at
      if (!date) return
      const day = new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      grouped[day] = (grouped[day] || 0) + 1
    })
    
    return Object.entries(grouped).map(([date, count]) => ({ date, count })).slice(-7)
  }, [subs.items])

  // Calculate performance distribution
  const performanceData = React.useMemo(() => {
    if (!subs.items || subs.items.length === 0) return []
    
    const ranges = { 'Excellent (>0.9)': 0, 'Good (0.8-0.9)': 0, 'Fair (0.7-0.8)': 0, 'Poor (<0.7)': 0 }
    
    subs.items.forEach(sub => {
      const score = sub.auc || sub.accuracy || sub.score || 0
      if (score > 0.9) ranges['Excellent (>0.9)']++
      else if (score > 0.8) ranges['Good (0.8-0.9)']++
      else if (score > 0.7) ranges['Fair (0.7-0.8)']++
      else ranges['Poor (<0.7)']++
    })
    
    return Object.entries(ranges).map(([name, value]) => ({ name, value }))
  }, [subs.items])

  const COLORS = ['#4318FF', '#6B46C1', '#9F7AEA', '#C4B5FD']

  // Calculate average metrics
  const avgMetrics = React.useMemo(() => {
    if (!subs.items || subs.items.length === 0) return { auc: 0, f1: 0, accuracy: 0 }
    
    let aucSum = 0, f1Sum = 0, accSum = 0, count = 0
    subs.items.forEach(sub => {
      if (sub.auc) { aucSum += sub.auc; count++ }
      if (sub.f1) f1Sum += sub.f1
      if (sub.accuracy) accSum += sub.accuracy
    })
    
    return {
      auc: count > 0 ? (aucSum / count).toFixed(3) : 0,
      f1: count > 0 ? (f1Sum / count).toFixed(3) : 0,
      accuracy: count > 0 ? (accSum / count).toFixed(3) : 0
    }
  }, [subs.items])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner"></div>
        <span className="ml-3 text-navy-600">Loading dashboard...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-brand-500 to-brand-600 bg-clip-text text-transparent">
            Dashboard
          </h1>
          <p className="text-navy-600 mt-2 text-base">Welcome to LUNA25 Lung Cancer Prediction System</p>
        </div>
        <div className="text-sm text-slate-500 bg-white px-4 py-2 rounded-xl border border-slate-200">
          {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="stat-card from-brand-500 to-brand-600">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm opacity-90 mb-1 font-medium">Total Datasets</div>
              <div className="text-4xl font-bold">{datasets.total || 0}</div>
            </div>
            <div className="text-5xl opacity-30">📚</div>
          </div>
        </div>
        
        <div className="stat-card from-green-500 to-green-600">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm opacity-90 mb-1 font-medium">Total Submissions</div>
              <div className="text-4xl font-bold">{subs.total || 0}</div>
            </div>
            <div className="text-5xl opacity-30">📤</div>
          </div>
        </div>

        <div className="stat-card from-purple-500 to-purple-600">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm opacity-90 mb-1 font-medium">Avg AUC Score</div>
              <div className="text-4xl font-bold">{avgMetrics.auc}</div>
            </div>
            <div className="text-5xl opacity-30">📊</div>
          </div>
        </div>

        <div className="stat-card from-orange-500 to-orange-600">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm opacity-90 mb-1 font-medium">Official Dataset</div>
              <div className="text-xl font-bold truncate">{official?.name || 'Not Set'}</div>
            </div>
            <div className="text-5xl opacity-30">⭐</div>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Submissions Over Time */}
        <div className="card">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-navy-700">
            <span className="text-2xl">📈</span>
            Submissions Over Time
          </h2>
          <div style={{width:'100%', height:280}}>
            {submissionsOverTime.length > 0 ? (
              <ResponsiveContainer>
                <BarChart data={submissionsOverTime}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="date" tick={{ fill: '#64748B', fontSize: 12 }} />
                  <YAxis tick={{ fill: '#64748B', fontSize: 12 }} />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#FFF', 
                      border: '1px solid #E2E8F0',
                      borderRadius: '12px',
                      boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
                    }}
                  />
                  <Bar dataKey="count" fill="#4318FF" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-400">
                No submission data available
              </div>
            )}
          </div>
        </div>

        {/* Performance Distribution */}
        <div className="card">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-navy-700">
            <span className="text-2xl">🎯</span>
            Performance Distribution
          </h2>
          <div style={{width:'100%', height:280}}>
            {performanceData.some(d => d.value > 0) ? (
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={performanceData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {performanceData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#FFF', 
                      border: '1px solid #E2E8F0',
                      borderRadius: '12px'
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-400">
                No performance data available
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-navy-700">
            <span className="text-2xl">📊</span>
            System Overview
          </h2>
          <div className="space-y-3">
            <div className="flex justify-between items-center p-4 bg-slate-50 rounded-xl hover:bg-slate-100 transition-colors">
              <span className="text-navy-600 font-medium">Active Datasets</span>
              <span className="font-semibold text-brand-600 text-lg">{datasets.items?.filter(d => d.is_official).length || 0}</span>
            </div>
            <div className="flex justify-between items-center p-4 bg-slate-50 rounded-xl hover:bg-slate-100 transition-colors">
              <span className="text-navy-600 font-medium">Avg F1 Score</span>
              <span className="font-semibold text-green-600 text-lg">{avgMetrics.f1}</span>
            </div>
            <div className="flex justify-between items-center p-4 bg-slate-50 rounded-xl hover:bg-slate-100 transition-colors">
              <span className="text-navy-600 font-medium">Avg Accuracy</span>
              <span className="font-semibold text-purple-600 text-lg">{avgMetrics.accuracy}</span>
            </div>
          </div>
        </div>

        <div className="card">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-navy-700">
            <span className="text-2xl">🎯</span>
            Quick Actions
          </h2>
          <div className="space-y-3">
            <a href="/datasets" className="block p-4 bg-gradient-to-r from-brand-50 to-indigo-50 rounded-xl border-2 border-brand-200 hover:border-brand-400 transition-all hover:shadow-md">
              <div className="font-semibold text-brand-700">📚 Manage Datasets</div>
              <div className="text-sm text-navy-600 mt-1">Upload and analyze datasets</div>
            </a>
            <a href="/leaderboard" className="block p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl border-2 border-purple-200 hover:border-purple-400 transition-all hover:shadow-md">
              <div className="font-semibold text-purple-700">🏆 View Leaderboard</div>
              <div className="text-sm text-navy-600 mt-1">Check team rankings and scores</div>
            </a>
            <a href="/submissions" className="block p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border-2 border-green-200 hover:border-green-400 transition-all hover:shadow-md">
              <div className="font-semibold text-green-700">📤 View Submissions</div>
              <div className="text-sm text-navy-600 mt-1">Review all team submissions</div>
            </a>
          </div>
        </div>
      </div>

      {/* About Section */}
      <div className="card bg-gradient-to-br from-indigo-50 to-blue-50 border-2 border-indigo-200">
        <h2 className="text-xl font-semibold mb-3 flex items-center gap-2 text-indigo-900">
          <span className="text-2xl">ℹ️</span>
          About LUNA25UET
        </h2>
        <p className="text-navy-700 leading-relaxed text-base">
          LUNA25UET is a lung cancer prediction system that evaluates malignant lung tumor risk from chest CT images. 
          The system ranks team models based on their performance on test datasets, with scoring from 6.5 to 10 (A+) 
          based on ranking positions. Teams submit their model APIs for evaluation on the official test dataset.
        </p>
      </div>
    </div>
  )
}
