import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';
import { Store, RefreshCw, LayoutDashboard, MessageSquare, Shield, Sparkles, MapPin, Clock, Users, Check, Plus, Trash2 } from 'lucide-react';
import { GoogleMap, useJsApiLoader, Marker } from '@react-google-maps/api';
import './StoreConfiguration.css'; // Loads your vanilla CSS!

const MENU_ITEMS = [
  { id: 'setup', label: 'Store Setup', icon: Store },
  { id: 'sync', label: 'Data Sync', icon: RefreshCw },
  { id: 'analysis', label: 'Analysis', icon: LayoutDashboard },
  { id: 'clarification', label: 'Clarification', icon: MessageSquare },
  { id: 'warroom', label: 'War Room', icon: Shield },
  { id: 'strategy', label: 'Strategy Synthesis', icon: Sparkles },
];

const center = { lat: 3.140853, lng: 101.693207 }; // KL City Centre

export default function StoreConfiguration() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('setup');
  const [isSaving, setIsSaving] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false); // 👈 ADD THIS
  const [locationName, setLocationName] = useState("Kuala Lumpur City Centre"); // 👈 ADD THIS

  // Form State
  const [storeName, setStoreName] = useState('Kopitiam AI Central');
  const [businessType, setBusinessType] = useState('Cafe');
  const [pricingTier, setPricingTier] = useState('Mid-Market');

  // Security Check
  useEffect(() => {
    const ownerId = localStorage.getItem("owner_id");
    if (!ownerId) navigate("/login");
  }, [navigate]);

  // Dynamic Audience Mix
  // --- Dynamic Audience Mix ---
  const [audiences, setAudiences] = useState([
    { id: '1', name: 'Local Residents', value: 50 },
    { id: '2', name: 'Office Staff', value: 50 }
  ]);

  const totalAllocation = useMemo(() => audiences.reduce((acc, curr) => acc + curr.value, 0), [audiences]);

  const updateAudienceValue = (id, newValue) => {
    // Basic update: just change the value for the specific audience
    setAudiences(audiences.map(a => a.id === id ? { ...a, value: newValue } : a));
  };

  const addAudience = () => {
    // Add a new audience with a default name and value
    const newAudience = {
      id: String(Date.now()), // Simple unique ID
      name: `New Customer Type`,
      value: 0
    };
    setAudiences([...audiences, newAudience]);
  };

  const removeAudience = (id) => {
    // Remove an audience, ensuring at least one remains
    if (audiences.length > 1) {
      setAudiences(audiences.filter(a => a.id !== id));
    } else {
      alert("You must have at least one audience type.");
    }
  };

  // Operating Hours
  const [hours, setHours] = useState({
    weekdayStart: '08:00', weekdayEnd: '22:00',
    weekendStart: '09:00', weekendEnd: '23:30'
  });

  // Map state
  const [markerPosition, setMarkerPosition] = useState(center);
  const { isLoaded } = useJsApiLoader({ id: 'google-map-script', googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '' });

  const onMarkerDragEnd = useCallback((e) => {
  if (e.latLng) {
    const newPos = { lat: e.latLng.lat(), lng: e.latLng.lng() };
    setMarkerPosition(newPos);

const geocoder = new window.google.maps.Geocoder();
    geocoder.geocode({ location: newPos }, (results, status) => {
      if (status === "OK" && results[0]) {
        setLocationName(results[0].formatted_address);
      } else {
        setLocationName("Unknown Location");
      }
    });
  }
}, []);

  const handleSaveProfile = async () => {
    if (totalAllocation !== 100) return alert("Audience allocation must equal 100%.");
    setIsSaving(true);
    
    const ownerId = localStorage.getItem("owner_id");
    
    // 1. Format audience as a clean JSON object
    const targetAudienceData = {};
    audiences.forEach(aud => { targetAudienceData[aud.name] = aud.value; });

    // 2. Format hours
    const formattedHours = `Mon-Fri: ${hours.weekdayStart}-${hours.weekdayEnd}, Sat-Sun: ${hours.weekendStart}-${hours.weekendEnd}`;

    try {
        const response = await fetch(`${API_BASE_URL}/merchants/setup-profile`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                merchant_id: ownerId,
                name: storeName,
                type: businessType,
                pricing_tier: pricingTier,        // 👈 Added
                operating_hours: formattedHours,
                target_audience: targetAudienceData,
                address: locationName, // 👈 Use your locationName state here
                latitude: markerPosition.lat,      // 👈 Added
                longitude: markerPosition.lng      // 👈 Added
            }),
        });

        const data = await response.json();
        if (data.status === "success") {
            // 1. Trigger the green success animation!
            setIsSuccess(true);
            
            // 2. Wait exactly 1.5 seconds, THEN jump to the dashboard
            setTimeout(() => {
                navigate("/landing");
            }, 1500); 
            
        } else {
            alert(data.message || "Failed to save profile.");
            setIsSaving(false); // Only stop loading if it fails!
        }
    } catch (error) {
        alert("Server connection error.");
        setIsSaving(false);
    } 
    // REMOVE the `finally { setIsSaving(false); }` block entirely! 
    // If we stop loading on success, the button text flickers.
  };

  return (
    <div className="sc-page">
      {/* Sidebar */}
      <aside className="sc-sidebar">
        <div className="sc-brand-header">
          <div className="sc-logo-box"><LayoutDashboard size={24} /></div>
          <div>
            <h1 style={{fontSize: '18px', fontWeight: 900}}>Tauke.AI</h1>
            <p style={{fontSize: '12px', color: '#717786'}}>SME Intelligence</p>
          </div>
        </div>
        <nav style={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
          {MENU_ITEMS.map((item) => (
            <button key={item.id} onClick={() => setActiveTab(item.id)} className={`sc-nav-btn ${activeTab === item.id ? 'active' : ''}`}>
              <item.icon size={20} /> {item.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="sc-main">
        <header style={{marginBottom: '48px'}}>
          <span style={{background: '#6ffb85', color: '#006e28', padding: '4px 12px', borderRadius: '99px', fontSize: '12px', fontWeight: 'bold'}}>ONBOARDING MODULE</span>
          <h2 className="sc-title">Business DNA <br /><span className="sc-gradient-text">Configuration</span></h2>
          <p style={{color: '#717786', fontSize: '18px'}}>Establish the core operating parameters for your SME.</p>
        </header>

        <div className="sc-grid">
          {/* Left Column */}
          <div>
            <div className="sc-card">
              <h3 className="sc-card-title"><Store color="#0058bc" /> Entity Profile</h3>
              <label className="sc-label">Store Name</label>
              <input type="text" className="sc-input" value={storeName} onChange={(e) => setStoreName(e.target.value)} />
              
              <div className="sc-row">
                <div>
                  <label className="sc-label">Business Type</label>
                  <select className="sc-input" value={businessType} onChange={(e) => setBusinessType(e.target.value)}>
                    <option>Cafe</option><option>Restaurant</option><option>Retail</option>
                  </select>
                </div>
                <div>
                  <label className="sc-label">Pricing Tier</label>
                  <select className="sc-input" value={pricingTier} onChange={(e) => setPricingTier(e.target.value)}>
                    <option>Budget</option><option>Mid-Market</option><option>Premium</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="sc-card">
                <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: '24px', alignItems: 'center'}}>
                    <h3 className="sc-card-title" style={{margin: 0}}><Users color="#0058bc" /> Audience Mix</h3>
                    <div style={{display: 'flex', alignItems: 'center', gap: '16px'}}>
                    <span style={{fontWeight: 'bold', color: totalAllocation === 100 ? '#0058bc' : 'red'}}>{totalAllocation}% Allocated</span>
                    <button className="sc-btn-secondary" style={{padding: '8px 16px'}} onClick={addAudience}>
                        <Plus size={16} /> Add Type
                    </button>
                    </div>
                </div>
                
                {audiences.map((aud) => (
                    <div key={aud.id} style={{marginBottom: '24px', border: '1px solid #e8e8ea', padding: '16px', borderRadius: '12px'}}>
                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: '16px', fontWeight: 'bold', alignItems: 'center'}}>
                        <input 
                            type="text" 
                            value={aud.name} 
                            onChange={(e) => setAudiences(audiences.map(a => a.id === aud.id ? { ...a, name: e.target.value } : a))}
                            style={{border: 'none', background: 'transparent', color: '#1a1c1d', padding: 0, width: 'auto'}}
                        />
                        <div style={{display: 'flex', alignItems: 'center', gap: '16px'}}>
                        <span>{aud.value}%</span>
                        <button className="sc-icon-btn" onClick={() => removeAudience(aud.id)} title={`Remove ${aud.name}`}>
                            <Trash2 size={16} color="red" />
                        </button>
                        </div>
                    </div>
                    <input type="range" min="0" max="100" value={aud.value} onChange={(e) => updateAudienceValue(aud.id, parseInt(e.target.value))} className="sc-range" />
                    </div>
                ))}
                </div>
            </div>

          {/* Right Column */}
          <div>
            <div className="sc-card">
              <h3 className="sc-card-title"><MapPin color="#0058bc" /> Location Context</h3>
              
              {/* 👈 Update this line to show the real address! */}
              <p style={{fontSize: '14px', color: '#717786', minHeight: '40px'}}>
                {locationName === "Kuala Lumpur City Centre" ? "Drag pin to your exact storefront." : locationName}
              </p>
              
              <div className="sc-map-container">
                {isLoaded ? (
                  <GoogleMap mapContainerStyle={{width: '100%', height: '100%'}} center={center} zoom={15} options={{disableDefaultUI: true}}>
                    <Marker position={markerPosition} draggable={true} onDragEnd={onMarkerDragEnd} />
                  </GoogleMap>
                ) : (<div style={{padding: '20px', textAlign: 'center'}}>Loading Map...</div>)}
              </div>
            </div>

            <div className="sc-card">
              <h3 className="sc-card-title"><Clock color="#0058bc" /> Operating Rhythm</h3>
              <div style={{marginBottom: '16px'}}>
                <label className="sc-label">Weekday Hours</label>
                <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
                  <input type="time" className="sc-input" style={{marginBottom: 0}} value={hours.weekdayStart} onChange={(e) => setHours({...hours, weekdayStart: e.target.value})} />
                  <span style={{fontWeight: 'bold'}}>-</span>
                  <input type="time" className="sc-input" style={{marginBottom: 0}} value={hours.weekdayEnd} onChange={(e) => setHours({...hours, weekdayEnd: e.target.value})} />
                </div>
              </div>
              <div>
                <label className="sc-label">Weekend Hours</label>
                <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
                  <input type="time" className="sc-input" style={{marginBottom: 0}} value={hours.weekendStart} onChange={(e) => setHours({...hours, weekendStart: e.target.value})} />
                  <span style={{fontWeight: 'bold'}}>-</span>
                  <input type="time" className="sc-input" style={{marginBottom: 0}} value={hours.weekendEnd} onChange={(e) => setHours({...hours, weekendEnd: e.target.value})} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Action Bar */}
        <div style={{display: 'flex', justifyContent: 'flex-end', marginTop: '32px'}}>
          <button 
            className="sc-btn-primary" 
            onClick={handleSaveProfile} 
            disabled={isSaving || isSuccess}
            style={{
                // If success, turn the button Green!
                background: isSuccess ? 'linear-gradient(135deg, #006e28, #6ffb85)' : '',
                boxShadow: isSuccess ? '0 4px 12px rgba(0, 110, 40, 0.3)' : '',
                transition: 'all 0.3s ease'
            }}
          >
            {isSaving ? "Saving Config..." : isSuccess ? "Saved Successfully!" : "Save Configuration"} 
            <Check size={20} />
          </button>
        </div>
      </main>
    </div>
  );
}