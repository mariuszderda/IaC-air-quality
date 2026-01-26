import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date, avg
from dotenv import load_dotenv

load_dotenv()

# --- Konfiguracja i Walidacja ---
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
CASSANDRA_NODE_IP = os.getenv("CASSANDRA_NODE_IP")

if not all([DATABASE_USER, DATABASE_PASSWORD, CASSANDRA_NODE_IP]):
    raise ValueError("Błąd: Zmienne DATABASE_USER, DATABASE_PASSWORD, CASSANDRA_NODE_IP muszą być ustawione w pliku .env")

# --- Inicjalizacja Sparka z konfiguracją Cassandry ---
spark = SparkSession \
    .builder \
    .appName("Cassandra Air Quality Aggregation") \
    .config("spark.jars.packages", "com.datastax.spark:spark-cassandra-connector_2.12:3.5.0") \
    .config("spark.cassandra.connection.host", CASSANDRA_NODE_IP) \
    .config("spark.cassandra.auth.username", DATABASE_USER) \
    .config("spark.cassandra.auth.password", DATABASE_PASSWORD) \
    .getOrCreate()

try:
    # 1. Odczyt danych z tabeli źródłowej
    print("Odczytywanie danych z air_quality.measurements...")
    df_measurements = spark.read \
        .format("org.apache.spark.sql.cassandra") \
        .options(table="measurements", keyspace="air_quality") \
        .load()

    # 2. FILTROWANIE ODSTAJĄCYCH WARTOŚCI
    # Odrzucamy wartości ujemne oraz fizycznie niemożliwe (np. powyżej 1000)
    print("Filtrowanie błędnych danych (outliers)...")
    df_filtered = df_measurements.filter(
        (col("value") >= 0) & (col("value") <= 1000)
    )

    # 3. Przetwarzanie: Grupowanie i obliczanie średniej
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