import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../config"; // Make sure this file exists!
import { supabase } from "../supabaseClient";

const logoGlyph = "https://www.figma.com/api/mcp/asset/af6bb38e-9e2c-4c62-8838-2bfd0291daec";

export default function Login() {
    const navigate = useNavigate();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [isGoogleLoading, setIsGoogleLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState("");

    const handleGoogleLogin = async () => {
        setIsGoogleLoading(true);
        setErrorMessage("");

        const redirectUrl = `${window.location.origin}/sync`;

        console.log("Redirect URL:", redirectUrl);

        // This physically redirects the browser to accounts.google.com
        const { error } = await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: {
                // Tells Google: "When the user finishes logging in, send them to this exact page"
                redirectTo: redirectUrl
            }
        });

        // We only hit this error block if the popup gets blocked or fails to open
        if (error) {
            console.error("Google Auth Error:", error.message);
            setErrorMessage("Could not connect to Google. Please try again.");
            setIsGoogleLoading(false);
        }
    };

    const handleLogin = async (e) => {
        e.preventDefault(); // Prevents the page from refreshing
        setIsLoading(true);
        setErrorMessage("");

        try {
            const response = await fetch(`${API_BASE_URL}/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });

            const data = await response.json();

            if (data.status === "success") {
                // Save the session data to localStorage so other pages know who is logged in!
                localStorage.setItem("owner_id", data.owner_id);
                localStorage.setItem("access_token", data.access_token);
                localStorage.setItem("user_email", email);
                localStorage.setItem("login_type", "email");
                // Clear any old Google data
                localStorage.removeItem("user_name");
                localStorage.removeItem("user_avatar");

                // Redirect to the dashboard/landing page
                navigate("/landing"); // Change this to your actual next page
            } else {
                setErrorMessage(data.message || "Incorrect password or unregistered account.");
            }
        } catch (error) {
            console.error("Login Error:", error);
            setErrorMessage("Server offline. Please check your internet connection.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="login-page">
            <style>{`
                /* ... Keep all your existing CSS here exactly as it was ... */
				.divider-container {
					display: flex;
					align-items: center;
					text-align: center;
					margin: 10px 0;
				}
				.divider-line {
					flex: 1;
					border-bottom: 1px solid #e5e7eb;
				}
				.divider-text {
					color: #86868b;
					padding: 0 10px;
					font-size: 13px;
					font-weight: 500;
				}
				.google-action {
					width: 100%;
					border: 1px solid #e5e7eb;
					border-radius: 24px;
					background: #ffffff;
					color: #1d1d1f;
					padding: 16px;
					font-family: "Inter", sans-serif;
					font-size: 17px;
					font-weight: 600;
					cursor: pointer;
					display: flex;
					align-items: center;
					justify-content: center;
					gap: 10px;
					transition: background 0.2s;
				}
				.google-action:hover {
					background: #f9fafb;
				}
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
                .login-page, .login-page * { box-sizing: border-box; }
                .login-page { min-height: 100vh; width: 100%; display: flex; align-items: center; justify-content: center; padding: 45px 0; position: relative; overflow: hidden; font-family: "Inter", sans-serif; background: #f5f5f7; color: #1d1d1f; -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
                .login-gradient { position: absolute; top: -200px; left: -200px; width: 400px; height: 400px; border-radius: 50%; background: radial-gradient(circle, rgba(0, 122, 255, 0.08) 0%, rgba(0, 122, 255, 0) 70%); pointer-events: none; }
                .login-canvas { width: 480px; max-width: 480px; padding: 0 24px; display: flex; flex-direction: column; gap: 39px; position: relative; z-index: 1; }
                .login-card { width: 100%; border-radius: 24px; border: 1px solid rgba(255, 255, 255, 0.5); background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(10px); box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04); padding: 49px; padding-bottom: 65px; display: flex; flex-direction: column; gap: 48px; }
                .brand-anchor { width: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; }
                .brand-icon-wrap { width: 56px; height: 80px; padding-bottom: 24px; }
                .brand-icon { width: 56px; height: 56px; border-radius: 9999px; background: #007aff; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04); display: flex; align-items: center; justify-content: center; }
                .brand-icon img { width: 22.5px; height: 22.5px; display: block; }
                .brand-title { margin: 0; color: #1d1d1f; font-size: 30px; font-weight: 600; line-height: 36px; letter-spacing: -0.6px; }
                .brand-subtitle-wrap { padding-top: 8px; }
                .brand-subtitle { margin: 0; color: #86868b; font-size: 16px; font-weight: 500; line-height: 24px; letter-spacing: -0.4px; }
                .interaction-form { width: 100%; display: flex; flex-direction: column; gap: 24px; }
                .field { width: 100%; display: flex; flex-direction: column; gap: 8px; }
                .field.password-field { padding-bottom: 24px; }
                .field-label-row { width: 100%; display: flex; align-items: center; justify-content: space-between; }
                .field-label { margin: 0; color: #86868b; font-size: 12px; font-weight: 600; line-height: 16px; letter-spacing: 0.3px; }
                .forgot-link { color: #007aff; font-size: 13px; font-weight: 500; line-height: 19.5px; letter-spacing: 0.325px; text-decoration: none; }
                .input { width: 100%; border: 1px solid #e5e7eb; border-radius: 8px; background: #ffffff; padding: 19px 17px; font-family: "Inter", sans-serif; color: #1d1d1f; font-size: 17px; font-weight: 400; line-height: 21px; letter-spacing: -0.4px; outline: none; }
                .input::placeholder { color: #9ca3af; opacity: 1; }
                .input:focus { border-color: #007aff; }
                .primary-action { width: 100%; border: 0; border-radius: 24px; background: #007aff; color: #ffffff; padding: 16px; font-family: "Inter", sans-serif; font-size: 17px; font-weight: 600; line-height: 25.5px; letter-spacing: -0.4px; cursor: pointer; transition: opacity 0.2s; }
                .primary-action:disabled { opacity: 0.6; cursor: not-allowed; }
                .footer-context { width: 100%; display: flex; justify-content: center; text-align: center; }
                .footer-text { margin: 0; color: #86868b; font-size: 15px; font-weight: 400; line-height: 22.5px; letter-spacing: -0.375px; }
                .footer-link { color: #007aff; font-weight: 500; text-decoration: none; }
                .error-message { color: #ff3b30; font-size: 14px; text-align: center; margin-top: -10px; }
                @media (max-width: 520px) { .login-page { padding-top: 40px; padding-bottom: 40px; } .login-canvas { width: 100%; max-width: 480px; padding-left: 16px; padding-right: 16px; } .login-card { padding: 32px 24px 40px; gap: 36px; } }
            `}</style>

            <div className="login-gradient" aria-hidden="true" />

            <main className="login-canvas">
                <section className="login-card">
                    <header className="brand-anchor">
                        <div className="brand-icon-wrap">
                            <div className="brand-icon" aria-hidden="true">
                                <img src={logoGlyph} alt="" />
                            </div>
                        </div>
                        <h1 className="brand-title">Tauke.AI</h1>
                        <div className="brand-subtitle-wrap">
                            <p className="brand-subtitle">Step into the Boss's Office</p>
                        </div>
                    </header>

                    <form className="interaction-form" onSubmit={handleLogin}>
                        {errorMessage && <p className="error-message">{errorMessage}</p>}

                        <div className="field">
                            <label className="field-label" htmlFor="email">Email Address</label>
                            <input
                                id="email"
                                name="email"
                                type="email"
                                placeholder="name@example.com"
                                className="input"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                            />
                        </div>

                        <div className="field password-field">
                            <div className="field-label-row">
                                <label className="field-label" htmlFor="password">Password</label>
                                <a href="#" className="forgot-link">Forgot Password?</a>
                            </div>

                            <input
                                id="password"
                                name="password"
                                type="password"
                                placeholder="••••••••"
                                className="input"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>

                        <button type="submit" className="primary-action" disabled={isLoading}>
                            {isLoading ? "Signing In..." : "Sign In"}
                        </button>
                    </form>

                    {/* 👇 THIS IS THE NEW GOOGLE SECTION 👇 */}
                    <div className="divider-container">
                        <div className="divider-line"></div>
                        <span className="divider-text">OR</span>
                        <div className="divider-line"></div>
                    </div>

                    <button type="button" className="google-action" onClick={handleGoogleLogin}>
                        {/* A simple SVG Google 'G' Logo */}
                        <svg width="20" height="20" viewBox="0 0 24 24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                        </svg>
                        Sign in with Google
                    </button>
                    {/* 👆 END OF GOOGLE SECTION 👆 */}
                </section>

                <footer className="footer-context">
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