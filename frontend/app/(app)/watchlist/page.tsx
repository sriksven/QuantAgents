"use client"

import { useState } from "react"
import { ArrowUpRight, ArrowDownRight, Bell, Plus, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"

const QUOTES = [
  { symbol: "AAPL",  price: 169.80, chg: 1.2,  chgAmt:  2.01, alert: "Price > $175.00" },
  { symbol: "MSFT",  price: 412.50, chg: -0.5, chgAmt: -2.06, alert: "RSI < 30"        },
  { symbol: "NVDA",  price: 890.50, chg: 2.4,  chgAmt: 20.88, alert: "Earnings 5/22"   },
  { symbol: "AMD",   price: 175.20, chg: 3.1,  chgAmt:  5.27, alert: "MACD Cross"       },
  { symbol: "TSLA",  price: 205.10, chg: -1.2, chgAmt: -2.50, alert: "IV Rank > 50"    },
]

const ALERTS = [
  { id: 1, type: "PRICE",     symbol: "AAPL",   condition: "Crosses Above",     value: "$175.00",   status: "ACTIVE",    time: null   },
  { id: 2, type: "TECHNICAL", symbol: "MSFT",   condition: "RSI Crosses Below",  value: "30",        status: "ACTIVE",    time: null   },
  { id: 3, type: "ORDER",     symbol: "NVDA",   condition: "Limit Sell Executed", value: "100 shares", status: "TRIGGERED", time: "2h ago"},
  { id: 4, type: "SYSTEM",    symbol: "—",      condition: "Monthly Retrain",    value: "Completed", status: "TRIGGERED", time: "1d ago"},
]

const TYPE_BADGE: Record<string, string> = {
  PRICE: "badge-blue", TECHNICAL: "badge-amber", ORDER: "badge-green", SYSTEM: "badge-gray",
}

export default function WatchlistPage() {
  const [query, setQuery] = useState("")

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto" }}>

      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 18, fontWeight: 600, color: "var(--text)", letterSpacing: "-0.02em" }}>
          Watchlist
        </h1>
        <p style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3 }}>
          Track equities and configure market condition alerts
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16 }}>

        {/* Quotes table */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Live Quotes</span>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                className="input"
                placeholder="Add symbol…"
                value={query}
                onChange={(e) => setQuery(e.target.value.toUpperCase())}
                style={{ width: 140, height: 28, fontSize: 12 }}
              />
              <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 11 }}>
                <Plus size={12} /> Add
              </button>
            </div>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th className="text-right">Price</th>
                <th className="text-right">Change</th>
                <th className="text-right">%</th>
                <th>Alert</th>
                <th className="text-right"></th>
              </tr>
            </thead>
            <tbody>
              {QUOTES.map((q) => (
                <tr key={q.symbol}>
                  <td style={{ fontWeight: 600, fontFamily: "JetBrains Mono, monospace", fontSize: 12 }}>
                    {q.symbol}
                  </td>
                  <td className="text-right mono">${q.price.toFixed(2)}</td>
                  <td className={cn("text-right mono", q.chg >= 0 ? "positive" : "negative")}>
                    {q.chg >= 0 ? "+" : ""}{q.chgAmt.toFixed(2)}
                  </td>
                  <td className={cn("text-right", q.chg >= 0 ? "positive" : "negative")} style={{ fontSize: 12 }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 1 }}>
                      {q.chg >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                      {Math.abs(q.chg)}%
                    </span>
                  </td>
                  <td style={{ fontSize: 11, color: "var(--text-2)" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                      <Bell size={11} style={{ color: q.alert ? "var(--amber)" : "var(--text-3)" }} />
                      {q.alert}
                    </span>
                  </td>
                  <td className="text-right">
                    <button style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", padding: 4 }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = "var(--red)")}
                      onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-3)")}
                    >
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Alerts panel */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Bell size={13} style={{ color: "var(--amber)" }} />
              Alerts
            </span>
            <button className="btn btn-ghost" style={{ padding: "3px 8px", fontSize: 11 }}>
              <Plus size={12} />
            </button>
          </div>
          <div style={{ padding: "8px 0" }}>
            {ALERTS.map((a) => (
              <div
                key={a.id}
                style={{
                  padding: "11px 16px",
                  borderBottom: "1px solid var(--border)",
                  background: a.status === "TRIGGERED" ? "var(--surface-2)" : "transparent",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                  <span className={`badge ${TYPE_BADGE[a.type]}`}>{a.type}</span>
                  <span style={{ fontSize: 10, color: a.status === "ACTIVE" ? "var(--amber)" : "var(--text-3)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                    {a.time || a.status}
                  </span>
                </div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", marginBottom: 2 }}>
                  {a.symbol}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-2)" }}>
                  {a.condition} <span style={{ color: "var(--text)" }}>{a.value}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
