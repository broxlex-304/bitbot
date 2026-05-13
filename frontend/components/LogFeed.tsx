'use client';
import { useStore, LogEntry } from '@/lib/store';

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch { return ''; }
}

export default function LogFeed({ maxHeight = '300px' }: { maxHeight?: string }) {
  const { logs } = useStore();

  return (
    <div className="log-feed" style={{ maxHeight }}>
      {logs.length === 0 && (
        <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px 0', fontSize: 12 }}>
          Waiting for bot activity...
        </div>
      )}
      {logs.map((log: LogEntry) => (
        <div key={log.id} className={`log-entry ${log.level}`}>
          <span className="log-time">{formatTime(log.timestamp)}</span>
          <span className="log-icon">{log.icon}</span>
          <span className="log-msg">{log.message}</span>
        </div>
      ))}
    </div>
  );
}
