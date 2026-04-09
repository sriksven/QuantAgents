"use client"

import { useState, useCallback } from 'react'

export type AgentNode = "research_committee" | "technical_analyst" | "risk_assessor" | "portfolio_strategist" | "options_analyst" | "quantum_optimizer" | "backtester" | "trade_executor"

export interface AgentUpdate {
  node: AgentNode
  content: Record<string, unknown> | string
  timestamp: string
}

export function useAgentStream(ticker: string) {
  const [updates, setUpdates] = useState<AgentUpdate[]>([])
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Connect to the backend web API endpoint via EventSource for SSE (Server-Sent Events)
  // Our FastAPI backend emits LangGraph events
  
  const startAnalysis = useCallback(async () => {
    setIsAnalyzing(true)
    setUpdates([])
    setError(null)
    
    try {
      // Create SSE connection to backend
      // Assuming FastAPI is running on localhost:8000
      const eventSource = new EventSource(`http://localhost:8000/api/analyze/stream?ticker=${ticker}`)
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.status === "complete" || data.status === "error") {
            eventSource.close()
            setIsAnalyzing(false)
            if (data.status === "error") setError(data.error)
            return
          }
          
          if (data.node && data.content) {
            setUpdates(prev => [...prev, {
              node: data.node as AgentNode,
              content: data.content,
              timestamp: new Date().toISOString()
            }])
          }
        } catch (err) {
          console.error("Error parsing message", err)
        }
      }
      
      eventSource.onerror = (err) => {
        console.error("EventSource error", err)
        eventSource.close()
        setIsAnalyzing(false)
        setError("Connection to backend lost.")
      }
    } catch (err) {
      setIsAnalyzing(false)
      setError(String(err))
    }
  }, [ticker])

  return { updates, isAnalyzing, error, startAnalysis }
}
