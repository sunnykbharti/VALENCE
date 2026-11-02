/**
 * Backend API Client connecting React Frontend directly to the Python VALENCE Server.
 */

const API_BASE = '/api'

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (err) {
    console.warn('Backend health check failed:', err)
    return null
  }
}

export async function fetchIndexedDocuments() {
  try {
    const res = await fetch(`${API_BASE}/documents`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    return data
  } catch (err) {
    console.error('Failed to fetch documents:', err)
    return { documents: {}, chunks: {} }
  }
}

export async function askQuestion(question, equipmentModel = null) {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, equipment_model: equipmentModel }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return await res.json()
}

export async function askQuestionWithImage(question, imageName, equipmentModel = null) {
  const res = await fetch(`${API_BASE}/query_image`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      image_name: imageName,
      equipment_model: equipmentModel,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return await res.json()
}

export async function indexDocumentFile(file, equipmentModel = null, synthetic = false) {
  const query = new URLSearchParams({
    filename: file.name,
    synthetic: String(synthetic),
  })
  if (equipmentModel) query.append('equipment_model', equipmentModel)

  const arrayBuffer = await file.arrayBuffer()
  const res = await fetch(`${API_BASE}/index_pdf?${query.toString()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/pdf' },
    body: arrayBuffer,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return await res.json()
}

export async function removeDocument(filename) {
  const res = await fetch(`${API_BASE}/remove_document`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return await res.json()
}

export async function removeChunk(chunkId, filename = null) {
  const res = await fetch(`${API_BASE}/remove_chunk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chunk_id: chunkId, filename }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return await res.json()
}

export async function resetBackendSession() {
  const res = await fetch(`${API_BASE}/reset`, { method: 'POST' })
  return await res.json()
}
