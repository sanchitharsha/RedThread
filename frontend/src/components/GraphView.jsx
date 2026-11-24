import React, { useRef, useEffect, useState, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Share2, ZoomIn, ZoomOut, Maximize2, Info } from 'lucide-react';
import { NODE_COLORS, TIER_CONFIG } from '../constants/reasons';

export default function GraphView({
  graphData = { nodes: [], links: [] },
  onSelectNode,
  onSelectLink,
  selectedElement
}) {
  const fgRef = useRef();
  const containerRef = useRef();
  const [dimensions, setDimensions] = useState({ width: 600, height: 400 });

  // Resize listener
  useEffect(() => {
    const updateDims = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth || 600,
          height: containerRef.current.clientHeight || 400
        });
      }
    };
    updateDims();
    window.addEventListener('resize', updateDims);
    return () => window.removeEventListener('resize', updateDims);
  }, []);

  // Format and dedupe nodes and links for ForceGraph
  const formattedData = useMemo(() => {
    const nodeMap = new Map();
    (graphData.nodes || []).forEach(n => {
      nodeMap.set(n.id, {
        ...n,
        color: NODE_COLORS[n.type] || '#64748b',
        val: n.type === 'Recall' ? 14 : n.type === 'Listing' ? 10 : 6
      });
    });

    const links = (graphData.links || [])
      .filter(l => nodeMap.has(typeof l.source === 'object' ? l.source.id : l.source) &&
                   nodeMap.has(typeof l.target === 'object' ? l.target.id : l.target))
      .map(l => {
        let linkColor = '#475569';
        if (l.type === 'MATCHES' && l.tier) {
          linkColor = TIER_CONFIG[l.tier]?.color || '#ef4444';
        }
        return {
          ...l,
          color: linkColor,
          width: l.type === 'MATCHES' ? 2.5 : 1.2
        };
      });

    return {
      nodes: Array.from(nodeMap.values()),
      links
    };
  }, [graphData]);

  const handleZoomIn = () => {
    if (fgRef.current) fgRef.current.zoom(fgRef.current.zoom() * 1.3, 400);
  };

  const handleZoomOut = () => {
    if (fgRef.current) fgRef.current.zoom(fgRef.current.zoom() * 0.7, 400);
  };

  const handleFit = () => {
    if (fgRef.current) fgRef.current.zoomToFit(400, 30);
  };

  return (
    <div className="card flex flex-col h-full overflow-hidden border-slate-800" ref={containerRef}>
      {/* Header */}
      <div className="px-3.5 py-2.5 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between z-10">
        <div className="flex items-center gap-2">
          <Share2 size={15} className="text-cyan-400" />
          <span className="text-xs font-semibold uppercase tracking-wider font-mono text-slate-200">
            Interactive Evidence Graph
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-400">
            {formattedData.nodes.length} nodes • {formattedData.links.length} edges
          </span>
          {/* Controls */}
          <div className="flex items-center gap-1 bg-slate-950 p-0.5 rounded border border-slate-800">
            <button
              type="button"
              onClick={handleZoomIn}
              className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white"
              title="Zoom In"
            >
              <ZoomIn size={12} />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white"
              title="Zoom Out"
            >
              <ZoomOut size={12} />
            </button>
            <button
              type="button"
              onClick={handleFit}
              className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white"
              title="Fit View"
            >
              <Maximize2 size={12} />
            </button>
          </div>
        </div>
      </div>

      {/* Force Graph Canvas */}
      <div className="flex-1 bg-slate-950 relative overflow-hidden">
        {formattedData.nodes.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-600 p-6 font-mono text-xs">
            <Share2 size={32} className="mb-2 opacity-40 text-slate-500" />
            <p>Evidence graph will render as deltas stream from the orchestrator.</p>
          </div>
        ) : (
          <ForceGraph2D
            ref={fgRef}
            width={dimensions.width}
            height={dimensions.height}
            graphData={formattedData}
            nodeLabel={node => `${node.type}: ${node.label || node.id}`}
            nodeColor={node => node.color}
            nodeVal={node => node.val}
            linkColor={link => link.color}
            linkWidth={link => link.width}
            linkDirectionalParticles={link => (link.type === 'MATCHES' ? 3 : 1)}
            linkDirectionalParticleSpeed={0.006}
            linkDirectionalParticleWidth={2}
            onNodeClick={node => onSelectNode && onSelectNode(node)}
            onLinkClick={link => onSelectLink && onSelectLink(link)}
            cooldownTicks={100}
            backgroundColor="#090d16"
            nodeCanvasObject={(node, ctx, globalScale) => {
              const label = node.label || node.id;
              const fontSize = 11 / globalScale;
              ctx.font = `${fontSize}px JetBrains Mono, monospace`;

              // Draw circle
              ctx.beginPath();
              ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI, false);
              ctx.fillStyle = node.color;
              ctx.fill();

              // Highlight if selected
              if (selectedElement && selectedElement.id === node.id) {
                ctx.lineWidth = 3 / globalScale;
                ctx.strokeStyle = '#f8fafc';
                ctx.stroke();
              }

              // Text label
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = '#f1f5f9';
              ctx.fillText(label, node.x, node.y + node.val + fontSize + 2);
            }}
          />
        )}

        {/* Legend */}
        <div className="absolute bottom-2 left-2 p-2 rounded bg-slate-950/90 border border-slate-800 text-[10px] font-mono flex flex-wrap gap-x-3 gap-y-1 backdrop-blur max-w-sm pointer-events-none">
          {Object.entries(NODE_COLORS).map(([type, col]) => (
            <div key={type} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: col }} />
              <span className="text-slate-400">{type}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
