import { useState, useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import "./AIDebate.css";
import { API_BASE_URL } from "../config";

const navItems = [
  { label: "Store Setup", icon: "storefront", to: "/store-configuration" },
  { label: "Data Sync", icon: "sync", to: "/data-sync" },
  { label: "Analysis", icon: "insights", to: "/detective-analysis" },
  { label: "Clarification", icon: "forum", to: "/supervisor-clarification" },
  { label: "War Room", icon: "groups", to: "/ai-debate", active: true },
  { label: "Strategy Synthesis", icon: "hub", to: "/final-synthesis" }
];

// Fallback hardcoded debate — shown while AI loads OR if API fails
const FALLBACK_DEBATE_ITEMS = [
  {
    role: "Growth Hacker",
    icon: "trending_up",
    stance: "Aggressive Push",
    copy: "Launch a 10-day student combo with limited-time urgency. Demand elasticity is still favorable and can recover top-line quickly.",
    indicatorLabel: "Impact",
    indicatorValue: "+18% traffic potential",
    tone: "up"
  },
  {
    role: "Risk Manager",
    icon: "shield",
    stance: "Margin Protection",
    copy: "Price compression beyond 7% may erode unit economics. If promoted, cap discounts by category and enforce daily margin guardrails.",
    indicatorLabel: "Risk",
    indicatorValue: "High if uncapped",
    tone: "down"
  },
  {
    role: "Competitor Analyst",
    icon: "monitoring",
    stance: "Differentiated Offer",
    copy: "Primary competitor is discounting drinks only. Bundle speed and reliability into our offer to avoid a direct price war.",
    indicatorLabel: "Evidence",
    indicatorValue: "3 nearby campaigns tracked",
    tone: "neutral"
  },
  {
    role: "Operations Chief",
    icon: "account_tree",
    stance: "Phased Rollout",
    copy: "Run pilot in two high-volume slots first. Operational readiness is moderate, and phased rollout reduces queue and staffing risk.",
    indicatorLabel: "Readiness",
    indicatorValue: "82% staffing coverage",
    tone: "up"
  }
];

export default function AIDebate() {
  const navigate = useNavigate();

  // ── State lives INSIDE the component function ──────────────────────────
  const [debateData, setDebateData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const ownerId = localStorage.getItem("owner_id");
  const bossAnswers = localStorage.getItem("boss_answers");

  // ── Fetch live AI debate on mount ───────────────────────────────────────
  useEffect(() => {
    const runDebate = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/boardroom/debate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            merchant_id: ownerId,
            target_month: "2026-04",
            boss_answers: bossAnswers || "No additional context provided."
          })
        });
        const data = await response.json();

        if (data.status === "success") {
          setDebateData(data.strategies);
          // Save the winning strategy for FinalSynthesis!
          localStorage.setItem("debate_strategies", JSON.stringify(data.strategies));
          localStorage.setItem("debate_winner", JSON.stringify(data.recommended_strategy));
        }
      } catch (err) {
        console.error("Debate failed:", err);
        // On error, debateData stays null → fallback UI is shown
      } finally {
        setIsLoading(false);
      }
    };

    runDebate();
  }, []); // runs once when the page loads

  // ── Use live data if available, otherwise use fallback ─────────────────
  const displayItems = debateData ?? FALLBACK_DEBATE_ITEMS;

  return (
    <div className="war-room-page">
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
                <p className="status-value">
                  {isLoading ? "AI agents are deliberating..." : "Evaluation complete"}
                </p>
                <div className="status-track" aria-hidden="true">
                  <div className="status-fill" />
                </div>
              </div>
            </div>

            {/* Loading state */}
            {isLoading && (
              <div style={{ textAlign: "center", padding: "40px", color: "#717786" }}>
                ⏳ AI personas are debating your strategy...
              </div>
            )}

            {/* Debate cards — live from AI or fallback */}
            {!isLoading && (
              <div className="debate-feed">
                {displayItems.map((item) => (
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
            )}

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
