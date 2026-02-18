import { AuthProvider, useAuth } from '@/context/AuthContext'
import { LoginPage } from '@/components/LoginPage'
import { Layout } from '@/components/Layout'
import { Toaster } from 'sonner'

function AppContent() {
  const { loggedIn } = useAuth()
  return loggedIn ? <Layout /> : <LoginPage />
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
      <Toaster position="top-right" richColors />
    </AuthProvider>
  )
}
