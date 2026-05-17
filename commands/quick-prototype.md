---
description: Rapidly create interactive prototypes and demos combining multiple artifact capabilities
argument-hint: [prototype-description]
disable-model-invocation: true
---

# Quick Prototype Generator

Create **complete, interactive prototypes** in minutes by combining React, visualization libraries, and data processing capabilities.

## User Request:
Prototype description: $ARGUMENTS

## What This Command Does:

This command helps you rapidly create functional prototypes by:
1. **Understanding** your requirements
2. **Selecting** the right combination of libraries
3. **Generating** a complete, working application
4. **Providing** immediate usability

## Available Capabilities:

### Data Processing
- 📊 Excel file handling (SheetJS) - Read, write, analyze Excel files with formulas
- 📄 CSV parsing (PapaParse) - Parse and process CSV data
- 🧮 Advanced calculations (Math.js) - Statistical analysis, mathematical operations

### Visualization
- 📈 Charts (Recharts) - Line, bar, pie, area charts
- 📉 Scientific plots (Plotly) - 3D plots, heatmaps, scientific visualizations
- 🎨 Custom visualizations (D3.js) - Custom SVG-based visualizations
- 📊 Chart.js - Alternative charting library

### UI Components
- 🎨 Styling (Tailwind CSS) - Modern, responsive design
- 🔤 Icons (Lucide) - Beautiful icon set
- 🖼️ 3D Graphics (Three.js) - 3D visualizations and animations

### Advanced Features
- 🤖 Machine Learning (TensorFlow.js) - ML models in the browser
- 🎵 Audio (Tone.js) - Sound synthesis and music
- 📝 Document processing (Mammoth) - Word document handling

## Common Prototype Patterns:

| Pattern | When to use | Core libraries |
|---------|-------------|----------------|
| Data Dashboard | Visualize data, statistics, reports | React + Recharts + Math.js + Tailwind |
| Interactive Calculator | Calculations, simulations, financial tools | React + Math.js + Tailwind |
| File Processor | Upload and process Excel/CSV | React + SheetJS/PapaParse + Recharts + Tailwind |
| Visualization Tool | Charts, graphs, diagrams | React + D3.js/Plotly + Tailwind |
| ML Demo | Machine learning demos | React + TensorFlow.js + Recharts + Tailwind |

## Implementation Steps:

1. Analyze requirements — clarify data type, visualizations, and key features needed.
2. Select libraries from: React + Tailwind (essential); SheetJS/PapaParse/Math.js (data); Recharts/Plotly/D3 (charts); TensorFlow.js/Three.js/Tone.js (special).
3. Generate a complete HTML file using the React artifact template with all required CDN libraries, full component code, inline styles, and clear comments.
4. Save as `{prototype-name}.html` and explain file location, key features, usage, customization points, and possible extensions.
5. To commit and publish: `git add {prototype-name}.html && git commit -m "feat: add {prototype-name} prototype"`, then run `/push`.
