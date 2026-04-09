"use client"

import { motion } from "framer-motion"
import { TrendingUp, PieChart, Activity, DollarSign, Target, Award } from "lucide-react"
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Line } from "recharts"

// Mock Data
const PORTFOLIO_HISTORY = Array.from({ length: 90 }).map((_, i) => ({
  date: `Day ${i + 1}`,
  portfolio: 100000 * (1 + (i * 0.002) + Math.sin(i / 10) * 0.05),
  spy: 100000 * (1 + (i * 0.001) + Math.sin(i / 15) * 0.02)
}))

const ALLOCATIONS = [
  { sector: "Technology", percent: 45, color: "bg-indigo-500" },
  { sector: "Healthcare", percent: 20, color: "bg-emerald-500" },
  { sector: "Consumer", percent: 15, color: "bg-amber-500" },
  { sector: "Energy", percent: 10, color: "bg-red-500" },
  { sector: "Cash", percent: 10, color: "bg-slate-500" },
]

export default function PortfolioDashboard() {
  return (
    <div className="min-h-full flex flex-col pt-4 max-w-[1600px] mx-auto w-full gap-6 pb-12">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-4 gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-white mb-1">Portfolio Dashboard</h2>
          <p className="text-slate-400">Quantum-optimized asset allocation & performance metrics</p>
        </div>
        
        <div className="flex bg-black/40 p-1 rounded-lg self-start">
          {["1W", "1M", "3M", "YTD", "1Y", "ALL"].map((tf, i) => (
            <button key={tf} className={`px-4 py-1.5 text-sm font-semibold rounded-md transition-all ${i === 2 ? 'bg-indigo-500/20 text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.2)]' : 'text-slate-500 hover:text-slate-300'}`}>
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[
          { label: "Net Asset Value", value: "$124,592.50", sub: "+24.5% YTD", icon: DollarSign, color: "text-emerald-400", bg: "bg-emerald-500/10" },
          { label: "Alpha (vs SPY)", value: "+8.2%", sub: "Quantum Edge", icon: Award, color: "text-indigo-400", bg: "bg-indigo-500/10" },
          { label: "Sharpe Ratio", value: "2.84", sub: "Risk-adjusted", icon: Target, color: "text-amber-400", bg: "bg-amber-500/10" },
          { label: "Max Drawdown", value: "-4.2%", sub: "90-day rolling", icon: Activity, color: "text-red-400", bg: "bg-red-500/10" }
        ].map((kpi, i) => (
          <div key={i} className="glass-panel p-6 rounded-2xl flex items-center gap-5">
            <div className={`p-4 rounded-xl ${kpi.bg}`}>
              <kpi.icon size={24} className={kpi.color} />
            </div>
            <div>
              <p className="text-sm text-slate-400 font-medium">{kpi.label}</p>
              <p className="text-2xl font-bold text-white tracking-wide font-mono mt-1">{kpi.value}</p>
              <p className={`text-xs mt-1 ${kpi.color}`}>{kpi.sub}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Equity Curve Chart */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl flex flex-col h-[500px]">
          <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
            <TrendingUp size={18} className="text-indigo-400" /> Performance History
          </h3>
          <div className="flex-1 w-full relative">
            <div className="absolute top-0 left-0 w-full h-full bg-indigo-500/5 blur-[100px] rounded-full pointer-events-none" />
            
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={PORTFOLIO_HISTORY}>
                <defs>
                  <linearGradient id="colorPort" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="date" stroke="rgba(255,255,255,0.2)" fontSize={12} tickMargin={10} minTickGap={30} />
                <YAxis domain={['auto', 'auto']} stroke="rgba(255,255,255,0.2)" fontSize={12} width={80} tickFormatter={(val) => `$${(val/1000).toFixed(0)}k`} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'rgba(17,17,24,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                  itemStyle={{ color: '#fff', fontSize: '13px' }}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  formatter={(val: any) => [`$${Number(val).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, undefined]}
                />
                {/* SPY Benchmark underneath */}
                <Line type="monotone" dataKey="spy" name="SPY Benchmark" stroke="rgba(255,255,255,0.2)" strokeWidth={2} dot={false} strokeDasharray="5 5" />
                {/* Portfolio Equity Curve */}
                <Area type="monotone" dataKey="portfolio" name="QuantAgents Portfolio" stroke="#8b5cf6" strokeWidth={3} fillOpacity={1} fill="url(#colorPort)" activeDot={{ r: 6, fill: '#8b5cf6', stroke: '#fff', strokeWidth: 2 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Allocation Sidebar */}
        <div className="flex flex-col gap-6">
          
          <div className="glass-panel p-6 rounded-2xl flex-1">
            <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
              <PieChart size={18} className="text-emerald-400" /> Sector Allocation
            </h3>
            
            <div className="space-y-5">
              {ALLOCATIONS.map((alloc) => (
                <div key={alloc.sector}>
                  <div className="flex justify-between items-end mb-2">
                    <span className="text-sm font-medium text-slate-200">{alloc.sector}</span>
                    <span className="text-sm text-slate-400 font-mono">{alloc.percent}%</span>
                  </div>
                  <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                    <motion.div 
                      initial={{ width: 0 }}
                      animate={{ width: `${alloc.percent}%` }}
                      transition={{ duration: 1, ease: "easeOut" }}
                      className={`h-full rounded-full ${alloc.color}`} 
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-8 p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-xl">
              <h4 className="text-xs text-indigo-400 font-bold uppercase tracking-wider mb-2">Quantum Optimizer</h4>
              <p className="text-[13px] text-indigo-300/80 leading-relaxed">
                QAOA detected high sector correlation risk. Healthcare exposure automatically reduced by 4.2% to rebalance the efficient frontier.
              </p>
            </div>
          </div>
          
        </div>

      </div>
    </div>
  )
}
