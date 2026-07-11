# Unified visual feedback pipeline

## Why this design

DeepSeek is used for semantic extraction and alignment, but it is not asked to
draw pixels. Text-to-image output is not reliable enough for exact values,
labels, axes, or repeatable comparisons. Instead, DeepSeek produces one
validated declarative representation and Vega-Lite renders it deterministically.

## Runtime flow

1. DePlot extracts the official chart table.
2. DeepSeek reads the DePlot text and the student's essay in one request.
3. The official table supplies the framework, ordering, labels, and units.
4. The essay supplies the displayed values. Omitted cells remain null and are
   marked as missing; inferred values are marked as estimated.
5. DeepSeek returns long-form records plus a Vega-Lite specification.
6. The backend validates the records and specification, injects a palette
   extracted locally from the uploaded image, and renders a PNG.

All statistical chart types use the same service and record fields:

```json
{
  "category": "2001",
  "series": "Local calls",
  "period": "2001",
  "region": null,
  "value": 72,
  "x": null,
  "y": null,
  "estimated": false,
  "missing": false,
  "confidence": 0.98
}
```

The currently enabled chart types are bar, line, area, pie, and scatter. The
same framework can add another statistical mark without a new merge algorithm
or a new Python plotting module.

## Map-task boundary

IELTS map tasks describe spatial objects and before/after relationships rather
than a numerical table. DePlot does not extract this scene structure, and a
DeepSeek text model cannot recover it from image pixels. Map support therefore
needs a domestic vision model adapter that outputs a scene graph (objects,
positions, connections, and states). Once that scene graph exists, it can use
the same alignment contract, but it should not be represented as fake tabular
data.
