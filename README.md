# Smart HR - Intelligent Resume Screening System

Smart HR is an AI-powered recruitment tool designed to automate the screening of candidate resumes against Job Descriptions (JDs). It utilizes a hybrid approach combining traditional information retrieval techniques (TF-IDF) with Large Language Models (LLM) to provide accurate, explainable, and efficient candidate matching.

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- A ModelScope API Key (for Qwen LLM)

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/Chenxi-dot/smartHR.git
    git clone git@github.com:Chenxi-dot/smartHR.git
    cd smartHR
    ```

2.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up Environment Variables**
    You can set these in your terminal or create a `.env` file (if supported by your runner, otherwise export them).
    ```bash
    export QWEN_API_KEY="your_modelscope_api_key"
    # Optional: Adjust performance/cost limits
    export MAX_CANDIDATES=50000      # Number of candidates to load from parquet
    export STAGE2_LIMIT=5            # Number of candidates to send to LLM for deep analysis
    export QWEN_TIMEOUT=8            # Timeout for LLM calls in seconds
    ```

4.  **Run the Application**
    ```bash
    # Development mode
    python app.py

    # Production mode (using Gunicorn)
    gunicorn app:app --bind 0.0.0.0:8000 --workers 2 --timeout 120
    ```

5.  **Access the UI**
    Open your browser and navigate to `http://localhost:5000` (or port 8000 if using Gunicorn).

---

## 🧠 Core Logic & Workflow

The system operates on a **Two-Stage Matching Pipeline** to balance speed and accuracy.

### 1. Data Loading & Caching
- **Source**: Candidate data is loaded from `candidates.parquet` (Djinni Dataset).
- **Optimization**: The `DataLoader` implements a singleton pattern with in-memory caching. The heavy Parquet file is read only once per worker process, ensuring subsequent requests are instant.

### 2. Job Description Analysis (LLM)
- When a user submits a JD, the system uses **Qwen-2.5-72B-Instruct** (via ModelScope) to analyze the text.
- **Extraction**: It extracts `Hard Requirements` (Years of Exp, English Level, Tech Skills) and `Soft Requirements` (Communication, Leadership).

### 3. Stage 1: Fast Screening (TF-IDF + Rules)
- **Goal**: Quickly filter thousands of candidates down to a manageable shortlist (e.g., Top 50).
- **Methods**:
    - **Keyword Matching**: TF-IDF vectorization compares the JD's keywords with candidate profiles.
    - **Hard Filters**: Checks for minimum experience years and English proficiency (e.g., "Upper-Intermediate").
    - **Scoring**: A weighted score is calculated based on Skill Overlap (50%), Intent Match (30%), Experience (10%), and English Level (10%).

### 4. Stage 2: Deep Evaluation (LLM)
- **Goal**: Provide human-like reasoning for the top candidates.
- **Process**: The top `STAGE2_LIMIT` (default 5-10) candidates from Stage 1 are sent to the LLM.
- **Analysis**: The LLM reads the full candidate profile and the JD to generate:
    - A **Fit Score** (0-100).
    - **Strengths & Risks** analysis.
    - A final **Verdict**.
- **Performance**: To prevent timeouts, this stage has strict time budgets and concurrency limits.

### 5. Result Presentation
- The UI displays a **Progress Bar** (polled via AJAX) to keep the user informed.
- **Top Recommendations**: The best matches are shown with detailed LLM-generated explanations.
- **Full List**: A broader list of candidates from Stage 1 is also provided.

---

## 📂 Project Structure

```text
smartHR/
├── app.py                 # Flask Web Application entry point
├── candidates.parquet     # Dataset file (Djinni CVs)
├── requirements.txt       # Python dependencies
├── src/
│   ├── data_loader.py     # Handles data loading, caching, and preprocessing
│   ├── llm_service.py     # Interface for Qwen LLM (using OpenAI SDK)
│   ├── matcher.py         # Core matching engine (Stage 1 & Stage 2 logic)
│   ├── cache_manager.py   # Caching utilities (SQLite/Redis)
│   └── vector_store.py    # Vector storage logic (TF-IDF/Chroma)
├── templates/
│   └── index.html         # Frontend UI (Bootstrap + AJAX)
└── ... (Documentation files)
```

---

## ⚙️ Configuration

| Environment Variable | Default | Description |
|----------------------|---------|-------------|
| `QWEN_API_KEY`       | *Required* | API Key for ModelScope/DashScope. |
| `QWEN_MODEL`         | `Qwen/Qwen2.5-7B-Instruct` | The model version to use. |
| `MAX_CANDIDATES`     | `50000` | Max rows to load from Parquet (RAM usage control). |
| `STAGE1_LIMIT`       | `20`    | Number of candidates to pass to Stage 2. |
| `STAGE2_LIMIT`       | `5`     | Max candidates to fully analyze with LLM (Cost/Time control). |
| `STAGE2_MAX_SECONDS` | `8`     | Time budget for the deep analysis phase. |
| `QWEN_TIMEOUT`       | `8`     | Read timeout for individual LLM requests. |

## 📖 Documentation

For more detailed information about the project design, development logs, and dataset specifics, please refer to the documents in the `doc/` folder:

- **[Design Document](doc/DESIGN.md)**: System architecture and design decisions.
- **[Project Documentation](doc/PROJECT_DOC.md)**: User requirements and project goals.
- **[Technical Documentation](doc/TECHNICAL_DOC.md)**: Implementation details and module descriptions.
- **[Development Log](doc/development_log.md)**: Chronological log of development progress.
- **[Core Intro](doc/core_intro.md)**: Introduction to the core logic.
- **[Dataset Info (Candidates)](doc/candidates_info.md)**: Details about the candidates dataset.
- **[Dataset Info (Jobs)](doc/job_description_info.md)**: Details about the job descriptions dataset.

---

## 📚 Dataset & Credits

This project uses the **Djinni Recruitment Dataset**, which contains anonymized developer CVs and job descriptions.
- **Source**: [HuggingFace - Djinni Recruitment Dataset](https://huggingface.co/datasets/lang-uk/recruitment-dataset-candidate-profiles-english)
- **License**: MIT

## 🛠 Technical Highlights
- **Robustness**: Handles API timeouts and failures gracefully.
- **Efficiency**: Uses in-memory caching to avoid repeated disk I/O.
- **User Experience**: Real-time progress tracking prevents the "hanging browser" feeling during long LLM operations.
