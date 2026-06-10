'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: '📊' },
  { href: '/analytics', label: 'Analytics', icon: '📈' },
  { href: '/strategy', label: 'Strategi', icon: '🎯' },
  { href: '/market', label: 'Market Data', icon: '🌐' },
  { href: '/alchemyzone', label: 'Alchemy Zone', icon: '🔮' },
];

const ADMIN_ITEM = { href: '/admin', label: 'Admin Panel', icon: '🛡️' };

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  if (!user) return null;

  const items = user.is_admin ? [...NAV_ITEMS, ADMIN_ITEM] : NAV_ITEMS;

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">{user.username}</div>
      <div className="sidebar-subtitle">Personal Dashboard</div>

      <nav className="sidebar-nav">
        {items.map((item) => (
          <Link key={item.href} href={item.href}
            className={`nav-link ${pathname === item.href ? 'active' : ''}`}>
            <span className="icon">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="sidebar-user">
        <div className="user-card">
          <div className="user-avatar">{user.username.charAt(0)}</div>
          <div>
            <div className="user-name">{user.username}</div>
            <div className="user-role">{user.is_admin ? 'Administrator' : 'Trader'}</div>
          </div>
        </div>
        <button className="btn-logout" onClick={logout}>Logout</button>
      </div>
    </aside>
  );
}
