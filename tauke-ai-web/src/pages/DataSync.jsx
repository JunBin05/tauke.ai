import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, LineChart, RefreshCw, BarChart3, Settings, HelpCircle,
  LogOut, Bell, Grid, ReceiptText, CheckCircle2, Database, Clock,
  AlertCircle, Upload, Search, ChevronDown, FileText, Package, Receipt,
  Loader2, Info, Sparkles
} from 'lucide-react';

import { API_BASE_URL } from '../config'; // 👈 Make sure you have your config imported!
import './DataSync.css'; 

export default function DataSync() {
  const navigate = useNavigate();
  const ownerId = localStorage.getItem("owner_id"); // 👈 Grab the Boss ID

  const getApiMonth = (displayMonth) => {
    // 1. Split "April 2026" into ["April", "2026"]
    const [monthName, year] = displayMonth.split(" ");
    
    // 2. The master dictionary of months
    const months = [
      "January", "February", "March", "April", "May", "June", 
      "July", "August", "September", "October", "November", "December"
    ];
    
    // 3. Find the exact month number (e.g., April is index 3. Add 1 to make it 4)
    const monthNumber = months.indexOf(monthName) + 1;
    
    // 4. Pad single digits with a zero (so "4" becomes "04")
    const formattedMonth = monthNumber.toString().padStart(2, '0');
    
    // 5. Combine them for the backend!
    return `${year}-${formattedMonth}`; 
  };
  
  const [selectedMonth, setSelectedMonth] = useState('April 2026');
  const [isMonthSelectOpen, setIsMonthSelectOpen] = useState(false);
  const [isMissingMonthSelectorOpen, setIsMissingMonthSelectorOpen] = useState(false);
  const [isChecking, setIsChecking] = useState(true); // Loading state for initial DB check
  
  // Default structure
  const months = ['April 2026', 'March 2026', 'February 2026'];
  const [allMonthsSyncStates, setAllMonthsSyncStates] = useState({
    'April 2026': { sales: { isSynced: false, isUploading: false }, procurement: { isSynced: false, isUploading: false }, invoices: { isSynced: false, isUploading: false } },
    'March 2026': { sales: { isSynced: false, isUploading: false }, procurement: { isSynced: false, isUploading: false }, invoices: { isSynced: false, isUploading: false } },
    'February 2026': { sales: { isSynced: false, isUploading: false }, procurement: { isSynced: false, isUploading: false }, invoices: { isSynced: false, isUploading: false } },
  });

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [showHint, setShowHint] = useState(true);

  // --- 1. FETCH SYNC STATUS ON LOAD ---
  useEffect(() => {
    if (!ownerId) {
        navigate("/login");
        return;
    }

    const checkAllMonths = async () => {
      try {
        // 👇 UPDATE THIS FETCH TO USE getApiMonth()
        const checks = months.map(m => 
          fetch(`${API_BASE_URL}/merchants/${ownerId}/sync-status/${getApiMonth(m)}`).then(res => res.json())
        );
        const results = await Promise.all(checks);
        
        setAllMonthsSyncStates(prevState => {
          const newState = { ...prevState };
          // 👇 UPDATE THIS FOREACH TO USE THE INDEX
          results.forEach((res, index) => {
            if (res.status === "success") {
              newState[months[index]] = res.sync_state; // Map it back to "April 2026"
            }
          });
          return newState;
        });
      } catch (err) {
        console.error("Failed to fetch sync status:", err);
      } finally {
        setIsChecking(false);
      }
    };

    checkAllMonths();
  }, [ownerId, navigate]);

  const isCurrentMonth = selectedMonth === 'April 2026';
  const currentSyncStates = allMonthsSyncStates[selectedMonth];

  // Helper to convert files to Base64
  const fileToBase64 = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result);
    reader.onerror = error => reject(error);
  });

  // --- 2. HANDLE INDIVIDUAL UPLOADS ---
  const handleFileUpload = async (type, file) => {
    if (!file || !ownerId) return;

    // Set UI to uploading
    setAllMonthsSyncStates(prev => ({
      ...prev,
      [selectedMonth]: { ...prev[selectedMonth], [type]: { ...prev[selectedMonth][type], isUploading: true } }
    }));

    try {
      const base64Data = await fileToBase64(file);
      
      // Determine the exact endpoint based on the card type
      let endpoint = "";
      if (type === 'sales') endpoint = "/upload/sales";
      if (type === 'procurement') endpoint = "/upload/statement";
      if (type === 'invoices') endpoint = "/upload/invoices";

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
              merchant_id: ownerId,
              report_month: getApiMonth(selectedMonth), // 👈 ADD TRANSLATOR HERE
              file_data_url: base64Data
          })
      });

      const data = await response.json();

      if (data.status === "success") {
        setAllMonthsSyncStates(prev => ({
          ...prev,
          [selectedMonth]: { ...prev[selectedMonth], [type]: { isSynced: true, isUploading: false, fileName: file.name } }
        }));
      } else {
        const errorMessage = data.detail || data.message || "Unknown error occurred";
        alert(`Upload failed: ${errorMessage}`);
        throw new Error(errorMessage);
      }
    } catch (err) {
      console.error(err);
      // Revert loading state on failure
      setAllMonthsSyncStates(prev => ({
        ...prev,
        [selectedMonth]: { ...prev[selectedMonth], [type]: { ...prev[selectedMonth][type], isUploading: false } }
      }));
    }
  };

  const handleNavigateToMonth = (month) => {
    setSelectedMonth(month);
    setIsMissingMonthSelectorOpen(false);
    setAnalysisProgress(0);
    setIsAnalyzing(false);
  };

  // --- 3. THE CRUNCHER (MASTER ANALYZE) ---
  const handleAnalyze = async () => {
    if (isAnalyzing || !ownerId) return;
    setIsAnalyzing(true);
    setAnalysisProgress(0);

    // Start a fake progress bar just for the UI visuals
    const interval = setInterval(() => {
      setAnalysisProgress(prev => (prev >= 90 ? 90 : prev + 5)); // Caps at 90% until backend is done
    }, 200);

    try {
      // Hit the Cruncher Endpoint
      const response = await fetch(`${API_BASE_URL}/analyze/monthly-patterns`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
              merchant_id: ownerId,
              report_month: getApiMonth(selectedMonth)
          })
      });

      const data = await response.json();

      if (data.status === "success") {
          clearInterval(interval);
          setAnalysisProgress(100);
          setTimeout(() => {
            setIsAnalyzing(false);
            navigate('/loading'); // Jump to the Swarm Simulation!
          }, 800);
      } else {
          clearInterval(interval);
          setIsAnalyzing(false);
          alert("Analysis failed to complete.");
      }
    } catch (err) {
        clearInterval(interval);
        setIsAnalyzing(false);
        console.error("Cruncher error", err);
        alert("Server connection failed.");
    }
  };

  const allSynced = Object.values(currentSyncStates).every(s => s.isSynced);
  const incompleteMonths = months.filter(m => 
    m !== selectedMonth && Object.values(allMonthsSyncStates[m]).some(s => !s.isSynced)
  );

  // Don't render the dashboard until the initial DB check is done
  if (isChecking) {
      return <div style={{height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center'}}><Loader2 className="lucide-spin text-primary" size={48} /></div>;
  }

  return (
    <div className="sync-layout-root">
      {/* Main Content Area */}
      <main className="sync-main-content">
        <div className="sync-page-container">
          <div className="sync-page-header">
            <div>
              <h2 className="sync-title">Data Intelligence Hub</h2>
              <p className="sync-subtitle">Synthesize your enterprise data for predictive modeling.</p>
            </div>

            <div className="sync-dropdown-container">
              <button onClick={() => setIsMonthSelectOpen(!isMonthSelectOpen)} className="sync-dropdown-btn">
                {selectedMonth}
                <ChevronDown size={16} style={{ transform: isMonthSelectOpen ? 'rotate(180deg)' : 'none', transition: '0.2s' }} />
              </button>
              <AnimatePresence>
                {isMonthSelectOpen && (
                  <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="sync-dropdown-menu">
                    {months.map((month) => (
                      <button key={month} onClick={() => { setSelectedMonth(month); setIsMonthSelectOpen(false); setAnalysisProgress(0); setIsAnalyzing(false); }} className={`sync-dropdown-item ${selectedMonth === month ? 'active' : ''}`}>
                        {month}
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          <AnimatePresence>
            {showHint && isCurrentMonth && incompleteMonths.length > 0 && (
              <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }} className="sync-hint-box">
                <div style={{ background: 'rgba(0, 88, 188, 0.1)', padding: '12px', borderRadius: '12px', height: 'fit-content' }}>
                  <Sparkles color="#0058bc" size={24} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: '0 0 4px 0', fontSize: '16px', fontWeight: 700 }}>Maximize Insight Quality</h4>
                  <p style={{ margin: '0 0 16px 0', fontSize: '14px', color: '#414755', lineHeight: 1.5 }}>
                    Some historical data is currently missing. While {selectedMonth} analysis is ready, 
                    providing past records allows the AI to detect deeper quarterly trends for a more accurate forecast.
                  </p>
                  <div style={{ display: 'flex', gap: '24px', alignItems: 'center' }}>
                    <div className="sync-dropdown-container">
                      <button onClick={() => setIsMissingMonthSelectorOpen(!isMissingMonthSelectorOpen)} style={{ background: 'transparent', border: 'none', color: '#0058bc', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', padding: 0 }}>
                        Fill missing record <ChevronDown size={14} />
                      </button>
                      <AnimatePresence>
                        {isMissingMonthSelectorOpen && (
                          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }} className="sync-dropdown-menu" style={{ left: 0, right: 'auto', bottom: '100%', top: 'auto', marginBottom: '8px', width: '220px' }}>
                            <div style={{ padding: '8px 16px', fontSize: '10px', fontWeight: 800, color: '#717786', textTransform: 'uppercase', borderBottom: '1px solid #e8e8ea' }}>Missing Periods</div>
                            {incompleteMonths.map(month => (
                              <button key={month} onClick={() => handleNavigateToMonth(month)} className="sync-dropdown-item">{month}</button>
                            ))}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                    <button onClick={() => setShowHint(false)} style={{ background: 'transparent', border: 'none', color: '#717786', cursor: 'pointer', fontSize: '14px' }}>
                      Dismiss for now
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="sync-grid">
            <SyncCard 
              title="Sales & Transactions" format="(CSV)" description="Historical POS records and daily transaction logs."
              icon={ReceiptText} isSynced={currentSyncStates.sales.isSynced} isUploading={currentSyncStates.sales.isUploading}
              onUpload={(file) => handleFileUpload('sales', file)} acceptedFormats=".csv" fileName={currentSyncStates.sales.fileName}
              rows={currentSyncStates.sales.isSynced ? "Ready" : null} colSpan="sync-col-12" accentColor="secondary"
            />

            <SyncCard 
              title="Monthly Statement" format="(PDF)"
              description={currentSyncStates.procurement.isSynced ? "All supplier ledgers are verified and reconciled." : "Awaiting period ledger for cost validation."}
              icon={Package} isSynced={currentSyncStates.procurement.isSynced} isUploading={currentSyncStates.procurement.isUploading}
              onUpload={(file) => handleFileUpload('procurement', file)} acceptedFormats=".pdf,image/*" fileName={currentSyncStates.procurement.fileName}
              errorMsg={!currentSyncStates.procurement.isSynced ? `Awaiting ${selectedMonth.split(' ')[0]} Supplier Ledger` : undefined}
              colSpan="sync-col-6" accentColor="error"
            />

            <SyncCard 
              title="Invoice Management" format="(PDF)"
              description={currentSyncStates.invoices.isSynced ? "Monthly invoicing data processed and stored." : "Internal invoicing data incomplete for this period."}
              icon={Receipt} isSynced={currentSyncStates.invoices.isSynced} isUploading={currentSyncStates.invoices.isUploading}
              onUpload={(file) => handleFileUpload('invoices', file)} acceptedFormats=".pdf,image/*" fileName={currentSyncStates.invoices.fileName}
              errorMsg={!currentSyncStates.invoices.isSynced ? `Missing ${selectedMonth.split(' ')[0]} Transaction Invoices` : undefined}
              colSpan="sync-col-6" accentColor="error"
            />

            <div className="sync-card sync-col-12" style={{ marginTop: '16px' }}>
               <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '24px' }}>
                <div style={{ flex: 1, minWidth: '300px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                    <LineChart color="#0058bc" size={24} />
                    <h3 style={{ margin: 0, fontSize: '20px', fontWeight: 700 }}>Data Analysis Pipeline</h3>
                  </div>
                  <p style={{ margin: 0, color: '#717786', fontSize: '14px' }}>
                    {!allSynced ? "Pipeline paused. Integrated intelligence requires all data sources to be present." 
                      : isAnalyzing ? `Analysis in progress... ${analysisProgress}%`
                      : "Pipeline active. You have enough data to initiate deep learning analysis."}
                  </p>
                  
                  {isAnalyzing && (
                    <div className="sync-progress-track">
                      <motion.div className="sync-progress-fill" initial={{ width: 0 }} animate={{ width: `${analysisProgress}%` }} />
                    </div>
                  )}
                </div>
                
                <button onClick={handleAnalyze} disabled={!allSynced || isAnalyzing} className="sync-btn-analyze">
                  {isAnalyzing ? <><Loader2 size={20} className="lucide-spin" /> Analysing...</> : <><Search size={20} /> Ready to analyse?</>}
                </button>
               </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

// Subcomponents
function NavItem({ icon: Icon, label, active = false }) {
  return (
    <button className={`sync-nav-item ${active ? 'active' : ''}`}>
      <Icon size={20} />
      <span>{label}</span>
    </button>
  );
}

function SyncCard({ title, format, description, icon: Icon, isSynced, isUploading, onUpload, rows, lastUpdate, errorMsg, colSpan, accentColor, acceptedFormats, fileName }) {
  const fileInputRef = useRef(null);

  // Triggers when a user actually selects a file from their computer
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      onUpload(e.target.files[0]);
    }
  };

  return (
    <div className={`sync-card ${colSpan}`}>
      {/* Hidden File Input! */}
      <input type="file" ref={fileInputRef} style={{ display: 'none' }} accept={acceptedFormats} onChange={handleFileChange} />

      <div className="sync-card-top-line" style={{ backgroundColor: isSynced ? '#006e28' : '#ba1a1a' }} />
      
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '24px', marginTop: '8px' }}>
        <Icon size={28} color={accentColor === 'error' && !isSynced ? '#ba1a1a' : '#1a1c1d'} />
        <div className={`sync-badge ${isSynced ? 'synced' : 'action'}`}>
          {isSynced ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
          {isSynced ? 'Synced' : 'Action Required'}
        </div>
      </div>

      <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: 700 }}>
        {title} <span style={{ fontWeight: 400, color: '#717786', fontSize: '14px' }}>{format}</span>
      </h3>
      
      {errorMsg && <p style={{ margin: '0 0 4px 0', color: '#ba1a1a', fontSize: '14px', fontWeight: 600 }}>{errorMsg}</p>}
      <p style={{ margin: '0 0 32px 0', color: '#717786', fontSize: '14px', lineHeight: 1.5 }}>{description}</p>

      {isSynced ? (
        <div>
          {fileName && (
            <div className="sync-stat-row" style={{ marginBottom: '8px' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><FileText size={16} color="#717786" /> <span style={{ fontSize: '14px', fontWeight: 600 }}>Uploaded File</span></div>
              <span style={{ fontSize: '14px', fontWeight: 700, color: '#0058bc', maxWidth: '200px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={fileName}>{fileName}</span>
            </div>
          )}
          {rows && (
            <div className="sync-stat-row">
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><Database size={16} color="#717786" /> <span style={{ fontSize: '14px', fontWeight: 600 }}>Data Parsed</span></div>
              <span style={{ fontSize: '14px', fontWeight: 700 }}>{rows}</span>
            </div>
          )}
          {!rows && (
             <div className="sync-stat-row">
               <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><FileText size={16} color="#717786" /> <span style={{ fontSize: '14px', fontWeight: 600 }}>Period Consistency</span></div>
               <CheckCircle2 size={16} color="#006e28" />
             </div>
          )}
          <button 
            onClick={() => fileInputRef.current.click()} 
            disabled={isUploading} 
            className="sync-btn-upload"
            style={{ marginTop: '16px', background: 'transparent', color: '#0058bc', border: '1px solid #0058bc' }}
          >
            {isUploading ? <><Loader2 size={20} className="lucide-spin" /> Uploading...</> : <><RefreshCw size={20} /> Edit File</>}
          </button>
        </div>
      ) : (
        <button onClick={() => fileInputRef.current.click()} disabled={isUploading} className="sync-btn-upload">
          {isUploading ? <><Loader2 size={20} className="lucide-spin" /> Uploading...</> : <><Upload size={20} /> Edit File</>}
        </button>
      )}
    </div>
  );
}