import json


def build_candidate_node(candidate):

    prof_map = {
        "beginner": 1,
        "intermediate": 2,
        "advanced": 3
    }

    rr = candidate.get("redrob_signals", {})

    # Industries
    industry_set = {
        job.get("industry")
        for job in candidate.get("career_history", [])
        if job.get("industry")
    }

    # Skills
    skills = {}

    for skill in candidate.get("skills", []):
        skills[skill["name"]] = {
            "proficiency": prof_map.get(
                skill.get("proficiency", "").lower(),
                0
            ),
            "endorsements": skill.get("endorsements", 0),
            "duration": skill.get("duration_months", 0)
        }

    # Certifications
    certifications = set()

    for cert in candidate.get("certifications", []):
        if isinstance(cert, dict):
            certifications.add(cert.get("name", ""))
        else:
            certifications.add(str(cert))

    candidate_node = {

        "candidate_id": candidate.get("candidate_id"),

        # EXPERIENCE
        "years_experience":
            candidate.get("profile", {}).get(
                "years_of_experience",
                0
            ),

        # INDUSTRY
        "industry_set": industry_set,

        # SKILLS
        "skills": skills,

        # CERTIFICATIONS
        "certifications": certifications,

        # ASSESSMENTS
        "assessment_scores":
            rr.get("skill_assessment_scores", {}),

        # REDROB FEATURES
        "redrob_vector": {

            "profile_completeness_score":
                rr.get("profile_completeness_score", 0),

            "open_to_work_flag":
                int(rr.get("open_to_work_flag", False)),

            "profile_views_received_30d":
                rr.get("profile_views_received_30d", 0),

            "applications_submitted_30d":
                rr.get("applications_submitted_30d", 0),

            "recruiter_response_rate":
                rr.get("recruiter_response_rate", 0),

            "avg_response_time_hours":
                rr.get("avg_response_time_hours", 0),

            "connection_count":
                rr.get("connection_count", 0),

            "endorsements_received":
                rr.get("endorsements_received", 0),

            "notice_period_days":
                rr.get("notice_period_days", 0),

            "salary_min":
                rr.get(
                    "expected_salary_range_inr_lpa",
                    {}
                ).get("min", 0),

            "salary_max":
                rr.get(
                    "expected_salary_range_inr_lpa",
                    {}
                ).get("max", 0),

            "willing_to_relocate":
                int(rr.get("willing_to_relocate", False)),

            "github_activity_score":
                rr.get("github_activity_score", 0),

            "search_appearance_30d":
                rr.get("search_appearance_30d", 0),

            "saved_by_recruiters_30d":
                rr.get("saved_by_recruiters_30d", 0),

            "interview_completion_rate":
                rr.get("interview_completion_rate", 0),

            "offer_acceptance_rate":
                rr.get("offer_acceptance_rate", 0),

            "verified_email":
                int(rr.get("verified_email", False)),

            "verified_phone":
                int(rr.get("verified_phone", False)),

            "linkedin_connected":
                int(rr.get("linkedin_connected", False))
        },

        # WORK MODE
        "preferred_work_mode":
            rr.get("preferred_work_mode", "")
    }

    return candidate_node


# ===========================
# READ JSONL AND FILTER
# ===========================

candidate_nodes = []

with open("sample_100.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        candidate = json.loads(line)

        node = build_candidate_node(candidate)

        candidate_nodes.append(node)

print("Total candidates:", len(candidate_nodes))

# Example
print(json.dumps(candidate_nodes[0], indent=4, default=list))


# ===========================
# OPTIONAL: SAVE FILTERED DATA
# ===========================

with open("candidate_nodes.json", "w", encoding="utf-8") as f:
    json.dump(
        candidate_nodes,
        f,
        indent=4,
        default=list
    )

print("Saved to candidate_nodes.json")