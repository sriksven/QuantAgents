"use client"

import { BookOpen, Network, Database, ShieldAlert, CheckCircle2, Server, Eye, ArrowUpRight } from "lucide-react"

export default function ObservabilityPage() {
  return (
    <div className="min-h-full flex flex-col pt-4 max-w-[1600px] mx-auto w-full gap-6 pb-12">
      
      {/* Header */}
      <div className="flex flex-col mb-2">
        <h2 className="text-3xl font-bold tracking-tight text-white mb-1">Observability & MLOps</h2>
        <p className="text-slate-400">Monitoring data pipelines, model registries, and Langfuse agent traces</p>
      </div>

      {/* Global Status */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-2">
        {[
          { label: "Data Pipeline", stat: "Synced", time: "2h ago", icon: Database, color: "text-emerald-400" },
          { label: "Model Registry", stat: "v1.2 Active", time: "30d left", icon: Network, color: "text-blue-400" },
          { label: "Graph Traces", stat: "1,245 Events", time: "24h Volume", icon: Eye, color: "text-indigo-400" },
          { label: "Bias Matrix", stat: "ALL_PASS", time: "0 HIGH", icon: ShieldAlert, color: "text-emerald-400" },
        ].map((sys, i) => (
          <div key={i} className="glass-panel p-5 rounded-xl border border-white/5 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">{sys.label}</p>
              <p className="text-lg font-bold text-white tracking-wide">{sys.stat}</p>
              <p className="text-xs mt-1 text-slate-500">{sys.time}</p>
            </div>
            <div className={`p-3 rounded-lg bg-black/40 ${sys.color}`}>
              <sys.icon size={20} />
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Airflow / MLflow Frame Placeholders */}
        <div className="glass-panel p-6 rounded-2xl flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Server size={18} className="text-indigo-400" /> Airflow Pipeline Status
            </h3>
            <a href="http://localhost:8080" target="_blank" rel="noreferrer" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors flex items-center gap-1">
              Open UI <ArrowUpRight size={12} />
            </a>
          </div>
          
          <div className="flex-1 bg-black/40 rounded-xl border border-white/5 p-4 flex flex-col items-center justify-center text-center gap-4 min-h-[300px]">
            <CheckCircle2 size={48} className="text-emerald-500/50" />
            <div>
              <p className="text-slate-300 font-medium">monthly_retrain DAG</p>
              <p className="text-sm text-slate-500 mt-1">Last successful run: May 01, 2026</p>
            </div>
          </div>
        </div>

        <div className="glass-panel p-6 rounded-2xl flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <BookOpen size={18} className="text-emerald-400" /> MLflow Tracking
            </h3>
            <a href="http://localhost:5001" target="_blank" rel="noreferrer" className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors flex items-center gap-1">
              Open UI <ArrowUpRight size={12} />
            </a>
          </div>
          
          <div className="flex-1 bg-black/40 rounded-xl border border-white/5 p-4 flex flex-col items-center justify-center text-center gap-4 min-h-[300px]">
            <Network size={48} className="text-emerald-500/50" />
            <div>
              <p className="text-slate-300 font-medium">Confidence Calibrator v3 (XGBoost)</p>
              <p className="text-sm text-slate-500 mt-1">AUC: 0.89 | R²: 0.74</p>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}


