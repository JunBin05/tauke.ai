/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom'; // Add this line
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Rocket, 
  Shield, 
  ArrowLeftRight, 
  Filter, 
  Download,
  X
} from 'lucide-react';

import './FinalSynthesis.css';

const Modal = ({ isOpen, onClose, onConfirm, title, children }) => {
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
                {/* Change onClose to onConfirm here! */}
                <button onClick={onConfirm} className="btn-modal">
                  Acknowledge & Continue
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

export default function App() {
  const navigate = useNavigate(); // Initialize navigation

  const [modalState, setModalState] = useState({
    isOpen: false,
    title: '',
    content: null,
    onConfirmAction: null // Add this line
  });

  // Update openModal to accept a third parameter
  const openModal = (title, content, customConfirmAction = null) => {
    setModalState({ isOpen: true, title, content, onConfirmAction: customConfirmAction });
  };

  const closeModal = () => {
    setModalState(prev => ({ ...prev, isOpen: false }));
  };

  const strategies = [
    {
      id: 'aggressive',
      title: 'Aggressive',
      description: 'Front-load capital for market dominance. Prioritizes rapid user acquisition over short-term burn rates.',
      growth: '+142%',
      riskLevel: 'HIGH RISK',
      icon: <Rocket size={24} fill="currentColor" />,
      accentColor: '#dc2626',
      bgColor: '#fef2f2'
    },
    {
      id: 'hybrid',
      title: 'Hybrid Pivot',
      description: 'Shift focus to Enterprise-tier integrations while maintaining existing B2C stability. Balanced liquidity approach.',
      growth: '+88%',
      riskLevel: 'OPTIMIZED',
      recommended: true,
      icon: <ArrowLeftRight size={24} />,
      accentColor: '#0058bc',
      bgColor: '#eff6ff'
    },
    {
      id: 'defensive',
      title: 'Defensive',
      description: 'Asset protection and yield optimization. Focuses on retention and infrastructure stability during volatility.',
      growth: '+22%',
      riskLevel: 'CONSERVATIVE',
      icon: <Shield size={24} fill="currentColor" />,
      accentColor: '#64748b',
      bgColor: '#f1f5f9'
    }
  ];

  const handleConfirmAction = () => {
    closeModal();
    navigate('/campaign-roadmap'); 
  };

  const handleExecute = (s) => {
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
      handleConfirmAction // Add this here!
    );
  };

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

        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="analysis-container"
        >
          <div className="analysis-header">
            <h3 className="analysis-title">Comparative Analysis</h3>
            <div className="tool-buttons">
              <button 
                onClick={() => openModal('Filters', 'Advanced filtering options for comparative metrics will appear here.')}
                className="btn-tool"
              >
                <Filter size={20} />
              </button>
              <button 
                onClick={() => openModal('Download Report', 'Preparing your strategic PDF export... Total size: 4.2MB')}
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
                  <td className="row-label">Core Pros</td>
                  <td className="cell-content" style={{ textAlign: 'center' }}>Total Market Cap Capture, Talent Drain</td>
                  <td className="cell-content cell-active" style={{ textAlign: 'center' }}>Sustainable Unit Economics, Agility</td>
                  <td className="cell-content" style={{ textAlign: 'center' }}>Max Dividend Yield, Low Burn</td>
                </tr>
                <tr>
                  <td className="row-label">Risk Factors</td>
                  <td className="cell-content" style={{ textAlign: 'center' }}>Cash Exhaustion &lt; 6 Months</td>
                  <td className="cell-content cell-active" style={{ textAlign: 'center' }}>Operational Friction (Mid-Shift)</td>
                  <td className="cell-content" style={{ textAlign: 'center' }}>Market Irrelevance in 24 Months</td>
                </tr>
                <tr>
                  <td className="row-label">Resource Drain</td>
                  <td>
                    <div className="progress-track">
                      <motion.div 
                        initial={{ width: 0 }}
                        whileInView={{ width: '100%' }}
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
                        whileInView={{ width: '60%' }}
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
                        whileInView={{ width: '25%' }}
                        transition={{ duration: 1, delay: 0.6 }}
                        className="progress-fill"
                        style={{ backgroundColor: '#cbd5e1' }}
                      />
                    </div>
                  </td>
                </tr>
                <tr>
                  <td className="row-label">Probability of Success</td>
                  <td className="prob-value">34%</td>
                  <td className="prob-value prob-value-active">81%</td>
                  <td className="prob-value">94%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </motion.div>

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
        // Use the custom action if it exists, otherwise just close the modal
        onConfirm={modalState.onConfirmAction ? modalState.onConfirmAction : closeModal} 
        title={modalState.title}
      >
        {modalState.content}
      </Modal>
    </div>
  );
}
