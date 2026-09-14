"""
Business analysis over the Gold layer — one function per business question
from documentation/business_questions.md (section 23 of the project
prompt). Each function reads only Gold tables (never Bronze/Silver
directly, per the project's "charts consume Gold" rule), prints a
console summary, and writes a tidy CSV answer to
data/gold/business_answers/qN_*.csv so the numbers behind the executive
narrative are reproducible and can be pulled straight into the
presentation/DataViz notebook.

Run:
    cd state-of-data-tech-challenge/scripts
    source ../.venv/bin/activate
    python3 business_analysis.py

Every function documents:
  - which Gold table(s) it reads
  - the exact caveat that must travel with the number (sample vs market
    size, structural NULLs, salary-band quantization, etc. — see
    documentation/data_quality_report.md)
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLD = REPO_ROOT / "data/gold"
OUT_DIR = GOLD / "business_answers"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_SAMPLE_SIZE = 30


def save(df: pd.DataFrame, name: str):
    path = OUT_DIR / f"{name}.csv"
    df.to_csv(path, index=False)
    print(f"  -> saved {path.relative_to(REPO_ROOT)} ({len(df)} rows)")


def header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


# ---------------------------------------------------------------------------
# Q1 - Como está estruturado o mercado brasileiro de Dados?
# Source: gold_market_overview (survey_year x dimension x dimension_value)
# Caveat: respondent_count differs by survey design/sample, not a tracked
# population - always read as respondent_share_within_year, never as
# "the market grew/shrank X%".
# ---------------------------------------------------------------------------
def q1_market_structure():
    header("Q1 - Estrutura do mercado brasileiro de Dados")
    mo = pd.read_csv(GOLD / "market_overview/gold_market_overview.csv")

    totals = mo[mo.dimension == "seniority"].groupby("survey_year")["respondent_count"].sum()
    print("Respondent count by survey_year (sample size, NOT market size):")
    print(totals.to_string())

    for dim in ["seniority", "current_work_model", "employment_status", "region"]:
        pivot = (
            mo[mo.dimension == dim]
            .pivot(index="dimension_value", columns="survey_year", values="respondent_share_within_year")
            .round(4)
        )
        print(f"\n-- {dim} (share within year) --")
        print(pivot.to_string())
        save(pivot.reset_index(), f"q1_market_structure_{dim}")


# ---------------------------------------------------------------------------
# Q2 - Quais perfis profissionais são mais valorizados pelo mercado?
# Source: gold_compensation_by_role, gold_compensation_by_seniority
# Caveat: current_role is the harmonized canonical role (mapping_role.csv);
# some categories merge/split differently across survey years - see
# comparability_group in that mapping table before comparing a single role
# across years. low_sample_flag rows are kept but must be shown flagged.
# ---------------------------------------------------------------------------
def q2_valued_profiles():
    header("Q2 - Perfis profissionais mais valorizados (remuneração)")
    role = pd.read_csv(GOLD / "gold_compensation_by_role/gold_compensation_by_role.csv")
    sen = pd.read_csv(GOLD / "gold_compensation_by_seniority/gold_compensation_by_seniority.csv")

    latest_year = role["survey_year"].max()
    top_roles = (
        role[role.survey_year == latest_year]
        .sort_values("median_salary_midpoint", ascending=False)
        [["current_role", "respondent_count", "median_salary_midpoint", "salary_iqr", "low_sample_flag"]]
    )
    print(f"Top roles by median salary ({latest_year}):")
    print(top_roles.head(10).to_string(index=False))
    save(top_roles, "q2_compensation_by_role_latest_year")

    print("\nSalary by seniority (all years):")
    sen_view = sen[["survey_year", "seniority", "respondent_count", "median_salary_midpoint"]]
    print(sen_view.to_string(index=False))
    save(sen_view, "q2_compensation_by_seniority_all_years")


# ---------------------------------------------------------------------------
# Q3 - Qual é o cenário de diversidade de gênero nas carreiras de dados?
# Source: gold_gender_representation
# Caveat: gender fields for Year1/Year2 were recovered from raw CSVs (see
# documentation/schema_audit_cross_year.md) - comparable across all 3
# years. share_within_bucket under cross_dimension='seniority'/'current_role'
# is the representation metric (e.g. "what % of SENIOR respondents are
# FEMALE"), not gender's own internal distribution.
# ---------------------------------------------------------------------------
def q3_gender_diversity():
    header("Q3 - Diversidade de gênero")
    g = pd.read_csv(GOLD / "gold_gender_representation/gold_gender_representation.csv")

    overall = g[g.cross_dimension == "overall"][
        ["survey_year", "gender", "respondent_count", "share_within_bucket", "median_salary_midpoint"]
    ]
    print("Overall gender share and median salary, by year:")
    print(overall.to_string(index=False))
    save(overall, "q3_gender_overall_by_year")

    seniority_funnel = g[(g.cross_dimension == "seniority") & (g.gender == "FEMALE")][
        ["survey_year", "cross_dimension_value", "respondent_count", "bucket_total", "share_within_bucket"]
    ].rename(columns={"cross_dimension_value": "seniority"})
    print("\nFemale share by seniority (career funnel), all years:")
    print(seniority_funnel.to_string(index=False))
    save(seniority_funnel, "q3_gender_share_by_seniority")

    latest_year = g["survey_year"].max()
    role_view = g[(g.cross_dimension == "current_role") & (g.gender == "FEMALE") & (g.survey_year == latest_year)][
        ["cross_dimension_value", "respondent_count", "bucket_total", "share_within_bucket"]
    ].rename(columns={"cross_dimension_value": "current_role"}).sort_values("bucket_total", ascending=False)
    print(f"\nFemale share by role ({latest_year}):")
    print(role_view.to_string(index=False))
    save(role_view, "q3_gender_share_by_role_latest_year")


# ---------------------------------------------------------------------------
# Q4 - Quais tecnologias apresentam maior adoção entre os profissionais?
# Source: gold_technology_adoption_by_year
# Caveat: SCOPE-LIMITED to the DATABASE technology family only (the only
# family with a bridge table built so far - see
# documentation/analytical_domains.md domain 3 status). adoption_rate uses
# eligible_respondents as denominator, not the full survey population.
# ---------------------------------------------------------------------------
def q4_technology_adoption():
    header("Q4 - Adoção de tecnologias (família DATABASE — escopo deste corte)")
    t = pd.read_csv(GOLD / "gold_technology_adoption_by_year/gold_technology_adoption_by_year.csv")
    latest_year = t["survey_year"].max()

    top_adoption = t[t.survey_year == latest_year].sort_values("adoption_rate", ascending=False)[
        ["technology", "technology_users", "eligible_respondents", "adoption_rate", "yoy_pp_change_vs_prev_survey"]
    ]
    print(f"Top technologies by adoption_rate ({latest_year}):")
    print(top_adoption.head(10).to_string(index=False))
    save(top_adoption, "q4_technology_adoption_latest_year")

    growth = t[t.survey_year == latest_year].sort_values("yoy_pp_change_vs_prev_survey", ascending=False)[
        ["technology", "adoption_rate", "yoy_pp_change_vs_prev_survey"]
    ]
    print("\nBiggest YoY adoption gains (vs previous survey):")
    print(growth.head(8).to_string(index=False))
    print("\nBiggest YoY adoption declines (vs previous survey):")
    print(growth.tail(8).sort_values("yoy_pp_change_vs_prev_survey").to_string(index=False))
    save(growth, "q4_technology_yoy_change_latest_year")


# ---------------------------------------------------------------------------
# Q5 - Qual é o índice de adoção de IA e seu impacto?
# Source: gold_ai_adoption_overview
# Caveat: Year1 has NO AI questions (question_available=False) - must never
# be read/plotted as 0% adoption, only omitted or shown as "N/A".
# ---------------------------------------------------------------------------
def q5_ai_adoption():
    header("Q5 - Adoção de Inteligência Artificial")
    ai = pd.read_csv(GOLD / "gold_ai_adoption_overview/gold_ai_adoption_overview.csv")

    availability = ai.groupby("survey_year")["question_available"].any()
    print("Question availability by year (Year1 must be N/A, never 0%):")
    print(availability.to_string())

    view = ai[ai.question_available][["survey_year", "metric", "eligible_respondents", "rate"]]
    print("\nAI adoption metrics (years where the question existed):")
    print(view.to_string(index=False))
    save(ai, "q5_ai_adoption_overview")


# ---------------------------------------------------------------------------
# Q6 - Diferenças por região, senioridade e modelo de trabalho?
# Source: gold_compensation_by_region, gold_compensation_by_seniority,
# gold_compensation_by_work_model
# Caveat: low_sample_flag (n < 30) must be surfaced, never silently
# dropped or silently trusted. Salary bands are coarse (~14 distinct
# midpoints), so tied medians across groups can reflect quantization, not
# genuine equality - report salary_iqr alongside the median.
# ---------------------------------------------------------------------------
def q6_cross_cutting_differences():
    header("Q6 - Diferenças por região, senioridade e modelo de trabalho")
    reg = pd.read_csv(GOLD / "gold_compensation_by_region/gold_compensation_by_region.csv")
    sen = pd.read_csv(GOLD / "gold_compensation_by_seniority/gold_compensation_by_seniority.csv")
    wm = pd.read_csv(GOLD / "gold_compensation_by_work_model/gold_compensation_by_work_model.csv")
    latest_year = reg["survey_year"].max()

    reg_view = reg[reg.survey_year == latest_year].sort_values("median_salary_midpoint", ascending=False)[
        ["region", "respondent_count", "median_salary_midpoint", "salary_iqr", "low_sample_flag"]
    ]
    print(f"By region ({latest_year}):")
    print(reg_view.to_string(index=False))
    save(reg_view, "q6_compensation_by_region_latest_year")

    sen_view = sen[["survey_year", "seniority", "respondent_count", "median_salary_midpoint", "salary_iqr"]]
    print("\nBy seniority (all years):")
    print(sen_view.to_string(index=False))
    save(sen_view, "q6_compensation_by_seniority_all_years")

    wm_view = wm[["survey_year", "current_work_model", "respondent_count", "median_salary_midpoint", "salary_iqr"]]
    print("\nBy work model (all years):")
    print(wm_view.to_string(index=False))
    save(wm_view, "q6_compensation_by_work_model_all_years")


# ---------------------------------------------------------------------------
# Q7 - Oportunidades e desafios para empresas que desejam investir em Dados/IA
# Source: gold_skill_priority_score + everything above (synthesis, not a
# new metric).
# Caveat: priority_score's future_interest component is NOT_MEASURED (no
# source question in any survey year) - weight redistributed across the
# other 4 components, documented in build_skill_priority_gold.py. Score
# covers the DATABASE family only.
# ---------------------------------------------------------------------------
def q7_opportunities_and_challenges():
    header("Q7 - Oportunidades e desafios (síntese via skill priority score)")
    sk = pd.read_csv(GOLD / "gold_skill_priority_score/gold_skill_priority_score.csv")

    view = sk.sort_values("priority_score", ascending=False)[
        ["rank", "technology", "priority_score", "adoption_growth_pp",
         "cross_role_prevalence", "salary_association", "senior_role_prevalence"]
    ]
    print("Skill priority ranking (DATABASE family, components shown - never present the score alone):")
    print(view.head(10).to_string(index=False))
    save(view, "q7_skill_priority_ranking")


if __name__ == "__main__":
    q1_market_structure()
    q2_valued_profiles()
    q3_gender_diversity()
    q4_technology_adoption()
    q5_ai_adoption()
    q6_cross_cutting_differences()
    q7_opportunities_and_challenges()
    print("\nAll answers saved under data/gold/business_answers/")
