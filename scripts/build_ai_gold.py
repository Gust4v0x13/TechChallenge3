"""
fact_ai_adoption (partial) + gold_ai_adoption_overview.

Scope (see documentation/schema_audit_cross_year.md, section on AI questions):
  - enterprise_ai_priority: P3_e (year_2) / 3.e (year_3). NOT_AVAILABLE for
    year_1 - the question did not exist in that survey edition. This is
    never treated as 0% priority (section 34 of the project prompt).
  - personal_genai_use: P4_m_1..5 (year_2) / 4.j.1..5 (year_3), a 5-option
    multi-select ("no use" / free personal / paid personal / company-paid /
    Copilot-type tool). Same NOT_AVAILABLE rule for year_1.

question_availability_by_year is written out explicitly so no chart or
metric downstream can accidentally present "no data" as "no adoption".
"""
import ast
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_FILES = {
    "year_1": REPO_ROOT / "data/raw/survey_year_1/data_2021-2022.csv",
    "year_2": REPO_ROOT / "data/raw/survey_year_2/data_2023-2024.csv",
    "year_3": REPO_ROOT / "data/raw/survey_year_3/data_2025-2026.csv",
}
SILVER_ROOT = REPO_ROOT / "data/silver"
GOLD_ROOT = REPO_ROOT / "data/gold"

PRIORITY_MAPPING = pd.read_csv(REPO_ROOT / "documentation/mappings/mapping_ai_priority.csv")
PRIORITY_LUT = dict(zip(PRIORITY_MAPPING["raw_value"], PRIORITY_MAPPING["canonical_value"]))

GENAI_ITEM_CANONICAL = {
    "Não uso soluções de AI Generativa com foco em produtividade": "genai_no_use",
    "Uso soluções gratuitas de AI Generativa com foco em produtividade": "genai_free_personal",
    "Uso e pago pelas soluções de AI Generativa com foco em produtividade": "genai_paid_personal",
    "A empresa que trabalho paga pelas soluções de AI Generativa com foco em produtividade": "genai_paid_by_company",
    "Uso soluções do tipo Copilot": "genai_copilot",
}


def resolve_year2_columns(df):
    code_to_col = {}
    for c in df.columns:
        try:
            code, label = ast.literal_eval(c)
        except Exception:
            continue
        code_to_col[code.strip()] = (c, label)
    priority_col = code_to_col["P3_e"][0]
    genai_cols = {}
    for code, (col, label) in code_to_col.items():
        if code.startswith("P4_m_"):
            canon = GENAI_ITEM_CANONICAL.get(label)
            if canon:
                genai_cols[canon] = col
    return priority_col, genai_cols


def resolve_year3_columns(df):
    priority_col = [c for c in df.columns if c.startswith("3.e")][0]
    genai_cols = {}
    for c in df.columns:
        if c.startswith("4.j.") or c.startswith("4.j "):
            # labels formatted "4.j.1 Não uso..." (space, not underscore)
            label = c.split(" ", 1)[1].strip() if " " in c else ""
            canon = GENAI_ITEM_CANONICAL.get(label)
            if canon:
                genai_cols[canon] = c
    return priority_col, genai_cols


def build_year(survey_year, available):
    n = len(pd.read_csv(RAW_FILES[survey_year], low_memory=False, usecols=[0]))
    respondent_id = [f"{survey_year}_{i:06d}" for i in range(n)]
    out = pd.DataFrame({"respondent_id": respondent_id, "survey_year": survey_year})

    if not available:
        out["enterprise_ai_priority"] = "NOT_AVAILABLE"
        for canon in GENAI_ITEM_CANONICAL.values():
            out[canon] = pd.NA
        out["genai_question_available"] = False
        out["genai_eligible"] = False
        return out

    df = pd.read_csv(RAW_FILES[survey_year], low_memory=False)
    if survey_year == "year_2":
        priority_col, genai_cols = resolve_year2_columns(df)
    else:
        priority_col, genai_cols = resolve_year3_columns(df)

    priority_raw = df[priority_col]
    priority_canonical = priority_raw.map(PRIORITY_LUT)
    unmapped = priority_raw.notna() & priority_canonical.isna()
    if unmapped.any():
        raise ValueError(f"Unmapped ai_priority values in {survey_year}: {sorted(priority_raw[unmapped].unique())}")
    priority_canonical = priority_canonical.where(priority_raw.notna(), "NOT_ASKED")
    out["enterprise_ai_priority"] = priority_canonical.values

    genai_block_cols = list(genai_cols.values())
    genai_eligible = df[genai_block_cols].notna().any(axis=1)
    for canon, col in genai_cols.items():
        selected = (df[col].astype(float) == 1.0)
        out[canon] = selected.where(genai_eligible, other=pd.NA).values
    out["genai_question_available"] = True
    out["genai_eligible"] = genai_eligible.values
    return out


def build_gold_ai_adoption_overview(fact):
    rows = []
    for survey_year, sub in fact.groupby("survey_year"):
        # enterprise AI priority
        available_priority = (sub["enterprise_ai_priority"] != "NOT_AVAILABLE").any()
        if available_priority:
            answered = sub[sub["enterprise_ai_priority"] != "NOT_ASKED"]
            eligible_n = len(answered)
            top_priority_n = answered["enterprise_ai_priority"].isin(["TOP_PRIORITY_MAIN", "TOP_PRIORITY_MEDIUM_TERM"]).sum()
            rows.append({
                "survey_year": survey_year, "metric": "enterprise_ai_priority_rate",
                "question_available": True,
                "eligible_respondents": eligible_n, "numerator": top_priority_n,
                "rate": (top_priority_n / eligible_n) if eligible_n else None,
            })
        else:
            rows.append({"survey_year": survey_year, "metric": "enterprise_ai_priority_rate",
                          "question_available": False, "eligible_respondents": 0, "numerator": None, "rate": None})

        if sub["genai_question_available"].iloc[0]:
            elig_sub = sub[sub["genai_eligible"] == True]
            eligible_n = len(elig_sub)
            for canon, metric_name in [
                ("genai_no_use", "personal_genai_no_use_rate"),
                ("genai_free_personal", "personal_genai_free_use_rate"),
                ("genai_paid_personal", "personal_genai_self_paid_rate"),
                ("genai_paid_by_company", "personal_genai_company_paid_rate"),
                ("genai_copilot", "personal_genai_copilot_rate"),
            ]:
                num = elig_sub[canon].astype(bool).sum()
                rows.append({
                    "survey_year": survey_year, "metric": metric_name, "question_available": True,
                    "eligible_respondents": eligible_n, "numerator": int(num), "rate": num / eligible_n,
                })
            not_no_use = eligible_n - elig_sub["genai_no_use"].astype(bool).sum()
            rows.append({
                "survey_year": survey_year, "metric": "personal_genai_usage_rate", "question_available": True,
                "eligible_respondents": eligible_n, "numerator": int(not_no_use), "rate": not_no_use / eligible_n,
            })
        else:
            for metric_name in ["personal_genai_no_use_rate", "personal_genai_free_use_rate",
                                 "personal_genai_self_paid_rate", "personal_genai_company_paid_rate",
                                 "personal_genai_copilot_rate", "personal_genai_usage_rate"]:
                rows.append({"survey_year": survey_year, "metric": metric_name, "question_available": False,
                              "eligible_respondents": 0, "numerator": None, "rate": None})

    out = pd.DataFrame(rows)
    out_dir = GOLD_ROOT / "gold_ai_adoption_overview"
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / "gold_ai_adoption_overview.csv", index=False)
    print(f"[gold] gold_ai_adoption_overview: {out.shape[0]} rows -> {out_dir}")
    return out


if __name__ == "__main__":
    frames = [
        build_year("year_1", available=False),
        build_year("year_2", available=True),
        build_year("year_3", available=True),
    ]
    fact_ai_adoption = pd.concat(frames, ignore_index=True)
    out_dir = SILVER_ROOT / "fact_ai_adoption"
    out_dir.mkdir(parents=True, exist_ok=True)
    fact_ai_adoption.to_csv(out_dir / "fact_ai_adoption.csv", index=False)
    print(f"[silver] fact_ai_adoption: {fact_ai_adoption.shape[0]} rows -> {out_dir}")

    build_gold_ai_adoption_overview(fact_ai_adoption)
