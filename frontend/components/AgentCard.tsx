"use client"

import { motion } from "framer-motion"
import { Brain, ShieldAlert, LineChart, Cpu, Zap, Activity, Briefcase, FileSearch } from "lucide-react"
import ReactMarkdown from "react-markdown"
import { AgentNode, AgentUpdate } from "../hooks/useAgentStream"
import { cn } from "../lib/utils"

const AGENT_CONFIG: Record<AgentNode, { title: string; icon: React.ElementType; color: string; logic: string }> = {
  research_committee: { title: "Market Researcher", icon: FileSearch, color: "text-blue-600", logic: "Queries Alpha Vantage & SEC Edgar. Outputs fundamental summaries." },
  technical_analyst: { title: "Technical Analyst", icon: LineChart, color: "text-purple-600", logic: "Compute Moving Averages, RSI from price feeds. Outputs technical scores." },
  risk_assessor: { title: "Risk Assessor", icon: ShieldAlert, color: "text-red-600", logic: "Calculates historic drawdowns and Beta. Outputs risk constraints." },
  portfolio_strategist: { title: "Portfolio Strategist", icon: Briefcase, color: "text-emerald-600", logic: "Aggregates researcher & analyst signals into base allocation targets." },
  options_analyst: { title: "Options Analyst", icon: Activity, color: "text-amber-600", logic: "Scans OPRA chain for volatility hedging. Outputs premium overlays." },
  quantum_optimizer: { title: "Quantum Optimizer", icon: Cpu, color: "text-cyan-600", logic: "Runs QAOA simulated annealing on allocations. Outputs ideal weights." },
  backtester: { title: "Backtest Engine", icon: Zap, color: "text-indigo-600", logic: "Validates optimized weights against 5Y historical data via VectorBT." },
  trade_executor: { title: "Trade Executor", icon: Brain, color: "text-slate-600", logic: "Formats final payloads and dispatches POST order to Alpaca API." }
}

export function AgentCard({ 
  node, 
  update, 
  isAnalyzing 
}: { 
  node: AgentNode; 
  update: AgentUpdate | null;
  isAnalyzing: boolean;
}) {
  const config = AGENT_CONFIG[node]
  const Icon = config.icon

  // Determine State
  const isIdle = !update && !isAnalyzing
  const isThinking = isAnalyzing && !update
  const hasResult = !!update

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        "glass-panel flex flex-col transition-all duration-300 relative bg-white",
        isThinking ? "border-blue-300 shadow-sm" : "border-slate-200",
        hasResult && "shadow-md border-slate-300"
      )}
    >
      {/* Header */}
      <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50 rounded-t-lg">
        <div className="flex items-center gap-3">
          <div className={cn("p-2 rounded-lg bg-white shadow-sm border border-slate-200", config.color)}>
            <Icon size={18} />
          </div>
          <h3 className="font-semibold text-[14px] tracking-wide text-slate-900">
            {config.title}
          </h3>
        </div>
        
        {/* Status indicator */}
        <div className="flex items-center gap-2">
          {isThinking && (
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
            </span>
          )}
          {hasResult && <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_8px_#10b981]" />}
          {isIdle && <span className="h-2 w-2 rounded-full bg-slate-600" />}
        </div>
      </div>

      {/* Body */}
      <div className="p-5 flex-1 max-h-[250px] overflow-y-auto min-h-[120px]">
        {isIdle && (
          <div className="h-full flex items-center justify-center text-slate-500 text-sm font-medium">
            Awaiting analysis...
          </div>
        )}

        {isThinking && (
          <div className="h-full flex flex-col items-center justify-center gap-3">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
              className="w-6 h-6 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full"
            />
            <span className="text-xs text-indigo-400/70 uppercase tracking-widest font-semibold animate-pulse">
              Computing
            </span>
          </div>
        )}

        {hasResult && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }} 
            animate={{ opacity: 1, y: 0 }}
            className="prose prose-invert prose-sm max-w-none 
                    prose-headings:text-slate-900 prose-headings:font-semibold
                       prose-a:text-blue-600 prose-p:text-slate-700
                       prose-strong:text-slate-900"
          >
            {typeof update.content === 'string' ? (
              <ReactMarkdown>{update.content}</ReactMarkdown>
            ) : (
              <pre className="text-[11px] bg-slate-100 p-3 rounded-lg overflow-x-auto text-emerald-700 font-mono border border-slate-200">
                {JSON.stringify(update.content, null, 2)}
              </pre>
            )}
          </motion.div>
        )}
      </div>

      <div className="px-4 py-3 bg-slate-50 border-t border-slate-100 rounded-b-lg">
        <p className="text-[11px] text-slate-500 leading-tight border-l-2 border-blue-200 pl-2">
          <strong className="text-slate-700">Methodology:</strong> {config.logic}
        </p>
        {hasResult && (
          <div className="mt-2 text-[9px] text-slate-400 uppercase tracking-wider text-right">
            Done: {new Date(update.timestamp).toLocaleTimeString()}
          </div>
        )}
      </div>
    </motion.div>
  )
}
