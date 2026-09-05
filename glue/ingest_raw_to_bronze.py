"""
AWS Glue Job: raw survey files -> S3 Bronze

Adds only ingestion metadata (survey_year, source_file, ingestion_timestamp).
Never touches categories, labels, or values - Bronze must be bit-for-bit
traceable back to the original CSV content (section 18 of the project
prompt). Run once per new raw file drop, not as part of bronze_2_silver.py,
so Bronze always reflects exactly what was ingested even if Silver logic
changes later.

Usage (Glue Job parameters):
  --RAW_PATH     s3://state-of-data-tech-challenge/raw-landing/
  --BRONZE_PATH  s3://state-of-data-tech-challenge/bronze/
  --SURVEY_YEAR  year_1 | year_2 | year_3
  --SOURCE_FILE  data_2021-2022.csv   (etc.)
"""
import sys

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

args = getResolvedOptions(
    sys.argv, ["JOB_NAME", "RAW_PATH", "BRONZE_PATH", "SURVEY_YEAR", "SOURCE_FILE"]
)

sc = SparkContext()
spark = SparkSession(sc)

df = spark.read.option("header", True).csv(f"{args['RAW_PATH'].rstrip('/')}/{args['SOURCE_FILE']}")

df = (
    df.withColumn("survey_year", F.lit(args["SURVEY_YEAR"]))
    .withColumn("source_file", F.lit(args["SOURCE_FILE"]))
    .withColumn("ingestion_timestamp", F.current_timestamp())
)

# reorder so metadata columns lead, matching the local pipeline output
meta_cols = ["survey_year", "source_file", "ingestion_timestamp"]
other_cols = [c for c in df.columns if c not in meta_cols]
df = df.select(*meta_cols, *other_cols)

(
    df.coalesce(1)
    .write.mode("overwrite")
    .option("header", True)
    .csv(f"{args['BRONZE_PATH'].rstrip('/')}/{args['SURVEY_YEAR']}/")
)
