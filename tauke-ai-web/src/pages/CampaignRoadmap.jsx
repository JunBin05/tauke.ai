import { useState, useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import "./CampaignRoadmap.css";
import { API_BASE_URL } from "../config";

const navItems = [
  { label: "Store Setup", icon: "storefront", to: "/store-configuration" },
  { label: "Data Sync", icon: "sync", to: "/data-sync" },
  { label: "Analysis", icon: "insights", to: "/detective-analysis" },
  { label: "Clarification", icon: "forum", to: "/supervisor-clarification" },
  { label: "War Room", icon: "groups", to: "/ai-debate" },
  { label: "Strategy Synthesis", icon: "hub", to: "/final-synthesis", active: true }
];

// Fallback phases — shown while AI generates OR if API fails
const FALLBACK_PHASES = [
  {
    phase_number: 1,
    title: "Campaign Setup And Offer Configuration",
    tasks: [
      "Finalize bundle composition and promotion guardrails",
      "Prepare channel-level message templates for a controlled launch",
      "Brief all staff on the promotion rules and POS discount codes"
    ],
    status: "Upcoming",
    tone: "next"
  },
  {
    phase_number: 2,
    title: "Pilot Launch In High-Volume Time Slots",
    tasks: [
      "Deploy promotion in selected time windows to validate demand response",
      "Monitor daily sales vs baseline and check margin hasn't dropped below 20%",
      "Track queue handling and customer feedback"
    ],
    status: "Upcoming",
    tone: "next"
  },
  {
    phase_number: 3,
    title: "Performance Review And Guardrail Adjustment",
    tasks: [
      "Review conversion rate, average order value, and contribution margin",
      "Tune category caps and inventory pacing based on results",
      "Schedule KPI checkpoint with finance team"
    ],
    status: "Upcoming",
    tone: "next"
  },
  {
    phase_number: 4,
    title: "Scaled Rollout With Weekly Optimization",
    tasks: [
      "Expand execution across all targeted windows",
      "Set weekly optimization loops and clear stop-loss triggers",
      "Report results to regional manager"
    ],
    status: "Queued",
    tone: "next"
  }
];

// Map phase index → tone for the timeline dots
function getPhaseTone(index, totalPhases) {
  if (index === 0) return "done";         // First phase = ready to start
  if (index === 1) return "active";       // Second phase = in progress
  return "next";                          // Rest = upcoming
}

export default function CampaignRoadmap() {
  const navigate = useNavigate();

  // ── State: roadmap from AI + chosen strategy from localStorage ──────────
  const [roadmap, setRoadmap] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState(null);

  const ownerId = localStorage.getItem("owner_id");
  const chosenStrategy = (() => {
    try {
      return JSON.parse(localStorage.getItem("chosen_strategy") || "{}");
    } catch {
      return {};
    }
  })();

  // ── Call /roadmap/generate on mount ────────────────────────────────────
  useEffect(() => {
    const generateRoadmap = async () => {
      // If no chosen strategy, skip API and show fallback
      if (!chosenStrategy?.strategy && !chosenStrategy?.copy) {
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch(`${API_BASE_URL}/roadmap/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            merchant_id: ownerId,
            target_month: "2026-04",
            source: "BOARDROOM",
            // strategy_text = the strategy title/copy
            strategy_text: chosenStrategy.strategy || chosenStrategy.copy || "Optimize business operations",
            // justification = why the AI chose it
            justification: chosenStrategy.argument_for || chosenStrategy.copy || "Recommended by AI consensus",
            external_signals: {},
            financial_trend: {},
            diagnostic_patterns: {}
          })
        });

        const data = await response.json();

        if (data.status === "success") {
          setRoadmap(data.roadmap);
        } else {
          setErrorMsg("AI could not generate a roadmap. Showing default plan.");
        }
      } catch (err) {
        console.error("Roadmap generation failed:", err);
        setErrorMsg("Connection error. Showing default plan.");
      } finally {
        setIsLoading(false);
      }
    };

    generateRoadmap();
  }, []); // runs once when page loads

  // ── Use live roadmap if available, otherwise use fallback ───────────────
  const phases = roadmap?.phases ?? FALLBACK_PHASES;
  const totalDays = roadmap?.estimated_total_days ?? 28;
  const totalPhases = phases.length;

  return (
    <div className="roadmap-page">
      <main className="roadmap-main">
        <div className="roadmap-shell">
          <header className="roadmap-header">
            <p className="roadmap-step">STEP 8 / EXECUTION ROADMAP</p>
            <h2 className="roadmap-title">Campaign Roadmap</h2>
            <p className="roadmap-subtitle">
              The final strategy has now been translated into a practical execution plan with clear
              milestones and measurable delivery checkpoints.
            </p>
            {/* Show strategy title if we have it */}
            {chosenStrategy?.strategy && (
              <p style={{ marginTop: "8px", fontSize: "14px", color: "#0058bc", fontWeight: 700 }}>
                ✅ Executing: {chosenStrategy.strategy}
              </p>
            )}
            {/* Error message if API failed but we're showing fallback */}
            {errorMsg && (
              <p style={{ marginTop: "8px", fontSize: "13px", color: "#ba1a1a" }}>
                ⚠️ {errorMsg}
              </p>
            )}
          </header>

          <section className="roadmap-layout" aria-label="Execution roadmap layout">
            <div className="timeline-column">
              <div className="timeline-head">
                <h3>Execution Timeline</h3>
                <span className="timeline-head-pill">
                  {isLoading ? "Generating..." : `${totalDays} day plan`}
                </span>
              </div>

              {/* Loading state */}
              {isLoading && (
                <div style={{ textAlign: "center", padding: "40px", color: "#717786" }}>
                  ⏳ AI is building your personalised action plan...
                </div>
              )}

              {/* Phase timeline — live from AI or fallback */}
              {!isLoading && (
                <ol className="timeline-list">
                  {phases.map((phase, index) => {
                    const tone = phase.tone ?? getPhaseTone(index, totalPhases);
                    const phaseLabel = `Phase ${phase.phase_number ?? index + 1}`;

                    return (
                      <li className="timeline-item" key={phase.title ?? phaseLabel}>
                        <div className="timeline-rail" aria-hidden="true">
                          <span className={`timeline-dot tone-${tone}`} />
                          {index < phases.length - 1 && <span className="timeline-line" />}
                        </div>

                        <article className="phase-card">
                          <div className="phase-top-row">
                            <p className="phase-label">{phaseLabel}</p>
                            <span className={`phase-status tone-${tone}`}>
                              {tone === "done" ? "Ready" : tone === "active" ? "In Progress" : "Upcoming"}
                            </span>
                          </div>

                          <h4 className="phase-title">{phase.title}</h4>

                          {/* Tasks as a bullet list */}
                          {phase.tasks && Array.isArray(phase.tasks) && (
                            <ul style={{ margin: "8px 0 0 0", paddingLeft: "18px" }}>
                              {phase.tasks.map((task, taskIdx) => (
                                <li
                                  key={taskIdx}
                                  style={{ fontSize: "13px", color: "#414755", marginBottom: "4px", lineHeight: 1.5 }}
                                >
                                  {task}
                                </li>
                              ))}
                            </ul>
                          )}

                          {/* Legacy description fallback */}
                          {phase.description && !phase.tasks && (
                            <p className="phase-description">{phase.description}</p>
                          )}
                        </article>
                      </li>
                    );
                  })}
                </ol>
              )}
            </div>

            <aside className="summary-column" aria-label="Progress summary">
              <section className="summary-card">
                <p className="summary-kicker">Execution plan</p>
                <h3 className="summary-value">{totalPhases} Phases</h3>
                <p className="summary-copy">
                  {isLoading
                    ? "Generating your personalised roadmap..."
                    : `${totalDays}-day execution plan tailored to your strategy.`}
                </p>

                <div className="summary-track" aria-hidden="true">
                  <span className="summary-fill" style={{ width: "25%" }} />
                </div>

                <div className="summary-list">
                  <div className="summary-row">
                    <span>Total phases</span>
                    <strong>{totalPhases}</strong>
                  </div>
                  <div className="summary-row">
                    <span>Estimated duration</span>
                    <strong>{totalDays} days</strong>
                  </div>
                  <div className="summary-row">
                    <span>Strategy source</span>
                    <strong>{chosenStrategy?.role || "AI Consensus"}</strong>
                  </div>
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
