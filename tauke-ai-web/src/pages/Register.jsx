import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom"; // 👈 Import useLocation
import { API_BASE_URL } from "../config";
import "./Register.css";

export default function Register() {
    const navigate = useNavigate();
    const location = useLocation(); // 👈 This catches the Google data!
    
    // Form State (Notice how it defaults to the Google data if it exists!)
    const [fullName, setFullName] = useState(location.state?.googleName || "");
    const [email, setEmail] = useState(location.state?.googleEmail || "");
    
    const [businessName, setBusinessName] = useState("");
    const [password, setPassword] = useState("");
    const [agreed, setAgreed] = useState(false);
    
    // UI State
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState("");

    const handleRegister = async (e) => {
        e.preventDefault();
        
        if (!agreed) {
            setErrorMessage("You must agree to the Terms of Service.");
            return;
        }

        setIsLoading(true);
        setErrorMessage("");

        try {
            // Sending exactly what the new backend expects
            const response = await fetch(`${API_BASE_URL}/auth/signup`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    email: email, 
                    password: password, 
                    business_name: businessName 
                }),
            });

            const data = await response.json();

            if (data.status === "success") {
                localStorage.setItem("owner_id", data.owner_id);
                navigate("/store-configuration"); 
            } else {
                setErrorMessage(data.message || "Registration failed.");
            }
        } catch (error) {
            console.error("Registration Error:", error);
            setErrorMessage("Could not connect to the server.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="register-page">
            <main className="register-main">
                <div className="register-brand">
                    <h1 className="register-title">Tauke.AI</h1>
                    <p className="register-subtitle">Assemble your AI Management Team.</p>
                </div>

                <div className="register-card">
                    <form className="register-form" onSubmit={handleRegister}>
                        {errorMessage && <p style={{color: '#ff3b30', fontSize: '14px', textAlign: 'center'}}>{errorMessage}</p>}
                        
                        <div className="form-group">
                            <label className="form-label" htmlFor="businessName">Business Name</label>
                            <div className="input-wrap">
                                <span className="input-icon material-symbols-outlined">storefront</span>
                                <input 
                                    className="form-input" 
                                    id="businessName" 
                                    placeholder="e.g. Maju Jaya Kopitiam" 
                                    type="text"
                                    value={businessName}
                                    onChange={(e) => setBusinessName(e.target.value)}
                                    required 
                                />
                            </div>
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="email">Email</label>
                            <div className="input-wrap">
                                <span className="input-icon material-symbols-outlined">mail</span>
                                <input 
                                    className="form-input" 
                                    id="email" 
                                    placeholder="e.g. ahmad@majujaya.com"
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    required 
                                />
                            </div>
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="password">Password</label>
                            <div className="input-wrap">
                                <span className="input-icon material-symbols-outlined">lock</span>
                                <input 
                                    className="form-input" 
                                    id="password" 
                                    placeholder="••••••••" 
                                    type={showPassword ? "text" : "password"}
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required 
                                />
                                <button 
                                    className="password-toggle" 
                                    type="button" 
                                    onClick={() => setShowPassword(!showPassword)}
                                    aria-label="Toggle password visibility"
                                >
                                    <span className="material-symbols-outlined">
                                        {showPassword ? "visibility" : "visibility_off"}
                                    </span>
                                </button>
                            </div>
                        </div>

                        <div className="terms-row">
                            <div className="terms-checkbox-wrap">
                                <input 
                                    className="terms-checkbox" 
                                    id="terms" 
                                    type="checkbox"
                                    checked={agreed}
                                    onChange={(e) => setAgreed(e.target.checked)}
                                />
                            </div>
                            <div className="terms-text-wrap">
                                <label className="terms-text" htmlFor="terms">
                                    I agree to the <a className="terms-link" href="#">Terms of Service</a> and <a className="terms-link" href="#">Privacy Policy</a>.
                                </label>
                            </div>
                        </div>

                        <div className="submit-row">
                            <button className="create-account-button" type="submit" disabled={isLoading}>
                                <span>{isLoading ? "Creating..." : "Create Account"}</span>
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