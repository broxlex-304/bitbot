'use client';
import { useEffect, useRef } from 'react';
import { useStore } from '@/lib/store';

declare global {
  interface Window {
    TradingView: any;
  }
}

export default function TradingChart() {
  const tvContainerRef = useRef<HTMLDivElement>(null);
  const { botState, prediction, currentPrice } = useStore();

  const initTradingView = () => {
    if (typeof window === 'undefined' || !window.TradingView || !tvContainerRef.current) return;
    
    // Clear previous widget
    tvContainerRef.current.innerHTML = '';
    const containerId = "tv_chart_widget";
    const container = document.createElement('div');
    container.id = containerId;
    container.style.height = '100%';
    container.style.width = '100%';
    tvContainerRef.current.appendChild(container);

    // Professional normalization: Strip everything except the core pair
    let sym = botState.symbol
      .replace('BINANCE:', '').replace('MEXC:', '').replace('BYBIT:', '').replace('KUCOIN:', '').replace('OKX:', '')
      .replace('/', '').replace('.P', '').replace('.p', '').replace('PERP', '');
    
    new window.TradingView.widget({
      "width": "100%",
      "height": "100%",
      "symbol": `BINANCE:${sym}PERP`,
      "interval": botState.timeframe === '1h' ? '60' : botState.timeframe === '15m' ? '15' : '1',
      "timezone": "Etc/UTC",
      "theme": "dark",
      "style": "1",
      "locale": "en",
      "toolbar_bg": "#111827",
      "enable_publishing": false,
      "allow_symbol_change": true,
      "container_id": containerId,
      "backgroundColor": "#111827",
      "gridColor": "rgba(255, 255, 255, 0.04)",
      "hide_side_toolbar": false,
      "save_image": false,
      "details": true,
      "hotlist": true,
      "calendar": true,
    });
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;

    if (!window.TradingView) {
      const scriptTV = document.createElement('script');
      scriptTV.src = 'https://s3.tradingview.com/tv.js';
      scriptTV.async = true;
      scriptTV.onload = () => initTradingView();
      document.head.appendChild(scriptTV);
    } else {
      initTradingView();
    }

    return () => {
      if (tvContainerRef.current) tvContainerRef.current.innerHTML = '';
    };
  }, [botState.symbol, botState.timeframe]);

  const isNeutral = !prediction.direction || prediction.direction === 'NEUTRAL';
  const color = prediction.direction === 'BUY' ? 'var(--green)' : prediction.direction === 'SELL' ? 'var(--red)' : 'var(--yellow)';

  // Calculate SL/TP prices based on current price if we have pct
  const slPrice = (prediction.stop_loss_pct && currentPrice) 
    ? (prediction.direction === 'BUY' ? currentPrice * (1 - prediction.stop_loss_pct/100) : currentPrice * (1 + prediction.stop_loss_pct/100))
    : null;
  const tpPrice = (prediction.take_profit_pct && currentPrice)
    ? (prediction.direction === 'BUY' ? currentPrice * (1 + prediction.take_profit_pct/100) : currentPrice * (1 - prediction.take_profit_pct/100))
    : null;

  return (
    <div className="chart-container animate-in" style={{ position: 'relative', height: 500 }}>
      <div className="chart-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: '-0.5px' }}>💎 Live Trading View</span>
          <span className="badge badge-blue">{botState.symbol}</span>
          <span className="badge badge-gray">{botState.timeframe}</span>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="status-dot running" /> 🟢 PRO Calculations Active
        </div>
      </div>
      
      <div id="tv_chart_container" ref={tvContainerRef} style={{ height: 'calc(100% - 48px)', width: '100%' }} />

      {/* Floating Prediction Overlay (Directly on Chart - MOVED TO BOTTOM) */}
      {!isNeutral && (
        <div style={{
          position: 'absolute',
          bottom: 20,
          left: 20,
          background: 'rgba(17, 24, 39, 0.85)',
          backdropFilter: 'blur(12px)',
          border: `1px solid ${color}40`,
          borderRadius: 12,
          padding: '12px 16px',
          width: 220,
          zIndex: 10,
          boxShadow: `0 8px 32px rgba(0,0,0,0.4), 0 0 15px ${color}20`,
          animation: 'fadeSlideIn 0.5s ease'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>AI Analysis</span>
            <span style={{ color, fontWeight: 900, fontSize: 16 }}>{prediction.confidence?.toFixed(0)}%</span>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <div style={{ 
                width: 32, height: 32, borderRadius: 8, background: `${color}20`, 
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18
            }}>
              {prediction.direction === 'BUY' ? '🚀' : '🔻'}
            </div>
            <div>
                <div style={{ fontSize: 14, fontWeight: 800, color }}>{prediction.direction} SIGNAL</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Strength: {prediction.confidence! > 85 ? 'High' : 'Moderate'}</div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                <span style={{ color: 'var(--text-secondary)' }}>Target TP</span>
                <span style={{ color: 'var(--green)', fontWeight: 600 }}>
                    {tpPrice ? `$${tpPrice.toLocaleString(undefined, {maximumFractionDigits:2})}` : `${prediction.take_profit_pct}%`}
                </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                <span style={{ color: 'var(--text-secondary)' }}>Stop Loss</span>
                <span style={{ color: 'var(--red)', fontWeight: 600 }}>
                    {slPrice ? `$${slPrice.toLocaleString(undefined, {maximumFractionDigits:2})}` : `${prediction.stop_loss_pct}%`}
                </span>
            </div>
            <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, marginTop: 4, overflow: 'hidden' }}>
                <div style={{ width: `${prediction.confidence}%`, height: '100%', background: color }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
