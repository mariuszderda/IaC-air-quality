import os
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, to_timestamp
from pyspark.sql.types import FloatType, StringType
from dotenv import load_dotenv

load_dotenv()

DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")

auth_provider = PlainTextAuthProvider(
    username= DATABASE_USER, password=DATABASE_PASSWORD
    )

# node_ips= ['34.118.23.223']
node_ips= ['192.168.0.24']
spark = SparkSession \
    .builder \
    .appName("Cassandra Air Quality") \
    .config("spark.jars.packages", "com.datastax.spark:spark-cassandra-connector_2.12:3.5.0") \
    .config("spark.cassandra.connection.host", node_ips[0]) \
    .config("spark.cassandra.auth.username", DATABASE_USER) \
    .config("spark.cassandra.auth.password", DATABASE_PASSWORD) \
    .config("spark.driver.extraJavaOptions", "--add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.lang.invoke=ALL-UNNAMED --add-opens=java.base/java.lang.reflect=ALL-UNNAMED --add-opens=java.base/java.io=ALL-UNNAMED --add-opens=java.base/java.net=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.util.concurrent=ALL-UNNAMED --add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/sun.nio.cs=ALL-UNNAMED --add-opens=java.base/sun.security.action=ALL-UNNAMED --add-opens=java.base/sun.util.calendar=ALL-UNNAMED") \
    .config("spark.executor.extraJavaOptions", "--add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.lang.invoke=ALL-UNNAMED --add-opens=java.base/java.lang.reflect=ALL-UNNAMED --add-opens=java.base/java.io=ALL-UNNAMED --add-opens=java.base/java.net=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.util.concurrent=ALL-UNNAMED --add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/sun.nio.cs=ALL-UNNAMED --add-opens=java.base/sun.security.action=ALL-UNNAMED --add-opens=java.base/sun.util.calendar=ALL-UNNAMED") \
    .getOrCreate()
df_raw = spark.read.option("header", "true").csv('../data/sensors.csv')

df_cleaned = df_raw \
        .withColumnRenamed("sensor_id", "station_id") \
        .withColumn("station_id", col("station_id").cast(StringType())) \
        .withColumn("value", col("value").cast(FloatType())) \
        .withColumnRenamed("date_utc", "measure_date") \
        .withColumn("measure_date", to_timestamp(col("measure_date"))) \
        .select("station_id", "value", "unit", "parameter", "measure_date")

print("Podgląd danych do zapisu:")
df_cleaned.printSchema()
df_cleaned.show(5)


try:
    df_cleaned.write \
        .format("org.apache.spark.sql.cassandra") \
        .mode("append") \
        .options(table="measurements", keyspace="air_quality") \
        .save()
    print("Dane zostały poprawnie zapisane do Cassandry.")
except Exception as e:
    print(f"Error message: {e}")

spark.stop()