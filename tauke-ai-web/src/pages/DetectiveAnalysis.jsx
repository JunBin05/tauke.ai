import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './DetectiveAnalysis.css';
import './LoadingPage.css'; // 👈 ADD THIS LINE
import { 
  LayoutDashboard, 
  Settings, 
  HelpCircle, 
  Bell, 
  ChevronDown,
  TrendingUp,
  AlertCircle,
  Users,
  Package
} from 'lucide-react';
import { EXTERNAL_INTELLIGENCE, PERFORMANCE_SUMMARIES } from './data';
import { API_BASE_URL } from '../config'; 
import { motion, AnimatePresence } from 'framer-motion';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer
} from 'recharts';

const AVAILABLE_MONTHS = [
  "Apr 2026", "Mar 2026", "Feb 2026", "Jan 2026", 
  "Dec 2025", "Nov 2025"
];

const InsightRow = ({ item }) => {
  const Icon = item.type === 'growth' ? TrendingUp : item.type === 'efficiency' ? Package : AlertCircle;
  
  return (
    <div className={`insight-row ${item.type}`}>
      <div className="insight-icon-container">
        <Icon className="w-5 h-5" />
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
          <h4 className="card-title" style={{ fontSize: '14px' }}>{item.title}</h4>
        </div>
        <p className="card-subtitle" style={{ fontSize: '14px' }}>{item.message}</p>
      </div>
    </div>
  );
};

const PerformanceSummaryList = ({ summary, month }) => (
  <motion.div
    key={month}
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    className="summary-card"
  >
    <div className="summary-header">
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div className="intelligence-icon" style={{ width: '48px', height: '48px', borderRadius: '12px' }}>
          <LayoutDashboard className="w-6 h-6" />
        </div>
        <div>
          <h3 className="card-title">Performance Summary: {month}</h3>
          <p className="card-subtitle" style={{ fontWeight: '500' }}>{summary.headline} • {summary.subheadline}</p>
        </div>
      </div>

      <div className="summary-score-display">
        <span className="score-label">Performance Score</span>
        <div>
          <span className="score-value">{summary.score}</span>
          <span className="score-max">/ 10</span>
        </div>
      </div>
    </div>

    <div className="insight-list">
      {summary.insights.map(item => (
        <InsightRow key={item.id} item={item} />
      ))}
    </div>
  </motion.div>
);

export default function DetectiveAnalysis() {
  const navigate = useNavigate();
  const [selectedMonth, setSelectedMonth] = useState(AVAILABLE_MONTHS[0]);
  const [isMonthDropdownOpen, setIsMonthDropdownOpen] = useState(false);

  const [chartData, setChartData] = useState([]);
  const [isLoadingChart, setIsLoadingChart] = useState(true);

  const [performanceSummary, setPerformanceSummary] = useState(null);
  const [externalIntelligence, setExternalIntelligence] = useState([]);
  const [isLoadingCards, setIsLoadingCards] = useState(true);

  // --- TIMER STATE FOR ROTATING CARDS ---
  const [activeIntelIndex, setActiveIntelIndex] = useState(0);

  const ownerId = localStorage.getItem("owner_id");

  // Format month for backend API calls
  const getApiMonth = (displayMonth) => {
    try {
      const [monthName, year] = displayMonth.split(" ");
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const monthNumber = months.indexOf(monthName) + 1;
      const formattedMonth = monthNumber.toString().padStart(2, '0');
      return `${year}-${formattedMonth}`;
    } catch (e) {
      return "2026-04";
    }
  };

  // --- AUTO-ROTATE EFFECT ---
  useEffect(() => {
    // Only run the timer if we have more than 1 card to show
    if (!externalIntelligence || externalIntelligence.length <= 1) return;

    const timer = setInterval(() => {
      setActiveIntelIndex((prevIndex) => (prevIndex + 1) % externalIntelligence.length);
    }, 5000); // Switches every 5 seconds

    return () => clearInterval(timer);
  }, [externalIntelligence]);

  // Grab the active card to render
  const currentIntel = externalIntelligence && externalIntelligence.length > 0 
      ? externalIntelligence[activeIntelIndex] 
      : null;

  useEffect(() => {
    const apiMonth = getApiMonth(selectedMonth);
    // Save selected month globally so War Room uses the exact same data
    localStorage.setItem("target_month", apiMonth);

    if (!ownerId) {
      setIsLoadingChart(false);
      setIsLoadingCards(false);
      return;
    }

    // 1. Fetch Area Chart Trend Data
    const fetchTrend = async () => {
      setIsLoadingChart(true);
      try {
        const response = await fetch(`${API_BASE_URL}/boardroom/trend/${ownerId}/${apiMonth}`);
        const data = await response.json();
        
        if (data.status === "success") {
          const [monthName, yearName] = selectedMonth.split(" ");
          const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
          const monthIndex = months.indexOf(monthName);
          const daysInMonth = new Date(parseInt(yearName), monthIndex + 1, 0).getDate();
          
          const fullMonthData = Array.from({ length: daysInMonth }, (_, i) => ({
            name: `${i + 1} ${monthName}`, revenue: 0
          }));
          
          if (data.trend_data && Array.isArray(data.trend_data)) {
            data.trend_data.forEach(realDay => {
              const index = fullMonthData.findIndex(d => d.name === realDay.name);
              if (index !== -1) fullMonthData[index].revenue = realDay.revenue;
            });
          }
          setChartData(fullMonthData);
        } else {
          setChartData([]);
        }
      } catch (error) {
        console.error("Failed to fetch chart data:", error);
        setChartData([]);
      } finally {
        setIsLoadingChart(false);
      }
    };

    // 2. Fetch AI Summary & External Signals
    const fetchDetectiveCards = async () => {
      setIsLoadingCards(true);
      try {
        const response = await fetch(`${API_BASE_URL}/boardroom/detective-cards`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ merchant_id: ownerId, target_month: apiMonth })
        });
        const json = await response.json();
        
        if (json.status === "success" && json.data) {
          if (json.data.performance_summary) {
            setPerformanceSummary(json.data.performance_summary);
          }
          if (json.data.external_intelligence && json.data.external_intelligence.length > 0) {
            setExternalIntelligence(json.data.external_intelligence);
          } else {
            setExternalIntelligence([]);
          }
        }
      } catch (err) {
        console.error("Failed to fetch detective cards:", err);
      } finally {
        setIsLoadingCards(false);
      }
    };

    fetchTrend();
    fetchDetectiveCards();
  }, [selectedMonth, ownerId]);

  if (isLoadingChart || isLoadingCards) {
    return (
      <div className="loading-page" role="status" aria-live="polite">
        <div className="loading-glow" aria-hidden="true" />
        <main className="loading-content">
          <p className="loading-brand">Tauke.AI</p>
          <div className="loading-spinner-wrap" aria-hidden="true">
            <div className="loading-spinner" />
            <div className="loading-spinner-center" />
          </div>
          <h1 className="loading-title">Generating Dashboard...</h1>
          <p className="loading-subtitle">Fusing your context with real-time market signals.</p>
        </main>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      <div className="main-content">
        <header className="top-app-bar">
          <div />
          <div className="header-icons">
            <button className="icon-btn"><Bell className="w-5 h-5" /></button>
            <button className="icon-btn"><Settings className="w-5 h-5" /></button>
            <button className="icon-btn"><HelpCircle className="w-5 h-5" /></button>
            <div className="user-profile">
              <img 
                src="https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?ixlib=rb-1.2.1&auto=format&fit=facearea&facepad=2&w=256&h=256&q=80" 
                alt="Profile" 
              />
            </div>
          </div>
        </header>

        <main className="scroll-area">
          <div className="page-center">
            <div className="page-header">
              <div className="badge-step">
                <div className="pulse-dot" />
                Detective Agent
              </div>
              <h2 className="page-title">Analysis</h2>
              <p className="page-subtitle">Identifying patterns and anomalies in your business data.</p>
            </div>

            <div className="bento-grid">
              
              {/* --- MAIN CHART CARD --- */}
              <div className="card main-chart-card">
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Revenue Velocity</h3>
                    <p className="card-subtitle">Trailing 30 Days Analysis</p>
                  </div>
                  
                  <div style={{ position: 'relative' }}>
                    <button 
                      onClick={() => setIsMonthDropdownOpen(!isMonthDropdownOpen)}
                      className="month-dropdown-btn"
                    >
                      {selectedMonth}
                      <ChevronDown style={{ width: '16px', transition: 'transform 0.3s', transform: isMonthDropdownOpen ? 'rotate(180deg)' : 'none' }} />
                    </button>
                    
                    <AnimatePresence>
                      {isMonthDropdownOpen && (
                        <motion.div 
                          initial={{ opacity: 0, y: -10 }} 
                          animate={{ opacity: 1, y: 0 }} 
                          exit={{ opacity: 0, y: -10 }} 
                          className="dropdown-panel"
                        >
                          {AVAILABLE_MONTHS.map(month => (
                            <button
                              key={month}
                              className={`dropdown-item ${selectedMonth === month ? 'active' : ''}`}
                              onClick={() => {
                                setSelectedMonth(month);
                                setIsMonthDropdownOpen(false);
                              }}
                            >
                              {month}
                            </button>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                <div className="chart-wrapper">
                  {!ownerId ? (
                    <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: '14px', fontWeight: '500' }}>
                      Please log in to view analytics.
                    </div>
                  ) : isLoadingChart ? (
                    <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: '#0058bc', fontSize: '14px', fontWeight: '600' }}>
                      Fetching data from server...
                    </div>
                  ) : chartData.length === 0 ? (
                    <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: '14px', fontWeight: '500' }}>
                      No sales data found for {selectedMonth}.
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.1}/>
                            <stop offset="95%" stopColor="var(--primary)" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                        <Tooltip 
                          contentStyle={{ 
                            borderRadius: '12px', border: 'none', 
                            boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)', fontSize: '12px'
                          }} 
                        />
                        <Area type="monotone" dataKey="revenue" stroke="var(--primary)" strokeWidth={4} fill="url(#colorRevenue)" animationDuration={1500} />
                      </AreaChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              {/* --- INTELLIGENCE CAROUSEL CARD --- */}
              <div className="intelligence-card">
                <div className="intelligence-header">
                  <div className="intelligence-icon">
                    <TrendingUp style={{ width: '16px' }} />
                  </div>
                  <h3 className="card-title" style={{ fontSize: '18px' }}>External Intelligence</h3>
                </div>

                <div style={{ position: 'relative', flex: 1 }}>
                  {isLoadingCards ? (
                    <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: '#0058bc', fontSize: '13px', fontWeight: 600 }}>
                      AI is analyzing your market signals...
                    </div>
                  ) : (
                    <div className="intelligence-section">
                      {currentIntel ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          
                          {/* Animated Rotating Card */}
                          <motion.div
                            key={activeIntelIndex}
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.4 }}
                            style={{ padding: '20px', backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #E2E8F0', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span className="material-symbols-outlined" style={{ color: 'var(--primary)' }}>radar</span>
                                <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: '700' }}>{currentIntel.title}</h4>
                              </div>
                              <span style={{ 
                                fontSize: '0.8rem', 
                                fontWeight: '700', 
                                color: currentIntel.trend === 'up' ? 'var(--green-600, #16a34a)' : 'var(--red-600, #dc2626)',
                                backgroundColor: currentIntel.trend === 'up' ? '#f0fdf4' : '#fef2f2',
                                padding: '4px 8px', borderRadius: '20px' 
                              }}>
                                {currentIntel.percentage} {currentIntel.trend === 'up' ? '↑' : '↓'}
                              </span>
                            </div>
                            
                            <p style={{ margin: 0, fontSize: '0.85rem', color: '#475569', lineHeight: '1.5' }}>
                              {currentIntel.content}
                            </p>
                          </motion.div>

                          {/* Navigation Dots */}
                          <div style={{ display: 'flex', justifyContent: 'center', gap: '6px', marginTop: '4px' }}>
                            {externalIntelligence.map((_, idx) => (
                              <div 
                                key={idx} 
                                onClick={() => setActiveIntelIndex(idx)}
                                style={{ 
                                  width: '8px', height: '8px', borderRadius: '50%', 
                                  backgroundColor: activeIntelIndex === idx ? 'var(--primary, #0058bc)' : '#cbd5e1',
                                  transition: 'background-color 0.3s ease',
                                  cursor: 'pointer'
                                }}
                              />
                            ))}
                          </div>

                        </div>
                      ) : (
                        <div style={{ padding: '20px', textAlign: 'center', color: '#94a3b8', border: '1px dashed #cbd5e1', borderRadius: '12px' }}>
                          No significant external signals detected this month.
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Subtext Footer */}
                <div style={{ marginTop: '32px', backgroundColor: 'rgba(255,255,255,0.5)', padding: '16px', borderRadius: '12px', border: '1px solid #fff' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', fontWeight: '900', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px' }}>
                    Industry Pulse <span style={{ color: 'var(--primary)' }}>Real-time</span>
                  </div>
                  <p style={{ fontSize: '12px', color: '#64748b', margin: 0, fontWeight: '500' }}>
                    {externalIntelligence.length > 0
                      ? `Tracking ${externalIntelligence.length} active market signal${externalIntelligence.length > 1 ? 's' : ''} in your area.`
                      : 'Tracking local competitors and macro trends in your market segment.'}
                  </p>
                </div>
              </div>

              {/* --- PERFORMANCE SUMMARY LIST --- */}
              <PerformanceSummaryList
                summary={performanceSummary ?? (PERFORMANCE_SUMMARIES[selectedMonth] || {
                  headline: isLoadingCards ? 'AI is generating your performance summary...' : `Operating Report: ${selectedMonth}`,
                  subheadline: isLoadingCards ? 'Please wait while we analyze your data.' : 'Analyzing historical patterns and synthesizing insights...',
                  insights: [],
                  score: 'N/A'
                })}
                month={selectedMonth}
              />
            </div>
          </div>

          {/* --- NEXT STEP CTA SECTION --- */}
          <div style={{
            marginTop: '40px',
            marginBottom: '24px',
            padding: '24px',
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
          }}>
            <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
              <div style={{
                backgroundColor: '#eff6ff',
                color: 'var(--primary, #0058bc)',
                padding: '12px',
                borderRadius: '12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Users className="w-8 h-8" />
              </div>
              <div style={{ flex: 1 }}>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: '700', color: '#0f172a' }}>
                  Next Step: Initiate the AI War Room
                </h3>
                <p style={{ margin: 0, fontSize: '14.5px', color: '#475569', lineHeight: '1.6' }}>
                  You now have the complete picture: internal sales diagnostics, your operational context, and real-time market signals. 
                  Proceed to the War Room to watch your <strong>AI CMO, COO, and CFO</strong> debate these findings and synthesize a bulletproof recovery strategy.
                </p>
              </div>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid #e2e8f0', paddingTop: '20px' }}>
              <button
                onClick={() => navigate('/ai-debate')}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '14px 28px', borderRadius: '12px',
                  background: 'var(--primary, #0058bc)', color: '#fff',
                  border: 'none', fontSize: '15px', fontWeight: 700,
                  cursor: 'pointer',
                  boxShadow: '0 4px 6px -1px rgba(0, 88, 188, 0.25)'
                }}
              >
                <span>Watch AI Agents Debate</span>
                <span className="material-symbols-outlined" style={{ fontSize: '20px' }} aria-hidden="true">forum</span>
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}