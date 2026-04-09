"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { TrendingUp, AlertCircle, ArrowUpRight, ArrowDownRight, DollarSign, Clock, Activity } from "lucide-react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import { cn } from "../../lib/utils"

// Mock Data
const MOCK_POSITIONS = [
  { symbol: "NVDA", shares: 45, avgPrice: 852.14, currentPrice: 890.50, pnl: 1726.20, pnlPct: 4.5 },
  { symbol: "AAPL", shares: 120, avgPrice: 172.40, currentPrice: 169.80, pnl: -312.00, pnlPct: -1.5 },
  { symbol: "TSLA", shares: 80, avgPrice: 195.20, currentPrice: 205.10, pnl: 792.00, pnlPct: 5.1 },
]

const MOCK_ORDERS = [
  { id: "ORD-1", symbol: "AMD", side: "BUY", type: "LIMIT", price: 175.50, status: "WORKING", time: "10:42 AM" },
  { id: "ORD-2", symbol: "NVDA", side: "SELL", type: "TAKE_PROFIT", price: 900.00, status: "WORKING", time: "09:30 AM" },
]

const MOCK_CHART_DATA = Array.from({ length: 50 }).map((_, i) => ({
  time: `10:${i.toString().padStart(2, '0')}`,
  price: 880 + Math.random() * 20 + Math.sin(i / 5) * 10
}))

export default function TradingTerminal() {
  const [ticker, setTicker] = useState("NVDA")
  const [orderSide, setOrderSide] = useState<"BUY" | "SELL">("BUY")
  const [shares, setShares] = useState(10)
  
  return (
    <div className="min-h-full flex flex-col pt-4 max-w-[1600px] mx-auto w-full gap-6">
      
      <div className="flex items-center justify-between mb-2">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-white mb-1">Trading Terminal</h2>
          <p className="text-slate-400">Execute trades and monitor Alpaca positions</p>
        </div>
        <div className="flex gap-4">
          <div className="glass-panel px-6 py-3 rounded-xl flex flex-col items-end">
            <span className="text-[10px] uppercase tracking-wider text-slate-400">Total Account Value</span>
            <span className="text-xl font-bold font-mono text-emerald-400">$124,592.50</span>
          </div>
          <div className="glass-panel px-6 py-3 rounded-xl flex flex-col items-end">
            <span className="text-[10px] uppercase tracking-wider text-slate-400">Buying Power</span>
            <span className="text-xl font-bold font-mono text-slate-200">$48,250.00</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Charting & Order Entry */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          
          {/* Main Chart */}
          <div className="glass-panel rounded-2xl p-6 h-[450px] flex flex-col relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 blur-[100px] rounded-full pointer-events-none" />
            
            <div className="flex justify-between items-start mb-6 z-10">
              <div className="flex items-center gap-4">
                <h3 className="text-2xl font-bold text-white tracking-widest">{ticker}</h3>
                <div className="px-2 py-1 bg-green-500/20 text-green-400 border border-green-500/30 rounded text-sm font-mono">
                  $890.50
                </div>
                <div className="text-green-400 text-sm flex items-center font-medium">
                  <ArrowUpRight size={16} /> +2.4% Today
                </div>
              </div>
              <div className="flex gap-2">
                {["1D", "1W", "1M", "3M", "YTD"].map(tf => (
                  <button key={tf} className="px-3 py-1 text-xs font-medium rounded bg-white/5 hover:bg-white/10 text-slate-300 transition-colors">
                    {tf}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex-1 w-full z-10">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={MOCK_CHART_DATA}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="time" stroke="rgba(255,255,255,0.2)" fontSize={12} tickMargin={10} />
                  <YAxis domain={['auto', 'auto']} stroke="rgba(255,255,255,0.2)" fontSize={12} width={60} tickFormatter={(val) => `$${val}`} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'rgba(17,17,24,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                    itemStyle={{ color: '#10b981' }}
                  />
                  <Line type="monotone" dataKey="price" stroke="#10b981" strokeWidth={2} dot={false} activeDot={{ r: 6, fill: '#10b981' }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Working Orders */}
          <div className="glass-panel rounded-2xl p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Clock size={18} className="text-amber-400" /> Working Orders
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-slate-400 uppercase border-b border-white/5">
                  <tr>
                    <th className="pb-3 font-medium">Symbol</th>
                    <th className="pb-3 font-medium">Side</th>
                    <th className="pb-3 font-medium">Type</th>
                    <th className="pb-3 font-medium text-right">Price</th>
                    <th className="pb-3 font-medium text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {MOCK_ORDERS.map((order) => (
                    <tr key={order.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-3 font-bold">{order.symbol}</td>
                      <td className="py-3">
                        <span className={cn("px-2 py-0.5 rounded text-[10px] font-bold tracking-wider", 
                          order.side === 'BUY' ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                        )}>
                          {order.side}
                        </span>
                      </td>
                      <td className="py-3 text-slate-300">{order.type}</td>
                      <td className="py-3 text-right font-mono">${order.price.toFixed(2)}</td>
                      <td className="py-3 text-right">
                        <span className="text-amber-400 text-xs flex items-center justify-end gap-1">
                          <Activity size={12} className="animate-pulse" /> {order.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        </div>

        {/* Right Column: Order Entry & Positions */}
        <div className="flex flex-col gap-6">
          
          {/* Order Entry */}
          <div className="glass-panel rounded-2xl p-6 relative overflow-hidden">
            <h3 className="text-lg font-semibold text-white mb-6">Quick Trade</h3>
            
            <div className="flex bg-black/40 p-1 rounded-lg mb-6">
              <button 
                onClick={() => setOrderSide("BUY")}
                className={cn("flex-1 py-2 text-sm font-bold rounded-md transition-all", 
                  orderSide === "BUY" ? "bg-green-500/20 text-green-400 shadow-[0_0_15px_rgba(16,185,129,0.2)]" : "text-slate-500 hover:text-slate-300"
                )}
              >
                BUY
              </button>
              <button 
                onClick={() => setOrderSide("SELL")}
                className={cn("flex-1 py-2 text-sm font-bold rounded-md transition-all", 
                  orderSide === "SELL" ? "bg-red-500/20 text-red-400 shadow-[0_0_15px_rgba(239,68,68,0.2)]" : "text-slate-500 hover:text-slate-300"
                )}
              >
                SELL
              </button>
            </div>

            <div className="space-y-4 mb-8">
              <div>
                <label className="text-xs text-slate-400 uppercase tracking-widest mb-1 block">Symbol</label>
                <div className="relative">
                  <input type="text" value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} className="input-field w-full font-bold tracking-wider" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-slate-400 uppercase tracking-widest mb-1 block">Shares</label>
                  <input type="number" value={shares} onChange={(e) => setShares(Number(e.target.value))} className="input-field w-full font-mono" />
                </div>
                <div>
                  <label className="text-xs text-slate-400 uppercase tracking-widest mb-1 block">Type</label>
                  <select className="input-field w-full appearance-none">
                    <option>MARKET</option>
                    <option>LIMIT</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="flex justify-between items-center py-4 border-t border-white/5 mb-6">
              <span className="text-sm text-slate-400">Estimated Total</span>
              <span className="text-xl font-mono text-white tracking-wider">~${(shares * 890.50).toLocaleString()}</span>
            </div>

            <button className={cn("w-full py-4 text-white font-bold tracking-widest text-lg rounded-xl transition-all shadow-[0_4px_20px_rgba(0,0,0,0.3)] hover:-translate-y-1",
              orderSide === "BUY" ? "bg-gradient-to-r from-green-600 to-green-500 hover:shadow-[0_0_25px_rgba(16,185,129,0.4)]" : "bg-gradient-to-r from-red-600 to-red-500 hover:shadow-[0_0_25px_rgba(239,68,68,0.4)]"
            )}>
              SUBMIT {orderSide}
            </button>
          </div>

          {/* Holdings */}
          <div className="glass-panel rounded-2xl p-6 flex-1">
            <h3 className="text-lg font-semibold text-white mb-4">Open Positions</h3>
            
            <div className="space-y-3">
              {MOCK_POSITIONS.map((pos) => (
                <div key={pos.symbol} className="p-4 rounded-xl bg-black/20 border border-white/5 hover:border-white/10 transition-colors group cursor-pointer">
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex flex-col">
                      <span className="font-bold text-white text-base">{pos.symbol}</span>
                      <span className="text-xs text-slate-400">{pos.shares} shares @ ${pos.avgPrice.toFixed(2)}</span>
                    </div>
                    <div className="flex flex-col items-end">
                      <span className="font-mono text-sm text-slate-200">${pos.currentPrice.toFixed(2)}</span>
                      <span className={cn("text-xs font-semibold flex items-center", pos.pnl >= 0 ? "text-green-400" : "text-red-400")}>
                        {pos.pnl >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                        ${Math.abs(pos.pnl).toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
