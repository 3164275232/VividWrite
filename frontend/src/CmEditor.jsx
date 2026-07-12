import React, { useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import { EditorState, StateEffect, StateField } from '@codemirror/state';
import { EditorView, keymap, Decoration } from '@codemirror/view';
import { placeholder as cmPlaceholder } from '@codemirror/view';
// Use history from commands (history package deprecated in later bundling) 
import { history, historyKeymap, defaultKeymap } from '@codemirror/commands';

// Effect to set transient highlight ranges
const setTransientHighlights = StateEffect.define({});

// Effect to set persistent highlight ranges (future use)
const setPersistentHighlights = StateEffect.define({});

// Build a decoration for yellow highlight
const yellowMark = Decoration.mark({ class: 'cm-hl-yellow' });

// Field for transient (auto-expiring) highlights (e.g., newly inserted sentence)
const transientHighlightField = StateField.define({
  create() { return Decoration.none; },
  update(value, tr) {
    // Map existing decorations through document changes
    value = value.map(tr.changes);
    for (let e of tr.effects) {
      if (e.is(setTransientHighlights)) {
        const ranges = e.value || [];
        if (ranges.length === 0) {
          value = Decoration.none;
        } else {
          let decos = [];
          for (const r of ranges) {
            decos.push(yellowMark.range(r.from, r.to));
          }
          value = Decoration.set(decos, true);
        }
      }
    }
    return value;
  },
  provide: f => EditorView.decorations.from(f)
});

// Field for persistent highlights
const persistentHighlightField = StateField.define({
  create() { return Decoration.none; },
  update(value, tr) {
    value = value.map(tr.changes);
    for (let e of tr.effects) {
      if (e.is(setPersistentHighlights)) {
        const ranges = e.value || [];
        if (ranges.length === 0) {
            value = Decoration.none;
        } else {
          let decos = [];
          for (const r of ranges) {
            const mark = Decoration.mark({ class: r.className || 'cm-hl-yellow' });
            decos.push(mark.range(r.from, r.to));
          }
          value = Decoration.set(decos, true);
        }
      }
    }
    return value;
  },
  provide: f => EditorView.decorations.from(f)
});

const baseExtensions = [
  history(),
  keymap.of([...defaultKeymap, ...historyKeymap]),
  transientHighlightField,
  persistentHighlightField,
  EditorView.lineWrapping,
  EditorView.theme({
    '.cm-content': {
      fontFamily: 'system-ui, sans-serif',
      fontSize: '14px'
    },
    '.cm-editor': {
      backgroundColor: '#f0f0f0'
    },
    '.cm-scroller': {
      backgroundColor: '#f0f0f0'
    },
    '.cm-hl-yellow': {
      backgroundColor: '#ffc107'
    }
  })
];

// Utility: compute CodeMirror diff-friendly transaction for external value changes
function updateIfChanged(view, newValue) {
  const current = view.state.doc.toString();
  if (current === newValue) return;
  view.dispatch({
    changes: { from: 0, to: current.length, insert: newValue }
  });
}

const CmEditor = forwardRef(function CmEditor({ value, onChange, style, placeholder = '' }, ref) {
  const hostRef = useRef(null);
  const viewRef = useRef(null);
  const initialValueRef = useRef(value);

  useEffect(() => {
    if (!hostRef.current) return;
    const dynamicExtensions = [];
    if (placeholder) {
      dynamicExtensions.push(cmPlaceholder(placeholder));
    }
    const state = EditorState.create({
      doc: initialValueRef.current || '',
      extensions: [
        ...baseExtensions,
        ...dynamicExtensions,
        EditorView.updateListener.of(vu => {
          if (vu.docChanged) {
            onChange && onChange(vu.state.doc.toString());
          }
        })
      ]
    });
    const view = new EditorView({ state, parent: hostRef.current });
    viewRef.current = view;
    return () => view.destroy();
  }, [onChange, placeholder]);

  // External value sync
  useEffect(() => {
    if (viewRef.current && typeof value === 'string') {
      updateIfChanged(viewRef.current, value);
    }
  }, [value]);

  useImperativeHandle(ref, () => ({
    getValue: () => viewRef.current?.state.doc.toString() || '',
    appendText: (text) => {
      const view = viewRef.current;
      if (!view) return;
      const doc = view.state.doc;
      view.dispatch({
        changes: { from: doc.length, to: doc.length, insert: text },
        selection: { anchor: doc.length + text.length }
      });
    },
    highlightRange: (from, to, transient = true) => {
      const view = viewRef.current;
      if (!view) return;
      const docLength = view.state.doc.length;
      let start = Math.max(0, Math.min(from, docLength));
      let end = Math.max(start, Math.min(to, docLength));
      if (end === start) return; // nothing to highlight
      const effect = transient ? setTransientHighlights.of([{ from: start, to: end }]) : setPersistentHighlights.of([{ from: start, to: end }]);
      view.dispatch({ effects: effect });
      if (transient) {
        setTimeout(() => {
          if (!view.destroyed) view.dispatch({ effects: setTransientHighlights.of([]) });
        }, 3500);
      }
    },
    highlightSentenceRanges: (ranges) => {
      // ranges: [{from,to}]
      const view = viewRef.current;
      if (!view) {
        console.log('❌ CmEditor: view not available for highlightSentenceRanges');
        return;
      }
      console.log('CmEditor: highlighting ranges:', ranges);
      const effects = setPersistentHighlights.of(ranges.map(r => ({ from: r.from, to: r.to, className: 'cm-hl-yellow'})));
      view.dispatch({ effects });
      console.log('✅ CmEditor: highlights applied');
    },
    clearHighlights: () => {
      const view = viewRef.current;
      if (!view) {
        console.log('❌ CmEditor: view not available for clearHighlights');
        return;
      }
      console.log('CmEditor: clearing all highlights');
      view.dispatch({ effects: [setTransientHighlights.of([]), setPersistentHighlights.of([])] });
      console.log('✅ CmEditor: highlights cleared');
    }
  }), []);

  return <div ref={hostRef} style={{ width: '100%', height: '100%', ...style }} />;
});

export default CmEditor;
