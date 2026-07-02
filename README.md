# India-runs-AI

Candidate discovery, anomaly detection, ranking, and graph visualization pipeline for the Redrob Intelligent Candidate Discovery & Ranking Challenge.

The repository contains:

- A CPU-only semantic retrieval pipeline using `sentence-transformers` E5 embeddings and FAISS.
- A candidate honeypot/suspicion detector.
- A LightGBM + SHAP reranker that creates the final top-100 `submission.csv`.
- A React/Vite graph visualization for candidate similarity data.
- Challenge reference files and validation utilities under `redrob_docs/`.

## Project Structure

```text
.
├── src/retrieval_stage/          # Reusable semantic retrieval package
│   ├── cli.py                    # CLI entry point
│   ├── config.py                 # Retrieval defaults
│   ├── embeddings.py             # E5 embedding generation
│   ├── faiss_index.py            # FAISS index build/search
│   ├── io_utils.py               # Candidate JSON/JSONL helpers
│   └── text_builders.py          # Candidate/JD text rendering
├── artifacts/                    # Generated retrieval artifacts
│   ├── candidate_embeddings.npy
│   ├── candidate_ids.csv
│   ├── candidate_texts.jsonl
│   ├── faiss.index
│   ├── metadata.json
│   └── top_1000.csv
├── graph-viz/                    # React graph visualization app
├── redrob_docs/                  # Challenge docs, sample data, validator
├── candidates.jsonl              # Full candidate dataset
├── rank.py                       # Final top-100 ranker
├── flag_profiles.py              # Suspicious/honeypot profile detector
├── filterrecords.py              # Builds candidate_nodes.json from sample_100.jsonl
├── graph.py                      # Extracts first 100 candidates into first100.jsonl
├── test2.py                      # Builds graphical_representation.json
├── requirements.txt              # Python dependencies
└── submission.csv                # Generated final submission
```

## Requirements

* Python 3.10+ recommended
* Node.js 18+ recommended for the graph viewer
* Git LFS if cloning/downloading through Git, because large files are tracked as LFS: *.jsonl, *.npy, *.index

## Python Setup
### Windows PowerShell
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install lightgbm shap
$env:PYTHONPATH = "src"
```

### macOS/Linux
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install lightgbm shap
export PYTHONPATH=src
```

## Run Semantic Retrieval Using Existing Artifacts

The `artifacts/` folder already contains embeddings, candidate IDs, and a FAISS index for 100,000 candidates.

```powershell
python -m retrieval_stage.cli search `
  --jd-file redrob_docs/job_description.docx `
  --artifacts-dir artifacts `
  --top-k 1000 `
  --out-file artifacts/top_1000.csv
```

for macOS/Linux

```
python -m retrieval_stage.cli search \
  --jd-file redrob_docs/job_description.docx \
  --artifacts-dir artifacts \
  --top-k 1000 \
  --out-file artifacts/top_1000.csv
```

Output: `artifacts/top_1000.csv`

## Rebuild Retrieval Artifacts From Scratch

This regenerates candidate embeddings, the FAISS index, and the top-k semantic retrieval file.

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

The embedding stage uses CPU and may take time on the `full candidates.jsonl` file.

## Preview Job Description Text

The retrieval pipeline converts `.docx`, `.json`, `.txt`, or `.md` job descriptions into normalized query text.

```powershell
python -m retrieval_stage.cli preview-jd --jd-file redrob_docs/job_description.docx
```

## Detect Suspicious or Honeypot Profiles

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

## Generate Final Submission

```powershell
python rank.py `
  --candidates candidates.jsonl `
  --flagged artifacts/flagged.csv `
  --out submission.csv `
  --top-k 1000 `
  --debug
```

Output:
`submission.csv`

Format:
`candidate_id,rank,score,reasoning`
It contains exactly 100 ranked candidates.

## Validate Submission

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

Create graphical_representation.json from candidate_nodes.json:
```powershell
python test2.py
```

The React app loads this file from:
`graph-viz/public/graphical_representation.json`

## Run Graph Visualization

```powershell
cd graph-viz
npm install
npm run dev
```

Then open locally: `http://localhost:5173`

Build production assets:
```powershell
Build production assets:
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

# 4. Generate final submission
python rank.py --candidates candidates.jsonl --flagged artifacts/flagged.csv --out submission.csv --top-k 1000 --debug

# 5. Validate final CSV
python redrob_docs/validate_submission.py submission.csv
```


