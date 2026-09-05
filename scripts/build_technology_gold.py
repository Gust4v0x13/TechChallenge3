"""
bridge_respondent_technology (DATABASE family only, first cut) +
gold_technology_adoption_by_year.

Scope note: only the "database/data source" option block is covered in this
cut (confirmed EXACT_MATCH-by-label across all 3 years per
documentation/schema_audit_cross_year.md section 4). Other technology
families (programming languages, cloud, BI, ETL, ML/DS tooling) are NOT
yet unpivoted - see documentation/analytical_domains.md domain 3 status.

Source option blocks (children columns only, parent umbrella column carries
no data - verified against the raw CSV):
  year_1: P4_f_a.. (34 items)
  year_2: P4_g_1.. (33 items - SAP dropped from the questionnaire)
  year_3: 4.d.1..  (33 items, same list as year_2)

Denominator rule (section 28 of the project prompt): adoption_rate uses
eligible_respondents (respondents who answered at least one option in the
block, i.e. NOT all-NaN across the block for that respondent), never the
full survey population - many respondents never reach this conditional
section.
"""
import ast
import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_FILES = {
    "year_1": REPO_ROOT / "data/raw/survey_year_1/data_2021-2022.csv",
    "year_2": REPO_ROOT / "data/raw/survey_year_2/data_2023-2024.csv",
    "year_3": REPO_ROOT / "data/raw/survey_year_3/data_2025-2026.csv",
}
GOLD_ROOT = REPO_ROOT / "data/gold"
SILVER_ROOT = REPO_ROOT / "data/silver"

TECH_MAPPING = pd.read_csv(REPO_ROOT / "documentation/mappings/mapping_technology.csv")
TECH_LUT = dict(zip(TECH_MAPPING["raw_label"], TECH_MAPPING["canonical_technology"]))


def extract_option_block_year1_year2(df, code_prefix):
    """Year1/Year2: headers are literal '(code, label)' tuple strings.
    Children codes look like 'P4_f_a ' / 'P4_g_12 ' - match by prefix on the
    code half, label half IS the technology name."""
    items = []  # (col, label)
    for c in df.columns:
        try:
            code, label = ast.literal_eval(c)
        except Exception:
            continue
        if code.startswith(code_prefix) and code.strip() != code_prefix.strip():
            items.append((c, label))
    return items


def extract_option_block_year3(df, code_prefix):
    items = []
    for c in df.columns:
        if c.startswith(code_prefix):
            label = c[len(code_prefix):]
            label = re.sub(r"^\d+[_ ]?", "", label)  # strip the leading sub-index, e.g. '1_MySQL' -> 'MySQL'
            items.append((c, label))
    return items


def build_bridge_for_year(survey_year, path, code_prefix, fmt):
    df = pd.read_csv(path, low_memory=False)
    if fmt == "tuple":
        items = extract_option_block_year1_year2(df, code_prefix)
    else:
        items = extract_option_block_year3(df, code_prefix)

    block_cols = [c for c, _ in items]
    eligible = df[block_cols].notna().any(axis=1)

    respondent_id = [f"{survey_year}_{i:06d}" for i in range(len(df))]

    long_rows = []
    for col, raw_label in items:
        canonical = TECH_LUT.get(raw_label)
        if canonical is None:
            raise ValueError(f"Unmapped technology label in {survey_year}: {raw_label!r} (add to mapping_technology.csv)")
        selected = (df[col].fillna(0).astype(float) == 1.0)
        long_rows.append(pd.DataFrame({
            "respondent_id": respondent_id,
            "survey_year": survey_year,
            "technology": canonical,
            "technology_family": "DATABASE",
            "eligible": eligible.values,
            "selected": selected.values,
        }))
    bridge = pd.concat(long_rows, ignore_index=True)
    # only keep rows for eligible respondents - a non-eligible respondent's
    # "selected=False" is not a real "did not use" signal, it's NOT_ASKED
    bridge = bridge[bridge["eligible"]].drop(columns=["eligible"])
    print(f"[bridge] {survey_year}: {eligible.sum()} eligible respondents x {len(items)} technologies -> {len(bridge)} rows")
    return bridge, eligible.sum()


def build_gold_technology_adoption(bridge_all, eligible_counts):
    g = bridge_all.groupby(["survey_year", "technology"]).agg(
        technology_users=("selected", "sum")
    ).reset_index()
    g["eligible_respondents"] = g["survey_year"].map(eligible_counts)
    g["adoption_rate"] = g["technology_users"] / g["eligible_respondents"]
    g["rank"] = g.groupby("survey_year")["adoption_rate"].rank(ascending=False, method="min").astype(int)
    g = g.sort_values(["survey_year", "rank"])

    # YoY percentage-point change: only meaningful where the technology option
    # existed in both years being compared (e.g. SAP only exists in year_1,
    # so year_1->year_2 delta for SAP is left NULL, not treated as -100pp)
    pivot = g.pivot(index="technology", columns="survey_year", values="adoption_rate")
    g = g.set_index(["technology", "survey_year"])
    if "year_1" in pivot.columns and "year_2" in pivot.columns:
        delta_12 = (pivot["year_2"] - pivot["year_1"]) * 100
        for tech, val in delta_12.items():
            if pd.notna(pivot.loc[tech, "year_1"]) and pd.notna(pivot.loc[tech, "year_2"]):
                g.loc[(tech, "year_2"), "yoy_pp_change_vs_prev_survey"] = val
    if "year_2" in pivot.columns and "year_3" in pivot.columns:
        delta_23 = (pivot["year_3"] - pivot["year_2"]) * 100
        for tech, val in delta_23.items():
            if pd.notna(pivot.loc[tech, "year_2"]) and pd.notna(pivot.loc[tech, "year_3"]):
                g.loc[(tech, "year_3"), "yoy_pp_change_vs_prev_survey"] = val
    g = g.reset_index()

    out_dir = GOLD_ROOT / "gold_technology_adoption_by_year"
    out_dir.mkdir(parents=True, exist_ok=True)
    g.to_csv(out_dir / "gold_technology_adoption_by_year.csv", index=False)
    print(f"[gold] gold_technology_adoption_by_year: {g.shape[0]} rows -> {out_dir}")
    return g


if __name__ == "__main__":
    specs = [
        ("year_1", RAW_FILES["year_1"], "P4_f_", "tuple"),
        ("year_2", RAW_FILES["year_2"], "P4_g_", "tuple"),
        ("year_3", RAW_FILES["year_3"], "4.d.", "dot"),
    ]
    bridges = []
    eligible_counts = {}
    for survey_year, path, prefix, fmt in specs:
        bridge, n_eligible = build_bridge_for_year(survey_year, path, prefix, fmt)
        bridges.append(bridge)
        eligible_counts[survey_year] = n_eligible

    bridge_all = pd.concat(bridges, ignore_index=True)
    bridge_dir = SILVER_ROOT / "bridge_respondent_technology"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    bridge_all.to_csv(bridge_dir / "bridge_respondent_technology.csv", index=False)
    print(f"[silver] bridge_respondent_technology: {bridge_all.shape[0]} rows -> {bridge_dir}")

    build_gold_technology_adoption(bridge_all, eligible_counts)
