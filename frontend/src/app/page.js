'use client';
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import { ToastProvider, useToast } from '@/components/Toast';
import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

function DashboardContent() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { addToast } = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [filters, setFilters] = useState({ dateFrom: '', dateTo: '', ticker: '', type: '', pnl: '', strategy: '' });

  const [form, setForm] = useState({
    nama_aset: '', jumlah: '', harga_beli: '', fee_persen: '0.20',
    tanggal_beli: new Date().toISOString().split('T')[0],
    waktu_transaksi: new Date().toTimeString().slice(0, 5),
    jenis_transaksi: 'BELI', strategy: '', kategori: 'Saham',
  });
  const [assetPosition, setAssetPosition] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get('/api/portfolio/dashboard');
      setData(res.data);
    } catch { }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
    else if (user) fetchData();
  }, [user, authLoading, router, fetchData]);

  // Fetch avg buy cost when user selects JUAL + types asset name
  useEffect(() => {
    if (form.jenis_transaksi !== 'JUAL' || !form.nama_aset.trim()) {
      setAssetPosition(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.get(`/api/transactions/position/${form.nama_aset.trim()}`);
        setAssetPosition(res.data);
      } catch {
        setAssetPosition(null);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [form.jenis_transaksi, form.nama_aset]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editItem) {
        await api.put(`/api/transactions/${editItem.id}`, form);
        addToast('Transaksi berhasil diperbarui!');
      } else {
        const res = await api.post('/api/transactions', form);
        addToast(res.data.message);
      }
      setShowForm(false);
      setEditItem(null);
      setForm({ nama_aset: '', jumlah: '', harga_beli: '', fee_persen: '0.20', tanggal_beli: new Date().toISOString().split('T')[0], waktu_transaksi: new Date().toTimeString().slice(0, 5), jenis_transaksi: 'BELI', strategy: '', kategori: 'Saham' });
      fetchData();
    } catch (err) {
      addToast(err.response?.data?.detail || 'Gagal menyimpan transaksi', 'error');
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Hapus transaksi ini?')) return;
    try {
      await api.delete(`/api/transactions/${id}`);
      addToast('Transaksi berhasil dihapus!');
      fetchData();
    } catch (err) {
      addToast(err.response?.data?.detail || 'Gagal menghapus', 'error');
    }
  };

  const handleEdit = (item) => {
    setEditItem(item);
    setForm({
      nama_aset: item.nama_aset, jumlah: item.jumlah, harga_beli: item.harga_beli,
      fee_persen: '0.20', tanggal_beli: item.tanggal_beli, waktu_transaksi: item.waktu_transaksi || '',
      jenis_transaksi: item.jenis_transaksi,
      strategy: item.strategy || '', kategori: item.kategori,
    });
    setShowForm(true);
  };

  const handleTopUp = async (e) => {
    e.preventDefault();
    const amt = parseFloat(e.target.jumlah_tambah.value);
    try {
      const res = await api.post(`/api/portfolio/topup?jumlah_tambah=${amt}`);
      addToast(res.data.message);
      fetchData();
      e.target.reset();
    } catch (err) {
      addToast(err.response?.data?.detail || 'Gagal top up', 'error');
    }
  };

  const fmtRp = (v) => `Rp ${Number(v).toLocaleString('id-ID', { minimumFractionDigits: 2 })}`;

  // Filter logic
  const filteredPortfolio = data?.portofolio?.filter((t) => {
    const f = filters;
    if (f.dateFrom && t.tanggal_beli < f.dateFrom) return false;
    if (f.dateTo && t.tanggal_beli > f.dateTo) return false;
    if (f.ticker && t.nama_aset !== f.ticker) return false;
    if (f.type && t.jenis_transaksi !== f.type) return false;
    if (f.strategy) {
      if (f.strategy === '_untagged' && t.strategy) return false;
      if (f.strategy !== '_untagged' && t.strategy !== f.strategy) return false;
    }
    if (f.pnl === 'profit' && t.profit_loss <= 0) return false;
    if (f.pnl === 'loss' && t.profit_loss >= 0) return false;
    if (f.pnl === 'even' && t.profit_loss !== 0) return false;
    return true;
  }) || [];

  // Chart data based on filters
  const getChartData = () => {
    const jualTrx = (data?.raw_jual_trx || []).filter((t) => {
      const f = filters;
      if (f.dateFrom && t.date < f.dateFrom) return false;
      if (f.dateTo && t.date > f.dateTo) return false;
      if (f.ticker && t.ticker !== f.ticker) return false;
      if (f.strategy) {
        if (f.strategy === '_untagged' && t.strategy) return false;
        if (f.strategy !== '_untagged' && t.strategy !== f.strategy) return false;
      }
      return true;
    });
    const dateMap = {};
    jualTrx.forEach((t) => { dateMap[t.date] = (dateMap[t.date] || 0) + t.pnl; });
    const labels = Object.keys(dateMap).sort();
    let run = 0;
    const values = labels.map((d) => { run += dateMap[d]; return run; });
    return { labels, values, total: run };
  };

  if (authLoading || loading) {
    return (
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <div className="page-header"><h1 className="page-title">Loading...</h1></div>
          <div className="stats-grid">
            {[1, 2, 3, 4].map((i) => <div key={i} className="skeleton" style={{ height: 100 }} />)}
          </div>
        </main>
      </div>
    );
  }

  if (!data) return null;

  const chart = getChartData();
  const pnlClass = data.total_realized_pnl > 0 ? 'profit' : data.total_realized_pnl < 0 ? 'loss' : 'neutral';

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1 className="page-title">Dashboard Trading Journal</h1>
          <p className="page-subtitle">Selamat datang, {data.username}</p>
        </div>

        {/* Stats */}
        <div className="stats-grid">
          <div className="stat-card accent-orange" style={{ animationDelay: '0.1s' }}>
            <div className="stat-label">Sisa Modal</div>
            <div className="stat-value">{fmtRp(data.saldo)}</div>
            <div className="stat-sub">Referensi: {fmtRp(data.referensi)}</div>
          </div>
          <div className="stat-card accent-blue" style={{ animationDelay: '0.2s' }}>
            <div className="stat-label">Modal Disertakan</div>
            <div className="stat-value">{fmtRp(data.modal_disetor)}</div>
          </div>
          <div className={`stat-card ${data.total_realized_pnl >= 0 ? 'accent-green' : 'accent-red'}`} style={{ animationDelay: '0.3s' }}>
            <div className="stat-label">Total Realized P/L</div>
            <div className={`stat-value ${pnlClass}`}>
              {data.total_realized_pnl > 0 ? '+' : ''}{fmtRp(data.total_realized_pnl)}
            </div>
            <div className="stat-sub">({data.pertumbuhan_persen > 0 ? '+' : ''}{data.pertumbuhan_persen}%)</div>
          </div>
          <div className="stat-card accent-purple" style={{ animationDelay: '0.4s' }}>
            <div className="stat-label">Total Transaksi</div>
            <div className="stat-value">{data.portofolio.length}</div>
          </div>
        </div>

        {/* Top Up & Download */}
        <div className="flex gap-4 mb-4" style={{ flexWrap: 'wrap' }}>
          <div className="card" style={{ flex: 1, minWidth: 300 }}>
            <div className="card-title">💰 Top Up Modal</div>
            <form onSubmit={handleTopUp} className="flex gap-3 items-center">
              <input type="number" step="0.01" name="jumlah_tambah" placeholder="Jumlah (Rp)" required className="form-input" style={{ maxWidth: 220 }} />
              <button type="submit" className="btn-primary">Request Top Up</button>
            </form>
            <div className="stat-sub mt-3">Syarat: Saldo harus ≤ {fmtRp((data.referensi * 0.75))} (Drawdown &gt; 25%)</div>
          </div>
          <div className="card" style={{ flex: 1, minWidth: 300 }}>
            <div className="card-title">📥 Ekspor Report</div>
            <div className="flex gap-3">
              <a href={`http://localhost:8000/api/portfolio/report/mingguan`} className="btn-primary" style={{ textDecoration: 'none', fontSize: 13 }}>⬇️ Mingguan</a>
              <a href={`http://localhost:8000/api/portfolio/report/bulanan`} className="btn-primary" style={{ textDecoration: 'none', fontSize: 13 }}>⬇️ Bulanan</a>
            </div>
          </div>
        </div>

        {/* Chart */}
        <div className="card card-delay-2">
          <div className="card-title">📈 Grafik Akumulasi Profit / Rugi Realized</div>
          {chart.labels.length > 0 ? (
            <Plot
              data={[{
                x: chart.labels, y: chart.values, type: 'scatter', mode: 'lines+markers',
                name: 'Akumulasi P/L', line: { color: chart.total >= 0 ? '#10B981' : '#EF4444', width: 3, shape: 'spline' },
                marker: { color: '#111827', line: { color: chart.total >= 0 ? '#10B981' : '#EF4444', width: 2 }, size: 8 },
                fill: 'tozeroy', fillcolor: chart.total >= 0 ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
              }]}
              layout={{
                font: { family: "'Inter', sans-serif", color: '#8B9AB5' },
                paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                margin: { t: 10, r: 10, b: 40, l: 70 },
                xaxis: { gridcolor: '#1A2332', tickcolor: '#5A6B83', linecolor: '#1A2332' },
                yaxis: { gridcolor: '#1A2332', tickcolor: '#5A6B83', linecolor: '#1A2332', tickprefix: 'Rp ' },
                hovermode: 'closest', showlegend: false, height: 320,
              }}
              config={{ responsive: true, displayModeBar: false }}
              style={{ width: '100%' }}
            />
          ) : (
            <p className="text-muted text-sm" style={{ padding: 40, textAlign: 'center' }}>Belum ada data transaksi JUAL.</p>
          )}
        </div>

        {/* Filter Bar */}
        <div className="filter-bar card-delay-3">
          <div className="filter-group">
            <label>Dari Tanggal</label>
            <input type="date" value={filters.dateFrom} onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })} />
          </div>
          <div className="filter-group">
            <label>Sampai Tanggal</label>
            <input type="date" value={filters.dateTo} onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })} />
          </div>
          <div className="filter-group">
            <label>Aset / Ticker</label>
            <select value={filters.ticker} onChange={(e) => setFilters({ ...filters, ticker: e.target.value })}>
              <option value="">Semua Aset</option>
              {data.all_tickers.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="filter-group">
            <label>Tipe</label>
            <select value={filters.type} onChange={(e) => setFilters({ ...filters, type: e.target.value })}>
              <option value="">Semua</option>
              <option value="BELI">BELI</option>
              <option value="JUAL">JUAL</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Status P/L</label>
            <select value={filters.pnl} onChange={(e) => setFilters({ ...filters, pnl: e.target.value })}>
              <option value="">Semua</option>
              <option value="profit">Profit</option>
              <option value="loss">Rugi</option>
              <option value="even">Break Even</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Strategi</label>
            <select value={filters.strategy} onChange={(e) => setFilters({ ...filters, strategy: e.target.value })}>
              <option value="">Semua</option>
              <option value="Swing">Swing</option>
              <option value="Scalping">Scalping</option>
              <option value="Investasi">Investasi</option>
              <option value="_untagged">Belum Ditandai</option>
            </select>
          </div>
          <button className="btn-danger" onClick={() => setFilters({ dateFrom: '', dateTo: '', ticker: '', type: '', pnl: '', strategy: '' })}>✕ Reset</button>
          {Object.values(filters).some(Boolean) && (
            <span className="text-sm text-muted" style={{ marginLeft: 'auto' }}>
              Menampilkan <strong className="text-profit">{filteredPortfolio.length}</strong> dari {data.portofolio.length}
            </span>
          )}
        </div>

        {/* Transaction Section */}
        <div className="card card-delay-3">
          <div className="flex justify-between items-center mb-4">
            <div className="card-title" style={{ marginBottom: 0 }}>📋 Riwayat Transaksi</div>
            <button className="btn-primary" onClick={() => { setEditItem(null); setForm({ nama_aset: '', jumlah: '', harga_beli: '', fee_persen: '0.20', tanggal_beli: data.today, waktu_transaksi: new Date().toTimeString().slice(0, 5), jenis_transaksi: 'BELI', strategy: '', kategori: 'Saham' }); setShowForm(true); }}>
              ＋ Tambah Transaksi
            </button>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Tipe</th><th>Kategori</th><th>Aset</th><th>Jumlah</th>
                  <th>Harga/Unit</th><th>Fee</th><th>P/L</th><th>Strategi</th>
                  <th>Tanggal</th><th>Jam</th><th>Durasi</th><th>Aksi</th>
                </tr>
              </thead>
              <tbody>
                {filteredPortfolio.map((t) => (
                  <tr key={t.id}>
                    <td><span className={`badge ${t.jenis_transaksi === 'BELI' ? 'badge-beli' : 'badge-jual'}`}>{t.jenis_transaksi}</span></td>
                    <td><span className="badge badge-strategy">{t.kategori}</span></td>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{t.nama_aset}</td>
                    <td>{t.jumlah}</td>
                    <td>
                      <div>{fmtRp(t.harga_beli)}</div>
                      <div style={{ fontSize: 11, color: '#5A6B83', marginTop: 2 }}>
                        Total: {fmtRp(t.jumlah * t.harga_beli)}
                      </div>
                    </td>
                    <td className="text-loss">{fmtRp(t.fee)}</td>
                    <td style={{ fontWeight: 600 }}>
                      {t.jenis_transaksi === 'JUAL' ? (
                        <span className={t.profit_loss > 0 ? 'text-profit' : t.profit_loss < 0 ? 'text-loss' : 'text-muted'}>
                          {t.profit_loss > 0 ? '+' : ''}{fmtRp(t.profit_loss)}
                        </span>
                      ) : <span className="text-muted">—</span>}
                    </td>
                    <td>
                      {t.strategy ? (
                        <span className={`badge badge-strategy ${(t.strategy || '').toLowerCase()}`}>{t.strategy}</span>
                      ) : <span className="text-muted">—</span>}
                    </td>
                    <td>{t.tanggal_beli}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{t.waktu_transaksi || <span className="text-muted">—</span>}</td>
                    <td>
                      {t.holding_duration ? (
                        <span className="badge" style={{ background: 'rgba(139,92,246,0.15)', color: '#A78BFA', border: '1px solid rgba(139,92,246,0.3)', fontSize: 11, padding: '3px 8px' }}>
                          ⏱ {t.holding_duration}
                        </span>
                      ) : <span className="text-muted">—</span>}
                    </td>
                    <td>
                      <div className="flex gap-2">
                        <button className="btn-icon" onClick={() => handleEdit(t)} title="Edit">✏️</button>
                        <button className="btn-icon" onClick={() => handleDelete(t.id)} title="Hapus" style={{ borderColor: 'rgba(239,68,68,0.3)', color: '#EF4444' }}>🗑️</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredPortfolio.length === 0 && (
                  <tr><td colSpan={12} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>Belum ada transaksi.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Transaction Form Modal */}
        {showForm && (
          <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && setShowForm(false)}>
            <div className="modal-content">
              <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>
                {editItem ? '✏️ Edit Transaksi' : '＋ Tambah Transaksi'}
              </h3>
              <form onSubmit={handleSubmit}>
                {/* Position info panel when JUAL is selected */}
                {form.jenis_transaksi === 'JUAL' && assetPosition && assetPosition.posisi_bersih > 0 && (
                  <div style={{
                    background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.25)',
                    borderRadius: 10, padding: '12px 16px', marginBottom: 16, fontSize: 13
                  }}>
                    <div style={{ fontWeight: 600, color: '#60A5FA', marginBottom: 6 }}>
                      📊 Info Posisi {assetPosition.nama_aset}
                    </div>
                    <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', color: '#8B9AB5' }}>
                      <span>Posisi: <strong style={{ color: '#E2E8F0' }}>{assetPosition.posisi_bersih} lot</strong></span>
                      <span>Avg Cost/Unit: <strong style={{ color: '#FBBF24' }}>{fmtRp(assetPosition.avg_cost_per_unit)}</strong></span>
                    </div>
                    {form.harga_beli && (
                      <div style={{ marginTop: 6, color: '#8B9AB5' }}>
                        {(() => {
                          const sellPrice = parseFloat(form.harga_beli) || 0;
                          const diff = sellPrice - assetPosition.avg_cost_per_unit;
                          const pct = assetPosition.avg_cost_per_unit > 0 ? (diff / assetPosition.avg_cost_per_unit * 100) : 0;
                          return (
                            <span>
                              Estimasi P/L per unit:{' '}
                              <strong style={{ color: diff >= 0 ? '#10B981' : '#EF4444' }}>
                                {diff >= 0 ? '+' : ''}{fmtRp(diff)} ({pct >= 0 ? '+' : ''}{pct.toFixed(2)}%)
                              </strong>
                            </span>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                )}

                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">Jenis Transaksi</label>
                    <select className="form-select" value={form.jenis_transaksi} onChange={(e) => setForm({ ...form, jenis_transaksi: e.target.value })}>
                      <option value="BELI">BELI</option>
                      <option value="JUAL">JUAL</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Nama Aset</label>
                    <input className="form-input" placeholder="BBCA" value={form.nama_aset} onChange={(e) => setForm({ ...form, nama_aset: e.target.value })} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Jumlah (Lot/Unit)</label>
                    <input className="form-input" type="number" step="0.01" placeholder="1.00" value={form.jumlah} onChange={(e) => setForm({ ...form, jumlah: e.target.value })} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">
                      {form.jenis_transaksi === 'JUAL' ? 'Harga Jual Per Unit (Rp)' : 'Harga Beli Per Unit (Rp)'}
                    </label>
                    <input className="form-input" type="number" step="0.01" placeholder="652500" value={form.harga_beli} onChange={(e) => setForm({ ...form, harga_beli: e.target.value })} required />
                    {/* Total value preview */}
                    {form.jumlah && form.harga_beli && (
                      <div style={{ fontSize: 12, marginTop: 4, color: '#8B9AB5' }}>
                        Total Nilai: <strong style={{ color: '#E2E8F0' }}>{fmtRp(parseFloat(form.jumlah) * parseFloat(form.harga_beli))}</strong>
                        {' '}| Fee ({form.fee_persen}%): <strong style={{ color: '#F87171' }}>{fmtRp(parseFloat(form.jumlah) * parseFloat(form.harga_beli) * (parseFloat(form.fee_persen) / 100))}</strong>
                      </div>
                    )}
                  </div>
                  <div className="form-group">
                    <label className="form-label">Fee (%)</label>
                    <input className="form-input" type="number" step="0.001" value={form.fee_persen} onChange={(e) => setForm({ ...form, fee_persen: e.target.value })} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Tanggal</label>
                    <input className="form-input" type="date" value={form.tanggal_beli} onChange={(e) => setForm({ ...form, tanggal_beli: e.target.value })} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Jam Transaksi</label>
                    <input className="form-input" type="time" value={form.waktu_transaksi} onChange={(e) => setForm({ ...form, waktu_transaksi: e.target.value })} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Kategori</label>
                    <select className="form-select" value={form.kategori} onChange={(e) => setForm({ ...form, kategori: e.target.value })}>
                      <option value="Saham">Saham</option>
                      <option value="Crypto">Crypto</option>
                      <option value="Futures">Futures</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Strategi</label>
                    <select className="form-select" value={form.strategy} onChange={(e) => setForm({ ...form, strategy: e.target.value })}>
                      <option value="">— Tidak Ditandai —</option>
                      <option value="Swing">Swing</option>
                      <option value="Scalping">Scalping</option>
                      <option value="Investasi">Investasi</option>
                    </select>
                  </div>
                </div>
                <div className="flex gap-3 mt-4">
                  <button type="submit" className="btn-primary">💾 Simpan</button>
                  <button type="button" className="btn-secondary" onClick={() => { setShowForm(false); setEditItem(null); }}>Batal</button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ToastProvider>
      <DashboardContent />
    </ToastProvider>
  );
}
