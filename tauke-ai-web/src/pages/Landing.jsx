import { Link } from "react-router-dom";
import "./Landing.css";

export default function Landing() {
  return (
    <div className="landing-page">
      <main className="landing-hero" aria-label="Hero section">
        <div className="hero-glow" aria-hidden="true" />

        <div className="hero-content">
          <p className="hero-brand">Tauke.AI</p>
          <h1 className="hero-title">Every Missed Signal Costs a Business Opportunity</h1>
          <p className="hero-subtitle">
            Tauke.AI helps you detect what changed, understand why it matters, and act before competitors do.
          </p>

          <Link to="/login" className="analyse-button" aria-label="Analyse Now">
            <span>Analyse Now</span>
            <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
          </Link>
        </div>
      </main>

      <footer className="landing-footer">
        <div className="footer-shell">
          <p className="footer-copy">© 2026 Tauke.AI. Precision Intelligence.</p>
          <div className="footer-links">
            <a href="#">Privacy Policy</a>
            <a href="#">Terms of Service</a>
            <a href="#">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
