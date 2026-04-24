import { useState, useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";

const NAV_ITEMS = [
  {
    label: "Profile",
    icon: "storefront",
    to: "/store-configuration",
    // Highlight when on store-configuration
    matches: ["/store-configuration"],
  },
  {
    label: "Analyse",
    icon: "insights",
    to: "/landing",
    // Highlight for the entire analyse pipeline
    matches: [
      "/landing",
      "/data-sync",
      "/loading",
      "/supervisor-clarification",
      "/detective-analysis",
      "/ai-debate",
      "/final-synthesis",
      "/campaign-roadmap",
    ],
  },
  {
    label: "Simulation",
    icon: "science",
    to: "/simulation",
    matches: ["/simulation", "/dashboard"],
  },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const currentPath = window.location.pathname;
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const userEmail = localStorage.getItem("user_email") || "SME Intelligence";
  const userName = localStorage.getItem("user_name") || "Boss Account";
  const userAvatar = localStorage.getItem("user_avatar");
  const loginType = localStorage.getItem("login_type") || "email";

  const handleLogout = () => {
    localStorage.removeItem("owner_id");
    localStorage.removeItem("target_month");
    localStorage.removeItem("user_email");
    localStorage.removeItem("user_name");
    localStorage.removeItem("user_avatar");
    localStorage.removeItem("login_type");
    navigate("/login");
  };

  // Close dropdown on click outside
  useEffect(() => {
    if (!isProfileOpen) return;
    const handleClick = () => setIsProfileOpen(false);
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, [isProfileOpen]);

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", boxSizing: "border-box" }}>
      {/* ── Global Sidebar ── */}
      <aside
        style={{
          width: "80px",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: "24px",
          paddingBottom: "20px",
          background: "#ffffff",
          borderRight: "1px solid #e8e8ea",
          zIndex: 100,
          gap: "8px",
          boxSizing: "border-box"
        }}
      >
        {/* Logo & Profile Trigger */}
        <div 
          style={{ 
            width: "100%", 
            display: "flex", 
            justifyContent: "center", 
            position: "relative", 
            marginBottom: "16px" 
          }} 
          onClick={(e) => e.stopPropagation()}
        >
          <div
            onClick={() => setIsProfileOpen(!isProfileOpen)}
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "16px",
              background: userAvatar ? `url(${userAvatar})` : "linear-gradient(135deg, #0058bc, #0070eb)",
              backgroundSize: 'cover',
              backgroundPosition: 'center',
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              boxShadow: isProfileOpen ? "0 0 0 2px #fff, 0 0 0 4px #0058bc" : "0 4px 12px rgba(0,0,0,0.05)",
              border: "none",
              transition: "all 0.2s ease",
              transform: isProfileOpen ? "scale(0.95)" : "scale(1)",
              boxSizing: "border-box",
              overflow: "hidden"
            }}
            title="Account Profile"
          >
            {!userAvatar && <span style={{ color: "#fff", fontWeight: 900, fontSize: "20px" }}>T</span>}
          </div>

          <AnimatePresence>
            {isProfileOpen && (
              <motion.div
                initial={{ opacity: 0, x: -10, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -10, scale: 0.95 }}
                style={{
                  position: "absolute",
                  left: "72px",
                  top: "0",
                  width: "220px",
                  background: "#ffffff",
                  borderRadius: "16px",
                  boxShadow: "0 12px 40px rgba(0,0,0,0.15)",
                  border: "1px solid #e8e8ea",
                  padding: "12px",
                  zIndex: 1000,
                  boxSizing: "border-box"
                }}
              >
                <div style={{ padding: "8px 12px", borderBottom: "1px solid #f1f5f9", marginBottom: "8px" }}>
                  <div style={{ fontSize: "14px", fontWeight: 800, color: "#1a1c1d", marginBottom: '2px' }}>{userName}</div>
                  <div style={{ fontSize: "12px", color: "#717786", wordBreak: 'break-all' }}>{userEmail}</div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  {loginType === 'email' && (
                    <button
                      onClick={() => navigate('/change-password')}
                      style={{
                        width: "100%",
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        padding: "10px 12px",
                        border: "none",
                        background: "transparent",
                        color: "#414755",
                        fontSize: "13px",
                        fontWeight: 600,
                        borderRadius: "10px",
                        cursor: "pointer",
                        transition: "background 0.2s",
                      }}
                      onMouseOver={(e) => e.currentTarget.style.background = '#f8fafc'}
                      onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>lock_reset</span>
                      Change Password
                    </button>
                  )}
                  
                  <button
                    onClick={handleLogout}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      padding: "10px 12px",
                      border: "none",
                      background: "transparent",
                      color: "#ba1a1a",
                      fontSize: "13px",
                      fontWeight: 600,
                      borderRadius: "10px",
                      cursor: "pointer",
                      transition: "background 0.2s",
                    }}
                    onMouseOver={(e) => e.currentTarget.style.background = '#fff1f0'}
                    onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>logout</span>
                    Logout
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Nav Items */}
        {NAV_ITEMS.map((item) => {
          const isActive = item.matches.some((m) => currentPath.startsWith(m));
          return (
            <NavLink
              key={item.label}
              to={item.to}
              title={item.label}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "4px",
                padding: "10px 8px",
                borderRadius: "12px",
                textDecoration: "none",
                width: "56px",
                transition: "all 0.2s",
                background: isActive ? "rgba(0,88,188,0.08)" : "transparent",
                color: isActive ? "#0058bc" : "#717786",
              }}
            >
              <span
                className="material-symbols-outlined"
                style={{
                  fontSize: "22px",
                  fontVariationSettings: isActive
                    ? "'FILL' 1, 'wght' 600"
                    : "'FILL' 0, 'wght' 400",
                }}
              >
                {item.icon}
              </span>
              <span style={{ fontSize: "10px", fontWeight: isActive ? 700 : 500, lineHeight: 1 }}>
                {item.label}
              </span>
            </NavLink>
          );
        })}
      </aside>

      {/* ── Page Content ── */}
      <div style={{ flex: 1, overflow: "auto", height: "100vh" }}>
        <Outlet />
      </div>
    </div>
  );
}
