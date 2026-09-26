import { Routes, Route, Link, useNavigate, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { api } from './api';
import Dashboard from './pages/Dashboard';
import Analyze from './pages/Analyze';
import Proposals from './pages/Proposals';
import Settings from './pages/Settings';
import Profile from './pages/Profile';
import './App.css';

function NavBar() {
  const navigate = useNavigate();
  const [running, setRunning] = useState(false);

  useEffect(() => {
    api.getAutobidStatus().then(d => setRunning(d.running)).catch(() => {});
  }, []);

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <div className="brand-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
          </svg>
        </div>
        <span className="brand-text">Upwork Autopilot</span>
      </div>
      <div className="navbar-links">
        <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`} onClick={() => navigate('/')}>Dashboard</Link>
        <Link to="/analyze" className={`nav-link ${location.pathname === '/analyze' ? 'active' : ''}`} onClick={() => navigate('/analyze')}>Job Analyzer</Link>
        <Link to="/proposals" className={`nav-link ${location.pathname === '/proposals' ? 'active' : ''}`} onClick={() => navigate('/proposals')}>Proposals</Link>
        <Link to="/profile" className={`nav-link ${location.pathname === '/profile' ? 'active' : ''}`} onClick={() => navigate('/profile')}>Profile</Link>
        <Link to="/settings" className={`nav-link ${location.pathname === '/settings' ? 'active' : ''}`} onClick={() => navigate('/settings')}>Settings</Link>
      </div>
      <div className="navbar-status">
        {running ? (
          <span className="status-pill running">
            <span className="status-dot running"></span>
            Running
          </span>
        ) : (
          <span className="status-pill stopped">
            <span className="status-dot stopped"></span>
            Stopped
          </span>
        )}
      </div>
    </nav>
  );
}

function Footer() {
  return (
    <footer className="app-footer">
      <span>Upwork Autopilot — AI-powered proposal assistant</span>
    </footer>
  );
}

export default function App() {
  const location = useLocation();
  return (
    <div className="app">
      <NavBar />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/analyze" element={<Analyze />} />
          <Route path="/proposals" element={<Proposals />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
