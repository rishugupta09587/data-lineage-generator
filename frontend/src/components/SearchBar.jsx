/**
 * components/SearchBar.jsx
 * -------------------------
 * Search nodes by name or ID within the loaded DAG.
 */

import React, { useState, useMemo } from 'react'
import { Search, X } from 'lucide-react'

const SearchBar = ({ dagData, onNodeSelect }) => {
  const [query, setQuery] = useState('')
  const [focused, setFocused] = useState(false)

  const results = useMemo(() => {
    if (!query.trim() || !dagData?.nodes) return []
    const q = query.toLowerCase()
    return dagData.nodes
      .filter(n =>
        n.id?.toLowerCase().includes(q) ||
        n.name?.toLowerCase().includes(q) ||
        n.type?.toLowerCase().includes(q) ||
        n.operation?.toLowerCase().includes(q)
      )
      .slice(0, 8)
  }, [query, dagData])

  const handleSelect = (nodeId) => {
    onNodeSelect(nodeId)
    setQuery('')
  }

  return (
    <div className="relative">
      <div className="flex items-center gap-2 bg-surface-700 border border-white/10 rounded-lg px-3 py-2
                      focus-within:border-indigo-500/50 focus-within:ring-2 focus-within:ring-indigo-500/20 transition-all">
        <Search className="w-4 h-4 text-slate-500 flex-shrink-0" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 150)}
          placeholder="Search nodes..."
          className="bg-transparent text-sm text-slate-200 placeholder:text-slate-500
                     focus:outline-none w-full"
        />
        {query && (
          <button onClick={() => setQuery('')} className="text-slate-500 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Dropdown Results */}
      {focused && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-surface-700 border border-white/10
                        rounded-lg overflow-hidden shadow-xl z-50 animate-fade-in">
          {results.map((node) => (
            <button
              key={node.id}
              onClick={() => handleSelect(node.id)}
              className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-surface-600 transition-colors text-left"
            >
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                node.type === 'source' ? 'bg-emerald-500' :
                node.type === 'sink' ? 'bg-rose-500' : 'bg-indigo-500'
              }`} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-200 truncate">{node.name || node.id}</p>
                <p className="text-xs text-slate-500 font-mono truncate">{node.id}</p>
              </div>
              <span className={`text-xs px-1.5 py-0.5 rounded font-medium flex-shrink-0 ${
                node.type === 'source' ? 'bg-emerald-500/20 text-emerald-400' :
                node.type === 'sink' ? 'bg-rose-500/20 text-rose-400' :
                'bg-indigo-500/20 text-indigo-400'
              }`}>{node.type}</span>
            </button>
          ))}
        </div>
      )}

      {focused && query && results.length === 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-surface-700 border border-white/10
                        rounded-lg p-3 text-center text-xs text-slate-500 z-50">
          No nodes match "{query}"
        </div>
      )}
    </div>
  )
}

export default SearchBar
