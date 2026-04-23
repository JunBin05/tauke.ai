export const MONTHS = [
  'Jan 2024', 'Feb 2024', 'Mar 2024', 'Apr 2024', 'May 2024', 'Jun 2024',
  'Jul 2024', 'Aug 2024', 'Sep 2024', 'Oct 2024', 'Nov 2024', 'Dec 2024'
];

export const MOCK_CHART_DATA = {
  'Oct 2023': [
    { name: '1 Oct', revenue: 45 },
    { name: '5 Oct', revenue: 52 },
    { name: '10 Oct', revenue: 48 },
    { name: '15 Oct', revenue: 70 },
    { name: '20 Oct', revenue: 65 },
    { name: '25 Oct', revenue: 85 },
    { name: '30 Oct', revenue: 80 },
  ],
  'Jan 2024': [
    { name: '1 Jan', revenue: 40 },
    { name: '5 Jan', revenue: 45 },
    { name: '10 Jan', revenue: 42 },
    { name: '15 Jan', revenue: 55 },
    { name: '20 Jan', revenue: 52 },
    { name: '25 Jan', revenue: 65 },
    { name: '30 Jan', revenue: 60 },
  ],
  'Feb 2024': [
    { name: '1 Feb', revenue: 50 },
    { name: '5 Feb', revenue: 58 },
    { name: '10 Feb', revenue: 55 },
    { name: '15 Feb', revenue: 75 },
    { name: '20 Feb', revenue: 72 },
    { name: '25 Feb', revenue: 95 },
    { name: '28 Feb', revenue: 90 },
  ],
};

// Default for other months to avoid empty charts
MONTHS.forEach(m => {
  if (!MOCK_CHART_DATA[m]) {
    MOCK_CHART_DATA[m] = Array.from({ length: 7 }, (_, i) => ({
      name: `${i * 4 + 1} ${m.split(' ')[0]}`,
      revenue: Math.floor(Math.random() * (90 - 40 + 1)) + 40
    }));
  }
});

export const EXTERNAL_INTELLIGENCE = [
  {
    id: '1',
    category: 'Competitor',
    title: 'Starbucks',
    content: 'Footfall decreased correlated with recent promotional end.',
    trend: 'down',
    percentage: '4.2%',
    progress: 75,
    color: '#ba1a1a'
  },
  {
    id: '2',
    category: 'Competitor',
    title: 'The Library Coffee',
    content: 'Capturing student demographic during mid-sem break via student bundle offers.',
    trend: 'up',
    percentage: '8.7%',
    progress: 80,
    color: '#0058bc'
  },
  {
    id: '3',
    category: 'Market',
    title: 'Costa Coffee',
    content: 'Increasing presence in office clusters with new grab-and-go kiosks.',
    trend: 'up',
    percentage: '5.1%',
    progress: 60,
    color: '#006e28'
  },
  {
    id: '4',
    category: 'Trend',
    title: 'Specialty Tea',
    content: 'Growing interest in cold-brew botanical teas among Gen Z customers.',
    trend: 'up',
    percentage: '12.4%',
    progress: 45,
    color: '#72fe88'
  }
];

export const PERFORMANCE_SUMMARIES = {
  'Oct 2023': {
    headline: 'Strong Q4 Kickoff',
    subheadline: 'Your revenue momentum is exceeding seasonal benchmarks.',
    insights: [
      { id: '1', type: 'growth', title: 'Retention Uplift', message: 'Retention rate up by 12% following the loyalty program update.' },
      { id: '2', type: 'efficiency', title: 'Peak Shift', message: 'Peak revenue hour shifted to 3 PM - 5 PM on weekdays.' },
      { id: '3', type: 'anomaly', title: 'Student Sensitivity', message: 'Anomaly detected during mid-sem break suggests high student sensitivity.' }
    ],
    score: '9.2'
  },
  'Jan 2024': {
    headline: 'Steady Post-Holiday Recovery',
    subheadline: 'Performance remains resilient despite natural seasonal dip.',
    insights: [
      { id: '1', type: 'growth', title: 'Transaction growth', message: 'Average transaction value grew by 4.5% compared to Dec 2023.' },
      { id: '2', type: 'growth', title: 'New Subscriptions', message: 'New morning subscription plan saw 200+ signups in the first week.' },
      { id: '3', type: 'efficiency', title: 'Automation Gains', message: 'Operational efficiency improved by 8% due to inventory automation.' }
    ],
    score: '7.8'
  },
  'Feb 2024': {
    headline: 'Exceptional Lunar New Year Surge',
    subheadline: 'Highest conversion rates recorded in the last 12 months.',
    insights: [
      { id: '1', type: 'growth', title: 'Festive Contribution', message: 'Gift hamper sales contributed to 24% of the total monthly revenue.' },
      { id: '2', type: 'anomaly', title: 'Footfall Peak', message: 'Customer footfall increased by 30% during festive promotion days.' },
      { id: '3', type: 'efficiency', title: 'Top Location', message: 'Top performing location discovered: KL Central branch.' }
    ],
    score: '9.8'
  }
};

// Default summaries for other months
MONTHS.forEach(m => {
  if (!PERFORMANCE_SUMMARIES[m]) {
    PERFORMANCE_SUMMARIES[m] = {
      headline: `Operating Report: ${m}`,
      subheadline: 'Performance aligns with projected growth metrics.',
      insights: [
        { id: '1', type: 'efficiency', title: 'Revenue variance', message: 'Revenue variance within expected 2% margin.' },
        { id: '2', type: 'growth', title: 'Stable CSAT', message: 'Customer satisfaction levels remain stable at 4.6/5.' },
        { id: '3', type: 'efficiency', title: 'Supply Chain', message: 'Supply chain overheads decreased by 3% this period.' }
      ],
      score: '8.4'
    };
  }
});
