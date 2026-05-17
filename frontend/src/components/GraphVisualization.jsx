/**
 * components/GraphVisualization.jsx
 * -----------------------------------
 * Interactive graph canvas using Cytoscape.js with dagre layout.
 *
 * Features:
 *   - DAG rendered with top-to-bottom hierarchical layout
 *   - Node color coding by type (source/transformation/sink)
 *   - Click node → highlights upstream (blue), downstream (green), selected (red)
 *   - Zoom + pan
 *   - Fit-to-screen button
 *   - Hover tooltips
 *   - Animated edge drawing
 */

import React, { useEffect, useRef, useCallback } from 'react'
import cytoscape from 'cytoscape'
import dagre from 'cytoscape-dagre'

// Register the dagre layout plugin once
cytoscape.use(dagre)

// ── Node color palette ────────────────────────────────────────────────────
const NODE_COLORS = {
  source:         { bg: '#10b981', border: '#059669', text: '#ffffff' },
  transformation: { bg: '#6366f1', border: '#4f46e5', text: '#ffffff' },
  sink:           { bg: '#f43f5e', border: '#e11d48', text: '#ffffff' },
  default:        { bg: '#64748b', border: '#475569', text: '#ffffff' },
}

// Highlight colors for lineage visualization
const HIGHLIGHT = {
  selected:   '#f43f5e',   // red — the clicked node
  upstream:   '#3b82f6',   // blue — ancestors
  downstream: '#10b981',   // green — descendants
  impact:     '#f59e0b',   // amber — affected nodes
  dim:        '#1e293b',   // dark gray — dimmed nodes
}

const GraphVisualization = ({
  dagData,          // { nodes: [...], edges: [...] }
  selectedNode,     // currently selected node id
  highlightData,    // { type, nodes: Set, edges: Set } from lineage result
  onNodeClick,      // (nodeId) => void
  className = '',
}) => {
  const containerRef = useRef(null)
  const cyRef = useRef(null)

  // ── Build Cytoscape elements from DAG data ──────────────────────────
  const buildElements = useCallback((data) => {
    if (!data?.nodes) return []

    const elements = []

    // Nodes
    data.nodes.forEach((node) => {
      const colors = NODE_COLORS[node.type] || NODE_COLORS.default
      elements.push({
        group: 'nodes',
        data: {
          id: node.id,
          label: node.name || node.id,
          type: node.type || 'default',
          operation: node.operation || '',
          description: node.description || '',
          bgColor: colors.bg,
          borderColor: colors.border,
          textColor: colors.text,
        },
      })
    })

    // Edges
    ;(data.edges || []).forEach((edge, idx) => {
      const fromNode = edge.from || edge.from_node
      const toNode = edge.to || edge.to_node
      if (fromNode && toNode) {
        elements.push({
          group: 'edges',
          data: {
            id: `e-${fromNode}-${toNode}-${idx}`,
            source: fromNode,
            target: toNode,
            relationship: edge.relationship_type || '',
          },
        })
      }
    })

    return elements
  }, [])

  // ── Initialize Cytoscape ────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || !dagData?.nodes?.length) return

    // Destroy previous instance
    if (cyRef.current) {
      cyRef.current.destroy()
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: buildElements(dagData),

      // ── Visual Styles ─────────────────────────────────────────────
      style: [
        // Default node style
        {
          selector: 'node',
          style: {
            'background-color': 'data(bgColor)',
            'border-color': 'data(borderColor)',
            'border-width': 2,
            'color': '#ffffff',
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-family': 'IBM Plex Sans, system-ui, sans-serif',
            'font-size': '11px',
            'font-weight': '500',
            'width': 'label',
            'height': '36px',
            'padding': '12px',
            'shape': 'round-rectangle',
            'text-max-width': '120px',
            'text-wrap': 'wrap',
            'text-overflow-wrap': 'anywhere',
            'transition-property': 'background-color border-color border-width opacity',
            'transition-duration': '0.25s',
          },
        },

        // Source node: hexagonal shape
        {
          selector: 'node[type="source"]',
          style: {
            shape: 'hexagon',
            'background-color': NODE_COLORS.source.bg,
            'border-color': NODE_COLORS.source.border,
          },
        },

        // Transformation node: diamond shape
        {
          selector: 'node[type="transformation"]',
          style: {
            shape: 'round-rectangle',
            'background-color': NODE_COLORS.transformation.bg,
            'border-color': NODE_COLORS.transformation.border,
          },
        },

        // Sink node: octagon shape
        {
          selector: 'node[type="sink"]',
          style: {
            shape: 'octagon',
            'background-color': NODE_COLORS.sink.bg,
            'border-color': NODE_COLORS.sink.border,
          },
        },

        // Default edge style
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#334155',
            'target-arrow-color': '#334155',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 1.2,
            'transition-property': 'line-color target-arrow-color width opacity',
            'transition-duration': '0.25s',
          },
        },

        // ── Highlight classes ─────────────────────────────────────

        // Selected node
        {
          selector: '.node-selected',
          style: {
            'background-color': HIGHLIGHT.selected,
            'border-color': '#ffffff',
            'border-width': 3,
            'z-index': 999,
            'box-shadow': '0 0 20px rgba(244, 63, 94, 0.8)',
          },
        },

        // Upstream ancestor nodes (blue)
        {
          selector: '.node-upstream',
          style: {
            'background-color': HIGHLIGHT.upstream,
            'border-color': '#60a5fa',
            'border-width': 2.5,
          },
        },

        // Downstream descendant nodes (green)
        {
          selector: '.node-downstream',
          style: {
            'background-color': HIGHLIGHT.downstream,
            'border-color': '#34d399',
            'border-width': 2.5,
          },
        },

        // Impact analysis nodes (amber)
        {
          selector: '.node-impact',
          style: {
            'background-color': HIGHLIGHT.impact,
            'border-color': '#fbbf24',
            'border-width': 2.5,
          },
        },

        // Dimmed nodes
        {
          selector: '.node-dimmed',
          style: {
            'background-color': '#1e293b',
            'border-color': '#334155',
            'color': '#475569',
            'opacity': 0.4,
          },
        },

        // Highlighted edge
        {
          selector: '.edge-highlighted',
          style: {
            'line-color': '#6366f1',
            'target-arrow-color': '#6366f1',
            'width': 3,
          },
        },

        // Dimmed edge
        {
          selector: '.edge-dimmed',
          style: {
            'opacity': 0.15,
          },
        },

        // Hover state
        {
          selector: 'node:active',
          style: { 'overlay-opacity': 0.1 },
        },
      ],

      // ── Layout ──────────────────────────────────────────────────
      layout: {
        name: 'dagre',
        rankDir: 'TB',         // Top → Bottom
        nodeSep: 60,
        rankSep: 80,
        edgeSep: 20,
        fit: true,
        padding: 40,
        animate: true,
        animationDuration: 500,
      },

      // ── Interaction Options ──────────────────────────────────────
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      autoungrabify: false,
      minZoom: 0.1,
      maxZoom: 4,
    })

    // ── Node Click Handler ────────────────────────────────────────
    cy.on('tap', 'node', (evt) => {
      const nodeId = evt.target.id()
      onNodeClick && onNodeClick(nodeId)
    })

    // ── Background Click → Deselect ───────────────────────────────
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        onNodeClick && onNodeClick(null)
        cy.elements().removeClass(
          'node-selected node-upstream node-downstream node-impact node-dimmed edge-highlighted edge-dimmed'
        )
      }
    })

    // ── Hover Tooltip ─────────────────────────────────────────────
    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target
      node.style('cursor', 'pointer')
    })

    cyRef.current = cy
    return () => { cy.destroy() }
  }, [dagData, buildElements])

  // ── Apply Highlight Classes ─────────────────────────────────────────
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    // Reset all classes
    cy.elements().removeClass(
      'node-selected node-upstream node-downstream node-impact node-dimmed edge-highlighted edge-dimmed'
    )

    if (!selectedNode && !highlightData) return

    if (selectedNode) {
      // Dim all nodes first
      cy.nodes().addClass('node-dimmed')
      cy.edges().addClass('edge-dimmed')

      // Highlight based on lineage type
      if (highlightData) {
        const { type, nodes: highlightNodes } = highlightData

        highlightNodes?.forEach((nodeId) => {
          const node = cy.$(`#${CSS.escape(nodeId)}`)
          if (nodeId === selectedNode) {
            node.removeClass('node-dimmed').addClass('node-selected')
          } else if (type === 'upstream' || type === 'full') {
            node.removeClass('node-dimmed').addClass('node-upstream')
          } else if (type === 'downstream') {
            node.removeClass('node-dimmed').addClass('node-downstream')
          } else if (type === 'impact') {
            node.removeClass('node-dimmed').addClass('node-impact')
          }
        })

        // For full lineage, upstream = blue, downstream = green
        if (type === 'full' && highlightData.upstream && highlightData.downstream) {
          highlightData.upstream.forEach((nodeId) => {
            if (nodeId !== selectedNode) {
              cy.$(`#${CSS.escape(nodeId)}`).removeClass('node-dimmed').addClass('node-upstream')
            }
          })
          highlightData.downstream.forEach((nodeId) => {
            if (nodeId !== selectedNode) {
              cy.$(`#${CSS.escape(nodeId)}`).removeClass('node-dimmed').addClass('node-downstream')
            }
          })
        }

        // Highlight related edges
        cy.edges().forEach((edge) => {
          const src = edge.source().id()
          const tgt = edge.target().id()
          if (highlightNodes?.has(src) && highlightNodes?.has(tgt)) {
            edge.removeClass('edge-dimmed').addClass('edge-highlighted')
          }
        })
      }

      // Always highlight the selected node
      const selectedEl = cy.$(`#${CSS.escape(selectedNode)}`)
      selectedEl.removeClass('node-dimmed node-upstream node-downstream').addClass('node-selected')

      // Pan to selected node
      cy.animate({
        center: { eles: selectedEl },
        zoom: Math.max(cy.zoom(), 1.2),
        duration: 400,
        easing: 'ease-in-out-cubic',
      })
    }
  }, [selectedNode, highlightData])

  // ── Expose fit-to-screen function via a simple DOM event ───────────────
  const fitGraph = () => {
    cyRef.current?.fit(undefined, 40)
  }

  const resetZoom = () => {
    cyRef.current?.reset()
  }

  return (
    <div className={`relative ${className}`}>
      {/* Graph Canvas */}
      <div
        ref={containerRef}
        className="w-full h-full bg-surface-900 rounded-xl"
        style={{ minHeight: '500px' }}
      />

      {/* Zoom Controls */}
      <div className="absolute top-3 right-3 flex flex-col gap-1.5">
        <button
          onClick={fitGraph}
          className="w-8 h-8 flex items-center justify-center bg-surface-700 hover:bg-surface-600
                     border border-white/10 rounded-lg text-slate-300 hover:text-white
                     text-xs font-mono transition-all"
          title="Fit to screen"
        >⊡</button>
        <button
          onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.3)}
          className="w-8 h-8 flex items-center justify-center bg-surface-700 hover:bg-surface-600
                     border border-white/10 rounded-lg text-slate-300 hover:text-white
                     text-sm transition-all"
          title="Zoom in"
        >+</button>
        <button
          onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.7)}
          className="w-8 h-8 flex items-center justify-center bg-surface-700 hover:bg-surface-600
                     border border-white/10 rounded-lg text-slate-300 hover:text-white
                     text-sm transition-all"
          title="Zoom out"
        >−</button>
        <button
          onClick={resetZoom}
          className="w-8 h-8 flex items-center justify-center bg-surface-700 hover:bg-surface-600
                     border border-white/10 rounded-lg text-slate-300 hover:text-white
                     text-xs transition-all"
          title="Reset view"
        >↺</button>
      </div>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 flex items-center gap-3 bg-surface-800/90
                      backdrop-blur border border-white/5 rounded-lg px-3 py-2">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm bg-emerald-500" />
          <span className="text-slate-400 text-xs">Source</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm bg-indigo-500" />
          <span className="text-slate-400 text-xs">Transform</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm bg-rose-500" />
          <span className="text-slate-400 text-xs">Sink</span>
        </div>
        <div className="w-px h-4 bg-white/10" />
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm bg-blue-500" />
          <span className="text-slate-400 text-xs">Upstream</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm bg-green-500" />
          <span className="text-slate-400 text-xs">Downstream</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm bg-red-500" />
          <span className="text-slate-400 text-xs">Selected</span>
        </div>
      </div>

      {/* Empty state */}
      {!dagData?.nodes?.length && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <div className="text-4xl mb-3 opacity-30">⬡</div>
            <p className="text-slate-500 text-sm">Upload a DAG to visualize the pipeline</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default GraphVisualization
