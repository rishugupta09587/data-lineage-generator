/**
 * services/api.js
 * ---------------
 * Centralized API client for all backend calls.
 * Uses axios with base URL configuration.
 */

import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,  // 30s timeout for large DAG processing
})

// ── Request Interceptor (logging) ─────────────────────────────────────────
api.interceptors.request.use((config) => {
  console.debug(`[API] ${config.method?.toUpperCase()} ${config.url}`)
  return config
})

// ── Response Interceptor (error normalization) ────────────────────────────
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail
      || error.response?.data?.message
      || error.message
      || 'Unknown API error'
    console.error('[API Error]', message)
    return Promise.reject(new Error(
      typeof message === 'object' ? JSON.stringify(message) : message
    ))
  }
)

// ── DAG Management ────────────────────────────────────────────────────────

/** Upload a DAG JSON object */
export const uploadDAG = (dagData) =>
  api.post('/upload-dag', dagData)

/** Upload a DAG from a File object */
export const uploadDAGFile = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload-dag/file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/** List all stored DAGs */
export const listDAGs = () => api.get('/dags')

/** Get full details + stats for a DAG */
export const getDAG = (dagId) => api.get(`/dags/${dagId}`)

/** Delete a DAG */
export const deleteDAG = (dagId) => api.delete(`/dags/${dagId}`)

// ── Lineage Analysis ──────────────────────────────────────────────────────

/** Upstream lineage: all ancestors of a node */
export const getUpstream = (dagId, nodeId) =>
  api.get(`/upstream/${dagId}/${encodeURIComponent(nodeId)}`)

/** Downstream lineage: all descendants of a node */
export const getDownstream = (dagId, nodeId) =>
  api.get(`/downstream/${dagId}/${encodeURIComponent(nodeId)}`)

/** Full lineage: ancestors + descendants */
export const getFullLineage = (dagId, nodeId) =>
  api.get(`/full-lineage/${dagId}/${encodeURIComponent(nodeId)}`)

/** Impact analysis: blast radius if this node fails */
export const getImpactAnalysis = (dagId, nodeId) =>
  api.get(`/impact-analysis/${dagId}/${encodeURIComponent(nodeId)}`)

/** Graph-level statistics for a DAG */
export const getGraphStats = (dagId) =>
  api.get(`/graph-stats/${dagId}`)

// ── Export ────────────────────────────────────────────────────────────────

/**
 * Get the download URL for a lineage export.
 * We use window.open() directly for file downloads rather than axios.
 */
export const getExportUrl = (dagId, nodeId, format = 'json', lineageType = 'full') =>
  `${BASE_URL}/export/${dagId}/${encodeURIComponent(nodeId)}?format=${format}&lineage_type=${lineageType}`

export default api
