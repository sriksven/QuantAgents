"use client"

import { motion } from "framer-motion"
import { Brain, ShieldAlert, LineChart, Cpu, Zap, Activity, Briefcase, FileSearch, CheckCircle } from "lucide-react"
import ReactMarkdown from "react-markdown"
import { AgentNode, AgentUpdate } from "../hooks/useAgentStream"
import { cn } from "../lib/utils"

const AGENT_CONFIG: Record<AgentNode, {
  title: string
  icon: React.ElementType
  tag: string
}> = {
  research_committee:  { title: "Market Researcher",     icon: FileSearch,  tag: "Fundamental"  },
  technical_analyst:   { title: "Technical Analyst",      icon: LineChart,   tag: "Technical"    },
  risk_assessor:       { title: "Risk Assessor",          icon: ShieldAlert, tag: "Risk"         },
  portfolio_strategist:{ title: "Portfolio Strategist",   icon: Briefcase,   tag: "Allocation"   },
  options_analyst:     { title: "Options Analyst",        icon: Activity,    tag: "Derivatives"  },
  quantum_optimizer:   { title: "Quantum Optimizer",      icon: Cpu,         tag: "Optimization" },
  backtester:          { title: "Backtest Engine",        icon: Zap,         tag: "Validation"   },
  trade_executor:      { title: "Trade Executor",         icon: Brain,       tag: "Execution"    },
}

export function AgentCard({
  node,
  update,
  isAnalyzing,
}: {
  node: AgentNode
  update: AgentUpdate | null
  isAnalyzing: boolean
}) {
  const config = AGENT_CONFIG[node]
  const Icon = config.icon

  const isIdle     = !update && !isAnalyzing
  const isThinking = isAnalyzing && !update
  const hasResult  = !!update

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        background: "var(--surface)",
        border: `1px solid ${isThinking ? "rgba(59,130,246,0.3)" : hasResult ? "rgba(34,197,94,0.2)" : "var(--border)"}`,
        borderRadius: 7,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        transition: "border-color 0.2s",
      }}
    >
      {/* Header */}
      <div style={{
        padding: "11px 14px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "var(--surface-2)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <Icon size={14} style={{ color: "var(--text-2)", flexShrink: 0 }} />
          <span style={{ fontSize: 12, fontWeight: 500, color: "var(--text)" }}>
            {config.title}
          </span>
        </div>

        {/* Status */}
        <div>
          {isIdle && (
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--text-3)", display: "block" }} />
          )}
          {isThinking && (
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-60" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
            </span>
          )}
          {hasResult && (
            <CheckCircle size={13} style={{ color: "var(--green)" }} />
          )}
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, minHeight: 100, maxHeight: 220, overflowY: "auto", padding: "12px 14px" }}>
        {isIdle && (
          <p style={{ fontSize: 12, color: "var(--text-3)", textAlign: "center", paddingTop: 16 }}>
            Awaiting input
          </p>
        )}

        {isThinking && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 8 }}>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1.4, ease: "linear" }}
              style={{
                width: 18, height: 18,
                border: "2px solid var(--border-2)",
                borderTopColor: "var(--accent)",
                borderRadius: "50%",
              }}
            />
            <span style={{ fontSize: 10, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
              Processing
            </span>
          </div>
        )}

        {hasResult && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.6 }}
            className="prose-minimal"
          >
            {typeof update.content === "string" ? (
              <ReactMarkdown
                components={{
                  p: ({ children }) => <p style={{ marginBottom: 6, color: "var(--text-2)", fontSize: 12 }}>{children}</p>,
                  strong: ({ children }) => <strong style={{ color: "var(--text)", fontWeight: 600 }}>{children}</strong>,
                  h1: ({ children }) => <p style={{ color: "var(--text)", fontWeight: 600, marginBottom: 4 }}>{children}</p>,
                  h2: ({ children }) => <p style={{ color: "var(--text)", fontWeight: 600, marginBottom: 4 }}>{children}</p>,
                  h3: ({ children }) => <p style={{ color: "var(--text)", fontWeight: 600, marginBottom: 4 }}>{children}</p>,
                  ul: ({ children }) => <ul style={{ paddingLeft: 14, marginBottom: 6 }}>{children}</ul>,
                  li: ({ children }) => <li style={{ color: "var(--text-2)", fontSize: 12, marginBottom: 2 }}>{children}</li>,
                }}
              >
                {update.content}
              </ReactMarkdown>
            ) : (
              <pre style={{
                fontSize: 10,
                background: "var(--surface-3)",
                border: "1px solid var(--border)",
                borderRadius: 4,
                padding: "8px 10px",
                overflowX: "auto",
                color: "var(--green)",
                fontFamily: "JetBrains Mono, monospace",
              }}>
                {JSON.stringify(update.content, null, 2)}
              </pre>
            )}
          </motion.div>
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: "7px 14px",
        borderTop: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <span style={{
          fontSize: 10,
          color: "var(--text-3)",
          textTransform: "uppercase",
          letterSpacing: "0.07em",
          fontWeight: 600,
        }}>
          {config.tag}
        </span>
        {hasResult && (
          <span style={{ fontSize: 10, color: "var(--text-3)", fontFamily: "JetBrains Mono, monospace" }}>
            {new Date(update.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </span>
        )}
      </div>
    </motion.div>
  )
}
