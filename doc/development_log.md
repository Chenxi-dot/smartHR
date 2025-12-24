# Development Log - Intelligent Resume Screening System (Data Engineer)

## Phase 1: Framework & Core Implementation
- **Architecture Design**: Created `framework_design.md` outlining the 5-layer architecture (Data, Storage, Query, Matching, Application).
- **Core Modules**:
  - `data_loader.py`: Implemented loading from parquet and filtering for "2D artist".
  - `llm_processor.py` (Deprecated): Initial TF-IDF/Heuristic implementation.
  - `vector_store.py`: Hybrid vector store (ChromaDB + In-memory fallback) using TF-IDF vectors.
  - `matcher.py`: Core matching logic with Hard/Soft scoring.
- **Web App**: `app.py` and `templates/index.html` for basic demo.

## Phase 2: Verification & Enhancement
- **Vectorization**: Confirmed use of `TfidfVectorizer` (scikit-learn) and `cosine_similarity` for real semantic operations.
- **LLM**: Transitioned from Regex/Heuristics to real API integration.

## Phase 3: Advanced Integration (Current)
- **ModelScope API Integration**:
  - Replaced `src/llm_processor.py` with `src/llm_service.py`.
  - Implemented `parse_resume` using `Qwen/Qwen2.5-72B-Instruct` via ModelScope API (key: ms-...).
  - Implemented `analyze_jd` for dynamic requirement extraction.
  - Added robust error handling (Proxy bypass, SSL verification skip) for environment compatibility.
- **Caching Mechanism**:
  - Created `src/cache_manager.py` supporting Redis (primary) and SQLite (fallback).
  - Implemented 7-day expiry logic for API results to save costs/time.
- **Matching Algorithm Upgrade**:
  - Implemented multi-dimensional scoring: `Final Score = (Hard Pass Rate * 70%) + (Soft Score * 30%)`.
  - Added anomaly detection for low matching rates.
- **Web UI Upgrade**:
  - Added "TOP 5 Recommendations" dashboard.
  - Implemented Timeline View for work experience.
  - Enhanced candidate cards with match details.
- **Workflow & Optimization**:
  - **Quota Protection**: Limited candidate processing to a maximum of 300 to protect API quotas.
  - **Target Position Change**: Switched target position from "2D artist" to "**Data Engineer**" to leverage a larger dataset (532 candidates), ensuring a more robust demonstration. The system now loads the top 300 Data Engineer candidates.
  - **Enhanced Filtering**: Upgraded filter to be case-insensitive (e.g., catching "Senior Data Engineer").

## Pending Tasks
- [ ] User Acceptance Testing of the new UI.
- [ ] Further tuning of prompt engineering for resume parsing.
- [ ] Redis server setup (currently using SQLite fallback).
