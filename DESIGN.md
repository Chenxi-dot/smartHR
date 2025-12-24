# System Design Document - Smart HR

## 1. Overview
Smart HR is an intelligent resume screening system designed to match candidate resumes with job descriptions using a combination of semantic analysis and rule-based filtering.

## 2. Architecture
The system follows a modular architecture:

- **Data Layer (`src/data_loader.py`)**: Handles loading of Parquet files for Candidates and Job Descriptions.
- **Preprocessing Layer (`src/preprocessor.py`)**: Cleans text, extracts structured features (Experience Years, Education Level, English Proficiency).
- **Matching Engine (`src/matcher.py`)**: The core logic that computes compatibility scores.
- **Web Interface (`app.py`)**: A Flask-based UI for user interaction.

## 3. Core Modules

### 3.1 Preprocessor
- **Text Cleaning**: Lowercasing, removing special characters.
- **Experience Parsing**: regex-based extraction of years from strings like "3-5 years".
- **Education/English Scoring**: Mapping text labels (e.g., "Master", "Fluent") to numerical scores (0-5) for comparison.

### 3.2 Matching Algorithm
The matching score is a weighted sum of four components:

1.  **Semantic Similarity (50%)**: 
    - Uses TF-IDF (Term Frequency-Inverse Document Frequency) to vectorize text.
    - Computes Cosine Similarity between Job Description and Candidate CV.
    - Captures keyword overlap and general context.

2.  **Experience Match (30%)**:
    - Full score if candidate experience >= minimum requirement.
    - Linear penalty for experience below requirement.

2.5 **English Level Match (Hard Filter)**:
    - Candidate English level is normalized into: `basic`, `pre`, `intermediate`, `upper`, `fluent`.
    - If JD specifies a required `english_level`, candidate must have level >= required level.

3.  **Education Match (10%)**:
    - Compares education level scores (e.g., PhD=5, Bachelor=3).
    - Penalty for being under-qualified.

4.  **English Proficiency (10%)**:
    - Compares language level scores.

### 3.3 Web Application
- **Stack**: Python, Flask, Bootstrap 5.
- **Features**: Job selection, Candidate matching, CSV Export.

## 4. Performance
- **Batch Processing**: Uses vectorization to handle 100+ candidates efficiently.
- **Scalability**: Designed to load data into memory; for production with millions of records, a Vector Database (like Chroma or Milvus) would be recommended.
