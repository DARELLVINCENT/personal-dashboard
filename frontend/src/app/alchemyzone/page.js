'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export default function AlchemyZonePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  // ── Forecast State ──
  const [ticker, setTicker] = useState('BBCA.JK');
  const [days, setDays] = useState(14);
  const [modelType, setModelType] = useState('ARIMA');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // ── Sentiment State ──
  const [sentTicker, setSentTicker] = useState('BBCA.JK');
  const [sentData, setSentData] = useState(null);
  const [sentLoading, setSentLoading] = useState(false);
  const [sentError, setSentError] = useState('');

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
    else if (user) {
      fetchForecast();
    }
  }, [user, authLoading, router]);

  // ── Forecast API ──
  const fetchForecast = async (e) => {
    if (e) e.preventDefault();
    if (!ticker) return;
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/api/forecast?ticker=${ticker}&days=${days}&model_type=${modelType}`);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Gagal memuat forecast. Pastikan ticker valid.');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  // ── Sentiment API ──
  const fetchSentiment = async (e) => {
    if (e) e.preventDefault();
    if (!sentTicker) return;
    setSentLoading(true);
    setSentError('');
    try {
      const res = await api.get(`/api/sentiment?ticker=${sentTicker}`);
      setSentData(res.data);
    } catch (err) {
      setSentError(err.response?.data?.detail || 'Gagal memuat analisis sentimen.');
      setSentData(null);
    } finally {
      setSentLoading(false);
    }
  };

  const fmtRp = (v) => `Rp ${Number(v).toLocaleString('id-ID', { minimumFractionDigits: 0 })}`;

  const getSentimentColor = (label) => {
    if (label === 'Bullish') return '#10B981';
    if (label === 'Bearish') return '#EF4444';
    return '#8B9AB5';
  };

  const getSentimentEmoji = (label) => {
    if (label === 'Bullish') return '🟢';
    if (label === 'Bearish') return '🔴';
    return '⚪';
  };

  if (authLoading) return null;

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-header">
          <h1 className="page-title">🔮 Alchemy Zone</h1>
          <p className="page-subtitle">Predictive Analytics, Price Forecasting & Market Sentiment NLP</p>
        </div>

        {/* ═══════════════════════════════════════════════════════
            SECTION 1: STOCK PRICE FORECASTING
            ═══════════════════════════════════════════════════════ */}
        <div className="alchemy-section-header">
          <span className="alchemy-section-icon">📈</span>
          <div>
            <h2 className="alchemy-section-title">Stock Price Forecasting</h2>
            <p className="alchemy-section-sub">Peramalan harga menggunakan Auto-ARIMA, LSTM Deep Learning, XGBoost, dan Ensemble</p>
          </div>
        </div>

        {/* Forecast Input */}
        <div className="card card-delay-1 mb-4">
          <form onSubmit={fetchForecast} className="flex gap-3 items-center flex-wrap">
            <div style={{ flex: 1, minWidth: '200px' }}>
              <label className="form-label">Ticker Symbol</label>
              <input
                type="text"
                className="form-input"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="e.g., BBCA.JK, TLKM.JK, AAPL"
                required
              />
            </div>
            <div style={{ width: '150px' }}>
              <label className="form-label">Forecast Days</label>
              <select className="form-select" value={days} onChange={(e) => setDays(Number(e.target.value))}>
                <option value={7}>7 Hari</option>
                <option value={14}>14 Hari</option>
                <option value={30}>30 Hari</option>
              </select>
            </div>
            <div style={{ width: '180px' }}>
              <label className="form-label">Model</label>
              <select className="form-select" value={modelType} onChange={(e) => setModelType(e.target.value)}>
                <option value="ARIMA">Auto-ARIMA</option>
                <option value="LSTM">LSTM (Deep Learning)</option>
                <option value="XGBOOST">XGBoost</option>
                <option value="ENSEMBLE">Ensemble (All)</option>
              </select>
            </div>
            <div style={{ marginTop: '22px' }}>
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? '🔮 Forecasting...' : 'Run Forecast'}
              </button>
            </div>
          </form>
          {error && <div className="login-error mt-4" style={{ marginBottom: 0 }}>{error}</div>}
        </div>

        {/* Forecast Loading */}
        {loading && (
          <div className="skeleton mt-4" style={{ height: '400px', width: '100%', borderRadius: 'var(--radius-lg)' }}></div>
        )}

        {/* Forecast Results */}
        {!loading && data && (
          <>
            {/* Row 1: Trend + Support/Resistance */}
            <div className="stats-grid card-delay-2">
              <div className={`stat-card ${data.analysis.trend === 'BULLISH' ? 'accent-green' : data.analysis.trend === 'BEARISH' ? 'accent-red' : 'accent-orange'}`}>
                <div className="stat-label">Trend Forecast</div>
                <div className={`stat-value ${data.analysis.trend === 'BULLISH' ? 'profit' : data.analysis.trend === 'BEARISH' ? 'loss' : ''}`}>
                  {data.analysis.trend}
                </div>
                <div className="stat-sub">{data.analysis.trend_pct}% expected change</div>
              </div>
              <div className="stat-card accent-blue">
                <div className="stat-label">Predicted Support</div>
                <div className="stat-value">{fmtRp(data.analysis.support)}</div>
                <div className="stat-sub">Lower bound estimate</div>
              </div>
              <div className="stat-card accent-purple">
                <div className="stat-label">Predicted Resistance</div>
                <div className="stat-value">{fmtRp(data.analysis.resistance)}</div>
                <div className="stat-sub">Upper bound estimate</div>
              </div>
              <div className="stat-card accent-orange">
                <div className="stat-label">Model Engine</div>
                <div className="stat-value text-sm" style={{ fontSize: '15px', marginTop: '6px', marginBottom: '4px' }}>
                  {data.model_info.name}
                </div>
                <div className="stat-sub" style={{ fontSize: '11px' }}>
                  {data.model_info.aic ? `AIC: ${data.model_info.aic}` : ''}
                </div>
              </div>
            </div>

            {/* Row 2: Model Accuracy Metrics */}
            <div className="stats-grid card-delay-2" style={{ marginTop: '12px' }}>
              <div className="stat-card" style={{ borderLeft: `3px solid ${data.model_info.mape <= 3 ? '#10B981' : data.model_info.mape <= 7 ? '#F59E0B' : '#EF4444'}` }}>
                <div className="stat-label">MAPE</div>
                <div className="stat-value" style={{ color: data.model_info.mape <= 3 ? '#10B981' : data.model_info.mape <= 7 ? '#F59E0B' : '#EF4444' }}>
                  {data.model_info.mape}%
                </div>
                <div className="stat-sub">Mean Abs % Error {data.model_info.mape <= 3 ? '(Excellent)' : data.model_info.mape <= 7 ? '(Good)' : '(Fair)'}</div>
              </div>
              <div className="stat-card" style={{ borderLeft: '3px solid #3B82F6' }}>
                <div className="stat-label">RMSE</div>
                <div className="stat-value">{fmtRp(data.model_info.rmse)}</div>
                <div className="stat-sub">Root Mean Squared Error</div>
              </div>
              <div className="stat-card" style={{ borderLeft: '3px solid #8B5CF6' }}>
                <div className="stat-label">MAE</div>
                <div className="stat-value">{fmtRp(data.model_info.mae)}</div>
                <div className="stat-sub">Mean Absolute Error</div>
              </div>
              <div className="stat-card" style={{ borderLeft: `3px solid ${data.model_info.directional_accuracy >= 60 ? '#10B981' : '#F59E0B'}` }}>
                <div className="stat-label">Direction Accuracy</div>
                <div className="stat-value" style={{ color: data.model_info.directional_accuracy >= 60 ? '#10B981' : '#F59E0B' }}>
                  {data.model_info.directional_accuracy}%
                </div>
                <div className="stat-sub">Prediksi arah naik/turun</div>
              </div>
            </div>

            {/* Data Preparation Info */}
            {data.data_preparation && (
              <div className="card card-delay-2" style={{ marginTop: '12px', padding: '14px 20px' }}>
                <div className="card-title" style={{ fontSize: '13px', marginBottom: '8px' }}>🔬 Data Preparation Summary</div>
                <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <span>📊 Data Points: <strong style={{ color: 'var(--text-primary)' }}>{data.data_preparation.total_data_points}</strong></span>
                  <span>🩹 Missing Filled: <strong style={{ color: 'var(--text-primary)' }}>{data.data_preparation.missing_filled}</strong></span>
                  <span>⚡ Outliers Capped: <strong style={{ color: data.data_preparation.outliers_capped > 0 ? '#F59E0B' : 'var(--text-primary)' }}>{data.data_preparation.outliers_capped}</strong></span>
                  <span>📈 Stationary: <strong style={{ color: data.data_preparation.is_stationary ? '#10B981' : '#F59E0B' }}>{data.data_preparation.is_stationary ? 'Yes' : 'No'}</strong>
                    {data.data_preparation.adf_pvalue !== null && ` (p=${data.data_preparation.adf_pvalue})`}
                  </span>
                  <span>🧪 Test Set: <strong style={{ color: 'var(--text-primary)' }}>{data.data_preparation.test_set_size} days</strong></span>
                </div>
              </div>
            )}

            {/* Sub-model comparison for Ensemble */}
            {data.sub_models && (
              <div className="card card-delay-2" style={{ marginTop: '12px' }}>
                <div className="card-title">⚖️ Ensemble — Sub-model Performance</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginTop: '8px' }}>
                  {Object.entries(data.sub_models).map(([key, sub]) => (
                    <div key={key} style={{
                      background: 'rgba(255,255,255,0.03)', borderRadius: '10px', padding: '14px',
                      border: '1px solid rgba(255,255,255,0.06)'
                    }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
                        {sub.name} {sub.weight != null && <span style={{ color: 'var(--text-secondary)', fontWeight: 400 }}>({(sub.weight * 100).toFixed(0)}%)</span>}
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px', fontSize: '11px' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>MAPE:</span>
                        <span style={{ color: sub.metrics.mape <= 3 ? '#10B981' : sub.metrics.mape <= 7 ? '#F59E0B' : '#EF4444', fontWeight: 600 }}>{sub.metrics.mape}%</span>
                        <span style={{ color: 'var(--text-secondary)' }}>RMSE:</span>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{fmtRp(sub.metrics.rmse)}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>Dir Acc:</span>
                        <span style={{ color: sub.metrics.directional_accuracy >= 60 ? '#10B981' : '#F59E0B', fontWeight: 600 }}>{sub.metrics.directional_accuracy}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="card card-delay-3" style={{ height: '500px', padding: '16px', marginTop: '12px' }}>
              <div className="card-title">📈 Price Forecast Chart ({data.ticker})</div>
              <Plot
                data={[
                  {
                    x: data.historical.dates,
                    y: data.historical.values,
                    type: 'scatter', mode: 'lines+markers', name: 'Historical',
                    line: { color: '#3B82F6', width: 2 }, marker: { size: 4 }
                  },
                  {
                    x: data.forecast.dates,
                    y: data.forecast.values,
                    type: 'scatter', mode: 'lines+markers', name: 'Forecast (Mean)',
                    line: { color: '#FFA116', width: 2, dash: 'dot' }, marker: { size: 4 }
                  },
                  {
                    x: data.forecast.dates, y: data.forecast.upper_bound,
                    type: 'scatter', mode: 'lines', name: 'Upper Bound',
                    line: { color: 'transparent' }, showlegend: false
                  },
                  {
                    x: data.forecast.dates, y: data.forecast.lower_bound,
                    type: 'scatter', mode: 'lines', name: 'Lower Bound',
                    fill: 'tonexty', fillcolor: 'rgba(255, 161, 22, 0.15)',
                    line: { color: 'transparent' }, showlegend: false
                  }
                ]}
                layout={{
                  paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                  font: { color: '#8B9AB5' }, margin: { t: 10, b: 40, l: 50, r: 20 },
                  xaxis: { gridcolor: 'rgba(56, 72, 96, 0.2)', tickangle: -45, type: 'category' },
                  yaxis: { gridcolor: 'rgba(56, 72, 96, 0.2)', tickprefix: 'Rp ' },
                  legend: { orientation: 'h', y: 1.1 }, autosize: true
                }}
                useResizeHandler={true}
                style={{ width: '100%', height: 'calc(100% - 40px)' }}
                config={{ displayModeBar: true, responsive: true }}
              />
            </div>
          </>
        )}

        {/* ═══════════════════════════════════════════════════════
            SECTION 2: MARKET SENTIMENT ANALYSIS
            ═══════════════════════════════════════════════════════ */}
        <div className="alchemy-divider"></div>

        <div className="alchemy-section-header">
          <span className="alchemy-section-icon">📰</span>
          <div>
            <h2 className="alchemy-section-title">Market Sentiment Analysis</h2>
            <p className="alchemy-section-sub">Analisis sentimen berita menggunakan NLP (Natural Language Processing)</p>
          </div>
        </div>

        {/* Sentiment Input */}
        <div className="card card-delay-1 mb-4">
          <form onSubmit={fetchSentiment} className="flex gap-3 items-center flex-wrap">
            <div style={{ flex: 1, minWidth: '200px' }}>
              <label className="form-label">Ticker / Keyword</label>
              <input
                type="text"
                className="form-input"
                value={sentTicker}
                onChange={(e) => setSentTicker(e.target.value.toUpperCase())}
                placeholder="e.g., BBCA.JK, AAPL, TSLA"
                required
              />
            </div>
            <div style={{ marginTop: '22px' }}>
              <button type="submit" className="btn-primary" disabled={sentLoading}>
                {sentLoading ? '📰 Analyzing...' : 'Analyze Sentiment'}
              </button>
            </div>
          </form>
          {sentError && <div className="login-error mt-4" style={{ marginBottom: 0 }}>{sentError}</div>}
        </div>

        {/* Sentiment Loading */}
        {sentLoading && (
          <div className="skeleton mt-4" style={{ height: '300px', width: '100%', borderRadius: 'var(--radius-lg)' }}></div>
        )}

        {/* Sentiment Results */}
        {!sentLoading && sentData && (
          <>
            {/* Summary + Gauge */}
            <div className="flex gap-4" style={{ flexWrap: 'wrap', marginBottom: '20px' }}>
              {/* Overall Sentiment Card */}
              <div className="card" style={{ flex: '1', minWidth: '280px' }}>
                <div className="card-title">🧠 Overall Sentiment: {sentData.ticker}</div>
                <div className="sentiment-gauge-container">
                  <div className="sentiment-gauge-bar">
                    <div className="sentiment-gauge-fill" style={{
                      width: `${((sentData.overall_sentiment + 1) / 2) * 100}%`,
                      background: sentData.overall_label === 'Bullish'
                        ? 'linear-gradient(90deg, #10B981, #34D399)'
                        : sentData.overall_label === 'Bearish'
                          ? 'linear-gradient(90deg, #EF4444, #F87171)'
                          : 'linear-gradient(90deg, #6B7280, #9CA3AF)'
                    }}></div>
                    <div className="sentiment-gauge-needle" style={{
                      left: `${((sentData.overall_sentiment + 1) / 2) * 100}%`
                    }}></div>
                  </div>
                  <div className="sentiment-gauge-labels">
                    <span style={{ color: '#EF4444' }}>Bearish</span>
                    <span style={{ color: '#8B9AB5' }}>Neutral</span>
                    <span style={{ color: '#10B981' }}>Bullish</span>
                  </div>
                </div>
                <div className="sentiment-overall-label" style={{ color: getSentimentColor(sentData.overall_label) }}>
                  {getSentimentEmoji(sentData.overall_label)} {sentData.overall_label}
                  <span className="sentiment-score">({sentData.overall_sentiment > 0 ? '+' : ''}{sentData.overall_sentiment})</span>
                </div>
                <p className="sentiment-summary">{sentData.summary}</p>
              </div>

              {/* Distribution Donut */}
              <div className="card" style={{ flex: '1', minWidth: '280px' }}>
                <div className="card-title">📊 Sentiment Distribution</div>
                {sentData.total_articles > 0 ? (
                  <Plot
                    data={[{
                      values: [sentData.bullish_count, sentData.neutral_count, sentData.bearish_count],
                      labels: ['Bullish', 'Neutral', 'Bearish'],
                      type: 'pie', hole: 0.55,
                      marker: { colors: ['#10B981', '#6B7280', '#EF4444'] },
                      textinfo: 'label+percent',
                      textfont: { size: 12, color: '#F0F4F8' },
                      hoverinfo: 'label+value+percent'
                    }]}
                    layout={{
                      paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                      font: { color: '#8B9AB5' },
                      margin: { t: 10, b: 10, l: 10, r: 10 },
                      showlegend: false, height: 240,
                      annotations: [{
                        text: `${sentData.total_articles}`,
                        showarrow: false,
                        font: { size: 22, color: '#F0F4F8', weight: 700 }
                      }]
                    }}
                    config={{ displayModeBar: false, responsive: true }}
                    style={{ width: '100%' }}
                  />
                ) : (
                  <p className="text-muted" style={{ textAlign: 'center', padding: 40 }}>Tidak ada artikel.</p>
                )}
                <div className="sentiment-dist-legend">
                  <div className="sentiment-dist-item">
                    <span className="sentiment-dot" style={{ background: '#10B981' }}></span>
                    Bullish: {sentData.bullish_count}
                  </div>
                  <div className="sentiment-dist-item">
                    <span className="sentiment-dot" style={{ background: '#6B7280' }}></span>
                    Neutral: {sentData.neutral_count}
                  </div>
                  <div className="sentiment-dist-item">
                    <span className="sentiment-dot" style={{ background: '#EF4444' }}></span>
                    Bearish: {sentData.bearish_count}
                  </div>
                </div>
              </div>
            </div>

            {/* News Cards */}
            <div className="card card-delay-3">
              <div className="card-title">📰 News Articles ({sentData.total_articles})</div>
              {sentData.articles.length === 0 ? (
                <p className="text-muted" style={{ textAlign: 'center', padding: 20 }}>Tidak ditemukan berita.</p>
              ) : (
                <div className="news-grid">
                  {sentData.articles.map((art, idx) => (
                    <div key={idx} className="news-card">
                      <div className="news-card-header">
                        <span className={`sentiment-badge sentiment-badge-${art.sentiment.label.toLowerCase()}`}>
                          {getSentimentEmoji(art.sentiment.label)} {art.sentiment.label}
                        </span>
                        <span className="news-source">{art.source}</span>
                      </div>
                      <a href={art.url} target="_blank" rel="noopener noreferrer" className="news-title">
                        {art.title}
                      </a>
                      {art.description && (
                        <p className="news-desc">{art.description}</p>
                      )}
                      <div className="news-card-footer">
                        <div className="news-polarity-bar">
                          <div className="news-polarity-fill" style={{
                            width: `${((art.sentiment.polarity + 1) / 2) * 100}%`,
                            background: getSentimentColor(art.sentiment.label)
                          }}></div>
                        </div>
                        <span className="news-date">
                          {art.published_at ? new Date(art.published_at).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }) : ''}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
