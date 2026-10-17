import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import AnimatedRoutes from './AnimatedRoutes.jsx'
import Navbar from './assets/components/navbar.jsx'
import { AuthProvider } from './auth/AuthContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Navbar />
        <main className="route-content">
          <AnimatedRoutes />
        </main>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
