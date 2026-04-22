import React from "react";
import { Link } from "react-router-dom";

const logoGlyph = "https://www.figma.com/api/mcp/asset/af6bb38e-9e2c-4c62-8838-2bfd0291daec";

export default function Login() {
	return (
		<div className="login-page">
			<style>{`
				@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

				.login-page,
				.login-page * {
					box-sizing: border-box;
				}

				.login-page {
					min-height: 100vh;
					width: 100%;
					display: flex;
					align-items: center;
					justify-content: center;
					padding: 177.25px 0;
					position: relative;
					overflow: hidden;
					font-family: "Inter", sans-serif;
					background: #f5f5f7;
					color: #1d1d1f;
					-webkit-font-smoothing: antialiased;
					text-rendering: optimizeLegibility;
				}

				.login-gradient {
					position: absolute;
					top: -200px;
					left: -200px;
					width: 400px;
					height: 400px;
					border-radius: 50%;
					background: radial-gradient(circle, rgba(0, 122, 255, 0.08) 0%, rgba(0, 122, 255, 0) 70%);
					pointer-events: none;
				}

				.login-canvas {
					width: 480px;
					max-width: 480px;
					padding: 0 24px;
					display: flex;
					flex-direction: column;
					gap: 39px;
					position: relative;
					z-index: 1;
				}

				.login-card {
					width: 100%;
					border-radius: 24px;
					border: 1px solid rgba(255, 255, 255, 0.5);
					background: rgba(255, 255, 255, 0.8);
					backdrop-filter: blur(10px);
					box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04);
					padding: 49px;
					padding-bottom: 65px;
					display: flex;
					flex-direction: column;
					gap: 48px;
				}

				.brand-anchor {
					width: 100%;
					display: flex;
					flex-direction: column;
					align-items: center;
					justify-content: center;
				}

				.brand-icon-wrap {
					width: 56px;
					height: 80px;
					padding-bottom: 24px;
				}

				.brand-icon {
					width: 56px;
					height: 56px;
					border-radius: 9999px;
					background: #007aff;
					box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04);
					display: flex;
					align-items: center;
					justify-content: center;
				}

				.brand-icon img {
					width: 22.5px;
					height: 22.5px;
					display: block;
				}

				.brand-title {
					margin: 0;
					color: #1d1d1f;
					font-size: 30px;
					font-weight: 600;
					line-height: 36px;
					letter-spacing: -0.6px;
				}

				.brand-subtitle-wrap {
					padding-top: 8px;
				}

				.brand-subtitle {
					margin: 0;
					color: #86868b;
					font-size: 16px;
					font-weight: 500;
					line-height: 24px;
					letter-spacing: -0.4px;
				}

				.interaction-form {
					width: 100%;
					display: flex;
					flex-direction: column;
					gap: 24px;
				}

				.field {
					width: 100%;
					display: flex;
					flex-direction: column;
					gap: 8px;
				}

				.field.password-field {
					padding-bottom: 24px;
				}

				.field-label-row {
					width: 100%;
					display: flex;
					align-items: center;
					justify-content: space-between;
				}

				.field-label {
					margin: 0;
					color: #86868b;
					font-size: 12px;
					font-weight: 600;
					line-height: 16px;
					letter-spacing: 0.3px;
				}

				.forgot-link {
					color: #007aff;
					font-size: 13px;
					font-weight: 500;
					line-height: 19.5px;
					letter-spacing: 0.325px;
					text-decoration: none;
				}

				.input {
					width: 100%;
					border: 1px solid #e5e7eb;
					border-radius: 8px;
					background: #ffffff;
					padding: 19px 17px;
					font-family: "Inter", sans-serif;
					color: #1d1d1f;
					font-size: 17px;
					font-weight: 400;
					line-height: 21px;
					letter-spacing: -0.4px;
					outline: none;
				}

				.input::placeholder {
					color: #9ca3af;
					opacity: 1;
				}

				.input:focus {
					border-color: #007aff;
				}

				.primary-action {
					width: 100%;
					border: 0;
					border-radius: 24px;
					background: #007aff;
					color: #ffffff;
					padding: 16px;
					font-family: "Inter", sans-serif;
					font-size: 17px;
					font-weight: 600;
					line-height: 25.5px;
					letter-spacing: -0.4px;
					cursor: pointer;
				}

				.footer-context {
					width: 100%;
					display: flex;
					justify-content: center;
					text-align: center;
				}

				.footer-text {
					margin: 0;
					color: #86868b;
					font-size: 15px;
					font-weight: 400;
					line-height: 22.5px;
					letter-spacing: -0.375px;
				}

				.footer-link {
					color: #007aff;
					font-weight: 500;
					text-decoration: none;
				}

				@media (max-width: 520px) {
					.login-page {
						padding-top: 40px;
						padding-bottom: 40px;
					}

					.login-canvas {
						width: 100%;
						max-width: 480px;
						padding-left: 16px;
						padding-right: 16px;
					}

					.login-card {
						padding: 32px 24px 40px;
						gap: 36px;
					}
				}
			`}</style>

			<div className="login-gradient" aria-hidden="true" />

			<main className="login-canvas" data-node-id="1:4">
				<section className="login-card" data-node-id="1:5">
					<header className="brand-anchor" data-node-id="1:6">
						<div className="brand-icon-wrap" data-node-id="1:7">
							<div className="brand-icon" data-node-id="1:8" aria-hidden="true">
								<img src={logoGlyph} alt="" />
							</div>
						</div>

						<h1 className="brand-title" data-node-id="1:11">Tauke.AI</h1>

						<div className="brand-subtitle-wrap" data-node-id="1:13">
							<p className="brand-subtitle">Enter the Digital Atelier</p>
						</div>
					</header>

					<form className="interaction-form" data-node-id="1:15">
						<div className="field" data-node-id="1:16">
							<label className="field-label" htmlFor="email">Email Address</label>
							<input
								id="email"
								name="email"
								type="email"
								placeholder="name@example.com"
								className="input"
							/>
						</div>

						<div className="field password-field" data-node-id="1:22">
							<div className="field-label-row" data-node-id="1:23">
								<label className="field-label" htmlFor="password">Password</label>
								<a href="#" className="forgot-link" data-node-id="1:26">Forgot Password?</a>
							</div>

							<input
								id="password"
								name="password"
								type="password"
								placeholder="••••••••"
								className="input"
							/>
						</div>

						<button type="submit" className="primary-action" data-node-id="1:31">Sign In</button>
					</form>
				</section>

				<footer className="footer-context" data-node-id="1:33">
					<p className="footer-text">
						New to Tauke.AI?{" "}
						<Link to="/register" className="footer-link">
							Create an account
						</Link>
					</p>
				</footer>
			</main>
		</div>
	);
}
