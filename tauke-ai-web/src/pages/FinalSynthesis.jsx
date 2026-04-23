import { useState, useEffect } from "react";
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

// Fallback content — shown if no debate data exists in localStorage
const FALLBACK_WINNER = {
  role: "Consensus",
  strategy: "Targeted Value Bundle With Guardrailed Promotions",
  argument_for:
    "It captures demand sensitivity without triggering broad discount dependency. The model favors this route because it balances conversion lift with controlled downside risk across cashflow, operational load, and margin stability.",
  argument_against:
    "Expected to improve weekly transaction momentum while maintaining margin discipline. Forecast indicates healthier recovery velocity versus full price-match tactics.",
  projected_profit_impact: "+RM 1,200 est."
};

const FALLBACK_SUPPORTING_CARDS = [
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

  // ── Read what AIDebate saved into localStorage ──────────────────────────
  const [winner, setWinner] = useState(null);
  const [strategies, setStrategies] = useState([]);

  useEffect(() => {
    // Read the winning strategy that AIDebate.jsx saved
    const savedWinner = localStorage.getItem("debate_winner");
    const savedStrategies = localStorage.getItem("debate_strategies");

    if (savedWinner) {
      try {
        setWinner(JSON.parse(savedWinner));
      } catch {
        // If JSON is malformed, fall back to defaults
        setWinner(FALLBACK_WINNER);
      }
    }

    if (savedStrategies) {
      try {
        setStrategies(JSON.parse(savedStrategies));
      } catch {
        setStrategies([]);
      }
    }
  }, []);

  // Use live data if available, otherwise use fallback
  const displayWinner = winner ?? FALLBACK_WINNER;

  // Build supporting cards from the LOSING strategies (the ones not chosen)
  // These become the "why we didn't pick those" rationale cards
  const supportingCards =
    strategies.length > 1
      ? strategies
          .filter((s) => s.role !== displayWinner.role)
          .slice(0, 3)
          .map((s) => ({
            title: `Why not: ${s.role}'s plan`,
            copy: s.argument_against || s.copy || "Not selected due to risk profile.",
            badge: s.stance || s.role
          }))
      : FALLBACK_SUPPORTING_CARDS;

  // ── On "Continue to Roadmap" — save the chosen strategy ────────────────
  const handleContinue = () => {
    localStorage.setItem("chosen_strategy", JSON.stringify(displayWinner));
    navigate("/campaign-roadmap");
  };

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

            {/* ── Live winner title from AIDebate, fallback if not available ── */}
            <h3 className="consensus-title">
              {displayWinner.strategy}
            </h3>

            <div className="consensus-grid">
              <article className="consensus-block">
                <h4>Why this is recommended</h4>
                <p>{displayWinner.argument_for}</p>
              </article>

              <article className="consensus-block">
                <h4>Business fit / expected impact</h4>
                <p>
                  {displayWinner.argument_against}
                  {displayWinner.projected_profit_impact && (
                    <strong style={{ display: "block", marginTop: "8px", color: "#006e28" }}>
                      Projected impact: {displayWinner.projected_profit_impact}
                    </strong>
                  )}
                </p>
              </article>
            </div>
          </section>

          {/* ── Supporting rationale cards (the rejected strategies) ── */}
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
              onClick={handleContinue}
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
