import React, { useRef, useEffect, useState } from 'react'
import * as d3 from 'd3'
import NetworkEditModal from '../NetworkEditModal/NetworkEditModal'
import './TopologyGraph.css'

const NODE_COLORS = {
  network: '#3b82f6',
  base_station: '#06b6d4',
  talkgroup: '#d946ef',
  radio: '#f59e0b',
}

const NODE_SIZES = { network: 28, base_station: 22, talkgroup: 16, radio: 10 }
const NODE_ICONS = { network: '🌐', base_station: '📡', talkgroup: '👥', radio: '📻' }

function TopologyGraph() {
  const svgRef = useRef(null)
  const [topology, setTopology] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [editNetwork, setEditNetwork] = useState(null)

  useEffect(() => {
    fetch('/api/topology')
      .then(r => r.json())
      .then(data => { setTopology(data); setLoading(false); })
      .catch(err => { console.error(err); setLoading(false); })
  }, [])

  useEffect(() => {
    if (!topology || !svgRef.current) return
    if (topology.nodes.length === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const width = svgRef.current.clientWidth
    const height = svgRef.current.clientHeight

    const g = svg.append('g')

    // Zoom
    const zoom = d3.zoom().scaleExtent([0.2, 4]).on('zoom', (event) => {
      g.attr('transform', event.transform)
    })
    svg.call(zoom)

    // Force simulation
    const simulation = d3.forceSimulation(topology.nodes)
      .force('link', d3.forceLink(topology.edges).id(d => d.id).distance(d => {
        return d.type === 'network_to_bs' ? 150 : d.type === 'bs_to_tg' ? 100 : 60
      }))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => NODE_SIZES[d.type] + 5))

    // Links
    const link = g.append('g').selectAll('line')
      .data(topology.edges)
      .join('line')
      .attr('class', 'topo-link')
      .attr('stroke-width', d => Math.min(Math.max(d.weight || 1, 1), 6))

    // Nodes
    const node = g.append('g').selectAll('g')
      .data(topology.nodes)
      .join('g')
      .attr('class', d => `topo-node topo-${d.type}`)
      .call(d3.drag()
        .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
        .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
      )
      .on('click', (e, d) => setSelected(d))

    node.append('circle')
      .attr('r', d => NODE_SIZES[d.type])
      .attr('fill', d => NODE_COLORS[d.type])
      .attr('fill-opacity', 0.2)
      .attr('stroke', d => NODE_COLORS[d.type])
      .attr('stroke-width', 2)

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', d => NODE_SIZES[d.type] * 0.7)
      .text(d => NODE_ICONS[d.type])

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => NODE_SIZES[d.type] + 14)
      .attr('class', 'node-label')
      .text(d => d.label?.slice(0, 16) || '')

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    return () => simulation.stop()
  }, [topology])

  if (loading) {
    return <div className="topo-loading"><div className="spinner"></div><p>Loading topology...</p></div>
  }

  return (
    <div className="topo-container">
      <div className="topo-header">
        <h2>🔗 Network Topology</h2>
        <div className="topo-legend">
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <span key={type} className="legend-item">
              <span className="legend-dot" style={{ background: color }}></span>
              {type.replace('_', ' ')}
            </span>
          ))}
        </div>
      </div>
      <div className="topo-graph glass">
        <svg ref={svgRef} width="100%" height="100%"></svg>
      </div>
      {selected && (
        <div className="topo-detail glass animate-slide-in">
          <h3>{NODE_ICONS[selected.type]} {selected.label}</h3>
          <p className="detail-type">{selected.type.replace('_', ' ').toUpperCase()}</p>
          {selected.protocol && <p>Protocol: <strong>{selected.protocol}</strong></p>}
          {selected.radio_id && <p>Radio ID: <strong>{selected.radio_id}</strong></p>}
          {selected.tg_number && <p>TG Number: <strong>{selected.tg_number}</strong></p>}
          {selected.encryption && <p>Encryption: <strong>{selected.encryption}</strong></p>}
          {selected.type === 'network' && (
            <button className="detail-edit-btn" onClick={() => {
              fetch(`/api/networks/${selected.id}`).then(r=>r.json()).then(d=>setEditNetwork(d.network)).catch(()=>{})
            }}>✏️ Edit Network</button>
          )}
          <button onClick={() => setSelected(null)} className="detail-close">✕</button>
        </div>
      )}
      {editNetwork && (
        <NetworkEditModal
          network={editNetwork}
          onClose={() => setEditNetwork(null)}
          onSave={() => { setEditNetwork(null); fetch('/api/topology').then(r=>r.json()).then(setTopology).catch(()=>{}) }}
        />
      )}
    </div>
  )
}

export default TopologyGraph
