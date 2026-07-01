import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  EdgeLabelRenderer,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  forceX,
  forceY,
} from 'd3-force';
import CandidateNode from './CandidateNode';
import './App.css';

const nodeTypes = { candidate: CandidateNode };

function processGraphData(rawData) {
  const nodeSet = new Set();
  const linkMap = new Map();

  Object.entries(rawData).forEach(([source, connections]) => {
    nodeSet.add(source);
    connections.forEach(([target, weight]) => {
      nodeSet.add(target);
      const key = [source, target].sort().join('|');
      if (!linkMap.has(key)) {
        linkMap.set(key, { source, target, weight });
      } else {
        const existing = linkMap.get(key);
        existing.weight = Math.max(existing.weight, weight);
      }
    });
  });

  const connectionCounts = {};
  nodeSet.forEach((n) => (connectionCounts[n] = 0));
  linkMap.forEach((link) => {
    connectionCounts[link.source] = (connectionCounts[link.source] || 0) + 1;
    connectionCounts[link.target] = (connectionCounts[link.target] || 0) + 1;
  });

  const allWeights = Array.from(linkMap.values()).map((l) => l.weight);
  const minWeight = Math.min(...allWeights);
  const maxWeight = Math.max(...allWeights);

  // Build adjacency map for quick neighbor lookup
  const adjacency = {};
  nodeSet.forEach((n) => (adjacency[n] = new Set()));
  linkMap.forEach((link) => {
    adjacency[link.source].add(link.target);
    adjacency[link.target].add(link.source);
  });

  return {
    nodeIds: Array.from(nodeSet),
    links: Array.from(linkMap.values()),
    connectionCounts,
    minWeight,
    maxWeight,
    rawData,
    adjacency,
  };
}

function runForceLayout(nodeIds, links, connectionCounts) {
  const simNodes = nodeIds.map((id) => ({ id }));
  const simLinks = links.map((l) => ({
    source: l.source,
    target: l.target,
    weight: l.weight,
  }));

  const simulation = forceSimulation(simNodes)
    .force(
      'link',
      forceLink(simLinks)
        .id((d) => d.id)
        .distance((d) => 220 * (1.3 - d.weight))
        .strength((d) => d.weight * 0.5)
    )
    .force('charge', forceManyBody().strength(-600))
    .force('center', forceCenter(0, 0))
    .force(
      'collision',
      forceCollide().radius((d) => {
        const count = connectionCounts[d.id] || 1;
        return 28 + Math.sqrt(count) * 12;
      })
    )
    .force('x', forceX(0).strength(0.05))
    .force('y', forceY(0).strength(0.05))
    .stop();

  for (let i = 0; i < 300; i++) {
    simulation.tick();
  }

  const positions = {};
  simNodes.forEach((n) => {
    positions[n.id] = { x: n.x, y: n.y };
  });
  return positions;
}

function GraphViz() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [graphInfo, setGraphInfo] = useState(null);
  const [threshold, setThreshold] = useState(0.29);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [loading, setLoading] = useState(true);
  const { fitView } = useReactFlow();

  // Load data once
  useEffect(() => {
    fetch('/graphical_representation.json')
      .then((r) => r.json())
      .then((rawData) => {
        const info = processGraphData(rawData);
        const positions = runForceLayout(
          info.nodeIds,
          info.links,
          info.connectionCounts
        );

        const maxConn = Math.max(...Object.values(info.connectionCounts));
        const rfNodes = info.nodeIds.map((id) => {
          const conn = info.connectionCounts[id] || 1;
          const size = 30 + (conn / maxConn) * 60;
          const isSource = info.rawData.hasOwnProperty(id);
          return {
            id,
            type: 'candidate',
            position: { x: positions[id].x, y: positions[id].y },
            data: {
              label: id.replace('CAND_00', '').replace('CAND_0', ''),
              fullLabel: id,
              connections: conn,
              size,
              isSource,
              highlighted: false,
              dimmed: false,
              selected: false,
            },
          };
        });

        setGraphInfo(info);
        setNodes(rfNodes);
        setLoading(false);
        setTimeout(() => fitView({ padding: 0.15 }), 100);
      });
  }, []);

  // Update node highlight states when selection changes
  useEffect(() => {
    if (!graphInfo) return;

    setNodes((nds) =>
      nds.map((node) => {
        if (!selectedNodeId) {
          return {
            ...node,
            data: {
              ...node.data,
              highlighted: false,
              dimmed: false,
              selected: false,
            },
          };
        }

        const isSelected = node.id === selectedNodeId;
        const isNeighbor = graphInfo.adjacency[selectedNodeId]?.has(node.id);
        return {
          ...node,
          data: {
            ...node.data,
            selected: isSelected,
            highlighted: isNeighbor,
            dimmed: !isSelected && !isNeighbor,
          },
        };
      })
    );
  }, [selectedNodeId, graphInfo]);

  // Update edges when threshold or selection changes
  useEffect(() => {
    if (!graphInfo) return;

    const { links, maxWeight } = graphInfo;
    const filteredLinks = links.filter((l) => l.weight >= threshold);

    const rfEdges = filteredLinks.map((link) => {
      const percent = Math.round((link.weight / maxWeight) * 100);
      const normalized = link.weight / maxWeight; // 0 → 1

      // Width scales with weight: thin for weak, thick for strong
      const width = 1 + normalized * 5;

      // Determine if this edge is connected to selected node
      const isConnectedToSelected =
        selectedNodeId &&
        (link.source === selectedNodeId || link.target === selectedNodeId);
      const isUnrelated = selectedNodeId && !isConnectedToSelected;

      // Color & opacity based on selection state
      let strokeColor, strokeOpacity;
      if (isConnectedToSelected) {
        // Highlighted edge: vivid teal, full opacity
        const r = Math.round(20 + normalized * 30);
        const g = Math.round(140 + normalized * 60);
        const b = Math.round(140 + normalized * 60);
        strokeColor = `rgb(${r}, ${g}, ${b})`;
        strokeOpacity = 0.7 + normalized * 0.3;
      } else if (isUnrelated) {
        // Dimmed edge
        strokeColor = `rgba(150, 180, 180, 0.08)`;
        strokeOpacity = 0.08;
      } else {
        // Default state
        const r = Math.round(50 + normalized * 30);
        const g = Math.round(140 + normalized * 50);
        const b = Math.round(140 + normalized * 50);
        strokeColor = `rgb(${r}, ${g}, ${b})`;
        strokeOpacity = 0.15 + normalized * 0.55;
      }

      return {
        id: `${link.source}-${link.target}`,
        source: link.source,
        target: link.target,
        type: 'default',
        data: { weight: link.weight, percent },
        style: {
          stroke: strokeColor,
          strokeWidth: isConnectedToSelected ? width * 1.5 : width,
          opacity: strokeOpacity,
        },
        label: isConnectedToSelected ? `${percent}%` : undefined,
        labelStyle: isConnectedToSelected
          ? {
              fontSize: 10,
              fontWeight: 700,
              fontFamily: "'JetBrains Mono', monospace",
              fill: '#2a6060',
            }
          : undefined,
        labelBgStyle: isConnectedToSelected
          ? {
              fill: 'rgba(255,255,255,0.85)',
              fillOpacity: 0.85,
            }
          : undefined,
        labelBgPadding: [4, 6],
        labelBgBorderRadius: 4,
        animated: false,
      };
    });

    setEdges(rfEdges);
  }, [graphInfo, threshold, selectedNodeId]);

  // Handle node click
  const onNodeClick = useCallback((event, node) => {
    setSelectedNodeId((prev) => (prev === node.id ? null : node.id));
  }, []);

  // Handle pane click (deselect)
  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  const edgeCount = edges.length;
  const nodeCount = nodes.length;

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
        <p>Computing force layout...</p>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Filter Panel */}
      <div className="filter-panel">
        <div className="filter-title">Weight Filter</div>
        <div className="filter-row">
          <input
            type="range"
            min={graphInfo.minWeight}
            max={graphInfo.maxWeight}
            step="0.005"
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            className="threshold-slider"
          />
          <span className="threshold-val">{threshold.toFixed(3)}</span>
        </div>
        <div className="filter-stats">
          <span>{nodeCount} nodes</span>
          <span>·</span>
          <span>{edgeCount} edges</span>
        </div>
        {selectedNodeId && (
          <div className="selected-info">
            <div className="selected-label">Selected</div>
            <div className="selected-id">{selectedNodeId}</div>
            <div className="selected-hint">
              {graphInfo.adjacency[selectedNodeId]?.size} connections shown ·
              click node or background to deselect
            </div>
          </div>
        )}
      </div>

      {/* Similarity Legend */}
      <div className="similarity-legend">
        <div className="legend-title">Similarity</div>
        <div className="legend-scale">
          <div className="legend-bar" />
          <div className="legend-labels">
            <span>0%</span>
            <span>50%</span>
            <span>100%</span>
          </div>
        </div>
        <div className="legend-note">
          100% = {graphInfo.maxWeight.toFixed(4)} (max observed)
        </div>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        maxZoom={4}
        defaultEdgeOptions={{ type: 'default' }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#d5dfe0" gap={40} size={1} />
        <Controls position="bottom-right" showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <GraphViz />
    </ReactFlowProvider>
  );
}
