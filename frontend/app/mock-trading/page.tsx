'use client';

import { useState, useEffect } from 'react';
import TradingTerminal from '@/components/sandbox/TradingTerminal';
import VirtualPortfolio from '@/components/sandbox/VirtualPortfolio';

export default function MockTradingSandbox() {
  const [portfolio, setPortfolio] = useState<{ cash_balance: number, positions: any[] } | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchPortfolio = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/mock-trade/portfolio`);
      if (res.ok) {
        const data = await res.json();
        setPortfolio(data);
      }
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchPortfolio();
  }, []);

  const handleOrderSuccess = () => {
    // Refresh portfolio instantly after a trade
    fetchPortfolio();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-[#0a0a0f] to-black p-8 font-sans">
      <div className="max-w-7xl mx-auto">
        <header className="mb-10">
          <h1 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-500 mb-2">
            Mock Trading Sandbox
          </h1>
          <p className="text-slate-400">
            Isolated local paper trading ledger. Trade with fake money using real-time market data without interfering with AI Agents.
          </p>
        </header>

        <div className="flex flex-col lg:flex-row gap-8 items-stretch h-full">
          {/* Left Column: Trading Terminal Component */}
          <div className="w-full lg:w-1/3">
            <TradingTerminal onOrderSuccess={handleOrderSuccess} />
          </div>

          {/* Right Column: Portfolio Ledger Component */}
          <div className="w-full lg:w-2/3 h-[600px]">
            <VirtualPortfolio portfolio={portfolio} loading={loading} onFundSuccess={handleOrderSuccess} />
          </div>
        </div>
      </div>
    </div>
  );
}
