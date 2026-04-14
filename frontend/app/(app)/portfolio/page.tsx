"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { TrendingUp } from "lucide-react"
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Line } from "recharts"

const HISTORY = Array.from({ length: 90 }).map((_, i) => ({
  d: `D${i + 1}`,
  portfolio: +(100000 * (1 + i * 0.002 + Math.sin(i / 10) * 0.05)).toFixed(0),
  spy:        +(100000 * (1 + i * 0.001 + Math.sin(i / 15) * 0.02)).toFixed(0),
}))

const ALLOCATIONS = [
  { sector: "Technology",  pct: 45, color: "#3b82f6" },
  { sector: "Healthcare",  pct: 20, color: "#22c55e" },
  { sector: "Consumer",    pct: 15, color: "#fbbf24" },
  { sector: "Energy",      pct: 10, color: "#f87171" },
  { sector: "Cash",        pct: 10, color: "#404040"  },
]

const STATS = [
  { label: "Net Asset Value", value: "$124,592.50", sub: "+24.5% YTD",      color: "var(--green)"  },
  { label: "Alpha vs SPY",    value: "+8.2%",        sub: "Quantum edge",    color: "var(--accent)" },
  { label: "Sharpe Ratio",    value: "2.84",          sub: "Risk-adjusted",  color: "var(--amber)"  },
  { label: "Max Drawdown",    value: "−4.2%",         sub: "90-day rolling", color: "var(--red)"    },
]

const TFS = ["1W", "1M", "3M", "YTD", "1Y", "ALL"]

export default function PortfolioDashboard() {
  const [tf, setTf] = useState("3M")

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto" }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 600, color: "var(--text)", letterSpacing: "-0.02em" }}>
            Portfolio
          </h1>
          <p style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3 }}>
            Quantum-optimized allocation &amp; performance attribution
          </p>
        </div>
        <div style={{ display: "flex", gap: 3 }}>
          {TFS.map((t) => (
            <button
              key={t}
              onClick={() => setTf(t)}
              style={{
                padding: "5px 12px", borderRadius: 4, fontSize: 11, fontWeight: 500,
                background: tf === t ? "var(--surface-3)" : "transparent",
                color: tf === t ? "var(--text)" : "var(--text-2)",
                border: `1px solid ${tf === t ? "var(--border-2)" : "transparent"}`,
                cursor: "pointer", transition: "all 0.15s",
              }}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* KPI row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        {STATS.map((s) => (
          <div key={s.label} className="stat-card">
            <div className="stat-label">{s.label}</div>
            <div className="stat-value" style={{ color: s.color }}>{s.value}</div>
            <div className="stat-sub">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Chart + Allocation */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16 }}>

        {/* Equity curve */}
        <div className="card" style={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 16 }}>
            <TrendingUp size={13} style={{ color: "var(--accent)" }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text)" }}>Performance History</span>
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
              <span style={{ fontSize: 11, color: "var(--text-2)", display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 20, height: 2, background: "var(--accent)", display: "inline-block", borderRadius: 1 }} />
                Portfolio
              </span>
              <span style={{ fontSize: 11, color: "var(--text-2)", display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 20, height: 2, background: "var(--border-2)", display: "inline-block", borderRadius: 1, borderTop: "1px dashed var(--border-2)", background: "transparent", borderBottom: "none", borderLeft: "none", borderRight: "none" }} />
                SPY
              </span>
            </div>
          </div>
          <div style={{ height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={HISTORY} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="gPort" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor="#3b82f6" stopOpacity={0.15} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0}    />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="d" stroke="var(--text-3)" fontSize={10} tickMargin={8} minTickGap={30} />
                <YAxis stroke="var(--text-3)" fontSize={10} width={60} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--border-2)", borderRadius: 5, fontSize: 11 }}
                  formatter={(v: any) => [`$${Number(v).toLocaleString()}`, undefined]}
                  labelStyle={{ color: "var(--text-2)" }}
                />
                <Line type="monotone" dataKey="spy" stroke="var(--border-2)" strokeWidth={1} dot={false} strokeDasharray="4 3" name="SPY" />
                <Area type="monotone" dataKey="portfolio" stroke="var(--accent)" strokeWidth={1.5} fill="url(#gPort)" dot={false} name="Portfolio" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Allocation */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", marginBottom: 16 }}>
              Sector Allocation
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {ALLOCATIONS.map((a) => (
                <div key={a.sector}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                    <span style={{ fontSize: 12, color: "var(--text-2)" }}>{a.sector}</span>
                    <span style={{ fontSize: 11, fontFamily: "JetBrains Mono, monospace", color: "var(--text)" }}>{a.pct}%</span>
                  </div>
                  <div style={{ height: 3, background: "var(--surface-3)", borderRadius: 2, overflow: "hidden" }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${a.pct}%` }}
                      transition={{ duration: 0.8, ease: "easeOut" }}
                      style={{ height: "100%", background: a.color, borderRadius: 2 }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card" style={{ padding: 14 }}>
            <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--accent)", marginBottom: 8 }}>
              Quantum Optimizer
            </div>
            <p style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.6 }}>
              QAOA detected high sector correlation risk. Healthcare exposure reduced by 4.2% to rebalance the efficient frontier.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
