# 🔗 Data Lineage Generator from a DAG-Based Data Pipeline

> A production-grade data engineering tool to visualize, trace, and analyze data lineage across complex pipeline DAGs — built as a final-year B.Tech CSE project.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)
![NetworkX](https://img.shields.io/badge/NetworkX-3.3-orange?style=flat)
![Tests](https://img.shields.io/badge/Tests-50%20passing-brightgreen?style=flat)

---

## 📋 Table of Contents

- [Project Overview](#-project-overview)
- [Architecture](#-architecture)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Installation & Setup](#-installation--setup)
- [Running the Application](#-running-the-application)
- [API Documentation](#-api-documentation)
- [Sample Input Format](#-sample-input-format)
- [How to Use](#-how-to-use)
- [Testing](#-testing)
- [Advanced Features](#-advanced-features)
- [Algorithm Details](#-algorithm-details)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Project Overview

This tool simulates real-world **data engineering pipelines** (like Apache Spark DAGs) and provides:

- **Lineage Tracking** — trace where your data came from (upstream) and where it goes (downstream)
- **Impact Analysis** — understand the blast radius if a pipeline node fails
- **Interactive Visualization** — explore the DAG with color-coded highlights
- **Export Reports** — download lineage as PDF or JSON

**Use Case Example:** In an e-commerce company, if the `clean_orders` transformation job fails, this tool immediately shows you which dashboards, ML models, and reports will break — and exactly which source data was feeding into it.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     React Frontend                        │
│    Cytoscape.js Graph │ Upload Panel │ Lineage Sidebar   │
└────────────────────────────┬─────────────────────────────┘
                             │ HTTP / REST
┌────────────────────────────▼─────────────────────────────┐
│                    FastAPI Backend                        │
│   routes/ → services/ → graph_service (NetworkX)         │
│              ↓                                           │
│           SQLAlchemy ORM                                 │
│         PostgreSQL (prod) / SQLite (dev)                 │
└──────────────────────────────────────────────────────────┘
```

**Data Flow:**
1. User uploads a DAG JSON describing the pipeline
2. Backend validates it (cycle detection, schema checks)
3. Stored in the database (nodes + edges tables)
4. On query: graph loaded → NetworkX traversal → result cached → returned
5. Frontend visualizes the subgraph with color highlights

---

## ✨ Features

### Core
| Feature | Description |
|---|---|
| DAG Upload | JSON upload via drag-drop, file picker, or paste |
| Upstream Lineage | All ancestors of a node (BFS on reversed graph) |
| Downstream Lineage | All descendants of a node (BFS) |
| Full Lineage | Combined ancestor + descendant subgraph |
| Impact Analysis | Blast radius + risk score if a node fails |
| Path Tracing | All paths from root sources to the target node |

### Advanced
| Feature | Description |
|---|---|
| Column-Level Lineage | Trace individual columns across transformations |
| Versioned DAGs | Each upload is a new version; switch between them |
| Result Caching | Lineage computed once, served from cache after |
| PDF Export | Download formatted lineage reports |
| JSON Export | Machine-readable lineage data |
| Cycle Detection | Rejects cyclic graphs with cycle path shown |
| Graph Statistics | Node count, critical path, density, sources/sinks |
| Large DAG Support | Tested with 1000+ nodes (< 5s traversal) |
| Search | Search nodes by name, ID, type, or operation |

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | Python 3.10+, FastAPI | REST API, async server |
| **Graph Engine** | NetworkX | DAG traversal, BFS/DFS, cycle detection |
| **Database** | PostgreSQL / SQLite | DAG storage, caching |
| **ORM** | SQLAlchemy 2.0 | Database abstraction |
| **Validation** | Pydantic v2 | Request/response schemas |
| **Frontend** | React 18, Vite | UI framework |
| **Graph Viz** | Cytoscape.js + dagre | Interactive graph rendering |
| **Styling** | Tailwind CSS | Dark theme UI |
| **PDF Export** | ReportLab | Professional PDF reports |
| **Testing** | pytest, FastAPI TestClient | 50 unit + integration tests |

---

## 📁 Project Structure

```
data-lineage-generator/
├── backend/
│   ├── main.py                   # FastAPI app + startup
│   ├── database.py               # SQLAlchemy engine + session
│   ├── requirements.txt
│   ├── models/
│   │   ├── db_models.py          # ORM table definitions
│   │   └── schemas.py            # Pydantic request/response schemas
│   ├── routes/
│   │   └── dag_routes.py         # All API endpoint handlers
│   ├── services/
│   │   ├── graph_service.py      # NetworkX traversal engine
│   │   └── lineage_service.py    # DB + graph orchestration
│   ├── utils/
│   │   ├── validators.py         # DAG validation + cycle detection
│   │   └── export_utils.py       # PDF + JSON export
│   └── tests/
│       ├── test_graph_service.py # Unit tests (graph algorithms)
│       └── test_api.py           # Integration tests (API endpoints)
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── App.jsx               # Root component + layout
│       ├── main.jsx
│       ├── index.css
│       ├── services/
│       │   └── api.js            # Axios API client
│       └── components/
│           ├── GraphVisualization.jsx  # Cytoscape.js canvas
│           ├── UploadPanel.jsx         # File upload + sample DAGs
│           ├── Sidebar.jsx             # Lineage results panel
│           ├── SearchBar.jsx           # Node search
│           ├── GraphStats.jsx          # Pipeline metrics
│           └── VersionPanel.jsx        # DAG version history
├── database/
│   ├── schema.sql                # PostgreSQL DDL
│   ├── sample_ecommerce_dag.json # 23-node sample DAG
│   └── generate_large_dag.py    # 1000+ node DAG generator
└── README.md
```

---

## ⚙️ Installation & Setup

### Prerequisites

- **Python** 3.10 or higher
- **Node.js** 18 or higher
- **npm** or **yarn**
- **PostgreSQL** 14+ *(optional — SQLite used by default)*

---

### Backend Setup

```bash
# 1. Navigate to backend
cd data-lineage-generator/backend

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

#### Database Configuration

**Option A: SQLite (zero-config, for development)**
No configuration needed — the app automatically creates `data_lineage.db`.

**Option B: PostgreSQL (recommended for production)**
```bash
# Create database
psql -U postgres -c "CREATE DATABASE data_lineage;"

# Apply schema
psql -U postgres -d data_lineage -f ../database/schema.sql

# Set environment variable
export DATABASE_URL="postgresql://postgres:password@localhost:5432/data_lineage"
```

---

### Frontend Setup

```bash
# Navigate to frontend
cd data-lineage-generator/frontend

# Install dependencies
npm install

# Note: If you see peer dependency warnings, use:
npm install --legacy-peer-deps
```

---

## 🚀 Running the Application

### Start Backend

```bash
cd backend

# Development mode (auto-reload on code changes)
python main.py

# OR with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at: **http://localhost:8000**
Swagger API docs: **http://localhost:8000/docs**

---

### Start Frontend

```bash
cd frontend

npm run dev
```

Frontend runs at: **http://localhost:5173**

---

## 📡 API Documentation

Full interactive documentation available at **http://localhost:8000/docs** (Swagger UI).

### Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/upload-dag` | Upload a DAG from JSON body |
| `POST` | `/api/v1/upload-dag/file` | Upload a DAG from `.json` file |
| `GET` | `/api/v1/dags` | List all uploaded DAGs |
| `GET` | `/api/v1/dags/{dag_id}` | Get DAG details + graph stats |
| `DELETE` | `/api/v1/dags/{dag_id}` | Delete a DAG |
| `GET` | `/api/v1/upstream/{dag_id}/{node_id}` | Get upstream lineage |
| `GET` | `/api/v1/downstream/{dag_id}/{node_id}` | Get downstream lineage |
| `GET` | `/api/v1/full-lineage/{dag_id}/{node_id}` | Get full lineage |
| `GET` | `/api/v1/impact-analysis/{dag_id}/{node_id}` | Get impact analysis |
| `GET` | `/api/v1/graph-stats/{dag_id}` | Get graph statistics |
| `GET` | `/api/v1/export/{dag_id}/{node_id}?format=pdf` | Export lineage report |

---

## 📄 Sample Input Format

```json
{
  "name": "My Data Pipeline",
  "description": "ETL pipeline for order processing",
  "nodes": [
    {
      "id": "raw_orders",
      "name": "Raw Orders",
      "type": "source",
      "description": "Order events from Kafka",
      "tags": ["kafka", "streaming"]
    },
    {
      "id": "clean_orders",
      "name": "Clean Orders",
      "type": "transformation",
      "operation": "filter",
      "description": "Remove invalid orders",
      "schema_info": {
        "order_id": {"type": "string", "description": "Unique order ID"},
        "total":    {"type": "decimal", "description": "Order total in USD"}
      }
    },
    {
      "id": "revenue_report",
      "name": "Revenue Dashboard",
      "type": "sink",
      "description": "Tableau dashboard"
    }
  ],
  "edges": [
    {"from": "raw_orders",  "to": "clean_orders",   "relationship_type": "produces"},
    {"from": "clean_orders", "to": "revenue_report", "relationship_type": "powers"}
  ]
}
```

**Node types:** `source` | `transformation` | `sink`

**Operations:** `filter` | `join` | `aggregation` | `projection` | `sort` | `deduplicate` | `union` | `custom`

---

## 🎮 How to Use

### 1. Load a Sample Pipeline
Click any sample in the **Upload Panel** (left sidebar) — "E-Commerce Order Pipeline" or "Spark ETL Pipeline" loads instantly.

### 2. Upload Your Own DAG
- Drag-and-drop a `.json` file onto the upload zone
- Or use the JSON Editor tab to paste your DAG

### 3. Explore Lineage
- Click any node in the graph
- Use the **Right Sidebar** to run: **Upstream / Downstream / Full Lineage / Impact Analysis**
- Highlighted nodes: 🔵 Blue = Upstream, 🟢 Green = Downstream, 🔴 Red = Selected, 🟡 Amber = Impact

### 4. Export Reports
With a lineage result loaded, click **Export → JSON** or **Export → PDF**.

### 5. Performance Test with Large DAG
```bash
cd database
python generate_large_dag.py
# Generates large_dag.json (~900 nodes, ~1500 edges)
# Upload it via the UI's file uploader
```

---

## 🧪 Testing

```bash
cd backend

# Run all 50 tests
pytest tests/ -v

# Run only graph algorithm tests (no DB needed)
pytest tests/test_graph_service.py -v

# Run only API tests
pytest tests/test_api.py -v

# With coverage report
pip install pytest-cov
pytest tests/ --cov=. --cov-report=term-missing
```

**Test Coverage:**

| Module | Tests | Coverage |
|---|---|---|
| DAG Validation (cycle, self-loop, duplicates) | 7 tests | ✅ Full |
| Upstream Lineage | 5 tests | ✅ Full |
| Downstream Lineage | 4 tests | ✅ Full |
| Full Lineage | 3 tests | ✅ Full |
| Impact Analysis | 5 tests | ✅ Full |
| Path Finding | 3 tests | ✅ Full |
| Graph Statistics | 3 tests | ✅ Full |
| Large Graph Performance | 1 test | ✅ <5s |
| API Endpoints (Health, Upload, CRUD) | 8 tests | ✅ Full |
| API Lineage Endpoints | 5 tests | ✅ Full |
| API Impact + Delete | 4 tests | ✅ Full |

---

## 🔥 Advanced Features

### Caching
Lineage results are cached in the `lineage_cache` table. Subsequent queries for the same `(dag_id, node_id, lineage_type)` are served from cache. Cache is invalidated on DAG re-upload or deletion.

```bash
# Cache hit indicator in API response:
{ "from_cache": true, ... }
```

### Versioned DAGs
Each DAG upload creates a new record. The **Version Panel** (bottom of left sidebar) lets you switch between DAG versions and compare lineage across them.

### Column-Level Lineage
Include `column_mapping` on edges and `schema_info` on nodes to enable column-level tracing:

```json
{
  "edges": [{
    "from": "raw_orders",
    "to": "clean_orders",
    "column_mapping": {
      "order_id": "id",
      "customer_email": "email"
    }
  }]
}
```

### Cycle Detection
Uploading a cyclic DAG returns a 422 error with the exact cycle path:
```json
{
  "error": "Invalid DAG structure",
  "message": "Cycle detected: A → B → C → A",
  "cycle_path": ["A", "B", "C", "A"]
}
```

---

## 🧮 Algorithm Details

### Upstream Lineage
Uses **BFS on the reversed graph**. NetworkX's `ancestors()` internally performs this traversal in O(V + E).

```python
ancestors = nx.ancestors(G, node_id)    # O(V + E)
```

### Downstream Lineage
Uses **BFS on the original graph** from the target node:
```python
descendants = nx.descendants(G, node_id)  # O(V + E)
```

### Impact Analysis
1. Find all descendants (O(V + E))
2. Compute `impact_score = len(descendants) / (total_nodes - 1)`
3. Classify: `< 0.25 = LOW`, `0.25–0.5 = MEDIUM`, `0.5–0.75 = HIGH`, `> 0.75 = CRITICAL`

### Path Finding
Uses **DFS with backtracking** (`nx.all_simple_paths`) — capped at 100 paths for performance:
```python
paths = list(nx.all_simple_paths(G, source, target, cutoff=50))
```

### Cycle Detection
Uses NetworkX's `find_cycle()` which runs a **DFS** and looks for back edges:
```python
cycle_edges = nx.find_cycle(G, orientation="original")
```

---

## 🔧 Troubleshooting

**Backend won't start:**
```bash
# Check Python version
python --version  # Must be 3.10+

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**"No such table: dags" error:**
The app auto-creates tables on startup via `init_db()`. If this fails:
```bash
# Check if SQLite file has write permissions
ls -la data_lineage.db

# Or manually trigger DB init
python -c "from database import init_db; init_db()"
```

**Frontend can't connect to backend:**
```bash
# Verify backend is running
curl http://localhost:8000/health

# Check CORS — ensure both servers on expected ports:
# Backend: 8000, Frontend: 5173
```

**Cytoscape graph not rendering:**
```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

**Large DAG is slow:**
- Results are cached after first computation
- The 1000-node test runs in < 5 seconds
- For DAGs > 5000 nodes, consider enabling PostgreSQL for better connection pooling

---

## 👨‍💻 Author

**Rishu** — Final Year B.Tech CSE (Data Science)
Dayananda Sagar Academy of Technology and Management (DSATM), Bengaluru

Built as a comprehensive demonstration of:
- Graph algorithms (BFS, DFS, DAG traversal)
- REST API design with FastAPI
- Database design and ORM
- React frontend with Cytoscape.js visualization
- Data engineering pipeline concepts

---

## 📜 License

MIT License — free to use for academic and portfolio purposes.
