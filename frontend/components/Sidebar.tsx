"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart2,
  BookOpen,
  Brain,
  FlaskConical,
  LineChart,
  TrendingUp,
} from "lucide-react";

const navItems = [
  {
    href: "/",
    label: "Analysis Console",
    icon: Brain,
    description: "8-agent research",
  },
  {
    href: "/trading",
    label: "Trading Terminal",
    icon: TrendingUp,
    description: "Orders & positions",
  },
  {
    href: "/portfolio",
    label: "Portfolio",
    icon: BarChart2,
    description: "P&L & allocations",
  },
  {
    href: "/backtest",
    label: "Backtest Lab",
    icon: FlaskConical,
    description: "Strategy validation",
  },
  {
    href: "/watchlist",
    label: "Watchlist",
    icon: LineChart,
    description: "Live prices & alerts",
  },
  {
    href: "/observability",
    label: "Observability",
    icon: BookOpen,
    description: "MLOps & traces",
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <h1>QuantAgents</h1>
        <p>Trading Intelligence Platform</p>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {navItems.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href;
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

      {/* Status */}
      <div className="sidebar-status">
        <div className="status-dot" />
        <span className="status-text">Paper trading active</span>
      </div>
    </aside>
  );
}
