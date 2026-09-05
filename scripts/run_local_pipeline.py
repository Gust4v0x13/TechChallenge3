"""
Local vertical-slice pipeline: Bronze -> Silver -> Gold.

Runs on pandas because PySpark cannot be installed in this environment
(no package-index egress). Logic mirrors glue/bronze_2_silver.py and
glue/silver_2_gold.py, which contain the equivalent AWS Glue PySpark jobs
for actual deployment. Do not let this script and the Glue scripts drift:
any transformation rule change must be applied to both.

Outputs (mirrors the proposed S3 layout):
  data/bronze/year_N/data.csv
  data/silver/respondents/survey_year=N/part.parquet
  data/gold/market_overview/part.parquet + .csv
"""
import ast
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from field_maps import FIELD_CODES_BY_YEAR

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_VERSION = "v1"

RAW_FILES = {
    "year_1": REPO_ROOT / "data/raw/survey_year_1/data_2021-2022.csv",
    "year_2": REPO_ROOT / "data/raw/survey_year_2/data_2023-2024.csv",
    "year_3": REPO_ROOT / "data/raw/survey_year_3/data_2025-2026.csv",
}

BRONZE_DIR = REPO_ROOT / "data/bronze"
SILVER_DIR = REPO_ROOT / "data/silver/respondents"
GOLD_DIR = REPO_ROOT / "data/gold/market_overview"


# ---------------------------------------------------------------------------
# Bronze
# ---------------------------------------------------------------------------

def build_bronze():
    """Bronze: preserve raw survey data as received, only ADD metadata columns.
    Never alter categories, remove columns, or modify responses (see
    documentation/analytical_domains.md, harmonization rule #1)."""
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    ingestion_ts = datetime.now(timezone.utc).isoformat()
    bronze_frames = {}
    for survey_year, path in RAW_FILES.items():
        df = pd.read_csv(path, low_memory=False)
        df.insert(0, "survey_year", survey_year)
        df.insert(1, "source_file", path.name)
        df.insert(2, "ingestion_timestamp", ingestion_ts)
        out_dir = BRONZE_DIR / survey_year
        out_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_dir / "data.csv", index=False)
        bronze_frames[survey_year] = df
        print(f"[bronze] {survey_year}: {df.shape[0]} rows x {df.shape[1]} cols -> {out_dir/'data.csv'}")
    return bronze_frames


# ---------------------------------------------------------------------------
# Silver
# ---------------------------------------------------------------------------

def _resolve_year1_year2_columns(df, field_codes):
    """Year 1 / Year 2 headers are '(code, label)' tuple strings. Resolve by
    exact code match (never by position, never by label text)."""
    code_to_col = {}
    for c in df.columns:
        try:
            code, _label = ast.literal_eval(c)
        except Exception:
            continue
        code_to_col[code] = c
    resolved = {}
    for field, code in field_codes.items():
        if code is None:
            resolved[field] = None
            continue
        col = code_to_col.get(code)
        if col is None:
            raise KeyError(f"Expected source code '{code}' for field '{field}' not found in columns")
        resolved[field] = col
    return resolved


def _resolve_year3_columns(df, field_codes):
    resolved = {}
    for field, code in field_codes.items():
        if code is None:
            resolved[field] = None
            continue
        if code not in df.columns:
            raise KeyError(f"Expected source column '{code}' for field '{field}' not found in Year 3 columns")
        resolved[field] = code
    return resolved


def load_mapping(name):
    path = REPO_ROOT / f"documentation/mappings/mapping_{name}.csv"
    return pd.read_csv(path)


def apply_categorical_mapping(series, mapping_df, unknown_value="UNKNOWN"):
    lut = dict(zip(mapping_df["raw_value"], mapping_df["canonical_value"]))
    lut_null = mapping_df.loc[mapping_df["raw_value"].isna(), "canonical_value"]
    fill = lut_null.iloc[0] if len(lut_null) else unknown_value
    mapped = series.map(lut)
    mapped = mapped.where(series.notna(), fill)
    # anything present but not found in the mapping table is a real gap -
    # surface it rather than silently forcing it to UNKNOWN
    unmapped_mask = series.notna() & mapped.isna()
    if unmapped_mask.any():
        missing_values = sorted(series[unmapped_mask].unique().tolist())
        raise ValueError(f"Unmapped raw values found (add to mapping table): {missing_values}")
    return mapped


SALARY_MAPPING = load_mapping("salary_band") if (REPO_ROOT / "documentation/mappings/mapping_salary_band.csv").exists() else None


def parse_salary_band(series):
    band_map = SALARY_MAPPING.set_index("raw_value")
    lower = series.map(band_map["salary_lower_bound"])
    upper = series.map(band_map["salary_upper_bound"])
    midpoint = series.map(band_map["salary_midpoint"])
    open_ended = series.map(band_map["open_ended"])
    anomaly = series.map(band_map["anomaly_flag"]).fillna(False)
    return lower, upper, midpoint, open_ended, anomaly


def build_silver(bronze_frames):
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    mapping_gender = load_mapping("gender")
    mapping_seniority = load_mapping("seniority")
    mapping_work_model = load_mapping("work_model")
    mapping_employment_status = load_mapping("employment_status")
    mapping_role = load_mapping("role")
    # role mapping has (raw_value, survey_year_scope) as the natural key since
    # a couple of raw labels only make sense within one year's scope
    role_lut = {}
    for _, row in mapping_role.iterrows():
        scopes = ["year_1", "year_2", "year_3"] if row["survey_year_scope"] == "all" else str(row["survey_year_scope"]).split(",")
        for sy in scopes:
            role_lut[(sy, row["raw_value"] if not pd.isna(row["raw_value"]) else None)] = row["canonical_role"]

    silver_parts = []
    for survey_year, df in bronze_frames.items():
        field_codes = FIELD_CODES_BY_YEAR[survey_year]
        if survey_year in ("year_1", "year_2"):
            resolved = _resolve_year1_year2_columns(df, field_codes)
        else:
            resolved = _resolve_year3_columns(df, field_codes)

        out = pd.DataFrame(index=df.index)
        out["survey_year"] = survey_year
        out["respondent_id"] = [f"{survey_year}_{i:06d}" for i in range(len(df))]

        def col(field):
            c = resolved.get(field)
            return df[c] if c is not None else pd.Series([None] * len(df), index=df.index)

        out["age_band"] = col("age_band")
        out["gender"] = apply_categorical_mapping(col("gender"), mapping_gender)
        out["ethnicity_raw"] = col("ethnicity")  # not yet harmonized - Year1 has no source
        out["pcd_flag_raw"] = col("pcd_flag")
        out["state"] = col("state")
        out["region"] = col("region")
        out["education_level"] = col("education_level")
        out["education_area"] = col("education_area")
        out["employment_status"] = apply_categorical_mapping(col("employment_status"), mapping_employment_status)
        out["sector"] = col("sector")
        out["company_size_raw"] = col("company_size")
        out["manager_flag"] = col("manager_flag").map({1.0: True, 0.0: False})
        out["current_role_raw"] = col("current_role")
        role_series = col("current_role")
        out["current_role"] = role_series.map(lambda v: role_lut.get((survey_year, v if pd.notna(v) else None), "UNKNOWN"))
        unmapped_roles = role_series.notna() & (out["current_role"] == "UNKNOWN") & (~role_series.map(lambda v: (survey_year, v) in role_lut))
        if unmapped_roles.any():
            raise ValueError(f"Unmapped current_role values in {survey_year}: {sorted(role_series[unmapped_roles].unique().tolist())}")
        out["seniority"] = apply_categorical_mapping(col("seniority"), mapping_seniority)
        salary_raw = col("salary_band")
        out["salary_band_raw"] = salary_raw
        (out["salary_lower_bound"], out["salary_upper_bound"], out["salary_midpoint"],
         out["salary_open_ended"], out["salary_anomaly_flag"]) = parse_salary_band(salary_raw)
        out["data_experience_band"] = col("data_experience_band")
        out["it_experience_band"] = col("it_experience_band")
        out["current_work_model"] = apply_categorical_mapping(col("current_work_model"), mapping_work_model)
        out["ideal_work_model"] = apply_categorical_mapping(col("ideal_work_model"), mapping_work_model)
        out["rto_attitude_raw"] = col("rto_attitude")

        out["source_file"] = df["source_file"]
        out["ingestion_timestamp"] = df["ingestion_timestamp"]
        out["pipeline_version"] = PIPELINE_VERSION
        out["processing_timestamp"] = datetime.now(timezone.utc).isoformat()

        part_dir = SILVER_DIR / f"survey_year={survey_year}"
        part_dir.mkdir(parents=True, exist_ok=True)
        # local validation writes CSV (no pyarrow available in this sandbox);
        # the AWS Glue job (glue/bronze_2_silver.py) writes real Parquet via Spark.
        out.to_csv(part_dir / "part.csv", index=False)
        print(f"[silver] {survey_year}: {out.shape[0]} rows -> {part_dir/'part.csv'}")
        silver_parts.append(out)

    return pd.concat(silver_parts, ignore_index=True)


# ---------------------------------------------------------------------------
# Gold
# ---------------------------------------------------------------------------

def build_gold_market_overview(fact_respondent):
    """gold_market_overview
    grain: survey_year
    business question: how has the Brazilian data market changed across surveys?
    measures: respondent_count, respondent_share is NOT computed as market growth
    (each survey is a separate, differently-sized sample - see harmonization rule).
    """
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    total_by_year = fact_respondent.groupby("survey_year").size().rename("respondent_count")

    def share_table(dim):
        g = (
            fact_respondent.groupby(["survey_year", dim])
            .size()
            .rename("respondent_count")
            .reset_index()
        )
        g["respondent_share_within_year"] = g["respondent_count"] / g.groupby("survey_year")["respondent_count"].transform("sum")
        g["dimension"] = dim
        g = g.rename(columns={dim: "dimension_value"})
        return g[["survey_year", "dimension", "dimension_value", "respondent_count", "respondent_share_within_year"]]

    dims = ["seniority", "gender", "current_work_model", "region", "employment_status"]
    parts = [share_table(d) for d in dims]
    gold = pd.concat(parts, ignore_index=True)

    # local validation writes CSV only; AWS Glue job writes Parquet via Spark.
    gold.to_csv(GOLD_DIR / "gold_market_overview.csv", index=False)
    print(f"[gold] gold_market_overview: {gold.shape[0]} rows -> {GOLD_DIR}")
    print("\nRespondent count by survey_year (raw sample size, NOT a market-size claim):")
    print(total_by_year.to_string())
    return gold


if __name__ == "__main__":
    bronze_frames = build_bronze()
    fact_respondent = build_silver(bronze_frames)
    build_gold_market_overview(fact_respondent)
