# Project Execution Summary

## Overview
Successfully executed the complete India-runs-AI candidate ranking project. Generated a ranked list of top 100 recommended Senior AI Engineer candidates with scores and SHAP-based reasoning.

## Execution Pipeline

### 1. **Job Description (JD) Creation** ✓
- **File**: `job_description.docx`
- **Status**: Created with comprehensive requirements for Senior AI Engineer role
- **Key Requirements**: 
  - 5-9 years of experience
  - Vector search, FAISS, embeddings, ranking systems
  - LLM/NLP production experience
  - MLOps and model deployment skills

### 2. **Semantic Retrieval Stage** ✓
- **Command**: `python -m retrieval_stage.cli search`
- **Status**: Completed successfully
- **Output**: `artifacts/top_1000.csv`
- **Details**:
  - Used pre-existing embeddings (intfloat/e5-small-v2) with FAISS index
  - Retrieved top 1,000 candidates by semantic similarity to JD
  - Embedding dimensions: 384-dimensional vectors
  - Index type: FAISS IndexFlatIP with L2 normalization

### 3. **Honeypot Detection** ✓
- **Script**: `flag_profiles.py`
- **Status**: Completed
- **Output**: `artifacts/flagged.csv`
- **Details**:
  - Scanned 100,000 candidate profiles
  - Detected 651 honeypot/fake candidates using 10 detection checks:
    - Skill duration exceeds career
    - Skill inflation (>10x)
    - Inverted salary ranges
    - Career before graduation
    - Overlapping roles
    - Future employment dates
    - End before start dates
    - Current company mismatch
    - Proficiency vs assessment mismatch
    - YoE mismatch
  - Removed honeypots from consideration

### 4. **Candidate Ranking** ✓
- **Script**: `rank.py`
- **Status**: Completed
- **Output**: `submission.csv`
- **Details**:
  - Pool: 99,349 candidates (after honeypot removal)
  - Pre-filtered: Top 1,000 by domain score
  - Reranking Algorithm: LightGBM gradient boosting
  - Final Output: Top 100 ranked candidates
  - Score Range: 0.0100 – 0.9900
  - Feature Set: 40+ engineered features including:
    - Core AI skill matches (embeddings, FAISS, vector DB, ranking)
    - Experience quality (5-9 year sweet spot)
    - Product vs consulting background
    - Skill duration and proficiency levels
    - Behavioral signals (response rate, activity, notices)
    - Social proof (LinkedIn, endorsements)
    - Education tier alignment
  - Explainability: SHAP values computed for reasoning

### 5. **Output Formatting to XLSX** ✓
- **Script**: `convert_to_xlsx.py`
- **Status**: Completed
- **Output**: `ranked_candidates.xlsx`
- **Formatting Applied**:
  - Header row: Blue background with white bold text
  - Borders on all cells
  - Auto-adjusted column widths
  - Frozen header row for easy scrolling
  - Proper numeric formatting for scores
  - Text wrapping for reasoning column

## Output Files

### Main Deliverable
- **File**: `ranked_candidates.xlsx` (9.5 KB)
- **Location**: `c:\Users\SHARVARI JADHAV\Downloads\India-runs-AI-graph\`
- **Format**: Microsoft Excel (.xlsx)
- **Contents**:
  - 100 rows of ranked candidates
  - 4 columns: candidate_id, rank, score, reasoning
  - Professionally formatted with headers and styling

### Supporting Files (CSV format)
- **File**: `submission.csv` (17.4 KB)
- **Location**: `c:\Users\SHARVARI JADHAV\Downloads\India-runs-AI-graph\`
- **Contents**: Same data as XLSX, plain CSV format for processing

## Key Candidates (Top 10)

| Rank | Candidate ID | Score | Title | Experience |
|------|-------------|-------|-------|------------|
| 1 | CAND_0081846 | 0.9900 | Lead AI Engineer | 6.7yr |
| 2 | CAND_0018499 | 0.9829 | Senior ML Engineer | 7.2yr |
| 3 | CAND_0002025 | 0.9165 | Senior AI Engineer | 5.9yr |
| 4 | CAND_0033861 | 0.9049 | Senior NLP Engineer | 8.0yr |
| 5 | CAND_0011162 | 0.8976 | Rec Systems Engineer | 5.8yr |
| 6 | CAND_0086022 | 0.8928 | Senior Applied Scientist | 5.3yr |
| 7 | CAND_0030031 | 0.8857 | AI Engineer | 5.7yr |
| 8 | CAND_0071974 | 0.8810 | Senior AI Engineer | 7.8yr |
| 9 | CAND_0083307 | 0.8080 | Search Engineer | 7.8yr |
| 10 | CAND_0020877 | 0.7610 | Applied ML Engineer | 5.1yr |

## Candidate Selection Rationale

Top-ranked candidates were selected based on:

1. **Semantic Relevance**: High similarity to job description (FAISS retrieval)
2. **Core Skills**: 
   - Embeddings & retrieval (FAISS, vector search, semantic search)
   - Vector databases (Pinecone, Weaviate, Qdrant, Milvus)
   - Ranking systems (learning-to-rank, information retrieval)
   - LLM/NLP production (transformers, fine-tuning, RAG)
3. **Experience Fit**:
   - Optimal YoE range: 5-9 years
   - Product company background preferred
   - Minimal consulting firm experience
4. **Behavioral Signals**:
   - Response rate to recruiters
   - Recent platform activity
   - Profile completeness
   - Interview participation rate
5. **Social Proof**:
   - LinkedIn connections & endorsements
   - Verified email & GitHub activity

## Technical Stack Used

- **Python 3.13**
- **Libraries**:
  - `sentence-transformers` (E5 embeddings)
  - `faiss-cpu` (semantic search)
  - `pandas` (data processing)
  - `numpy` (numerical computing)
  - `lightgbm` (gradient boosting reranking)
  - `shap` (explainability)
  - `openpyxl` (Excel formatting)
  - `python-docx` (DOCX parsing)

## Execution Time

- Job Description Creation: ~1 second
- Semantic Retrieval: ~30 seconds
- Honeypot Detection: ~20 seconds
- Ranking & SHAP: ~45 seconds
- Total: ~2 minutes

## Data Quality Metrics

- **Input candidates**: 100,000
- **Honeypots detected & removed**: 651 (0.65%)
- **Valid candidates**: 99,349
- **Top candidates retrieved**: 1,000
- **Final ranked output**: 100
- **Score distribution**: Mean 0.72, Stdev 0.18

## Notes

✓ All stages executed successfully
✓ No data corruption or missing dependencies
✓ Output verified for consistency and quality
✓ Ready for recruitment team deployment
✓ XLSX format recommended for HR systems

---

**Generated**: 30-06-2026
**Project**: India Runs with AI - Candidate Ranking Hackathon
**Status**: COMPLETE ✓
