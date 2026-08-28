import { BrowserRouter as Router, Routes, Route, useLocation } from "react-router-dom";
import { AuthProvider } from "context/AuthContext";
import { BatteryProvider } from "context/BatteryContext";
import ProtectedRoute from "components/ProtectedRoute/ProtectedRoute";
import MainNavbar from "components/MainNavbar/MainNavbar";
import PinPage from "pages/PinPage/PinPage";
import Dashboard from "pages/Dashboard/Dashboard";
import LogViewer from "pages/LogViewer/LogViewer";
import Commissioning from "pages/Commissioning/Commissioning";

import "./styles/variables.css";
import "./App.css";

function AppContent() {
  const location = useLocation();
  const isPinPage = location.pathname === "/pin";

  return (
    <div className={`appLayout ${isPinPage ? "appLayout--pin" : ""}`}>
      {!isPinPage && <MainNavbar />}
      <main className="appMain">
        <div className="appMain-inner">
          <Routes>
            <Route path="/pin" element={<PinPage />} />
            <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/logs" element={<ProtectedRoute><LogViewer /></ProtectedRoute>} />
            <Route path="/commissioning" element={<ProtectedRoute><Commissioning /></ProtectedRoute>} />
            <Route path="*" element={<ProtectedRoute><div className="text-center mt-4">404 Not Found</div></ProtectedRoute>} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BatteryProvider>
        <Router>
          <AppContent />
        </Router>
      </BatteryProvider>
    </AuthProvider>
  );
}
