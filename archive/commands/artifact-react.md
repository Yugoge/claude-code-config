---
description: Create a standalone React application with full library ecosystem
argument-hint: [app-name] [required-libraries]
---

# Create React Artifact

You are now creating a **standalone React application** as a single HTML file.

## Requirements from user:
- App name/purpose: $1
- Required libraries: $2

## IMPORTANT Instructions:

1. **Create a complete, standalone HTML file** that includes:
   - React 18 (production build)
   - ReactDOM 18
   - Babel standalone for JSX
   - Tailwind CSS (CDN)

2. **Include these libraries based on user needs**:
   - **Lucide Icons**: `https://unpkg.com/lucide@latest` (for icons)
   - **Recharts**: `https://unpkg.com/recharts@2.5.0/dist/Recharts.js` (for charts)
   - **Lodash**: `https://cdn.jsdelivr.net/npm/lodash@4.17.21/lodash.min.js` (utilities)
   - **D3.js**: `https://d3js.org/d3.v7.min.js` (advanced visualizations)
   - **Math.js**: `https://cdnjs.cloudflare.com/ajax/libs/mathjs/11.11.0/math.min.js` (calculations)
   - **Papa Parse**: `https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.4.1/papaparse.min.js` (CSV parsing)
   - **SheetJS**: `https://cdn.sheetjs.com/xlsx-0.20.0/package/dist/xlsx.full.min.js` (Excel handling)
   - **Chart.js**: `https://cdn.jsdelivr.net/npm/chart.js` (charts alternative)
   - **Plotly**: `https://cdn.plot.ly/plotly-2.26.0.min.js` (scientific plots)
   - **Three.js**: `https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js` (3D graphics)
   - **TensorFlow.js**: `https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.11.0/dist/tf.min.js` (ML)

3. **Template structure**:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>App Name</title>

    <!-- Core React -->
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>

    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- Additional libraries based on needs -->
    <!-- ... -->
</head>
<body>
    <div id="root"></div>

    <script type="text/babel">
        const { useState, useEffect, useRef } = React;

        function App() {
            // Your React component code here
            return (
                <div className="p-8">
                    <h1 className="text-3xl font-bold mb-4">App Title</h1>
                    {/* Content */}
                </div>
            );
        }

        ReactDOM.createRoot(document.getElementById('root')).render(<App />);
    </script>
</body>
</html>
```

4. **Write the file** using the Write tool with filename: `{app-name}.html`

5. **After creation**, tell the user:
   - File location
   - How to open it (just double-click or `open {filename}`)
   - What libraries are included
   - How to modify it

## Example Usage:
- `/artifact-react counter-app recharts` - Create a counter with charts
- `/artifact-react excel-viewer sheetjs,recharts` - Excel file viewer with visualization
- `/artifact-react ml-demo tensorflow` - Machine learning demo
