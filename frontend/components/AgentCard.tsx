"use client"

import { motion } from "framer-motion"
import { Brain, ShieldAlert, LineChart, Cpu, Zap, Activity, Briefcase, FileSearch } from "lucide-react"
import ReactMarkdown from "react-markdown"
import { AgentNode, AgentUpdate } from "../hooks/useAgentStream"
import { cn } from "../lib/utils"

const AGENT_CONFIG: Record<AgentNode, { title: string; icon: React.ElementType; color: string }> = {
  research_committee: { title: "Market Researcher", icon: FileSearch, color: "text-blue-400" },
  technical_analyst: { title: "Technical Analyst", icon: LineChart, color: "text-purple-400" },
  risk_assessor: { title: "Risk Assessor", icon: ShieldAlert, color: "text-red-400" },
  portfolio_strategist: { title: "Portfolio Strategist", icon: Briefcase, color: "text-emerald-400" },
  options_analyst: { title: "Options Analyst", icon: Activity, color: "text-amber-400" },
  quantum_optimizer: { title: "Quantum Optimizer", icon: Cpu, color: "text-cyan-400" },
  backtester: { title: "Backtest Engine", icon: Zap, color: "text-indigo-400" },
  trade_executor: { title: "Trade Executor", icon: Brain, color: "text-slate-300" }
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
        "glass-panel rounded-xl overflow-hidden flex flex-col transition-all duration-300 relative",
        isThinking ? "ring-1 ring-white/10" : "border border-white/5",
        hasResult && "shadow-[0_4px_30px_rgba(0,0,0,0.5)] border-white/10"
      )}
    >
      {/* Header */}
      <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
        <div className="flex items-center gap-3">
          <div className={cn("p-2 rounded-lg bg-white/5", config.color)}>
            <Icon size={18} />
          </div>
          <h3 className="font-semibold text-[14px] tracking-wide text-slate-200">
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
                       prose-headings:text-slate-200 prose-headings:font-semibold
                       prose-a:text-indigo-400 prose-p:text-slate-300
                       prose-strong:text-indigo-300"
          >
            {typeof update.content === 'string' ? (
              <ReactMarkdown>{update.content}</ReactMarkdown>
            ) : (
              <pre className="text-[11px] bg-black/40 p-3 rounded-lg overflow-x-auto text-emerald-400 font-mono border border-white/5">
                {JSON.stringify(update.content, null, 2)}
              </pre>
            )}
          </motion.div>
        )}
      </div>

      {hasResult && (
        <div className="px-4 py-2 text-[10px] text-slate-500 uppercase tracking-wider text-right border-t border-white/5 bg-black/20">
          Last updated: {new Date(update.timestamp).toLocaleTimeString()}
        </div>
      )}
    </motion.div>
  )
}
