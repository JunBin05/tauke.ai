import React, { useState, useEffect } from 'react';
import './DetectiveAnalysis.css';
import { 
  LayoutDashboard, 
  Users, 
  RefreshCcw, 
  MessageSquare, 
  ShieldAlert, 
  Bell, 
  Settings, 
  HelpCircle, 
  ArrowUpRight, 
  ArrowDownRight,
  ChevronDown,
  TrendingUp,
  AlertCircle,
  Package
} from 'lucide-react';
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
import { EXTERNAL_INTELLIGENCE, PERFORMANCE_SUMMARIES } from './data';
import { API_BASE_URL } from '../config'; 

// 🚀 FIX 1: Overriding the old 2024 data.js import with fresh 2026 months
const AVAILABLE_MONTHS = [
  "Apr 2026", "Mar 2026", "Feb 2026", "Jan 2026", 
  "Dec 2025", "Nov 2025"
];

const SidebarItem = ({ icon: Icon, label, active = false }) => (
  <a href="#" className={`sidebar-item ${active ? 'active' : ''}`}>
    <Icon className="w-5 h-5" />
    <span>{label}</span>
  </a>
);

const IntelligenceCard = ({ item }) => (
  <motion.div
    initial={{ opacity: 0, x: 20 }}
    animate={{ opacity: 1, x: 0 }}
    exit={{ opacity: 0, x: -20 }}
    className="intelligence-content-card"
  >
    <div>
      <div className="card-header" style={{ marginBottom: '12px' }}>
        <span className="card-title" style={{ fontSize: '16px' }}>{item.title}</span>
        <span className={`badge-trend ${item.trend === 'up' ? 'up' : 'down'}`}>
          {item.trend === 'up' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
          {item.percentage}
        </span>
      </div>
      <div className="intelligence-progress-bar">
        <div 
          className="progress-fill" 
          style={{ 
            width: `${item.progress}%`, 
            backgroundColor: item.trend === 'up' ? 'var(--primary)' : '#94a3b8' 
          }} 
        />
      </div>
    </div>
    <p className="card-subtitle" style={{ fontSize: '12px', lineHeight: '1.5' }}>
      {item.content}
    </p>
  </motion.div>
);

const InsightRow = ({ item }) => {
  const Icon = item.type === 'growth' ? TrendingUp : item.type === 'efficiency' ? Package : AlertCircle;
  const typeClass = item.type;
  
  return (
    <div className={`insight-row ${typeClass}`}>
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
  const [selectedMonth, setSelectedMonth] = useState(AVAILABLE_MONTHS[0]);
  const [intelligenceIndex, setIntelligenceIndex] = useState(0);
  const [isMonthDropdownOpen, setIsMonthDropdownOpen] = useState(false);

  const [chartData, setChartData] = useState([]);
  const [isLoadingChart, setIsLoadingChart] = useState(true);
  
  // 🚀 FIX 2: Safely grab the ownerId
  const ownerId = localStorage.getItem("owner_id");

  useEffect(() => {
    const fetchRealTrend = async () => {
      // Don't even try to fetch if we don't have an ID
      if (!ownerId) {
        setIsLoadingChart(false);
        return;
      }
      
      setIsLoadingChart(true);
      try {
        const targetMonth = getApiMonth(selectedMonth);
        const response = await fetch(`${API_BASE_URL}/boardroom/trend/${ownerId}/${targetMonth}`);
        const data = await response.json();
        
        if (data.status === "success") {
            // 1. Figure out how many days are in the selected month
            const [monthName, yearName] = selectedMonth.split(" ");
            const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
            const monthIndex = months.indexOf(monthName);
            const daysInMonth = new Date(parseInt(yearName), monthIndex + 1, 0).getDate();

            // 2. Create a blank template for the whole month with 0 revenue
            const fullMonthData = Array.from({ length: daysInMonth }, (_, i) => ({
              name: `${i + 1} ${monthName}`,
              revenue: 0
            }));

            // 3. Merge the actual backend data into our blank template
            if (data.trend_data && Array.isArray(data.trend_data)) {
                data.trend_data.forEach(realDay => {
                  // Find the matching day in our template (e.g., "1 Mar")
                  const index = fullMonthData.findIndex(d => d.name === realDay.name);
                  if (index !== -1) {
                    fullMonthData[index].revenue = realDay.revenue;
                  }
                });
            }

            // 4. Set the padded data into the chart!
            setChartData(fullMonthData);
        } else {
            setChartData([]); // Reset on failure
        }
      } catch (error) {
        console.error("Failed to fetch real chart data:", error);
        setChartData([]);
      } finally {
        setIsLoadingChart(false);
      }
    };

    fetchRealTrend();
  }, [selectedMonth, ownerId]);

  // 🚀 FIX 3: Bulletproof Month Translator
  const getApiMonth = (displayMonth) => {
    try {
      const [monthName, year] = displayMonth.split(" ");
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const monthNumber = months.indexOf(monthName) + 1;
      const formattedMonth = monthNumber.toString().padStart(2, '0');
      return `${year}-${formattedMonth}`; 
    } catch (e) {
      console.error("Failed to parse month string:", displayMonth);
      return "2026-04"; // Safe fallback
    }
  };

  useEffect(() => {
    const fetchRealTrend = async () => {
      // Don't even try to fetch if we don't have an ID
      if (!ownerId) {
        setIsLoadingChart(false);
        return;
      }
      
      setIsLoadingChart(true);
      try {
        const targetMonth = getApiMonth(selectedMonth);
        const response = await fetch(`${API_BASE_URL}/boardroom/trend/${ownerId}/${targetMonth}`);
        const data = await response.json();
        
        if (data.status === "success") {
            setChartData(data.trend_data);
        } else {
            setChartData([]); // Reset on failure
        }
      } catch (error) {
        console.error("Failed to fetch real chart data:", error);
        setChartData([]);
      } finally {
        setIsLoadingChart(false);
      }
    };

    fetchRealTrend();
  }, [selectedMonth, ownerId]);

  return (
    <div className="dashboard-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1 className="sidebar-logo">Tauke.AI</h1>
          <p className="sidebar-tagline">SME Intelligence</p>
        </div>
        
        <nav className="sidebar-nav">
          <SidebarItem icon={Users} label="Onboarding" />
          <SidebarItem icon={RefreshCcw} label="Data Sync" />
          <SidebarItem icon={LayoutDashboard} label="Analysis" active />
          <SidebarItem icon={MessageSquare} label="Clarification" />
          <SidebarItem icon={ShieldAlert} label="War Room" />
        </nav>

        <div style={{ padding: '0 16px' }}>
          <button className="upgrade-btn">
            <ArrowUpRight className="w-4 h-4" style={{ transform: 'rotate(45deg)' }} />
            Upgrade Plan
          </button>
        </div>
      </aside>

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
                Step 4: Detective Agent
              </div>
              <h2 className="page-title">Analysis</h2>
              <p className="page-subtitle">Identifying patterns and anomalies in your business data.</p>
            </div>

            <div className="bento-grid">
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
                    
                    {isMonthDropdownOpen && (
                      <div className="dropdown-panel">
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
                      </div>
                    )}
                  </div>
                </div>

                <div className="chart-wrapper">
                  {/* 🚀 FIX 4: Proper UI handling for loading, empty, and errors! */}
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
                  {/* 🚀 FIX 5: Hardcoded anomaly alert removed from here! */}
                </div>
              </div>

              <div className="intelligence-card">
                <div className="intelligence-header">
                  <div className="intelligence-icon">
                    <TrendingUp style={{ width: '16px' }} />
                  </div>
                  <h3 className="card-title" style={{ fontSize: '18px' }}>External Intelligence</h3>
                </div>

                <div style={{ position: 'relative', flex: 1 }}>
                  <AnimatePresence mode="wait">
                    <IntelligenceCard key={EXTERNAL_INTELLIGENCE[intelligenceIndex].id} item={EXTERNAL_INTELLIGENCE[intelligenceIndex]} />
                  </AnimatePresence>
                  
                  <div className="dot-carousel">
                    {EXTERNAL_INTELLIGENCE.map((_, idx) => (
                      <div key={idx} className={`dot ${idx === intelligenceIndex ? 'active' : ''}`} />
                    ))}
                  </div>
                </div>

                <div style={{ marginTop: '32px', backgroundColor: 'rgba(255,255,255,0.5)', padding: '16px', borderRadius: '12px', border: '1px solid #fff' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', fontWeight: '900', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px' }}>
                    Industry Pulse <span style={{ color: 'var(--primary)' }}>Real-time</span>
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0, fontWeight: '500' }}>
                    Tracking 12 local competitors and 5 global brands in your market segment.
                  </p>
                </div>
              </div>

              <PerformanceSummaryList 
                summary={PERFORMANCE_SUMMARIES[selectedMonth] || {
                  headline: `Operating Report: ${selectedMonth}`,
                  subheadline: 'Analyzing historical patterns and synthesizing insights...',
                  insights: [],
                  score: 'N/A'
                }} 
                month={selectedMonth}
              />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}