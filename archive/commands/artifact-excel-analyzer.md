---
description: Create a powerful Excel file analyzer with formula extraction and visualization
---

# Create Excel Analyzer Artifact

Create a **complete Excel analyzer application** as a standalone HTML file.

## Features to include:

1. **File Upload** - Accept .xlsx and .xls files
2. **Formula Extraction** - Display all Excel formulas with their values
3. **Data Visualization** - Charts using Recharts
4. **Statistical Analysis** - Using Math.js
5. **Export Capability** - Download modified Excel files

## Required Libraries:
- React 18
- SheetJS (xlsx) - Excel file handling
- Recharts - Data visualization
- Math.js - Statistical calculations
- Tailwind CSS - Styling

## Component Structure:

```jsx
function App() {
    const [data, setData] = useState(null);
    const [formulas, setFormulas] = useState([]);
    const [stats, setStats] = useState(null);
    const [sheets, setSheets] = useState([]);
    const [activeSheet, setActiveSheet] = useState(0);

    const handleFile = (e) => {
        const file = e.target.files[0];
        const reader = new FileReader();

        reader.onload = (evt) => {
            const workbook = XLSX.read(evt.target.result, {
                type: 'binary',
                cellFormula: true,
                cellStyles: true,
                cellDates: true
            });

            // Process all sheets
            const allSheets = workbook.SheetNames.map(sheetName => {
                const worksheet = workbook.Sheets[sheetName];

                // Extract data
                const jsonData = XLSX.utils.sheet_to_json(worksheet, {
                    header: 1,
                    raw: false
                });

                // Extract formulas
                const formulaList = [];
                const range = XLSX.utils.decode_range(worksheet['!ref']);

                for (let R = range.s.r; R <= range.e.r; ++R) {
                    for (let C = range.s.c; C <= range.e.c; ++C) {
                        const addr = XLSX.utils.encode_cell({r: R, c: C});
                        const cell = worksheet[addr];
                        if (cell && cell.f) {
                            formulaList.push({
                                cell: addr,
                                formula: cell.f,
                                value: cell.v,
                                type: cell.t
                            });
                        }
                    }
                }

                return {
                    name: sheetName,
                    data: jsonData,
                    formulas: formulaList,
                    range: worksheet['!ref']
                };
            });

            setSheets(allSheets);
            setData(allSheets[0].data);
            setFormulas(allSheets[0].formulas);

            // Calculate statistics
            calculateStats(allSheets[0].data);
        };

        reader.readAsBinaryString(file);
    };

    const calculateStats = (sheetData) => {
        const numbers = sheetData.flat().filter(v => typeof v === 'number');
        if (numbers.length > 0) {
            setStats({
                count: numbers.length,
                sum: math.sum(numbers),
                mean: math.mean(numbers),
                median: math.median(numbers),
                std: math.std(numbers),
                min: math.min(numbers),
                max: math.max(numbers)
            });
        }
    };

    const downloadExcel = () => {
        const ws = XLSX.utils.aoa_to_sheet(data);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, "Analyzed Data");
        XLSX.writeFile(wb, "analyzed_data.xlsx");
    };

    return (
        <div className="min-h-screen bg-gray-50 p-8">
            <div className="max-w-7xl mx-auto">
                <h1 className="text-4xl font-bold mb-8 text-gray-800">
                    📊 Excel Analyzer
                </h1>

                {/* File Upload */}
                <div className="mb-8 p-6 bg-white rounded-lg shadow">
                    <input
                        type="file"
                        accept=".xlsx,.xls"
                        onChange={handleFile}
                        className="block w-full text-sm text-gray-500
                            file:mr-4 file:py-2 file:px-4
                            file:rounded-full file:border-0
                            file:text-sm file:font-semibold
                            file:bg-blue-50 file:text-blue-700
                            hover:file:bg-blue-100"
                    />
                </div>

                {/* Formulas Section */}
                {formulas.length > 0 && (
                    <div className="mb-8 p-6 bg-white rounded-lg shadow">
                        <h2 className="text-2xl font-bold mb-4 text-gray-800">
                            🔢 Formulas Found: {formulas.length}
                        </h2>
                        <div className="space-y-2 max-h-96 overflow-y-auto">
                            {formulas.map((f, i) => (
                                <div key={i} className="p-3 bg-gray-50 rounded font-mono text-sm">
                                    <span className="text-blue-600 font-bold">{f.cell}</span>
                                    <span className="text-gray-500 mx-2">=</span>
                                    <span className="text-green-600">{f.formula}</span>
                                    <span className="text-gray-500 mx-2">→</span>
                                    <span className="text-purple-600">{f.value}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Statistics Section */}
                {stats && (
                    <div className="mb-8 p-6 bg-white rounded-lg shadow">
                        <h2 className="text-2xl font-bold mb-4 text-gray-800">
                            📈 Statistical Analysis
                        </h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="p-4 bg-blue-50 rounded">
                                <div className="text-sm text-gray-600">Count</div>
                                <div className="text-2xl font-bold text-blue-600">{stats.count}</div>
                            </div>
                            <div className="p-4 bg-green-50 rounded">
                                <div className="text-sm text-gray-600">Sum</div>
                                <div className="text-2xl font-bold text-green-600">{stats.sum.toFixed(2)}</div>
                            </div>
                            <div className="p-4 bg-purple-50 rounded">
                                <div className="text-sm text-gray-600">Mean</div>
                                <div className="text-2xl font-bold text-purple-600">{stats.mean.toFixed(2)}</div>
                            </div>
                            <div className="p-4 bg-orange-50 rounded">
                                <div className="text-sm text-gray-600">Median</div>
                                <div className="text-2xl font-bold text-orange-600">{stats.median.toFixed(2)}</div>
                            </div>
                            <div className="p-4 bg-red-50 rounded">
                                <div className="text-sm text-gray-600">Std Dev</div>
                                <div className="text-2xl font-bold text-red-600">{stats.std.toFixed(2)}</div>
                            </div>
                            <div className="p-4 bg-yellow-50 rounded">
                                <div className="text-sm text-gray-600">Min</div>
                                <div className="text-2xl font-bold text-yellow-600">{stats.min}</div>
                            </div>
                            <div className="p-4 bg-pink-50 rounded">
                                <div className="text-sm text-gray-600">Max</div>
                                <div className="text-2xl font-bold text-pink-600">{stats.max}</div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Visualization */}
                {data && data.length > 1 && (
                    <div className="mb-8 p-6 bg-white rounded-lg shadow">
                        <h2 className="text-2xl font-bold mb-4 text-gray-800">
                            📊 Data Visualization
                        </h2>
                        <Recharts.ResponsiveContainer width="100%" height={400}>
                            <Recharts.LineChart data={data.slice(1).map(row => {
                                const obj = {};
                                data[0].forEach((header, i) => {
                                    obj[header] = row[i];
                                });
                                return obj;
                            })}>
                                <Recharts.CartesianGrid strokeDasharray="3 3" />
                                <Recharts.XAxis dataKey={data[0][0]} />
                                <Recharts.YAxis />
                                <Recharts.Tooltip />
                                <Recharts.Legend />
                                {data[0].slice(1).map((header, i) => (
                                    <Recharts.Line
                                        key={header}
                                        type="monotone"
                                        dataKey={header}
                                        stroke={['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c'][i % 4]}
                                        strokeWidth={2}
                                    />
                                ))}
                            </Recharts.LineChart>
                        </Recharts.ResponsiveContainer>
                    </div>
                )}

                {/* Download Button */}
                {data && (
                    <div className="text-center">
                        <button
                            onClick={downloadExcel}
                            className="bg-blue-600 text-white px-8 py-3 rounded-lg font-semibold
                                hover:bg-blue-700 transition-colors shadow-lg"
                        >
                            📥 Download Analyzed Excel
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
```

## Instructions:
1. Create the complete HTML file with all required libraries
2. Use the Write tool to save as `excel-analyzer.html`
3. Tell the user how to use it:
   - Open the HTML file in a browser
   - Upload an Excel file
   - View formulas, statistics, and visualizations
   - Download the analyzed data

This analyzer can handle complex Excel files with formulas and multiple sheets!
