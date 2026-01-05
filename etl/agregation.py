# %%
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date, avg, first
from dotenv import load_dotenv

load_dotenv()
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
NODE_IP = '34.116.155.182'

spark = SparkSession.builder \
    .appName("Cassandra Daily Aggregation") \
    .config("spark.jars.packages", "com.datastax.spark:spark-cassandra-connector_2.12:3.5.0") \
    .config("spark.cassandra.connection.host", NODE_IP) \
    .config("spark.cassandra.auth.username", DATABASE_USER) \
    .config("spark.cassandra.auth.password", DATABASE_PASSWORD) \
    .config("spark.driver.extraJavaOptions", "--add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.lang.invoke=ALL-UNNAMED --add-opens=java.base/java.lang.reflect=ALL-UNNAMED --add-opens=java.base/java.io=ALL-UNNAMED --add-opens=java.base/java.net=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.util.concurrent=ALL-UNNAMED --add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/sun.nio.cs=ALL-UNNAMED --add-opens=java.base/sun.security.action=ALL-UNNAMED --add-opens=java.base/sun.util.calendar=ALL-UNNAMED") \
    .config("spark.executor.extraJavaOptions", "--add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.lang.invoke=ALL-UNNAMED --add-opens=java.base/java.lang.reflect=ALL-UNNAMED --add-opens=java.base/java.io=ALL-UNNAMED --add-opens=java.base/java.net=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.util.concurrent=ALL-UNNAMED --add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/sun.nio.cs=ALL-UNNAMED --add-opens=java.base/sun.security.action=ALL-UNNAMED --add-opens=java.base/sun.util.calendar=ALL-UNNAMED") \
    .getOrCreate()


df = spark.read \
    .format("org.apache.spark.sql.cassandra") \
    .options(table="measurements", keyspace="air_quality") \
    .load()

daily_df = df.withColumn("day", to_date(col("measure_date"))) \
    .groupBy("station_id", "day") \
    .agg(
        avg("value").alias("avg_value"),
        first("unit").alias("unit"),
        first("parameter").alias("parameter")
    )

print("Wyliczono średnie dzienne. Przykładowe dane:")

try:
    daily_df.write \
        .format("org.apache.spark.sql.cassandra") \
        .mode("append") \
        .options(table="daily_averages", keyspace="air_quality") \
        .save()
    print("Zapisano średnie do tabeli daily_averages.")
except Exception as e:
    print(f"Błąd podczas zapisu: {e}")

spark.stop()