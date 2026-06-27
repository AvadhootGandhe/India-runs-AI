# Candidate Retrieval Stage

CPU-only semantic retrieval for the Redrob candidate ranking hackathon.

This stage does only:

1. Build candidate text from allowed profile, career, skill, education, and certification fields.
2. Build JD query text from structured JSON or DOCX job descriptions.
3. Encode with `intfloat/e5-small-v2` using correct E5 prefixes.
4. Save embeddings and IDs.
5. Build a FAISS inner-product index over normalized vectors.
6. Retrieve top-k candidate IDs for a JD.

Redrob behavioral signals are deliberately excluded from candidate embeddings. Use them later in reranking.

## Folder Structure

```text
.
├── requirements.txt
├── README.md
└── src/
    └── retrieval_stage/
        ├── __init__.py
        ├── cli.py
        ├── config.py
        ├── embeddings.py
        ├── faiss_index.py
        ├── io_utils.py
        └── text_builders.py
```

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On Linux/macOS, use `source .venv/bin/activate` instead.

## Input Format

Candidates can be:

- JSONL: one candidate object per line
- JSON: either a list of candidate objects, a single candidate object, or an object containing a `candidates` list

JD files can be:

- `.docx`
- `.json`

The provided JD is a structured DOCX. `JDTextBuilder` preserves headings and bullets and emphasizes title, company, location, experience, must-have skills, responsibilities, disqualifiers, logistics, and ideal-candidate hints.

## Commands

Run commands from the repository root with `PYTHONPATH=src`, or install the package in editable mode if you add packaging later.

PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m retrieval_stage.cli embed-candidates --candidates candidates.jsonl --out-dir artifacts
python -m retrieval_stage.cli build-index --artifacts-dir artifacts
python -m retrieval_stage.cli search --jd-file job_description.docx --artifacts-dir artifacts --top-k 1000 --out-file artifacts/top_1000.csv
```

Bash:

```bash
PYTHONPATH=src python -m retrieval_stage.cli embed-candidates --candidates candidates.jsonl --out-dir artifacts
PYTHONPATH=src python -m retrieval_stage.cli build-index --artifacts-dir artifacts
PYTHONPATH=src python -m retrieval_stage.cli search --jd-file job_description.docx --artifacts-dir artifacts --top-k 1000 --out-file artifacts/top_1000.csv
```

## Serialization

`artifacts/` contains:

- `candidate_embeddings.npy`: `float32` matrix, shape `(num_candidates, 384)`
- `candidate_ids.csv`: row-aligned candidate IDs
- `candidate_texts.jsonl`: optional audit trail of generated candidate text
- `faiss.index`: FAISS index
- `metadata.json`: model/index metadata
- `top_1000.csv`: search output with `rank`, `candidate_id`, and `score`

## FAISS Configuration

Default index: `IndexFlatIP`.

The code normalizes embeddings, so inner product equals cosine similarity. For 100k candidates this exact index is simple, reliable, and fast enough on CPU. Approximate indexes such as IVF are unnecessary unless the dataset grows into the millions.

## Memory Estimates

`intfloat/e5-small-v2` outputs 384-dimensional `float32` vectors.

- One embedding: `384 * 4 = 1,536 bytes`
- 100k embeddings: about `153.6 MB`
- FAISS flat index: about another `153.6 MB`, plus small overhead
- IDs CSV and metadata: tiny
- Candidate text audit file: depends on text length, often `100-300 MB`
- Model runtime RAM on CPU: commonly `1-2 GB`

Recommended machine: `8 GB RAM` minimum, `16 GB RAM` comfortable.

## Recommended Batch Sizes

CPU batch size depends on cores and RAM.

- Conservative laptop: `32`
- Typical 8-16 GB machine: `64`
- Larger CPU workstation: `128`

Start with `64`. If RAM spikes or encoding slows due to swapping, lower it to `32`.

## Notes On E5 Usage

E5 expects prefixes:

- Candidates: `passage: <candidate_text>`
- Job descriptions: `query: <jd_text>`

Embeddings are L2-normalized before indexing and search.
