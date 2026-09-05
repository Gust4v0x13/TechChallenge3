"""
gold_skill_priority_score - composite score over the DATABASE technology
family only (the only technology family with a bridge table built so far -
see documentation/analytical_domains.md domain 3 status).

Suggested formula from documentation/analytical_domains.md (domain 9):

    priority_score =
        0.30 * normalized_adoption_growth
      + 0.25 * normalized_cross_role_prevalence
      + 0.20 * normalized_salary_association
      + 0.15 * normalized_senior_role_prevalence
      + 0.10 * normalized_future_interest

`future_interest` has no source field anywhere in the three surveys (no
question asks respondents which technology they want to learn next), so it
is NOT estimated or proxied - inventing it would violate the project's
"never invent a metric" rule. Its 0.10 weight is redistributed
proportionally across the four measurable components instead:

    adjusted_weight = original_weight / 0.90

    adoption_growth:        0.30 / 0.90 = 0.3333
    cross_role_prevalence:  0.25 / 0.90 = 0.2778
    salary_association:     0.20 / 0.90 = 0.2222
    senior_role_prevalence: 0.15 / 0.90 = 0.1667

This redistribution, and every component value, is kept in the output
table - the final score is never published without its components (project
prompt section 35/55: never present a composite score as objective truth).

Technologies without a valid Year1->Year3 trend (only SAP, dropped from
the questionnaire after Year1) are excluded from the score and reported
separately.
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SILVER_ROOT = REPO_ROOT / "data/silver"
GOLD_ROOT = REPO_ROOT / "data/gold"

MIN_ELIGIBLE_FOR_SCORE = 30  # never score a technology on a tiny sample


def minmax(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    if hi == lo:
        return s * 0.0
    return (s - lo) / (hi - lo)


def main():
    bridge = pd.read_csv(SILVER_ROOT / "bridge_respondent_technology/bridge_respondent_technology.csv")
    fact_parts = [pd.read_csv(p) for p in sorted((SILVER_ROOT / "respondents").glob("survey_year=*/part.csv"))]
    fact = pd.concat(fact_parts, ignore_index=True)

    adoption = pd.read_csv(GOLD_ROOT / "gold_technology_adoption_by_year/gold_technology_adoption_by_year.csv")

    # --- component 1: adoption_growth (year_1 -> year_3 pp change) ---
    piv = adoption.pivot(index="technology", columns="survey_year", values="adoption_rate")
    growth = (piv["year_3"] - piv["year_1"]) * 100
    excluded_no_trend = growth[growth.isna()].index.tolist()
    growth = growth.dropna().rename("adoption_growth_pp")

    # focus the score on the most recent survey (year_3) for the
    # role/seniority/salary lenses - "which skills matter now"
    y3_bridge = bridge[(bridge.survey_year == "year_3") & (bridge.technology.isin(growth.index))]
    y3_fact = fact[fact.survey_year == "year_3"][["respondent_id", "current_role", "seniority", "salary_midpoint"]]
    joined = y3_bridge.merge(y3_fact, on="respondent_id", how="left")

    eligible_n = y3_bridge["respondent_id"].nunique()
    overall_roles = set(y3_fact.loc[y3_fact.current_role != "UNKNOWN", "current_role"].unique())
    overall_median_salary = y3_fact["salary_midpoint"].median()
    overall_senior_share = y3_fact["seniority"].isin(["SENIOR", "SPECIALIST"]).mean()

    rows = []
    for tech, g in joined.groupby("technology"):
        users = g[g.selected == True]
        n_users = users["respondent_id"].nunique()
        if n_users < MIN_ELIGIBLE_FOR_SCORE:
            continue

        # component 2: cross_role_prevalence - breadth of roles using the tech
        roles_using = set(users.loc[users.current_role != "UNKNOWN", "current_role"].unique())
        cross_role_prevalence = len(roles_using) / len(overall_roles) if overall_roles else None

        # component 3: salary_association - relative lift in median salary among users
        median_users = users["salary_midpoint"].median()
        salary_association = (
            (median_users - overall_median_salary) / overall_median_salary
            if pd.notna(median_users) and overall_median_salary else None
        )

        # component 4: senior_role_prevalence - relative lift in senior/specialist share among users
        senior_share_users = users["seniority"].isin(["SENIOR", "SPECIALIST"]).mean()
        senior_role_prevalence = (
            (senior_share_users - overall_senior_share) / overall_senior_share if overall_senior_share else None
        )

        rows.append({
            "technology": tech,
            "year_3_users": n_users,
            "year_3_eligible_respondents": eligible_n,
            "adoption_growth_pp": growth.get(tech),
            "cross_role_prevalence": cross_role_prevalence,
            "salary_association": salary_association,
            "senior_role_prevalence": senior_role_prevalence,
        })

    out = pd.DataFrame(rows)

    for col in ["adoption_growth_pp", "cross_role_prevalence", "salary_association", "senior_role_prevalence"]:
        out[f"normalized_{col}"] = minmax(out[col])

    W = {"adoption_growth_pp": 0.30 / 0.90, "cross_role_prevalence": 0.25 / 0.90,
         "salary_association": 0.20 / 0.90, "senior_role_prevalence": 0.15 / 0.90}

    out["priority_score"] = (
        W["adoption_growth_pp"] * out["normalized_adoption_growth_pp"]
        + W["cross_role_prevalence"] * out["normalized_cross_role_prevalence"]
        + W["salary_association"] * out["normalized_salary_association"]
        + W["senior_role_prevalence"] * out["normalized_senior_role_prevalence"]
    )
    out["future_interest_component"] = "NOT_MEASURED - no source question in any of the 3 surveys; weight redistributed to the other 4 components (see script docstring)"
    out = out.sort_values("priority_score", ascending=False).reset_index(drop=True)
    out["rank"] = out.index + 1

    out_dir = GOLD_ROOT / "gold_skill_priority_score"
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / "gold_skill_priority_score.csv", index=False)
    print(f"[gold] gold_skill_priority_score: {out.shape[0]} technologies scored -> {out_dir}")
    print(f"Excluded (no Year1->Year3 trend, e.g. dropped from questionnaire): {excluded_no_trend}")
    print(out[["rank", "technology", "priority_score", "adoption_growth_pp",
                "cross_role_prevalence", "salary_association", "senior_role_prevalence"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
