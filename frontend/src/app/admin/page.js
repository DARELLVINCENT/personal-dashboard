'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';
import Sidebar from '@/components/Sidebar';

export default function AdminPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filterUser, setFilterUser] = useState('');
  const [filterAction, setFilterAction] = useState('');

  const fetchAdmin = (p = 1, fu = '', fa = '') => {
    const params = new URLSearchParams({ page: p, filter_user: fu, filter_action: fa });
    api.get(`/api/admin?${params}`).then((res) => { setData(res.data); setLoading(false); }).catch((err) => {
      if (err.response?.status === 403) router.push('/');
      setLoading(false);
    });
  };

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
    else if (user) fetchAdmin();
  }, [user, authLoading, router]);

  if (authLoading || loading || !data) {
    return (<div className="app-layout"><Sidebar /><main className="main-content"><div className="page-header"><h1 className="page-title">Loading Admin...</h1></div></main></div>);
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1 className="page-title">🛡️ Admin Dashboard</h1>
          <p className="page-subtitle">User management & activity monitoring</p>
        </div>

        {/* Stats */}
        <div className="stats-grid">
          <div className="stat-card accent-blue" style={{ animationDelay: '0.1s' }}>
            <div className="stat-label">Total Users</div>
            <div className="stat-value">{data.total_users}</div>
          </div>
          <div className="stat-card accent-green" style={{ animationDelay: '0.15s' }}>
            <div className="stat-label">Activities Today</div>
            <div className="stat-value">{data.activities_today}</div>
          </div>
          <div className="stat-card accent-purple" style={{ animationDelay: '0.2s' }}>
            <div className="stat-label">Database Size</div>
            <div className="stat-value">{data.total_db_size}</div>
          </div>
        </div>

        {/* User Summary */}
        <div className="card">
          <div className="card-title">👥 User Summary</div>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead><tr><th>ID</th><th>Username</th><th>Created</th><th>Logins</th><th>Total Activity</th><th>Last Active</th></tr></thead>
              <tbody>
                {data.user_summary.map((u) => (
                  <tr key={u.id}>
                    <td>{u.id}</td>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{u.username}</td>
                    <td>{u.created_at?.split(' ')[0] || '—'}</td>
                    <td>{u.login_count}</td>
                    <td>{u.total_activity}</td>
                    <td>{u.last_activity?.split('.')[0] || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Storage */}
        <div className="card card-delay-2">
          <div className="card-title">💾 Data Storage per User</div>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead><tr><th>User</th><th>Portofolio</th><th>Activities</th><th>Total Rows</th><th>Est. Size</th></tr></thead>
              <tbody>
                {data.user_storage.map((s) => (
                  <tr key={s.user_id}>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{s.username}</td>
                    <td>{s.portofolio_rows}</td>
                    <td>{s.activity_rows}</td>
                    <td>{s.total_rows}</td>
                    <td>{s.estimated_size}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Activity Logs */}
        <div className="card card-delay-3">
          <div className="card-title">📜 Activity Log</div>
          <div className="flex gap-3 mb-3" style={{ flexWrap: 'wrap' }}>
            <select className="form-select" style={{ maxWidth: 180 }} value={filterUser} onChange={(e) => { setFilterUser(e.target.value); fetchAdmin(1, e.target.value, filterAction); }}>
              <option value="">All Users</option>
              {data.log_users.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
            <select className="form-select" style={{ maxWidth: 200 }} value={filterAction} onChange={(e) => { setFilterAction(e.target.value); fetchAdmin(1, filterUser, e.target.value); }}>
              <option value="">All Actions</option>
              {data.log_actions.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead><tr><th>ID</th><th>User</th><th>Action</th><th>Detail</th><th>IP</th><th>Time</th></tr></thead>
              <tbody>
                {data.activity_logs.map((l) => (
                  <tr key={l.id}>
                    <td>{l.id}</td>
                    <td style={{ fontWeight: 600 }}>{l.username}</td>
                    <td><span className="badge badge-strategy">{l.action}</span></td>
                    <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.detail || '—'}</td>
                    <td>{l.ip_address}</td>
                    <td>{l.created_at?.split('.')[0] || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Pagination */}
          <div className="flex justify-between items-center mt-3">
            <span className="text-sm text-muted">{data.total_logs} total logs</span>
            <div className="flex gap-2">
              <button className="btn-secondary" disabled={data.page <= 1} onClick={() => { setPage(data.page - 1); fetchAdmin(data.page - 1, filterUser, filterAction); }}>← Prev</button>
              <span className="text-sm" style={{ padding: '8px 12px' }}>Page {data.page} / {data.total_pages}</span>
              <button className="btn-secondary" disabled={data.page >= data.total_pages} onClick={() => { setPage(data.page + 1); fetchAdmin(data.page + 1, filterUser, filterAction); }}>Next →</button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
