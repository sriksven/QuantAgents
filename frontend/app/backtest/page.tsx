"use client"

import { useState } from "react"
import { Play, Settings2, BarChart2, Cpu } from "lucide-react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import { cn } from "../../lib/utils"

// Generate 5 random drift paths
const PATHS = 5
const DAYS = 30
const START_PRICE = 100

const MOCK_MONTE_CARLO = Array.from({ length: DAYS }).map((_, day) => {
  const result: Record<string, string | number> = { day: `Day ${day}` }
  for (let p = 0; p < PATHS; p++) {
    // Random walk with slight upward drift
    const prev = day === 0 ? START_PRICE : (MOCK_MONTE_CARLO[day - 1][`path${p}`] as number)
    result[`path${p}`] = prev * (1 + (Math.random() - 0.45) * 0.04)
  }
  return result
})

const PATH_COLORS = ["#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#06b6d4"]

export default function BacktestLab() {
  const [isRunning, setIsRunning] = useState(false)
  const hasResults = true

  const handleRun = () => {
    setIsRunning(true)
    setTimeout(() => setIsRunning(false), 2000)
  }

  return (
    <div className="min-h-full flex flex-col pt-4 max-w-[1600px] mx-auto w-full gap-6 pb-12">
      
      {/* Header */}
      <div className="flex flex-col mb-2">
        <h2 className="text-3xl font-bold tracking-tight text-white mb-1">Backtest Lab</h2>
        <p className="text-slate-400">Monte Carlo simulations via the VectorBT backtesting engine</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        
        {/* Controls Sidebar */}
        <div className="glass-panel p-6 rounded-2xl flex flex-col gap-6">
          <div className="flex items-center gap-2 border-b border-white/5 pb-4">
            <Settings2 className="text-indigo-400" size={20} />
            <h3 className="font-semibold text-white tracking-wide">Parameters</h3>
          </div>

          <div className="space-y-5">
            <div>
              <label className="text-xs text-slate-400 uppercase tracking-widest mb-2 block">Strategy</label>
              <select className="input-field w-full appearance-none">
                <option>Multi-Agent Ensemble</option>
                <option>Mean Reversion (Bollinger)</option>
                <option>Momentum (MACD)</option>
                <option>Options Strat (Iron Condor)</option>
              </select>
            </div>
            
            <div>
              <label className="text-xs text-slate-400 uppercase tracking-widest mb-2 block">Asset Universe</label>
              <input type="text" defaultValue="SPY, QQQ, AAPL, MSFT" className="input-field w-full" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 uppercase tracking-widest mb-2 block">Initial Cap</label>
                <input type="text" defaultValue="$100k" className="input-field w-full" />
              </div>
              <div>
                <label className="text-xs text-slate-400 uppercase tracking-widest mb-2 block">Timeframe</label>
                <select className="input-field w-full appearance-none">
                  <option>1 Year</option>
                  <option>3 Years</option>
                  <option>5 Years</option>
                </select>
              </div>
            </div>

            <div>
              <label className="text-xs text-slate-400 uppercase tracking-widest mb-2 block flex justify-between">
                <span>Monte Carlo Paths</span>
                <span className="text-indigo-400 font-mono">1,000</span>
              </label>
              <input type="range" className="w-full accent-indigo-500" min="100" max="5000" defaultValue="1000" />
            </div>
          </div>

          <button 
            onClick={handleRun}
            disabled={isRunning}
            className="glow-btn mt-4 w-full flex items-center justify-center gap-2 py-3 rounded-xl shadow-[0_4px_20px_rgba(0,0,0,0.3)]"
          >
            {isRunning ? (
              <Cpu size={18} className="animate-pulse" />
            ) : (
              <Play size={18} />
            )}
            {isRunning ? "Simulating..." : "Run Backtest"}
          </button>
        </div>

        {/* Results Area */}
        <div className="lg:col-span-3 flex flex-col gap-6">
          
          {hasResults ? (
            <>
              {/* Monte Carlo Chart */}
              <div className="glass-panel p-6 rounded-2xl h-[400px] flex flex-col relative overflow-hidden">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-indigo-500/10 blur-[100px] rounded-full pointer-events-none" />
                
                <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2 z-10">
                  <BarChart2 size={18} className="text-indigo-400" /> Monte Carlo Equity Paths (Sample)
                </h3>
                
                <div className="flex-1 w-full z-10">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={MOCK_MONTE_CARLO}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                      <XAxis dataKey="day" stroke="rgba(255,255,255,0.2)" fontSize={12} tickMargin={10} minTickGap={5} />
                      <YAxis domain={['auto', 'auto']} stroke="rgba(255,255,255,0.2)" fontSize={12} width={60} tickFormatter={(val) => `$${val.toFixed(0)}`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: 'rgba(17,17,24,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                        itemStyle={{ fontSize: '12px' }}
                      />
                      {Array.from({ length: PATHS }).map((_, p) => (
                        <Line key={p} type="monotone" dataKey={`path${p}`} stroke={PATH_COLORS[p]} strokeWidth={1} dot={false} strokeOpacity={0.8} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: "Expected Return", value: "+18.4%", color: "text-emerald-400" },
                  { label: "Win Rate", value: "62.5%", color: "text-white" },
                  { label: "Profit Factor", value: "1.85", color: "text-white" },
                  { label: "Max Drawdown", value: "-14.2%", color: "text-red-400" },
                  { label: "Sharpe Ratio", value: "1.95", color: "text-amber-400" },
                  { label: "Sortino Ratio", value: "2.41", color: "text-amber-400" },
                  { label: "Alpha", value: "6.2%", color: "text-indigo-400" },
                  { label: "Beta", value: "0.85", color: "text-slate-300" }
                ].map((stat, i) => (
                  <div key={i} className="glass-panel p-4 rounded-xl flex flex-col justify-center items-center text-center">
                    <span className="text-xs text-slate-400 uppercase tracking-wider mb-1">{stat.label}</span>
                    <span className={cn("text-xl font-bold font-mono tracking-wide", stat.color)}>{stat.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="glass-panel rounded-2xl flex-1 flex flex-col items-center justify-center text-slate-500 min-h-[500px]">
              <Cpu size={48} className="opacity-20 mb-4" />
              <p>Configure parameters and run simulation.</p>
            </div>
          )}

        </div>

      </div>
    </div>
  )
}
