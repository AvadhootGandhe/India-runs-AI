# India-runs-AI

Candidate discovery, anomaly detection, ranking, and graph visualization pipeline for the Redrob Intelligent Candidate Discovery & Ranking Challenge.

The project has four main parts:

- CPU-only semantic retrieval using E5 embeddings and FAISS.
- Honeypot/suspicion detection for candidate profiles.
- Retrieval-gated top-100 ranking using full profile features, LightGBM, and SHAP reasoning.
- React/Vite graph visualization for candidate similarity data.

## Architecture

The final ranker is retrieval-gated: semantic search first narrows the full dataset to `artifacts/top_1000.csv`, then `rank.py` reranks only those retrieved candidate IDs using full profile features, honeypot flags, a rule-based domain score, LightGBM LambdaRank, and SHAP-based reasoning.

```text
candidates.jsonl
      |
      v
src/retrieval_stage/
CandidateTextBuilder + JDTextBuilder
      |
      v
E5 embeddings on CPU
intfloat/e5-small-v2
      |
      v
FAISS index
artifacts/faiss.index
      |
      v
Semantic search against job description
      |
      v
artifacts/top_1000.csv
      |
      |-----------------------------|
      |                             |
      v                             v
rank.py                       flag_profiles.py
reads retrieved IDs           scans full candidates.jsonl
from top_1000.csv             for suspicious/honeypot profiles
      |                             |
      |                             v
      |                       artifacts/flagged.csv
      |                             |
      |-----------------------------|
      v
rank.py loads full profiles
from candidates.jsonl only for
candidate IDs in top_1000.csv
      |
      v
Feature extraction
AI skills, embeddings/vector DB,
LLM/NLP, ranking/IR, experience,
location, behavioral signals,
education, product/consulting fit
      |
      v
Rule-based domain score
      |
      v
LightGBM LambdaRank reranker
trained on pseudo-labels from rule scores
      |
      v
SHAP reasoning generation
      |
      v
submission.csv
top 100 candidates
candidate_id, rank, score, reasoning
```

Graph architecture:

```text
sample_100.jsonl
      |
      v
filterrecords.py
      |
      v
candidate_nodes.json
      |
      v
test2.py
candidate similarity calculation
      |
      v
graphical_representation.json
      |
      v
graph-viz/public/graphical_representation.json
      |
      v
React + Vite graph UI
@xyflow/react + d3-force
      |
      v
Interactive candidate similarity graph
```

## Project Structure

```text
.
|-- src/retrieval_stage/          # Reusable semantic retrieval package
|   |-- cli.py                    # CLI entry point
|   |-- config.py                 # Retrieval defaults
|   |-- embeddings.py             # E5 embedding generation
|   |-- faiss_index.py            # FAISS index build/search
|   |-- io_utils.py               # Candidate JSON/JSONL helpers
|   `-- text_builders.py          # Candidate/JD text rendering
|-- artifacts/                    # Generated retrieval/ranking artifacts
|   |-- candidate_embeddings.npy
|   |-- candidate_ids.csv
|   |-- candidate_texts.jsonl
|   |-- faiss.index
|   |-- metadata.json
|   |-- top_1000.csv
|   `-- flagged.csv
|-- graph-viz/                    # React graph visualization app
|-- redrob_docs/                  # Challenge docs, sample data, validator
|-- candidates.jsonl              # Full candidate dataset
|-- rank.py                       # Final retrieval-gated top-100 ranker
|-- flag_profiles.py              # Suspicious/honeypot profile detector
|-- filterrecords.py              # Builds candidate_nodes.json from sample_100.jsonl
|-- graph.py                      # Extracts first 100 candidates into first100.jsonl
|-- test2.py                      # Builds graphical_representation.json
|-- requirements.txt              # Python dependencies
`-- submission.csv                # Generated final submission
```

## Requirements

- Python 3.10+ recommended.
- Node.js 18+ recommended for the graph viewer.
- Git LFS if cloning/downloading through Git, because large files are tracked as LFS: `*.jsonl`, `*.npy`, `*.index`.

## Python Setup

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:PYTHONPATH = "src"
```

### macOS/Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export PYTHONPATH=src
```

## Workflow

### 1. Generate or Reuse Retrieval Artifacts

The repository can reuse existing files in `artifacts/`, including `candidate_embeddings.npy`, `candidate_ids.csv`, and `faiss.index`.

To run semantic search using existing embeddings/index:

```powershell
python -m retrieval_stage.cli search `
  --jd-file redrob_docs/job_description.docx `
  --artifacts-dir artifacts `
  --top-k 1000 `
  --out-file artifacts/top_1000.csv
```

macOS/Linux:

```bash
python -m retrieval_stage.cli search \
  --jd-file redrob_docs/job_description.docx \
  --artifacts-dir artifacts \
  --top-k 1000 \
  --out-file artifacts/top_1000.csv
```

Output:

```text
artifacts/top_1000.csv
```

### 2. Rebuild Retrieval Artifacts From Scratch

Only run this if you need to regenerate embeddings and the FAISS index.

```powershell
python -m retrieval_stage.cli embed-candidates `
  --candidates candidates.jsonl `
  --out-dir artifacts

python -m retrieval_stage.cli build-index `
  --artifacts-dir artifacts

python -m retrieval_stage.cli search `
  --jd-file redrob_docs/job_description.docx `
  --artifacts-dir artifacts `
  --top-k 1000 `
  --out-file artifacts/top_1000.csv
```

The embedding stage is CPU-only and can take time on the full `candidates.jsonl` file.

### 3. Preview Job Description Text

The retrieval pipeline converts `.docx`, `.json`, `.txt`, or `.md` job descriptions into normalized query text.

```powershell
python -m retrieval_stage.cli preview-jd --jd-file redrob_docs/job_description.docx
```

### 4. Detect Suspicious or Honeypot Profiles

```powershell
python flag_profiles.py `
  --input candidates.jsonl `
  --output artifacts/flagged.csv
```

Strict mode uses tighter thresholds:

```powershell
python flag_profiles.py `
  --input candidates.jsonl `
  --output artifacts/flagged.csv `
  --strict
```

Write only suspicious/honeypot rows:

```powershell
python flag_profiles.py `
  --input candidates.jsonl `
  --output artifacts/flagged.csv `
  --only-flagged
```

If `candidate_nodes.json` exists, this script also creates:

```text
graph-viz/public/candidate_nodes_enriched.json
```

### 5. Generate Final Submission

`rank.py` reads candidate IDs from `artifacts/top_1000.csv` by default, loads full profile records for only those IDs from `candidates.jsonl`, removes `HONEYPOT` profiles from `artifacts/flagged.csv`, and writes the final top-100 submission.

```powershell
python rank.py `
  --candidates candidates.jsonl `
  --retrieval-results artifacts/top_1000.csv `
  --flagged artifacts/flagged.csv `
  --out submission.csv `
  --top-k 1000 `
  --debug
```

`--top-k` controls how many rows are read from the retrieval results before reranking. The default retrieval file is `artifacts/top_1000.csv`, so this shorter command is equivalent:

```powershell
python rank.py `
  --candidates candidates.jsonl `
  --flagged artifacts/flagged.csv `
  --out submission.csv `
  --top-k 1000 `
  --debug
```

Output:

```text
submission.csv
```

Format:

```csv
candidate_id,rank,score,reasoning
```

It contains exactly 100 ranked candidates.

### 6. Validate Submission

```powershell
python redrob_docs/validate_submission.py submission.csv
```

Expected success output:

```text
Submission is valid.
```

## Graph Data Generation

The graph workflow is exploratory and uses sample candidate data.

Create `candidate_nodes.json` from `sample_100.jsonl`:

```powershell
python filterrecords.py
```

Create `graphical_representation.json` from `candidate_nodes.json`:

```powershell
python test2.py
```

The React app loads this file from:

```text
graph-viz/public/graphical_representation.json
```

If you regenerate `graphical_representation.json` at the repository root, copy it into `graph-viz/public/graphical_representation.json` before starting the graph app.

## Run Graph Visualization

```powershell
cd graph-viz
npm install
npm run dev
```

Then open:

```text
http://localhost:5173
```

Build production assets:

```powershell
npm run build
```

Preview production build:

```powershell
npm run preview
```

Lint frontend code:

```powershell
npm run lint
```

## Main Pipeline Summary

```powershell
# 1. Activate Python environment and set PYTHONPATH
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"

# 2. Optional: rebuild retrieval artifacts
python -m retrieval_stage.cli embed-candidates --candidates candidates.jsonl --out-dir artifacts
python -m retrieval_stage.cli build-index --artifacts-dir artifacts
python -m retrieval_stage.cli search --jd-file redrob_docs/job_description.docx --artifacts-dir artifacts --top-k 1000 --out-file artifacts/top_1000.csv

# 3. Flag suspicious profiles
python flag_profiles.py --input candidates.jsonl --output artifacts/flagged.csv

# 4. Generate final submission from retrieved top-1000 pool
python rank.py --candidates candidates.jsonl --retrieval-results artifacts/top_1000.csv --flagged artifacts/flagged.csv --out submission.csv --top-k 1000 --debug

# 5. Validate final CSV
python redrob_docs/validate_submission.py submission.csv
```

## Notes

- `rank.py` is retrieval-gated and should be run after `artifacts/top_1000.csv` exists.
- `rank.py` still needs `candidates.jsonl` because `top_1000.csv` only stores IDs and retrieval scores, while final ranking needs full profile fields.
- `flag_profiles.py` labels candidates as `CLEAN`, `SUSPICIOUS`, or `HONEYPOT`; `rank.py` skips only `HONEYPOT` candidates.
- Large files are tracked with Git LFS. If a cloned `.jsonl`, `.npy`, or `.index` file is unexpectedly tiny, run `git lfs pull`.
