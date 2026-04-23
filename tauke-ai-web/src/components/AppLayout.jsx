import { NavLink, Outlet, useNavigate } from "react-router-dom";

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

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {/* ── Global Sidebar ── */}
      <aside
        style={{
          width: "72px",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: "20px",
          paddingBottom: "20px",
          background: "#ffffff",
          borderRight: "1px solid #e8e8ea",
          zIndex: 100,
          gap: "4px",
        }}
      >
        {/* Logo */}
        <div
          onClick={() => navigate("/landing")}
          style={{
            width: "40px",
            height: "40px",
            borderRadius: "12px",
            background: "linear-gradient(135deg, #0058bc, #0070eb)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: "24px",
            cursor: "pointer",
            boxShadow: "0 4px 12px rgba(0,88,188,0.25)",
          }}
          title="Tauke.AI"
        >
          <span style={{ color: "#fff", fontWeight: 900, fontSize: "14px" }}>T</span>
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
