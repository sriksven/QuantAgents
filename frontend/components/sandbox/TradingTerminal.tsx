'use client';

import { useState, useEffect } from 'react';

export default function TradingTerminal({ onOrderSuccess }: { onOrderSuccess: () => void }) {
  const [ticker, setTicker] = useState('AAPL');
  const [price, setPrice] = useState<number | null>(null);
  const [qty, setQty] = useState(1);
  const [side, setSide] = useState('BUY');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchQuote = async () => {
    if (!ticker) return;
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/mock-trade/quote/${encodeURIComponent(ticker.trim())}`);
      if (!res.ok) return;
      const data = await res.json();
      setPrice(data.price);
      setError('');
    } catch (err) {
      console.error(err);
    }
  };

  // Poll quote every 5 seconds
  useEffect(() => {
    fetchQuote();
    const interval = setInterval(fetchQuote, 5000);
    return () => clearInterval(interval);
  }, [ticker]);

  const placeOrder = async () => {
    if (!price || !Number.isInteger(qty) || qty <= 0) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/mock-trade/order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: ticker.toUpperCase(), side, qty, price })
      });
      const data = await res.json();
      
      if (!res.ok) {
        setError(data.detail || 'Failed to place order');
      } else {
        onOrderSuccess();
      }
    } catch (err: any) {
      setError(err.message);
    }
    setLoading(false);
  };

  return (
    <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl p-6 flex flex-col gap-4 shadow-xl">
      <h2 className="text-xl font-bold text-white">Trading Terminal</h2>
      
      {error && <div className="bg-red-500/20 text-red-300 p-3 rounded-lg text-sm">{error}</div>}
      
      <div>
        <label className="text-gray-400 text-sm mb-1 block">Ticker Symbol</label>
        <input 
          type="text" 
          value={ticker} 
          onChange={e => setTicker(e.target.value.toUpperCase())}
          className="w-full bg-black/30 border border-white/10 rounded-lg p-3 text-white font-mono uppercase focus:outline-none focus:border-purple-500 transition-colors"
          placeholder="AAPL"
        />
      </div>

      <div className="flex justify-between items-center bg-black/20 p-4 rounded-xl border border-white/5">
        <span className="text-gray-400">Live Price</span>
        <span className="text-3xl font-bold text-green-400 font-mono">
          {price !== null ? `$${price.toFixed(2)}` : '---'}
        </span>
      </div>

      <div className="flex gap-4">
        <div className="flex-1">
          <label className="text-gray-400 text-sm mb-1 block">Action</label>
          <div className="flex gap-2">
            <button 
              onClick={() => setSide('BUY')}
              className={`flex-1 py-3 rounded-lg font-bold transition-all ${side === 'BUY' ? 'bg-green-500 text-black' : 'bg-black/30 text-gray-400 hover:bg-black/50'}`}
            >
              BUY
            </button>
            <button 
              onClick={() => setSide('SELL')}
              className={`flex-1 py-3 rounded-lg font-bold transition-all ${side === 'SELL' ? 'bg-red-500 text-black' : 'bg-black/30 text-gray-400 hover:bg-black/50'}`}
            >
              SELL
            </button>
          </div>
        </div>
        <div className="w-1/3">
          <label className="text-gray-400 text-sm mb-1 block">Quantity</label>
          <input 
            type="number" 
            value={qty} 
            onChange={e => setQty(Number(e.target.value))}
            min="1"
            className="w-full bg-black/30 border border-white/10 rounded-lg p-3 text-white focus:outline-none focus:border-purple-500"
          />
        </div>
      </div>

      <div className="pt-4 border-t border-white/10 mt-2">
        <div className="flex justify-between mb-4">
          <span className="text-gray-400">Estimated Total</span>
          <span className="text-white font-mono">
            {price !== null ? `$${(price * qty).toFixed(2)}` : '---'}
          </span>
        </div>
        
        <button 
          onClick={placeOrder}
          disabled={loading || price === null}
          className="w-full bg-purple-600 hover:bg-purple-500 active:bg-purple-700 disabled:opacity-50 text-white font-bold py-4 rounded-xl transition-colors"
        >
          {loading ? 'Processing...' : `Place ${side} Order`}
        </button>
      </div>
    </div>
  );
}
