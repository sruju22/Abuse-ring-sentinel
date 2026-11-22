import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw,
  Eye,
  EyeOff,
  X,
  Shield,
  Smartphone,
  Globe,
  Target,
  Filter,
  Layers,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';

// =============================================================================
// DETERMINISTIC LAYERED BIPARTITE LAYOUT ENGINE FOR CLUSTERS
// =============================================================================

function runBipartiteLayout({ nodes, links, width, height }) {
  if (!nodes || nodes.length === 0) {
    return { positions: {}, autoTransform: { x: 0, y: 0, k: 1 }, columnHeaders: [], virtualHeight: height };
  }

  // 1. Calculate degree for all nodes from active links
  const degreeMap = new Map();
  nodes.forEach((n) => degreeMap.set(n.id, 0));
  links.forEach((l) => {
    const srcId = typeof l.source === 'object' ? l.source.id : l.source;
    const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
    if (degreeMap.has(srcId)) degreeMap.set(srcId, degreeMap.get(srcId) + 1);
    if (degreeMap.has(tgtId)) degreeMap.set(tgtId, degreeMap.get(tgtId) + 1);
  });

  // 2. Separate account nodes and infrastructure entity nodes
  const accountNodes = [];
  const entityNodesByType = { destination: [], device: [], ip: [] };
  const otherEntities = [];

  nodes.forEach((node) => {
    const type = (node.type || '').toLowerCase();
    if (type === 'account') {
      accountNodes.push(node);
    } else if (type === 'destination') {
      entityNodesByType.destination.push(node);
    } else if (type === 'device') {
      entityNodesByType.device.push(node);
    } else if (type === 'ip') {
      entityNodesByType.ip.push(node);
    } else {
      otherEntities.push(node);
    }
  });

  // 3. Sort Account nodes deterministically by:
  //    (a) Calibrated Risk Tier: Critical (P >= 0.70) -> High (P >= 0.35) -> Below Threshold (P < 0.35)
  //    (b) Calibrated Probability descending
  //    (c) Account ID string tie-breaker
  const getTierRank = (node) => {
    const score = node.risk_score ?? (node.probability != null ? node.probability * 100 : 25);
    if (score >= 70) return 0; // Critical
    if (score >= 35) return 1; // High
    return 2;                  // Below threshold
  };
  const getProb = (node) => {
    if (node.probability != null) return node.probability;
    if (node.risk_score != null) return node.risk_score / 100;
    return 0.25;
  };

  accountNodes.sort((a, b) => {
    const tierA = getTierRank(a);
    const tierB = getTierRank(b);
    if (tierA !== tierB) return tierA - tierB;
    const probDiff = getProb(b) - getProb(a);
    if (Math.abs(probDiff) > 1e-5) return probDiff;
    return a.id.localeCompare(b.id);
  });

  // 4. Sort Entity nodes within each column by descending degree, then ID
  const sortEntities = (list) => {
    list.sort((a, b) => {
      const degDiff = (degreeMap.get(b.id) || 0) - (degreeMap.get(a.id) || 0);
      if (degDiff !== 0) return degDiff;
      return a.id.localeCompare(b.id);
    });
  };

  sortEntities(entityNodesByType.destination);
  sortEntities(entityNodesByType.device);
  sortEntities(entityNodesByType.ip);
  sortEntities(otherEntities);

  // 5. Establish Columns:
  //    Column 0: Accounts (on left)
  //    Subsequent Columns: Destination, Device, IP (only if nodes exist)
  const columns = [];
  if (accountNodes.length > 0) {
    columns.push({
      key: 'account',
      title: 'ACCOUNTS',
      badge: `${accountNodes.length}`,
      color: '#D58A27',
      nodes: accountNodes,
    });
  }
  if (entityNodesByType.destination.length > 0) {
    columns.push({
      key: 'destination',
      title: 'DESTINATIONS',
      badge: `${entityNodesByType.destination.length}`,
      color: '#D58A27',
      nodes: entityNodesByType.destination,
    });
  }
  if (entityNodesByType.device.length > 0) {
    columns.push({
      key: 'device',
      title: 'DEVICES',
      badge: `${entityNodesByType.device.length}`,
      color: '#7C6EAF',
      nodes: entityNodesByType.device,
    });
  }
  if (entityNodesByType.ip.length > 0) {
    columns.push({
      key: 'ip',
      title: 'IPS',
      badge: `${entityNodesByType.ip.length}`,
      color: '#4E9BB5',
      nodes: entityNodesByType.ip,
    });
  }
  if (otherEntities.length > 0) {
    columns.push({
      key: 'other',
      title: 'OTHER',
      badge: `${otherEntities.length}`,
      color: '#78858A',
      nodes: otherEntities,
    });
  }

  const numCols = columns.length;
  if (numCols === 0) {
    return { positions: {}, autoTransform: { x: 0, y: 0, k: 1 }, columnHeaders: [], virtualHeight: height };
  }

  // Viewport bounds: safe margins between top and bottom
  const screenPadTop = 44;
  const screenPadBottom = 38;
  const availableScreenH = Math.max(height - screenPadTop - screenPadBottom, 120);

  const maxNodesInCol = Math.max(...columns.map((c) => c.nodes.length));
  let spacingY;
  if (maxNodesInCol <= 12) spacingY = 32;
  else if (maxNodesInCol <= 25) spacingY = 22;
  else if (maxNodesInCol <= 50) spacingY = 16;
  else if (maxNodesInCol <= 100) spacingY = 13;
  else spacingY = 11;

  const totalColSpan = (maxNodesInCol - 1) * spacingY;
  const targetScale = Math.min(1.25, availableScreenH / Math.max(totalColSpan, 100));

  const screenPadLeft = numCols <= 2 ? 85 : 65;
  const screenPadRight = numCols <= 2 ? 85 : 65;
  const availableScreenW = Math.max(width - screenPadLeft - screenPadRight, 200);
  const screenColSpacing = numCols > 1 ? availableScreenW / (numCols - 1) : 0;

  const padLeft = screenPadLeft / targetScale;
  const colSpacing = screenColSpacing / targetScale;

  const contentTopY = 44 / targetScale;
  const virtualHeight = contentTopY + totalColSpan + 30 / targetScale;

  columns.forEach((col, idx) => {
    col.x = padLeft + idx * colSpacing;
  });

  const positions = {};
  const columnHeaders = [];

  columns.forEach((col) => {
    columnHeaders.push({
      key: col.key,
      title: col.title,
      badge: col.badge,
      color: col.color,
      x: col.x,
    });

    const n = col.nodes.length;
    if (n === 0) return;
    if (n === 1) {
      positions[col.nodes[0].id] = {
        x: col.x,
        y: contentTopY + totalColSpan / 2,
        type: col.nodes[0].type,
        colKey: col.key,
      };
      return;
    }

    // For smaller columns, space nodes gracefully across the span
    const step = n < maxNodesInCol * 0.45
      ? Math.min(spacingY * 2.8, Math.max(spacingY, totalColSpan / (n + 1)))
      : spacingY;
    const actualHeight = (n - 1) * step;
    const startY = contentTopY + (totalColSpan - actualHeight) / 2;

    col.nodes.forEach((node, idx) => {
      positions[node.id] = {
        x: col.x,
        y: startY + idx * step,
        type: node.type,
        colKey: col.key,
      };
    });
  });

  return {
    positions,
    autoTransform: { x: 0, y: 0, k: targetScale },
    columnHeaders,
    virtualHeight,
  };
}

// =============================================================================
// COMPONENT-AWARE & LABEL-AWARE FORCE-DIRECTED LAYOUT ENGINE
// =============================================================================

function runForceSimulation({
  nodes,
  links,
  width,
  height,
  focalNodeId,
  iterations = 200,
}) {
  if (!nodes || nodes.length === 0) {
    return { positions: {}, autoTransform: { x: 0, y: 0, k: 1 } };
  }

  const cx = width / 2;
  const cy = height / 2;

  // 1. Build adjacency list for connected components analysis
  const adj = new Map();
  nodes.forEach((n) => adj.set(n.id, new Set()));
  links.forEach((l) => {
    const srcId = typeof l.source === 'object' ? l.source.id : l.source;
    const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
    if (adj.has(srcId) && adj.has(tgtId) && srcId !== tgtId) {
      adj.get(srcId).add(tgtId);
      adj.get(tgtId).add(srcId);
    }
  });

  // 2. Detect Connected Components via BFS
  const visited = new Set();
  const components = [];
  const singletons = [];

  nodes.forEach((node) => {
    if (visited.has(node.id)) return;
    const neighbors = adj.get(node.id);

    if (!neighbors || neighbors.size === 0) {
      visited.add(node.id);
      singletons.push(node);
      return;
    }

    const comp = [];
    const queue = [node.id];
    visited.add(node.id);

    while (queue.length > 0) {
      const currId = queue.shift();
      const currNode = nodes.find((n) => n.id === currId);
      if (currNode) comp.push(currNode);

      adj.get(currId).forEach((nbrId) => {
        if (!visited.has(nbrId)) {
          visited.add(nbrId);
          queue.push(nbrId);
        }
      });
    }

    components.push(comp);
  });

  // Sort components by size descending
  components.sort((a, b) => b.length - a.length);

  // 3. Assign Component Anchor Centers & IDs
  const compCenters = new Map();
  const compIdMap = new Map();
  const isEgoNetwork = components.length === 1 && Boolean(focalNodeId);

  if (components.length === 1) {
    // Single connected component (e.g. ego network)
    components[0].forEach((n) => {
      compCenters.set(n.id, { x: cx, y: cy });
      compIdMap.set(n.id, 0);
    });
  } else if (components.length > 1) {
    // Multi-component graph: distribute component centers in an ellipse
    const numComp = components.length;
    const compRadiusX = Math.min(width, 720) * 0.32;
    const compRadiusY = Math.min(height, 460) * 0.26;

    components.forEach((comp, cIdx) => {
      const angle = (cIdx / numComp) * 2 * Math.PI - Math.PI / 2;
      const compX = cx + Math.cos(angle) * compRadiusX;
      const compY = cy - 22 + Math.sin(angle) * compRadiusY;
      comp.forEach((n) => {
        compCenters.set(n.id, { x: compX, y: compY });
        compIdMap.set(n.id, cIdx);
      });
    });
  }

  // Singletons track (arranged in a neat bottom row with clear spacing)
  singletons.forEach((n, idx) => {
    const spacing = Math.min(65, (width - 120) / Math.max(1, singletons.length));
    const startX = cx - ((singletons.length - 1) * spacing) / 2;
    compCenters.set(n.id, {
      x: startX + idx * spacing,
      y: height - 68,
    });
    compIdMap.set(n.id, -1);
  });

  // 4. Initialize node bodies with label-aware dimensions
  const nodeMap = new Map();
  const nonFocalAccounts = nodes.filter((n) => !n.isFocal && n.id !== focalNodeId && n.type === 'account');
  const infraNodes = nodes.filter((n) => n.type !== 'account');

  nodes.forEach((node, idx) => {
    const isFocal = node.isFocal || node.id === focalNodeId;
    const isSingleton = singletons.some((s) => s.id === node.id);
    const assignedCenter = compCenters.get(node.id) || { x: cx, y: cy };

    let initX, initY, targetR = 0;
    if (isEgoNetwork) {
      if (isFocal) {
        initX = cx;
        initY = cy;
        targetR = 0;
      } else if (node.type !== 'account') {
        const infIdx = infraNodes.findIndex((x) => x.id === node.id);
        const angle = (infIdx / Math.max(1, infraNodes.length)) * 2 * Math.PI - Math.PI / 2;
        targetR = 85;
        initX = cx + Math.cos(angle) * 85;
        initY = cy + Math.sin(angle) * 70;
      } else {
        const accIdx = nonFocalAccounts.findIndex((x) => x.id === node.id);
        const angle = (accIdx / Math.max(1, nonFocalAccounts.length)) * 2 * Math.PI;
        targetR = 175;
        initX = cx + Math.cos(angle) * 175;
        initY = cy + Math.sin(angle) * 145;
      }
    } else {
      // Cluster graph: separate infrastructure hubs from member accounts
      if (node.type !== 'account') {
        const infIdx = infraNodes.findIndex((x) => x.id === node.id);
        const angle = (infIdx / Math.max(1, infraNodes.length)) * 2 * Math.PI - Math.PI / 2;
        const hubRadiusX = Math.min(width, 700) * 0.35;
        const hubRadiusY = Math.min(height, 400) * 0.32;
        initX = assignedCenter.x + Math.cos(angle) * hubRadiusX;
        initY = assignedCenter.y + Math.sin(angle) * hubRadiusY;
      } else {
        const accIdx = nonFocalAccounts.findIndex((x) => x.id === node.id);
        const angle = (accIdx / Math.max(1, nonFocalAccounts.length)) * 2 * Math.PI;
        const accRadiusX = isSingleton ? 0 : Math.min(width, 700) * 0.44;
        const accRadiusY = isSingleton ? 0 : Math.min(height, 400) * 0.40;
        initX = isSingleton ? assignedCenter.x : assignedCenter.x + Math.cos(angle) * accRadiusX;
        initY = isSingleton ? assignedCenter.y : assignedCenter.y + Math.sin(angle) * accRadiusY;
      }
    }

    // Label-aware collision half-dimensions:
    // Focal account has a permanent label (~120px wide by 30px high)
    // Other accounts / entities have compact collision bounds
    let rx = 24;
    let ry = 24;
    if (isFocal) {
      rx = 85; // Extra horizontal margin for the permanent focal label pill
      ry = 42;
    } else if (node.type === 'destination' || node.type === 'device' || node.type === 'ip') {
      rx = 34; // Margin for short infrastructure ID pill (e.g. DEST_0366)
      ry = 26;
    } else {
      rx = 26;
      ry = 26;
    }

    nodeMap.set(node.id, {
      id: node.id,
      x: initX,
      y: initY,
      vx: 0,
      vy: 0,
      rx,
      ry,
      isFocal,
      targetR,
      type: node.type,
      compId: compIdMap.get(node.id) ?? -1,
      compCenter: assignedCenter,
      isSingleton,
      node,
    });
  });

  // 5. Prepare link list
  const linkList = [];
  links.forEach((l) => {
    const srcId = typeof l.source === 'object' ? l.source.id : l.source;
    const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
    if (nodeMap.has(srcId) && nodeMap.has(tgtId) && srcId !== tgtId) {
      linkList.push({
        source: nodeMap.get(srcId),
        target: nodeMap.get(tgtId),
        type: l.type,
      });
    }
  });

  // 6. Physics Simulation Loop with Label-Aware Collision Avoidance
  const nodesArr = Array.from(nodeMap.values());
  let temp = 1.0;
  const tempDecay = 0.982;

  for (let step = 0; step < iterations; step++) {
    // A. Label-aware repulsion and collision resolution
    for (let i = 0; i < nodesArr.length; i++) {
      const u = nodesArr[i];
      for (let j = i + 1; j < nodesArr.length; j++) {
        const v = nodesArr[j];
        if (u.isSingleton && v.isSingleton) continue;

        const dx = v.x - u.x;
        const dy = v.y - u.y;
        const distSq = dx * dx + dy * dy;
        const dist = Math.sqrt(distSq) || 1;

        // Same-component repulsion (or ego network focal repulsion)
        if (u.compId === v.compId && u.compId !== -1) {
          const isBothHubs = u.type !== 'account' && v.type !== 'account';
          const kRep = (u.isFocal || v.isFocal) ? 2800 : isBothHubs ? 10000 : 3800;
          const force = (kRep / Math.max(distSq, 400)) * temp;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          if (!u.isFocal && !u.isSingleton) {
            u.vx -= fx;
            u.vy -= fy;
          }
          if (!v.isFocal && !v.isSingleton) {
            v.vx += fx;
            v.vy += fy;
          }
        } else if (dist < 280) {
          // Cross-component gentle anti-collision
          const force = (600 / Math.max(distSq, 400)) * temp;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          if (!u.isFocal && !u.isSingleton) {
            u.vx -= fx;
            u.vy -= fy;
          }
          if (!v.isFocal && !v.isSingleton) {
            v.vx += fx;
            v.vy += fy;
          }
        }

        // Elliptical label-aware collision push
        const sumRx = u.rx + v.rx + 8;
        const sumRy = u.ry + v.ry + 8;
        const normDistSq = (dx * dx) / (sumRx * sumRx) + (dy * dy) / (sumRy * sumRy);
        if (normDistSq < 1.0) {
          const overlap = (1.0 - Math.sqrt(normDistSq)) * 6 * temp;
          const pushX = (dx / dist) * overlap * 0.5;
          const pushY = (dy / dist) * overlap * 0.5;

          if (!u.isFocal && !u.isSingleton) {
            u.x -= pushX;
            u.y -= pushY;
          }
          if (!v.isFocal && !v.isSingleton) {
            v.x += pushX;
            v.y += pushY;
          }
        }
      }
    }

    // B. Spring attraction along links
    linkList.forEach((link) => {
      const u = link.source;
      const v = link.target;
      const dx = v.x - u.x;
      const dy = v.y - u.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;

      // Rest length: give focal account neighborhood ample room
      let idealDist = 80;
      if (u.isFocal || v.isFocal) {
        idealDist = u.type === 'account' && v.type === 'account' ? 140 : 105;
      } else if (u.type === 'account' && v.type === 'account') {
        idealDist = 110;
      } else {
        idealDist = nodes.length > 40 ? 75 : 105;
      }

      const displacement = dist - idealDist;
      const force = displacement * (nodes.length > 30 ? 0.04 : 0.06) * temp;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;

      if (!u.isFocal && !u.isSingleton) {
        u.vx += fx;
        u.vy += fy;
      }
      if (!v.isFocal && !v.isSingleton) {
        v.vx += fx;
        v.vy += fy;
      }
    });

    // C. Orbit Tether or Anchor Center Gravity
    nodesArr.forEach((u) => {
      if (u.isFocal) {
        u.x = cx;
        u.y = cy;
        u.vx = 0;
        u.vy = 0;
        return;
      }

      if (u.isSingleton) {
        u.y = u.compCenter.y;
        u.vx = 0;
        u.vy = 0;
        return;
      }

      if (isEgoNetwork) {
        const dx = u.x - cx;
        const dy = u.y - cy;
        const curR = Math.sqrt(dx * dx + dy * dy) || 1;
        const rDiff = u.targetR - curR;
        const kOrbit = 0.08;
        u.vx += (dx / curR) * rDiff * kOrbit;
        u.vy += (dy / curR) * rDiff * kOrbit;
      } else {
        const kGrav = nodes.length > 30 ? 0.005 : 0.045;
        u.vx += (u.compCenter.x - u.x) * kGrav;
        u.vy += (u.compCenter.y - u.y) * kGrav;
      }

      u.x += Math.max(-10, Math.min(10, u.vx));
      u.y += Math.max(-10, Math.min(10, u.vy));

      u.vx *= 0.65;
      u.vy *= 0.65;
    });

    temp *= tempDecay;
  }

  // 7. Calculate Bounding Box and Auto-Fit Transform
  const finalNodes = Array.from(nodeMap.values());
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  const positions = {};
  finalNodes.forEach((n) => {
    positions[n.id] = { x: n.x, y: n.y };
    // Include node dimensions in bounding box
    if (n.x - n.rx < minX) minX = n.x - n.rx;
    if (n.x + n.rx > maxX) maxX = n.x + n.rx;
    if (n.y - n.ry < minY) minY = n.y - n.ry;
    if (n.y + n.ry > maxY) maxY = n.y + n.ry;
  });

  const padX = 40;
  const padTop = 45;
  const padBottom = 45;

  const contentW = Math.max(maxX - minX, 80);
  const contentH = Math.max(maxY - minY, 80);

  const availableW = Math.max(width - padX * 2, 100);
  const availableH = Math.max(height - padTop - padBottom, 100);

  const maxScale = nodes.length <= 6 ? 1.3 : nodes.length <= 25 ? 2.2 : 2.5;
  const scale = Math.min(availableW / contentW, availableH / contentH, maxScale);

  const midX = (minX + maxX) / 2;
  const midY = (minY + maxY) / 2;

  const tx = width / 2 - midX * scale;
  const ty = padTop + availableH / 2 - midY * scale;

  return {
    positions,
    autoTransform: { x: tx, y: ty, k: scale },
    componentsCount: components.length,
    singletonsCount: singletons.length,
  };
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function NetworkGraph({
  nodes = [],
  links = [],
  onSelectNode,
  selectedNodeId,
  onInspectAccount,
  height = 380,
  focalNodeId = null,
  hideEdgeFilter = false,
  defaultLayout = 'bipartite',
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  // Layout & Transform state
  const [layoutMode, setLayoutMode] = useState(defaultLayout);
  const [columnHeaders, setColumnHeaders] = useState([]);
  const [virtualHeight, setVirtualHeight] = useState(height);
  const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
  const [defaultTransform, setDefaultTransform] = useState({ x: 0, y: 0, k: 1 });
  const [nodePositions, setNodePositions] = useState({});
  const [showAllLabels, setShowAllLabels] = useState(false);
  const [filterType, setFilterType] = useState('ALL');

  // Mouse interaction state
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [internalSelectedId, setInternalSelectedId] = useState(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  // Effective selected ID supports both controlled (selectedNodeId) and internal selection
  const effectiveSelectedId = selectedNodeId !== undefined ? selectedNodeId : internalSelectedId;

  // Active focal ID
  const activeFocalId = useMemo(() => {
    if (focalNodeId) return focalNodeId;
    const focalNode = nodes.find((n) => n.isFocal);
    return focalNode ? focalNode.id : null;
  }, [focalNodeId, nodes]);

  // Find inspected node object
  const activeInspectedNode = useMemo(() => {
    return nodes.find((n) => n.id === effectiveSelectedId) || (inspectorOpen ? hoveredNode : null);
  }, [nodes, effectiveSelectedId, inspectorOpen, hoveredNode]);

  // Adjust canvas viewport dynamically so inspector dock does NOT expand the card or cause page overflow
  const canvasHeight = inspectorOpen && activeInspectedNode ? Math.max(height - 56, 260) : height;

  // Extract unique relationship types from links for the filter bar
  const availableRelTypes = useMemo(() => {
    const types = new Set();
    links.forEach((l) => {
      if (l.type) types.add(l.type.toUpperCase());
    });
    return Array.from(types);
  }, [links]);

  // Filtered links based on toolbar filter
  const filteredLinks = useMemo(() => {
    if (filterType === 'ALL') return links;
    return links.filter(
      (l) => (l.type || '').toUpperCase() === filterType
    );
  }, [links, filterType]);

  // ---------------------------------------------------------------------------
  // RUN LAYOUT (Bipartite Layered OR Force-Directed Physics)
  // ---------------------------------------------------------------------------
  const runLayout = useCallback(() => {
    if (!nodes || nodes.length === 0) return;
    const width = containerRef.current?.clientWidth || 750;

    if (layoutMode === 'bipartite') {
      const res = runBipartiteLayout({
        nodes,
        links,
        width,
        height: canvasHeight,
      });
      setNodePositions(res.positions);
      setColumnHeaders(res.columnHeaders);
      setVirtualHeight(res.virtualHeight || canvasHeight);
      setTransform(res.autoTransform);
      setDefaultTransform(res.autoTransform);
    } else {
      const res = runForceSimulation({
        nodes,
        links,
        width,
        height: canvasHeight,
        focalNodeId: activeFocalId,
        iterations: 210,
      });
      setNodePositions(res.positions);
      setColumnHeaders([]);
      setVirtualHeight(canvasHeight);
      setTransform(res.autoTransform);
      setDefaultTransform(res.autoTransform);
    }
  }, [nodes, links, canvasHeight, activeFocalId, layoutMode]);

  // Trigger layout on data change or container resize
  useEffect(() => {
    runLayout();

    if (!containerRef.current) return;
    const observer = new ResizeObserver(() => {
      runLayout();
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [runLayout]);

  // Automatically open inspector dock when selectedNodeId changes externally
  useEffect(() => {
    if (selectedNodeId) {
      setInspectorOpen(true);
    }
  }, [selectedNodeId]);

  // Automatically fit the graph transform to available viewport after opening or closing inspector
  useEffect(() => {
    const width = containerRef.current?.clientWidth || 750;
    if (Object.keys(nodePositions).length > 0) {
      let minX = Infinity;
      let maxX = -Infinity;
      let minY = Infinity;
      let maxY = -Infinity;

      nodes.forEach((n) => {
        const p = nodePositions[n.id];
        if (!p) return;
        const rx = n.rx || (n.isFocal ? 85 : n.type === 'account' ? 26 : 34);
        const ry = n.ry || (n.isFocal ? 42 : n.type === 'account' ? 26 : 26);
        if (p.x - rx < minX) minX = p.x - rx;
        if (p.x + rx > maxX) maxX = p.x + rx;
        if (p.y - ry < minY) minY = p.y - ry;
        if (p.y + ry > maxY) maxY = p.y + ry;
      });

      if (isFinite(minX)) {
        const padX = 35;
        const padTop = 35;
        const padBottom = 35;
        const contentW = Math.max(maxX - minX + padX * 2, 80);
        const contentH = Math.max(maxY - minY + padTop + padBottom, 80);
        const availableW = Math.max(width - 30, 100);
        const availableH = Math.max(canvasHeight - 30, 100);
        const maxScale = layoutMode === 'bipartite' ? 1.25 : (nodes.length <= 6 ? 1.3 : nodes.length <= 25 ? 2.2 : 2.5);
        const scale = Math.min(availableW / contentW, availableH / contentH, maxScale);
        const midX = (minX + maxX) / 2;
        const midY = (minY + maxY) / 2;
        const tx = width / 2 - midX * scale;
        const ty = canvasHeight / 2 - midY * scale;

        setTransform({ x: tx, y: ty, k: scale });
        setDefaultTransform({ x: tx, y: ty, k: scale });
      }
    }
  }, [canvasHeight, nodes, nodePositions, layoutMode]);

  // ---------------------------------------------------------------------------
  // CANVAS RENDER LOOP
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = containerRef.current?.clientWidth || 750;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = canvasHeight * dpr;
    ctx.scale(dpr, dpr);

    // Warm light background
    ctx.fillStyle = '#F7F6F2';
    ctx.fillRect(0, 0, width, canvasHeight);

    ctx.save();
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.k, transform.k);

    // Compute active target and direct neighbors (hover takes precedence during mouseover)
    const activeTargetId = hoveredNode?.id || effectiveSelectedId;
    const neighborIds = new Set();
    const activeLinkList = [];

    if (activeTargetId) {
      neighborIds.add(activeTargetId);
      links.forEach((link) => {
        const srcId = typeof link.source === 'object' ? link.source.id : link.source;
        const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
        if (srcId === activeTargetId) {
          neighborIds.add(tgtId);
          activeLinkList.push(link);
        }
        if (tgtId === activeTargetId) {
          neighborIds.add(srcId);
          activeLinkList.push(link);
        }
      });
    }

    // -------------------------------------------------------------------------
    // 0. DRAW COLUMN GUIDELINES (Bipartite Mode Only)
    // -------------------------------------------------------------------------
    if (layoutMode === 'bipartite' && columnHeaders.length > 0) {
      columnHeaders.forEach((col) => {
        ctx.save();
        ctx.setLineDash([2, 5]);
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.06)';
        ctx.lineWidth = Math.max(1, 1 / transform.k);
        ctx.beginPath();
        ctx.moveTo(col.x, 30 / transform.k);
        ctx.lineTo(col.x, (virtualHeight || 600) + 20);
        ctx.stroke();
        ctx.restore();
      });
    }

    // -------------------------------------------------------------------------
    // 1. DRAW EDGES (Curved Beziers with Progressive Relationship Labels)
    // -------------------------------------------------------------------------
    const isBipartite = layoutMode === 'bipartite';
    const isHighVolume = filteredLinks.length > 500;
    const isMedVolume = filteredLinks.length > 150;

    filteredLinks.forEach((link) => {
      const srcId = typeof link.source === 'object' ? link.source.id : link.source;
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
      const src = nodePositions[srcId];
      const tgt = nodePositions[tgtId];

      if (!src || !tgt) return;

      const isConnected =
        activeTargetId ? srcId === activeTargetId || tgtId === activeTargetId : false;
      const isDimmed = activeTargetId && !isConnected;

      ctx.beginPath();
      ctx.moveTo(src.x, src.y);

      let midX = (src.x + tgt.x) / 2;
      let midY = (src.y + tgt.y) / 2;

      if (isBipartite) {
        // Horizontal S-curve (cubic bezier)
        const leftNode = src.x <= tgt.x ? src : tgt;
        const rightNode = src.x <= tgt.x ? tgt : src;
        const dx = rightNode.x - leftNode.x;
        const cpDist = Math.max(30, dx * 0.48);

        const cp1x = src.x + (src.x <= tgt.x ? cpDist : -cpDist);
        const cp1y = src.y;
        const cp2x = tgt.x + (src.x <= tgt.x ? -cpDist : cpDist);
        const cp2y = tgt.y;

        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, tgt.x, tgt.y);
      } else {
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const nx = -dy / dist;
        const ny = dx / dist;

        let pairHash = 0;
        const str = `${srcId}-${tgtId}`;
        for (let i = 0; i < str.length; i++) pairHash += str.charCodeAt(i);
        const curveAmount = (pairHash % 2 === 0 ? 1 : -1) * 12;

        const cx = midX + nx * curveAmount;
        const cy = midY + ny * curveAmount;
        ctx.quadraticCurveTo(cx, cy, tgt.x, tgt.y);
        midX = cx;
        midY = cy;
      }

      const relType = (link.type || '').toUpperCase();

      if (relType.includes('DESTINATION')) {
        // Warm Amber dashed
        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = isDimmed
          ? 'rgba(213, 138, 39, 0.03)'
          : isConnected && activeTargetId
          ? '#D58A27'
          : isHighVolume
          ? 'rgba(213, 138, 39, 0.12)'
          : isMedVolume
          ? 'rgba(213, 138, 39, 0.25)'
          : 'rgba(213, 138, 39, 0.45)';
        ctx.lineWidth = isConnected && activeTargetId ? 2.4 : isHighVolume ? 0.85 : 1.2;
      } else if (relType.includes('DEVICE')) {
        // Muted violet solid
        ctx.setLineDash([]);
        ctx.strokeStyle = isDimmed
          ? 'rgba(124, 110, 175, 0.03)'
          : isConnected && activeTargetId
          ? '#7C6EAF'
          : isHighVolume
          ? 'rgba(124, 110, 175, 0.14)'
          : isMedVolume
          ? 'rgba(124, 110, 175, 0.25)'
          : 'rgba(124, 110, 175, 0.45)';
        ctx.lineWidth = isConnected && activeTargetId ? 2.4 : isHighVolume ? 0.95 : 1.4;
      } else if (relType.includes('IP')) {
        // Muted teal solid
        ctx.setLineDash([]);
        ctx.strokeStyle = isDimmed
          ? 'rgba(78, 155, 181, 0.03)'
          : isConnected && activeTargetId
          ? '#4E9BB5'
          : isHighVolume
          ? 'rgba(78, 155, 181, 0.12)'
          : isMedVolume
          ? 'rgba(78, 155, 181, 0.22)'
          : 'rgba(78, 155, 181, 0.40)';
        ctx.lineWidth = isConnected && activeTargetId ? 2.4 : isHighVolume ? 0.9 : 1.3;
      } else if (relType.includes('TIMING') || relType.includes('SYNCHRONY')) {
        // Coral dotted
        ctx.setLineDash([2, 3]);
        ctx.strokeStyle = isDimmed
          ? 'rgba(198, 75, 67, 0.03)'
          : isConnected && activeTargetId
          ? '#C64B43'
          : 'rgba(198, 75, 67, 0.35)';
        ctx.lineWidth = isConnected && activeTargetId ? 2.4 : 1.2;
      } else {
        // Generic subtle grey
        ctx.setLineDash([]);
        ctx.strokeStyle = isDimmed
          ? 'rgba(120, 133, 138, 0.03)'
          : 'rgba(120, 133, 138, 0.18)';
        ctx.lineWidth = 0.9;
      }

      ctx.stroke();
      ctx.setLineDash([]); // Reset

      // Progressive Relationship Label: Reveal ONLY on hover or selection
      if (isConnected && activeTargetId && (hoveredNode || selectedNodeId)) {
        const edgeLabel = link.type.replace('shared_', '').replace('_', ' ').toUpperCase();
        ctx.font = 'bold 9px JetBrains Mono, monospace';
        const tw = ctx.measureText(edgeLabel).width;

        ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
        ctx.strokeStyle = 'rgba(20, 125, 105, 0.6)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.rect(midX - tw / 2 - 4, midY - 7, tw + 8, 14);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#147D69';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(edgeLabel, midX, midY);
      }
    });

    // -------------------------------------------------------------------------
    // 2. DRAW NODES (Distinct Shapes & Probability-Derived Colors)
    // -------------------------------------------------------------------------
    nodes.forEach((node) => {
      const pos = nodePositions[node.id];
      if (!pos) return;

      const isSelected = selectedNodeId === node.id || internalSelectedId === node.id;
      const isHovered = hoveredNode?.id === node.id;
      const isFocal = node.isFocal || node.id === activeFocalId;
      const isNeighbor = activeTargetId ? neighborIds.has(node.id) : true;

      ctx.save();
      if (activeTargetId && !isNeighbor) {
        ctx.globalAlpha = 0.15;
      }

      const baseRadius = isFocal ? 14 : node.type === 'account' ? (nodes.length > 100 ? 7 : 9) : (nodes.length > 100 ? 6.5 : 8);
      const minScreenR = 4.0;
      const radius = Math.max(baseRadius, minScreenR / transform.k);

      // Subtle halo for focal, selected, or critical nodes
      if (isFocal || isSelected || isHovered || (node.risk_score && node.risk_score >= 70 && !activeTargetId)) {
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius + 5, 0, 2 * Math.PI);
        ctx.fillStyle = isFocal
          ? 'rgba(20, 125, 105, 0.25)'
          : isSelected || isHovered
          ? 'rgba(20, 125, 105, 0.30)'
          : 'rgba(198, 75, 67, 0.20)';
        ctx.fill();
      }

      // Outer focus beacon ring
      if (isFocal || isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius + 5, 0, 2 * Math.PI);
        ctx.setLineDash([4, 3]);
        ctx.strokeStyle = '#147D69';
        ctx.lineWidth = 1.6;
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Render distinct shape based on node.type
      if (node.type === 'account') {
        // --- ACCOUNT: CIRCLE ---
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius, 0, 2 * Math.PI);

        const score = node.risk_score != null ? node.risk_score : (node.probability != null ? node.probability * 100 : 25);
        if (score >= 70) ctx.fillStyle = '#C64B43'; // Critical (P >= 0.70)
        else if (score >= 35) ctx.fillStyle = '#D58A27'; // High (P >= 0.35)
        else ctx.fillStyle = '#78858A'; // Below Threshold

        ctx.fill();
        ctx.strokeStyle = isSelected || isHovered ? '#252B29' : '#E2E0D8';
        ctx.lineWidth = isSelected || isHovered ? 2.5 : 1.6;
        ctx.stroke();

        // Inner white dot for focal node
        if (isFocal) {
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, 4, 0, 2 * Math.PI);
          ctx.fillStyle = '#FFFFFF';
          ctx.fill();
        }
      } else if (node.type === 'device') {
        // --- DEVICE: ROUNDED SQUARE ---
        const s = radius * 2;
        const x = pos.x - radius;
        const y = pos.y - radius;
        const r = 3;

        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + s - r, y);
        ctx.quadraticCurveTo(x + s, y, x + s, y + r);
        ctx.lineTo(x + s, y + s - r);
        ctx.quadraticCurveTo(x + s, y + s, x + s - r, y + s);
        ctx.lineTo(x + r, y + s);
        ctx.quadraticCurveTo(x, y + s, x, y + s - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();

        ctx.fillStyle = '#7C6EAF'; // Muted violet
        ctx.fill();
        ctx.strokeStyle = isSelected || isHovered ? '#252B29' : '#E2E0D8';
        ctx.lineWidth = isSelected || isHovered ? 2.5 : 1.6;
        ctx.stroke();

        if (radius >= 6) {
          ctx.fillStyle = '#FFFFFF';
          ctx.fillRect(pos.x - 3, pos.y - 3, 6, 6);
        }
      } else if (node.type === 'ip') {
        // --- IP: DIAMOND ---
        const d = radius * 1.2;
        ctx.beginPath();
        ctx.moveTo(pos.x, pos.y - d);
        ctx.lineTo(pos.x + d, pos.y);
        ctx.lineTo(pos.x, pos.y + d);
        ctx.lineTo(pos.x - d, pos.y);
        ctx.closePath();

        ctx.fillStyle = '#4E9BB5'; // Muted teal
        ctx.fill();
        ctx.strokeStyle = isSelected || isHovered ? '#252B29' : '#E2E0D8';
        ctx.lineWidth = isSelected || isHovered ? 2.5 : 1.6;
        ctx.stroke();

        if (radius >= 6) {
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, 2.5, 0, 2 * Math.PI);
          ctx.fillStyle = '#FFFFFF';
          ctx.fill();
        }
      } else if (node.type === 'destination') {
        // --- DESTINATION: HEXAGON ---
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
          const angle = (i * Math.PI) / 3;
          const hx = pos.x + radius * 1.15 * Math.cos(angle);
          const hy = pos.y + radius * 1.15 * Math.sin(angle);
          if (i === 0) ctx.moveTo(hx, hy);
          else ctx.lineTo(hx, hy);
        }
        ctx.closePath();

        ctx.fillStyle = '#D58A27'; // Warm Amber
        ctx.fill();
        ctx.strokeStyle = isSelected || isHovered ? '#252B29' : '#E2E0D8';
        ctx.lineWidth = isSelected || isHovered ? 2.5 : 1.6;
        ctx.stroke();

        if (radius >= 6) {
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, 3, 0, 2 * Math.PI);
          ctx.fillStyle = '#FFFFFF';
          ctx.fill();
        }
      }

      // -----------------------------------------------------------------------
      // 3. NODE LABELS (Progressive Disclosure Policy)
      // -----------------------------------------------------------------------
      const isEntity = node.type !== 'account';
      const infraNodesCount = nodes.filter((n) => n.type !== 'account').length;
      const shouldDrawLabel =
        isFocal ||
        isHovered ||
        isSelected ||
        (activeTargetId && isNeighbor) ||
        showAllLabels ||
        (isEntity && infraNodesCount <= 6 && layoutMode !== 'bipartite');

      if (shouldDrawLabel) {
        const labelText = isFocal ? `${node.id} (Focal)` : node.label || node.id;
        ctx.font = isFocal
          ? 'bold 11px JetBrains Mono, monospace'
          : '10px JetBrains Mono, monospace';
        const textMetrics = ctx.measureText(labelText);
        const textW = textMetrics.width;
        const textH = 14;
        const labelY = pos.y - radius - 6;

        // Label background pill
        ctx.fillStyle = isSelected || isHovered
          ? 'rgba(255, 255, 255, 0.96)'
          : isFocal
          ? 'rgba(20, 125, 105, 0.12)'
          : 'rgba(255, 255, 255, 0.92)';
        ctx.strokeStyle = isSelected || isHovered
          ? '#147D69'
          : isFocal
          ? '#147D69'
          : 'rgba(226, 224, 216, 0.8)';
        ctx.lineWidth = 1;

        ctx.beginPath();
        const rx = pos.x - textW / 2 - 4;
        const ry = labelY - textH + 2;
        ctx.rect(rx, ry, textW + 8, textH);
        ctx.fill();
        ctx.stroke();

        // Label text
        ctx.fillStyle = isSelected || isHovered
          ? '#147D69'
          : isFocal
          ? '#147D69'
          : '#252B29';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(labelText, pos.x, labelY - textH / 2 + 2);
      }

      ctx.restore();
    });

    ctx.restore();

    // -------------------------------------------------------------------------
    // 4. DRAW COLUMN HEADER PILLS IN SCREEN-SPACE (Crisp 1:1, Never Clipped)
    // -------------------------------------------------------------------------
    if (layoutMode === 'bipartite' && columnHeaders.length > 0) {
      columnHeaders.forEach((col) => {
        const screenX = col.x * transform.k + transform.x;
        const screenY = 20; // Fixed 20px from top of canvas
        const label = `${col.title} (${col.badge})`;

        ctx.save();
        ctx.font = 'bold 10px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const tw = ctx.measureText(label).width;
        const pillH = 19;
        const pillPad = 7;

        // Header Pill Background & Border
        ctx.fillStyle = '#FFFFFF';
        ctx.strokeStyle = col.color;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.rect(screenX - tw / 2 - pillPad, screenY - pillH / 2, tw + pillPad * 2, pillH);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = col.color;
        ctx.fillText(label, screenX, screenY);
        ctx.restore();
      });
    }
  }, [
    nodes,
    links,
    filteredLinks,
    nodePositions,
    transform,
    selectedNodeId,
    internalSelectedId,
    hoveredNode,
    activeFocalId,
    canvasHeight,
    showAllLabels,
    layoutMode,
    columnHeaders,
    virtualHeight,
  ]);

  // ---------------------------------------------------------------------------
  // INTERACTION HANDLERS (Pan, Zoom, Hover, Selection)
  // ---------------------------------------------------------------------------
  const handleMouseDown = (e) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - transform.x, y: e.clientY - transform.y });
  };

  const getNodeAtPoint = (clientX, clientY) => {
    let closestNode = null;
    let closestDistSq = Infinity;
    const hitThreshold = 14; // Screen pixels threshold for easy hover

    for (const node of nodes) {
      const pos = nodePositions[node.id];
      if (pos) {
        const screenX = pos.x * transform.k + transform.x;
        const screenY = pos.y * transform.k + transform.y;
        const dx = screenX - clientX;
        const dy = screenY - clientY;
        const distSq = dx * dx + dy * dy;
        const hitR = node.isFocal ? 24 : hitThreshold;
        if (distSq <= hitR * hitR && distSq < closestDistSq) {
          closestDistSq = distSq;
          closestNode = node;
        }
      }
    }
    return closestNode;
  };

  const handleMouseMove = (e) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;
    setMousePos({ x: clientX, y: clientY });

    if (isDragging) {
      setTransform((prev) => ({
        ...prev,
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      }));
      return;
    }

    setHoveredNode(getNodeAtPoint(clientX, clientY));
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleClick = (e) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    let hit = hoveredNode;
    if (e && rect) {
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;
      hit = getNodeAtPoint(clientX, clientY) || hoveredNode;
    }

    if (hit) {
      setInternalSelectedId(hit.id);
      setInspectorOpen(true);
      if (onSelectNode) onSelectNode(hit);
    } else {
      // Clicked empty background: deselect
      setInternalSelectedId(null);
      setInspectorOpen(false);
      if (onSelectNode) onSelectNode(null);
    }
  };

  const handleZoom = (factor) => {
    setTransform((prev) => {
      const width = containerRef.current?.clientWidth || 750;
      const newK = Math.max(0.35, Math.min(3.5, prev.k * factor));
      const midX = width / 2;
      const midY = canvasHeight / 2;
      return {
        k: newK,
        x: midX - (midX - prev.x) * (newK / prev.k),
        y: midY - (midY - prev.y) * (newK / prev.k),
      };
    });
  };

  const handleFitToScreen = () => {
    setTransform(defaultTransform);
  };

  const handleReset = () => {
    runLayout();
  };

  // Connected direct neighbors for inspected node
  const neighborList = useMemo(() => {
    if (!activeInspectedNode) return [];
    const directSet = new Map();

    links.forEach((l) => {
      const srcId = typeof l.source === 'object' ? l.source.id : l.source;
      const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
      if (srcId === activeInspectedNode.id) {
        const other = nodes.find((n) => n.id === tgtId);
        if (other) directSet.set(other.id, { node: other, type: l.type });
      } else if (tgtId === activeInspectedNode.id) {
        const other = nodes.find((n) => n.id === srcId);
        if (other) directSet.set(other.id, { node: other, type: l.type });
      }
    });

    return Array.from(directSet.values());
  }, [activeInspectedNode, links, nodes]);

  return (
    <div
      ref={containerRef}
      className="flex flex-col border border-[#E2E0D8] rounded-xl bg-[#F3F1EB] overflow-hidden select-none font-sans"
    >
      {/* ----------------------------------------------------------------- */}
      {/* 1. TOP CONTROLS & LAYOUT TOOLBAR (Dedicated Strip, Zero Overlap)  */}
      {/* ----------------------------------------------------------------- */}
      <div className="flex flex-wrap items-center justify-between px-3 py-1.5 border-b border-[#E2E0D8] bg-white gap-2 z-10">
        {/* Left: Relationship Filter Pills (or subtle title when hideEdgeFilter is true) */}
        {!hideEdgeFilter ? (
          <div className="flex flex-wrap items-center gap-1.5 bg-[#F7F6F2] border border-[#E2E0D8] px-2 py-0.5 rounded-lg text-[10px]">
            <span className="text-[#9BA09D] uppercase flex items-center gap-1 mr-1">
              <Filter className="w-3 h-3 text-[#737A76]" />
              Edge:
            </span>
            <button
              onClick={() => setFilterType('ALL')}
              className={`px-2 py-0.5 rounded transition-all font-semibold ${
                filterType === 'ALL'
                  ? 'bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/30'
                  : 'text-[#737A76] hover:text-[#252B29]'
              }`}
            >
              All ({links.length})
            </button>
            {availableRelTypes.map((t) => (
              <button
                key={t}
                onClick={() => setFilterType(t)}
                className={`px-2 py-0.5 rounded transition-all ${
                  filterType === t
                    ? 'bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/30 font-bold'
                    : 'text-[#737A76] hover:text-[#252B29]'
                }`}
              >
                {t.replace('SHARED_', '').replace('_', ' ')}
              </button>
            ))}
            <span className="text-[9px] text-[#9BA09D] ml-1 pl-1 border-l border-[#E2E0D8]">
              Showing {filteredLinks.length} of {links.length}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs font-semibold text-[#3D4543]">
            <Layers className="w-3.5 h-3.5 text-[#147D69]" />
            <span>Investigation Topology</span>
          </div>
        )}

        {/* Right: Layout Switcher & Zoom/Action Buttons */}
        <div className="flex items-center gap-1.5 bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg p-0.5 shadow-sm">
          {/* Deterministic Bipartite / Force Physics Switcher */}
          <div className="flex items-center bg-white border border-[#E2E0D8] rounded p-0.5 text-[10px] mr-1">
            <button
              onClick={() => setLayoutMode('bipartite')}
              className={`px-2 py-0.5 rounded transition-all ${
                layoutMode === 'bipartite'
                  ? 'bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/30 font-bold'
                  : 'text-[#737A76] hover:text-[#252B29]'
              }`}
              title="Deterministic Layered Bipartite Layout"
            >
              Layered
            </button>
            <button
              onClick={() => setLayoutMode('force')}
              className={`px-2 py-0.5 rounded transition-all ${
                layoutMode === 'force'
                  ? 'bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/30 font-bold'
                  : 'text-[#737A76] hover:text-[#252B29]'
              }`}
              title="Force-Directed Physics Layout"
            >
              Force
            </button>
          </div>

          <button
            onClick={() => setShowAllLabels(!showAllLabels)}
            title={showAllLabels ? 'Hide Inactive Labels' : 'Reveal All Labels'}
            className={`p-1.5 rounded transition-colors ${
              showAllLabels
                ? 'text-[#147D69] bg-[#147D69]/10'
                : 'text-[#737A76] hover:bg-[#F3F1EB]'
            }`}
          >
            {showAllLabels ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={() => handleZoom(1.25)}
            title="Zoom In"
            className="p-1.5 text-[#737A76] hover:text-[#252B29] hover:bg-[#F3F1EB] rounded transition-colors"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => handleZoom(0.8)}
            title="Zoom Out"
            className="p-1.5 text-[#737A76] hover:text-[#252B29] hover:bg-[#F3F1EB] rounded transition-colors"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleFitToScreen}
            title="Fit to Screen"
            className="p-1.5 text-[#737A76] hover:text-[#252B29] hover:bg-[#F3F1EB] rounded transition-colors"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleReset}
            title="Reset Layout"
            className="p-1.5 text-[#737A76] hover:text-[#252B29] hover:bg-[#F3F1EB] rounded transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* 2. CANVAS VIEWPORT (100% UNOBSTRUCTED)                            */}
      {/* ----------------------------------------------------------------- */}
      <div className="relative w-full overflow-hidden">
        {/* Interactive Canvas */}
        <canvas
          ref={canvasRef}
          style={{
            width: '100%',
            height: `${canvasHeight}px`,
            cursor: isDragging ? 'grabbing' : 'grab',
          }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onClick={handleClick}
        />

        {/* Floating Hover Tooltip */}
        {hoveredNode && !isDragging && (
          <div
            className={`pointer-events-none absolute z-30 bg-white/95 backdrop-blur-sm border border-[#147D69]/40 rounded-lg px-3 py-2 shadow text-xs space-y-1 transform transition-opacity duration-150 ${
              mousePos.y < 90 ? 'translate-y-3' : '-translate-y-full -translate-y-3'
            } ${
              mousePos.x < 130
                ? 'translate-x-3'
                : mousePos.x > (containerRef.current?.clientWidth || 600) - 130
                ? '-translate-x-full -translate-x-3'
                : '-translate-x-1/2'
            }`}
            style={{
              left: `${mousePos.x}px`,
              top: `${mousePos.y}px`,
            }}
          >
            <div className="flex items-center gap-1.5">
              {hoveredNode.type === 'account' && <Shield className="w-3.5 h-3.5 text-[#147D69]" />}
              {hoveredNode.type === 'device' && <Smartphone className="w-3.5 h-3.5 text-[#7C6EAF]" />}
              {hoveredNode.type === 'ip' && <Globe className="w-3.5 h-3.5 text-[#4E9BB5]" />}
              {hoveredNode.type === 'destination' && <Target className="w-3.5 h-3.5 text-[#D58A27]" />}
              <span className="font-bold text-[#252B29] text-[11px] font-mono">{hoveredNode.id}</span>
              <span className="text-[9px] px-1 py-0.2 rounded bg-[#F3F1EB] text-[#3D4543] font-semibold uppercase font-mono">
                {hoveredNode.type}
              </span>
            </div>

            {hoveredNode.type === 'account' ? (
              <div className="space-y-0.5 text-[10px] font-mono text-[#3D4543]">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[#737A76]">P(Abuse):</span>
                  <span
                    className={`font-bold ${
                      (hoveredNode.risk_score || 0) >= 70
                        ? 'text-[#C64B43]'
                        : (hoveredNode.risk_score || 0) >= 35
                        ? 'text-[#D58A27]'
                        : 'text-[#737A76]'
                    }`}
                  >
                    {hoveredNode.probability != null
                      ? hoveredNode.probability.toFixed(4)
                      : hoveredNode.risk_score != null
                      ? (hoveredNode.risk_score / 100).toFixed(4)
                      : '0.2500'}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[#737A76]">Decision Tier:</span>
                  <span
                    className={`font-bold ${
                      (hoveredNode.risk_score || 0) >= 70
                        ? 'text-[#C64B43]'
                        : (hoveredNode.risk_score || 0) >= 35
                        ? 'text-[#D58A27]'
                        : 'text-[#737A76]'
                    }`}
                  >
                    {(hoveredNode.risk_score || 0) >= 70
                      ? 'CRITICAL (P ≥ 0.70)'
                      : (hoveredNode.risk_score || 0) >= 35
                      ? 'HIGH (P ≥ 0.35)'
                      : 'BELOW THRESHOLD'}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3 text-[#737A76] pt-0.5 border-t border-[#E2E0D8]">
                  <span>Connected Hubs:</span>
                  <span className="text-[#147D69] font-bold">
                    {links.filter(l => (typeof l.source === 'object' ? l.source.id : l.source) === hoveredNode.id || (typeof l.target === 'object' ? l.target.id : l.target) === hoveredNode.id).length} links
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-[10px] font-mono text-[#3D4543] flex items-center justify-between gap-3">
                <span className="text-[#737A76]">Cluster Connections:</span>
                <span className="text-[#147D69] font-bold">
                  {links.filter(l => (typeof l.source === 'object' ? l.source.id : l.source) === hoveredNode.id || (typeof l.target === 'object' ? l.target.id : l.target) === hoveredNode.id).length} accounts
                </span>
              </div>
            )}
          </div>
        )}

        {/* Bottom Legend */}
        <div className="absolute bottom-2.5 left-3 right-3 flex items-center justify-between pointer-events-none text-[10px]">
          <div className="flex flex-wrap items-center gap-3 bg-white/90 backdrop-blur-sm border border-[#E2E0D8] px-3 py-1 rounded-lg pointer-events-auto shadow-sm">
            <div className="flex items-center gap-1 text-[#3D4543]">
              <span className="w-2.5 h-2.5 rounded-full bg-[#C64B43] inline-block" />
              <span>Critical (P &ge; 0.70)</span>
            </div>
            <div className="flex items-center gap-1 text-[#3D4543]">
              <span className="w-2.5 h-2.5 rounded-full bg-[#D58A27] inline-block" />
              <span>High (P &ge; 0.35)</span>
            </div>
            <div className="flex items-center gap-1 text-[#3D4543]">
              <span className="w-2.5 h-2.5 rounded-full bg-[#78858A] inline-block" />
              <span>Low (P &lt; 0.35)</span>
            </div>
            <div className="flex items-center gap-1 text-[#3D4543]">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#7C6EAF] inline-block" />
              <span>Device</span>
            </div>
            <div className="flex items-center gap-1 text-[#3D4543]">
              <span className="w-2 h-2 rotate-45 bg-[#4E9BB5] inline-block" />
              <span>IP</span>
            </div>
            <div className="flex items-center gap-1 text-[#3D4543]">
              <span className="w-2.5 h-2.5 bg-[#D58A27] inline-block rounded-xs" />
              <span>Destination</span>
            </div>

            <div className="w-px h-3 bg-[#E2E0D8]" />

            <div className="flex items-center gap-1.5 text-[#737A76]">
              <span className="w-3 h-0.5 border-t border-dashed border-[#D58A27] inline-block" />
              <span>Destination</span>
            </div>
            <div className="flex items-center gap-1.5 text-[#737A76]">
              <span className="w-3 h-0.5 bg-[#7C6EAF] inline-block" />
              <span>Device</span>
            </div>
            <div className="flex items-center gap-1.5 text-[#737A76]">
              <span className="w-3 h-0.5 bg-[#4E9BB5] inline-block" />
              <span>IP</span>
            </div>
            <div className="flex items-center gap-1.5 text-[#737A76]">
              <span className="w-3 h-0.5 border-t border-dotted border-[#C64B43] inline-block" />
              <span>Timing</span>
            </div>
          </div>

          <div className="text-[9px] text-[#9BA09D] bg-[#F3F1EB]/80 px-2 py-0.5 rounded border border-[#E2E0D8]">
            Hover to view label • Click to select
          </div>
        </div>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* 2. DEDICATED INSPECTOR DOCK (OUTSIDE THE GRAPH CANVAS)            */}
      {/* ----------------------------------------------------------------- */}
      {inspectorOpen && activeInspectedNode && (
        <div className="border-t border-[#E2E0D8] bg-white p-3 text-xs flex flex-col md:flex-row md:items-center justify-between gap-3 animate-in fade-in slide-in-from-top-1 duration-150">
          {/* Node Meta Left */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              {activeInspectedNode.type === 'account' && (
                <div className="p-1.5 rounded-lg bg-[#147D69]/10 border border-[#147D69]/25 text-[#147D69]">
                  <Shield className="w-4 h-4" />
                </div>
              )}
              {activeInspectedNode.type === 'device' && (
                <div className="p-1.5 rounded-lg bg-[#7C6EAF]/10 border border-[#7C6EAF]/25 text-[#7C6EAF]">
                  <Smartphone className="w-4 h-4" />
                </div>
              )}
              {activeInspectedNode.type === 'ip' && (
                <div className="p-1.5 rounded-lg bg-[#4E9BB5]/10 border border-[#4E9BB5]/25 text-[#4E9BB5]">
                  <Globe className="w-4 h-4" />
                </div>
              )}
              {activeInspectedNode.type === 'destination' && (
                <div className="p-1.5 rounded-lg bg-[#D58A27]/10 border border-[#D58A27]/25 text-[#D58A27]">
                  <Target className="w-4 h-4" />
                </div>
              )}
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-[#252B29] text-xs">{activeInspectedNode.id}</span>
                  <span className="text-[9px] uppercase px-1.5 py-0.2 rounded bg-[#F3F1EB] text-[#3D4543] font-bold">
                    {activeInspectedNode.type}
                  </span>
                  {activeInspectedNode.isFocal && (
                    <span className="text-[9px] uppercase px-1.5 py-0.2 rounded bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/25 font-bold">
                      Focal Account
                    </span>
                  )}
                </div>
                {activeInspectedNode.type === 'account' ? (
                  <div className="text-[10px] text-[#737A76] mt-0.5">
                    Risk Score:{' '}
                    <span
                      className={`font-bold ${
                        (activeInspectedNode.risk_score || 0) >= 70
                          ? 'text-[#C64B43]'
                          : (activeInspectedNode.risk_score || 0) >= 35
                          ? 'text-[#D58A27]'
                          : 'text-[#147D69]'
                      }`}
                    >
                      {activeInspectedNode.risk_score != null
                        ? `${activeInspectedNode.risk_score.toFixed(1)} / 100`
                        : 'Unrated'}
                    </span>
                  </div>
                ) : (
                  <div className="text-[10px] text-[#737A76] mt-0.5">
                    Shared infrastructure node linking ring members
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Direct Neighbors Pills Middle */}
          {neighborList.length > 0 && (
            <div className="flex items-center gap-2 overflow-x-auto py-1 max-w-xl">
              <span className="text-[10px] text-[#737A76] uppercase tracking-wider shrink-0">
                Connected ({neighborList.length}):
              </span>
              <div className="flex items-center gap-1.5">
                {neighborList.slice(0, 8).map(({ node: nbr, type: nbrType }) => (
                  <button
                    key={nbr.id}
                    onClick={() => {
                      setInternalSelectedId(nbr.id);
                      setInspectorOpen(true);
                      if (onSelectNode) onSelectNode(nbr);
                    }}
                    className="px-2 py-0.5 rounded bg-[#F7F6F2] hover:bg-[#F3F1EB] border border-[#E2E0D8] text-[10px] text-[#3D4543] hover:text-[#147D69] transition-colors shrink-0 flex items-center gap-1 cursor-pointer"
                  >
                    <span>{nbr.id}</span>
                    <span className="text-[8px] text-[#9BA09D] uppercase">{nbr.type}</span>
                  </button>
                ))}
                {neighborList.length > 8 && (
                  <span className="text-[10px] text-[#9BA09D]">+{neighborList.length - 8} more</span>
                )}
              </div>
            </div>
          )}

          {/* Close & Action Right */}
          <div className="flex items-center gap-2 shrink-0">
            {activeInspectedNode.type === 'account' && !activeInspectedNode.isFocal && onInspectAccount && (
              <button
                onClick={() => onInspectAccount(activeInspectedNode.id)}
                className="px-2.5 py-1 rounded bg-[#147D69]/10 hover:bg-[#147D69]/20 text-[#147D69] border border-[#147D69]/30 text-[10px] font-bold font-mono flex items-center gap-1.5 transition-colors cursor-pointer"
                title={`Investigate account ${activeInspectedNode.id}`}
              >
                <span>Deep Dive</span>
                <ChevronRight className="w-3 h-3" />
              </button>
            )}
            <button
              onClick={() => {
                setInspectorOpen(false);
                setInternalSelectedId(null);
                if (onSelectNode) onSelectNode(null);
              }}
              className="p-1 rounded bg-[#F7F6F2] hover:bg-[#F3F1EB] text-[#737A76] hover:text-[#252B29] border border-[#E2E0D8] transition-colors cursor-pointer"
              title="Close Inspector"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
