import "./StoreConfiguration.css";

const mapImage = "https://www.figma.com/api/mcp/asset/64ac90b4-bb3f-4a1b-8208-b65aa12cb3b3";
const userProfileImage = "https://www.figma.com/api/mcp/asset/ef476901-5451-49c9-b805-738dc35b7bd4";
const entityIcon = "https://www.figma.com/api/mcp/asset/ed9c16b2-d4eb-43c3-9966-e5c1ef11961a";
const selectChevron = "https://www.figma.com/api/mcp/asset/3433d5dd-038a-4b20-8670-bfe675d1bc41";
const audienceIcon = "https://www.figma.com/api/mcp/asset/c4ef8104-9d90-46d7-a172-e708c9c1357d";
const locationIcon = "https://www.figma.com/api/mcp/asset/856afad6-9e1c-412d-ae89-7afbefbdc4cd";
const rhythmIcon = "https://www.figma.com/api/mcp/asset/baf167fc-530d-4cf0-a9b7-955e55a10cfa";
const saveArrow = "https://www.figma.com/api/mcp/asset/18b68d4e-d5f0-4a2b-a975-b1dde1dec9bf";
const brandIcon = "https://www.figma.com/api/mcp/asset/01caa6e2-8e61-4a6d-9f84-c0ebe9a34804";
const navStore = "https://www.figma.com/api/mcp/asset/b18daa35-8051-4e50-bf81-c4c4cd81aaa7";
const navSync = "https://www.figma.com/api/mcp/asset/e61c5006-1ce5-4665-b8ff-16a09f679c30";
const navAnalysis = "https://www.figma.com/api/mcp/asset/17e9bc1f-81e7-4909-ac85-043548b86f3c";
const navClarification = "https://www.figma.com/api/mcp/asset/856f7b69-97e6-4b58-8ff5-89172cbef7a0";
const navWarRoom = "https://www.figma.com/api/mcp/asset/40506338-582e-4125-835d-d5f0aa716040";
const navStrategy = "https://www.figma.com/api/mcp/asset/a9ceb1e5-3217-4de1-8c99-aadb8ebe9b35";

const audienceRows = [
	{
		label: "Local Residents",
		description: "Primary community base",
		value: "60%",
		bar: "60%",
		color: "#0058bc"
	},
	{
		label: "Office Workers",
		description: "Weekday lunch & transit",
		value: "30%",
		bar: "30%",
		color: "#006e28"
	},
	{
		label: "Tourists / Visitors",
		description: "Weekend & seasonal traffic",
		value: "10%",
		bar: "10%",
		color: "#e2241f"
	}
];

const navItems = [
	{ label: "Store Setup", icon: navStore, active: true },
	{ label: "Data Sync", icon: navSync },
	{ label: "Analysis", icon: navAnalysis },
	{ label: "Clarification", icon: navClarification },
	{ label: "War Room", icon: navWarRoom },
	{ label: "Strategy Synthesis", icon: navStrategy }
];

export default function StoreConfiguration() {
	return (
		<div className="store-config-page">
			<aside className="store-sidebar">
				<div className="sidebar-brand-wrap">
					<div className="sidebar-brand">
						<div className="brand-badge" aria-hidden="true">
							<img src={brandIcon} alt="" />
						</div>
						<div className="brand-copy">
							<h2>Tauke.AI</h2>
							<p>SME Intelligence</p>
						</div>
					</div>
				</div>

				<nav className="sidebar-nav" aria-label="Primary">
					{navItems.map((item) => (
						<button key={item.label} type="button" className={`sidebar-nav-item${item.active ? " is-active" : ""}`}>
							<img className="nav-icon" src={item.icon} alt="" aria-hidden="true" />
							<span>{item.label}</span>
						</button>
					))}
				</nav>

				<div className="sidebar-footer">
					<div className="user-row">
						<div className="avatar" aria-hidden="true">
							<img src={userProfileImage} alt="" />
						</div>
						<div className="user-copy">
							<h4>Admin User</h4>
							<p>Manage Account</p>
						</div>
					</div>
				</div>
			</aside>

			<div className="store-main-wrap">
				<main className="store-main">
					<header className="header-section">
						<span className="module-pill">Onboarding Module</span>
						<h1 className="page-title">Business DNA Configuration</h1>
						<p className="page-subtitle">
							Establish the core operating parameters for your SME. This context drives
							localized intelligence and tailored strategic insights.
						</p>
					</header>

					<section className="config-grid">
						<article className="config-card entity-card">
							<div className="card-heading">
								<img className="card-heading-icon" src={entityIcon} alt="" aria-hidden="true" />
								<h3>Entity Profile</h3>
							</div>

							<div className="field-group">
								<p className="field-label">Store Name</p>
								<div className="display-input store-name">Kopitiam AI Central</div>
							</div>

							<div className="compact-two-col">
								<div className="field-group">
									<p className="field-label">Business Type</p>
									<div className="select-display">
										<span>Food &amp; Beverage (F&amp;B)</span>
										<img className="select-chevron" src={selectChevron} alt="" aria-hidden="true" />
									</div>
								</div>

								<div className="field-group">
									<p className="field-label">Pricing Tier</p>
									<div className="select-display">
										<span>Mid-Market</span>
										<img className="select-chevron" src={selectChevron} alt="" aria-hidden="true" />
									</div>
								</div>
							</div>
						</article>

						<article className="config-card location-card">
							<div className="card-heading">
								<img className="card-heading-icon" src={locationIcon} alt="" aria-hidden="true" />
								<h3>Location Context</h3>
							</div>
							<p className="location-subtitle">Kuala Lumpur City Centre</p>

							<div className="map-frame">
								<img src={mapImage} alt="Location map" />
								<div className="map-pin" aria-hidden="true">
									<div className="map-pin-inner" />
								</div>
								<div className="map-overlay">
									<button type="button" className="map-button">Adjust Pin</button>
								</div>
							</div>
						</article>

						<article className="config-card audience-card">
							<div className="audience-top">
								<div className="card-heading">
									<img className="card-heading-icon" src={audienceIcon} alt="" aria-hidden="true" />
									<h3>Audience Mix</h3>
								</div>
								<span className="allocation-pill">100% Allocated</span>
							</div>

							<div className="audience-list">
								{audienceRows.map((row) => (
									<div className="audience-row" key={row.label}>
										<div className="audience-meta">
											<div className="audience-copy">
												<h4>{row.label}</h4>
												<p>{row.description}</p>
											</div>
											<p className="audience-value">{row.value}</p>
										</div>
										<div className="progress-track" aria-hidden="true">
											<div className="progress-fill" style={{ width: row.bar, backgroundColor: row.color }} />
										</div>
									</div>
								))}
							</div>
						</article>

						<article className="config-card rhythm-card">
							<div className="card-heading">
								<img className="card-heading-icon" src={rhythmIcon} alt="" aria-hidden="true" />
								<h3>Operating Rhythm</h3>
							</div>

							<div className="schedule-list">
								<div className="schedule-row">
									<div className="schedule-copy">
										<h4>Weekday Hours</h4>
										<p>Mon - Fri</p>
									</div>
									<div className="time-pill">
										<span>08:00</span>
										<span className="dash">-</span>
										<span>22:00</span>
									</div>
								</div>

								<div className="schedule-row">
									<div className="schedule-copy">
										<h4>Weekend Hours</h4>
										<p>Sat - Sun</p>
									</div>
									<div className="time-pill">
										<span>09:00</span>
										<span className="dash">-</span>
										<span>23:30</span>
									</div>
								</div>

								<div className="traffic-row">
									<h4>Peak Traffic Hours</h4>
									<span className="traffic-pill">Auto-calculated</span>
								</div>
							</div>
						</article>
					</section>

					<div className="action-bar">
						<button type="button" className="btn btn-secondary">Discard Changes</button>
						<button type="button" className="btn btn-primary">
							<span>Save Configuration</span>
							<img src={saveArrow} alt="" aria-hidden="true" />
						</button>
					</div>
				</main>
			</div>
		</div>
	);
}
