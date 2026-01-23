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
# Pozwól na listę adresów IP oddzielonych przecinkami dla większej odporności
NODE_IPS = [ip.strip() for ip in os.getenv("CASSANDRA_NODE_IP", "").split(',') if ip.strip()]

# Ustalenie ścieżki do pliku względem lokalizacji skryptu
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKPOINT_FILE = os.path.join(SCRIPT_DIR, 'checkpoint.json')
SENSORS_FILE = os.path.join(SCRIPT_DIR, '../data/location_list.csv')

# === POŁĄCZENIE Z CASSANDRĄ ===
auth_provider = PlainTextAuthProvider(username=DATABASE_USER, password=DATABASE_PASSWORD)
cluster = Cluster(NODE_IPS, auth_provider=auth_provider)
session = cluster.connect('air_quality')

# Przygotowanie zapytania (Prepared Statement) dla wydajności
insert_stmt = session.prepare("""
    INSERT INTO measurements (station_id, name, value, unit, parameter, measure_date)
    VALUES (?, ?, ?, ?, ?, ?)
""")

def load_checkpoints():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("Warning: Checkpoint file is corrupted. Starting from scratch.")
                return {}
    return {}

def save_checkpoint(data):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_iso_date_str(date_obj):
    # Konwersja datetime na string ISO dla API OpenAQ
    return date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")

def process_sensor(client, sensor_id, sensor_name, last_date):
    print(f"\n--- Przetwarzanie sensora: {sensor_name} ({sensor_id}) ---")
    print(f"Szukam danych nowszych niż: {last_date}")

    current_page = 1
    max_date_in_batch = last_date
    new_records_found = False

    while True:
        try:
            response = client.measurements.list(
                sensors_id=int(sensor_id),
                date_from=last_date,
                page=current_page,
                limit=1000,
                sort="asc"
            )
        except Exception as e:
            print(f"Błąd podczas zapytania do API OpenAQ: {e}")
            break

        results = response.results
        if not results:
            if not new_records_found:
                print("Brak nowych danych dla tego sensora.")
            break

        new_records_found = True
        print(f"Strona {current_page}: pobrano {len(results)} rekordów. Zapisuję do DB...")
        
        batch = BatchStatement()
        count = 0

        for item in results:
            try:
                measure_dt = item.date.utc
                
                batch.add(insert_stmt, (
                    str(sensor_id),
                    sensor_name,  # Używamy nazwy sensora z pliku CSV
                    float(item.value),
                    item.parameter.unit,
                    item.parameter.name,
                    measure_dt
                ))
                count += 1

                current_iso = get_iso_date_str(measure_dt)
                if current_iso > max_date_in_batch:
                    max_date_in_batch = current_iso

                if count >= 100:
                    session.execute(batch)
                    batch = BatchStatement()
                    count = 0
            
            except (ValueError, TypeError) as e:
                print(f"Błąd parsowania rekordu: {item}. Błąd: {e}")
                continue

        if count > 0:
            session.execute(batch)

        checkpoints[str(sensor_id)] = max_date_in_batch
        save_checkpoint(checkpoints)
        
        current_page += 1
        time.sleep(1.2)

        if current_page > 50:
            print("Osiągnięto limit 50 stron na jedno uruchomienie dla tego sensora.")
            break

# === MAIN ===
try:
    if not NODE_IPS:
        raise ValueError("CASSANDRA_NODE_IP nie jest ustawione w pliku .env")

    with open(SENSORS_FILE, 'r') as f:
        sensors_list = [tuple(line.strip().split(";")) for line in f if line.strip() and not line.startswith('#')]

    client = OpenAQ(api_key=OPENAQ_API_KEY)
    checkpoints = load_checkpoints()

    for sensor, name in sensors_list:
        last_sync = checkpoints.get(str(sensor), "2024-01-01T00:00:00Z")
        process_sensor(client, sensor, name, last_sync)

    print("\nZakończono pobieranie danych.")

except Exception as e:
    print(f"Krytyczny błąd: {e}")
finally:
    cluster.shutdown()