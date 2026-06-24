import json

with open("candidate_nodes.json", "r") as f:
    candidates = json.load(f)

all_skills = set()

for c in candidates:
    all_skills.update(
        c["skills"].keys()
    )

all_skills = sorted(all_skills)

all_assessments = set()

for c in candidates:
    all_assessments.update(
        c["assessment_scores"].keys()
    )

all_assessments = sorted(all_assessments)

numeric_fields = [

    "profile_completeness_score",

    "profile_views_received_30d",

    "applications_submitted_30d",

    "recruiter_response_rate",

    "avg_response_time_hours",

    "connection_count",

    "endorsements_received",

    "notice_period_days",

    "salary_min",

    "salary_max",

    "github_activity_score",

    "search_appearance_30d",

    "saved_by_recruiters_30d",

    "interview_completion_rate",

    "offer_acceptance_rate"
]

mins = {}
maxs = {}

for field in numeric_fields:

    values = [
        c["redrob_vector"][field]
        for c in candidates
    ]

    mins[field] = min(values)
    maxs[field] = max(values)

def skill_similarity(c1, c2):

    s1 = set(c1["skills"].keys())
    s2 = set(c2["skills"].keys())

    union = s1 | s2

    if len(union) == 0:
        return 0

    return len(s1 & s2) / len(union)


def industry_similarity(c1, c2):

    i1 = set(c1["industry_set"])
    i2 = set(c2["industry_set"])

    union = i1 | i2

    if len(union) == 0:
        return 0

    return len(i1 & i2) / len(union)


def certification_similarity(c1, c2):

    a = set(c1["certifications"])
    b = set(c2["certifications"])

    if len(a | b) == 0:
        return 1

    return len(a & b) / len(a | b)  

MAX_EXP = max(
    c["years_experience"]
    for c in candidates
)

def experience_similarity(c1, c2):

    diff = abs(
        c1["years_experience"]
        -
        c2["years_experience"]
    )

    return max(
        0,
        1 - diff/MAX_EXP
    )

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

def assessment_vector(candidate):

    scores = candidate["assessment_scores"]

    return np.array([

        scores.get(skill, 0)

        for skill in all_assessments

    ])

def assessment_similarity(c1, c2):

    v1 = assessment_vector(c1)
    v2 = assessment_vector(c2)

    if np.sum(v1) == 0 or np.sum(v2) == 0:
        return 0

    return cosine_similarity(
        [v1],
        [v2]
    )[0][0]


def redrob_vector(candidate):

    r = candidate["redrob_vector"]

    vec = []

    for field in numeric_fields:

        value = r[field]

        mn = mins[field]
        mx = maxs[field]

        norm = (
            value - mn
        ) / (
            mx - mn + 1e-9
        )

        vec.append(norm)

    vec.extend([

        r["open_to_work_flag"],

        r["willing_to_relocate"],

        r["verified_email"],

        r["verified_phone"],

        r["linkedin_connected"]

    ])

    return np.array(vec)


def redrob_similarity(c1, c2):

    v1 = redrob_vector(c1)
    v2 = redrob_vector(c2)

    return cosine_similarity(
        [v1],
        [v2]
    )[0][0]


def final_similarity(c1, c2):

    return (

        0.40 * skill_similarity(c1,c2)

        +

        0.15 * assessment_similarity(c1,c2)

        +

        0.10 * certification_similarity(c1,c2)

        +

        0.10 * industry_similarity(c1,c2)

        +

        0.10 * experience_similarity(c1,c2)

        +

        0.15 * redrob_similarity(c1,c2)

    )

graph = {}

for candidate in candidates:

    sims = []

    for other in candidates:

        if (
            candidate["candidate_id"]
            ==
            other["candidate_id"]
        ):
            continue

        sim = final_similarity(
            candidate,
            other
        )

        sims.append(
            (
                other["candidate_id"],
                round(sim,4)
            )
        )

    sims.sort(
        key=lambda x:x[1],
        reverse=True
    )

    graph[
        candidate["candidate_id"]
    ] = sims[:5]



print(graph["CAND_0071487"])

import json

with open("graphical_representation.json", "w") as f:
    json.dump(graph, f, indent=4)