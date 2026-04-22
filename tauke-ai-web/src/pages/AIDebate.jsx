import { NavLink, useNavigate } from "react-router-dom";
import "./AIDebate.css";

const navItems = [
  { label: "Store Setup", icon: "storefront", to: "/store-configuration" },
  { label: "Data Sync", icon: "sync", to: "/data-sync" },
  { label: "Analysis", icon: "insights", to: "/detective-analysis" },
  { label: "Clarification", icon: "forum", to: "/supervisor-clarification" },
  { label: "War Room", icon: "groups", to: "/ai-debate", active: true },
  { label: "Strategy Synthesis", icon: "hub", to: "/final-synthesis" }
];

const debateItems = [
  {
    role: "Growth Hacker",
    icon: "trending_up",
    stance: "Aggressive Push",
    copy:
      "Launch a 10-day student combo with limited-time urgency. Demand elasticity is still favorable and can recover top-line quickly.",
    indicatorLabel: "Impact",
    indicatorValue: "+18% traffic potential",
    tone: "up"
  },
  {
    role: "Risk Manager",
    icon: "shield",
    stance: "Margin Protection",
    copy:
      "Price compression beyond 7% may erode unit economics. If promoted, cap discounts by category and enforce daily margin guardrails.",
    indicatorLabel: "Risk",
    indicatorValue: "High if uncapped",
    tone: "down"
  },
  {
    role: "Competitor Analyst",
    icon: "monitoring",
    stance: "Differentiated Offer",
    copy:
      "Primary competitor is discounting drinks only. Bundle speed and reliability into our offer to avoid a direct price war.",
    indicatorLabel: "Evidence",
    indicatorValue: "3 nearby campaigns tracked",
    tone: "neutral"
  },
  {
    role: "Operations Chief",
    icon: "account_tree",
    stance: "Phased Rollout",
    copy:
      "Run pilot in two high-volume slots first. Operational readiness is moderate, and phased rollout reduces queue and staffing risk.",
    indicatorLabel: "Readiness",
    indicatorValue: "82% staffing coverage",
    tone: "up"
  }
];

export default function AIDebate() {
  const navigate = useNavigate();

  return (
    <div className="war-room-page">
      <aside className="war-room-sidebar" aria-label="Sidebar">
        <div className="sidebar-brand-block">
          <h1 className="sidebar-brand-title">Tauke.AI</h1>
          <p className="sidebar-brand-subtitle">SME Intelligence</p>
        </div>

        <nav className="sidebar-nav" aria-label="Primary navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.label}
              to={item.to}
              className={({ isActive }) => `sidebar-nav-item${isActive || item.active ? " is-active" : ""}`}
            >
              <span className="material-symbols-outlined sidebar-nav-icon" aria-hidden="true">{item.icon}</span>
              <span className="sidebar-nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-user-block">
          <div className="sidebar-avatar" aria-hidden="true">A</div>
          <div>
            <p className="sidebar-user-name">Admin User</p>
            <p className="sidebar-user-meta">Manage Account</p>
          </div>
        </div>
      </aside>

      <main className="war-room-main">
        <div className="war-room-shell">
          <header className="war-room-header">
            <p className="war-room-step">STEP 6 / AI WAR ROOM</p>
            <h2 className="war-room-title">Strategic Debate</h2>
            <p className="war-room-subtitle">
              Multiple AI perspectives are evaluating the strongest next business action before synthesis.
            </p>
          </header>

          <section className="debate-panel" aria-label="AI debate war room">
            <div className="debate-panel-header">
              <div>
                <p className="debate-panel-kicker">Live Session</p>
                <h3 className="debate-panel-title">Q3 Recovery Strategy Simulator</h3>
              </div>

              <div className="debate-status-card" aria-label="Debate status">
                <p className="status-label">System status</p>
                <p className="status-value">Evaluating strategic options</p>
                <div className="status-track" aria-hidden="true">
                  <div className="status-fill" />
                </div>
              </div>
            </div>

            <div className="debate-feed">
              {debateItems.map((item) => (
                <article key={item.role} className="agent-card">
                  <div className="agent-icon-wrap" aria-hidden="true">
                    <span className="material-symbols-outlined">{item.icon}</span>
                  </div>

                  <div className="agent-content">
                    <div className="agent-top-row">
                      <p className="agent-role">{item.role}</p>
                      <span className={`stance-pill tone-${item.tone}`}>{item.stance}</span>
                    </div>

                    <p className="agent-copy">{item.copy}</p>

                    <div className="agent-indicator-row">
                      <span className="indicator-label">{item.indicatorLabel}</span>
                      <span className={`indicator-value tone-${item.tone}`}>{item.indicatorValue}</span>
                    </div>
                  </div>
                </article>
              ))}
            </div>

            <div className="debate-actions">
              <button
                type="button"
                className="secondary-action"
                onClick={() => navigate("/supervisor-clarification")}
              >
                Back to Clarification
              </button>
              <button
                type="button"
                className="primary-action"
                onClick={() => navigate("/final-synthesis")}
              >
                <span>Continue to Synthesis</span>
                <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
              </button>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
