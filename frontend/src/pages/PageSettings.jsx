import React from 'react'
import { Settings, HardDrive, Trash2 } from 'lucide-react'
import { useApp } from '../context/AppContext'
import { resetBackendSession } from '../services/api'

export default function PageSettings() {
  const { setChatHistory, setIndexedDocs, useMock, setUseMock, backendOnline } = useApp()

  const handlePurge = async () => {
    setIndexedDocs({})
    if (backendOnline) {
      await resetBackendSession().catch(() => {})
    }
    alert('Corpus memory purged.')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="grid-2">
        <div className="card">
          <div className="section-header">
            <Settings size={16} />
            <span>Air-Gapped Node Parameters</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div className="insight-row">
              <span className="insight-label">Execution Mode</span>
              <span className="insight-value" style={{ color: useMock ? 'var(--accent-orange)' : 'var(--accent-green)' }}>
                {useMock ? 'Mock Engine (Deterministic)' : 'Live Python Server (REST)'}
              </span>
            </div>

            <div className="insight-row">
              <span className="insight-label">Local Backend API</span>
              <span className="insight-value">http://localhost:8000</span>
            </div>

            <div className="insight-row">
              <span className="insight-label">Backend Status</span>
              <span className="insight-value" style={{ color: backendOnline ? 'var(--accent-green)' : 'var(--accent-orange)' }}>
                {backendOnline ? 'CONNECTED' : 'DISCONNECTED'}
              </span>
            </div>

            <div className="insight-row">
              <span className="insight-label">Remote Network Requests</span>
              <span className="insight-value" style={{ color: 'var(--accent-red)' }}>BLOCKED (Strict Air-Gap)</span>
            </div>

            <div style={{ marginTop: '10px' }}>
              <button className="btn btn-outline" onClick={() => setUseMock(!useMock)}>
                Toggle to {useMock ? 'Live Backend API' : 'Mock Mode'}
              </button>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="section-header">
            <HardDrive size={16} />
            <span>Session Reset & Data Purge</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              Clear current session transcripts and reset indexed memory stores.
            </p>

            <button
              className="btn btn-outline"
              style={{ color: 'var(--accent-orange)', width: 'fit-content' }}
              onClick={() => {
                setChatHistory([])
                alert('Transcript cleared.')
              }}
            >
              <Trash2 size={13} style={{ marginRight: '6px' }} />
              Clear Q&A Transcript
            </button>

            <button
              className="btn btn-outline"
              style={{ color: 'var(--accent-red)', width: 'fit-content' }}
              onClick={handlePurge}
            >
              <Trash2 size={13} style={{ marginRight: '6px' }} />
              Purge Document Memory
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

