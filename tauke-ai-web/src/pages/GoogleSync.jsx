import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../supabaseClient";
import { API_BASE_URL } from "../config";

export default function GoogleSync() {
    const navigate = useNavigate();

    useEffect(() => {
        const syncAccount = async () => {
            // 1. Grab the session Google just handed back to Supabase
            const { data: { session }, error } = await supabase.auth.getSession();

            if (error || !session) {
                console.error("No Google session found");
                navigate("/login");
                return;
            }

            try {
                // 2. Fire your exact Python endpoint!
                // We use their Google Name to create a placeholder Business Name
                const googleName = session.user.user_metadata.full_name || "New Boss";
                
                const response = await fetch(`${API_BASE_URL}/auth/sync-google-profile`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        access_token: session.access_token,
                        name: `${googleName}'s Cafe` // We just send the name now!
                    })
                });

                const data = await response.json();

                if (data.status === "success") {
                    // Save the credentials
                    localStorage.setItem("owner_id", data.owner_id);
                    localStorage.setItem("access_token", session.access_token);
                    
                    // 👇 THE BULLETPROOF ROUTING LOGIC 👇
                    if (!data.profile_complete) {
                        // Profile is missing data -> Send to Store Configuration!
                        navigate("/store-configuration"); 
                    } else {
                        // Profile is 100% complete -> Send to the Dashboard!
                        navigate("/landing"); 
                    }
                }else {
                    console.error("Backend Sync Failed:", data.message);
                    navigate("/login");
                }
            } catch (err) {
                console.error("Network error during sync", err);
                navigate("/login");
            }
        };

        syncAccount();
    }, [navigate]);

    return (
        <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', fontFamily: 'Inter, sans-serif' }}>
            <h2>Syncing your Boss profile...</h2>
        </div>
    );
}