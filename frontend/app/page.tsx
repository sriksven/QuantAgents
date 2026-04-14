import Link from "next/link";
import { ArrowRight, BrainCircuit, LineChart, Shield, LayoutDashboard, Zap } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col justify-center relative overflow-hidden bg-black selection:bg-white/20">
      
      {/* Absolute Ambient Background UI */}
      <div className="absolute top-0 inset-x-0 h-[600px] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/10 via-black to-black pointer-events-none" />
      <div className="absolute inset-0 bg-[url('https://res.cloudinary.com/dzl9yxixg/image/upload/v1714490805/grid_1_ub2o6y.svg')] bg-center [mask-image:linear-gradient(180deg,white,rgba(255,255,255,0))] opacity-10 pointer-events-none" />

      {/* Hero Section */}
      <section className="pt-32 pb-24 px-6 max-w-7xl mx-auto relative z-10 w-full flex flex-col items-center">
        
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.03] border border-white/[0.08] mb-8 shadow-2xl backdrop-blur-md">
          <Zap size={14} className="text-indigo-400" />
          <span className="text-xs font-medium text-slate-300 tracking-wide">Multi-Agent Intelligence System v2.0</span>
        </div>

        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-6xl md:text-7xl font-extrabold tracking-[-0.04em] mb-8">
            <span className="text-transparent bg-clip-text bg-gradient-to-b from-white via-white/90 to-white/40">
              Institutional Grade AI
            </span>
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-br from-indigo-400 to-indigo-600/40">
              Trading Infrastructure
            </span>
          </h1>
          <p className="text-lg md:text-xl text-slate-400/90 mb-12 leading-relaxed max-w-2xl mx-auto font-light">
            QuantAgents isn't a black box. It's an automated deployment of 8 specialized cognitive financial models that research, debate, and backtest portfolio strategies in a fully transparent execution pipeline.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Link 
              href="/analyze"
              className="glow-btn flex items-center justify-center gap-2 w-full sm:w-auto"
            >
              Launch Agentic Flow <ArrowRight size={18} />
            </Link>
            <Link 
              href="/mock-trading"
              className="subtle-btn flex items-center justify-center gap-2 w-full sm:w-auto"
            >
              Manual Mock Trading <LineChart size={18} />
            </Link>
          </div>
        </div>
      </section>

      {/* Feature Drill-downs */}
      <section className="py-24 px-6 max-w-6xl mx-auto relative z-10 border-t border-white/[0.05]">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-24">
          
          {/* Agentic Flow Explanation */}
          <div className="flex flex-col gap-6 relative">
            <div className="absolute -inset-4 bg-indigo-500/5 blur-3xl rounded-[100px] pointer-events-none" />
            <div className="glass-panel p-10 rounded-[32px] h-full flex flex-col hover:border-white/10 transition-colors duration-500 bg-white/[0.01]">
              <div className="mb-6 w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shadow-[0_0_30px_rgba(99,102,241,0.15)]">
                <BrainCircuit size={28} />
              </div>
              <h2 className="text-2xl font-semibold text-white tracking-tight mb-4">1. Agentic Flow (Automated)</h2>
              <p className="text-slate-400 leading-relaxed mb-6 font-light">
                In the Agentic Flow, human intervention is removed. When a ticker is provided, the platform spins up a robust computational committee:
              </p>
              <ul className="flex flex-col gap-4 text-slate-400 font-light text-sm mb-8">
                <li className="flex items-start gap-3">
                  <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-500 flex-shrink-0" />
                  <span><strong className="text-slate-200 font-medium">Market Researcher:</strong> Pulls SEC filings, Alpha Vantage endpoints, and scrapes web news.</span>
                </li>
                <li className="flex items-start gap-3">
                  <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-500 flex-shrink-0" />
                  <span><strong className="text-slate-200 font-medium">Technical Analyst:</strong> Parses moving averages, RSI, and MACD.</span>
                </li>
                <li className="flex items-start gap-3">
                  <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-500 flex-shrink-0" />
                  <span><strong className="text-slate-200 font-medium">Portfolio & Options Analysts:</strong> Consolidate signals into a directional allocation strategy.</span>
                </li>
                <li className="flex items-start gap-3">
                  <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-500 flex-shrink-0" />
                  <span><strong className="text-slate-200 font-medium">Quantum Optimizer & Backtester:</strong> The strategy passes through vector processing to confirm drawdown safety.</span>
                </li>
                <li className="flex items-start gap-3">
                  <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-500 flex-shrink-0" />
                  <span><strong className="text-slate-200 font-medium">Trade Executor:</strong> Dispatches final, heavily-vetted payloads directly to Alpaca.</span>
                </li>
              </ul>
              <div className="mt-auto pt-6 border-t border-white/[0.05]">
                <p className="text-slate-500 text-xs italic tracking-wide">
                  This pipeline is entirely visible natively in the Analysis Console. You watch the agents communicate dynamically.
                </p>
              </div>
            </div>
          </div>

          {/* Manual Flow Explanation */}
          <div className="flex flex-col gap-6 relative">
            <div className="absolute -inset-4 bg-emerald-500/5 blur-3xl rounded-[100px] pointer-events-none" />
            <div className="glass-panel p-10 rounded-[32px] h-full flex flex-col hover:border-white/10 transition-colors duration-500 bg-white/[0.01]">
              <div className="mb-6 w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shadow-[0_0_30px_rgba(16,185,129,0.15)]">
                <LayoutDashboard size={28} />
              </div>
              <h2 className="text-2xl font-semibold text-white tracking-tight mb-4">2. Manual Flow (Mock Sandbox)</h2>
              <p className="text-slate-400 leading-relaxed mb-8 font-light">
                If you wish to test your own strategies without relying on the AI Models, the platform provides a completely secure sandbox.
              </p>
              <div className="flex flex-col gap-5 flex-1">
                <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/[0.04]">
                  <h3 className="font-semibold text-slate-200 mb-2 flex items-center gap-2">
                    <Shield size={16} className="text-emerald-400"/> Isolated Sub-Ledger
                  </h3>
                  <p className="text-sm text-slate-400 font-light">
                    Manual trades execute against a specialized local PostgreSQL database table to ensure your live AI models remain untainted by human meddling.
                  </p>
                </div>
                <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/[0.04]">
                  <h3 className="font-semibold text-slate-200 mb-2">Live Sync Polling</h3>
                  <p className="text-sm text-slate-400 font-light">
                    The manual terminal aggressively routes current price lookups directly to the Alpaca SIP feeds. Match quotes with 100% accuracy.
                  </p>
                </div>
                <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/[0.04] mt-auto">
                  <h3 className="font-semibold text-slate-200 mb-2">Dynamic Fund Allocation</h3>
                  <p className="text-sm text-slate-400 font-light">
                    Dynamically adjust, increase, or reset your liquid cash via the Virtual Ledger interface to test diverse margin schemas.
                  </p>
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

    </div>
  );
}
