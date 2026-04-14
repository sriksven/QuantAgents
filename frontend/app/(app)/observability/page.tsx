"use client"

import { Network, Database, ShieldCheck, Eye, Server, BookOpen, ArrowUpRight, CheckCircle2 } from "lucide-react"

const STATUS_CARDS = [
  { label: "Data Pipeline",  stat: "Synced",       sub: "Updated 2h ago",  icon: Database,    color: "var(--green)"  },
  { label: "Model Registry", stat: "v1.2 Active",   sub: "30 days left",   icon: Network,     color: "var(--accent)" },
  { label: "Graph Traces",   stat: "1,245 Events",  sub: "24h volume",     icon: Eye,         color: "var(--accent)" },
  { label: "Bias Matrix",    stat: "ALL PASS",      sub: "0 HIGH severity", icon: ShieldCheck, color: "var(--green)"  },
]

export default function ObservabilityPage() {
  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>

      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 18, fontWeight: 600, color: "var(--text)", letterSpacing: "-0.02em" }}>
          Observability
        </h1>
        <p style={{ fontSize: 12, color: "var(--text-2)", marginTop: 3 }}>
          Data pipelines, model registry, Langfuse traces, bias monitoring
        </p>
      </div>

      {/* Status row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        {STATUS_CARDS.map((s) => (
          <div key={s.label} className="stat-card" style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 6,
              background: "var(--surface-3)", border: "1px solid var(--border)",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <s.icon size={16} style={{ color: s.color }} />
            </div>
            <div>
              <div className="stat-label">{s.label}</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", lineHeight: 1.2 }}>{s.stat}</div>
              <div style={{ fontSize: 10, color: "var(--text-3)", marginTop: 2 }}>{s.sub}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Service panels */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        {[
          {
            title: "Airflow Pipeline",
            icon: Server,
            color: "var(--accent)",
            href: "http://localhost:8080",
            icon2: CheckCircle2,
            icon2Color: "var(--green)",
            name: "monthly_retrain DAG",
            meta: "Last run: May 01, 2026 — Success",
          },
          {
            title: "MLflow Tracking",
            icon: BookOpen,
            color: "var(--green)",
            href: "http://localhost:5001",
            icon2: Network,
            icon2Color: "var(--accent)",
            name: "Confidence Calibrator v3 (XGBoost)",
            meta: "AUC: 0.89 · R²: 0.74",
          },
        ].map((svc) => (
          <div key={svc.title} className="card">
            <div className="card-header">
              <span className="card-title">
                <svc.icon size={13} style={{ color: svc.color }} />
                {svc.title}
              </span>
              <a
                href={svc.href}
                target="_blank"
                rel="noreferrer"
                style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 11, color: "var(--text-2)", textDecoration: "none" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-2)")}
              >
                Open UI <ArrowUpRight size={11} />
              </a>
            </div>
            <div style={{
              minHeight: 240, display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center", gap: 12,
              background: "var(--surface-2)", margin: 12, borderRadius: 5,
              border: "1px solid var(--border)",
            }}>
              <svc.icon2 size={40} style={{ color: svc.icon2Color, opacity: 0.3 }} />
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-2)" }}>{svc.name}</div>
                <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4, fontFamily: "JetBrains Mono, monospace" }}>{svc.meta}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
