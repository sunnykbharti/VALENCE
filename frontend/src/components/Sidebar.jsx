import React from 'react'
import {
  LayoutDashboard,
  Cpu,
  Wrench,
  Bot,
  FolderOpen,
  Settings as SettingsIcon
} from 'lucide-react'
import { useApp } from '../context/AppContext'

export default function Sidebar({ pages, activePage, setActivePage, useMock, setUseMock, backendOnline }) {
  const { chatHistory } = useApp()

  const getIcon = (page) => {
    switch (page) {
      case 'Overview': return <LayoutDashboard size={18} strokeWidth={1.8} />
      case 'Query Assistant': return <Bot size={18} strokeWidth={1.8} />
      case 'Image Analysis': return <Cpu size={18} strokeWidth={1.8} />
      case 'Document Library': return <FolderOpen size={18} strokeWidth={1.8} />
      case 'Settings': return <SettingsIcon size={18} strokeWidth={1.8} />
      default: return <LayoutDashboard size={18} strokeWidth={1.8} />
    }
  }

  // Extract user queries from chat history in reverse chronological order
  const userQueries = chatHistory
    .filter((m) => m.role === 'user' && m.content)
    .map((m) => m.content.trim())

  const recentSearches = Array.from(new Set(userQueries.reverse())).slice(0, 10)

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Wrench size={18} color="#ffffff" strokeWidth={2} />
        </div>
        <div>
          <div className="sidebar-logo-name">VALENCE</div>
          <div className="sidebar-logo-sub">Smart Maintenance</div>
        </div>
      </div>

      {/* Navigation Links */}
      <div className="sidebar-nav">
        {pages.map((p) => {
          const isActive = activePage === p
          return (
            <button
              key={p}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => setActivePage(p)}
            >
              {getIcon(p)}
              <span>{p}</span>
              {p === 'Query Assistant' && <span className="nav-badge">AI</span>}
            </button>
          )
        })}

        {/* Recents Section matching exact font, layout & dark blue styling */}
        <div style={{ marginTop: '22px', padding: '0 4px' }}>
          <div style={{
            fontSize: '0.82rem',
            fontWeight: 500,
            color: '#64748b',
            padding: '6px 12px',
            letterSpacing: '-0.01em',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
          }}>
            Recents
          </div>

          {recentSearches.length === 0 ? (
            <div style={{
              fontSize: '0.86rem',
              color: '#475569',
              padding: '6px 12px',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
            }}>
              No recent searches
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
              {recentSearches.map((query, idx) => (
                <button
                  key={idx}
                  onClick={() => setActivePage('Query Assistant')}
                  title={query}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    background: 'transparent',
                    border: 'none',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    color: '#cbd5e1',
                    fontSize: '0.88rem',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.07)'
                    e.currentTarget.style.color = '#ffffff'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = '#cbd5e1'
                  }}
                >
                  {query}
                </button>
              ))}
            </div>
          )}
        </div>

        <div style={{ margin: '18px 8px 10px', borderTop: '1px solid rgba(255, 255, 255, 0.07)' }} />

        {/* Mock Mode Toggle */}
        <div style={{ padding: '6px 12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
            fontSize: '0.82rem',
            color: '#cbd5e1',
            fontWeight: 500
          }}>
            <input
              type="checkbox"
              checked={useMock}
              onChange={(e) => setUseMock(e.target.checked)}
              style={{ accentColor: '#38bdf8' }}
            />
            <span>Mock Engine</span>
          </label>
          <span style={{ fontSize: '0.7rem', color: '#64748b', paddingLeft: '22px' }}>
            {useMock ? 'In-memory mock backend' : 'Direct Python REST API'}
          </span>
        </div>
      </div>

      {/* Footer Connectivity Indicators */}
      <div className="sidebar-footer">
        <div className="sidebar-status-row">
          <span className={`dot ${backendOnline ? 'dot-green' : 'dot-orange'}`} />
          <span>{backendOnline ? 'Backend API Online' : 'Backend Connecting...'}</span>
        </div>
        <div className="sidebar-status-row">
          <span className="dot dot-green" />
          <span>Air-Gapped Offline</span>
        </div>
        <div className="sidebar-status-row">
          <span className="dot dot-green" />
          <span>VLM Diagnostic Ready</span>
        </div>
      </div>
    </aside>
  )
}
