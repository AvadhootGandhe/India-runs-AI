"""
rank.py — Senior AI Engineer candidate ranker for Redrob Hackathon

Produces submission.csv: top-100 candidates ranked with score + SHAP reasoning.

Usage:
    python rank.py --candidates candidates.jsonl --out submission.csv

Optional:
    --flagged   artifacts/flagged.csv   (from flag_profiles.py; auto-runs if omitted)
    --retrieval-results artifacts/top_1000.csv (semantic retrieval pool)
    --top-k     1000                    (pre-filter pool size before reranking)
    --debug                             (print feature stats + top-10 preview)
"""

import json
import csv
import argparse
import sys
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import numpy as np

TODAY = datetime(2026, 6, 25)

# ─── JD ground truth ──────────────────────────────────────────────────────────

# Core skills the JD explicitly requires / values
CORE_AI_SKILLS = {
    # retrieval & search
    "faiss", "vector search", "vector database", "hybrid search", "bm25",
    "elasticsearch", "opensearch", "pinecone", "weaviate", "qdrant", "milvus",
    "sentence-transformers", "sentence transformers", "dense retrieval",
    "semantic search", "embedding", "embeddings",
    # ranking / rec
    "learning to rank", "lambdarank", "listwise", "pairwise", "ndcg",
    "recommendation system", "ranking system", "information retrieval",
    # LLM / NLP
    "llm", "large language model", "fine-tuning", "fine tuning", "lora", "qlora",
    "peft", "rag", "retrieval augmented", "nlp", "natural language processing",
    "transformers", "bert", "gpt", "t5", "llama", "mistral",
    # MLOps / production
    "mlflow", "weights & biases", "wandb", "kubeflow", "ray", "triton",
    "model serving", "onnx", "tensorrt",
    # general ML
    "pytorch", "tensorflow", "scikit-learn", "xgboost", "lightgbm",
    "neural network", "deep learning", "machine learning",
}

# Skills explicitly NOT wanted (CV, speech, robotics focus)
NON_FIT_SKILLS = {
    "computer vision", "image classification", "object detection", "yolo",
    "resnet", "cnn", "convolutional", "speech recognition", "asr",
    "text to speech", "tts", "robotics", "ros", "slam",
    "video understanding", "action recognition",
}

# Consulting firm disqualifiers (pure-services background)
CONSULTING_FIRMS = {
    "tcs", "tata consultancy", "infosys", "wipro", "accenture",
    "cognizant", "capgemini", "hcl", "tech mahindra", "mphasis",
    "hexaware", "l&t infotech", "ltimindtree", "birlasoft",
    "niit technologies", "zensar", "mastech",
}

# India tier-1 cities (location fit)
INDIA_TIER1 = {
    "pune", "noida", "hyderabad", "mumbai", "delhi", "bengaluru",
    "bangalore", "gurugram", "gurgaon", "chennai", "india",
}

# ─── Feature engineering ───────────────────────────────────────────────────────

def _months_since(date_str):
    """How many months ago was this date? Returns -1 if unparseable."""
    if not date_str:
        return -1
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return max(0, (TODAY.year - d.year) * 12 + (TODAY.month - d.month))
    except ValueError:
        return -1


def _normalise(text):
    return text.lower().strip() if text else ""


def _skill_set(candidate):
    return {_normalise(s.get("name", "")) for s in candidate.get("skills", [])}


def _career_company_types(candidate):
    """Returns (product_months, consulting_months, total_months)."""
    product_months = consulting_months = total_months = 0
    for r in candidate.get("career_history", []):
        dur = r.get("duration_months") or 0
        company_lower = _normalise(r.get("company", ""))
        total_months += dur
        if any(cf in company_lower for cf in CONSULTING_FIRMS):
            consulting_months += dur
        else:
            product_months += dur
    return product_months, consulting_months, total_months


def _has_only_consulting(candidate):
    """True if entire career is at consulting firms — JD hard disqualifier."""
    product_m, consulting_m, total_m = _career_company_types(candidate)
    if total_m == 0:
        return False
    # >85% consulting with no product experience
    return consulting_m / total_m > 0.85 and product_m < 6


def extract_features(candidate):
    """
    Returns a flat feature dict. All features are floats or 0/1 ints.
    Feature names are stable (used by SHAP for reasoning labels).
    """
    profile  = candidate.get("profile", {})
    career   = candidate.get("career_history", [])
    skills   = candidate.get("skills", [])
    edu      = candidate.get("education", [])
    sig      = candidate.get("redrob_signals", {}) or {}

    skill_names = _skill_set(candidate)
    prod_m, cons_m, total_m = _career_company_types(candidate)
    stated_yoe = profile.get("years_of_experience") or 0

    # ── 1. Experience quality ────────────────────────────────────────────────
    yoe_fit = 1.0 if 5 <= stated_yoe <= 9 else (
        0.7 if 4 <= stated_yoe < 5 or 9 < stated_yoe <= 12 else
        0.3 if stated_yoe > 12 else 0.1
    )

    product_ratio   = prod_m / total_m if total_m > 0 else 0
    consulting_ratio = cons_m / total_m if total_m > 0 else 0
    only_consulting  = int(_has_only_consulting(candidate))

    # ── 2. Core AI skill match ───────────────────────────────────────────────
    core_skill_hits = sum(1 for s in skill_names if s in CORE_AI_SKILLS)
    core_skill_ratio = core_skill_hits / max(len(CORE_AI_SKILLS), 1)

    # Expert/advanced core AI skills — weighted higher
    expert_core = sum(
        1 for s in skills
        if _normalise(s.get("name","")) in CORE_AI_SKILLS
        and s.get("proficiency") in ("expert", "advanced")
    )

    # Core AI skill duration (months of verified practice)
    core_skill_duration = sum(
        s.get("duration_months") or 0
        for s in skills
        if _normalise(s.get("name","")) in CORE_AI_SKILLS
    )

    # Non-fit skill penalty
    non_fit_hits = sum(1 for s in skill_names if s in NON_FIT_SKILLS)
    non_fit_penalty = min(non_fit_hits / 3, 1.0)

    # Embedding/retrieval specifically (hard requirement)
    has_embeddings = int(any(
        kw in skill_names or kw in _normalise(profile.get("summary",""))
        for kw in ("embedding", "embeddings", "sentence-transformers",
                   "faiss", "vector search", "dense retrieval", "semantic search")
    ))

    # Vector DB experience
    has_vector_db = int(any(
        kw in skill_names
        for kw in ("faiss", "pinecone", "weaviate", "qdrant", "milvus",
                   "elasticsearch", "opensearch", "vector database", "vector search")
    ))

    # LLM / NLP production signal
    has_llm_nlp = int(any(
        kw in skill_names or kw in _normalise(profile.get("summary",""))
        for kw in ("llm", "large language model", "nlp", "natural language processing",
                   "transformers", "bert", "fine-tuning", "rag")
    ))

    # Ranking / IR experience
    has_ranking_ir = int(any(
        kw in skill_names or kw in _normalise(profile.get("summary",""))
        for kw in ("ranking", "information retrieval", "recommendation",
                   "learning to rank", "ndcg", "search", "retrieval")
    ))

    # ── 3. Assessment scores (platform-verified) ─────────────────────────────
    assessments = sig.get("skill_assessment_scores", {}) or {}
    ai_assessment_scores = [
        v for k, v in assessments.items()
        if any(kw in k.lower() for kw in ("nlp", "llm", "ml", "deep", "transformer",
                                           "retrieval", "embedding", "fine", "language"))
    ]
    avg_ai_assessment   = np.mean(ai_assessment_scores) if ai_assessment_scores else 0
    n_ai_assessments    = len(ai_assessment_scores)

    # ── 4. Location ──────────────────────────────────────────────────────────
    location = _normalise(profile.get("location", ""))
    country  = _normalise(profile.get("country", ""))
    in_india = int("india" in country or any(city in location for city in INDIA_TIER1))
    in_preferred = int(any(city in location for city in ("pune", "noida", "hyderabad",
                                                          "mumbai", "delhi", "bengaluru",
                                                          "bangalore", "gurugram", "gurgaon")))
    willing_relocate = int(sig.get("willing_to_relocate", False) or False)
    location_score = (
        1.0 if in_preferred else
        0.8 if in_india else
        0.5 if willing_relocate else
        0.2
    )

    # ── 5. Behavioral / availability signals ─────────────────────────────────
    open_to_work     = int(sig.get("open_to_work_flag", False) or False)
    response_rate    = sig.get("recruiter_response_rate") or 0
    last_active_m    = _months_since(sig.get("last_active_date"))
    recency_score    = max(0, 1 - last_active_m / 12) if last_active_m >= 0 else 0
    notice_days      = sig.get("notice_period_days") or 90
    notice_score     = 1.0 if notice_days <= 30 else (0.7 if notice_days <= 60 else 0.3)
    github_score     = (sig.get("github_activity_score") or 0) / 100
    interview_rate   = sig.get("interview_completion_rate") or 0
    profile_complete = (sig.get("profile_completeness_score") or 0) / 100

    # ── 6. Career trajectory (progression, not just total) ───────────────────
    n_roles = len(career)
    # Did they hold "senior" / "lead" / "principal" / "staff" titles?
    senior_titles = sum(
        1 for r in career
        if any(kw in _normalise(r.get("title", ""))
               for kw in ("senior", "lead", "principal", "staff", "head", "architect"))
    )
    # ML/AI title signal
    ai_titles = sum(
        1 for r in career
        if any(kw in _normalise(r.get("title", ""))
               for kw in ("ml", "machine learning", "ai", "data scientist",
                          "nlp", "research", "deep learning", "engineer"))
    )

    # ── 7. Research / external validation ────────────────────────────────────
    linkedin_connected = int(sig.get("linkedin_connected", False) or False)
    verified_email     = int(sig.get("verified_email", False) or False)
    endorsements       = min((sig.get("endorsements_received") or 0) / 50, 1.0)

    # ── 8. Education ─────────────────────────────────────────────────────────
    def _parse_tier(t):
        if isinstance(t, (int, float)): return float(t)
        if isinstance(t, str):
            import re as _re; m = _re.search(r"\d+", t)
            return max(0.0, 4.0 - float(m.group())) if m else 0.0
        return 0.0
    edu_tiers = [_parse_tier(e.get("tier", 0)) for e in edu]
    max_edu_tier = max(edu_tiers, default=0.0)
    cs_edu = int(any(
        any(kw in _normalise(e.get("field_of_study", "") + " " + e.get("degree", ""))
            for kw in ("computer", "software", "ai", "machine", "data", "information"))
        for e in edu
    ))

    return {
        # Experience
        "yoe_fit":                yoe_fit,
        "stated_yoe":             float(stated_yoe),
        "product_ratio":          product_ratio,
        "consulting_ratio":       consulting_ratio,
        "only_consulting":        only_consulting,
        "product_months":         float(prod_m),
        # Core AI skills
        "core_skill_hits":        float(core_skill_hits),
        "core_skill_ratio":       core_skill_ratio,
        "expert_core_skills":     float(expert_core),
        "core_skill_duration":    float(core_skill_duration),
        "non_fit_penalty":        non_fit_penalty,
        "has_embeddings":         has_embeddings,
        "has_vector_db":          has_vector_db,
        "has_llm_nlp":            has_llm_nlp,
        "has_ranking_ir":         has_ranking_ir,
        # Assessments
        "avg_ai_assessment":      float(avg_ai_assessment),
        "n_ai_assessments":       float(n_ai_assessments),
        # Location
        "location_score":         location_score,
        "in_india":               in_india,
        "willing_relocate":       willing_relocate,
        # Behavioral
        "open_to_work":           open_to_work,
        "response_rate":          float(response_rate),
        "recency_score":          recency_score,
        "notice_score":           notice_score,
        "github_score":           github_score,
        "interview_rate":         float(interview_rate),
        "profile_complete":       profile_complete,
        # Career trajectory
        "n_roles":                float(n_roles),
        "senior_titles":          float(senior_titles),
        "ai_titles":              float(ai_titles),
        # Social proof
        "linkedin_connected":     linkedin_connected,
        "verified_email":         verified_email,
        "endorsements":           endorsements,
        # Education
        "max_edu_tier":           float(max_edu_tier),
        "cs_edu":                 cs_edu,
    }


# ─── Scoring model ─────────────────────────────────────────────────────────────
# Domain-informed weights — no training data, so we hand-craft a linear scorer
# then use LightGBM to produce a smooth ranking score via DART boosting
# on synthetic relevance labels derived from these weights.

FEATURE_WEIGHTS = {
    # Hard JD signals — very high weight
    "has_embeddings":      3.0,
    "has_vector_db":       2.5,
    "has_ranking_ir":      2.0,
    "has_llm_nlp":         1.8,
    "yoe_fit":             2.0,
    "product_ratio":       2.5,
    "only_consulting":    -5.0,   # hard disqualifier
    # Skill depth
    "expert_core_skills":  1.5,
    "core_skill_hits":     0.8,
    "core_skill_duration": 0.005, # per month
    "avg_ai_assessment":   0.03,  # per score point
    "non_fit_penalty":    -2.0,
    # Location
    "location_score":      1.5,
    "in_india":            0.5,
    "willing_relocate":    0.3,
    # Behavioral availability
    "open_to_work":        1.0,
    "response_rate":       1.5,
    "recency_score":       1.0,
    "notice_score":        0.8,
    "github_score":        0.8,
    "interview_rate":      0.5,
    "profile_complete":    0.4,
    # Career
    "ai_titles":           0.4,
    "senior_titles":       0.3,
    # Social proof
    "endorsements":        0.3,
    "linkedin_connected":  0.2,
    "verified_email":      0.1,
    # Education
    "cs_edu":              0.3,
    "max_edu_tier":        0.1,
}


def compute_rule_score(features):
    """Deterministic domain score — used to generate synthetic labels for LGB."""
    score = sum(features.get(f, 0) * w for f, w in FEATURE_WEIGHTS.items())
    return score


def build_lgb_ranker(candidates_feats, rule_scores):
    """
    Train a LightGBM ranker using rule_scores as pseudo-relevance labels.
    This smooths over the linear scorer and captures non-linear interactions.
    """
    import lightgbm as lgb

    X = np.array([[f[k] for k in sorted(f.keys())] for f in candidates_feats])
    feature_names = sorted(candidates_feats[0].keys())

    # Clip rule scores to [0, 4] relevance levels (LGB needs int labels)
    min_s, max_s = np.min(rule_scores), np.max(rule_scores)
    norm = (rule_scores - min_s) / (max_s - min_s + 1e-9)
    labels = np.clip((norm * 4).astype(int), 0, 4)

    group = [len(X)]  # single query group

    train_data = lgb.Dataset(
        X, label=labels,
        group=group,
        feature_name=feature_names,
        free_raw_data=False,
    )

    params = {
        "objective":       "lambdarank",
        "metric":          "ndcg",
        "ndcg_eval_at":    [10, 50],
        "boosting":        "dart",
        "num_leaves":      31,
        "learning_rate":   0.05,
        "n_estimators":    200,
        "min_child_samples": 5,
        "subsample":       0.8,
        "colsample_bytree": 0.8,
        "verbose":         -1,
        "n_jobs":          -1,
        "seed":            42,
    }

    model = lgb.train(
        params,
        train_data,
        num_boost_round=200,
        valid_sets=[train_data],
        callbacks=[lgb.log_evaluation(period=-1)],
    )

    return model, feature_names, X


# ─── SHAP reasoning ────────────────────────────────────────────────────────────

FEATURE_DESCRIPTIONS = {
    "has_embeddings":      "production embeddings experience",
    "has_vector_db":       "vector DB / hybrid search experience",
    "has_ranking_ir":      "ranking/retrieval/IR experience",
    "has_llm_nlp":         "LLM/NLP background",
    "yoe_fit":             "YoE in target range (5-9yr)",
    "product_ratio":       "product company background",
    "only_consulting":     "pure consulting background (disqualifier)",
    "expert_core_skills":  "expert-level AI skills",
    "core_skill_hits":     "core AI skill count",
    "core_skill_duration": "AI skill practice duration",
    "avg_ai_assessment":   "AI assessment scores",
    "non_fit_penalty":     "CV/speech/robotics focus (non-fit)",
    "location_score":      "India location fit",
    "in_india":            "based in India",
    "willing_relocate":    "willing to relocate",
    "open_to_work":        "actively open to work",
    "response_rate":       "recruiter response rate",
    "recency_score":       "recently active on platform",
    "notice_score":        "short notice period",
    "github_score":        "GitHub activity",
    "interview_rate":      "interview completion rate",
    "profile_complete":    "profile completeness",
    "ai_titles":           "AI/ML job titles",
    "senior_titles":       "senior-level titles",
    "endorsements":        "peer endorsements",
    "linkedin_connected":  "LinkedIn connected",
    "cs_edu":              "CS/AI education",
    "max_edu_tier":        "education tier",
}


def build_reasoning(candidate, features, shap_vals, feature_names, score):
    """
    Build a concise reasoning string from SHAP values.
    Format matches sample_submission.csv style.
    """
    profile  = candidate.get("profile", {})
    sig      = candidate.get("redrob_signals", {}) or {}

    title    = profile.get("current_title", "AI Engineer")
    yoe      = profile.get("years_of_experience", 0)
    location = profile.get("location", "")
    rr       = sig.get("recruiter_response_rate", 0) or 0

    # Top positive SHAP drivers
    shap_pairs = list(zip(feature_names, shap_vals))
    positives  = sorted([(f, v) for f, v in shap_pairs if v > 0.01],
                        key=lambda x: -x[1])[:3]
    negatives  = sorted([(f, v) for f, v in shap_pairs if v < -0.01],
                        key=lambda x: x[1])[:2]

    parts = [f"{title}, {yoe:.1f}yr"]

    if features.get("has_embeddings"):
        parts.append("embeddings/retrieval exp")
    if features.get("has_vector_db"):
        parts.append("vector DB exp")
    if features.get("has_ranking_ir") and "has_embeddings" not in [p.split("/")[0] for p in parts]:
        parts.append("ranking/IR exp")

    for feat, _ in positives:
        desc = FEATURE_DESCRIPTIONS.get(feat, feat)
        if desc not in " ".join(parts):
            parts.append(desc)
        if len(parts) >= 5:
            break

    if negatives:
        feat, _ = negatives[0]
        desc = FEATURE_DESCRIPTIONS.get(feat, feat)
        parts.append(f"[-{desc}]")

    parts.append(f"resp={rr:.2f}")
    if location:
        parts.append(location)

    return "; ".join(parts[:7]) + "."


# ─── Flagging (inline, avoids subprocess) ─────────────────────────────────────

def quick_flag(candidate):
    """Returns (verdict, suspicion_score) using core honeypot checks."""
    career  = candidate.get("career_history", [])
    skills  = candidate.get("skills", [])
    sig     = candidate.get("redrob_signals", {}) or {}

    total_career = sum(r.get("duration_months", 0) or 0 for r in career)
    total_skills = sum(s.get("duration_months", 0) or 0 for s in skills)

    flags = 0
    score = 0.0

    # skill exceeds career
    for s in skills:
        if (s.get("duration_months") or 0) - total_career > 12:
            flags += 1; score += 0.20; break

    # skill inflation >10x
    if total_career > 0 and total_skills / total_career > 10:
        flags += 1; score += 0.15

    # inverted salary
    sal = sig.get("expected_salary_range_inr_lpa", {}) or {}
    mn, mx = sal.get("min") or 0, sal.get("max") or 0
    if mx > 0 and mn > mx:
        flags += 1; score += 0.10

    # career before graduation
    edu = candidate.get("education", [])
    latest_edu = max((e.get("end_year") or 0 for e in edu), default=0)
    if latest_edu:
        for r in career:
            try:
                sy = datetime.strptime(r["start_date"], "%Y-%m-%d").year
                if sy < latest_edu - 2:
                    flags += 1; score += 0.15; break
            except (ValueError, KeyError):
                pass

    # end before start
    for r in career:
        try:
            s = datetime.strptime(r["start_date"], "%Y-%m-%d")
            if r.get("end_date"):
                e = datetime.strptime(r["end_date"], "%Y-%m-%d")
                if e < s:
                    flags += 1; score += 0.25; break
        except (ValueError, KeyError):
            pass

    max_w = 0.20 + 0.15 + 0.10 + 0.15 + 0.25
    suspicion = round(score / max_w, 4)

    verdict = (
        "HONEYPOT"   if (suspicion >= 0.30 or flags >= 3) else
        "SUSPICIOUS" if (suspicion >= 0.12 or flags >= 1) else
        "CLEAN"
    )
    return verdict, suspicion


# ─── I/O ───────────────────────────────────────────────────────────────────────

def iter_candidates(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)
    elif suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        yield from (data if isinstance(data, list) else [data])
    else:
        raise ValueError(f"Unsupported: {suffix}")


def load_external_flags(path: Path):
    """Load pre-computed verdicts from flag_profiles.py output."""
    flags = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            flags[row["candidate_id"]] = row["verdict"]
    return flags


def load_retrieval_candidate_ids(path: Path, limit: int | None = None):
    """Load candidate IDs from the semantic retrieval output."""
    candidate_ids = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            candidate_id = row.get("candidate_id")
            if candidate_id:
                candidate_ids.append(candidate_id)
                if limit is not None and len(candidate_ids) >= limit:
                    break
    return set(candidate_ids)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", "-c", required=True)
    parser.add_argument("--out",        "-o", default="submission.csv")
    parser.add_argument("--flagged",    "-f", default=None,
                        help="Pre-computed flagged.csv from flag_profiles.py")
    parser.add_argument("--retrieval-results", "-r", default="artifacts/top_1000.csv",
                        help="Top candidate CSV from semantic retrieval stage")
    parser.add_argument("--top-k",  type=int, default=1000,
                        help="Max rows to read from retrieval results before reranking (default 1000)")
    parser.add_argument("--debug",  action="store_true")
    args = parser.parse_args()

    in_path  = Path(args.candidates)
    out_path = Path(args.out)
    retrieval_path = Path(args.retrieval_results)

    if not in_path.exists():
        print(f"ERROR: {in_path} not found", file=sys.stderr); sys.exit(1)
    if not retrieval_path.exists():
        print(f"ERROR: {retrieval_path} not found", file=sys.stderr); sys.exit(1)

    retrieval_candidate_ids = load_retrieval_candidate_ids(retrieval_path, limit=args.top_k)
    if not retrieval_candidate_ids:
        print(f"ERROR: {retrieval_path} has no candidate_id rows", file=sys.stderr); sys.exit(1)
    print(f"Loaded {len(retrieval_candidate_ids):,} retrieval candidates from {retrieval_path}")

    # Load external flags if provided
    external_flags = {}
    if args.flagged and Path(args.flagged).exists():
        external_flags = load_external_flags(Path(args.flagged))
        print(f"Loaded {len(external_flags):,} pre-computed flags from {args.flagged}")

    # ── Pass 1: load + feature extraction ────────────────────────────────────
    print(f"Loading candidate profiles from {in_path} ...", flush=True)

    all_candidates = []
    all_features   = []
    all_rule_scores = []
    skipped_honeypot = 0
    skipped_not_retrieved = 0

    for i, c in enumerate(iter_candidates(in_path)):
        cid = c["candidate_id"]
        if cid not in retrieval_candidate_ids:
            skipped_not_retrieved += 1
            continue

        # Flag check — skip confirmed honeypots
        verdict = external_flags.get(cid)
        if verdict is None:
            verdict, _ = quick_flag(c)
        if verdict == "HONEYPOT":
            skipped_honeypot += 1
            continue

        feats = extract_features(c)
        rule  = compute_rule_score(feats)

        all_candidates.append(c)
        all_features.append(feats)
        all_rule_scores.append(rule)

        if (i + 1) % 20000 == 0:
            print(f"  {i+1:,} loaded ...", flush=True)

    print(f"Loaded {len(all_candidates):,} candidates "
          f"({skipped_honeypot:,} honeypots removed, "
          f"{skipped_not_retrieved:,} outside retrieval pool skipped)")

    rule_scores = np.array(all_rule_scores)

    # ── Pass 2: rerank semantic retrieval pool by domain score ───────────────
    top_k = len(all_candidates)
    top_idx = np.argsort(rule_scores)[::-1]
    print(f"Reranking {top_k:,} retrieved candidates by domain score")

    pool_candidates = [all_candidates[i] for i in top_idx]
    pool_features   = [all_features[i]   for i in top_idx]
    pool_rule       = rule_scores[top_idx]

    # ── Pass 3: LightGBM reranker ─────────────────────────────────────────────
    print("Training LightGBM reranker ...", flush=True)
    model, feature_names, X_pool = build_lgb_ranker(pool_features, pool_rule)
    lgb_scores = model.predict(X_pool)

    # ── Pass 4: SHAP values for reasoning ─────────────────────────────────────
    print("Computing SHAP values ...", flush=True)
    import shap
    explainer  = shap.TreeExplainer(model)
    shap_vals  = explainer.shap_values(X_pool)  # shape: (n, features)

    # ── Pass 5: Final ranking ──────────────────────────────────────────────────
    # Blend LGB score with rule score for robustness
    lgb_norm  = (lgb_scores - lgb_scores.min()) / (np.ptp(lgb_scores) + 1e-9)
    rule_norm = (pool_rule  - pool_rule.min())  / (np.ptp(pool_rule)  + 1e-9)
    final_scores = 0.65 * lgb_norm + 0.35 * rule_norm

    ranked_idx = np.argsort(final_scores)[::-1][:100]

    if args.debug:
        print("\n── Feature importances (top 10) ──")
        importances = model.feature_importance(importance_type="gain")
        fi_pairs = sorted(zip(feature_names, importances), key=lambda x: -x[1])
        for fname, imp in fi_pairs[:10]:
            print(f"  {fname:<30} {imp:.1f}")

        print("\n── Top-10 preview ──")
        for rank_pos, idx in enumerate(ranked_idx[:10], 1):
            c    = pool_candidates[idx]
            s    = final_scores[idx]
            feat = pool_features[idx]
            print(f"  {rank_pos:2d}. {c['candidate_id']}  "
                  f"score={s:.4f}  "
                  f"yoe={feat['stated_yoe']:.1f}  "
                  f"prod={feat['product_ratio']:.2f}  "
                  f"emb={feat['has_embeddings']}  "
                  f"vdb={feat['has_vector_db']}")

    # ── Pass 6: Write submission ───────────────────────────────────────────────
    # Scale final scores to (0, 1] with rank-1 = highest
    max_s = final_scores[ranked_idx[0]]
    min_s = final_scores[ranked_idx[-1]]
    scale = max_s - min_s if max_s > min_s else 1.0

    rows = []
    for rank_pos, idx in enumerate(ranked_idx, 1):
        c     = pool_candidates[idx]
        feat  = pool_features[idx]
        sv    = shap_vals[idx]
        raw_s = final_scores[idx]

        # Map to (0, 1] — rank 1 → ~0.99, rank 100 → ~0.01
        norm_s = 0.01 + 0.98 * (raw_s - min_s) / scale
        norm_s = round(norm_s, 4)

        reasoning = build_reasoning(c, feat, sv, feature_names, norm_s)

        rows.append({
            "candidate_id": c["candidate_id"],
            "rank":         rank_pos,
            "score":        norm_s,
            "reasoning":    reasoning,
        })

    # Validate monotone scores + tie-break by candidate_id ascending (required by validator)
    for i in range(len(rows) - 1):
        if rows[i]["score"] < rows[i + 1]["score"]:
            rows[i + 1]["score"] = rows[i]["score"]

    # Fix tie-breaks: equal scores must be in candidate_id ascending order
    i = 0
    while i < len(rows) - 1:
        j = i
        while j < len(rows) - 1 and rows[j]["score"] == rows[j+1]["score"]:
            j += 1
        if j > i:
            tied = rows[i:j+1]
            tied.sort(key=lambda r: r["candidate_id"])
            rows[i:j+1] = tied
        i = j + 1
    # Re-number ranks after tie-break reordering
    for pos, row in enumerate(rows, 1):
        row["rank"] = pos

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✓ submission.csv → {out_path}")
    print(f"  {len(rows)} candidates ranked")
    print(f"  score range: {rows[-1]['score']:.4f} – {rows[0]['score']:.4f}")
    print(f"\nRun: python validate_submission.py {out_path}")


if __name__ == "__main__":
    main()
