import React, { useState, useRef } from 'react'
import {
  Upload,
  FolderOpen,
  Trash2,
  ChevronDown,
  ChevronRight,
  Layers,
  FileText,
  Play,
  X,
  CheckCircle2,
  AlertCircle
} from 'lucide-react'
import { useApp } from '../context/AppContext'
import { indexDocumentFile, removeDocument, removeChunk, fetchIndexedDocuments } from '../services/api'

export default function PageDocumentLibrary() {
  const { indexedDocs, setIndexedDocs, useMock, backendOnline } = useApp()
  const [equipmentModel, setEquipmentModel] = useState('')
  const [isSynthetic, setIsSynthetic] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)
  const [statusType, setStatusType] = useState('success') // 'success' | 'error' | 'info'
  const [expandedDocs, setExpandedDocs] = useState({})
  const [selectedFile, setSelectedFile] = useState(null)
  const [indexingInProgress, setIndexingInProgress] = useState(false)
  const fileInputRef = useRef(null)

  const toggleExpand = (fname) => {
    setExpandedDocs((prev) => ({ ...prev, [fname]: !prev[fname] }))
  }

  const handleFileSelected = (file) => {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setStatusType('error')
      setStatusMsg('Please select a valid PDF manual or SOP file.')
      setTimeout(() => setStatusMsg(null), 4000)
      return
    }
    setSelectedFile(file)
    setStatusType('info')
    setStatusMsg(`Selected '${file.name}' (${(file.size / 1024).toFixed(1)} KB). Click "Start Indexing" to process.`)
  }

  const handleStartIndexing = async () => {
    if (!selectedFile) {
      setStatusType('error')
      setStatusMsg('Please choose a PDF file first.')
      setTimeout(() => setStatusMsg(null), 3000)
      return
    }

    setIndexingInProgress(true)
    setStatusType('info')
    setStatusMsg(`Parsing and extracting text chunks from '${selectedFile.name}'...`)

    try {
      if (!useMock && backendOnline) {
        const res = await indexDocumentFile(selectedFile, equipmentModel, isSynthetic)
        
        // Immediately fetch updated documents from backend
        const backendRes = await fetchIndexedDocuments()
        const docs = backendRes.documents || {}
        const chunksByDoc = backendRes.chunks || {}
        
        if (docs && Object.keys(docs).length > 0) {
          const formatted = {}
          Object.entries(docs).forEach(([fname, meta]) => {
            formatted[fname] = {
              ...meta,
              chunks: chunksByDoc[fname] || [],
            }
          })
          setIndexedDocs(formatted)
        } else {
          // Fallback update in state if backend list not ready
          setIndexedDocs((prev) => ({
            ...prev,
            [selectedFile.name]: {
              document_id: res.document_id || `doc_${Date.now().toString(16)}`,
              chunks_count: res.chunks_indexed || 1,
              equipment_model: equipmentModel.trim() || 'SIMATIC S7-1200',
              synthetic: isSynthetic,
              chunks: [],
            },
          }))
        }
        
        setStatusType('success')
        setStatusMsg(`Successfully indexed ${res.chunks_indexed} chunks for '${selectedFile.name}' into vector store.`)
      } else {
        const docId = `doc_${Math.abs(selectedFile.name.split('').reduce((a, b) => ((a << 5) - a) + b.charCodeAt(0), 0)).toString(16).slice(0, 8)}`
        const chunksCount = Math.max(3, Math.floor(selectedFile.size / 2048) || 4)
        const mockChunks = Array.from({ length: chunksCount }).map((_, i) => ({
          chunk_id: `${docId}#p${i + 1}#c${i}`,
          page: i + 1,
          text: `Operating instructions section ${i + 1} for ${equipmentModel || 'SIMATIC S7-1200'}. Inspect power rails, terminal wiring, and verify safety protocols.`,
          equipment_model: equipmentModel.trim() || 'SIMATIC S7-1200',
        }))

        setIndexedDocs((prev) => ({
          ...prev,
          [selectedFile.name]: {
            document_id: docId,
            chunks_count: chunksCount,
            equipment_model: equipmentModel.trim() || 'SIMATIC S7-1200',
            synthetic: isSynthetic,
            chunks: mockChunks,
          },
        }))
        setStatusType('success')
        setStatusMsg(`Indexed ${chunksCount} chunks for '${selectedFile.name}' into mock corpus.`)
      }
      setSelectedFile(null)
    } catch (err) {
      setStatusType('error')
      setStatusMsg(`Indexing failed: ${err.message}`)
    } finally {
      setIndexingInProgress(false)
      setTimeout(() => setStatusMsg(null), 5000)
    }
  }

  const handleRemoveDoc = async (filename) => {
    if (!confirm(`Are you sure you want to remove '${filename}' and all its chunks?`)) return

    if (!useMock && backendOnline) {
      try {
        await removeDocument(filename)
      } catch (err) {
        console.warn('Backend delete error:', err)
      }
    }

    setIndexedDocs((prev) => {
      const copy = { ...prev }
      delete copy[filename]
      return copy
    })
    setStatusType('info')
    setStatusMsg(`Removed document '${filename}'`)
    setTimeout(() => setStatusMsg(null), 3000)
  }

  const handleRemoveChunk = async (filename, chunkId) => {
    if (!useMock && backendOnline) {
      try {
        await removeChunk(chunkId, filename)
      } catch (err) {
        console.warn('Backend chunk delete error:', err)
      }
    }

    setIndexedDocs((prev) => {
      const doc = prev[filename]
      if (!doc) return prev
      const updatedChunks = (doc.chunks || []).filter((c) => c.chunk_id !== chunkId)
      return {
        ...prev,
        [filename]: {
          ...doc,
          chunks: updatedChunks,
          chunks_count: Math.max(0, (doc.chunks_count || 1) - 1),
        },
      }
    })
    setStatusType('info')
    setStatusMsg(`Removed chunk '${chunkId}'`)
    setTimeout(() => setStatusMsg(null), 3000)
  }

  const handleLoadDemoSOPs = () => {
    setIndexedDocs({
      'SOP_SIMATIC_S7-1200.pdf': {
        document_id: 'doc_s7_1200_sop',
        chunks_count: 4,
        equipment_model: 'SIMATIC S7-1200 CPU 1214C',
        synthetic: true,
        chunks: [
          { chunk_id: 'doc_s7_1200_sop#p1#c0', page: 1, text: 'Safety instructions: Disconnect power before maintenance. Check LOTO status.' },
          { chunk_id: 'doc_s7_1200_sop#p2#c1', page: 2, text: 'CPU status LED indicators: RUN/STOP green indicates execution. ERROR red indicates fault.' },
          { chunk_id: 'doc_s7_1200_sop#p3#c2', page: 3, text: 'Digital input/output wiring guidelines. Nominal 24V DC auxiliary power supply.' },
          { chunk_id: 'doc_s7_1200_sop#p4#c3', page: 4, text: 'PROFINET communication port diagnostic buffer and interface parameters.' },
        ],
      },
      'Pump_Hydraulic_Manual.pdf': {
        document_id: 'doc_pump_hyd_sop',
        chunks_count: 3,
        equipment_model: 'HydroForce H-400',
        synthetic: true,
        chunks: [
          { chunk_id: 'doc_pump_hyd_sop#p1#c0', page: 1, text: 'Hydraulic pump start-up check: Check oil reservoir level and fluid clarity.' },
          { chunk_id: 'doc_pump_hyd_sop#p2#c1', page: 2, text: 'Relief valve calibration and maximum pressure limit settings (250 bar).' },
          { chunk_id: 'doc_pump_hyd_sop#p3#c2', page: 3, text: 'Seal replacement procedures and preventive maintenance schedule.' },
        ],
      },
    })
    setStatusType('success')
    setStatusMsg('Loaded default factory SOP documents with viewable chunks.')
    setTimeout(() => setStatusMsg(null), 3000)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="grid-2">
        {/* Upload Card */}
        <div className="card">
          <div className="section-header">
            <Upload size={16} />
            <span>Upload & Index Technical Document</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              accept=".pdf"
              onChange={(e) => {
                if (e.target.files?.[0]) {
                  handleFileSelected(e.target.files[0])
                }
              }}
            />

            {/* Drag & Drop / Click Zone */}
            <div
              className="upload-zone"
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="upload-zone-icon">📄</div>
              <div className="upload-zone-text">
                {selectedFile ? `Selected: ${selectedFile.name}` : 'Click to choose an Equipment Manual or SOP (PDF)'}
              </div>
              <div className="upload-zone-sub">
                {selectedFile ? `${(selectedFile.size / 1024).toFixed(1)} KB — Ready to index` : 'Air-gapped extraction & chunking per contracts.py'}
              </div>
            </div>

            {/* Selected File Chip */}
            {selectedFile && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'rgba(34, 211, 238, 0.08)',
                border: '1px solid rgba(34, 211, 238, 0.25)',
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '0.8rem',
                color: 'var(--accent-cyan)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                  <FileText size={16} flexShrink={0} />
                  <span style={{ fontWeight: 500, textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                    {selectedFile.name}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedFile(null)
                  }}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center'
                  }}
                  title="Remove selected file"
                >
                  <X size={14} />
                </button>
              </div>
            )}

            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                Equipment Model Tag (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. S7-1200 CPU 1214C"
                value={equipmentModel}
                onChange={(e) => setEquipmentModel(e.target.value)}
                style={{
                  width: '100%',
                  background: 'var(--bg-card2)',
                  border: '1px solid var(--border)',
                  borderRadius: '6px',
                  padding: '8px 12px',
                  color: 'var(--text-primary)',
                  fontSize: '0.82rem',
                }}
              />
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              <input
                type="checkbox"
                checked={isSynthetic}
                onChange={(e) => setIsSynthetic(e.target.checked)}
                style={{ accentColor: 'var(--accent-cyan)' }}
              />
              <span>Mark as synthetic test data</span>
            </label>

            {/* Action Buttons: START INDEXING & Demo Loader */}
            <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleStartIndexing}
                disabled={indexingInProgress || !selectedFile}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '9px 18px',
                  fontSize: '0.84rem',
                  opacity: (!selectedFile || indexingInProgress) ? 0.5 : 1,
                  cursor: (!selectedFile || indexingInProgress) ? 'not-allowed' : 'pointer'
                }}
              >
                <Play size={15} fill="currentColor" />
                <span>{indexingInProgress ? 'Indexing Document...' : 'Start Indexing'}</span>
              </button>

              <button
                type="button"
                className="btn btn-outline"
                onClick={handleLoadDemoSOPs}
                style={{ padding: '9px 14px', fontSize: '0.82rem' }}
              >
                Load Demo SOP Library
              </button>
            </div>

            {/* Status Message Display */}
            {statusMsg && (
              <div style={{
                background: statusType === 'error'
                  ? 'rgba(248, 113, 113, 0.1)'
                  : statusType === 'info'
                    ? 'rgba(56, 189, 248, 0.1)'
                    : 'rgba(52, 211, 153, 0.1)',
                borderLeft: `3px solid ${
                  statusType === 'error'
                    ? 'var(--accent-red)'
                    : statusType === 'info'
                      ? 'var(--accent-blue)'
                      : 'var(--accent-green)'
                }`,
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '0.78rem',
                color: statusType === 'error'
                  ? 'var(--accent-red)'
                  : statusType === 'info'
                    ? 'var(--accent-blue)'
                    : 'var(--accent-green)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                {statusType === 'error' ? <AlertCircle size={15} /> : <CheckCircle2 size={15} />}
                <span>{statusMsg}</span>
              </div>
            )}
          </div>
        </div>

        {/* Corpus Management & Chunk Inspector */}
        <div className="card">
          <div className="section-header" style={{ justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FolderOpen size={16} />
              <span>Document Corpus ({Object.keys(indexedDocs).length})</span>
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Expand to inspect & delete chunks
            </span>
          </div>

          {Object.keys(indexedDocs).length === 0 ? (
            <div style={{
              height: '240px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)'
            }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '8px' }}>📂</div>
              <div>No documents currently indexed</div>
              <div style={{ fontSize: '0.75rem', marginTop: '4px' }}>Select a PDF on the left and click "Start Indexing"</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {Object.entries(indexedDocs).map(([fname, info]) => {
                const isExpanded = expandedDocs[fname]
                const chunks = info.chunks || []

                return (
                  <div
                    key={fname}
                    style={{
                      background: 'var(--bg-card2)',
                      border: '1px solid var(--border)',
                      borderRadius: '8px',
                      overflow: 'hidden',
                    }}
                  >
                    {/* Document Header Row */}
                    <div style={{
                      padding: '12px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      borderBottom: isExpanded ? '1px solid var(--border)' : 'none',
                    }}>
                      <div
                        style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', flex: 1 }}
                        onClick={() => toggleExpand(fname)}
                      >
                        {isExpanded ? <ChevronDown size={16} color="var(--accent-cyan)" /> : <ChevronRight size={16} color="var(--text-muted)" />}
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>📄 {fname}</div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                            ID: <code>{info.document_id}</code> • Model: <span style={{ color: 'var(--accent-cyan)' }}>{info.equipment_model}</span>
                            {info.synthetic && ' • [Synthetic]'}
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div style={{ textAlign: 'right' }}>
                          <span style={{ color: 'var(--accent-green)', fontWeight: 700, fontSize: '0.9rem' }}>
                            {info.chunks_count}
                          </span>
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}> chunks</span>
                        </div>

                        {/* Delete Document Button */}
                        <button
                          type="button"
                          className="btn btn-outline"
                          title="Remove this document from corpus"
                          style={{
                            color: 'var(--accent-red)',
                            borderColor: 'rgba(248, 113, 113, 0.25)',
                            padding: '4px 8px'
                          }}
                          onClick={() => handleRemoveDoc(fname)}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>

                    {/* Expandable Chunk List */}
                    {isExpanded && (
                      <div style={{ padding: '10px 14px', background: '#0a1424' }}>
                        <div style={{
                          fontSize: '0.72rem',
                          color: 'var(--text-muted)',
                          marginBottom: '8px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px'
                        }}>
                          <Layers size={13} />
                          <span>Extracted Chunks (Individual Vector Entities)</span>
                        </div>

                        {chunks.length === 0 ? (
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', padding: '6px 0' }}>
                            No detailed chunk breakdown available for this file.
                          </div>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {chunks.map((chk, cIdx) => (
                              <div
                                key={chk.chunk_id || cIdx}
                                style={{
                                  background: 'var(--bg-card2)',
                                  border: '1px solid var(--border)',
                                  borderRadius: '6px',
                                  padding: '8px 10px',
                                  display: 'flex',
                                  alignItems: 'flex-start',
                                  justifyContent: 'space-between',
                                  gap: '10px',
                                }}
                              >
                                <div style={{ flex: 1 }}>
                                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: '3px' }}>
                                    <code>{chk.chunk_id}</code> • Page {chk.page}
                                  </div>
                                  <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                                    {chk.text}
                                  </div>
                                </div>

                                <button
                                  type="button"
                                  className="btn btn-outline"
                                  title="Delete this chunk"
                                  style={{
                                    color: 'var(--accent-red)',
                                    borderColor: 'rgba(248, 113, 113, 0.2)',
                                    padding: '3px 6px',
                                    flexShrink: 0,
                                  }}
                                  onClick={() => handleRemoveChunk(fname, chk.chunk_id)}
                                >
                                  <Trash2 size={11} />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
