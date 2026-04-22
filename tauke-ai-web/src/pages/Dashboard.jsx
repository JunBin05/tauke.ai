import React from 'react';
import { motion } from 'framer-motion';
import { Users, TrendingUp, ShieldCheck, Clock, ArrowUpRight } from 'lucide-react';

export default function Dashboard() {
  return (
    <div className="dashboard-container">
      <div className="bg-decor-top" />
      <div className="bg-decor-bottom" />

      <main style={{ width: '100%', maxWidth: '1280px', margin: '0 auto', paddingTop: '4rem', zIndex: 10 }}>
        <header style={{ marginBottom: '3rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <h1 className="label-caps">MANAGEMENT DASHBOARD</h1>
            <h2 style={{ fontSize: '2.25rem', fontWeight: 700, color: '#1a1c1d' }}>Simulation Analysis Report</h2>
          </div>
        </header>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.5rem', marginBottom: '3rem' }}>
          {[
            { label: 'Total Synchronized', value: '2,840', unit: 'Agents', icon: Users, color: '#0058bc' },
            { label: 'Average Throughput', value: '92.4', unit: '%', icon: TrendingUp, color: '#006e28' },
            { label: 'Uptime Reliability', value: '99.9', unit: '%', icon: ShieldCheck, color: '#0058bc' },
            { label: 'Session Duration', value: '42:15', unit: 'Minutes', icon: Clock, color: '#717786' },
          ].map((stat, i) => (
            <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }} className="stat-card">
              <stat.icon style={{ color: stat.color, marginBottom: '1rem' }} size={32} />
              <h3 className="label-caps">{stat.label}</h3>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.875rem', fontWeight: 700 }}>{stat.value}</span>
                <span style={{ fontSize: '0.875rem', color: '#717786' }}>{stat.unit}</span>
              </div>
            </motion.div>
          ))}
        </div>
      </main>
    </div>
  );
}