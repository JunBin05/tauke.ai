import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config';
import { GoogleMap, useJsApiLoader, Marker, Autocomplete } from '@react-google-maps/api';
import './StoreConfiguration.css';
import { Store, RefreshCw, LayoutDashboard, MessageSquare, Shield, Sparkles, MapPin, Clock, Users, Check, Plus, Trash2, Loader2, Search } from 'lucide-react';

const center = { lat: 3.140853, lng: 101.693207 };
const libraries = ['places'];

export default function StoreConfiguration() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('setup');
  const [isSaving, setIsSaving] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [isFetching, setIsFetching] = useState(true); // <-- NEW: Loading state for initial fetch
  const [locationName, setLocationName] = useState("Kuala Lumpur City Centre");
  const [searchQuery, setSearchQuery] = useState("");
  

  // Form State
  const [storeName, setStoreName] = useState('Kopitiam AI Central');
  const [businessType, setBusinessType] = useState('Cafe');
  const [pricingTier, setPricingTier] = useState('Mid-Market');

  const [audiences, setAudiences] = useState([
    { id: '1', name: 'Local Residents', value: 50 },
    { id: '2', name: 'Office Staff', value: 50 }
  ]);

  const [hours, setHours] = useState({
    weekdayStart: '08:00', weekdayEnd: '22:00',
    weekendStart: '09:00', weekendEnd: '23:30'
  });

  const [markerPosition, setMarkerPosition] = useState(center);
  const { isLoaded } = useJsApiLoader({ id: 'google-map-script', googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '', libraries: libraries });

  const [autocomplete, setAutocomplete] = useState(null);

  const onLoadAutocomplete = (autoC) => setAutocomplete(autoC);

  const onPlaceChanged = () => {
    if (autocomplete !== null) {
      const place = autocomplete.getPlace();
      if (place.geometry && place.geometry.location) {
        const newPos = {
          lat: place.geometry.location.lat(),
          lng: place.geometry.location.lng()
        };
        setMarkerPosition(newPos);
        setLocationName(place.formatted_address || place.name);
        setSearchQuery(place.formatted_address || place.name);
      }
    }
  };

  // --- NEW: Fetch Existing Profile Data ---
  useEffect(() => {
    const ownerId = localStorage.getItem("owner_id");
    if (!ownerId) {
      navigate("/login");
      return;
    }

    const fetchProfile = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/merchants/profile/${ownerId}`);
        const data = await response.json();

        if (data.status === "success" && data.profile) {
          const p = data.profile;

          if (p.name) setStoreName(p.name);
          if (p.type) setBusinessType(p.type);
          if (p.pricing_tier) setPricingTier(p.pricing_tier);
          if (p.address) {setLocationName(p.address);setSearchQuery(p.address);}
          if (p.latitude && p.longitude) setMarkerPosition({ lat: p.latitude, lng: p.longitude });

          // Parse JSON target audience back into React state array
          if (p.target_audience && Object.keys(p.target_audience).length > 0) {
            const parsedAudiences = Object.entries(p.target_audience).map(([name, value], index) => ({
              id: String(Date.now() + index), // Unique ID
              name,
              value: Number(value)
            }));
            setAudiences(parsedAudiences);
          }

          // Parse operating hours string back into state
          if (p.operating_hours) {
            // Expecting: "Mon-Fri: 08:00-22:00, Sat-Sun: 09:00-23:30"
            const regex = /Mon-Fri:\s*([\d:]+)-([\d:]+),\s*Sat-Sun:\s*([\d:]+)-([\d:]+)/;
            const match = p.operating_hours.match(regex);
            if (match) {
              setHours({
                weekdayStart: match[1],
                weekdayEnd: match[2],
                weekendStart: match[3],
                weekendEnd: match[4]
              });
            }
          }
        }
      } catch (error) {
        console.error("Failed to fetch profile:", error);
      } finally {
        setIsFetching(false);
      }
    };

    fetchProfile();
  }, [navigate]);
  // -----------------------------------------

  const totalAllocation = useMemo(() => audiences.reduce((acc, curr) => acc + curr.value, 0), [audiences]);

  const updateAudienceValue = (id, newValue) => {
    setAudiences(audiences.map(a => a.id === id ? { ...a, value: newValue } : a));
  };

  const addAudience = () => {
    const newAudience = { id: String(Date.now()), name: `New Customer Type`, value: 0 };
    setAudiences([...audiences, newAudience]);
  };

  const removeAudience = (id) => {
    if (audiences.length > 1) {
      setAudiences(audiences.filter(a => a.id !== id));
    } else {
      alert("You must have at least one audience type.");
    }
  };

  const onMarkerDragEnd = useCallback((e) => {
      if (e.latLng) {
        const newPos = { lat: e.latLng.lat(), lng: e.latLng.lng() };
        setMarkerPosition(newPos);

        const geocoder = new window.google.maps.Geocoder();
        geocoder.geocode({ location: newPos }, (results, status) => {
          if (status === "OK" && results[0]) {
            setLocationName(results[0].formatted_address);
            setSearchQuery(results[0].formatted_address); // <-- ADD THIS
          } else {
            setLocationName("Unknown Location");
          }
        });
      }
    }, []);
    
    const handleSearchAddress = useCallback(() => {
    if (!searchQuery.trim() || !window.google) return;
    
    const geocoder = new window.google.maps.Geocoder();
    geocoder.geocode({ address: searchQuery }, (results, status) => {
      if (status === "OK" && results[0]) {
        const newPos = { 
          lat: results[0].geometry.location.lat(), 
          lng: results[0].geometry.location.lng() 
        };
        setMarkerPosition(newPos);
        setLocationName(results[0].formatted_address);
        setSearchQuery(results[0].formatted_address); // Auto-formats the text they typed
      } else {
        alert("Location not found. Please try a more specific address or city.");
      }
    });
  }, [searchQuery]);

  const handleSaveProfile = async () => {
    if (totalAllocation !== 100) return alert("Audience allocation must equal 100%.");
    setIsSaving(true);

    const ownerId = localStorage.getItem("owner_id");

    const targetAudienceData = {};
    audiences.forEach(aud => { targetAudienceData[aud.name] = aud.value; });

    const formattedHours = `Mon-Fri: ${hours.weekdayStart}-${hours.weekdayEnd}, Sat-Sun: ${hours.weekendStart}-${hours.weekendEnd}`;

    try {
      const response = await fetch(`${API_BASE_URL}/merchants/setup-profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          merchant_id: ownerId,
          name: storeName,
          type: businessType,
          pricing_tier: pricingTier,
          operating_hours: formattedHours,
          target_audience: targetAudienceData,
          address: locationName,
          latitude: markerPosition.lat,
          longitude: markerPosition.lng
        }),
      });

      const data = await response.json();
      if (data.status === "success") {
        setIsSuccess(true);
        setTimeout(() => {
          navigate("/data-sync");
        }, 1500);
      } else {
        alert(data.message || "Failed to save profile.");
        setIsSaving(false);
      }
    } catch (error) {
      alert("Server connection error.");
      setIsSaving(false);
    }
  };

  // Show a loading state while fetching existing data
  if (isFetching) {
    return (
      <div className="sc-page" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <div style={{ textAlign: 'center', color: '#0058bc' }}>
          <Loader2 size={48} className="spinner" style={{ marginBottom: '16px', animation: 'spin 1s linear infinite' }} />
          <h3>Loading your business profile...</h3>
        </div>
      </div>
    );
  }

  return (
    <div className="sc-page">
      <main className="sc-main">
        <header style={{ marginBottom: '48px' }}>
          <span style={{ background: '#6ffb85', color: '#006e28', padding: '4px 12px', borderRadius: '99px', fontSize: '12px', fontWeight: 'bold' }}>ONBOARDING MODULE</span>
          <h2 className="sc-title">Business DNA <br /><span className="sc-gradient-text">Configuration</span></h2>
          <p style={{ color: '#717786', fontSize: '18px' }}>Let’s set the ground rules for how our business runs.</p>
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
                  <label className="sc-label">rice levels</label>
                  <select className="sc-input" value={pricingTier} onChange={(e) => setPricingTier(e.target.value)}>
                    <option>Budget</option><option>Mid-Market</option><option>Premium</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="sc-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '24px', alignItems: 'center' }}>
                <h3 className="sc-card-title" style={{ margin: 0 }}><Users color="#0058bc" /> Audience Mix</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <span style={{ fontWeight: 'bold', color: totalAllocation === 100 ? '#0058bc' : 'red' }}>{totalAllocation}% Allocated</span>
                  <button className="sc-btn-secondary" style={{ padding: '8px 16px' }} onClick={addAudience}>
                    <Plus size={16} /> Add Type
                  </button>
                </div>
              </div>

              {audiences.map((aud) => (
                <div key={aud.id} style={{ marginBottom: '24px', border: '1px solid #e8e8ea', padding: '16px', borderRadius: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px', fontWeight: 'bold', alignItems: 'center' }}>
                    <input
                      type="text"
                      value={aud.name}
                      onChange={(e) => setAudiences(audiences.map(a => a.id === aud.id ? { ...a, name: e.target.value } : a))}
                      style={{ border: 'none', background: 'transparent', color: '#1a1c1d', padding: 0, width: 'auto' }}
                    />
                      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        {/* THE NEW TYPEABLE INPUT */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
                          <input
                            type="number"
                            min="0"
                            max="100"
                            value={aud.value === 0 ? '' : aud.value} // Allows user to easily delete and retype
                            onChange={(e) => {
                              let val = e.target.value;
                              if (val === '') {
                                updateAudienceValue(aud.id, 0);
                                return;
                              }
                              val = parseInt(val, 10);
                              if (val > 100) val = 100; // Prevents typing over 100
                              if (val < 0) val = 0;     // Prevents typing negative numbers
                              updateAudienceValue(aud.id, val);
                            }}
                            className="sc-audience-number"
                            placeholder="0"
                          />
                          <span style={{ fontSize: '16px' }}>%</span>
                        </div>
                        
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
              
              {/* 👇 THE NEW PREMIUM SEARCH BAR 👇 */}
              {isLoaded && (
                <div className="sc-location-search-container">
                  <Autocomplete onLoad={onLoadAutocomplete} onPlaceChanged={onPlaceChanged}>
                    <div className="sc-search-input-wrapper">
                      <Search size={18} className="sc-search-icon-left" />
                      <input 
                        type="text" 
                        className="sc-location-input" 
                        placeholder="Search for your store address..." 
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSearchAddress()}
                      />
                      <button className="sc-search-btn-right" onClick={handleSearchAddress}>
                        Search
                      </button>
                    </div>
                  </Autocomplete>
                </div>
              )}
              
              <p style={{ fontSize: '12px', color: '#717786', margin: '8px 0 16px 0', lineHeight: 1.4 }}>
                Select a suggestion, type your address and hit Enter, or drag the pin to fine-tune your exact storefront coordinates.
              </p>

              <div className="sc-map-container">
                {isLoaded ? (
                  <GoogleMap mapContainerStyle={{ width: '100%', height: '100%' }} center={markerPosition} zoom={15} options={{ disableDefaultUI: true }}>
                    <Marker position={markerPosition} draggable={true} onDragEnd={onMarkerDragEnd} />
                  </GoogleMap>
                ) : (<div style={{ padding: '20px', textAlign: 'center' }}>Loading Map...</div>)}
              </div>
            </div>

            <div className="sc-card">
              <h3 className="sc-card-title"><Clock color="#0058bc" /> Operating Rhythm</h3>
              <div style={{ marginBottom: '16px' }}>
                <label className="sc-label">Weekday Hours</label>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <input type="time" className="sc-input" style={{ marginBottom: 0 }} value={hours.weekdayStart} onChange={(e) => setHours({ ...hours, weekdayStart: e.target.value })} />
                  <span style={{ fontWeight: 'bold' }}>-</span>
                  <input type="time" className="sc-input" style={{ marginBottom: 0 }} value={hours.weekdayEnd} onChange={(e) => setHours({ ...hours, weekdayEnd: e.target.value })} />
                </div>
              </div>
              <div>
                <label className="sc-label">Weekend Hours</label>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <input type="time" className="sc-input" style={{ marginBottom: 0 }} value={hours.weekendStart} onChange={(e) => setHours({ ...hours, weekendStart: e.target.value })} />
                  <span style={{ fontWeight: 'bold' }}>-</span>
                  <input type="time" className="sc-input" style={{ marginBottom: 0 }} value={hours.weekendEnd} onChange={(e) => setHours({ ...hours, weekendEnd: e.target.value })} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Action Bar */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '32px' }}>
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