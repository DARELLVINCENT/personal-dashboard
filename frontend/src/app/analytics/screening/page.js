'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import styles from './page.module.css';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ScreeningPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [mode, setMode] = useState('demo');
  const [manualTickers, setManualTickers] = useState('');

  // Filters
  const [ma50, setMa50] = useState('ignore');
  const [rsiMin, setRsiMin] = useState('');
  const [rsiMax, setRsiMax] = useState('');
  const [minVolume, setMinVolume] = useState('');
  const [maxPe, setMaxPe] = useState('');

  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [passedStocks, setPassedStocks] = useState([]);
  const [failedStocks, setFailedStocks] = useState([]);
  const [logs, setLogs] = useState([]);
  const [scanComplete, setScanComplete] = useState(false);
  const terminalRef = useRef(null);
  const abortRef = useRef(null);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs]);

  const addLog = useCallback((msg, type = 'info') => {
    const ts = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { ts, msg, type }]);
  }, []);

  const handleScan = async () => {
    // Reset state
    setScanning(true);
    setScanComplete(false);
    setPassedStocks([]);
    setFailedStocks([]);
    setLogs([]);
    setProgress({ done: 0, total: 0 });

    const modeLabel = { demo: 'DEMO (10 Bluechip)', full: 'FULL SCAN (Seluruh IHSG)', manual: 'MANUAL WATCHLIST' };
    addLog(`Memulai screening mode: ${modeLabel[mode] || mode}`, 'info');

    const payload = {
      mode,
      tickers: mode === 'manual' ? manualTickers.split(',').map(t => t.trim()).filter(Boolean) : [],
      filters: {
        ma50,
        rsi_min: rsiMin ? parseFloat(rsiMin) : null,
        rsi_max: rsiMax ? parseFloat(rsiMax) : null,
        min_volume: minVolume ? parseFloat(minVolume) : null,
        max_pe: maxPe ? parseFloat(maxPe) : null,
      },
    };

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      addLog('Menghubungi server & mengambil daftar saham...', 'info');

      const response = await fetch(`${API_BASE}/api/screening/scan_stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));

            if (evt.type === 'start') {
              setProgress({ done: 0, total: evt.total });
              addLog(`Memulai scanning ${evt.total} saham secara paralel...`, 'info');
            } else if (evt.type === 'result') {
              setProgress({ done: evt.progress, total: evt.total });
              if (evt.passed) {
                setPassedStocks((prev) => [...prev, evt]);
                addLog(`✅ ${evt.ticker} — LOLOS (Harga: ${Number(evt.price).toLocaleString('id-ID')}, RSI: ${evt.rsi != null ? Number(evt.rsi).toFixed(1) : 'N/A'})`, 'success');
              } else {
                setFailedStocks((prev) => [...prev, evt]);
                const reason = evt.reasons?.[0] || 'Tidak memenuhi kriteria';
                addLog(`❌ ${evt.ticker} — GAGAL: ${reason}`, 'error');
              }
            } else if (evt.type === 'done') {
              addLog(`Selesai! ${evt.total} saham telah dipindai.`, 'info');
            }
          } catch { /* skip malformed lines */ }
        }
      }

      setScanComplete(true);
    } catch (err) {
      if (err.name === 'AbortError') {
        addLog('Screening dibatalkan oleh pengguna.', 'warn');
      } else {
        console.error(err);
        addLog(`Error: ${err.message}`, 'error');
      }
    } finally {
      setScanning(false);
      abortRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortRef.current) abortRef.current.abort();
  };

  const handleExport = async () => {
    try {
      addLog('Mengekspor hasil ke Excel...', 'info');
      const res = await api.post('/api/screening/export_excel', {
        passed: passedStocks,
        failed: failedStocks,
      }, { responseType: 'blob' });

      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'screening_results.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      addLog('✅ File Excel berhasil diunduh!', 'success');
    } catch (err) {
      console.error(err);
      addLog('❌ Gagal mengekspor file Excel.', 'error');
    }
  };

  if (authLoading) return null;

  const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : 0;
  const hasResults = passedStocks.length > 0 || failedStocks.length > 0;

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 className="page-title">Automated Stock Screening</h1>
            <p className="page-subtitle">Pindai seluruh saham IHSG berdasarkan kriteria teknikal & fundamental</p>
          </div>
          <button
            className="btn btn-secondary"
            onClick={() => router.push('/analytics')}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            ← Kembali ke Analytics
          </button>
        </div>

        <div className={styles.screeningGrid}>
          {/* ─── Config Panel ─── */}
          <div className={`card ${styles.configPanel}`}>
            <h2 className="card-title">⚙️ Pengaturan Scan</h2>

            <div className="form-group">
              <label>Mode Scan</label>
              <select className="form-control" value={mode} onChange={(e) => setMode(e.target.value)} disabled={scanning}>
                <option value="demo">⚡ Demo Cepat (10 Bluechip)</option>
                <option value="full">🔍 Full Scan (900+ Saham IHSG)</option>
                <option value="manual">📝 Manual Watchlist</option>
              </select>
            </div>

            {mode === 'manual' && (
              <div className="form-group">
                <label>Daftar Ticker (pisahkan koma)</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="contoh: BBCA, BBRI, GOTO, ANTM"
                  value={manualTickers}
                  onChange={(e) => setManualTickers(e.target.value)}
                  disabled={scanning}
                />
              </div>
            )}

            {mode === 'full' && (
              <div className={styles.infoBox}>
                <strong>ℹ️ Full Scan</strong> akan memindai semua saham yang terdaftar di IDX. 
                Proses ini bisa memakan waktu beberapa menit tergantung jumlah emiten.
                Hasil akan muncul satu per satu di terminal.
              </div>
            )}

            <div className="form-group">
              <label>Filter MA50</label>
              <select className="form-control" value={ma50} onChange={(e) => setMa50(e.target.value)} disabled={scanning}>
                <option value="ignore">Abaikan</option>
                <option value="above">📈 Harga Di Atas MA50 (Uptrend)</option>
                <option value="below">📉 Harga Di Bawah MA50 (Downtrend)</option>
              </select>
            </div>

            <div className={styles.row}>
              <div className="form-group" style={{ flex: 1 }}>
                <label>RSI Min</label>
                <input type="number" className="form-control" placeholder="0" value={rsiMin} onChange={(e) => setRsiMin(e.target.value)} disabled={scanning} min="0" max="100" />
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label>RSI Max</label>
                <input type="number" className="form-control" placeholder="100" value={rsiMax} onChange={(e) => setRsiMax(e.target.value)} disabled={scanning} min="0" max="100" />
              </div>
            </div>

            <div className="form-group">
              <label>Min Volume Harian</label>
              <input type="number" className="form-control" placeholder="Abaikan" value={minVolume} onChange={(e) => setMinVolume(e.target.value)} disabled={scanning} />
            </div>

            <div className="form-group">
              <label>Max P/E Ratio</label>
              <input type="number" className="form-control" placeholder="Abaikan" value={maxPe} onChange={(e) => setMaxPe(e.target.value)} disabled={scanning} />
            </div>

            {!scanning ? (
              <button
                className={`btn btn-primary ${styles.scanBtn}`}
                onClick={handleScan}
                disabled={mode === 'manual' && !manualTickers}
              >
                🚀 Mulai Screening
              </button>
            ) : (
              <button className={`btn btn-danger ${styles.scanBtn}`} onClick={handleStop}>
                ⏹ Stop Screening
              </button>
            )}
          </div>

          {/* ─── Output Panel ─── */}
          <div className={styles.outputPanel}>
            {/* Progress Bar */}
            {scanning && progress.total > 0 && (
              <div className={styles.progressContainer}>
                <div className={styles.progressInfo}>
                  <span>Scanning {progress.done} / {progress.total} saham</span>
                  <span>{pct}%</span>
                </div>
                <div className={styles.progressBar}>
                  <div className={styles.progressFill} style={{ width: `${pct}%` }} />
                </div>
              </div>
            )}

            {/* Terminal */}
            <div className={`card ${styles.terminalCard}`}>
              <div className={styles.terminalHeader}>
                <div className={styles.terminalDots}>
                  <span /><span /><span />
                </div>
                <span>Terminal Log</span>
                {scanning && <span className={styles.terminalLive}>● LIVE</span>}
              </div>
              <div className={styles.terminalBody} ref={terminalRef}>
                {logs.length === 0 ? (
                  <span className={styles.terminalMuted}>$ Siap untuk memulai screening...</span>
                ) : (
                  logs.map((log, idx) => (
                    <div key={idx} className={`${styles.terminalLine} ${styles[`log_${log.type}`] || ''}`}>
                      <span className={styles.terminalTs}>[{log.ts}]</span> {log.msg}
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Results */}
            {hasResults && (
              <div className={`card ${styles.resultsCard}`}>
                <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>📊 Hasil Screening {scanComplete ? '' : '(sedang berjalan...)'}</span>
                  {scanComplete && (
                    <button className="btn btn-sm btn-outline" onClick={handleExport}>
                      📥 Export Excel
                    </button>
                  )}
                </div>

                {/* Summary badges */}
                <div className={styles.summaryRow}>
                  <div className={styles.summaryCard}>
                    <div className={styles.summaryNum} style={{ color: '#3fb950' }}>{passedStocks.length}</div>
                    <div className={styles.summaryLabel}>Lolos</div>
                  </div>
                  <div className={styles.summaryCard}>
                    <div className={styles.summaryNum} style={{ color: '#f85149' }}>{failedStocks.length}</div>
                    <div className={styles.summaryLabel}>Gagal</div>
                  </div>
                  <div className={styles.summaryCard}>
                    <div className={styles.summaryNum} style={{ color: '#8b949e' }}>{progress.done}</div>
                    <div className={styles.summaryLabel}>Total</div>
                  </div>
                </div>

                {/* Passed Table */}
                <h3 className={styles.sectionTitle}>
                  <span className={styles.badgeSuccess}>{passedStocks.length}</span> Saham Lolos Filter
                </h3>
                {passedStocks.length > 0 ? (
                  <div className={styles.tableContainer}>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Ticker</th>
                          <th>Price</th>
                          <th>MA50</th>
                          <th>RSI</th>
                          <th>Volume</th>
                          <th>P/E</th>
                        </tr>
                      </thead>
                      <tbody>
                        {passedStocks.map((s) => (
                          <tr key={s.ticker}>
                            <td className="font-bold" style={{ color: 'var(--accent-green)' }}>{s.ticker}</td>
                            <td>{s.price != null ? Number(s.price).toLocaleString('id-ID') : '—'}</td>
                            <td>{s.ma50 != null ? Number(s.ma50).toLocaleString('id-ID', { maximumFractionDigits: 0 }) : '—'}</td>
                            <td>{s.rsi != null ? Number(s.rsi).toFixed(1) : '—'}</td>
                            <td>{s.volume != null ? Number(s.volume).toLocaleString('id-ID', { maximumFractionDigits: 0 }) : '—'}</td>
                            <td>{s.pe_ratio != null ? Number(s.pe_ratio).toFixed(2) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-muted" style={{ padding: '12px 0' }}>Belum ada saham yang lolos filter.</p>
                )}

                {/* Failed Table */}
                <h3 className={styles.sectionTitle} style={{ marginTop: 24 }}>
                  <span className={styles.badgeDanger}>{failedStocks.length}</span> Saham Tidak Lolos
                </h3>
                {failedStocks.length > 0 ? (
                  <div className={styles.tableContainer}>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Ticker</th>
                          <th>Price</th>
                          <th>Alasan Gagal</th>
                        </tr>
                      </thead>
                      <tbody>
                        {failedStocks.map((s) => (
                          <tr key={s.ticker}>
                            <td className="font-bold text-muted">{s.ticker}</td>
                            <td className="text-muted">{s.price != null ? s.price.toLocaleString('id-ID') : '—'}</td>
                            <td style={{ fontSize: 13 }}>
                              <ul style={{ paddingLeft: 16, margin: 0, color: '#f85149' }}>
                                {s.reasons.map((r, i) => <li key={i}>{r}</li>)}
                              </ul>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-muted" style={{ padding: '12px 0' }}>Semua saham lolos filter! 🎉</p>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
