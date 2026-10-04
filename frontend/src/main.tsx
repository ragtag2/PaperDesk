import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { AuthProvider } from './app/AuthContext'
import { App } from './app/App'
import './styles/index.css'
import './styles/notifications.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider><App /></AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
