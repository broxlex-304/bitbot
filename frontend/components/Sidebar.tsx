'use client';
import { useStore } from '@/lib/store';

const NAV_ITEMS = [
  { id: 'dashboard', icon: '📊', label: 'Dashboard' },
  { id: 'chart',     icon: '📈', label: 'Live Chart' },
  { id: 'signals',   icon: '🎯', label: 'Signals' },
  { id: 'positions', icon: '💼', label: 'Positions' },
  { id: 'news',      icon: '📰', label: 'News Feed' },
  { id: 'logs',      icon: '📋', label: 'Activity Logs' },
  { id: 'settings',  icon: '⚙️', label: 'Settings' },
];

export default function Sidebar() {
  const { activeTab, setActiveTab, botState, wsConnected } = useStore();

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">🤖</div>
        <div>
          <div className="sidebar-logo-name"><span>Bit</span>Bot</div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 500 }}>v1.0 · AI Trading</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-label">Navigation</div>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
            onClick={() => setActiveTab(item.id)}
            style={{ background: 'none', border: activeTab === item.id ? '1px solid rgba(59,130,246,0.2)' : '1px solid transparent' }}
          >
            <span style={{ fontSize: 16 }}>{item.icon}</span>
            {item.label}
          </button>
        ))}

        <div className="nav-label" style={{ marginTop: 8 }}>System</div>
        <div style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* WS Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            <span className={`status-dot ${wsConnected ? 'running' : 'idle'}`} />
            {wsConnected ? 'WebSocket live' : 'Disconnected'}
          </div>
          {/* Exchange */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            <span className={`status-dot ${botState.exchange_connected ? 'running' : 'idle'}`} />
            {botState.exchange_connected
              ? `${botState.exchange?.toUpperCase()} ${botState.paper_mode ? '(Paper)' : '(Live)'}`
              : 'No exchange'
            }
          </div>
          {/* Bot status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            <span className={`status-dot ${botState.status}`} />
            {botState.status.charAt(0).toUpperCase() + botState.status.slice(1)}
          </div>
        </div>
      </nav>

      {/* Cycle counter */}
      <div style={{ padding: '14px 16px', borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>Analysis Cycles</div>
        <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--primary)' }}>{botState.cycle_count}</div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>since start</div>
      </div>
    </aside>
  );
}
