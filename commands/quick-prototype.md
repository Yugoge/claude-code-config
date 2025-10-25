---
description: Rapidly create interactive prototypes and demos combining multiple artifact capabilities
argument-hint: [prototype-description]
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

### 1. Data Dashboard
**When to use**: User wants to visualize data, see statistics, create reports
**Libraries**: React + Recharts + Math.js + Tailwind
**Features**: File upload, charts, statistics, export

### 2. Interactive Calculator
**When to use**: User needs calculations, simulations, financial tools
**Libraries**: React + Math.js + Tailwind
**Features**: Input forms, real-time calculations, formula display

### 3. File Processor
**When to use**: User wants to upload and process files (Excel, CSV, etc.)
**Libraries**: React + SheetJS/PapaParse + Recharts + Tailwind
**Features**: File upload, data preview, processing, download

### 4. Visualization Tool
**When to use**: User wants to create charts, graphs, diagrams
**Libraries**: React + D3.js/Plotly + Tailwind
**Features**: Data input, multiple chart types, customization

### 5. ML Demo
**When to use**: User wants machine learning demo
**Libraries**: React + TensorFlow.js + Recharts + Tailwind
**Features**: Model training, prediction, visualization

## Implementation Steps:

### Step 1: Analyze Requirements
Ask clarifying questions if needed:
- "What type of data will this handle?"
- "What visualizations do you need?"
- "Any specific features or calculations?"

### Step 2: Select Libraries
Based on requirements, choose from:
- **Essential**: React, Tailwind CSS
- **Data**: SheetJS, PapaParse, Math.js
- **Charts**: Recharts (simple), Plotly (advanced), D3 (custom)
- **Special**: TensorFlow.js, Three.js, Tone.js (if needed)

### Step 3: Create Prototype Structure
```jsx
function App() {
    // State management
    const [data, setData] = useState(null);
    const [results, setResults] = useState(null);

    // File handling
    const handleFileUpload = (e) => {
        // Process file
    };

    // Processing logic
    const processData = () => {
        // Transform data
        // Calculate results
        // Update visualizations
    };

    return (
        <div className="min-h-screen bg-gray-50 p-8">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <h1 className="text-4xl font-bold mb-8">Prototype Title</h1>

                {/* Input Section */}
                <div className="mb-8 p-6 bg-white rounded-lg shadow">
                    {/* File upload or data input */}
                </div>

                {/* Results/Visualization Section */}
                {results && (
                    <div className="mb-8 p-6 bg-white rounded-lg shadow">
                        {/* Charts, tables, results */}
                    </div>
                )}

                {/* Actions */}
                <div className="text-center">
                    {/* Buttons for download, reset, etc. */}
                </div>
            </div>
        </div>
    );
}
```

### Step 4: Generate Complete HTML File
Use the React artifact template with:
- All required CDN libraries
- Complete component code
- Inline styles if needed
- Clear comments

### Step 5: Deliver to User
1. **Save file** using Write tool as `{prototype-name}.html`
2. **Explain** what it does and how to use it
3. **Provide** customization suggestions
4. **Mention** how to extend it

## Example Prototypes:

### Sales Dashboard
```
User: "Create a sales dashboard"
Result: React app with:
- CSV/Excel file upload
- Monthly revenue charts (Recharts)
- Statistical summary (Math.js)
- Top products table
- Export functionality
```

### Mortgage Calculator
```
User: "Mortgage payment calculator"
Result: React app with:
- Input fields (loan amount, rate, term)
- Real-time calculation (Math.js)
- Amortization chart (Recharts)
- Payment schedule table
- Tailwind styling
```

### Image Classifier Demo
```
User: "ML image classifier"
Result: React app with:
- Image upload
- TensorFlow.js model (MobileNet)
- Prediction results
- Confidence visualization (Recharts)
```

### Budget Tracker
```
User: "Personal budget tracker"
Result: React app with:
- Expense entry form
- Category breakdown (pie chart)
- Monthly trends (line chart)
- Save/load data (localStorage)
- Export to Excel (SheetJS)
```

## Quality Standards:

Every prototype must have:
- ✅ Clean, modern UI (Tailwind CSS)
- ✅ Responsive design (mobile-friendly)
- ✅ Clear instructions for users
- ✅ Error handling
- ✅ Loading states (if applicable)
- ✅ Helpful tooltips/hints
- ✅ Export functionality (when relevant)

## After Creation:

Tell the user:
1. **File location** and how to open it
2. **What it does** (key features)
3. **How to use it** (step-by-step if complex)
4. **How to customize** (which parts to modify)
5. **Possible extensions** (what could be added)

## Example Usage:
- `/quick-prototype "Sales data visualization dashboard"`
- `/quick-prototype "Compound interest calculator with charts"`
- `/quick-prototype "CSV data analyzer with statistics"`
- `/quick-prototype "Task management app with local storage"`

Remember: The goal is to create something **immediately useful** that the user can **run right away** without any setup!
