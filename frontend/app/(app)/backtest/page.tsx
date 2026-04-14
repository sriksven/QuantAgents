"use client"

import { useState } from "react"
import { Play, BarChart2, Cpu } from "lucide-react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import { cn } from "@/lib/utils"

const PATHS = 5
const DAYS  = 30

const MONTE_CARLO: Record<string, string | number>[] = []
for (let d = 0; d < DAYS; d++) {
  const row: Record<string, string | number> = { day: `D${d + 1}` }
  for (let p = 0; p < PATHS; p++) {
    const prev = d === 0 ? 100 : (MONTE_CARLO[d - 1][`p${p}`] as number)
    row[`p${p}`] = +(prev * (1 + (Math.random() - 0.45) * 0.04)).toFixed(2)
  }
  MONTE_CARLO.push(row)
}

const PATH_COLORS = ["#3b82f6", "#22c55e", "#fbbf24", "#f87171", "#a78bfa"]

const STATS = [
  { label: "Expected Return", value: "+18.4%", color: "var(--green)"  },
  { label: "Win Rate",         value: "62.5%",  color: "var(--text)"   },
  { label: "Profit Factor",    value: "1.85",   color: "var(--text)"   },
  { label: "Max Drawdown",     value: "−14.2%", color: "var(--red)"    },
  { label: "Sharpe Ratio",     value: "1.95",   color: "var(--amber)"  },
  { label: "Sortino Ratio",    value: "2.41",   color: "var(--amber)"  },
  { label: "Alpha",            value: "+6.2%",  color: "var(--accent)" },
  { label: "Beta",             value: "0.85",   color: "var(--text-2)" },
]

export default function BacktestLab() {
  const [running, setRunning] = useState(false)

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto" }}>

      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 18, fontWeight: 600, color: "var(--text)", letterSpacing: "-0.02em" }}>
          Backtest Lab
        </h1>
        <p style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3 }}>
          Monte Carlo simulation via VectorBT backtesting engine
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 16 }}>

        {/* Parameters panel */}
        <div className="card" style={{ padding: 16, alignSelf: "start" }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", marginBottom: 14 }}>
            Parameters
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label className="field-label">Strategy</label>
              <select className="input-field">
                <option>Multi-Agent Ensemble</option>
                <option>Mean Reversion (Bollinger)</option>
                <option>Momentum (MACD)</option>
                <option>Iron Condor</option>
              </select>
            </div>
            <div>
              <label className="field-label">Asset Universe</label>
              <input className="input" defaultValue="SPY, QQQ, AAPL, MSFT" />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <div>
                <label className="field-label">Initial Cap</label>
                <input className="input input-mono" defaultValue="$100k" />
              </div>
              <div>
                <label className="field-label">Timeframe</label>
                <select className="input-field">
                  <option>1 Year</option>
                  <option>3 Years</option>
                  <option>5 Years</option>
                </select>
              </div>
            </div>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                <label className="field-label" style={{ margin: 0 }}>MC Paths</label>
                <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--accent)" }}>1,000</span>
              </div>
              <input type="range" style={{ width: "100%", accentColor: "var(--accent)" }} min="100" max="5000" defaultValue="1000" />
            </div>
          </div>

          <button
            className="btn btn-primary"
            style={{ width: "100%", justifyContent: "center", marginTop: 16 }}
            onClick={() => { setRunning(true); setTimeout(() => setRunning(false), 2000) }}
            disabled={running}
          >
            {running ? <Cpu size={13} style={{ animation: "spin 1s linear infinite" }} /> : <Play size={13} />}
            {running ? "Simulating…" : "Run Backtest"}
          </button>
        </div>

        {/* Results */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Monte Carlo chart */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 14 }}>
              <BarChart2 size={13} style={{ color: "var(--accent)" }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text)" }}>
                Monte Carlo Equity Paths
              </span>
              <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-3)" }}>
                {PATHS} sample paths shown
              </span>
            </div>
            <div style={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={MONTE_CARLO} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="day" stroke="var(--text-3)" fontSize={10} tickMargin={8} minTickGap={5} />
                  <YAxis stroke="var(--text-3)" fontSize={10} width={44} tickFormatter={(v) => `$${v}`} />
                  <Tooltip
                    contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--border-2)", borderRadius: 5, fontSize: 11 }}
                    itemStyle={{ fontSize: 11 }}
                  />
                  {Array.from({ length: PATHS }).map((_, i) => (
                    <Line key={i} type="monotone" dataKey={`p${i}`} stroke={PATH_COLORS[i]}
                      strokeWidth={1.2} dot={false} strokeOpacity={0.85} name={`Path ${i + 1}`} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Stats grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
            {STATS.map((s) => (
              <div key={s.label} className="stat-card">
                <div className="stat-label">{s.label}</div>
                <div className="stat-value" style={{ fontSize: 16, color: s.color }}>{s.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
