import { NavLink, useNavigate } from "react-router-dom";
import "./FinalSynthesis.css";

const navItems = [
  { label: "Store Setup", icon: "storefront", to: "/store-configuration" },
  { label: "Data Sync", icon: "sync", to: "/data-sync" },
  { label: "Analysis", icon: "insights", to: "/detective-analysis" },
  { label: "Clarification", icon: "forum", to: "/supervisor-clarification" },
  { label: "War Room", icon: "groups", to: "/ai-debate" },
  { label: "Strategy Synthesis", icon: "hub", to: "/final-synthesis", active: true }
];

const supportingCards = [
  {
    title: "Why not price match",
    copy: "Direct matching drives fast volume but compresses gross margin beyond the threshold needed for stable weekly cashflow.",
    badge: "Margin Safety"
  },
  {
    title: "Expected impact",
    copy: "Projected +9% order recovery in 4 to 6 weeks with healthier contribution margin than broad discount-led alternatives.",
    badge: "Balanced Growth"
  },
  {
    title: "Operational fit",
    copy: "The rollout can be executed with current staffing and supplier cadence, reducing implementation risk during peak periods.",
    badge: "Execution Ready"
  }
];

export default function FinalSynthesis() {
  const navigate = useNavigate();

  return (
    <div className="synthesis-page">
      <main className="synthesis-main">
        <div className="synthesis-shell">
          <header className="synthesis-header">
            <p className="synthesis-step">STEP 7 / FINAL SYNTHESIS</p>
            <h2 className="synthesis-title">Final Synthesis</h2>
            <p className="synthesis-subtitle">
              The system is now presenting the safest and most suitable final recommendation based on
              cross-agent consensus, business constraints, and expected outcome quality.
            </p>
          </header>

          <section className="consensus-card" aria-label="Final recommendation">
            <div className="consensus-head">
              <p className="consensus-kicker">Consensus Recommendation</p>
              <span className="consensus-pill">Highest confidence path</span>
            </div>

            <h3 className="consensus-title">Targeted Value Bundle With Guardrailed Promotions</h3>
            <p className="consensus-summary">
              Prioritize a value-bundle strategy focused on high-volume windows, while keeping selective
              promotional caps by category to protect contribution margin and avoid reactive price wars.
            </p>

            <div className="consensus-grid">
              <article className="consensus-block">
                <h4>Why this is recommended</h4>
                <p>
                  It captures demand sensitivity without triggering broad discount dependency. The
                  model favors this route because it balances conversion lift with controlled downside
                  risk across cashflow, operational load, and margin stability.
                </p>
              </article>

              <article className="consensus-block">
                <h4>Business fit / expected impact</h4>
                <p>
                  Expected to improve weekly transaction momentum while maintaining margin discipline.
                  Forecast indicates healthier recovery velocity versus full price-match tactics, with
                  better sustainability over the next quarter.
                </p>
              </article>
            </div>
          </section>

          <section className="support-grid" aria-label="Supporting rationale cards">
            {supportingCards.map((card) => (
              <article key={card.title} className="support-card">
                <span className="support-badge">{card.badge}</span>
                <h4>{card.title}</h4>
                <p>{card.copy}</p>
              </article>
            ))}
          </section>

          <div className="synthesis-actions">
            <button
              type="button"
              className="secondary-action"
              onClick={() => navigate("/ai-debate")}
            >
              Back to War Room
            </button>
            <button
              type="button"
              className="primary-action"
              onClick={() => navigate("/campaign-roadmap")}
            >
              <span>Continue to Roadmap</span>
              <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
