import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Settings, User, BarChart3, Store, ArrowUp, ArrowDown, Users, Bolt, Activity } from 'lucide-react';

export default function LoadingScreen() {
  const navigate = useNavigate();
  const [progress, setProgress] = useState(0);
  const [queue, setQueue] = useState(Array.from({ length: 5 }, (_, i) => ({ id: `p-${i}`, status: 'queued' })));
  const [nextId, setNextId] = useState(5);
  const [showShopPulse, setShowShopPulse] = useState(false);
  const totalSlots = 10; // Sped up for demo purposes!

  const processQueue = useCallback(() => {
    if (progress >= 100) {
      navigate('/dashboard'); // Jump to the final dashboard!
      return;
    }

    setQueue(prev => {
      const newQueue = [...prev];
      if (newQueue.length === 0) return newQueue;

      const person = { ...newQueue[0], status: 'moving' };
      newQueue[0] = person;

      setTimeout(() => {
        setQueue(q => {
          const updated = [...q];
          if (updated[0]) updated[0] = { ...updated[0], status: 'deciding' };
          return updated;
        });

        setTimeout(() => {
          const isAccepted = Math.random() > 0.4;
          setQueue(q => {
            const updated = [...q];
            if (updated[0]) updated[0] = { ...updated[0], status: isAccepted ? 'accepted' : 'rejected' };
            return updated;
          });

          if (isAccepted) {
            setProgress(p => Math.min(p + (100 / totalSlots), 100));
            setTimeout(() => setShowShopPulse(true), 500);
            setTimeout(() => setShowShopPulse(false), 1200);
          }

          setTimeout(() => {
            setQueue(q => [...q.filter((_, i) => i !== 0), { id: `p-${nextId + Math.random()}`, status: 'queued' }]);
            setNextId(n => n + 1);
          }, 1000);
        }, 800);
      }, 800);

      return newQueue;
    });
  }, [progress, nextId, navigate]);

  useEffect(() => {
    const interval = setInterval(processQueue, 3000);
    return () => clearInterval(interval);
  }, [processQueue]);

  return (
    <div className="app-container">
      <div className="bg-decor-top" />
      <div className="bg-decor-bottom" />
      
      <main style={{ width: '100%', maxWidth: '1024px', display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: '6rem', margin: '0 auto', zIndex: 10 }}>
        <div style={{ marginBottom: '2.5rem', textAlign: 'center' }}>
          <h1 className="label-caps">INITIALIZING SIMULATION</h1>
          <p style={{color: '#717786'}}>Analyzing queue dynamics... Please wait.</p>
        </div>

        <div className="glass-card">
          <div style={{ display: 'flex', alignItems: 'center', zIndex: 10, width: '100%', position: 'relative', height: '100%' }}>
            
            {/* The Queue (Left) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', position: 'relative', width: '40%' }}>
              <AnimatePresence mode="popLayout">
                {queue.map((person, index) => (
                  <motion.div
                    key={person.id}
                    layout
                    initial={{ opacity: 0, x: -50 }}
                    animate={{ 
                      opacity: 1, 
                      x: ['moving', 'deciding', 'accepted', 'rejected'].includes(person.status) ? 250 : 0,
                      scale: ['moving', 'deciding'].includes(person.status) ? 1.3 : (index === 0 ? 1.1 : 1),
                      zIndex: index === 0 ? 50 : 10,
                      backgroundColor: person.status === 'accepted' ? '#72fe88' : person.status === 'rejected' ? '#ffdad6' : '#ffffff',
                      borderColor: person.status === 'accepted' ? '#006e28' : person.status === 'rejected' ? '#ba1a1a' : (index === 0 ? '#0058bc' : 'transparent'),
                    }}
                    exit={{ opacity: 0, filter: 'blur(8px)' }}
                    className={`person-icon ${index === 0 ? 'active' : ''}`}
                  >
                    <User size={32} style={{ color: person.status === 'accepted' ? '#006e28' : person.status === 'rejected' ? '#ba1a1a' : '#0058bc' }} />
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>

            {/* The Shop (Right) */}
            <div style={{ position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)', zIndex: 10 }}>
              <motion.div 
                animate={showShopPulse ? { scale: [1, 1.05, 1] } : {}}
                style={{ width: '16rem', height: '13rem', backgroundColor: 'white', borderRadius: '0.75rem', padding: '1.5rem', boxShadow: '0 10px 15px rgba(0,0,0,0.1)' }}
              >
                 <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                    <Store style={{ color: 'rgba(0, 88, 188, 0.3)' }} size={48} />
                 </div>
              </motion.div>
            </div>
          </div>

          <div style={{ position: 'absolute', bottom: 0, left: 0, width: '100%', padding: '0 2.5rem 2rem 2.5rem' }}>
            <div className="progress-container">
              <motion.div className="progress-fill" animate={{ width: `${progress}%` }} />
            </div>
            <p style={{textAlign: 'center', marginTop: '1rem', fontSize: '12px', fontWeight: 'bold'}}>{Math.round(progress)}% SYNCHRONIZED</p>
          </div>
        </div>
      </main>
    </div>
  );
}