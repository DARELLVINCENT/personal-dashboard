'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const STRAT_COLORS = { Swing: '#3B82F6', Scalping: '#F59E0B', Investasi: '#10B981', Untagged: '#6B7280' };

export default function StrategyPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
    else if (user) {
      api.get('/api/strategy').then((res) => { setData(res.data); setLoading(false); }).catch(() => setLoading(false));
    }
  }, [user, authLoading, router]);

  const fmtRp = (v) => `Rp ${Number(v).toLocaleString('id-ID', { minimumFractionDigits: 2 })}`;

  if (authLoading || loading || !data) {
    return (<div className="app-layout"><Sidebar /><main className="main-content"><div className="page-header"><h1 className="page-title">Loading...</h1></div></main></div>);
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1 className="page-title">Strategy Analytics</h1>
          <p className="page-subtitle">Performa per strategi trading</p>
        </div>

        {/* Strategy KPI Cards */}
        {data.strategy_data.map((s, i) => (
          <div className="card" key={s.name} style={{ animationDelay: `${0.1 + i * 0.1}s`, borderLeft: `3px solid ${STRAT_COLORS[s.name] || '#8B5CF6'}` }}>
            <div className="flex justify-between items-center mb-3">
              <div className="card-title" style={{ marginBottom: 0 }}>
                <span className={`badge badge-strategy ${s.name.toLowerCase()}`}>{s.name}</span>
              </div>
              <span className={`font-bold ${s.total_pnl >= 0 ? 'text-profit' : 'text-loss'}`} style={{ fontSize: 20 }}>
                {s.total_pnl > 0 ? '+' : ''}{fmtRp(s.total_pnl)}
              </span>
            </div>
            <div className="stats-grid" style={{ marginBottom: 0 }}>
              <div style={{ fontSize: 13 }}><span className="text-muted">Trades:</span> <strong>{s.trades}</strong></div>
              <div style={{ fontSize: 13 }}><span className="text-muted">Win Rate:</span> <strong className="text-profit">{s.win_rate}%</strong></div>
              <div style={{ fontSize: 13 }}><span className="text-muted">R:R:</span> <strong>{s.rr_ratio}x</strong></div>
              <div style={{ fontSize: 13 }}><span className="text-muted">W/L:</span> <strong>{s.wins}/{s.losses}</strong></div>
              <div style={{ fontSize: 13 }}><span className="text-muted">Best:</span> <strong className="text-profit">{fmtRp(s.best)}</strong></div>
              <div style={{ fontSize: 13 }}><span className="text-muted">Worst:</span> <strong className="text-loss">{fmtRp(s.worst)}</strong></div>
            </div>
          </div>
        ))}
        {data.strategy_data.length === 0 && (
          <div className="card"><p className="text-muted" style={{ textAlign: 'center', padding: 40 }}>Belum ada data strategi.</p></div>
        )}

        {/* Bar Chart */}
        {data.chart_labels.length > 0 && (
          <div className="card card-delay-2">
            <div className="card-title">📊 P/L per Strategi</div>
            <Plot
              data={[{ x: data.chart_labels, y: data.chart_pnl, type: 'bar',
                marker: { color: data.chart_colors, borderRadius: 8 }, text: data.chart_pnl.map((v) => fmtRp(v)),
                textposition: 'outside', textfont: { color: '#8B9AB5', size: 11 } }]}
              layout={{ paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { family: "'Inter'", color: '#8B9AB5' },
                margin: { t: 30, r: 20, b: 40, l: 70 }, xaxis: { gridcolor: '#1A2332' }, yaxis: { gridcolor: '#1A2332', tickprefix: 'Rp ' }, height: 300, showlegend: false }}
              config={{ displayModeBar: false, responsive: true }} style={{ width: '100%' }}
            />
          </div>
        )}

        {/* Timeline */}
        {Object.keys(data.timeline).length > 0 && (
          <div className="card card-delay-3">
            <div className="card-title">📈 Cumulative P/L Timeline</div>
            <Plot
              data={Object.entries(data.timeline).map(([strat, points]) => ({
                x: points.map((p) => p.date), y: points.map((p) => p.pnl), type: 'scatter', mode: 'lines+markers',
                name: strat, line: { color: STRAT_COLORS[strat] || '#8B5CF6', width: 2.5 },
                marker: { size: 6 },
              }))}
              layout={{ paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { family: "'Inter'", color: '#8B9AB5' },
                margin: { t: 10, r: 20, b: 40, l: 70 }, xaxis: { gridcolor: '#1A2332' }, yaxis: { gridcolor: '#1A2332', tickprefix: 'Rp ' },
                height: 300, legend: { orientation: 'h', y: 1.1, font: { color: '#D1D5DB' } }, hovermode: 'closest' }}
              config={{ displayModeBar: false, responsive: true }} style={{ width: '100%' }}
            />
          </div>
        )}
      </main>
    </div>
  );
}
