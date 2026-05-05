/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useRef, useState, useEffect } from 'react';
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE_URL } from '../config';
import {
  Rocket,
  Shield,
  ArrowLeftRight,
  Filter,
  Download,
  X
} from 'lucide-react';

import './FinalSynthesis.css';
import './LoadingPage.css'; // Added for the loading state!

const Modal = ({ isOpen, onClose, onConfirm, title, children, confirmText = 'Acknowledge & Continue' }) => {
  return (
    <AnimatePresence>
      {isOpen && (
        <div className="modal-overlay" onClick={onClose}>
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="modal-card"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-body">
              <div className="modal-header">
                <h3 className="modal-title">{title}</h3>
                <button onClick={onConfirm} className="modal-close">
                  <X size={24} />
                </button>
              </div>
              <div className="modal-text">
                {children}
              </div>
              <div className="modal-footer">
                <button onClick={onConfirm} className="btn-modal">
                  {confirmText}
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

const StrategyCard = ({ strategy, onExecute }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      whileHover={{ y: -5 }}
      className={`strategy-card ${strategy.recommended ? 'recommended' : ''}`}
    >
      {strategy.recommended && (
        <div className="recommended-badge">Recommended</div>
      )}

      <div className="card-header">
        <div className="icon-box" style={{ backgroundColor: strategy.bgColor }}>
          <div style={{ color: strategy.accentColor }}>
            {strategy.icon}
          </div>
        </div>
        <span className="risk-tag" style={{ color: strategy.accentColor, backgroundColor: strategy.bgColor }}>
          {strategy.riskLevel}
        </span>
      </div>

      <h3 className="card-title">{strategy.title}</h3>
      <p className="card-description">{strategy.description}</p>

      <div className="card-footer">
        <span>Est. Growth</span>
        <span>{strategy.growth}</span>
      </div>

      <button
        onClick={() => onExecute(strategy)}
        className={`btn-execute ${strategy.recommended ? 'premium' : 'standard'}`}
      >
        Execute Campaign
      </button>
    </motion.div>
  );
};

// We define the visuals here so they perfectly map to the dynamic LLM data
const VISUAL_MAPPINGS = {
  aggressive: { icon: <Rocket size={24} fill="currentColor" />, accentColor: '#dc2626', bgColor: '#fef2f2' },
  hybrid: { icon: <ArrowLeftRight size={24} />, accentColor: '#0058bc', bgColor: '#eff6ff' },
  defensive: { icon: <Shield size={24} fill="currentColor" />, accentColor: '#64748b', bgColor: '#f1f5f9' }
};

export default function App() {
  const navigate = useNavigate();

  const [isLoading, setIsLoading] = useState(true);
  const [strategies, setStrategies] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [selectedStrategy, setSelectedStrategy] = useState(null); // Track what they clicked!

  const [modalState, setModalState] = useState({
    isOpen: false,
    title: '',
    content: null,
    onConfirmAction: null,
    confirmText: 'Acknowledge & Continue'
  });

  const reportRef = useRef(null);

  useEffect(() => {
    const fetchSynthesis = async () => {
      const ownerId = localStorage.getItem("owner_id");
      const targetMonth = localStorage.getItem("target_month");
      const bossAnswers = localStorage.getItem("boss_answers") || "";
      const debateStrategies = JSON.parse(localStorage.getItem("boardroom_debate_strategies") || "[]");
      
      
      if (!ownerId) {
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch(`${API_BASE_URL}/boardroom/synthesis`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            merchant_id: ownerId,
            target_month: targetMonth,
            boss_answers: bossAnswers,
            debate_strategies: debateStrategies
          })
        });

        const json = await response.json();

        if (json.status === "success" && json.data) {
          // Merge LLM data with your hardcoded colors and icons!
          const mappedStrategies = json.data.strategies.map(s => ({
            ...s,
            ...(VISUAL_MAPPINGS[s.id] || VISUAL_MAPPINGS.hybrid)
          }));

          setStrategies(mappedStrategies);
          setAnalysis(json.data.comparativeAnalysis);
        }
      } catch (error) {
        console.error("Failed to generate synthesis:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSynthesis();
  }, []);

  const openModal = (title, content, customConfirmAction = null, confirmText = 'Acknowledge & Continue') => {
    setModalState({ isOpen: true, title, content, onConfirmAction: customConfirmAction, confirmText });
  };

  const closeModal = () => {
    setModalState(prev => ({ ...prev, isOpen: false }));
  };

  const handleDownloadPDF = async () => {
    // 1. Grab the HTML element we want to convert
    const element = reportRef.current;
    if (!element) {
      alert("Report table is not ready yet!");
      return;
    }

    try {
      // 2. Take a high-quality hidden screenshot of the table
      const canvas = await html2canvas(element, { 
        scale: 2, // Makes the text sharp
        useCORS: true,
        backgroundColor: '#ffffff' 
      });
      
      const imgData = canvas.toDataURL('image/png');

      // 3. Create a new PDF document
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pdfWidth = pdf.internal.pageSize.getWidth();
      
      // Calculate height to maintain the correct aspect ratio
      const pdfHeight = (canvas.height * pdfWidth) / canvas.width;

      // 4. Paste the image into the PDF and save it!
      pdf.addImage(imgData, 'PNG', 0, 10, pdfWidth, pdfHeight);
      
      const targetMonth = localStorage.getItem("target_month") || "Report";
      pdf.save(`Tauke_Strategy_${targetMonth}.pdf`);

      // 5. Close the modal when done
      closeModal();
      
    } catch (error) {
      console.error("Failed to generate PDF:", error);
      alert("Error generating PDF.");
      closeModal();
    }
  };

  const handleConfirmAction = async (strategy) => {
    if (!strategy) {
      closeModal();
      return;
    }

    // 1. Immediately wipe any old roadmap data from previous simulations!
    localStorage.removeItem("swarm_roadmap");
    localStorage.removeItem("swarm_scenario");

    // 2. Update the modal to show a loading state
    setModalState(prev => ({
      ...prev,
      title: 'Generating Blueprint...',
      content: (
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <div className="loading-spinner" style={{ margin: '0 auto 16px' }} />
          <p>Translating the <strong>{strategy.title}</strong> strategy into an actionable AI roadmap...</p>
        </div>
      ),
      onConfirmAction: null // Disable button while loading
    }));

    try {
      const merchantId = localStorage.getItem("owner_id");
      const targetMonth = localStorage.getItem("target_month");

      // 3. Call your Roadmap API
      const response = await fetch(`${API_BASE_URL}/roadmap/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          merchant_id: merchantId,
          target_month: targetMonth,
          strategy_text: strategy.description,
          source: 'BOARDROOM',
          justification: `Executive Decision: Proceeding with ${strategy.title} strategy. Risk Level: ${strategy.riskLevel}. Expected Growth: ${strategy.growth}.`,
          financial_trend: {},
          diagnostic_patterns: {},
          external_signals: {}
        })
      });

      const json = await response.json();

      if (response.ok && json.status === "success") {
        // 4. Overwrite the main shared keys so the roadmap page picks it up perfectly!
        localStorage.setItem("ceo_verdict", JSON.stringify(strategy));
        localStorage.setItem("swarm_roadmap", JSON.stringify(json.roadmap));
        localStorage.setItem("swarm_scenario", `Executed Strategy: ${strategy.title}`);

        closeModal();
        navigate('/campaign-roadmap');
      } else {
        throw new Error(json.detail || "Failed to generate roadmap");
      }
    } catch (error) {
      console.error("Roadmap generation error:", error);
      setModalState(prev => ({
        ...prev,
        title: 'Generation Failed',
        content: <p style={{ color: '#ef4444' }}>Failed to generate the roadmap. Please try again.</p>,
        onConfirmAction: closeModal
      }));
    }
  };

  const handleExecute = (s) => {
    setSelectedStrategy(s); // Keep this for anything else that might need it
    openModal(
      `Executing ${s.title} Campaign`,
      <>
        <p>You are about to initiate the <strong>{s.title}</strong> market movement.</p>
        <div className="modal-quote">
          "Simulating 1.2M market iterations... Alignment confirmed."
        </div>
        <p>This path focuses on <span style={{ fontWeight: 600 }}>{s.growth} growth</span> with a
          <span style={{ color: s.accentColor, fontWeight: 700 }}> {s.riskLevel}</span> risk profile.</p>
      </>,
      () => handleConfirmAction(s) // <--- CRITICAL FIX: Pass 's' directly into the closure here
    );
  };

  // The Loading Screen perfectly mimics the transition flow you already built!
  if (isLoading) {
    return (
      <div className="loading-page" role="status" aria-live="polite">
        <div className="loading-glow" aria-hidden="true" />
        <main className="loading-content">
          <p className="loading-brand">Tauke.AI</p>
          <div className="loading-spinner-wrap" aria-hidden="true">
            <div className="loading-spinner" />
            <div className="loading-spinner-center" />
          </div>
          <h1 className="loading-title">Synthesizing Iterations...</h1>
          <p className="loading-subtitle">Formulating high-probability strategic vectors based on executive debate.</p>
        </main>
      </div>
    );
  }

  return (
    <div className="app-container">
      <main className="dashboard-main">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="hero-header"
        >
          <button
            onClick={() => openModal('Synthesis & Execution', 'This module synthesizes 1.2M market simulations into actionable strategic vectors.')}
            className="text-label-pill"
          >
            Synthesis & Execution
          </button>
          <h2 className="hero-title">Strategic Vectors</h2>
          <p className="hero-description">
            Tauke.AI has simulated 1.2M market iterations. Review the high-probability paths below to finalize your Q4 market positioning.
          </p>
        </motion.div>

        <div className="strategy-grid">
          {strategies.map((s) => (
            <StrategyCard key={s.id} strategy={s} onExecute={handleExecute} />
          ))}
        </div>

        {analysis && (
          <motion.div
            ref={reportRef}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="analysis-container"
          >
            <div className="analysis-header">
              <h3 className="analysis-title">Comparative Analysis</h3>
              <div className="tool-buttons">
                <button
                  onClick={() => openModal('Download Report', 'Preparing your strategic PDF export... Total size: 4.2MB', handleDownloadPDF, 'Download as PDF')}
                  className="btn-tool"
                >
                  <Download size={20} />
                </button>
              </div>
            </div>

            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th style={{ textAlign: 'center' }}>Aggressive</th>
                    <th className="active" style={{ textAlign: 'center' }}>Hybrid Pivot</th>
                    <th style={{ textAlign: 'center' }}>Defensive</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="row-label">Core Benefits</td>
                    <td className="cell-content" style={{ textAlign: 'center' }}>{analysis.corePros.aggressive}</td>
                    <td className="cell-content cell-active" style={{ textAlign: 'center' }}>{analysis.corePros.hybrid}</td>
                    <td className="cell-content" style={{ textAlign: 'center' }}>{analysis.corePros.defensive}</td>
                  </tr>
                  <tr>
                    <td className="row-label">Risk Factors</td>
                    <td className="cell-content" style={{ textAlign: 'center' }}>{analysis.riskFactors.aggressive}</td>
                    <td className="cell-content cell-active" style={{ textAlign: 'center' }}>{analysis.riskFactors.hybrid}</td>
                    <td className="cell-content" style={{ textAlign: 'center' }}>{analysis.riskFactors.defensive}</td>
                  </tr>
                  <tr>
                    <td className="row-label">Resource Loss</td>
                    <td>
                      <div className="progress-track">
                        <motion.div
                          initial={{ width: 0 }}
                          whileInView={{ width: `${parseInt(analysis.resourceDrain.aggressive) || 0}%` }}
                          transition={{ duration: 1, delay: 0.2 }}
                          className="progress-fill"
                          style={{ backgroundColor: '#ef4444' }}
                        />
                      </div>
                    </td>
                    <td>
                      <div className="progress-track">
                        <motion.div
                          initial={{ width: 0 }}
                          whileInView={{ width: `${parseInt(analysis.resourceDrain.aggressive) || 0}%` }}
                          transition={{ duration: 1, delay: 0.4 }}
                          className="progress-fill"
                          style={{ backgroundColor: '#0058bc' }}
                        />
                      </div>
                    </td>
                    <td>
                      <div className="progress-track">
                        <motion.div
                          initial={{ width: 0 }}
                          whileInView={{ width: `${parseInt(analysis.resourceDrain.aggressive) || 0}%` }}
                          transition={{ duration: 1, delay: 0.6 }}
                          className="progress-fill"
                          style={{ backgroundColor: '#cbd5e1' }}
                        />
                      </div>
                    </td>
                  </tr>
                  <tr>
                    <td className="row-label">Probability of Success</td>
                    <td className="prob-value">{analysis.probabilityOfSuccess.aggressive}</td>
                    <td className="prob-value prob-value-active">{analysis.probabilityOfSuccess.hybrid}</td>
                    <td className="prob-value">{analysis.probabilityOfSuccess.defensive}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </motion.div>
        )}

        <footer className="dashboard-footer">
          <div className="footer-links">
            <span style={{ color: '#64748b' }}>© 2024 Tauke.AI Corp.</span>
            <button
              onClick={() => openModal('Privacy Policy', 'Your data is encrypted with enterprise-grade AES-256.')}
              className="footer-btn"
            >
              Privacy Policy
            </button>
            <button
              onClick={() => openModal('Compliance Hub', 'Tauke.AI maintains SOC2 Type II, HIPAA, and GDPR compliance.')}
              className="footer-btn"
            >
              Compliance Hub
            </button>
          </div>
          <div className="system-status">
            <div className="status-pill">
              <span className="status-dot"></span>
              <span>System Live</span>
            </div>
            <span className="version-tag">v2.4.82-boutique</span>
          </div>
        </footer>
      </main>

      <Modal
        isOpen={modalState.isOpen}
        onClose={closeModal}
        onConfirm={modalState.onConfirmAction ? modalState.onConfirmAction : closeModal}
        title={modalState.title}
        confirmText={modalState.confirmText} 
      >
        {modalState.content}
      </Modal>
    </div>
  );
}