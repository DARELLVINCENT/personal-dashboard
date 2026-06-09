'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { user, login } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (user) router.push('/');
  }, [user, router]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      router.push('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Login gagal. Periksa kembali username dan password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <h1>PORTFOLIO</h1>
          <p>Trading Journal v2.0</p>
        </div>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <input
            type="text" className="login-input" placeholder="User ID"
            value={username} onChange={(e) => setUsername(e.target.value)}
            required autoFocus
          />
          <input
            type="password" className="login-input" placeholder="Password"
            value={password} onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? 'Memproses...' : 'Login'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 24, fontSize: 12, color: 'var(--text-muted)' }}>
          FastAPI + Next.js · Portfolio Tracker
        </p>
      </div>
    </div>
  );
}
