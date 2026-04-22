import { useNavigate } from "react-router-dom";
import "./DataSync.css";

const sidebarItems = [
  { label: "Dashboard", icon: "dashboard" },
  { label: "Insights", icon: "query_stats" },
  { label: "Data Sync", icon: "sync", active: true },
  { label: "Reporting", icon: "bar_chart" },
  { label: "Settings", icon: "settings" },
  { label: "Support", icon: "help" },
  { label: "Sign Out", icon: "logout" }
];

const periodChips = [
  { label: "April 2026", type: "done" },
  { label: "March 2026", type: "active" },
  { label: "February 2026", type: "pending" }
];

export default function DataSync() {
  const navigate = useNavigate();

  return (
    <div className="data-sync-page">
      <aside className="data-sync-sidebar" aria-label="Sidebar">
        <div className="sidebar-brand-block">
          <h1 className="sidebar-brand-title">Tauke.AI</h1>
          <p className="sidebar-brand-subtitle">SME Intelligence</p>
        </div>

        <nav className="sidebar-nav" aria-label="Primary navigation">
          {sidebarItems.map((item) => (
            <button
              key={item.label}
              type="button"
              className={`sidebar-nav-item${item.active ? " is-active" : ""}`}
            >
              <span className="material-symbols-outlined sidebar-nav-icon" aria-hidden="true">{item.icon}</span>
              <span className="sidebar-nav-label">{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <main className="data-sync-main">
        <div className="data-sync-shell">
          <header className="page-header">
            <h2 className="page-title">Data Intelligence Hub</h2>
            <p className="page-subtitle">Synthesize your enterprise data for predictive modeling.</p>
          </header>

          <section className="data-sync-grid" aria-label="Data sync cards">
            <article className="sync-card">
              <div className="card-header-row">
                <div>
                  <h3 className="card-title">Sales &amp; Transactions <span>(CSV)</span></h3>
                </div>
                <span className="status-pill synced-pill">
                  <span className="material-symbols-outlined" aria-hidden="true">check_circle</span>
                  Synced
                </span>
              </div>

              <p className="card-copy">Historical POS records and daily transaction logs.</p>

              <div className="stats-block">
                <div className="stat-row">
                  <span>Rows Parsed</span>
                  <strong>13,426</strong>
                </div>
                <div className="stat-row">
                  <span>Last Update</span>
                  <strong>Today, 09:41 AM</strong>
                </div>
              </div>
            </article>

            <article className="sync-card">
              <div className="card-header-row">
                <div>
                  <h3 className="card-title">Financial Performance <span>(PDF)</span></h3>
                </div>
                <span className="status-pill processing-pill">
                  <span className="material-symbols-outlined" aria-hidden="true">sync</span>
                  Processing
                </span>
              </div>

              <p className="card-copy">Monthly balance sheets and P&amp;L statements.</p>

              <div className="progress-panel">
                <div className="progress-row">
                  <span>Scanning ledger entities...</span>
                  <strong>72%</strong>
                </div>
                <div className="progress-track" aria-hidden="true">
                  <div className="progress-value" />
                </div>
              </div>

              <div className="period-chip-row">
                {periodChips.map((chip) => (
                  <span key={chip.label} className={`period-chip chip-${chip.type}`}>
                    {chip.label}
                  </span>
                ))}
              </div>
            </article>

            <article className="sync-card wide-card">
              <div className="card-header-row">
                <div>
                  <h3 className="card-title">Procurement &amp; Invoices <span>(PDF)</span></h3>
                </div>
                <span className="status-pill action-pill">
                  <span className="material-symbols-outlined" aria-hidden="true">warning</span>
                  Action Required
                </span>
              </div>

              <p className="card-copy">Awaiting March Supplier Ledger. Cannot proceed with cost analysis until the missing file is uploaded.</p>

              <button type="button" className="upload-btn">
                <span className="material-symbols-outlined" aria-hidden="true">upload_file</span>
                Upload Missing File
              </button>
            </article>
          </section>

          <div className="bottom-action-row">
            <button
              type="button"
              className="run-analyst-btn"
              onClick={() => navigate("/detective-analysis")}
            >
              <span className="material-symbols-outlined" aria-hidden="true">manage_search</span>
              Run Detective Analyst
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
