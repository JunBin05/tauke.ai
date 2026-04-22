import { Link } from "react-router-dom";
import "./Register.css";

export default function Register() {
    return (
        <div className="register-page">
            <main className="register-main">
                <div className="register-brand">
                    <h1 className="register-title">Tauke.AI</h1>
                    <p className="register-subtitle">Create your studio account.</p>
                </div>

                <div className="register-card">
                    <form className="register-form">
                        <div className="form-group">
                            <label className="form-label" htmlFor="fullName">Full Name</label>
                            <div className="input-wrap">
                                <span className="input-icon material-symbols-outlined">person</span>
                                <input className="form-input" id="fullName" placeholder="Jane Doe" type="text" />
                            </div>
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="businessName">Business Name</label>
                            <div className="input-wrap">
                                <span className="input-icon material-symbols-outlined">storefront</span>
                                <input className="form-input" id="businessName" placeholder="Studio Roasters" type="text" />
                            </div>
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="email">Email</label>
                            <div className="input-wrap">
                                <span className="input-icon material-symbols-outlined">mail</span>
                                <input className="form-input" id="email" placeholder="jane@studioroasters.com" type="email" />
                            </div>
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="password">Password</label>
                            <div className="input-wrap">
                                <span className="input-icon material-symbols-outlined">lock</span>
                                <input className="form-input" id="password" placeholder="••••••••" type="password" />
                                <button className="password-toggle" type="button" aria-label="Toggle password visibility">
                                    <span className="material-symbols-outlined">visibility_off</span>
                                </button>
                            </div>
                        </div>

                        <div className="terms-row">
                            <div className="terms-checkbox-wrap">
                                <input className="terms-checkbox" id="terms" type="checkbox" />
                            </div>
                            <div className="terms-text-wrap">
                                <label className="terms-text" htmlFor="terms">
                                    I agree to the <a className="terms-link" href="#">Terms of Service</a> and <a className="terms-link" href="#">Privacy Policy</a>.
                                </label>
                            </div>
                        </div>

                        <div className="submit-row">
                            <button className="create-account-button" type="submit">
                                <span>Create Account</span>
                                <span className="material-symbols-outlined">arrow_forward</span>
                            </button>
                        </div>
                    </form>
                </div>

                <div className="signin-row">
                    <p className="signin-text">
                        Already have an account?{" "}
                        <Link to="/login" className="signin-link">
                            Sign In
                        </Link>
                    </p>
                </div>
            </main>
        </div>
    );
}
