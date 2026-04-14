'use client';

import { useState, useEffect } from 'react';
import TradingTerminal from '@/components/sandbox/TradingTerminal';
import VirtualPortfolio from '@/components/sandbox/VirtualPortfolio';

export default function MockTradingSandbox() {
  const [portfolio, setPortfolio] = useState<{ cash_balance: number; positions: any[] } | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchPortfolio = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/mock-trade/portfolio`);
      if (res.ok) setPortfolio(await res.json());
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchPortfolio(); }, []);

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>

      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 18, fontWeight: 600, color: "var(--text)", letterSpacing: "-0.02em" }}>
          Mock Trading
        </h1>
        <p style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3 }}>
          Isolated paper trading ledger — real-time prices, fake money, no impact on AI agents
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 16, alignItems: "start" }}>
        <TradingTerminal onOrderSuccess={fetchPortfolio} />
        <div style={{ height: 560 }}>
          <VirtualPortfolio portfolio={portfolio} loading={loading} onFundSuccess={fetchPortfolio} />
        </div>
      </div>
    </div>
  );
}
