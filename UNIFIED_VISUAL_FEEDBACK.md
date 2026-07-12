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

## Hybrid rendering for spatial tasks

IELTS map and process tasks describe spatial objects, changes, stages and
connections rather than numerical tables. They now bypass DePlot and use the
uploaded image as a reference for Alibaba Cloud Wan2.7 image editing.

```text
bar/line/pie/area/scatter -> DeepSeek records -> Vega-Lite -> PNG
map/process                -> original image + essay -> Wan2.7 -> local PNG
```

Configure the spatial renderer in `backend/.env`:

```env
WAN_API_KEY=your_dashscope_api_key
WAN_IMAGE_MODEL=wan2.7-image-pro
WAN_WORKSPACE_ID=your_bailian_workspace_id
WAN_API_ENDPOINT=
```

`WAN_WORKSPACE_ID` selects Alibaba Cloud Model Studio's China (Beijing)
workspace endpoint. `WAN_API_ENDPOINT` can override the complete endpoint.
The returned temporary image URL is downloaded immediately and stored under
`backend/generated_charts`, so the frontend always uses a stable local URL.

Spatial feedback remains generative. It can contain label or layout mistakes,
so the response metadata marks it as `manual-review-required`. Next Sentence
and Sample Essay are disabled for map/process tasks until a vision-language
model is added for those writing features.
