import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

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
// Inside your App.jsx Router:
import Simulation from './pages/Simulation';
import Dashboard from './pages/Dashboard';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/store-configuration" element={<StoreConfiguration />} />
        <Route path="/data-sync" element={<DataSync />} />
        <Route path="/detective-analysis" element={<DetectiveAnalysis />} />
        <Route path="/supervisor-clarification" element={<SupervisorClarification />} />
        <Route path="/ai-debate" element={<AIDebate />} />
        <Route path="/final-synthesis" element={<FinalSynthesis />} />
        <Route path="/campaign-roadmap" element={<CampaignRoadmap />} />
        <Route path="/landing" element={<Landing />} />
        <Route path="/loading" element={<LoadingPage />} />
        <Route path="/sync" element={<GoogleSync />} />
        <Route path="/simulation" element={<Simulation />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;