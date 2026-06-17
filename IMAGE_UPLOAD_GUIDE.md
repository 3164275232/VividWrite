# Image Upload Feature Guide

## 🎯 Overview

VividWrite 2.0 supports uploading an original chart image. The system analyzes the image together with the student's written description to produce visual feedback and revision suggestions.

## 📸 Supported Image Formats

- **JPG/JPEG**: Common format
- **PNG**: Supports transparency
- **GIF**: Supports animation
- **Size Limit**: Max 5MB

## 🚀 How to Use

### 1. Upload Image
1. Click the "Choose Image" button in the "Original Image" section (left side)
2. Select the chart image to analyze
3. The image appears immediately with basic file info

### 2. Enter Student Answer
1. Type the IELTS Task 1 answer in the "Writing Area"
2. Make sure the answer describes and analyzes the chart

### 3. Run Analysis
1. Click the "Analyze Text" button
2. The system analyzes using both the image and the written answer
3. This may take a few seconds

### 4. View Results
1. **Visual Feedback**: Original image, extracted/deconstructed chart data, and generated chart
2. **Revision Suggestions**: Suggested improvements based on the analysis

## 🎨 UI Features

### Upload Area
- **Drag & Drop**: Drag image files directly
- **File Picker**: Click button to choose
- **Preview**: Immediate preview after upload
- **Delete**: Remove with the × button (planning stage only)
- **File Info**: Shows name and size

### Analysis Output
- **Original Image**: The uploaded chart
- **Extracted Data**: Textual/chart data extracted from the image
- **Generated Chart**: System-produced visualization
- **Error Handling**: Clear messages if loading fails

## 🔧 Implementation Details

### Frontend
- **Validation**: File type & size checks
- **Preview**: Generated via FileReader API
- **Upload**: multipart/form-data FormData submission
- **Errors**: User-friendly feedback

### Backend
- **Storage**: Saved in `uploaded_images`
- **Unique Naming**: UUID prevents collision
- **Static Serving**: Available via `/uploads`
- **Chart Analysis**: Integrates `bar.py` and `pie.py`

## 📊 Analysis Flow

```
User uploads image → Saved to server → Combined with written answer → AI analysis → Chart data generated → Results returned
```

### Detailed Steps
1. **Upload**: User selects image
2. **Validate**: Type & size
3. **Persist**: Store in `uploaded_images`
4. **Prepare**: Build analysis request payload
5. **AI Analysis**: Call OpenAI (and DePlot extraction if needed)
6. **Output**: Produce chart structure + suggestions
7. **Display**: Render in frontend

## 🎯 Use Cases

### Teaching
1. **Instructor**: Upload chart + student answer to get structured feedback
2. **Student Practice**: Self-check practice responses
3. **Assignment Review**: Rapid feedback loop

### Learning
1. **Self‑Assessment**: Compare writing with extracted data
2. **Comparative Study**: Observe differences between raw and generated charts
3. **Skill Improvement**: Use suggestions to refine structure and accuracy

## 🔍 Troubleshooting

### Common Issues

#### 1. Upload Fails
- Check format (JPG / PNG / GIF only)
- Check size (≤ 5MB)
- Check network connectivity

#### 2. Analysis Fails
- Ensure chart is clear and readable
- Ensure answer includes sufficient description
- Verify API configuration (OPENAI API key)

#### 3. Image Not Displayed
- Verify file saved correctly
- Check server read permissions
- Clear cache / refresh

### Error Messages Explained
- **"Please upload an image file"**: Non-image file chosen
- **"Image file size must not exceed 5MB"**: File too large
- **"Please upload the original image first"**: Analysis attempted without an image
- **"Analysis failed"**: Backend exception during processing

## 🚀 Performance Tips

### Image Optimization
- Compress before upload
- Use appropriate resolution
- Ensure clarity of labels and numbers

### Network Optimization
- Maintain stable connection
- Allow time for processing
- Retry if transient failure

## 📈 Future Extensions

### Planned Features
- **Batch Upload**
- **Inline Image Editing**
- **Format Conversion**
- **Cloud Storage Integration**

### Analysis Enhancements
- **More Chart Types**
- **Automatic Chart Type Detection**
- **Multilingual Support**
