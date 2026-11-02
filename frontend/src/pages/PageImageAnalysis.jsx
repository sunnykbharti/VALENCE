import React, { useRef } from 'react'
import { Upload, Image as ImageIcon, Trash2, Cpu } from 'lucide-react'
import { useApp } from '../context/AppContext'

export default function PageImageAnalysis() {
  const { visionImage, setVisionImage } = useApp()
  const fileInputRef = useRef(null)

  const handleFile = (file) => {
    if (!file) return
    const previewUrl = URL.createObjectURL(file)
    setVisionImage({
      name: file.name,
      size: file.size,
      url: previewUrl,
      file,
    })
  }

  const handleClear = () => {
    if (visionImage?.url) URL.revokeObjectURL(visionImage.url)
    setVisionImage(null)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{
        background: 'rgba(34, 211, 238, 0.08)',
        borderLeft: '4px solid var(--accent-cyan)',
        padding: '12px 16px',
        borderRadius: '8px',
        fontSize: '0.82rem',
        display: 'flex',
        alignItems: 'center',
        gap: '10px'
      }}>
        <Cpu size={18} style={{ color: 'var(--accent-cyan)' }} />
        <div>
          <b>Multimodal VLM Inspection:</b> Attach an equipment status photo (e.g. PLC LED panel).
          Switch to <b>Query Assistant</b> to inspect alongside retrieved SOPs.
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="section-header">
            <Upload size={16} />
            <span>Upload Photo / Diagnostic Image</span>
          </div>

          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            accept="image/*"
            onChange={(e) => handleFile(e.target.files[0])}
          />

          <div className="upload-zone" onClick={() => fileInputRef.current?.click()}>
            <div className="upload-zone-icon">📷</div>
            <div className="upload-zone-text">Click to browse or drag and drop image here</div>
            <div className="upload-zone-sub">Supported: PNG, JPG, JPEG, WEBP, BMP (Max 20MB)</div>
          </div>

          <div style={{ marginTop: '16px', display: 'flex', gap: '10px' }}>
            <button
              className="btn btn-outline"
              onClick={() => handleFile(new File([''], 'synthetic_plc_leds_normal.png', { type: 'image/png' }))}
            >
              Test: Normal PLC
            </button>
            <button
              className="btn btn-outline"
              onClick={() => handleFile(new File([''], 'synthetic_blurry_panel.png', { type: 'image/png' }))}
            >
              Test: Blurry Panel
            </button>
            <button
              className="btn btn-outline"
              onClick={() => handleFile(new File([''], 'synthetic_ambiguous_model.png', { type: 'image/png' }))}
            >
              Test: Ambiguous Model
            </button>
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div className="section-header" style={{ margin: 0 }}>
              <ImageIcon size={16} />
              <span>Diagnostic Preview</span>
            </div>
            {visionImage && (
              <button
                className="btn btn-outline"
                style={{ color: 'var(--accent-red)' }}
                onClick={handleClear}
              >
                <Trash2 size={13} style={{ marginRight: '4px' }} />
                Remove
              </button>
            )}
          </div>

          {visionImage ? (
            <div>
              <div style={{
                background: '#070d18',
                borderRadius: '8px',
                border: '1px solid var(--border)',
                height: '220px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                overflow: 'hidden',
                marginBottom: '12px'
              }}>
                <img
                  src={visionImage.url}
                  alt={visionImage.name}
                  style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
                />
              </div>

              <div className="insight-row">
                <span className="insight-label">Filename</span>
                <span className="insight-value" style={{ color: 'var(--accent-cyan)' }}>{visionImage.name}</span>
              </div>
              <div className="insight-row">
                <span className="insight-label">File Size</span>
                <span className="insight-value">
                  {visionImage.size ? `${(visionImage.size / 1024).toFixed(1)} KB` : 'Fixture'}
                </span>
              </div>
            </div>
          ) : (
            <div style={{
              height: '240px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)'
            }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '8px' }}>🔍</div>
              <div>No image currently loaded</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

