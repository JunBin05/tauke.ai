import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import AppLayout from "./components/AppLayout";

import Login from "./pages/Login";
import Register from "./pages/Register";
import StoreConfiguration from "./pages/StoreConfiguration";
import DataSync from "./pages/DataSync";
import DetectiveAnalysis from "./pages/DetectiveAnalysis";
import SupervisorClarification from "./pages/SupervisorClarification";
import AIDebate from "./pages/AIDebate";
import FinalSynthesis from "./pages/FinalSynthesis";
import CampaignRoadmap from "./pages/CampaignRoadmap";
import Landing from "./pages/Landing";
import LoadingPage from "./pages/LoadingPage";
import GoogleSync from "./pages/GoogleSync";
import Dashboard from './pages/Dashboard';
import SwarmSimulation from './pages/SwarmSimulation';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ── Full-screen routes (no sidebar) ── */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/loading" element={<LoadingPage />} />

        {/* ── App routes wrapped with the global sidebar layout ── */}
        <Route element={<AppLayout />}>
          <Route path="/store-configuration" element={<StoreConfiguration />} />
          <Route path="/landing" element={<Landing />} />
          <Route path="/data-sync" element={<DataSync />} />
          <Route path="/supervisor-clarification" element={<SupervisorClarification />} />
          <Route path="/detective-analysis" element={<DetectiveAnalysis />} />
          <Route path="/ai-debate" element={<AIDebate />} />
          <Route path="/final-synthesis" element={<FinalSynthesis />} />
          <Route path="/campaign-roadmap" element={<CampaignRoadmap />} />
          <Route path="/simulation" element={<SwarmSimulation />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/sync" element={<GoogleSync />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;