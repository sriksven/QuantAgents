import { useState } from 'react';

export default function VirtualPortfolio({ 
  portfolio, 
  loading,
  onFundSuccess
}: { 
  portfolio: { cash_balance: number, positions: any[] } | null, 
  loading: boolean,
  onFundSuccess?: () => void
}) {
  const [fundAmount, setFundAmount] = useState<string>('10000');
  const [isFunding, setIsFunding] = useState(false);

  const handleFund = async () => {
    const amount = parseFloat(fundAmount);
    if (isNaN(amount) || amount <= 0) return;
    
    setIsFunding(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/mock-trade/fund`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount })
      });
      if (res.ok && onFundSuccess) onFundSuccess();
    } catch (e) {
      console.error("Funding error", e);
    }
    setIsFunding(false);
  };
  if (loading || !portfolio) {
    return (
      <div className="glass-panel p-6 h-64 flex items-center justify-center">
        <div className="animate-pulse text-slate-400 font-medium">Loading Portfolio...</div>
      </div>
    );
  }

  // Calculate total portfolio value roughly (assuming positions entry price is roughly current price for display, unless we poll later)
  const holdingsValue = portfolio.positions.reduce((acc, p) => acc + (p.qty * p.average_entry_price), 0);
  const totalValue = portfolio.cash_balance + holdingsValue;

  return (
    <div className="glass-panel p-6 h-full flex flex-col">
      <h2 className="text-xl font-bold text-white mb-6 border-b border-white/10 pb-2">Virtual Ledger</h2>
      
      <div className="grid grid-cols-2 gap-4 mb-8">
        <div className="bg-white/5 p-4 rounded-xl border border-white/5 flex flex-col justify-between">
          <div>
            <p className="text-slate-400 text-sm mb-1 font-medium">Available Cash</p>
            <p className="text-3xl font-mono text-white mb-3">${portfolio.cash_balance.toFixed(2)}</p>
          </div>
          <div className="flex items-center gap-2 mt-auto">
            <input 
              type="number" 
              value={fundAmount} 
              onChange={e => setFundAmount(e.target.value)}
              className="px-2 py-1 bg-black/30 border border-white/10 rounded text-sm w-24 text-white focus:outline-none focus:border-emerald-500 transition-colors"
            />
            <button 
              onClick={handleFund}
              disabled={isFunding}
              className="glow-btn text-xs px-3 py-1.5 disabled:opacity-50"
            >
              Add Funds
            </button>
          </div>
        </div>
        <div className="bg-white/5 p-4 rounded-xl border border-white/5 flex flex-col justify-between">
          <div>
            <p className="text-slate-400 text-sm mb-1 font-medium">Total Account Value</p>
            <p className="text-3xl font-mono text-emerald-400">${totalValue.toFixed(2)}</p>
          </div>
        </div>
      </div>

      <h3 className="text-lg font-semibold text-slate-300 mb-4">Open Positions</h3>
      
      <div className="flex-1 overflow-auto rounded-xl border border-white/5 bg-black/20">
        {portfolio.positions.length === 0 ? (
          <div className="text-center py-10 text-slate-500">
            No open positions. Use the terminal to place a mock trade.
          </div>
        ) : (
          <table className="w-full text-left">
            <thead className="bg-white/5">
              <tr className="text-slate-400 border-b border-white/10 text-sm">
                <th className="py-3 px-4 font-medium">Ticker</th>
                <th className="py-3 px-4 font-medium text-right">Shares</th>
                <th className="py-3 px-4 font-medium text-right">Avg Entry</th>
                <th className="py-3 px-4 font-medium text-right">Total Invested</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {portfolio.positions.map((pos, idx) => (
                <tr key={idx} className="hover:bg-white/5 transition-colors">
                  <td className="py-4 px-4 font-bold text-white">{pos.ticker}</td>
                  <td className="py-4 px-4 text-slate-300 text-right font-mono">{pos.qty}</td>
                  <td className="py-4 px-4 text-slate-300 text-right font-mono">${pos.average_entry_price.toFixed(2)}</td>
                  <td className="py-4 px-4 text-white text-right font-mono font-medium">${(pos.qty * pos.average_entry_price).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
