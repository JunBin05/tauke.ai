import { useState, useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import "./SupervisorClarification.css";
import { API_BASE_URL } from "../config";

const navItems = [
    { label: "Store Setup", icon: "storefront", to: "/store-configuration" },
    { label: "Data Sync", icon: "sync", to: "/data-sync" },
    { label: "Analysis", icon: "insights", to: "/detective-analysis" },
    { label: "Clarification", icon: "forum", to: "/supervisor-clarification", active: true },
    { label: "War Room", icon: "groups", to: "/ai-debate" },
    { label: "Strategy Synthesis", icon: "hub", to: "/final-synthesis" }
];

export default function SupervisorClarification() {
    const navigate = useNavigate();
    const [selectedReason, setSelectedReason] = useState("mid_sem_break");
    const [notes, setNotes] = useState("");
    const [questions, setQuestions] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const ownerId = localStorage.getItem("owner_id");

    useEffect(() => {
        const fetchQuestions = async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/boardroom/start`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        merchant_id: ownerId,
                        target_month: "2026-04"
                    })
                });
                const data = await response.json();

                // ✅ Real response shape: { analyst_questions, financial_context, financial_trend, diagnostic_patterns }
                if (data.analyst_questions) {
                    // The AI returns a raw text block of questions — split by newline into an array
                    const questionLines = data.analyst_questions
                        .split("\n")
                        .map(q => q.replace(/^\d+[\.\)\s]+/, "").trim()) // strip "1. " or "1) "
                        .filter(q => q.length > 0);

                    setQuestions(questionLines);

                    // Save everything AIDebate will need
                    localStorage.setItem("boardroom_questions", JSON.stringify(questionLines));
                    localStorage.setItem("boardroom_financial_context", JSON.stringify(data.financial_context || {}));
                    localStorage.setItem("boardroom_financial_trend", JSON.stringify(data.financial_trend || {}));
                    localStorage.setItem("boardroom_diagnostic_patterns", JSON.stringify(data.diagnostic_patterns || {}));
                }
            } catch (err) {
                console.error("Failed to fetch boardroom questions:", err);
            } finally {
                setIsLoading(false);
            }
        };
        fetchQuestions();
    }, []);

    const handleSubmit = (event) => {
        event.preventDefault();
        localStorage.setItem("boss_answers", selectedReason === "other" ? notes : selectedReason);
        navigate("/ai-debate");
    };

    return (
        <div className="clarification-page">
            <main className="clarification-main">
                <div className="clarification-shell">
                    <header className="clarification-header">
                        <p className="step-label">Step 5 / Supervisor Agent</p>
                        <h2 className="page-title">Clarification Request</h2>
                        <p className="page-subtitle">The AI needs your confirmation before proceeding with strategic synthesis.</p>
                    </header>

                    <section className="featured-clarification-card" aria-label="Clarification card">
                        <span className="status-pill">
                            <span className="material-symbols-outlined" aria-hidden="true">priority_high</span>
                            Action Required
                        </span>

                        <h3 className="question-title">
                            {isLoading ? "AI is analyzing your data..."
                                : questions?.[0] ?? "We detected a 40% margin drop..."}
                        </h3>
                        <p className="question-subtitle">Your confirmation improves forecasting accuracy and aligns strategic next actions.</p>

                        <form className="clarification-form" onSubmit={handleSubmit}>
                            <label className="response-option">
                                <input
                                    type="radio"
                                    name="clarification_reason"
                                    value="mid_sem_break"
                                    checked={selectedReason === "mid_sem_break"}
                                    onChange={(event) => setSelectedReason(event.target.value)}
                                />
                                <div className="response-card">
                                    <div className="response-radio" aria-hidden="true" />
                                    <div className="response-copy">
                                        <h4>Confirm Mid-Sem Break</h4>
                                        <p>Known seasonal fluctuation in student area demand.</p>
                                    </div>
                                </div>
                            </label>

                            <label className="response-option">
                                <input
                                    type="radio"
                                    name="clarification_reason"
                                    value="supply_chain"
                                    checked={selectedReason === "supply_chain"}
                                    onChange={(event) => setSelectedReason(event.target.value)}
                                />
                                <div className="response-card">
                                    <div className="response-radio" aria-hidden="true" />
                                    <div className="response-copy">
                                        <h4>Supply Chain Issue</h4>
                                        <p>Unexpected cost increases or delayed replenishment.</p>
                                    </div>
                                </div>
                            </label>

                            <label className="response-option response-other">
                                <input
                                    type="radio"
                                    name="clarification_reason"
                                    value="other"
                                    checked={selectedReason === "other"}
                                    onChange={(event) => setSelectedReason(event.target.value)}
                                />
                                <div className="response-card">
                                    <div className="response-radio" aria-hidden="true" />
                                    <div className="response-copy">
                                        <h4>Other Context</h4>
                                        <p>Add brief operational context for better AI interpretation.</p>
                                    </div>
                                </div>
                                <div className="response-extra">
                                    <textarea
                                        rows="3"
                                        placeholder="Provide additional details for the AI..."
                                        value={notes}
                                        onChange={(event) => setNotes(event.target.value)}
                                    />
                                </div>
                            </label>

                            <div className="clarification-actions">
                                <button type="button" className="secondary-button">Remind Me Later</button>
                                <button type="submit" className="primary-button">
                                    <span>Continue</span>
                                    <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
                                </button>
                            </div>
                        </form>
                    </section>

                    <section className="support-cards" aria-label="Supporting context">
                        <article className="support-card">
                            <div className="support-icon" aria-hidden="true">
                                <span className="material-symbols-outlined">history</span>
                            </div>
                            <div>
                                <h4>Historical Context</h4>
                                <p>Last year, UM Mid-Sem break caused a similar 35% dip in revenue.</p>
                            </div>
                        </article>

                        <article className="support-card">
                            <div className="support-icon" aria-hidden="true">
                                <span className="material-symbols-outlined">inventory_2</span>
                            </div>
                            <div>
                                <h4>Supply Signals</h4>
                                <p>Vendor Alpha Corp reported minor delivery delays in the same period.</p>
                            </div>
                        </article>
                    </section>
                </div>
            </main>
        </div>
    );
}