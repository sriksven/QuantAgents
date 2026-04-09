"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { Bell, Search, ArrowUpRight, ArrowDownRight, Activity, Plus, Trash2 } from "lucide-react"
import { cn } from "../../lib/utils"

const MOCK_WATCHLIST = [
  { symbol: "AAPL", price: 169.80, change: 1.2, alert: "Price > $175.00" },
  { symbol: "MSFT", price: 412.50, change: -0.5, alert: "RSI < 30" },
  { symbol: "NVDA", price: 890.50, change: 2.4, alert: "Earnings 5/22" },
  { symbol: "AMD", price: 175.20, change: 3.1, alert: "MACD Cross" },
  { symbol: "TSLA", price: 205.10, change: -1.2, alert: "IV Rank > 50" }
]

const MOCK_ALERTS = [
  { id: 1, type: "PRICE", symbol: "AAPL", condition: "Crosses Above", value: "$175.00", status: "ACTIVE" },
  { id: 2, type: "TECHNICAL", symbol: "MSFT", condition: "RSI Crosses Below", value: "30", status: "ACTIVE" },
  { id: 3, type: "ORDER", symbol: "NVDA", condition: "Limit Sell Executed", value: "100 shares", status: "TRIGGERED", time: "2h ago" },
  { id: 4, type: "SYSTEM", symbol: "SYSTEM", condition: "Monthly Model Retrain", value: "Completed", status: "TRIGGERED", time: "1d ago" },
]

export default function WatchlistPage() {
  const [query, setQuery] = useState("")

  return (
    <div className="min-h-full flex flex-col pt-4 max-w-[1600px] mx-auto w-full gap-6 pb-12">
      
      {/* Header */}
      <div className="flex flex-col mb-2">
        <h2 className="text-3xl font-bold tracking-tight text-white mb-1">Watchlist & Alerts</h2>
        <p className="text-slate-400">Track equities and configure market condition alerts</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Watchlist */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl flex flex-col min-h-[500px]">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Activity size={18} className="text-emerald-400" /> Live Quotes
            </h3>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
              <input 
                type="text" 
                placeholder="Add symbol..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="input-field w-full pl-10 h-9 text-sm"
              />
            </div>
          </div>

          <table className="w-full text-left">
            <thead className="text-xs text-slate-400 uppercase tracking-widest border-b border-white/5">
              <tr>
                <th className="pb-3 px-4 font-medium">Symbol</th>
                <th className="pb-3 px-4 font-medium text-right">Price</th>
                <th className="pb-3 px-4 font-medium text-right">Change %</th>
                <th className="pb-3 px-4 font-medium">Active Alert</th>
                <th className="pb-3 px-4 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {MOCK_WATCHLIST.map((item, i) => (
                <motion.tr 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  key={item.symbol} 
                  className="hover:bg-white/[0.02] group"
                >
                  <td className="py-4 px-4 font-bold text-white tracking-wider">{item.symbol}</td>
                  <td className="py-4 px-4 text-right font-mono text-slate-200">${item.price.toFixed(2)}</td>
                  <td className="py-4 px-4 text-right">
                    <span className={cn("inline-flex items-center justify-end font-semibold text-sm", item.change >= 0 ? "text-green-400" : "text-red-400")}>
                      {item.change >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                      {Math.abs(item.change)}%
                    </span>
                  </td>
                  <td className="py-4 px-4 text-sm text-slate-400 flex items-center gap-2">
                    <Bell size={12} className={item.alert ? "text-amber-400" : "text-slate-600"} />
                    {item.alert || "None"}
                  </td>
                  <td className="py-4 px-4 text-right">
                    <button className="text-slate-500 hover:text-red-400 transition-colors">
                      <Trash2 size={16} />
                    </button>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Alerts Center */}
        <div className="glass-panel p-6 rounded-2xl flex flex-col gap-6">
          <div className="flex items-center justify-between border-b border-white/5 pb-4">
            <h3 className="font-semibold text-white tracking-wide flex items-center gap-2">
              <Bell size={18} className="text-amber-400" /> System Alerts
            </h3>
            <button className="p-1.5 bg-indigo-500/20 text-indigo-400 rounded-md hover:bg-indigo-500/30 transition-colors">
              <Plus size={16} />
            </button>
          </div>

          <div className="space-y-4">
            {MOCK_ALERTS.map((alert) => (
              <div key={alert.id} className={cn("p-4 rounded-xl border transition-all", 
                alert.status === "ACTIVE" ? "bg-black/20 border-white/5" : "bg-white/5 border-white/10"
              )}>
                <div className="flex justify-between items-start mb-2">
                  <span className={cn("text-[10px] font-bold tracking-wider px-2 py-0.5 rounded", 
                    alert.type === "SYSTEM" ? "bg-purple-500/20 text-purple-400" :
                    alert.type === "ORDER" ? "bg-emerald-500/20 text-emerald-400" :
                    "bg-blue-500/20 text-blue-400"
                  )}>
                    {alert.type}
                  </span>
                  <span className={cn("text-[10px] font-bold tracking-wider", 
                    alert.status === "ACTIVE" ? "text-amber-400" : "text-slate-400"
                  )}>
                    {alert.time || alert.status}
                  </span>
                </div>
                
                <h4 className="font-semibold text-white tracking-wide">{alert.symbol !== "SYSTEM" ? alert.symbol : "QuantAgents Platform"}</h4>
                <p className="text-sm text-slate-400 mt-1">
                  {alert.condition} <strong className="text-slate-200">{alert.value}</strong>
                </p>
              </div>
            ))}
          </div>

        </div>

      </div>
    </div>
  )
}
