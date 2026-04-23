import { useNavigate } from "react-router-dom";
import "./AIDebate.css";

const debateItems = [
  {
    role: "Growth Hacker",
    icon: "trending_up",
    stance: "PROPOSE",
    copy:
      "I recommend immediate aggressive pricing for the student segment. Data shows high price sensitivity and immediate volume upside.",
    time: "10:42 AM",
    tone: "propose"
  },
  {
    role: "Risk Manager",
    icon: "shield",
    stance: "DISAGREE",
    copy:
      "Counter-point: This could lead to a 15% margin erosion if operational costs aren\u2019t offset. We need a phased rollout.",
    time: "10:43 AM",
    tone: "disagree"
  },
  {
    role: "Competitor Analyst",
    icon: "monitoring",
    stance: "AGREE W/ RISK",
    copy:
      "Agreed with Risk Manager. The Library Coffee just launched a similar loyalty program. We must differentiate on speed, not just price.",
    time: "10:44 AM",
    tone: "agree-risk"
  },
  {
    role: "Operations Chief",
    icon: "account_tree",
    stance: "CAUTION",
    copy:
      "Can we support the volume? F&B staff alignment is currently at 80%. A phased approach gives us time to hire.",
    time: "10:45 AM",
    tone: "caution"
  }
];

export default function AIDebate() {
  const navigate = useNavigate();

  return (
    <div className="war-room-page">
      <main className="war-room-main">
        <div className="war-room-shell">
          <div className="utility-row" aria-label="Top utilities">
            <label className="utility-search" aria-label="Search">
              <span className="material-symbols-outlined" aria-hidden="true">search</span>
              <input type="search" placeholder="Search debates, agents, or strategy notes" />
            </label>
            <div className="utility-icons">
              <button type="button" className="utility-icon-btn" aria-label="Notifications">
                <span className="material-symbols-outlined" aria-hidden="true">notifications</span>
              </button>
              <button type="button" className="utility-icon-btn" aria-label="Pinned items">
                <span className="material-symbols-outlined" aria-hidden="true">push_pin</span>
              </button>
              <button type="button" className="utility-icon-btn" aria-label="Settings">
                <span className="material-symbols-outlined" aria-hidden="true">settings</span>
              </button>
            </div>
          </div>

          <header className="war-room-header">
            <h2 className="war-room-title">AI Agent Debate War Room</h2>
            <p className="war-room-subtitle">Session: Q3 Pricing Strategy Optimization</p>
          </header>

          <section className="debate-panel" aria-label="AI debate war room">
            <div className="debate-panel-head">
              <h3 className="debate-panel-title">Live Strategic Debate</h3>
              <span className="agents-active-badge">4 Agents Active</span>
            </div>

            <div className="debate-feed">
              {debateItems.map((item, index) => {
                const isRight = index % 2 !== 0;
                return (
                  <div
                    key={item.role}
                    className={`debate-row-shell ${isRight ? "is-right" : "is-left"}`}
                  >
                    {/* Avatar always on the outer side */}
                    {!isRight && (
                      <div className="agent-avatar" aria-hidden="true">
                        <span className="material-symbols-outlined">{item.icon}</span>
                      </div>
                    )}

                    <div className="message-group">
                      <div className={`debate-row-header ${isRight ? "header-right" : ""}`}>
                        <div className="debate-row-top">
                          <p className="agent-name">{item.role}</p>
                          <span className={`stance-pill tone-${item.tone}`}>{item.stance}</span>
                        </div>
                        <time className="row-time">{item.time}</time>
                      </div>
                      <p className={`message-bubble ${isRight ? "bubble-right" : ""}`}>{item.copy}</p>
                    </div>

                    {isRight && (
                      <div className="agent-avatar" aria-hidden="true">
                        <span className="material-symbols-outlined">{item.icon}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="consensus-section">
              <p className="consensus-label">CONSENSUS STRENGTH</p>
              <div className="consensus-track" aria-hidden="true">
                <div className="consensus-fill" />
              </div>
              <div className="consensus-footer">
                <p className="consensus-text">Phased rollout emerging as dominant strategy.</p>
                <button
                  type="button"
                  className="primary-action"
                  onClick={() => navigate("/final-synthesis")}
                >
                  Proceed to Synthesis <span aria-hidden="true">&#x2192;</span>
                </button>
              </div>
            </div>

          </section>
        </div>
      </main>
    </div>
  );
}