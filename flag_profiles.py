"""
flag_profiles.py — Fake/honeypot candidate detection for Redrob Hackathon

Usage (matches repo layout):
    python flag_profiles.py --input candidates.jsonl --output artifacts/flagged.csv

Automatically generates graph-viz/public/candidate_nodes_enriched.json
if candidate_nodes.json exists (produced by filterrecords.py).

Optional overrides:
    --candidate-nodes  path to candidate_nodes.json   (default: candidate_nodes.json)
    --enriched-out     path for enriched output JSON  (default: graph-viz/public/candidate_nodes_enriched.json)
    --only-flagged     only write SUSPICIOUS/HONEYPOT rows to CSV
"""

import json
import csv
import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

TODAY = datetime(2026, 6, 25)

# ---------------------------------------------------------------------------
# Detection checks — each returns (flag: bool, detail: str)
# ---------------------------------------------------------------------------

def check_skill_duration_exceeds_career(candidate):
    career = candidate.get("career_history", [])
    skills = candidate.get("skills", [])
    total_career = sum(r.get("duration_months", 0) or 0 for r in career)
    worst_excess, worst_skill = 0, None
    for s in skills:
        excess = (s.get("duration_months") or 0) - total_career
        if excess > worst_excess:
            worst_excess = excess
            worst_skill = s["name"]
    if worst_excess > 12:
        return True, f"{worst_skill} claims {worst_excess}m more than total career ({total_career}m)"
    return False, ""


def check_skill_duration_inflation(candidate):
    career = candidate.get("career_history", [])
    skills = candidate.get("skills", [])
    total_career = sum(r.get("duration_months", 0) or 0 for r in career)
    total_skills = sum(s.get("duration_months", 0) or 0 for s in skills)
    if total_career == 0:
        return False, ""
    ratio = total_skills / total_career
    if ratio > 10:
        return True, f"skill_sum={total_skills}m vs career={total_career}m (ratio={ratio:.1f}x)"
    return False, ""


def check_inverted_salary(candidate):
    sig = candidate.get("redrob_signals", {}) or {}
    sal = sig.get("expected_salary_range_inr_lpa", {}) or {}
    sal_min = sal.get("min") or 0
    sal_max = sal.get("max") or 0
    if sal_max > 0 and sal_min > sal_max:
        return True, f"salary min={sal_min}L > max={sal_max}L"
    return False, ""


def check_career_before_graduation(candidate):
    edu    = candidate.get("education", [])
    career = candidate.get("career_history", [])
    latest_edu_end = max((e.get("end_year") or 0 for e in edu), default=0)
    if not latest_edu_end or not career:
        return False, ""
    for r in career:
        try:
            s = datetime.strptime(r["start_date"], "%Y-%m-%d")
            if s.year < latest_edu_end - 2:
                return True, f"{r['company']} started {r['start_date']} but edu ends {latest_edu_end}"
        except (ValueError, KeyError):
            pass
    return False, ""


def check_overlapping_roles(candidate):
    career = candidate.get("career_history", [])
    parsed = []
    for r in career:
        try:
            s = datetime.strptime(r["start_date"], "%Y-%m-%d")
            e = datetime.strptime(r["end_date"], "%Y-%m-%d") if r.get("end_date") else TODAY
            parsed.append((s, e, r.get("company", "?")))
        except (ValueError, KeyError):
            pass
    parsed.sort()
    for i in range(len(parsed) - 1):
        s1, e1, c1 = parsed[i]
        s2, e2, c2 = parsed[i + 1]
        if c1 != c2 and s2 < e1:
            overlap_days = (min(e1, e2) - s2).days
            if overlap_days > 60:
                return True, f"{c1} overlaps {c2} by {overlap_days} days"
    return False, ""


def check_future_employment(candidate):
    for r in candidate.get("career_history", []):
        try:
            if datetime.strptime(r["start_date"], "%Y-%m-%d") > TODAY:
                return True, f"{r.get('company', '?')} starts {r['start_date']}"
        except (ValueError, KeyError):
            pass
    return False, ""


def check_end_before_start(candidate):
    for r in candidate.get("career_history", []):
        try:
            s = datetime.strptime(r["start_date"], "%Y-%m-%d")
            if r.get("end_date"):
                e = datetime.strptime(r["end_date"], "%Y-%m-%d")
                if e < s:
                    return True, f"{r.get('company', '?')}: end={r['end_date']} before start={r['start_date']}"
        except (ValueError, KeyError):
            pass
    return False, ""


def check_current_company_mismatch(candidate):
    profile_company = (candidate["profile"].get("current_company") or "").strip().lower()
    career          = candidate.get("career_history", [])
    if not profile_company:
        return False, ""
    current_roles = [r.get("company", "").strip().lower() for r in career if r.get("is_current")]
    if current_roles and profile_company not in current_roles:
        return True, (
            f"profile='{candidate['profile'].get('current_company')}' "
            f"but current_role(s)={[r.get('company') for r in career if r.get('is_current')]}"
        )
    return False, ""


def check_proficiency_vs_assessment(candidate):
    EXPECTED = {
        "beginner":     (0,  50),
        "intermediate": (30, 75),
        "advanced":     (55, 95),
        "expert":       (70, 100),
    }
    skills      = candidate.get("skills", [])
    sig         = candidate.get("redrob_signals", {}) or {}
    assessments = sig.get("skill_assessment_scores", {}) or {}
    mismatches  = []
    for s in skills:
        score = assessments.get(s.get("name", ""))
        if score is None:
            continue
        lo, hi = EXPECTED.get(s.get("proficiency", ""), (0, 100))
        if score < lo - 20 or score > hi + 10:
            mismatches.append(f"{s['name']}(self={s.get('proficiency')},assessed={score:.0f})")
    if len(mismatches) >= 2:
        return True, "; ".join(mismatches[:3])
    return False, ""


def check_yoe_mismatch(candidate):
    stated        = candidate["profile"].get("years_of_experience") or 0
    career        = candidate.get("career_history", [])
    career_months = sum(r.get("duration_months", 0) or 0 for r in career)
    diff          = abs((career_months / 12) - stated)
    if diff > 3:
        return True, f"stated={stated}yr vs career_sum={career_months/12:.1f}yr (diff={diff:.1f})"
    return False, ""


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

CHECKS = [
    (check_skill_duration_exceeds_career, 0.20, "skill_exceeds_career"),
    (check_skill_duration_inflation,      0.15, "skill_inflation"),
    (check_inverted_salary,               0.10, "inverted_salary"),
    (check_career_before_graduation,      0.15, "career_before_grad"),
    (check_overlapping_roles,             0.20, "overlapping_roles"),
    (check_future_employment,             0.25, "future_employment"),
    (check_end_before_start,             0.25, "end_before_start"),
    (check_current_company_mismatch,     0.20, "company_mismatch"),
    (check_proficiency_vs_assessment,    0.15, "proficiency_mismatch"),
    (check_yoe_mismatch,                 0.15, "yoe_mismatch"),
]

MAX_WEIGHT = sum(w for _, w, _ in CHECKS)


def score_candidate(candidate):
    result     = {"candidate_id": candidate["candidate_id"]}
    total      = 0.0
    all_details = []

    for fn, weight, label in CHECKS:
        flagged, detail = fn(candidate)
        result[label]            = flagged
        result[f"{label}_detail"] = detail
        if flagged:
            total += weight
            all_details.append(f"[{label}] {detail}")

    result["suspicion_score"] = round(total / MAX_WEIGHT, 4)
    result["flags_triggered"] = sum(1 for _, _, lbl in CHECKS if result[lbl])
    result["flag_summary"]    = " | ".join(all_details)

    score   = result["suspicion_score"]
    n_flags = result["flags_triggered"]
    result["verdict"] = (
        "HONEYPOT"   if (score >= 0.30 or n_flags >= 3) else
        "SUSPICIOUS" if (score >= 0.12 or n_flags >= 1) else
        "CLEAN"
    )
    return result


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

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
        if isinstance(data, list):
            yield from data
        else:
            yield data
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def write_csv(rows, out_path: Path):
    if not rows:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_enriched_nodes(flagged_rows, candidate_nodes_path: Path, out_path: Path):
    """
    Merge flag verdicts into candidate_nodes.json (written by filterrecords.py)
    and save as candidate_nodes_enriched.json for the graph-viz React app.
    """
    flag_map = {r["candidate_id"]: r for r in flagged_rows}

    with open(candidate_nodes_path, encoding="utf-8") as f:
        nodes = json.load(f)

    enriched = {}
    for node in nodes:
        cid      = node["candidate_id"]
        flag_row = flag_map.get(cid, {})
        enriched[cid] = {
            **node,
            "flag": {
                "verdict":         flag_row.get("verdict", "CLEAN"),
                "suspicion_score": float(flag_row.get("suspicion_score", 0)),
                "flags_triggered": int(flag_row.get("flags_triggered", 0)),
                "flag_summary":    flag_row.get("flag_summary", ""),
            },
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, default=list)

    return Counter(v["flag"]["verdict"] for v in enriched.values())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Flag fake/honeypot candidate profiles")
    parser.add_argument("--input",  "-i", required=True,
                        help="candidates.jsonl or sample_candidates.json")
    parser.add_argument("--output", "-o", required=True,
                        help="Output CSV path (e.g. artifacts/flagged.csv)")
    parser.add_argument("--candidate-nodes", default="candidate_nodes.json",
                        help="candidate_nodes.json produced by filterrecords.py "
                             "(default: candidate_nodes.json)")
    parser.add_argument("--enriched-out",
                        default="graph-viz/public/candidate_nodes_enriched.json",
                        help="Output path for enriched nodes JSON consumed by graph-viz "
                             "(default: graph-viz/public/candidate_nodes_enriched.json)")
    parser.add_argument("--only-flagged", action="store_true",
                        help="Only write SUSPICIOUS/HONEYPOT rows to the CSV")
    args = parser.parse_args()

    in_path  = Path(args.input)
    out_path = Path(args.output)

    if not in_path.exists():
        print(f"ERROR: {in_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {in_path} ...", flush=True)

    rows   = []
    counts = {"CLEAN": 0, "SUSPICIOUS": 0, "HONEYPOT": 0}

    for i, candidate in enumerate(iter_candidates(in_path)):
        row = score_candidate(candidate)
        counts[row["verdict"]] += 1
        rows.append(row)
        if (i + 1) % 10000 == 0:
            print(f"  {i+1:,} processed ...", flush=True)

    out_rows = rows if not args.only_flagged else [r for r in rows if r["verdict"] != "CLEAN"]
    write_csv(out_rows, out_path)

    total = sum(counts.values())
    print(f"\nDone. {total:,} candidates → {out_path}")
    print(f"  CLEAN      : {counts['CLEAN']:>7,}  ({counts['CLEAN']/total*100:.1f}%)")
    print(f"  SUSPICIOUS : {counts['SUSPICIOUS']:>7,}  ({counts['SUSPICIOUS']/total*100:.1f}%)")
    print(f"  HONEYPOT   : {counts['HONEYPOT']:>7,}  ({counts['HONEYPOT']/total*100:.2f}%)")

    # Auto-generate enriched nodes for graph-viz if candidate_nodes.json exists
    cn_path      = Path(args.candidate_nodes)
    enriched_out = Path(args.enriched_out)
    if cn_path.exists():
        verdict_counts = build_enriched_nodes(rows, cn_path, enriched_out)
        print(f"\nEnriched graph nodes → {enriched_out}")
        print(f"  {dict(verdict_counts)}")
    else:
        print(f"\nSkipping graph enrichment ({cn_path} not found — run filterrecords.py first)")


if __name__ == "__main__":
    main()
