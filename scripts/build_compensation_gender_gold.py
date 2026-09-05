"""
Gold: compensation and gender-representation tables built directly from
fact_respondent (Silver). No new bridge tables needed for this batch.

Tables produced:
  gold_compensation_by_role
  gold_compensation_by_seniority
  gold_compensation_by_region
  gold_compensation_by_work_model
  gold_gender_representation

Salary statistics always exclude rows with a NULL salary_midpoint
(open-ended bands and the one confirmed data-entry anomaly - see
documentation/data_quality_report.md section 3) rather than imputing a
value. respondent_count still includes those rows so the denominator is
never silently understated; salary_known_count is reported alongside so
readers can see how many respondents actually fed the salary statistics.
"""
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SILVER_DIR = REPO_ROOT / "data/silver/respondents"
GOLD_ROOT = REPO_ROOT / "data/gold"

MIN_SAMPLE_SIZE = 30  # section 30 of the project prompt: never publish small-n comparisons silently


def load_fact_respondent():
    parts = []
    for p in sorted(SILVER_DIR.glob("survey_year=*/part.csv")):
        parts.append(pd.read_csv(p))
    return pd.concat(parts, ignore_index=True)


def salary_stats(df: pd.DataFrame, group_cols):
    g = df.groupby(group_cols, dropna=False)
    respondent_count = g.size().rename("respondent_count")
    known = df.dropna(subset=["salary_midpoint"]).groupby(group_cols, dropna=False)["salary_midpoint"]
    salary_known_count = known.count().rename("salary_known_count")
    median_salary_midpoint = known.median().rename("median_salary_midpoint")
    mean_salary_midpoint = known.mean().rename("mean_salary_midpoint")
    p25 = known.quantile(0.25).rename("salary_p25")
    p75 = known.quantile(0.75).rename("salary_p75")
    out = pd.concat(
        [respondent_count, salary_known_count, median_salary_midpoint, mean_salary_midpoint, p25, p75], axis=1
    ).reset_index()
    out["salary_iqr"] = out["salary_p75"] - out["salary_p25"]
    out["low_sample_flag"] = out["respondent_count"] < MIN_SAMPLE_SIZE
    return out


def write_gold(df, table_name):
    out_dir = GOLD_ROOT / table_name
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / f"{table_name}.csv", index=False)
    print(f"[gold] {table_name}: {df.shape[0]} rows -> {out_dir/(table_name+'.csv')}")


def build_compensation_by_role(fact):
    df = fact[fact["current_role"] != "UNKNOWN"]
    out = salary_stats(df, ["survey_year", "current_role"])
    write_gold(out, "gold_compensation_by_role")
    return out


def build_compensation_by_seniority(fact):
    df = fact[fact["seniority"] != "UNKNOWN"]
    out = salary_stats(df, ["survey_year", "seniority"])
    write_gold(out, "gold_compensation_by_seniority")
    return out


def build_compensation_by_region(fact):
    df = fact.dropna(subset=["region"])
    out = salary_stats(df, ["survey_year", "region"])
    write_gold(out, "gold_compensation_by_region")
    return out


def build_compensation_by_work_model(fact):
    df = fact[fact["current_work_model"] != "UNKNOWN"]
    out = salary_stats(df, ["survey_year", "current_work_model"])
    write_gold(out, "gold_compensation_by_work_model")
    return out


def build_gender_representation(fact):
    """grain: survey_year x gender x cross_dimension x cross_dimension_value
    - cross_dimension='overall' -> gender's share of the whole survey_year (representation)
    - cross_dimension='seniority'/'current_role'/'region' -> gender's share WITHIN that bucket
      (e.g. what % of SENIOR respondents are FEMALE), which is what "representation" means
      in domain 7 of analytical_domains.md, plus each cell's median salary."""
    rows = []

    def add_dimension(cross_dimension, group_col=None):
        if group_col is None:
            sub = fact.copy()
            sub["__bucket"] = "ALL"
        else:
            sub = fact[fact[group_col] != "UNKNOWN"].copy() if group_col in ("seniority", "current_role", "current_work_model") else fact.dropna(subset=[group_col]).copy()
            sub["__bucket"] = sub[group_col]

        bucket_totals = sub.groupby(["survey_year", "__bucket"]).size().rename("bucket_total")
        cell = sub.groupby(["survey_year", "__bucket", "gender"]).size().rename("respondent_count").reset_index()
        cell = cell.merge(bucket_totals.reset_index(), on=["survey_year", "__bucket"])
        cell["share_within_bucket"] = cell["respondent_count"] / cell["bucket_total"]

        known = sub.dropna(subset=["salary_midpoint"]).groupby(["survey_year", "__bucket", "gender"])["salary_midpoint"].median().rename("median_salary_midpoint")
        cell = cell.merge(known.reset_index(), on=["survey_year", "__bucket", "gender"], how="left")

        cell["cross_dimension"] = cross_dimension
        cell = cell.rename(columns={"__bucket": "cross_dimension_value"})
        cell["low_sample_flag"] = cell["respondent_count"] < MIN_SAMPLE_SIZE
        rows.append(cell[["survey_year", "gender", "cross_dimension", "cross_dimension_value",
                           "respondent_count", "bucket_total", "share_within_bucket",
                           "median_salary_midpoint", "low_sample_flag"]])

    add_dimension("overall")
    add_dimension("seniority", "seniority")
    add_dimension("current_role", "current_role")
    add_dimension("region", "region")

    out = pd.concat(rows, ignore_index=True)
    write_gold(out, "gold_gender_representation")
    return out


if __name__ == "__main__":
    fact = load_fact_respondent()
    build_compensation_by_role(fact)
    build_compensation_by_seniority(fact)
    build_compensation_by_region(fact)
    build_compensation_by_work_model(fact)
    build_gender_representation(fact)
