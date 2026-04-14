"use client"

import { useState } from "react"
import { ArrowUpRight, ArrowDownRight, Activity } from "lucide-react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import { cn } from "@/lib/utils"

const MOCK_POSITIONS = [
  { symbol: "NVDA", shares: 45, avgPrice: 852.14, currentPrice: 890.50, pnl: 1726.20, pnlPct: 4.5 },
  { symbol: "AAPL", shares: 120, avgPrice: 172.40, currentPrice: 169.80, pnl: -312.00, pnlPct: -1.5 },
  { symbol: "TSLA", shares: 80, avgPrice: 195.20, currentPrice: 205.10, pnl: 792.00, pnlPct: 5.1 },
]

const MOCK_ORDERS = [
  { id: "ORD-001", symbol: "AMD",  side: "BUY",  type: "LIMIT",       price: 175.50, qty: 50,  status: "WORKING" },
  { id: "ORD-002", symbol: "NVDA", side: "SELL", type: "TAKE_PROFIT", price: 900.00, qty: 20,  status: "WORKING" },
]

const CHART_DATA = Array.from({ length: 50 }).map((_, i) => ({
  t: `${String(9 + Math.floor(i / 6)).padStart(2,"0")}:${String((i * 10) % 60).padStart(2,"0")}`,
  p: +(880 + Math.random() * 20 + Math.sin(i / 5) * 8).toFixed(2),
}))

const TIMEFRAMES = ["1D", "1W", "1M", "3M", "YTD"]

export default function TradingTerminal() {
  const [side, setSide] = useState<"BUY" | "SELL">("BUY")
  const [ticker, setTicker] = useState("NVDA")
  const [shares, setShares] = useState(10)
  const [tf, setTf] = useState("1D")

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto" }}>

      {/* Header row */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 600, color: "var(--text)", letterSpacing: "-0.02em" }}>
            Trading Terminal
          </h1>
          <p style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3 }}>
            Live Alpaca positions & order management
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          {[
            { label: "Account Value", value: "$124,592.50", color: "var(--green)" },
            { label: "Buying Power",  value: "$48,250.00",  color: "var(--text)"  },
          ].map((s) => (
            <div key={s.label} style={{
              background: "var(--surface)", border: "1px solid var(--border)",
              borderRadius: 6, padding: "10px 16px", textAlign: "right",
            }}>
              <div style={{ fontSize: 10, color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 4 }}>
                {s.label}
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, fontFamily: "JetBrains Mono, monospace", color: s.color }}>
                {s.value}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Body grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 16 }}>

        {/* Left column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Chart */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontSize: 16, fontWeight: 700, fontFamily: "JetBrains Mono, monospace", letterSpacing: "0.04em" }}>
                  {ticker}
                </span>
                <span style={{ fontSize: 14, fontWeight: 600, fontFamily: "JetBrains Mono, monospace", color: "var(--green)" }}>
                  $890.50
                </span>
                <span style={{ fontSize: 12, color: "var(--green)", display: "flex", alignItems: "center", gap: 2 }}>
                  <ArrowUpRight size={13} /> +2.4%
                </span>
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                {TIMEFRAMES.map((t) => (
                  <button
                    key={t}
                    onClick={() => setTf(t)}
                    style={{
                      padding: "4px 10px", borderRadius: 4, fontSize: 11, fontWeight: 500,
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
            <div style={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={CHART_DATA} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="t" stroke="var(--text-3)" fontSize={10} tickMargin={8} minTickGap={40} />
                  <YAxis
                    domain={["auto", "auto"]} stroke="var(--text-3)" fontSize={10} width={56}
                    tickFormatter={(v) => `$${v}`}
                  />
                  <Tooltip
                    contentStyle={{ background: "var(--surface-2)", border: "1px solid var(--border-2)", borderRadius: 5, fontSize: 12 }}
                    itemStyle={{ color: "var(--green)" }}
                    labelStyle={{ color: "var(--text-2)" }}
                  />
                  <Line type="monotone" dataKey="p" stroke="var(--green)" strokeWidth={1.5} dot={false} activeDot={{ r: 4, fill: "var(--green)", strokeWidth: 0 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Orders table */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                <Activity size={13} style={{ color: "var(--amber)" }} />
                Working Orders
              </span>
              <span style={{ fontSize: 11, color: "var(--text-3)" }}>{MOCK_ORDERS.length} active</span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Order ID</th>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Type</th>
                  <th className="text-right">Qty</th>
                  <th className="text-right">Price</th>
                  <th className="text-right">Status</th>
                </tr>
              </thead>
              <tbody>
                {MOCK_ORDERS.map((o) => (
                  <tr key={o.id}>
                    <td className="mono" style={{ color: "var(--text-2)" }}>{o.id}</td>
                    <td style={{ fontWeight: 600 }}>{o.symbol}</td>
                    <td>
                      <span className={`badge ${o.side === "BUY" ? "badge-green" : "badge-red"}`}>
                        {o.side}
                      </span>
                    </td>
                    <td style={{ color: "var(--text-2)" }}>{o.type}</td>
                    <td className="text-right mono">{o.qty}</td>
                    <td className="text-right mono">${o.price.toFixed(2)}</td>
                    <td className="text-right">
                      <span className="badge badge-amber">{o.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Positions table */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Open Positions</span>
              <span style={{ fontSize: 11, color: "var(--text-3)" }}>{MOCK_POSITIONS.length} positions</span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th className="text-right">Shares</th>
                  <th className="text-right">Avg Cost</th>
                  <th className="text-right">Last</th>
                  <th className="text-right">P&amp;L</th>
                  <th className="text-right">Return</th>
                </tr>
              </thead>
              <tbody>
                {MOCK_POSITIONS.map((p) => (
                  <tr key={p.symbol}>
                    <td style={{ fontWeight: 600 }}>{p.symbol}</td>
                    <td className="text-right mono">{p.shares}</td>
                    <td className="text-right mono">${p.avgPrice.toFixed(2)}</td>
                    <td className="text-right mono">${p.currentPrice.toFixed(2)}</td>
                    <td className={cn("text-right mono", p.pnl >= 0 ? "positive" : "negative")}>
                      {p.pnl >= 0 ? "+" : ""}{p.pnl.toFixed(2)}
                    </td>
                    <td className={cn("text-right", p.pnl >= 0 ? "positive" : "negative")} style={{ fontSize: 12 }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
                        {p.pnl >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                        {Math.abs(p.pnlPct)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right column — Order Entry */}
        <div className="card" style={{ padding: 16, alignSelf: "start" }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", marginBottom: 14 }}>
            Quick Trade
          </div>

          {/* Buy / Sell toggle */}
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 1fr",
            background: "var(--surface-2)", border: "1px solid var(--border)",
            borderRadius: 5, padding: 3, marginBottom: 16, gap: 3,
          }}>
            {(["BUY", "SELL"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSide(s)}
                style={{
                  padding: "7px 0", borderRadius: 3, fontSize: 12, fontWeight: 600,
                  cursor: "pointer", transition: "all 0.15s", border: "none",
                  background: side === s
                    ? s === "BUY" ? "var(--green-dim)" : "var(--red-dim)"
                    : "transparent",
                  color: side === s
                    ? s === "BUY" ? "var(--green)" : "var(--red)"
                    : "var(--text-3)",
                }}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Fields */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
            <div>
              <label className="field-label">Symbol</label>
              <input
                className="input input-mono"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                style={{ fontWeight: 600 }}
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <div>
                <label className="field-label">Shares</label>
                <input
                  type="number"
                  className="input input-mono"
                  value={shares}
                  onChange={(e) => setShares(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="field-label">Type</label>
                <select className="input-field">
                  <option>MARKET</option>
                  <option>LIMIT</option>
                </select>
              </div>
            </div>
          </div>

          {/* Est total */}
          <div style={{
            display: "flex", justifyContent: "space-between",
            padding: "10px 0", borderTop: "1px solid var(--border)",
            borderBottom: "1px solid var(--border)", marginBottom: 14,
          }}>
            <span style={{ fontSize: 11, color: "var(--text-2)" }}>Est. Total</span>
            <span style={{ fontSize: 13, fontWeight: 600, fontFamily: "JetBrains Mono, monospace", color: "var(--text)" }}>
              ${(shares * 890.50).toLocaleString()}
            </span>
          </div>

          <button style={{
            width: "100%", padding: "10px 0", borderRadius: 5, fontSize: 13,
            fontWeight: 700, cursor: "pointer", border: "none",
            background: side === "BUY" ? "var(--green)" : "var(--red)",
            color: "#0c0c0c", letterSpacing: "0.04em",
            transition: "opacity 0.15s",
          }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.85")}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
          >
            {side} {ticker || "—"}
          </button>
        </div>
      </div>
    </div>
  )
}
