"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart2,
  Brain,
  FlaskConical,
  LineChart,
  MonitorDot,
  TrendingUp,
  Activity,
  LayoutGrid,
} from "lucide-react";

const navItems = [
  { href: "/analyze",       label: "Analysis",         icon: Brain       },
  { href: "/trading",       label: "Trading Terminal",  icon: TrendingUp  },
  { href: "/portfolio",     label: "Portfolio",         icon: BarChart2   },
  { href: "/mock-trading",  label: "Mock Trading",      icon: MonitorDot  },
  { href: "/backtest",      label: "Backtest Lab",      icon: FlaskConical},
  { href: "/watchlist",     label: "Watchlist",         icon: LineChart   },
  { href: "/observability", label: "Observability",     icon: Activity    },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <h1>QuantAgents</h1>
        <p>Trading Intelligence</p>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav" style={{ paddingTop: 8 }}>
        {navItems.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={`nav-item ${isActive ? "active" : ""}`}
            >
              <Icon className="nav-icon" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer status */}
      <div className="sidebar-footer">
        <div className="status-dot" />
        <span className="status-text">Paper trading active</span>
      </div>
    </aside>
  );
}
