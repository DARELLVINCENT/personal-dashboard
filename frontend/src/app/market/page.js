// perlu di taruh di github
'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import { ToastProvider, useToast } from '@/components/Toast';

function MarketContent() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { addToast } = useToast();
  const [ticker, setTicker] = useState('');
  const [timeframe, setTimeframe] = useState('1d');
  const [period, setPeriod] = useState('1mo');
  const [broker, setBroker] = useState('standard');
  const [csvFile, setCsvFile] = useState(null);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  const handleDownload = async (e) => {
    e.preventDefault();
    if (!ticker) return addToast('Masukkan ticker terlebih dahulu', 'error');
    try {
      const formData = new FormData();
      formData.append('ticker', ticker);
      formData.append('timeframe', timeframe);
      formData.append('period', period);
      const res = await api.post('/api/market/download_yfinance', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${ticker}_${timeframe}_${period}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      addToast(`Data ${ticker.toUpperCase()} berhasil diunduh!`);
    } catch (err) {
      addToast(err.response?.data?.detail || 'Gagal mengunduh data', 'error');
    }
  };

  const handleImport = async (e) => {
    e.preventDefault();
    if (!csvFile) return addToast('Pilih file CSV terlebih dahulu', 'error');
    setImporting(true);
    try {
      const formData = new FormData();
      formData.append('broker', broker);
      formData.append('file', csvFile);
      const res = await api.post('/api/market/import_csv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      addToast(res.data.message);
      setCsvFile(null);
    } catch (err) {
      addToast(err.response?.data?.detail || 'Gagal mengimpor CSV', 'error');
    }
    setImporting(false);
  };

  if (authLoading) return null;

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1 className="page-title">Market Data</h1>
          <p className="page-subtitle">Download data historis & import CSV trade summary</p>
        </div>

        {/* YFinance Download */}
        <div className="card">
          <div className="card-title">📊 Download Data Historis (YFinance)</div>
          <form onSubmit={handleDownload}>
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">Ticker Symbol</label>
                <input className="form-input" placeholder="BBCA.JK, AAPL, BTC-USD" value={ticker} onChange={(e) => setTicker(e.target.value)} required />
              </div>
              <div className="form-group">
                <label className="form-label">Timeframe</label>
                <select className="form-select" value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
                  <option value="1m">1 Menit</option>
                  <option value="5m">5 Menit</option>
                  <option value="15m">15 Menit</option>
                  <option value="1h">1 Jam</option>
                  <option value="1d">1 Hari</option>
                  <option value="1wk">1 Minggu</option>
                  <option value="1mo">1 Bulan</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Period</label>
                <select className="form-select" value={period} onChange={(e) => setPeriod(e.target.value)}>
                  <option value="1d">1 Hari</option>
                  <option value="5d">5 Hari</option>
                  <option value="1mo">1 Bulan</option>
                  <option value="3mo">3 Bulan</option>
                  <option value="6mo">6 Bulan</option>
                  <option value="1y">1 Tahun</option>
                  <option value="2y">2 Tahun</option>
                  <option value="5y">5 Tahun</option>
                  <option value="max">Max</option>
                </select>
              </div>
            </div>
            <button type="submit" className="btn-primary mt-3">⬇️ Download CSV</button>
          </form>
        </div>

        {/* CSV Import */}
        <div className="card card-delay-2">
          <div className="card-title">📤 Import Trade Summary (CSV)</div>
          <form onSubmit={handleImport}>
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">Broker</label>
                <select className="form-select" value={broker} onChange={(e) => setBroker(e.target.value)}>
                  <option value="standard">Standard (Generic)</option>
                  <option value="ajaib">Ajaib</option>
                  <option value="stockbit">Stockbit</option>
                  <option value="ipot">IPOT (Indo Premier)</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">File CSV</label>
                <input type="file" accept=".csv" className="form-input" onChange={(e) => setCsvFile(e.target.files[0])} style={{ paddingTop: 9 }} />
              </div>
            </div>
            <button type="submit" className="btn-primary mt-3" disabled={importing}>
              {importing ? '⏳ Mengimpor...' : '📥 Import Transaksi'}
            </button>
          </form>
          <div className="stat-sub mt-3">
            Format kolom: Tanggal, Ticker, Tipe (BELI/JUAL), Jumlah, Harga, Fee
          </div>
        </div>
      </main>
    </div>
  );
}

export default function MarketPage() {
  return <ToastProvider><MarketContent /></ToastProvider>;
}
