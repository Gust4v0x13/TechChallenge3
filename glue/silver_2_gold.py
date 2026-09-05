"""
AWS Glue Job: Silver -> Gold (gold_market_overview)

table: gold_market_overview
grain: survey_year x dimension x dimension_value
business question: how has the Brazilian data market changed across the
  three surveys? (domain 1, documentation/analytical_domains.md)
dimensions: seniority, gender, current_work_model, region, employment_status
measures: respondent_count, respondent_share_within_year
denominator: total respondents in that survey_year (NOT a cross-year
  denominator - the three surveys are independent samples, not a single
  tracked population; see the harmonization note below)
quality_constraints: none suppressed at this grain (all groups reported);
  small-sample warnings are the responsibility of downstream Gold tables
  that slice by region/state (gold_compensation_by_region)
source_tables: silver/respondents (fact_respondent)

Explicitly NOT computed here: any year-over-year "market grew X%" framing.
A larger respondent_count in one survey year reflects a different (and
differently sized) self-selected sample, not a measured market-size change
(section 24 of the project prompt). Use respondent_share_within_year for
mix comparisons across years instead of raw counts.

Usage (Glue Job parameters):
  --SILVER_PATH  s3://state-of-data-tech-challenge/silver/respondents/
  --GOLD_PATH    s3://state-of-data-tech-challenge/gold/market_overview/
"""
import sys
from functools import reduce

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, ["JOB_NAME", "SILVER_PATH", "GOLD_PATH"])

sc = SparkContext()
spark = SparkSession(sc)

DIMENSIONS = ["seniority", "gender", "current_work_model", "region", "employment_status"]


def share_table(fact_respondent: DataFrame, dimension: str) -> DataFrame:
    counts = fact_respondent.groupBy("survey_year", dimension).agg(F.count(F.lit(1)).alias("respondent_count"))
    year_totals = counts.groupBy("survey_year").agg(F.sum("respondent_count").alias("__year_total"))
    counts = counts.join(F.broadcast(year_totals), "survey_year")
    counts = counts.withColumn(
        "respondent_share_within_year", F.col("respondent_count") / F.col("__year_total")
    )
    counts = (
        counts.withColumn("dimension", F.lit(dimension))
        .withColumnRenamed(dimension, "dimension_value")
        .select("survey_year", "dimension", "dimension_value", "respondent_count", "respondent_share_within_year")
    )
    return counts


if __name__ == "__main__":
    fact_respondent = spark.read.parquet(args["SILVER_PATH"])

    parts = [share_table(fact_respondent, d) for d in DIMENSIONS]
    gold_market_overview = reduce(DataFrame.unionByName, parts)

    (
        gold_market_overview.write
        .mode("overwrite")
        .partitionBy("survey_year")
        .parquet(args["GOLD_PATH"])
    )
