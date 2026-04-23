import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./LoadingPage.css";

export default function LoadingPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      navigate("/supervisor-clarification");
    }, 2200);

    return () => {
      window.clearTimeout(timeoutId);
    };
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

        <h1 className="loading-title">Preparing your intelligence workspace...</h1>
        <p className="loading-subtitle">Syncing your business context and loading analysis modules.</p>
      </main>
    </div>
  );
}
