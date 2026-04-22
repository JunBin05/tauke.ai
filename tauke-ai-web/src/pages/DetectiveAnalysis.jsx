import { NavLink } from "react-router-dom";
import "./DetectiveAnalysis.css";

const navItems = [
  { label: "Store Setup", icon: "storefront", to: "/store-configuration" },
  { label: "Data Sync", icon: "sync", to: "/data-sync" },
  { label: "Analysis", icon: "insights", to: "/detective-analysis", active: true },
  { label: "Clarification", icon: "forum", to: "/supervisor-clarification" },
  { label: "War Room", icon: "groups", to: "/ai-debate" },
  { label: "Strategy Synthesis", icon: "hub", to: "/final-synthesis" }
];

const theoryCards = [
  {
    title: "Student Break Sensitivity",
    description: "Weekend and mid-sem schedule shifts are likely driving abrupt weekday demand volatility."
  },
  {
    title: "Competitor Offer Pressure",
    description: "Nearby bundle campaigns appear to be redirecting value-focused visitors during peak lunch windows."
  },
  {
    title: "Category Mix Imbalance",
    description: "Strong growth in trending beverages may be masking slower-moving core menu contribution margins."
  }
];

export default function DetectiveAnalysis() {
  return (
    <div className="detective-page">
      <aside className="detective-sidebar" aria-label="Sidebar">
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

      <main className="detective-main">
        <div className="detective-shell">
          <header className="detective-header">
            <p className="step-label">Step 4 / Detective Agent</p>
            <h2 className="page-title">Analysis</h2>
            <p className="page-subtitle">Identifying patterns and anomalies in your business data.</p>
          </header>

          <section className="analysis-grid" aria-label="Analysis cards">
            <article className="analysis-card revenue-card">
              <div className="card-header-row">
                <div>
                  <h3 className="card-title">Revenue Velocity</h3>
                  <p className="card-subtitle">Trailing 30 days</p>
                </div>
                <button type="button" className="month-dropdown">
                  <span>Oct 2023</span>
                  <span className="material-symbols-outlined" aria-hidden="true">expand_more</span>
                </button>
              </div>

              <div className="chart-panel">
                <svg viewBox="0 0 560 220" preserveAspectRatio="none" className="line-chart" aria-hidden="true">
                  <path d="M0 170 C60 130, 90 140, 150 110 C210 80, 250 95, 300 70 C350 45, 400 55, 460 40 C500 32, 530 28, 560 25" />
                  <circle cx="350" cy="55" r="5" />
                </svg>

                <div className="anomaly-tooltip">
                  <p className="tooltip-title">Anomaly Detected</p>
                  <p className="tooltip-copy">UM mid-sem break demand shift</p>
                </div>
              </div>
            </article>

            <article className="analysis-card external-card">
              <h3 className="card-title">External Intelligence</h3>

              <div className="competitor-list">
                <div className="competitor-item">
                  <div className="competitor-header">
                    <p className="competitor-name">Starbucks</p>
                    <span className="competitor-badge badge-down">-4.2%</span>
                  </div>
                  <p className="competitor-copy">Footfall softened after the latest campaign cycle ended in this district.</p>
                </div>

                <div className="competitor-item">
                  <div className="competitor-header">
                    <p className="competitor-name">The Library Coffee</p>
                    <span className="competitor-badge badge-up">+8.7%</span>
                  </div>
                  <p className="competitor-copy">Student bundle offers are attracting short-stay visits during afternoon peak.</p>
                </div>
              </div>
            </article>

            <article className="analysis-card theories-card">
              <div className="theories-header">
                <h3 className="card-title">Detective Theories</h3>
                <p className="theories-subtitle">Strategic hypotheses generated from cross-data analysis.</p>
              </div>

              <div className="theory-grid">
                {theoryCards.map((theory) => (
                  <div key={theory.title} className="theory-card">
                    <h4>{theory.title}</h4>
                    <p>{theory.description}</p>
                  </div>
                ))}
              </div>
            </article>
          </section>
        </div>
      </main>
    </div>
  );
}
