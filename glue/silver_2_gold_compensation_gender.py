"""
AWS Glue Job: Silver -> Gold (compensation + gender representation)

Mirrors scripts/build_compensation_gender_gold.py (validated pandas
reference). Produces:
  gold_compensation_by_role       grain: survey_year x current_role
  gold_compensation_by_seniority  grain: survey_year x seniority
  gold_compensation_by_region     grain: survey_year x region
  gold_compensation_by_work_model grain: survey_year x current_work_model
  gold_gender_representation      grain: survey_year x gender x cross_dimension x cross_dimension_value

Salary statistics (median/mean/p25/p75) always exclude rows with a NULL
salary_midpoint (open-ended bands / anomalies); respondent_count still
counts them so the denominator is never silently understated.
low_sample_flag marks any group with respondent_count < MIN_SAMPLE_SIZE
(section 30 of the project prompt) - never publish a small-n comparison
without a visible warning.

Usage (Glue Job parameters):
  --SILVER_PATH s3://state-of-data-tech-challenge/silver/respondents/
  --GOLD_PATH   s3://state-of-data-tech-challenge/gold/
"""
import sys

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, ["JOB_NAME", "SILVER_PATH", "GOLD_PATH"])
sc = SparkContext()
spark = SparkSession(sc)

MIN_SAMPLE_SIZE = 30


def salary_stats(df: DataFrame, group_cols):
    known = df.filter(F.col("salary_midpoint").isNotNull())
    counts = df.groupBy(*group_cols).agg(F.count(F.lit(1)).alias("respondent_count"))
    stats = known.groupBy(*group_cols).agg(
        F.count(F.lit(1)).alias("salary_known_count"),
        F.expr("percentile_approx(salary_midpoint, 0.5)").alias("median_salary_midpoint"),
        F.mean("salary_midpoint").alias("mean_salary_midpoint"),
        F.expr("percentile_approx(salary_midpoint, 0.25)").alias("salary_p25"),
        F.expr("percentile_approx(salary_midpoint, 0.75)").alias("salary_p75"),
    )
    out = counts.join(stats, group_cols, "left")
    out = out.withColumn("salary_iqr", F.col("salary_p75") - F.col("salary_p25"))
    out = out.withColumn("low_sample_flag", F.col("respondent_count") < F.lit(MIN_SAMPLE_SIZE))
    return out


def gender_representation(fact: DataFrame) -> DataFrame:
    def dimension_table(cross_dimension, group_col):
        if group_col is None:
            sub = fact.withColumn("__bucket", F.lit("ALL"))
        else:
            sub = fact.filter(F.col(group_col) != "UNKNOWN") if group_col in ("seniority", "current_role") else fact.filter(F.col(group_col).isNotNull())
            sub = sub.withColumn("__bucket", F.col(group_col))
        totals = sub.groupBy("survey_year", "__bucket").agg(F.count(F.lit(1)).alias("bucket_total"))
        cell = sub.groupBy("survey_year", "__bucket", "gender").agg(F.count(F.lit(1)).alias("respondent_count"))
        cell = cell.join(totals, ["survey_year", "__bucket"])
        cell = cell.withColumn("share_within_bucket", F.col("respondent_count") / F.col("bucket_total"))
        med = sub.filter(F.col("salary_midpoint").isNotNull()).groupBy("survey_year", "__bucket", "gender").agg(
            F.expr("percentile_approx(salary_midpoint, 0.5)").alias("median_salary_midpoint")
        )
        cell = cell.join(med, ["survey_year", "__bucket", "gender"], "left")
        cell = cell.withColumn("cross_dimension", F.lit(cross_dimension)).withColumnRenamed("__bucket", "cross_dimension_value")
        cell = cell.withColumn("low_sample_flag", F.col("respondent_count") < F.lit(MIN_SAMPLE_SIZE))
        return cell.select("survey_year", "gender", "cross_dimension", "cross_dimension_value",
                            "respondent_count", "bucket_total", "share_within_bucket",
                            "median_salary_midpoint", "low_sample_flag")

    parts = [
        dimension_table("overall", None),
        dimension_table("seniority", "seniority"),
        dimension_table("current_role", "current_role"),
        dimension_table("region", "region"),
    ]
    out = parts[0]
    for p in parts[1:]:
        out = out.unionByName(p)
    return out


def write_gold(df: DataFrame, table_name: str):
    (df.write.mode("overwrite").parquet(f"{args['GOLD_PATH'].rstrip('/')}/{table_name}/"))


if __name__ == "__main__":
    fact_respondent = spark.read.parquet(args["SILVER_PATH"])

    write_gold(salary_stats(fact_respondent.filter(F.col("current_role") != "UNKNOWN"), ["survey_year", "current_role"]), "gold_compensation_by_role")
    write_gold(salary_stats(fact_respondent.filter(F.col("seniority") != "UNKNOWN"), ["survey_year", "seniority"]), "gold_compensation_by_seniority")
    write_gold(salary_stats(fact_respondent.filter(F.col("region").isNotNull()), ["survey_year", "region"]), "gold_compensation_by_region")
    write_gold(salary_stats(fact_respondent.filter(F.col("current_work_model") != "UNKNOWN"), ["survey_year", "current_work_model"]), "gold_compensation_by_work_model")
    write_gold(gender_representation(fact_respondent), "gold_gender_representation")
