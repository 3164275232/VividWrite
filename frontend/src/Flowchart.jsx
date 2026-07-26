import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Plus, RotateCcw, Trash2 } from 'lucide-react';

const TYPE_STYLES = {
  introduction: {
    color: '#fff7df',
    border: '#a76609',
    title: 'Introduction / Orient the Visual',
    defaultText: 'Paraphrase the task and identify what the visual presents.',
  },
  overview: {
    color: '#eaf7ef',
    border: '#247047',
    title: 'Overview / Highlight Key Patterns',
    defaultText: 'Summarize the most important trends, contrasts, or overall features.',
  },
  key_details_a: {
    color: '#eaf3ff',
    border: '#2f67a8',
    title: 'Key Details A / Report & Compare',
    defaultText: 'Report and compare the first logically grouped set of data.',
  },
  key_details_b: {
    color: '#fff0f2',
    border: '#a9475a',
    title: 'Key Details B / Report & Compare',
    defaultText: 'Report and compare the second logically grouped set of data.',
  },
  optional_commentary: {
    color: '#f3f0f8',
    border: '#71558f',
    title: 'Optional Commentary / Interpret',
    defaultText: 'Interpret only when supported by the task or visual; do not invent causes or conclusions.',
    optional: true,
  },
  custom: {
    color: '#f3f4f6',
    border: '#5f6368',
    title: 'Custom Structure Node',
    defaultText: 'Rename this node to describe its role in your writing plan.',
  },
};

const initialNodes = [
  {
    id: 'introduction', type: 'introduction', x: 205, y: 20, width: 230, height: 84,
    ...TYPE_STYLES.introduction,
    text: TYPE_STYLES.introduction.defaultText,
  },
  {
    id: 'overview', type: 'overview', x: 205, y: 125, width: 230, height: 84,
    ...TYPE_STYLES.overview,
    text: TYPE_STYLES.overview.defaultText,
  },
  {
    id: 'key_details_a', type: 'key_details_a', x: 205, y: 230, width: 230, height: 84,
    ...TYPE_STYLES.key_details_a,
    text: TYPE_STYLES.key_details_a.defaultText,
  },
  {
    id: 'key_details_b', type: 'key_details_b', x: 205, y: 335, width: 230, height: 84,
    ...TYPE_STYLES.key_details_b,
    text: TYPE_STYLES.key_details_b.defaultText,
  },
  {
    id: 'optional_commentary', type: 'optional_commentary', x: 205, y: 440, width: 230, height: 92,
    ...TYPE_STYLES.optional_commentary,
    text: TYPE_STYLES.optional_commentary.defaultText,
  },
];

const initialEdges = [
  { id: 'e1', from: 'introduction', to: 'overview', type: 'sequence' },
  { id: 'e2', from: 'overview', to: 'key_details_a', type: 'sequence' },
  { id: 'e3', from: 'key_details_a', to: 'key_details_b', type: 'sequence' },
  { id: 'e4', from: 'key_details_b', to: 'optional_commentary', type: 'sequence' },
];

export default function Flowchart({ imageReady = false, onFlowchartChange, onNodeClick, missingNodeIds = new Set(), nodeSentenceCounts = {}, nodeParagraphCounts = {}, readOnly = false, currentStage = 'planning' }) {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState(null);
  const [creatingEdge, setCreatingEdge] = useState(null); // { fromNodeId, startX, startY, currentX, currentY }
  const [newNodeType, setNewNodeType] = useState('introduction');

  const canvasRef = useRef(null);
  const dragInfoRef = useRef(null); // { id, offsetX, offsetY }

  const getNodeById = (id) => nodes.find(n => n.id === id);

  const handleMouseDownNode = (e, node) => {
    e.stopPropagation();
    const rect = canvasRef.current.getBoundingClientRect();
    dragInfoRef.current = {
      id: node.id,
      offsetX: e.clientX - rect.left - node.x,
      offsetY: e.clientY - rect.top - node.y
    };
    setSelectedNodeId(node.id);
    setSelectedEdgeId(null);
  };

  const handleMouseMove = (e) => {
    if (!canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();

    if (dragInfoRef.current) {
      const { id, offsetX, offsetY } = dragInfoRef.current;
      const newX = e.clientX - rect.left - offsetX;
      const newY = e.clientY - rect.top - offsetY;
      setNodes(prev => prev.map(n => n.id === id ? { ...n, x: Math.max(0, newX), y: Math.max(0, newY) } : n));
      return;
    }

    if (creatingEdge) {
      setCreatingEdge(prev => prev ? { ...prev, currentX: e.clientX - rect.left, currentY: e.clientY - rect.top } : null);
    }
  };

  const handleMouseUp = () => {
    dragInfoRef.current = null;
    if (creatingEdge) setCreatingEdge(null);
  };

  const addNode = () => {
    if (!imageReady || readOnly) return;
    const style = TYPE_STYLES[newNodeType];
    const existingCount = nodes.filter(n => n.type === newNodeType).length;
    const computedTitle = existingCount > 0
      ? `${style.title} ${existingCount + 1}`
      : style.title;
    const baseY = nodes.length ? Math.max(...nodes.map(n => n.y + n.height)) + 40 : 30;
    const x = 320;
    const id = 'node_' + Math.random().toString(36).slice(2, 8);
    
    const newNode = {
      id,
      type: newNodeType,
      x: x - 80,
      y: baseY,
      width: 160,
      height: 72,
      title: computedTitle,
      text: style.defaultText,
      color: style.color,
      border: style.border,
      optional: Boolean(style.optional),
    };

    setNodes(prev => [...prev, newNode]);
  };

  const startEdgeCreation = (e, node) => {
    if (!imageReady || readOnly) return;
    e.stopPropagation();
    const rect = canvasRef.current.getBoundingClientRect();
    setCreatingEdge({
      fromNodeId: node.id,
      startX: node.x + node.width / 2,
      startY: node.y + node.height / 2,
      currentX: e.clientX - rect.left,
      currentY: e.clientY - rect.top
    });
  };

  const handleMouseUpCanvas = (e) => {
    if (!creatingEdge) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const target = [...nodes].reverse().find(n => x >= n.x && x <= n.x + n.width && y >= n.y && y <= n.y + n.height);
    if (target && target.id !== creatingEdge.fromNodeId) {
      const duplicate = edges.some(ed => ed.from === creatingEdge.fromNodeId && ed.to === target.id);
      if (!duplicate) {
        const id = 'e_' + Math.random().toString(36).slice(2, 8);
        setEdges(prev => [...prev, {
          id,
          from: creatingEdge.fromNodeId,
          to: target.id,
          type: 'sequence',
        }]);
      }
    }
    setCreatingEdge(null);
  };

  const deleteSelectedNode = useCallback(() => {
    if (readOnly) return;
    if (!selectedNodeId) return;
    setEdges(prev => prev.filter(e => e.from !== selectedNodeId && e.to !== selectedNodeId));
    setNodes(prev => prev.filter(n => n.id !== selectedNodeId));
    setSelectedNodeId(null);
  }, [selectedNodeId, readOnly]);

  const deleteSelectedEdge = useCallback(() => {
    if (readOnly) return;
    if (!selectedEdgeId) return;
    setEdges(prev => prev.filter(e => e.id !== selectedEdgeId));
    setSelectedEdgeId(null);
  }, [selectedEdgeId, readOnly]);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key !== 'Delete' && event.key !== 'Backspace') return;
      if (selectedNodeId) {
        deleteSelectedNode();
      } else if (selectedEdgeId) {
        deleteSelectedEdge();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedNodeId, selectedEdgeId, deleteSelectedNode, deleteSelectedEdge]);

  const unifiedDelete = () => {
    if (readOnly) return;
    if (selectedNodeId) {
      deleteSelectedNode();
    } else if (selectedEdgeId) {
      deleteSelectedEdge();
    }
  };

  const resetChart = () => {
    if (!imageReady || readOnly) return;
    setNodes(initialNodes);
    setEdges(initialEdges);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  };

  const updateNodeTitle = (id, title) => {
    if (readOnly) return;
    setNodes(prev => prev.map(n => n.id === id ? { ...n, title } : n));
  };

  const renderEdges = () => {
    return edges.map(edge => {
      const from = getNodeById(edge.from);
      const to = getNodeById(edge.to);
      if (!from || !to) return null;
      const x1 = from.x + from.width / 2;
      const y1 = from.y + from.height / 2;
      const x2 = to.x + to.width / 2;
      const y2 = to.y + to.height / 2;
      const midX = (x1 + x2) / 2;
      const midY = (y1 + y2) / 2;
      const isSelected = edge.id === selectedEdgeId;
      
      const strokeColor = isSelected ? '#0a66d8' : '#77777c';
      const strokeWidth = isSelected ? 3 : 2;
      
      return (
        <g key={edge.id} style={{ cursor: 'pointer' }}>
          <path
            d={`M ${x1} ${y1} Q ${midX} ${midY} ${x2} ${y2}`}
            stroke="#000"
            strokeOpacity={0}
            strokeWidth={16}
            fill="none"
            pointerEvents="stroke"
            onMouseDown={(e) => { e.stopPropagation(); setSelectedEdgeId(edge.id); setSelectedNodeId(null); }}
          />
          <path
            d={`M ${x1} ${y1} Q ${midX} ${midY} ${x2} ${y2}`}
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            fill="none"
            markerEnd="url(#arrow)"
            onMouseDown={(e) => { e.stopPropagation(); setSelectedEdgeId(edge.id); setSelectedNodeId(null); }}
          />
          {isSelected && (
            <path
              d={`M ${x1} ${y1} Q ${midX} ${midY} ${x2} ${y2}`}
              stroke="#0a66d8"
              strokeWidth={10}
              strokeOpacity={0.15}
              fill="none"
              pointerEvents="none"
            />
          )}
        </g>
      );
    });
  };

  const tempEdge = creatingEdge ? (
    <line x1={creatingEdge.startX} y1={creatingEdge.startY} x2={creatingEdge.currentX} y2={creatingEdge.currentY} stroke="#999" strokeDasharray="4 4" strokeWidth={2} />
  ) : null;

  // Initialize nodes/edges only once when image becomes ready
  useEffect(() => {
    if (imageReady && nodes.length === 0 && edges.length === 0) {
      setNodes(initialNodes);
      setEdges(initialEdges);
    }
  }, [imageReady, nodes.length, edges.length]);

  // Notify parent when nodes or edges change (after ready)
  useEffect(() => {
    if (!imageReady) return;
    if (typeof onFlowchartChange === 'function') {
      onFlowchartChange({
        nodes: nodes.map(n => ({ id: n.id, type: n.type, title: n.title, text: n.text, x: n.x, y: n.y, width: n.width, height: n.height, optional: Boolean(n.optional) })),
        edges: edges.map(e => ({ id: e.id, from: e.from, to: e.to, type: e.type || 'sequence' }))
      });
    }
  }, [nodes, edges, imageReady, onFlowchartChange]);

  const editingDisabled = !imageReady || readOnly;

  return (
    <div className="flowchart-root" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="flowchart-toolbar" style={{ marginBottom: '0.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
  <button title="Reset structure" onClick={resetChart} disabled={editingDisabled} style={{ padding: '0.4rem 0.8rem', cursor: editingDisabled ? 'not-allowed' : 'pointer', opacity: editingDisabled ? 0.5 : 1 }}><RotateCcw size={14} /> Reset</button>
  <button title="Delete selected item" onClick={unifiedDelete} disabled={editingDisabled || (!selectedNodeId && !selectedEdgeId)} style={{ padding: '0.4rem 0.8rem', cursor: (!editingDisabled && (selectedNodeId || selectedEdgeId)) ? 'pointer' : 'not-allowed', opacity: (!editingDisabled && (selectedNodeId || selectedEdgeId)) ? 1 : 0.5 }}><Trash2 size={14} /> Delete</button>
  <button title="Add a structure node" onClick={addNode} disabled={editingDisabled} style={{ padding: '0.4rem 0.8rem', cursor: editingDisabled ? 'not-allowed' : 'pointer', opacity: editingDisabled ? 0.5 : 1 }}><Plus size={14} /> Add node</button>
        <label style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 4 }}>
          New node type:
          <select value={newNodeType} onChange={(e) => setNewNodeType(e.target.value)} style={{ fontSize: '0.75rem' }} disabled={editingDisabled}>
            <option value="introduction">Introduction / Orient the Visual</option>
            <option value="overview">Overview / Highlight Key Patterns</option>
            <option value="key_details_a">Key Details A / Report & Compare</option>
            <option value="key_details_b">Key Details B / Report & Compare</option>
            <option value="optional_commentary">Optional Commentary / Interpret</option>
            <option value="custom">Custom Structure Node</option>
          </select>
        </label>
        <span className="flowchart-status" style={{ fontSize: '0.7rem', color: '#555', lineHeight: 1.2 }}>
          {editingDisabled ? (readOnly ? 'Read-only view (revision stage): node editing disabled' : 'Please upload an image first (Flowchart disabled until image uploaded)') : 'Task 1 structure: Introduction -> Overview -> Key Details A -> Key Details B -> Optional Commentary | Drag nodes to move or link'}
        </span>
      </div>

      <div
        className="flowchart-canvas"
        ref={canvasRef}
        onMouseMove={editingDisabled ? undefined : handleMouseMove}
        onMouseUp={editingDisabled ? undefined : (e) => { handleMouseUp(); handleMouseUpCanvas(e); }}
        onMouseLeave={editingDisabled ? undefined : handleMouseUp}
        style={{
          position: 'relative',
          flex: 1,
          background: '#f8f8fa',
          border: '1px solid #ddd',
          borderRadius: 8,
          overflow: 'auto',
          userSelect: 'none',
          cursor: editingDisabled ? 'not-allowed' : (dragInfoRef.current ? 'grabbing' : creatingEdge ? 'crosshair' : 'default'),
          filter: editingDisabled && !readOnly ? 'grayscale(0.4) brightness(0.95)' : 'none',
          opacity: editingDisabled && !readOnly ? 0.85 : 1
        }}
        onMouseDown={editingDisabled ? undefined : () => { setSelectedNodeId(null); setSelectedEdgeId(null); }}
      >
        {(!imageReady) && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none', fontSize: 18, fontWeight: 500, color: '#444' }}>
            Upload image to start planning...
          </div>
        )}
        <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0 }}>
          <defs>
            <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L10,5 L0,10 z" fill="#666" />
            </marker>
          </defs>
          {renderEdges()}
          {tempEdge}
        </svg>

        {nodes.map(node => {
          const isSelected = node.id === selectedNodeId;
          const isMissing = missingNodeIds.has(node.id);
          const rawVal = nodeParagraphCounts[node.id] ?? nodeSentenceCounts[node.id];
          const mappingCount = Array.isArray(rawVal) ? rawVal.length : (typeof rawVal === 'number' ? rawVal : 0);
          return (
            <div
              className={`flowchart-node ${isSelected ? 'is-selected' : ''} ${isMissing ? 'is-missing' : ''}`}
              key={node.id}
              onMouseDown={(e) => { if (editingDisabled) { e.stopPropagation(); return; } handleMouseDownNode(e, node); }}
              style={{
                position: 'absolute',
                top: node.y,
                left: node.x,
                width: node.width,
                height: node.height,
                background: isMissing ? '#f9f9f9' : node.color,
                border: isMissing ? '2px dashed #77777c' : `2px solid ${isSelected ? '#0a66d8' : node.border}`,
                borderRadius: 8,
                padding: '8px 10px 10px 10px',
                boxSizing: 'border-box',
                display: 'flex',
                flexDirection: 'column',
                fontSize: 12,
                cursor: 'grab',
                boxShadow: isSelected ? '0 0 0 3px rgba(10,102,216,0.16)' : '0 2px 8px rgba(0,0,0,0.08)',
                backdropFilter: 'blur(2px)',
                filter: isMissing ? 'grayscale(1)' : 'none',
                opacity: isMissing ? 0.9 : 1,
                borderStyle: node.optional ? 'dashed' : 'solid',
                borderWidth: '2px',
              }}
              onClick={(e) => { e.stopPropagation(); if (onNodeClick) onNodeClick(node.id); }}
              title={
                isMissing 
                  ? 'Content missing: please add this structural point in the main text' 
                  : currentStage === 'planning'
                    ? 'Start writing to enable sentence highlighting'
                    : mappingCount
                      ? `Linked paragraphs: ${mappingCount}`
                      : 'Click to view related writing'
              }
            >
              <div style={{ fontWeight: 'bold', fontSize: 13, marginBottom: 4, marginTop: node.optional ? 18 : 4 }}
                contentEditable={!editingDisabled}
                suppressContentEditableWarning
                onDoubleClick={(e) => { if (editingDisabled) return; e.stopPropagation(); setSelectedNodeId(node.id); }}
                onBlur={(e) => updateNodeTitle(node.id, e.currentTarget.textContent.slice(0,60))}
                onMouseDown={(e) => { if (editingDisabled) return; e.stopPropagation(); }}
              >
                {node.title}
              </div>
              <div style={{ flex: 1, lineHeight: 1.25, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'pre-line' }}>{node.text}</div>
              {!isMissing && (
                <div style={{ position: 'absolute', top: 4, right: 6, fontSize: 10, color: '#333', background: 'rgba(255,255,255,0.7)', padding: '1px 4px', borderRadius: 4 }}>
                  {mappingCount}
                </div>
              )}
              {node.optional && (
                <div style={{ position: 'absolute', top: 4, left: 6, fontSize: 8, color: '#6d3f91', background: 'rgba(255,255,255,0.8)', padding: '1px 3px', borderRadius: 3, fontWeight: 'bold' }}>
                  OPTIONAL
                </div>
              )}
              <div
                onMouseDown={(e) => { if (editingDisabled) return; startEdgeCreation(e, node); }}
                style={{
                  position: 'absolute',
                  bottom: -6,
                  right: -6,
                  width: 16,
                  height: 16,
                  background: creatingEdge?.fromNodeId === node.id ? '#0a66d8' : '#77777c',
                  borderRadius: '50%',
                  border: '2px solid white',
                  cursor: 'crosshair',
                  boxShadow: '0 0 0 2px rgba(0,0,0,0.15)'
                }}
                title="Drag to create a connection"
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

