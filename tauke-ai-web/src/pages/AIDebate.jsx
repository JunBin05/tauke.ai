import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';
import './LoadingPage.css';
import {
  TrendingUp,
  ShieldAlert,
  GitMerge
} from 'lucide-react';

export default function AIDebate() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [strategies, setStrategies] = useState([]);

  useEffect(() => {
    const fetchDebate = async () => {
      const ownerId = localStorage.getItem("owner_id");
      const targetMonth = localStorage.getItem("target_month");
      const bossAnswers = localStorage.getItem("boss_answers") || "No additional context provided.";

      if (!ownerId) {
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch(`${API_BASE_URL}/boardroom/debate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            merchant_id: ownerId,
            target_month: targetMonth,
            boss_answers: bossAnswers
          })
        });

        const data = await response.json();

        if (data.status === "success") {
          setStrategies(data.strategies);
          // Save the debate to local storage so the CEO on the next page can read it!
          localStorage.setItem("boardroom_debate_strategies", JSON.stringify(data.strategies));
        }
      } catch (error) {
        console.error("Debate generation failed:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDebate();
  }, []);

  if (isLoading) {
    return (
      <div className="loading-page" role="status" aria-live="polite">
        <div className="loading-glow" aria-hidden="true" />
        <main className="loading-content">
          <p className="loading-brand">Tauke.AI War Room</p>
          <div className="loading-spinner-wrap" aria-hidden="true">
            <div className="loading-spinner" />
            <div className="loading-spinner-center" />
          </div>
          <h1 className="loading-title">Summoning the Board...</h1>
          <p className="loading-subtitle">The AI CMO, COO, and CFO are currently debating your sales data.</p>
        </main>
      </div>
    );
  }

  return (
    <div style={{ padding: '40px 20px', maxWidth: '1200px', margin: '0 auto', fontFamily: 'system-ui, sans-serif' }}>

      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '48px' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', backgroundColor: '#eff6ff', color: 'var(--primary, #0058bc)', padding: '8px 16px', borderRadius: '20px', fontWeight: 'bold', fontSize: '14px', marginBottom: '16px' }}>
          <div className="pulse-dot" style={{ width: '8px', height: '8px', backgroundColor: 'var(--primary, #0058bc)', borderRadius: '50%' }} />
          Executive Debate
        </div>
        <h1 style={{ fontSize: '36px', color: '#0f172a', margin: '0 0 12px 0', letterSpacing: '-0.5px' }}>The War Room</h1>
        <p style={{ color: '#64748b', fontSize: '18px', margin: 0 }}>Your AI board members have analyzed the signals and formulated their competing strategies.</p>
      </div>

      {/* The 3 Competing Strategies (CHAT BUBBLE UI) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', maxWidth: '800px', margin: '0 auto', marginBottom: '48px' }}>
        {strategies.map((strat, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              gap: '16px',
              alignItems: 'flex-start',
              flexDirection: idx === 1 ? 'row-reverse' : 'row'
            }}
          >

            {/* Avatar Profile Picture */}
            <div style={{
              width: '56px', height: '56px', borderRadius: '50%',
              backgroundColor: idx === 0 ? '#dbeafe' : idx === 1 ? '#fee2e2' : '#f3e8ff',
              color: idx === 0 ? '#2563eb' : idx === 1 ? '#dc2626' : '#9333ea',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
            }}>
              {idx === 0 ? <TrendingUp size={28} /> : idx === 1 ? <ShieldAlert size={28} /> : <GitMerge size={28} />}
            </div>

            {/* The Chat Bubble */}
            <div style={{
              backgroundColor: '#ffffff',
              borderRadius: idx === 1 ? '16px 2px 16px 16px' : '2px 16px 16px 16px',
              padding: '24px',
              border: '1px solid #e2e8f0',
              boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)',
              flex: 1
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ fontWeight: '800', color: '#0f172a', fontSize: '15px' }}>
                  {strat.role} <span style={{ color: '#94a3b8', fontWeight: '500', fontSize: '13px', marginLeft: '4px' }}>says...</span>
                </span>

                <span style={{
                  fontSize: '12px', fontWeight: '700',
                  color: strat.tone === 'up' ? '#16a34a' : strat.tone === 'down' ? '#dc2626' : '#0058bc',
                  backgroundColor: strat.tone === 'up' ? '#f0fdf4' : strat.tone === 'down' ? '#fef2f2' : '#eff6ff',
                  padding: '4px 10px', borderRadius: '12px'
                }}>
                  {strat.indicatorLabel}: {strat.indicatorValue}
                </span>
              </div>

              <h4 style={{ margin: '0 0 8px 0', fontSize: '17px', color: '#1e293b' }}>{strat.stance}</h4>
              <p style={{ margin: 0, color: '#475569', lineHeight: '1.6', fontSize: '15px' }}>
                "{strat.copy}"
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* The Bridge to the CEO */}
      <div style={{ display: 'flex', justifyContent: 'center', borderTop: '1px solid #e2e8f0', paddingTop: '40px' }}>
        <button
          onClick={() => navigate('/final-synthesis')}
          style={{
            display: 'flex', alignItems: 'center', gap: '12px',
            padding: '16px 32px', borderRadius: '12px',
            background: 'var(--primary, #0058bc)', color: '#fff',
            border: 'none', fontSize: '16px', fontWeight: 700,
            cursor: 'pointer', boxShadow: '0 4px 12px rgba(0, 88, 188, 0.2)'
          }}
        >
          <span>Request CEO Final Verdict</span>
          <span className="material-symbols-outlined" style={{ fontSize: '22px' }}>gavel</span>
        </button>
      </div>

    </div>
  );
}