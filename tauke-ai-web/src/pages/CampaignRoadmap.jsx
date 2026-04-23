import { NavLink, useNavigate } from "react-router-dom";
import "./CampaignRoadmap.css";

const navItems = [
  { label: "Store Setup", icon: "storefront", to: "/store-configuration" },
  { label: "Data Sync", icon: "sync", to: "/data-sync" },
  { label: "Analysis", icon: "insights", to: "/detective-analysis" },
  { label: "Clarification", icon: "forum", to: "/supervisor-clarification" },
  { label: "War Room", icon: "groups", to: "/ai-debate" },
  { label: "Strategy Synthesis", icon: "hub", to: "/final-synthesis", active: true }
];

const roadmapPhases = [
  {
    phase: "Phase 1",
    title: "Campaign Setup And Offer Configuration",
    description:
      "Finalize bundle composition, promotion guardrails, and channel-level message templates for a controlled launch.",
    status: "Completed",
    tone: "done",
    owner: "Owner: Strategy Team",
    timeline: "Timeline: Week 1",
    activity: "Activity: 12 launch assets prepared"
  },
  {
    phase: "Phase 2",
    title: "Pilot Launch In High-Volume Time Slots",
    description:
      "Deploy in selected windows to validate demand response, queue handling, and margin behavior before full rollout.",
    status: "In Progress",
    tone: "active",
    owner: "Owner: Operations Lead",
    timeline: "Timeline: Weeks 2 to 3",
    activity: "Activity: 68% execution completion"
  },
  {
    phase: "Phase 3",
    title: "Performance Review And Guardrail Adjustment",
    description:
      "Review conversion, average order value, and contribution margin to tune category caps and inventory pacing.",
    status: "Upcoming",
    tone: "next",
    owner: "Owner: Finance + Growth",
    timeline: "Timeline: Week 4",
    activity: "Activity: KPI checkpoint scheduled"
  },
  {
    phase: "Phase 4",
    title: "Scaled Rollout With Weekly Optimization",
    description:
      "Expand execution across all targeted windows with weekly optimization loops and clear stop-loss triggers.",
    status: "Queued",
    tone: "next",
    owner: "Owner: Regional Manager",
    timeline: "Timeline: Weeks 5 to 8",
    activity: "Activity: Expansion readiness at 82%"
  }
];

const summaryItems = [
  { label: "Overall completion", value: "68%" },
  { label: "On-track phases", value: "3 / 4" },
  { label: "Expected launch window", value: "Next 10 days" }
];

export default function CampaignRoadmap() {
  const navigate = useNavigate();

  return (
    <div className="roadmap-page">
      <main className="roadmap-main">
        <div className="roadmap-shell">
          <header className="roadmap-header">
            <p className="roadmap-step">STEP 8 / EXECUTION ROADMAP</p>
            <h2 className="roadmap-title">Campaign Roadmap</h2>
            <p className="roadmap-subtitle">
              The final strategy has now been translated into a practical execution plan with clear owners,
              milestones, and measurable delivery checkpoints.
            </p>
          </header>

          <section className="roadmap-layout" aria-label="Execution roadmap layout">
            <div className="timeline-column">
              <div className="timeline-head">
                <h3>Execution Timeline</h3>
                <span className="timeline-head-pill">Live plan</span>
              </div>

              <ol className="timeline-list">
                {roadmapPhases.map((phase, index) => (
                  <li className="timeline-item" key={phase.title}>
                    <div className="timeline-rail" aria-hidden="true">
                      <span className={`timeline-dot tone-${phase.tone}`} />
                      {index < roadmapPhases.length - 1 && <span className="timeline-line" />}
                    </div>

                    <article className="phase-card">
                      <div className="phase-top-row">
                        <p className="phase-label">{phase.phase}</p>
                        <span className={`phase-status tone-${phase.tone}`}>{phase.status}</span>
                      </div>

                      <h4 className="phase-title">{phase.title}</h4>
                      <p className="phase-description">{phase.description}</p>

                      <div className="phase-meta-grid">
                        <p>{phase.owner}</p>
                        <p>{phase.timeline}</p>
                        <p>{phase.activity}</p>
                      </div>
                    </article>
                  </li>
                ))}
              </ol>
            </div>

            <aside className="summary-column" aria-label="Progress summary">
              <section className="summary-card">
                <p className="summary-kicker">Execution status</p>
                <h3 className="summary-value">68%</h3>
                <p className="summary-copy">Current completion across setup and pilot rollout activities.</p>

                <div className="summary-track" aria-hidden="true">
                  <span className="summary-fill" />
                </div>

                <div className="summary-list">
                  {summaryItems.map((item) => (
                    <div className="summary-row" key={item.label}>
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                    </div>
                  ))}
                </div>
              </section>
            </aside>
          </section>

          <div className="roadmap-actions">
            <button
              type="button"
              className="roadmap-secondary-action"
              onClick={() => navigate("/final-synthesis")}
            >
              Back to Synthesis
            </button>
            <button
              type="button"
              className="roadmap-primary-action"
              onClick={() => navigate("/landing")}
            >
              <span>Confirm and Launch Plan</span>
              <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
