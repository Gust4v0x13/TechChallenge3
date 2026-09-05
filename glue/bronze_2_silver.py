"""
AWS Glue Job: Bronze -> Silver

Reads the three State of Data Brasil surveys from S3 Bronze (raw CSV, as
ingested with survey_year/source_file/ingestion_timestamp metadata only -
see the ingestion step notes at the bottom of this file) and produces the
harmonized `fact_respondent` Silver table, partitioned by survey_year.

Mirrors scripts/run_local_pipeline.py (pandas), which is the validated
local reference implementation. Any change to source field codes or
harmonization rules must be applied to both.

Harmonization rules enforced here (documentation/analytical_domains.md):
  1. Bronze is never modified - this job only reads it.
  2. survey_year and a surrogate respondent_id are added, never inferred
     from row order across files.
  3. Categorical normalization uses versioned mapping tables
     (documentation/mappings/*.csv), not inline chained replacements.
  4. Salary bands are parsed into lower/upper/midpoint bounds; open-ended
     bands (e.g. "Acima de R$ 40.001/mes") keep salary_midpoint NULL rather
     than an invented upper bound.
  5. A value present in the source but absent from a mapping table fails
     the job loudly (see the anti-join validation) instead of silently
     becoming NULL/UNKNOWN.

Usage (Glue Job parameters):
  --BRONZE_PATH   s3://state-of-data-tech-challenge/bronze/
  --SILVER_PATH   s3://state-of-data-tech-challenge/silver/respondents/
  --MAPPINGS_PATH s3://state-of-data-tech-challenge/glue-scripts/mappings/
"""
import sys

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType

from utils.field_maps import FIELD_CODES_BY_YEAR

args = getResolvedOptions(
    sys.argv, ["JOB_NAME", "BRONZE_PATH", "SILVER_PATH", "MAPPINGS_PATH"]
)

sc = SparkContext()
spark = SparkSession(sc)

PIPELINE_VERSION = "v1"


def resolve_column(columns, code):
    """Year 1/2 columns are literal '(code, label)' tuple strings; Year 3
    columns are dot-notation strings equal to the code itself. Resolve by
    exact code match on the *code* half only - never by label text or
    position, since question codes can be reused for different questions
    across survey years (see documentation/schema_audit_cross_year.md,
    the P2_q collision note)."""
    if code is None:
        return None
    for c in columns:
        if c == code:  # Year 3: column name IS the code
            return c
        if c.startswith("('") and code.strip() in c.split("',")[0]:
            # Year 1 / Year 2 tuple-string header: ('P1_b ', 'Genero')
            head = c.split("',", 1)[0].strip("(' ")
            if head == code.strip():
                return c
    raise KeyError(f"Source code '{code}' not found among columns")


def read_bronze_year(survey_year, path):
    df = spark.read.option("header", True).csv(f"{path.rstrip('/')}/{survey_year}/")
    field_codes = FIELD_CODES_BY_YEAR[survey_year]
    columns = df.columns
    select_exprs = [F.col("survey_year"), F.col("source_file"), F.col("ingestion_timestamp")]
    for field, code in field_codes.items():
        src_col = resolve_column(columns, code)
        if src_col is None:
            select_exprs.append(F.lit(None).cast("string").alias(field))
        else:
            select_exprs.append(F.col(f"`{src_col}`").alias(field))
    out = df.select(*select_exprs)
    out = out.withColumn(
        "respondent_id",
        F.concat(F.lit(f"{survey_year}_"), F.lpad(F.monotonically_increasing_id().cast("string"), 6, "0")),
    )
    return out


def load_mapping(name, mappings_path):
    return spark.read.option("header", True).csv(f"{mappings_path.rstrip('/')}/mapping_{name}.csv")


def apply_categorical_mapping(df: DataFrame, source_col: str, target_col: str, mapping_df: DataFrame) -> DataFrame:
    """Broadcast-join against a versioned mapping table (section 19 of the
    project prompt). Fails the job if a raw value has no mapping row,
    instead of silently defaulting to UNKNOWN, so schema drift in future
    survey editions is caught immediately."""
    m = F.broadcast(mapping_df.select(
        F.col("raw_value").alias("__raw"), F.col("canonical_value").alias("__canonical")
    ))
    joined = df.join(m, df[source_col] == m["__raw"], "left")

    unmapped = joined.filter(F.col(source_col).isNotNull() & F.col("__canonical").isNull())
    unmapped_count = unmapped.limit(1).count()
    if unmapped_count > 0:
        sample = [r[source_col] for r in unmapped.select(source_col).distinct().limit(20).collect()]
        raise ValueError(f"Unmapped raw values for {target_col} (add to mapping_{target_col}.csv): {sample}")

    unknown_row = mapping_df.filter(F.col("raw_value").isNull()).select("canonical_value").collect()
    unknown_value = unknown_row[0][0] if unknown_row else "UNKNOWN"

    joined = joined.withColumn(
        target_col, F.when(F.col(source_col).isNull(), F.lit(unknown_value)).otherwise(F.col("__canonical"))
    )
    return joined.drop("__raw", "__canonical")


def apply_salary_parsing(df: DataFrame, source_col: str, mapping_df: DataFrame) -> DataFrame:
    m = F.broadcast(
        mapping_df.select(
            F.col("raw_value").alias("__raw"),
            F.col("salary_lower_bound").cast(DoubleType()).alias("salary_lower_bound"),
            F.col("salary_upper_bound").cast(DoubleType()).alias("salary_upper_bound"),
            F.col("salary_midpoint").cast(DoubleType()).alias("salary_midpoint"),
            F.col("open_ended").alias("salary_open_ended"),
            F.col("anomaly_flag").alias("salary_anomaly_flag"),
        )
    )
    out = df.withColumnRenamed(source_col, "salary_band_raw").join(
        m, F.col("salary_band_raw") == m["__raw"], "left"
    ).drop("__raw")
    out = out.withColumn(
        "salary_anomaly_flag",
        F.when(F.col("salary_anomaly_flag").isNull(), F.lit(False)).otherwise(F.col("salary_anomaly_flag")),
    )
    return out


def build_fact_respondent():
    bronze_path = args["BRONZE_PATH"]
    mappings_path = args["MAPPINGS_PATH"]

    mapping_gender = load_mapping("gender", mappings_path)
    mapping_seniority = load_mapping("seniority", mappings_path)
    mapping_work_model = load_mapping("work_model", mappings_path)
    mapping_employment_status = load_mapping("employment_status", mappings_path)
    mapping_salary = load_mapping("salary_band", mappings_path)

    frames = []
    for survey_year in FIELD_CODES_BY_YEAR:
        df = read_bronze_year(survey_year, bronze_path)

        df = apply_categorical_mapping(df, "gender", "gender_canonical", mapping_gender)
        df = df.drop("gender").withColumnRenamed("gender_canonical", "gender")

        df = apply_categorical_mapping(df, "seniority", "seniority_canonical", mapping_seniority)
        df = df.drop("seniority").withColumnRenamed("seniority_canonical", "seniority")

        df = apply_categorical_mapping(df, "employment_status", "employment_status_canonical", mapping_employment_status)
        df = df.drop("employment_status").withColumnRenamed("employment_status_canonical", "employment_status")

        df = apply_categorical_mapping(df, "current_work_model", "current_work_model_canonical", mapping_work_model)
        df = df.drop("current_work_model").withColumnRenamed("current_work_model_canonical", "current_work_model")

        df = apply_categorical_mapping(df, "ideal_work_model", "ideal_work_model_canonical", mapping_work_model)
        df = df.drop("ideal_work_model").withColumnRenamed("ideal_work_model_canonical", "ideal_work_model")

        df = apply_salary_parsing(df, "salary_band", mapping_salary)

        df = df.withColumn("manager_flag", F.col("manager_flag").cast("double") == F.lit(1.0))
        df = df.withColumnRenamed("current_role", "current_role_raw")
        df = df.withColumnRenamed("ethnicity", "ethnicity_raw")
        df = df.withColumnRenamed("pcd_flag", "pcd_flag_raw")
        df = df.withColumnRenamed("company_size", "company_size_raw")
        df = df.withColumnRenamed("rto_attitude", "rto_attitude_raw")

        df = df.withColumn("pipeline_version", F.lit(PIPELINE_VERSION))
        df = df.withColumn("processing_timestamp", F.current_timestamp())

        frames.append(df)

    fact_respondent = frames[0]
    for f in frames[1:]:
        fact_respondent = fact_respondent.unionByName(f, allowMissingColumns=True)

    return fact_respondent


if __name__ == "__main__":
    fact_respondent = build_fact_respondent()
    (
        fact_respondent.write
        .mode("overwrite")
        .partitionBy("survey_year")
        .parquet(args["SILVER_PATH"])
    )
