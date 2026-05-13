import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'BitBot — AI Crypto Trading Bot',
  description: 'Intelligent AI-powered cryptocurrency trading bot with real-time chart analysis, multi-indicator signals, and automated execution.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
