import { Routes, Route, Navigate } from "react-router-dom"
import { useAuthStore } from "../store/authStore"
import LoginPage              from "../pages/LoginPage"
import PlantationProjectsPage from "../pages/PlantationProjectsPage"
import NewProjectWizardPage   from "../pages/NewProjectWizardPage"
import SatelliteAnalysisPage  from "../pages/SatelliteAnalysisPage"

function ProtectedRoute({ children }) {
    const user = useAuthStore((s) => s.user)
    return user ? children : <Navigate to="/" replace />
}

export default function AppRoutes() {
    return (
        <Routes>
            <Route path="/"          element={<LoginPage />} />
            <Route path="/dashboard" element={<ProtectedRoute><PlantationProjectsPage /></ProtectedRoute>} />
            <Route path="/projects/new" element={<ProtectedRoute><NewProjectWizardPage /></ProtectedRoute>} />
            <Route path="/analysis"  element={<ProtectedRoute><SatelliteAnalysisPage /></ProtectedRoute>} />
            <Route path="*"          element={<Navigate to="/" replace />} />
        </Routes>
    )
}
