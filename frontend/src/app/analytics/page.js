'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export default function AnalyticsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
    else if (user) {
      api.get('/api/analytics').then((res) => { setData(res.data); setLoading(false); }).catch(() => setLoading(false));
    }
  }, [user, authLoading, router]);

  const fmtRp = (v) => `Rp ${Number(v).toLocaleString('id-ID', { minimumFractionDigits: 2 })}`;

  if (authLoading || loading || !data) {
    return (<div className="app-layout"><Sidebar /><main className="main-content"><div className="page-header"><h1 className="page-title">Loading Analytics...</h1></div></main></div>);
  }

  const kpi = data.kpi;

  const getHeatColor = (pct) => {
    if (!pct || pct === 0) return { bg: 'var(--bg-elevated)', color: 'var(--text-muted)' };
    const intensity = Math.min(Math.abs(pct) / (data.max_abs_pct || 1), 1);
    if (pct > 0) return { bg: `rgba(16,185,129,${0.1 + intensity * 0.5})`, color: '#34D399' };
    return { bg: `rgba(239,68,68,${0.1 + intensity * 0.5})`, color: '#F87171' };
  };

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 className="page-title">Analytics Dashboard</h1>
            <p className="page-subtitle">Performance insights & portfolio composition</p>
          </div>
          <button 
            className="btn btn-primary" 
            onClick={() => router.push('/analytics/screening')}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            Stock Screening
          </button>
        </div>

        {/* KPI Cards */}
        <div className="stats-grid">
          <div className="stat-card accent-green" style={{ animationDelay: '0.1s' }}>
            <div className="stat-label">Win Rate</div>
            <div className="stat-value profit">{kpi.win_rate}%</div>
            <div className="stat-sub">{kpi.total_win}W / {kpi.total_loss}L / {kpi.total_even}E</div>
          </div>
          <div className="stat-card accent-blue" style={{ animationDelay: '0.15s' }}>
            <div className="stat-label">Risk:Reward</div>
            <div className="stat-value">{kpi.rr_ratio}x</div>
            <div className="stat-sub">Avg Win: {fmtRp(kpi.avg_profit)}</div>
          </div>
          <div className={`stat-card ${kpi.total_pnl >= 0 ? 'accent-green' : 'accent-red'}`} style={{ animationDelay: '0.2s' }}>
            <div className="stat-label">Total P/L</div>
            <div className={`stat-value ${kpi.total_pnl >= 0 ? 'profit' : 'loss'}`}>{fmtRp(kpi.total_pnl)}</div>
          </div>
          <div className="stat-card accent-orange" style={{ animationDelay: '0.25s' }}>
            <div className="stat-label">Total Trades</div>
            <div className="stat-value">{kpi.total_jual}</div>
            <div className="stat-sub">Best: {fmtRp(kpi.best_trade)}</div>
          </div>
        </div>

        {/* Donut Chart + Positions */}
        <div className="flex gap-4" style={{ flexWrap: 'wrap' }}>
          <div className="card" style={{ flex: 1, minWidth: 350 }}>
            <div className="card-title">🍩 Portfolio Composition</div>
            {data.donut_labels.length > 0 ? (
              <Plot
                data={[{ values: data.donut_values, labels: data.donut_labels, type: 'pie', hole: 0.55,
                  marker: { colors: data.donut_colors }, textinfo: 'label+percent', textfont: { size: 11, color: '#F0F4F8' },
                  hoverinfo: 'label+value+percent' }]}
                layout={{ paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { color: '#8B9AB5' },
                  margin: { t: 20, b: 20, l: 20, r: 20 }, showlegend: false, height: 300,
                  annotations: [{ text: `${fmtRp(data.grand_total)}`, showarrow: false, font: { size: 13, color: '#F0F4F8' } }] }}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: '100%' }}
              />
            ) : <p className="text-muted" style={{ textAlign: 'center', padding: 40 }}>Belum ada posisi aktif.</p>}
          </div>

          <div className="card" style={{ flex: 1, minWidth: 350 }}>
            <div className="card-title">📊 Posisi Aktif</div>
            <table className="data-table">
              <thead><tr><th>Aset</th><th>Units</th><th>Avg Cost</th><th>Total Value</th></tr></thead>
              <tbody>
                {Object.entries(data.positions).map(([name, pos]) => (
                  <tr key={name}>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{name}</td>
                    <td>{pos.units}</td>
                    <td>{fmtRp(pos.avg_cost)}</td>
                    <td style={{ fontWeight: 600 }}>{fmtRp(pos.total_value)}</td>
                  </tr>
                ))}
                {Object.keys(data.positions).length === 0 && (
                  <tr><td colSpan={4} className="text-muted" style={{ textAlign: 'center', padding: 20 }}>Tidak ada posisi aktif</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Monthly Heatmap */}
        <div className="card card-delay-2">
          <div className="card-title">🗓️ Monthly Performance Heatmap</div>
          <div style={{ overflowX: 'auto' }}>
            <div className="heatmap-grid">
              <div className="heatmap-row">
                <div className="heatmap-label"></div>
                {data.month_names.map((m) => (
                  <div key={m} className="heatmap-cell" style={{ background: 'transparent', fontSize: 11, color: 'var(--text-muted)', fontWeight: 700 }}>{m}</div>
                ))}
              </div>
              {data.heatmap_years.map((year) => (
                <div key={year} className="heatmap-row">
                  <div className="heatmap-label">{year}</div>
                  {[1,2,3,4,5,6,7,8,9,10,11,12].map((m) => {
                    const cell = data.heatmap_data?.[year]?.[m];
                    const { bg, color } = getHeatColor(cell?.pct || 0);
                    return (
                      <div key={m} className="heatmap-cell" style={{ background: bg, color }}
                        title={cell ? `${fmtRp(cell.pnl)} (${cell.pct}%)` : 'No data'}>
                        {cell ? `${cell.pct > 0 ? '+' : ''}${cell.pct}%` : '—'}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Top 5 Best & Worst */}
        <div className="flex gap-4" style={{ flexWrap: 'wrap' }}>
          <div className="card card-delay-3" style={{ flex: 1, minWidth: 350 }}>
            <div className="card-title">🏆 Top 5 Best Assets</div>
            <table className="data-table">
              <thead><tr><th>Aset</th><th>Trades</th><th>Win Rate</th><th>Total P/L</th></tr></thead>
              <tbody>
                {data.top5_best.map((a) => (
                  <tr key={a.name}>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{a.name}</td>
                    <td>{a.trades}</td>
                    <td>{a.win_rate}%</td>
                    <td className="text-profit font-bold">{fmtRp(a.total_pnl)}</td>
                  </tr>
                ))}
                {data.top5_best.length === 0 && <tr><td colSpan={4} className="text-muted" style={{ textAlign: 'center' }}>—</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card card-delay-3" style={{ flex: 1, minWidth: 350 }}>
            <div className="card-title">📉 Top 5 Worst Assets</div>
            <table className="data-table">
              <thead><tr><th>Aset</th><th>Trades</th><th>Win Rate</th><th>Total P/L</th></tr></thead>
              <tbody>
                {data.top5_worst.map((a) => (
                  <tr key={a.name}>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{a.name}</td>
                    <td>{a.trades}</td>
                    <td>{a.win_rate}%</td>
                    <td className="text-loss font-bold">{fmtRp(a.total_pnl)}</td>
                  </tr>
                ))}
                {data.top5_worst.length === 0 && <tr><td colSpan={4} className="text-muted" style={{ textAlign: 'center' }}>—</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
