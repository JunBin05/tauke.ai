import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../config";
import "./LoadingPage.css";

export default function LoadingPage() {
  const navigate = useNavigate();
  const hasFetched = useRef(false);

  useEffect(() => {
    // Prevent React StrictMode from firing the LLM twice
    if (hasFetched.current) return;
    hasFetched.current = true;

    const ownerId = localStorage.getItem("owner_id");
    const targetMonth = localStorage.getItem("target_month") || "2026-04";

    const fetchQuestions = async () => {
      try {
        // 1. Call the LLM to generate the questions
        const response = await fetch(`${API_BASE_URL}/boardroom/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            merchant_id: ownerId,
            target_month: targetMonth
          })
        });

        const data = await response.json();

        if (data.analyst_questions) {
          // 2. Save the AI's questions to localStorage so the next page can read them instantly
          localStorage.setItem("boardroom_questions", JSON.stringify(data.analyst_questions));
          localStorage.setItem("boardroom_financial_context", JSON.stringify(data.financial_context || {}));
          localStorage.setItem("boardroom_financial_trend", JSON.stringify(data.financial_trend || {}));
          localStorage.setItem("boardroom_diagnostic_patterns", JSON.stringify(data.diagnostic_patterns || {}));
        }
      } catch (err) {
        console.error("Failed to fetch boardroom questions during loading:", err);
      } finally {
        // 3. ONLY navigate to the Clarification page once the LLM is totally finished!
        navigate("/supervisor-clarification");
      }
    };

    fetchQuestions();
  }, [navigate]);

  return (
    <div className="loading-page" role="status" aria-live="polite">
      <div className="loading-glow" aria-hidden="true" />
      <main className="loading-content">
        <p className="loading-brand">Tauke.AI</p>
        <div className="loading-spinner-wrap" aria-hidden="true">
          <div className="loading-spinner" />
          <div className="loading-spinner-center" />
        </div>
        <h1 className="loading-title">Analyzing your data...</h1>
        <p className="loading-subtitle">The AI is reviewing your records and formulating questions.</p>
      </main>
    </div>
  );
}