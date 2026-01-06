## 🏗️ System Architecture

```mermaid
graph TD
    %% --- STYLING ---
    classDef frontend fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1;
    classDef backend fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20;
    classDef database fill:#fff3e0,stroke:#e65100,stroke-width:2px,stroke-dasharray: 5 5,color:#e65100;
    classDef external fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;
    classDef user fill:#fff,stroke:#333,stroke-width:2px;

    %% --- ACTORS & EXTERNAL ---
    User((👤 User / Planner)):::user
    Shapefile_Input[📄 .zip Shapefile]:::external

    %% --- FRONTEND LAYER ---
    subgraph "Frontend Presentation Layer (Browser)"
        HTML_CSS[HTML Templates & Glassmorphism CSS]:::frontend
        AppJS["⚙️ app.js (Client Logic)"]:::frontend
        Leaflet["🗺️ Leaflet.js & Mapbox Tiles"]:::frontend
        TurfJS["📐 Turf.js (Client GIS)"]:::frontend
        GCharts["📊 Google Charts"]:::frontend
    end

    %% --- BACKEND LAYER ---
    subgraph "Backend Application Layer (Python/FastAPI)"
        FastAPI["🚀 main.py (FastAPI Server)"]:::backend
        SessionMgr["🔑 Session Manager (Cookies)"]:::backend
        API_Routes["🌐 API Routes\n(/api/resources, /api/add, etc.)"]:::backend
        Upload_Route["📤 Route: /upload"]:::backend
    end

    %% --- PROCESSING LAYER ---
    subgraph "GIS Processing Core (Python)"
        Utils["🧠 utils.py (Logic Core)"]:::backend
        GeoPandas["🐼 GeoPandas & Shapely"]:::backend
        RangeAlgo["📏 Dynamic Range Algorithm"]:::backend
    end

    %% --- DATABASE LAYER ---
    subgraph "Data Persistence Layer"
        SQLAlchemy["🏛️ SQLAlchemy ORM\n(database.py, models.py)"]:::database
        DB[("🗄️ Turso (libSQL) / SQLite")]:::database
    end

    %% --- FLOWS ---
    %% User Interactions
    User <-->|Interacts & Views| HTML_CSS
    User -->|Uploads GIS Data| Shapefile_Input

    %% Frontend Internal
    HTML_CSS --> AppJS
    AppJS -->|Draws Map| Leaflet
    AppJS -->|Client-side buffering/unions| TurfJS
    AppJS -->|Renders Stats| GCharts

    %% Frontend to Backend API
    AppJS <-->|HTTP fetch (JSON)| API_Routes

    %% Shapefile Upload Flow (The Heavy Lifting)
    Shapefile_Input -->|POST Form Data| Upload_Route
    Upload_Route -->|Passes file path & session| Utils
    Utils -->|Parses & Reprojects CRS| GeoPandas
    GeoPandas -->|Extracted Geometry Data| Utils
    Utils -->|Saves GIS Objects| SQLAlchemy

    %% Backend Internal & DB Interaction
    FastAPI --> SessionMgr
    FastAPI --> API_Routes
    FastAPI --> Upload_Route
    API_Routes <-->|Query & Save Data| SQLAlchemy
    SQLAlchemy <-->|Read/Write| DB

    %% Dynamic Range Calc Flow
    API_Routes -->|Request Calculation on read| RangeAlgo
    RangeAlgo -->|Returns Calculated Radius| API_Routes

    %% Export Flow
    API_Routes -->|GET /api/export_shp| Utils
    Utils -->|Converts DB data to .shp/.zip| FastAPI
    FastAPI -->|Returns .zip file| User
