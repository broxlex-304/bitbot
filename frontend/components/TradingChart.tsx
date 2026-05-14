'use client';
import { useEffect, useRef, useState } from 'react';
import { useStore } from '@/lib/store';

declare global {
  interface Window {
    LightweightCharts: {
      createChart: (container: HTMLElement, options: Record<string, unknown>) => {
        addCandlestickSeries: (opts?: Record<string, unknown>) => {
          setData: (data: unknown[]) => void;
          update: (d: unknown) => void;
        };
        addHistogramSeries: (opts?: Record<string, unknown>) => {
          setData: (data: unknown[]) => void;
          update: (d: unknown) => void;
        };
        applyOptions: (o: Record<string, unknown>) => void;
        timeScale: () => { fitContent: () => void };
        remove: () => void;
      };
    };
    TradingView: any;
  }
}

export default function TradingChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const tvContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const candleSeriesRef = useRef<any>(null);
  const volSeriesRef = useRef<any>(null);
  const [chartMode, setChartMode] = useState<'lightweight' | 'tradingview'>('lightweight');
  const { candles, botState, prediction } = useStore();

  const initLightweight = () => {
    if (!containerRef.current || !window.LightweightCharts) return;
    if (chartRef.current) { try { chartRef.current.remove(); } catch(e){} }

    const chart = window.LightweightCharts.createChart(containerRef.current, {
      layout: { background: { color: '#111827' }, textColor: '#94a3b8' },
      grid: { vertLines: { color: 'rgba(255,255,255,0.04)' }, horzLines: { color: 'rgba(255,255,255,0.04)' } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.06)', scaleMargins: { top: 0.1, bottom: 0.25 } },
      timeScale: { borderColor: 'rgba(255,255,255,0.06)', timeVisible: true, secondsVisible: false },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981', downColor: '#ef4444',
      borderUpColor: '#10b981', borderDownColor: '#ef4444',
      wickUpColor: '#10b981', wickDownColor: '#ef4444',
    });

    const volSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '',
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volSeriesRef.current = volSeries;
  };

  const initTradingView = () => {
    if (typeof window === 'undefined' || !window.TradingView) return;
    const sym = botState.symbol.replace('/', '');
    new window.TradingView.widget({
      "width": "100%",
      "height": 420,
      "symbol": `BINANCE:${sym}PERP`,
      "interval": botState.timeframe === '1h' ? '60' : botState.timeframe === '15m' ? '15' : '1',
      "timezone": "Etc/UTC",
      "theme": "dark",
      "style": "1",
      "locale": "en",
      "toolbar_bg": "#f1f3f6",
      "enable_publishing": false,
      "allow_symbol_change": true,
      "container_id": "tv_chart_container"
    });
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;

    // Load LightweightCharts
    if (!window.LightweightCharts) {
      const script = document.createElement('script');
      script.src = 'https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js';
      script.onload = () => { if (chartMode === 'lightweight') initLightweight(); };
      document.head.appendChild(script);
    } else if (chartMode === 'lightweight') {
      initLightweight();
    }

    // Load TradingView
    if (!window.TradingView) {
      const scriptTV = document.createElement('script');
      scriptTV.src = 'https://s3.tradingview.com/tv.js';
      scriptTV.onload = () => { if (chartMode === 'tradingview') initTradingView(); };
      document.head.appendChild(scriptTV);
    } else if (chartMode === 'tradingview') {
      initTradingView();
    }

    return () => {
      if (chartRef.current) {
        try { chartRef.current.remove(); chartRef.current = null; } catch(e){}
      }
      // Clear the container to ensure no remnants of TradingView are left
      if (tvContainerRef.current) tvContainerRef.current.innerHTML = '';
      if (containerRef.current) containerRef.current.innerHTML = '';
    };
  }, [chartMode, botState.symbol]); // Also re-init on symbol change to keep TV synced

  // Update Lightweight Chart when candles or prediction change
  useEffect(() => {
    if (chartMode !== 'lightweight' || !candleSeriesRef.current || !volSeriesRef.current || candles.length === 0) return;
    
    // 1. Update Candles
    const candleData = candles.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close }));
    const volData = candles.map((c) => ({
      time: c.time, value: c.volume,
      color: c.close >= c.open ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)',
    }));
    candleSeriesRef.current.setData(candleData);
    volSeriesRef.current.setData(volData);

    // 2. Handle Price Projections (Dotted Lines)
    const series = candleSeriesRef.current;
    
    // Clear existing price lines (workaround as LW charts doesn't have a simple clear method for price lines)
    // We can't easily track them without a ref, so we'll use the API if possible or just let them stay if they match
    // Actually, we'll store them in a ref
    if ((series as any)._priceLines) {
        (series as any)._priceLines.forEach((l: any) => series.removePriceLine(l));
    }
    (series as any)._priceLines = [];

    const lastPrice = candles[candles.length - 1].close;
    const { prediction, botState } = useStore.getState();

    // Show projections if we have a signal or an open position
    const activePos = botState.open_positions.find(p => p.symbol === botState.symbol);
    
    if (activePos) {
        // Draw lines for open position
        const entryLine = series.createPriceLine({
            price: activePos.entry_price,
            color: '#6366f1',
            lineWidth: 2,
            lineStyle: 2, // Dashed
            axisLabelVisible: true,
            title: 'ENTRY',
        });
        const slLine = series.createPriceLine({
            price: activePos.stop_loss_price,
            color: '#ef4444',
            lineWidth: 1,
            lineStyle: 1, // Dotted
            axisLabelVisible: true,
            title: 'STOP LOSS',
        });
        const tpLine = series.createPriceLine({
            price: activePos.take_profit_price,
            color: '#10b981',
            lineWidth: 1,
            lineStyle: 1, // Dotted
            axisLabelVisible: true,
            title: 'TAKE PROFIT',
        });
        (series as any)._priceLines.push(entryLine, slLine, tpLine);
    } else if (prediction && prediction.direction !== 'NEUTRAL') {
        // Draw projections for current signal
        const isBuy = prediction.direction === 'BUY';
        const slPct = prediction.stop_loss_pct || 2;
        const tpPct = prediction.take_profit_pct || 4;
        
        const slPrice = isBuy ? lastPrice * (1 - slPct/100) : lastPrice * (1 + slPct/100);
        const tpPrice = isBuy ? lastPrice * (1 + tpPct/100) : lastPrice * (1 - tpPct/100);

        const slLine = series.createPriceLine({
            price: slPrice,
            color: '#ef4444',
            lineWidth: 1,
            lineStyle: 1, // Dotted
            axisLabelVisible: true,
            title: 'PROJ. EXIT (SL)',
        });
        const tpLine = series.createPriceLine({
            price: tpPrice,
            color: '#10b981',
            lineWidth: 1,
            lineStyle: 1, // Dotted
            axisLabelVisible: true,
            title: 'PROJ. TARGET (TP)',
        });
        (series as any)._priceLines.push(slLine, tpLine);
    }

    chartRef.current?.timeScale().fitContent();
  }, [candles, chartMode, prediction, botState.open_positions]);

  return (
    <div className="chart-container animate-in">
      <div className="chart-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontWeight: 700, fontSize: 15 }}>{botState.symbol}</span>
          <div className="tab-pill-container" style={{ display: 'flex', background: 'var(--bg-base)', padding: 2, borderRadius: 6 }}>
            <button 
              onClick={() => setChartMode('lightweight')}
              style={{ padding: '4px 10px', fontSize: 11, borderRadius: 4, background: chartMode === 'lightweight' ? 'var(--bg-card)' : 'transparent', border: 'none', color: chartMode === 'lightweight' ? 'var(--text-primary)' : 'var(--text-muted)', cursor: 'pointer' }}
            >Simple</button>
            <button 
              onClick={() => setChartMode('tradingview')}
              style={{ padding: '4px 10px', fontSize: 11, borderRadius: 4, background: chartMode === 'tradingview' ? 'var(--bg-card)' : 'transparent', border: 'none', color: chartMode === 'tradingview' ? 'var(--text-primary)' : 'var(--text-muted)', cursor: 'pointer' }}
            >TradingView</button>
          </div>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 8 }}>
          {chartMode === 'lightweight' ? (candles.length === 0 ? '⏳ Waiting...' : '✅ Live Sync') : '📺 Advanced Widget'}
        </div>
      </div>
      
      {chartMode === 'lightweight' ? (
        <div ref={containerRef} style={{ height: 420, width: '100%' }} />
      ) : (
        <div id="tv_chart_container" ref={tvContainerRef} style={{ height: 420, width: '100%' }} />
      )}
    </div>
  );
}
