"use client"

import { useState } from "react"
import { Search, Brain } from "lucide-react"
import { useAgentStream, AgentNode, AgentUpdate } from "@/hooks/useAgentStream"
import { AgentCard } from "@/components/AgentCard"

const AGENT_ORDER: AgentNode[] = [
  "research_committee",
  "technical_analyst",
  "risk_assessor",
  "options_analyst",
  "portfolio_strategist",
  "quantum_optimizer",
  "backtester",
  "trade_executor",
]

export default function AnalysisPage() {
  const [ticker, setTicker] = useState("")
  const [activeTicker, setActiveTicker] = useState<string | null>(null)
  const { updates, isAnalyzing, error, startAnalysis } = useAgentStream(activeTicker || "")

  const handleAnalyze = (e: React.FormEvent) => {
    e.preventDefault()
    if (!ticker.trim() || isAnalyzing) return
    setActiveTicker(ticker.trim().toUpperCase())
    startAnalysis()
  }

  const nodeUpdates = updates.reduce((acc, curr) => {
    acc[curr.node] = curr
    return acc
  }, {} as Record<string, AgentUpdate>)

  const doneCount = Object.keys(nodeUpdates).length

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto" }}>

      {/* Page header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 18, fontWeight: 600, color: "var(--text)", letterSpacing: "-0.02em" }}>
          Analysis Console
        </h1>
        <p style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3 }}>
          8-agent research pipeline — fundamental, technical, risk, options, quantum optimization
        </p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleAnalyze} style={{ display: "flex", gap: 8, marginBottom: 28, maxWidth: 480 }}>
        <div style={{ flex: 1, position: "relative" }}>
          <Search
            size={14}
            style={{
              position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)",
              color: "var(--text-3)", pointerEvents: "none",
            }}
          />
          <input
            type="text"
            placeholder="Ticker symbol — AAPL, NVDA, TSLA..."
            className="input input-mono"
            style={{ paddingLeft: 32, textTransform: "uppercase" }}
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            disabled={isAnalyzing}
          />
        </div>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!ticker.trim() || isAnalyzing}
        >
          {isAnalyzing ? (
            <>
              <Brain size={13} style={{ animation: "spin 1s linear infinite" }} />
              Analyzing…
            </>
          ) : (
            "Run Analysis"
          )}
        </button>
      </form>

      {/* Progress row */}
      {(isAnalyzing || doneCount > 0) && (
        <div style={{
          display: "flex", alignItems: "center", gap: 12,
          marginBottom: 20, padding: "8px 12px",
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 6, fontSize: 12,
        }}>
          <span style={{ color: "var(--text-2)" }}>
            {activeTicker && <span style={{ color: "var(--text)", fontFamily: "JetBrains Mono, monospace", fontWeight: 600, marginRight: 8 }}>{activeTicker}</span>}
            {isAnalyzing ? "Running pipeline…" : "Analysis complete"}
          </span>
          <span style={{
            marginLeft: "auto", fontSize: 11,
            color: doneCount === 8 ? "var(--green)" : "var(--text-2)",
            fontFamily: "JetBrains Mono, monospace",
          }}>
            {doneCount} / 8 agents
          </span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          padding: "10px 14px", marginBottom: 20,
          background: "var(--red-dim)", border: "1px solid rgba(248,113,113,0.2)",
          borderRadius: 6, color: "var(--red)", fontSize: 12,
        }}>
          {error}
        </div>
      )}

      {/* Agent grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
        gap: 12,
      }}>
        {AGENT_ORDER.map((node) => (
          <AgentCard
            key={node}
            node={node}
            update={nodeUpdates[node] || null}
            isAnalyzing={isAnalyzing}
          />
        ))}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
