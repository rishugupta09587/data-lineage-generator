/**
 * components/UploadPanel.jsx
 * --------------------------
 * DAG upload panel with:
 *   - Drag-and-drop JSON file upload
 *   - Manual JSON editor (paste/type)
 *   - Load sample DAGs
 *   - DAG history list
 */

import React, { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileJson, Play, ChevronRight, Trash2, Clock } from 'lucide-react'
import toast from 'react-hot-toast'
import { uploadDAG, uploadDAGFile, deleteDAG } from '../services/api'

// ── Sample DAG Datasets ───────────────────────────────────────────────────
const SAMPLE_DAGS = {
  ecommerce: {
    name: "E-Commerce Order Pipeline",
    description: "Simulates an e-commerce data pipeline from orders to analytics",
    nodes: [
      { id: "raw_orders", name: "Raw Orders", type: "source", description: "Raw order events from Kafka" },
      { id: "raw_customers", name: "Raw Customers", type: "source", description: "Customer master data from CRM" },
      { id: "raw_products", name: "Raw Products", type: "source", description: "Product catalog from inventory system" },
      { id: "clean_orders", name: "Clean Orders", type: "transformation", operation: "filter", description: "Remove invalid/test orders" },
      { id: "clean_customers", name: "Clean Customers", type: "transformation", operation: "deduplicate", description: "Deduplicate customer records" },
      { id: "orders_customers", name: "Orders + Customers", type: "transformation", operation: "join", description: "Join orders with customer data" },
      { id: "orders_products", name: "Enrich with Products", type: "transformation", operation: "join", description: "Enrich with product details" },
      { id: "revenue_agg", name: "Revenue Aggregation", type: "transformation", operation: "aggregation", description: "Aggregate revenue by date/region" },
      { id: "customer_ltv", name: "Customer LTV", type: "transformation", operation: "aggregation", description: "Calculate lifetime value per customer" },
      { id: "orders_mart", name: "Orders Data Mart", type: "sink", description: "Orders dimensional model in Redshift" },
      { id: "revenue_report", name: "Revenue Dashboard", type: "sink", description: "Tableau revenue dashboard" },
      { id: "ltv_model_input", name: "LTV Model Input", type: "sink", description: "Feature store for ML model" },
    ],
    edges: [
      { from: "raw_orders", to: "clean_orders" },
      { from: "raw_customers", to: "clean_customers" },
      { from: "clean_orders", to: "orders_customers" },
      { from: "clean_customers", to: "orders_customers" },
      { from: "orders_customers", to: "orders_products" },
      { from: "raw_products", to: "orders_products" },
      { from: "orders_products", to: "revenue_agg" },
      { from: "orders_products", to: "customer_ltv" },
      { from: "orders_products", to: "orders_mart" },
      { from: "revenue_agg", to: "revenue_report" },
      { from: "customer_ltv", to: "ltv_model_input" },
    ],
  },

  spark_pipeline: {
    name: "Apache Spark ETL Pipeline",
    description: "Simulates a Spark DAG with multiple transformation stages",
    nodes: [
      { id: "hdfs_raw", name: "HDFS Raw Zone", type: "source", description: "Raw files in HDFS landing zone" },
      { id: "s3_events", name: "S3 Event Logs", type: "source", description: "Application event logs from S3" },
      { id: "schema_validate", name: "Schema Validation", type: "transformation", operation: "filter" },
      { id: "parse_events", name: "Parse Events", type: "transformation", operation: "projection" },
      { id: "sessionize", name: "Session Builder", type: "transformation", operation: "aggregation" },
      { id: "feature_eng", name: "Feature Engineering", type: "transformation", operation: "custom" },
      { id: "join_enriched", name: "Enrich Dataset", type: "transformation", operation: "join" },
      { id: "ml_features", name: "ML Feature Store", type: "sink", description: "Features for model training" },
      { id: "silver_layer", name: "Silver Layer", type: "sink", description: "Cleansed data in Delta Lake" },
    ],
    edges: [
      { from: "hdfs_raw", to: "schema_validate" },
      { from: "s3_events", to: "parse_events" },
      { from: "schema_validate", to: "join_enriched" },
      { from: "parse_events", to: "sessionize" },
      { from: "sessionize", to: "feature_eng" },
      { from: "feature_eng", to: "join_enriched" },
      { from: "join_enriched", to: "ml_features" },
      { from: "join_enriched", to: "silver_layer" },
    ],
  },
}

// ─────────────────────────────────────────────────────────────────────────

const UploadPanel = ({ onDAGUploaded, dagHistory, onSelectDAG, onDeleteDAG }) => {
  const [mode, setMode] = useState('upload')  // 'upload' | 'editor' | 'history'
  const [editorValue, setEditorValue] = useState('')
  const [loading, setLoading] = useState(false)

  // ── Drag-and-drop ───────────────────────────────────────────────────
  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0]
    if (!file) return
    setLoading(true)
    try {
      const result = await uploadDAGFile(file)
      toast.success(`DAG "${result.name}" uploaded! ${result.node_count} nodes, ${result.edge_count} edges`)
      onDAGUploaded(result)
    } catch (err) {
      toast.error(`Upload failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [onDAGUploaded])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/json': ['.json'] },
    multiple: false,
  })

  // ── JSON Editor Submit ──────────────────────────────────────────────
  const handleEditorSubmit = async () => {
    if (!editorValue.trim()) return toast.error('Please enter DAG JSON')
    setLoading(true)
    try {
      const parsed = JSON.parse(editorValue)
      const result = await uploadDAG(parsed)
      toast.success(`DAG uploaded successfully! (${result.node_count} nodes)`)
      onDAGUploaded(result)
      setEditorValue('')
    } catch (err) {
      if (err instanceof SyntaxError) {
        toast.error('Invalid JSON syntax')
      } else {
        toast.error(err.message)
      }
    } finally {
      setLoading(false)
    }
  }

  // ── Load Sample DAG ─────────────────────────────────────────────────
  const loadSample = async (key) => {
    setLoading(true)
    try {
      const result = await uploadDAG(SAMPLE_DAGS[key])
      toast.success(`Sample "${SAMPLE_DAGS[key].name}" loaded!`)
      onDAGUploaded(result)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Tab Bar */}
      <div className="flex border-b border-white/5 mb-4">
        {[
          { key: 'upload', label: 'Upload' },
          { key: 'editor', label: 'JSON Editor' },
          { key: 'history', label: `History (${dagHistory?.length || 0})` },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setMode(tab.key)}
            className={`px-3 py-2 text-xs font-medium border-b-2 transition-all mr-1
              ${mode === tab.key
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-500 hover:text-slate-300'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Upload Tab */}
      {mode === 'upload' && (
        <div className="flex flex-col gap-4 flex-1">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all
              ${isDragActive
                ? 'border-indigo-500 bg-indigo-500/10'
                : 'border-white/10 hover:border-white/20 hover:bg-white/2'}`}
          >
            <input {...getInputProps()} />
            <Upload className="w-8 h-8 mx-auto mb-2 text-slate-500" />
            {isDragActive
              ? <p className="text-indigo-400 text-sm">Drop your DAG JSON here...</p>
              : <div>
                  <p className="text-slate-300 text-sm font-medium mb-1">Drop DAG JSON file</p>
                  <p className="text-slate-500 text-xs">or click to browse</p>
                </div>
            }
          </div>

          <div>
            <p className="section-title">Sample Pipelines</p>
            <div className="flex flex-col gap-2">
              {Object.entries(SAMPLE_DAGS).map(([key, dag]) => (
                <button
                  key={key}
                  onClick={() => loadSample(key)}
                  disabled={loading}
                  className="flex items-center justify-between p-3 bg-surface-700 hover:bg-surface-600
                             border border-white/5 hover:border-white/10 rounded-lg
                             transition-all text-left group disabled:opacity-50"
                >
                  <div>
                    <p className="text-slate-200 text-sm font-medium">{dag.name}</p>
                    <p className="text-slate-500 text-xs mt-0.5">{dag.nodes.length} nodes · {dag.edges.length} edges</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-indigo-400 transition-colors" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* JSON Editor Tab */}
      {mode === 'editor' && (
        <div className="flex flex-col gap-3 flex-1">
          <p className="text-slate-500 text-xs">
            Paste your DAG JSON directly. Must include <code className="text-indigo-400">nodes</code> and <code className="text-indigo-400">edges</code> arrays.
          </p>
          <textarea
            value={editorValue}
            onChange={(e) => setEditorValue(e.target.value)}
            placeholder={`{\n  "name": "My Pipeline",\n  "nodes": [\n    {"id": "A", "type": "source"},\n    {"id": "B", "type": "transformation"},\n    {"id": "C", "type": "sink"}\n  ],\n  "edges": [\n    {"from": "A", "to": "B"},\n    {"from": "B", "to": "C"}\n  ]\n}`}
            className="flex-1 input-dark font-mono text-xs resize-none min-h-[280px]"
            spellCheck={false}
          />
          <button
            onClick={handleEditorSubmit}
            disabled={loading || !editorValue.trim()}
            className="btn-primary justify-center"
          >
            <Play className="w-4 h-4" />
            {loading ? 'Uploading...' : 'Upload DAG'}
          </button>
        </div>
      )}

      {/* History Tab */}
      {mode === 'history' && (
        <div className="flex flex-col gap-2 flex-1 overflow-y-auto">
          {dagHistory?.length === 0 && (
            <div className="text-center py-8 text-slate-500 text-sm">
              No DAGs uploaded yet
            </div>
          )}
          {dagHistory?.map((dag) => (
            <div
              key={dag.dag_id}
              className="flex items-center justify-between p-3 bg-surface-700 border border-white/5
                         rounded-lg hover:border-white/10 transition-all group"
            >
              <button
                onClick={() => onSelectDAG(dag.dag_id)}
                className="flex-1 text-left"
              >
                <p className="text-slate-200 text-sm font-medium truncate">{dag.name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <Clock className="w-3 h-3 text-slate-500" />
                  <span className="text-slate-500 text-xs">
                    {dag.node_count}n · {dag.edge_count}e · v{dag.version}
                  </span>
                </div>
              </button>
              <button
                onClick={() => onDeleteDAG(dag.dag_id)}
                className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/20
                           rounded text-slate-500 hover:text-red-400 transition-all"
                title="Delete DAG"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default UploadPanel
