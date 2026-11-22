import { Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from './auth/AuthContext.jsx'
import Layout from './components/Layout.jsx'
import ComparisonDetailPage from './pages/ComparisonDetailPage.jsx'
import ComparisonsPage from './pages/ComparisonsPage.jsx'
import DocumentsPage from './pages/DocumentsPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import SearchPage from './pages/SearchPage.jsx'

function RequireAuth({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/comparisons" replace />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/comparisons" element={<ComparisonsPage />} />
        <Route path="/comparisons/:id" element={<ComparisonDetailPage />} />
        <Route path="/search" element={<SearchPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
