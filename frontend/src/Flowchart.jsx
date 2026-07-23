import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Plus, RotateCcw, Trash2 } from 'lucide-react';

// Type style definitions for DATA COMMENTARY MOVE structure
const TYPE_STYLES = {
  background: { 
    color: '#fff8e8',
    border: '#b97912',
    title: 'Background', 
    defaultText: 'Disciplinary knowledge (IELTS: request; Academic: aim, etc.)',
    standard: true
  },
  presentation: { 
    color: '#eef8f0',
    border: '#368a4c',
    title: 'Presentation of Visual', 
    defaultText: 'Core step: Guide different ways of introducing visuals. Choose from multiple options:',
    core: true
  },
  comment: { 
    color: '#edf5ff',
    border: '#397bbf',
    title: 'Comment on Result', 
    defaultText: 'Final step: Students add interpretations or highlight key findings.',
    final: true
  },
  // Sub-options for Presentation of Visual
  summary: { 
    color: '#f6f2fa',
    border: '#8063a6',
    title: 'a. Summary', 
    defaultText: 'Basic introduction of the visual：Figure 1 shows... ',
    subtype: 'presentation'
  },
  results: { 
    color: '#edf8f8',
    border: '#438c91',
    title: 'b. Results', 
    defaultText: 'Specific data presentation：Figure 1 shows City A had 100,000 people in 1990',
    subtype: 'presentation'
  },
  reference_explanation: { 
    color: '#fff1f4',
    border: '#b85d75',
    title: 'c. Reference & Explanation', 
    defaultText: 'Comparison, trend analysis, and detailed explanation',
    subtype: 'presentation'
  }
};

// DATA COMMENTARY MOVE node templates
const initialNodes = [
  {
    id: 'background', type: 'background', x: 220, y: 30, width: 200, height: 100,
    title: TYPE_STYLES.background.title,
    text: TYPE_STYLES.background.defaultText,
    color: TYPE_STYLES.background.color, 
    border: TYPE_STYLES.background.border,
    standard: true
  },
  {
    id: 'presentation', type: 'presentation', x: 220, y: 160, width: 200, height: 100,
    title: TYPE_STYLES.presentation.title,
    text: TYPE_STYLES.presentation.defaultText,
    color: TYPE_STYLES.presentation.color, 
    border: TYPE_STYLES.presentation.border,
    core: true
  },
  {
    id: 'summary', type: 'summary', x: 0, y: 280, width: 180, height: 100,
    title: TYPE_STYLES.summary.title,
    text: TYPE_STYLES.summary.defaultText,
    color: TYPE_STYLES.summary.color, 
    border: TYPE_STYLES.summary.border,
    subtype: 'presentation'
  },
  {
    id: 'results', type: 'results', x: 200, y: 280, width: 180, height: 120,
    title: TYPE_STYLES.results.title,
    text: TYPE_STYLES.results.defaultText,
    color: TYPE_STYLES.results.color, 
    border: TYPE_STYLES.results.border,
    subtype: 'presentation'
  },
  {
    id: 'reference_explanation', type: 'reference_explanation', x: 430, y: 280, width: 180, height: 120,
    title: TYPE_STYLES.reference_explanation.title,
    text: TYPE_STYLES.reference_explanation.defaultText,
    color: TYPE_STYLES.reference_explanation.color, 
    border: TYPE_STYLES.reference_explanation.border,
    subtype: 'presentation'
  },
  {
    id: 'comment', type: 'comment', x: 150, y: 450, width: 200, height: 120,
    title: TYPE_STYLES.comment.title,
    text: TYPE_STYLES.comment.defaultText,
    color: TYPE_STYLES.comment.color, 
    border: TYPE_STYLES.comment.border,
    final: true
  }
];

const initialEdges = [
  { id: 'e1', from: 'background', to: 'presentation', type: 'sequence' },
  { id: 'e2', from: 'presentation', to: 'summary', type: 'parent-child' },
  { id: 'e3', from: 'presentation', to: 'results', type: 'parent-child' },
  { id: 'e4', from: 'presentation', to: 'reference_explanation', type: 'parent-child' },
  { id: 'e5', from: 'presentation', to: 'comment', type: 'sequence' },
];

export default function Flowchart({ imageReady = false, onFlowchartChange, onNodeClick, missingNodeIds = new Set(), nodeSentenceCounts = {}, readOnly = false, currentStage = 'planning' }) {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState(null);
  const [creatingEdge, setCreatingEdge] = useState(null); // { fromNodeId, startX, startY, currentX, currentY }
  const [newNodeType, setNewNodeType] = useState('presentation');

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

  // New explicit add node (replacing previous double-click-to-add)
  const addNode = () => {
    if (!imageReady || readOnly) return;
    const style = TYPE_STYLES[newNodeType];
    let computedTitle = style.title;
    
    // Handle special cases for presentation subtypes
    if (newNodeType === 'summary' || newNodeType === 'results' || newNodeType === 'reference_explanation') {
      const existingCount = nodes.filter(n => n.type === newNodeType).length;
      if (existingCount > 0) {
        computedTitle = `${style.title} ${existingCount + 1}`;
      }
    }
    
    // Position strategy: stack downward; place below lowest existing node of same type else increment by 120
    const baseY = nodes.length ? Math.max(...nodes.map(n => n.y + n.height)) + 40 : 30;
    const x = 320; // center-ish default
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
      border: style.border
    };
    
                // Add special properties for different node types
                if (style.standard) newNode.standard = true;
                if (style.core) newNode.core = true;
                if (style.final) newNode.final = true;
                if (style.subtype) newNode.subtype = style.subtype;
    
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
        // Determine edge type based on node types
        const fromNode = getNodeById(creatingEdge.fromNodeId);
        const toNode = getNodeById(target.id);
        let edgeType = 'sequence'; // default
        
        // Parent-child relationship: presentation -> summary/results/reference_explanation
        if (fromNode?.type === 'presentation' && 
            (toNode?.type === 'summary' || toNode?.type === 'results' || toNode?.type === 'reference_explanation')) {
          edgeType = 'parent-child';
        }
        
        setEdges(prev => [...prev, { id, from: creatingEdge.fromNodeId, to: target.id, type: edgeType }]);
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
      
      // Determine edge style based on type
      const isParentChild = edge.type === 'parent-child';
      const isSequence = edge.type === 'sequence';
      
      // Different styles for different edge types
      const strokeColor = isSelected ? '#0a66d8' : (isParentChild ? '#8063a6' : '#77777c');
      const strokeWidth = isSelected ? 3 : (isParentChild ? 2 : 2);
      const strokeDasharray = isParentChild ? '5,5' : 'none';
      const markerEnd = isSequence ? 'url(#arrow)' : 'url(#circle)';
      
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
            strokeDasharray={strokeDasharray}
            fill="none"
            markerEnd={markerEnd}
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
        nodes: nodes.map(n => ({ id: n.id, type: n.type, title: n.title, text: n.text, x: n.x, y: n.y, width: n.width, height: n.height })),
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
            <option value="background">Background</option>
            <option value="presentation">Presentation of Visual</option>
            <option value="summary">a. Summary</option>
            <option value="results">b. Results</option>
            <option value="reference_explanation">c. Reference & Explanation</option>
            <option value="comment">Comment on Result</option>
          </select>
        </label>
        <span className="flowchart-status" style={{ fontSize: '0.7rem', color: '#555', lineHeight: 1.2 }}>
          {editingDisabled ? (readOnly ? 'Read-only view (revision stage): node editing disabled' : 'Please upload an image first (Flowchart disabled until image uploaded)') : 'DATA COMMENTARY MOVE: Background → Presentation (core) → Comment (final) | Drag nodes to move | Drag bottom-right dot to create links'}
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
            <marker id="circle" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto" markerUnits="strokeWidth">
              <circle cx="4" cy="4" r="3" fill="#9c27b0" />
            </marker>
          </defs>
          {renderEdges()}
          {tempEdge}
        </svg>

        {nodes.map(node => {
          const isSelected = node.id === selectedNodeId;
          const isMissing = missingNodeIds.has(node.id);
          // nodeSentenceCounts now stores arrays of sentence indices; display length starting from 1 logically (count of sentences)
          const rawVal = nodeSentenceCounts[node.id];
          const sentenceCount = Array.isArray(rawVal) ? rawVal.length : (typeof rawVal === 'number' ? rawVal : 0);
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
                borderRadius: 10,
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
                // Add special styling for different node types
                borderStyle: node.optional ? 'dashed' : 'solid',
                borderWidth: node.core ? '3px' : '2px',
                fontWeight: node.final ? 'bold' : 'normal',
              }}
              onClick={(e) => { e.stopPropagation(); if (onNodeClick) onNodeClick(node.id); }}
              title={
                isMissing 
                  ? 'Content missing: please add this structural point in the main text' 
                  : currentStage === 'planning'
                    ? 'Start writing to enable sentence highlighting'
                    : sentenceCount 
                      ? `Linked sentences: ${sentenceCount}` 
                      : 'Click to view related sentences'
              }
            >
              <div style={{ fontWeight: 'bold', fontSize: 13, marginBottom: 4, marginTop: 20 }}
                contentEditable={!readOnly}
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
                  {sentenceCount}
                </div>
              )}
              {/* Add type indicators */}
              {node.optional && (
                <div style={{ position: 'absolute', top: 4, left: 6, fontSize: 8, color: '#ff9800', background: 'rgba(255,255,255,0.8)', padding: '1px 3px', borderRadius: 3, fontWeight: 'bold' }}>
                  OPTIONAL
                </div>
              )}
              {node.core && (
                <div style={{ position: 'absolute', top: 4, left: 6, fontSize: 8, color: '#4caf50', background: 'rgba(255,255,255,0.8)', padding: '1px 3px', borderRadius: 3, fontWeight: 'bold' }}>
                  CORE
                </div>
              )}
              {node.final && (
                <div style={{ position: 'absolute', top: 4, left: 6, fontSize: 8, color: '#2196f3', background: 'rgba(255,255,255,0.8)', padding: '1px 3px', borderRadius: 3, fontWeight: 'bold' }}>
                  FINAL
                </div>
              )}
              {node.core && (
                <div style={{ position: 'absolute', top: 4, right: 6, fontSize: 8, color: '#9c27b0', background: 'rgba(255,255,255,0.8)', padding: '1px 3px', borderRadius: 3, fontWeight: 'bold' }}>
                  HAS SUB-OPTIONS
                </div>
              )}
              {node.subtype === 'presentation' && (
                <div style={{ position: 'absolute', top: 4, left: 6, fontSize: 8, color: '#9c27b0', background: 'rgba(255,255,255,0.8)', padding: '1px 3px', borderRadius: 3, fontWeight: 'bold' }}>
                  SUB-OPTION
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

