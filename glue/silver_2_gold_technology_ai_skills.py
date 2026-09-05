"""
AWS Glue Job: bridge_respondent_technology (DATABASE family) + fact_ai_adoption
+ gold_technology_adoption_by_year + gold_ai_adoption_overview +
gold_skill_priority_score.

Mirrors scripts/build_technology_gold.py, scripts/build_ai_gold.py and
scripts/build_skill_priority_gold.py (validated pandas reference - see
those files for the full rationale on denominators, NOT_AVAILABLE vs
NOT_ASKED, and the skill-score weight redistribution).

Reads Bronze directly (not Silver) for the technology/AI option blocks,
since those wide option columns are not part of fact_respondent - only
fact_respondent's role/seniority/salary_midpoint are joined in for the
skill-score components.

Usage (Glue Job parameters):
  --BRONZE_PATH   s3://state-of-data-tech-challenge/bronze/
  --SILVER_PATH   s3://state-of-data-tech-challenge/silver/respondents/
  --GOLD_PATH     s3://state-of-data-tech-challenge/gold/
  --MAPPINGS_PATH s3://state-of-data-tech-challenge/glue-scripts/mappings/
"""
import sys

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from utils.field_maps import FIELD_CODES_BY_YEAR  # noqa: F401 (kept for consistency with bronze_2_silver.py)

args = getResolvedOptions(sys.argv, ["JOB_NAME", "BRONZE_PATH", "SILVER_PATH", "GOLD_PATH", "MAPPINGS_PATH"])
sc = SparkContext()
spark = SparkSession(sc)

DB_BLOCK_PREFIX = {"year_1": "P4_f_", "year_2": "P4_g_", "year_3": "4.d."}
AI_PRIORITY_CODE = {"year_2": "P3_e", "year_3": "3.e"}
GENAI_BLOCK_PREFIX = {"year_2": "P4_m_", "year_3": "4.j."}


def option_block_columns(columns, prefix, year3_dot):
    items = []
    for c in columns:
        if year3_dot:
            if c.startswith(prefix):
                label = c[len(prefix):]
                items.append((c, label))
        else:
            if c.startswith("('") :
                head = c.split("',", 1)[0].strip("(' ")
                if head.startswith(prefix.strip()) and head != prefix.strip():
                    tail_label = c.split("', '", 1)[1].rstrip("')")
                    items.append((c, tail_label))
    return items


def build_technology_bridge_and_gold(mapping_technology):
    tech_lut = {r["raw_label"]: r["canonical_technology"] for r in mapping_technology.collect()}
    bridges = []
    eligible_counts = {}
    for survey_year, prefix in DB_BLOCK_PREFIX.items():
        df = spark.read.option("header", True).csv(f"{args['BRONZE_PATH'].rstrip('/')}/{survey_year}/")
        items = option_block_columns(df.columns, prefix, year3_dot=(survey_year == "year_3"))
        block_cols = [c for c, _ in items]
        eligible_expr = F.greatest(*[F.col(f"`{c}`").isNotNull().cast("int") for c in block_cols]) == 1
        df = df.withColumn("__eligible", eligible_expr)
        df = df.withColumn(
            "respondent_id",
            F.concat(F.lit(f"{survey_year}_"), F.lpad(F.monotonically_increasing_id().cast("string"), 6, "0")),
        )
        long_parts = []
        for col, raw_label in items:
            canonical = tech_lut.get(raw_label)
            if canonical is None:
                raise ValueError(f"Unmapped technology label in {survey_year}: {raw_label!r}")
            part = df.select(
                "respondent_id", "__eligible",
                F.lit(survey_year).alias("survey_year"),
                F.lit(canonical).alias("technology"),
                F.lit("DATABASE").alias("technology_family"),
                (F.col(f"`{col}`").cast("double") == F.lit(1.0)).alias("selected"),
            )
            long_parts.append(part)
        year_bridge = long_parts[0]
        for p in long_parts[1:]:
            year_bridge = year_bridge.unionByName(p)
        year_bridge = year_bridge.filter(F.col("__eligible")).drop("__eligible")
        bridges.append(year_bridge)
        eligible_counts[survey_year] = df.filter(F.col("__eligible")).count()

    bridge_all = bridges[0]
    for b in bridges[1:]:
        bridge_all = bridge_all.unionByName(b)
    bridge_all.write.mode("overwrite").parquet(f"{args['SILVER_PATH'].rstrip('/').rsplit('/', 1)[0]}/bridge_respondent_technology/")

    adoption = bridge_all.groupBy("survey_year", "technology").agg(
        F.sum(F.col("selected").cast("int")).alias("technology_users")
    )
    eligible_map = spark.createDataFrame(list(eligible_counts.items()), ["survey_year", "eligible_respondents"])
    adoption = adoption.join(eligible_map, "survey_year")
    adoption = adoption.withColumn("adoption_rate", F.col("technology_users") / F.col("eligible_respondents"))
    adoption.write.mode("overwrite").parquet(f"{args['GOLD_PATH'].rstrip('/')}/gold_technology_adoption_by_year/")
    return bridge_all, adoption


if __name__ == "__main__":
    mapping_technology = spark.read.option("header", True).csv(f"{args['MAPPINGS_PATH'].rstrip('/')}/mapping_technology.csv")
    build_technology_bridge_and_gold(mapping_technology)

    # NOTE: fact_ai_adoption, gold_ai_adoption_overview and
    # gold_skill_priority_score follow the exact same pattern as
    # scripts/build_ai_gold.py and scripts/build_skill_priority_gold.py -
    # ported to native PySpark (percentile_approx / when-otherwise, no
    # UDFs) at AWS Glue execution time, once Lab access is available to
    # validate against the real Glue runtime rather than guessing API
    # behavior blind. The pandas reference scripts are the source of
    # truth for the transformation rules until then.
