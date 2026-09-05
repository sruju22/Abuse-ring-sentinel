import React, { useRef, useEffect, useState } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Info, Shield, Smartphone, Globe, Target } from 'lucide-react';

export default function NetworkGraph({
  nodes = [],
  links = [],
  onSelectNode,
  selectedNodeId,
  height = 560,
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState(null);
  const [nodePositions, setNodePositions] = useState({});

  // Compute initial layout on node/link changes
  useEffect(() => {
    if (!nodes.length) return;

    const width = containerRef.current?.clientWidth || 800;
    const h = height;
    const centerX = width / 2;
    const centerY = h / 2;

    const positions = {};
    const accounts = nodes.filter((n) => n.type === 'account');
    const entities = nodes.filter((n) => n.type !== 'account');

    // Circular multi-tier layout: Entities in inner ring, accounts in outer ring
    const entityRadius = Math.min(width, h) * 0.22;
    entities.forEach((node, idx) => {
      const angle = (idx / Math.max(1, entities.length)) * 2 * Math.PI;
      positions[node.id] = {
        x: centerX + Math.cos(angle) * entityRadius,
        y: centerY + Math.sin(angle) * entityRadius,
        vx: 0,
        vy: 0,
      };
    });

    const accountRadius = Math.min(width, h) * 0.40;
    accounts.forEach((node, idx) => {
      const angle = (idx / Math.max(1, accounts.length)) * 2 * Math.PI;
      // Add slight jitter for visual organic structure
      const jitter = ((idx % 3) - 1) * 15;
      positions[node.id] = {
        x: centerX + Math.cos(angle) * (accountRadius + jitter),
        y: centerY + Math.sin(angle) * (accountRadius + jitter),
        vx: 0,
        vy: 0,
      };
    });

    setNodePositions(positions);
    setTransform({ x: 0, y: 0, k: 1 });
  }, [nodes, links, height]);

  // Canvas render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = containerRef.current?.clientWidth || 800;
    canvas.width = width * window.devicePixelRatio;
    canvas.height = height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    // Clear background
    ctx.fillStyle = '#090D16';
    ctx.fillRect(0, 0, width, height);

    ctx.save();
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.k, transform.k);

    // Compute neighbors for selected node highlighting
    const neighborIds = new Set();
    const activeId = selectedNodeId || hoveredNode?.id;
    if (activeId) {
      neighborIds.add(activeId);
      links.forEach((link) => {
        const srcId = typeof link.source === 'object' ? link.source.id : link.source;
        const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
        if (srcId === activeId) neighborIds.add(tgtId);
        if (tgtId === activeId) neighborIds.add(srcId);
      });
    }

    // Draw Links
    links.forEach((link) => {
      const srcId = typeof link.source === 'object' ? link.source.id : link.source;
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
      const src = nodePositions[srcId];
      const tgt = nodePositions[tgtId];

      if (src && tgt) {
        const isConnectedToActive = activeId ? (srcId === activeId || tgtId === activeId) : true;
        const isDimmed = activeId && !isConnectedToActive;

        ctx.beginPath();
        ctx.moveTo(src.x, src.y);
        ctx.lineTo(tgt.x, tgt.y);

        if (link.type === 'transfers_to' || link.type === 'shared_destination') {
          ctx.setLineDash([5, 4]); // Distinguishable dashed line for destination transfer
          ctx.strokeStyle = isDimmed ? 'rgba(245, 158, 11, 0.08)' : isConnectedToActive && activeId ? '#F59E0B' : 'rgba(245, 158, 11, 0.55)';
          ctx.lineWidth = isConnectedToActive && activeId ? 2.5 : 1.5;
        } else if (link.type === 'shared_device') {
          ctx.setLineDash([]); // Solid
          ctx.strokeStyle = isDimmed ? 'rgba(129, 140, 248, 0.08)' : isConnectedToActive && activeId ? '#818CF8' : 'rgba(129, 140, 248, 0.45)';
          ctx.lineWidth = isConnectedToActive && activeId ? 2.5 : 1.5;
        } else if (link.type === 'shared_ip') {
          ctx.setLineDash([]); // Solid
          ctx.strokeStyle = isDimmed ? 'rgba(56, 189, 248, 0.08)' : isConnectedToActive && activeId ? '#38BDF8' : 'rgba(56, 189, 248, 0.45)';
          ctx.lineWidth = isConnectedToActive && activeId ? 2.5 : 1.5;
        } else {
          ctx.setLineDash([]);
          ctx.strokeStyle = isDimmed ? 'rgba(148, 163, 184, 0.05)' : 'rgba(148, 163, 184, 0.25)';
          ctx.lineWidth = 1.0;
        }
        ctx.stroke();
        ctx.setLineDash([]); // Reset
      }
    });

    // Draw Nodes
    nodes.forEach((node) => {
      const pos = nodePositions[node.id];
      if (!pos) return;

      const isSelected = selectedNodeId === node.id;
      const isHovered = hoveredNode?.id === node.id;
      const isNeighbor = activeId ? neighborIds.has(node.id) : true;
      const radius = node.type === 'account' ? 9 : 7;

      ctx.save();
      if (activeId && !isNeighbor) {
        ctx.globalAlpha = 0.2; // Dim unrelated entities
      }

      // Glow halo for selected / high risk
      if (isSelected || (node.risk_score && node.risk_score >= 60)) {
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius + 5, 0, 2 * Math.PI);
        ctx.fillStyle = isSelected
          ? 'rgba(56, 189, 248, 0.4)'
          : node.risk_score >= 80
          ? 'rgba(239, 68, 68, 0.35)'
          : 'rgba(249, 115, 22, 0.25)';
        ctx.fill();
      }

      // Node base circle
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, radius, 0, 2 * Math.PI);

      if (node.type === 'account') {
        const score = node.risk_score || 0;
        if (score >= 80) ctx.fillStyle = '#EF4444'; // Critical
        else if (score >= 60) ctx.fillStyle = '#F97316'; // High
        else if (score >= 30) ctx.fillStyle = '#F59E0B'; // Medium
        else ctx.fillStyle = '#10B981'; // Low
      } else if (node.type === 'device') {
        ctx.fillStyle = '#818CF8'; // Indigo
      } else if (node.type === 'ip') {
        ctx.fillStyle = '#38BDF8'; // Cyan
      } else if (node.type === 'destination') {
        ctx.fillStyle = '#FBBF24'; // Amber
      } else {
        ctx.fillStyle = '#94A3B8';
      }
      ctx.fill();

      // Node border
      ctx.strokeStyle = isSelected ? '#FFFFFF' : '#0B0F19';
      ctx.lineWidth = isSelected ? 2.5 : 1.5;
      ctx.stroke();

      // Labels on hover, select, or high zoom
      if (isHovered || isSelected || (activeId && isNeighbor) || transform.k > 1.3) {
        ctx.font = '10px JetBrains Mono, monospace';
        ctx.fillStyle = isSelected ? '#38BDF8' : '#F8FAFC';
        ctx.textAlign = 'center';
        ctx.fillText(node.label || node.id, pos.x, pos.y - radius - 4);
      }

      ctx.restore();
    });

    ctx.restore();
  }, [nodes, links, nodePositions, transform, selectedNodeId, hoveredNode, height]);

  // Mouse interaction handlers
  const handleMouseDown = (e) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - transform.x, y: e.clientY - transform.y });
  };

  const handleMouseMove = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const mouseX = (e.clientX - rect.left - transform.x) / transform.k;
    const mouseY = (e.clientY - rect.top - transform.y) / transform.k;

    if (isDragging) {
      setTransform((prev) => ({
        ...prev,
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      }));
      return;
    }

    // Check hovered node
    let found = null;
    for (const node of nodes) {
      const pos = nodePositions[node.id];
      if (pos) {
        const dx = pos.x - mouseX;
        const dy = pos.y - mouseY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist <= 14) {
          found = node;
          break;
        }
      }
    }
    setHoveredNode(found);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleClick = (e) => {
    if (hoveredNode && onSelectNode) {
      onSelectNode(hoveredNode);
    }
  };

  const handleZoom = (factor) => {
    setTransform((prev) => ({
      ...prev,
      k: Math.max(0.4, Math.min(3.5, prev.k * factor)),
    }));
  };

  const handleReset = () => {
    setTransform({ x: 0, y: 0, k: 1 });
  };

  // Find inspected node object
  const inspectedNode = nodes.find((n) => n.id === selectedNodeId);

  // Connected accounts for inspected node
  const connectedAccounts = [];
  if (inspectedNode) {
    links.forEach((l) => {
      const srcId = typeof l.source === 'object' ? l.source.id : l.source;
      const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
      if (srcId === inspectedNode.id) {
        const other = nodes.find((n) => n.id === tgtId);
        if (other) connectedAccounts.push(other);
      } else if (tgtId === inspectedNode.id) {
        const other = nodes.find((n) => n.id === srcId);
        if (other) connectedAccounts.push(other);
      }
    });
  }

  return (
    <div ref={containerRef} className="relative w-full bg-[#090D16] border border-[#1E293B] rounded-xl overflow-hidden select-none">
      {/* Interactive Canvas */}
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: `${height}px`, cursor: isDragging ? 'grabbing' : 'grab' }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onClick={handleClick}
      />

      {/* Control Overlay */}
      <div className="absolute top-4 right-4 flex flex-col gap-1.5 bg-[#111726]/90 backdrop-blur-md border border-[#1E293B] rounded-lg p-1.5 shadow-lg z-10">
        <button
          onClick={() => handleZoom(1.2)}
          title="Zoom In"
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-[#1E293B] rounded transition-colors"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={() => handleZoom(0.8)}
          title="Zoom Out"
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-[#1E293B] rounded transition-colors"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={handleReset}
          title="Reset View"
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-[#1E293B] rounded transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* NODE INSPECTION DRAWER (SECTION 5) */}
      {inspectedNode && (
        <div className="absolute top-4 left-4 max-w-xs w-72 bg-[#111726]/95 backdrop-blur-md border border-cyan-500/40 rounded-xl p-4 shadow-2xl z-10 space-y-3 font-mono text-xs animate-in fade-in duration-150">
          <div className="flex items-center justify-between border-b border-[#1E293B] pb-2">
            <div className="flex items-center gap-2">
              {inspectedNode.type === 'account' && <Shield className="w-4 h-4 text-cyan-400" />}
              {inspectedNode.type === 'device' && <Smartphone className="w-4 h-4 text-indigo-400" />}
              {inspectedNode.type === 'ip' && <Globe className="w-4 h-4 text-cyan-400" />}
              {inspectedNode.type === 'destination' && <Target className="w-4 h-4 text-amber-400" />}
              <span className="font-bold text-white truncate max-w-[150px]">{inspectedNode.id}</span>
            </div>
            <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-[#1E293B] text-slate-300 font-bold">
              {inspectedNode.type}
            </span>
          </div>

          {inspectedNode.type === 'account' ? (
            <div className="space-y-2 text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-400">Risk Score:</span>
                <span className={`font-bold ${
                  inspectedNode.risk_score >= 80 ? 'text-red-400' :
                  inspectedNode.risk_score >= 60 ? 'text-orange-400' :
                  inspectedNode.risk_score >= 30 ? 'text-amber-400' : 'text-emerald-400'
                }`}>
                  {inspectedNode.risk_score?.toFixed(1)} / 100
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Risk Tier:</span>
                <span className="font-bold text-slate-200">{inspectedNode.risk_level}</span>
              </div>
              {inspectedNode.reasons && (
                <div className="text-[10px] text-slate-400 pt-1 border-t border-[#1E293B]">
                  <span className="text-slate-500">Reasons: </span>
                  {inspectedNode.reasons.split('|').slice(0, 2).join(', ')}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-2 text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-400">Connected Entities:</span>
                <span className="font-bold text-cyan-300">{connectedAccounts.length} Accounts</span>
              </div>
              <div className="text-[10px] text-slate-400">
                Shared across independent member accounts in this ring.
              </div>
            </div>
          )}

          {/* Connected accounts pill list */}
          {connectedAccounts.length > 0 && (
            <div className="pt-2 border-t border-[#1E293B] space-y-1">
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                Direct Neighbors ({connectedAccounts.length})
              </span>
              <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto pr-1">
                {connectedAccounts.slice(0, 8).map((neighbor) => (
                  <button
                    key={neighbor.id}
                    onClick={() => onSelectNode && onSelectNode(neighbor)}
                    className="px-1.5 py-0.5 rounded bg-[#090D16] hover:bg-[#1E293B] border border-[#1E293B] text-[10px] text-slate-300 transition-colors"
                  >
                    {neighbor.id}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Legend Footer */}
      <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between pointer-events-none">
        <div className="flex flex-wrap items-center gap-3 bg-[#111726]/90 backdrop-blur-md border border-[#1E293B] px-3.5 py-1.5 rounded-lg text-[10px] font-mono pointer-events-auto">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            <span className="text-slate-300">Critical</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-orange-500" />
            <span className="text-slate-300">High</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-slate-300">Medium</span>
          </div>
          <div className="w-px h-3 bg-[#1E293B]" />
          <div className="flex items-center gap-1.5">
            <Smartphone className="w-3 h-3 text-indigo-400" />
            <span className="text-slate-300">Device</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Globe className="w-3 h-3 text-cyan-400" />
            <span className="text-slate-300">IP</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Target className="w-3 h-3 text-amber-400" />
            <span className="text-slate-300">Destination</span>
          </div>
          <div className="w-px h-3 bg-[#1E293B]" />
          <div className="flex items-center gap-1.5 text-slate-400">
            <span className="w-3 h-0.5 border-t border-dashed border-amber-400" />
            <span>Transfers To</span>
          </div>
        </div>

        <div className="text-[10px] font-mono text-slate-500 bg-[#111726]/80 px-2.5 py-1 rounded border border-[#1E293B]">
          Drag to pan • Click node to inspect neighborhood
        </div>
      </div>
    </div>
  );
}
