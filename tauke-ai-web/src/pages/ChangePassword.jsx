import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, ArrowLeft, CheckCircle2, AlertCircle, Loader2, ShieldCheck } from 'lucide-react';
import { supabase } from '../supabaseClient';
import './ChangePassword.css';

export default function ChangePassword() {
  const navigate = useNavigate();
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState({ type: null, message: '' });

  const handleUpdatePassword = async (e) => {
    e.preventDefault();

    if (newPassword !== confirmPassword) {
      setStatus({ type: 'error', message: 'Passwords do not match.' });
      return;
    }

    if (newPassword.length < 6) {
      setStatus({ type: 'error', message: 'Password must be at least 6 characters.' });
      return;
    }

    setIsSubmitting(true);
    setStatus({ type: null, message: '' });

    try {
      const { error } = await supabase.auth.updateUser({
        password: newPassword
      });

      if (error) throw error;

      setStatus({ type: 'success', message: 'Password updated successfully!' });

      // Navigate back after a short delay
      setTimeout(() => {
        navigate(-1);
      }, 2000);

    } catch (err) {
      console.error("Password update error:", err);
      setStatus({ type: 'error', message: err.message || 'Failed to update password. Please try logging in again.' });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="cp-layout">
      <motion.div
        className="cp-card"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <header className="cp-header">
          <button className="cp-back-btn" onClick={() => navigate(-1)}>
            <ArrowLeft size={18} /> Back to Dashboard
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <div style={{ padding: '10px', background: 'rgba(0, 88, 188, 0.1)', borderRadius: '12px' }}>
              <ShieldCheck color="#0058bc" size={24} />
            </div>
            <h1 className="cp-title">Security</h1>
          </div>
          <p className="cp-subtitle">Update your account password to keep your business intelligence secure.</p>
        </header>

        <form className="cp-form" onSubmit={handleUpdatePassword}>
          <AnimatePresence mode="wait">
            {status.type && (
              <motion.div
                className={`cp-status ${status.type}`}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
              >
                {status.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                {status.message}
              </motion.div>
            )}
          </AnimatePresence>

          <div className="cp-field">
            <label className="cp-label">New Password</label>
            <div className="cp-input-wrap">
              <Lock className="cp-input-icon" size={18} />
              <input
                type="password"
                className="cp-input"
                placeholder="Enter new password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
          </div>

          <div className="cp-field">
            <label className="cp-label">Confirm New Password</label>
            <div className="cp-input-wrap">
              <Lock className="cp-input-icon" size={18} />
              <input
                type="password"
                className="cp-input"
                placeholder="Confirm new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="cp-btn-submit"
            disabled={isSubmitting || status.type === 'success'}
          >
            {isSubmitting ? (
              <><Loader2 size={20} className="lucide-spin" /> Updating...</>
            ) : (
              'Update Password'
            )}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
