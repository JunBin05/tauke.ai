import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2 } from "lucide-react";
import "./Landing.css";

export default function Landing() {
  const navigate = useNavigate();
  const [isTransitioning, setIsTransitioning] = useState(false);

  const handleAnalyseClick = (e) => {
    e.preventDefault();
    setIsTransitioning(true);
    
    // Wait 1.5 seconds for the premium animation to play out
    setTimeout(() => {
      // NOTE: I routed this to /sync based on your previous request. 
      // If they need to log in first, change this to "/login"!
      navigate("/data-sync"); 
    }, 1500);
  };

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

          {/* Changed from <Link> to a <button> to trigger the transition */}
          <button onClick={handleAnalyseClick} className="analyse-button" aria-label="Analyse Now">
            <span>Analyse Now</span>
            <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
          </button>
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

      {/* --- PREMIUM TRANSITION OVERLAY --- */}
      <AnimatePresence>
        {isTransitioning && (
          <motion.div
            initial={{ opacity: 0, backdropFilter: "blur(0px)" }}
            animate={{ opacity: 1, backdropFilter: "blur(12px)" }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              width: "100vw",
              height: "100vh",
              background: "rgba(255, 255, 255, 0.85)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 9999, // Ensures it covers everything
            }}
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
              style={{ marginBottom: "24px" }}
            >
              <Loader2 size={48} color="#0058bc" />
            </motion.div>

            <motion.h2
              initial={{ y: 10, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.2 }}
              style={{
                fontSize: "28px",
                fontWeight: 800,
                color: "#1a1c1d",
                marginBottom: "8px",
                fontFamily: "Inter, sans-serif"
              }}
            >
              Initializing AI Boardroom...
            </motion.h2>

            <motion.p
              initial={{ y: 10, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.4 }}
              style={{
                color: "#717786",
                fontSize: "16px",
                fontWeight: 500,
                fontFamily: "Inter, sans-serif"
              }}
            >
              Preparing secure data pipeline
            </motion.p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}