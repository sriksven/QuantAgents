"use client"

import { useState } from "react"
import { Search, BrainCircuit, Activity } from "lucide-react"
import { useAgentStream, AgentNode, AgentUpdate } from "../hooks/useAgentStream"
import { AgentCard } from "../components/AgentCard"

const AGENT_ORDER: AgentNode[] = [
  "research_committee",
  "technical_analyst",
  "risk_assessor",
  "options_analyst",
  "portfolio_strategist",
  "quantum_optimizer",
  "backtester",
  "trade_executor"
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

  // Map updates to latest per node
  const nodeUpdates = updates.reduce((acc, curr) => {
    acc[curr.node] = curr
    return acc
  }, {} as Record<string, AgentUpdate>)

  return (
    <div className="min-h-full flex flex-col bg-dot-grid relative">
      {/* Background Glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[300px] bg-indigo-500/10 blur-[120px] rounded-full pointer-events-none" />

      {/* Header & Search */}
      <div className="z-10 mb-8 max-w-3xl mx-auto w-full text-center mt-6">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold uppercase tracking-widest mb-6">
          <Activity size={14} className="animate-pulse" />
          Live Intelligence Stream
        </div>
        
        <h2 className="text-3xl font-bold tracking-tight mb-2 text-white">
          Analysis Console
        </h2>
        <p className="text-slate-400 mb-8 max-w-xl mx-auto">
          Deploy the 8-agent committee to perform deep fundamental, technical, options, 
          and quantum-enhanced research on any equity.
        </p>

        <form onSubmit={handleAnalyze} className="relative max-w-md mx-auto flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
            <input 
              type="text" 
              placeholder="Enter ticker (e.g. AAPL, TSLA)"
              className="input-field w-full pl-11 text-lg font-mono tracking-widest uppercase placeholder:normal-case placeholder:tracking-normal"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              disabled={isAnalyzing}
            />
          </div>
          <button 
            type="submit" 
            className="glow-btn flex items-center gap-2"
            disabled={!ticker.trim() || isAnalyzing}
          >
            {isAnalyzing ? (
              <BrainCircuit className="animate-pulse" size={18} />
            ) : (
              <Search size={18} />
            )}
            {isAnalyzing ? "Analyzing..." : "Analyze"}
          </button>
        </form>

        {error && (
          <div className="mt-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm max-w-md mx-auto">
            {error}
          </div>
        )}
      </div>

      {/* Agent Grid */}
      <div className="z-10 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 w-full max-w-[1400px] mx-auto pb-12">
        {AGENT_ORDER.map((node) => (
          <AgentCard 
            key={node}
            node={node}
            update={nodeUpdates[node] || null}
            isAnalyzing={isAnalyzing}
          />
        ))}
      </div>
    </div>
  )
}
