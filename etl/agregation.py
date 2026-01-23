import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date, avg
from dotenv import load_dotenv

load_dotenv()

DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
node_ips = os.getenv("CASSANDRA_NODE_IP")

spark = SparkSession \
    .builder \
    .appName("Cassandra Air Quality Aggregation") \
    .getOrCreate()


try:
    # 1. Odczyt danych z tabeli źródłowej
    print("Odczytywanie danych z air_quality.measurements...")
    df_measurements = spark.read \
        .format("org.apache.spark.sql.cassandra") \
        .options(table="measurements", keyspace="air_quality") \
        .load()

    # 2. FILTROWANIE ODSTAJĄCYCH WARTOŚCI
    # Odrzucamy wartości ujemne oraz fizycznie niemożliwe (np. powyżej 1000 dla NO2)
    print("Filtrowanie błędnych danych (outliers)...")
    df_filtered = df_measurements.filter(
        (col("value") >= 0) & (col("value") <= 1000)
        )

    # 3. Przetwarzanie: Grupowanie i obliczanie średniej na przefiltrowanych danych
    print("Obliczanie średnich dziennych z oczyszczonych danych...")
    df_daily_avg = df_filtered \
        .withColumn("day", to_date(col("measure_date"))) \
        .groupBy("station_id", "day", "name", "parameter", "unit") \
        .agg(avg("value").alias("avg_value"))

    # Podgląd wyników
    df_daily_avg.show(5)

    # 4. Zapis do tabeli docelowej
    print("Zapisywanie oczyszczonych średnich do air_quality.daily_averages...")
    df_daily_avg.write \
        .format("org.apache.spark.sql.cassandra") \
        .mode("append") \
        .options(table="daily_averages", keyspace="air_quality") \
        .save()

    print("Agregacja i czyszczenie zakończone sukcesem!")

except Exception as e:
    print(f"Wystąpił błąd: {e}")

finally:
    spark.stop()