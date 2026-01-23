import os
import time
import json
import datetime
from openaq import OpenAQ
from dotenv import load_dotenv
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import BatchStatement

load_dotenv()

# === KONFIGURACJA ===
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
NODE_IP = os.getenv("CASSANDRA_NODE_IP")

CHECKPOINT_FILE = 'checkpoint.json'
SENSORS_FILE = '../data/location_list.csv'

# === POŁĄCZENIE Z CASSANDRĄ ===
auth_provider = PlainTextAuthProvider(username=DATABASE_USER, password=DATABASE_PASSWORD)
cluster = Cluster([NODE_IP], auth_provider=auth_provider)
session = cluster.connect('air_quality')

# Przygotowanie zapytania (Prepared Statement) dla wydajności
insert_stmt = session.prepare("""
    INSERT INTO measurements (station_id, value, unit, parameter, measure_date)
    VALUES (?, ?, ?, ?, ?)
""")

def load_checkpoints():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_checkpoint(data):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_iso_date_str(date_obj):
    # Konwersja datetime na string ISO dla API OpenAQ
    return date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")

def process_sensor(client, sensor_id, last_date):
    print(f"\n--- Przetwarzanie sensora: {sensor_id} ---")
    print(f"Szukam danych nowszych niż: {last_date}")

    current_page = 1
    # Używamy zmiennej do śledzenia najnowszej daty w tej partii
    max_date_in_batch = last_date

    while True:
        try:
            # Pobieramy dane sortowane od najstarszych do najnowszych (asc)
            # Dzięki temu, jeśli przerwiemy, wiemy, że mamy ciągłość do pewnego momentu
            response = client.measurements.list(
                sensors_id=sensor_id,
                datetime_from=last_date,
                page=current_page,
                limit=1000
            )
        except Exception as e:
            print(f"Błąd API: {e}")
            break

        results = response.results
        if not results:
            print("Brak nowych danych.")
            break

        print(f"Strona {current_page}: pobrano {len(results)} rekordów. Zapisuję do DB...")

        # Używamy BatchStatement do grupowania insertów (szybciej)
        batch = BatchStatement()
        count = 0

        for item in results:
            try:
                # Parsowanie daty
                measure_dt = item.period.datetime_from.utc
                # Konwersja na obiekt datetime (dla Cassandry i porównań)
                # OpenAQ library zwraca już obiekty datetime, ale upewnijmy się
                if isinstance(measure_dt, str):
                    measure_dt = datetime.datetime.fromisoformat(measure_dt.replace("Z", "+00:00"))

                # Dodanie do batcha
                # STATION_01 to placeholder - musisz ustalić skąd brać ID stacji (z pliku csv?)
                batch.add(insert_stmt, (
                    str(sensor_id),
                    float(item.value),
                    item.parameter.units,
                    item.parameter.name,
                    measure_dt
                ))
                count += 1

                # Aktualizacja najnowszej daty
                current_iso = get_iso_date_str(measure_dt)
                if current_iso > max_date_in_batch:
                    max_date_in_batch = current_iso

                # Cassandra ma limity wielkości batcha, wysyłaj co 100 rekordów
                if count >= 100:
                    session.execute(batch)
                    batch = BatchStatement()
                    count = 0

            except Exception as e:
                print(f"Błąd parsowania rekordu: {e}")
                continue

        # Wyślij resztkę batcha
        if count > 0:
            session.execute(batch)

        # Zapisz checkpoint po każdej pomyślnej stronie
        checkpoints[str(sensor_id)] = max_date_in_batch
        save_checkpoint(checkpoints)

        current_page += 1
        time.sleep(1.2) # Grzeczność wobec API

        if current_page > 20: # Zabezpieczenie przed nieskończoną pętlą w jednym uruchomieniu
            print("Osiągnięto limit stron na jedno uruchomienie.")
            break

# === MAIN ===
try:
    with open(SENSORS_FILE, 'r') as f:
        sensors_list = [line.strip() for line in f if line.strip()]

    client = OpenAQ(api_key=OPENAQ_API_KEY)
    checkpoints = load_checkpoints()

    for sensor in sensors_list:
        # Domyślnie startujemy od 2024 roku jeśli nie ma wpisu w checkpoint
        last_sync = checkpoints.get(str(sensor), "2016-10-10T00:00:00Z")
        process_sensor(client, sensor, last_sync)

    print("\nZakończono pobieranie danych.")

except Exception as e:
    print(f"Krytyczny błąd: {e}")
finally:
    cluster.shutdown()