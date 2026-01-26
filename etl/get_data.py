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

# === KONFIGURACJA I STAŁE ===
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
NODE_IPS = [ip.strip() for ip in os.getenv("CASSANDRA_NODE_IP", "").split(',') if ip.strip()]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKPOINT_FILE = os.path.join(SCRIPT_DIR, 'checkpoint.json')
SENSORS_FILE = os.path.join(SCRIPT_DIR, '../data/location_list.csv')


# === FUNKCJE POMOCNICZE (LOGIKA BAZODANOWA I PLIKOWA) ===

def get_cassandra_session():
    if not NODE_IPS:
        raise ValueError("CASSANDRA_NODE_IP nie jest ustawione w pliku .env")
    auth = PlainTextAuthProvider(username=DATABASE_USER, password=DATABASE_PASSWORD)
    cluster = Cluster(NODE_IPS, auth_provider=auth)
    return cluster.connect('air_quality'), cluster


def load_checkpoints():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print("Warning: Checkpoint file error. Starting from scratch.")
    return {}


def save_checkpoint(data):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(data, f, indent=4)


def parse_measure_date(item):
    """Wyciąga i parsuje datę z rekordu OpenAQ."""
    # Używamy period.datetime_from.utc zgodnie z Twoim kodem
    dt = item.period.datetime_from.utc
    if isinstance(dt, str):
        return datetime.datetime.fromisoformat(dt.replace("Z", "+00:00"))
    return dt


# === GŁÓWNA LOGIKA PRZETWARZANIA ===

def save_to_cassandra(session, insert_stmt, results, sensor_id, sensor_name):
    """Zapisuje paczkę wyników do Cassandry przy użyciu BatchStatement."""
    batch = BatchStatement()
    max_dt_str = "1900-01-01T00:00:00Z"
    count = 0

    for item in results:
        try:
            measure_dt = parse_measure_date(item)
            batch.add(insert_stmt, (
                str(sensor_id), sensor_name, float(item.value),
                item.parameter.units, item.parameter.name, measure_dt
                ))

            iso_str = measure_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            if iso_str > max_dt_str:
                max_dt_str = iso_str

            count += 1
            if count >= 100:
                session.execute(batch)
                batch = BatchStatement()
                count = 0
        except Exception as e:
            print(f"Błąd rekordu: {e}")
            continue

    if count > 0:
        session.execute(batch)
    return max_dt_str


def process_sensor(client, session, insert_stmt, sensor_info, checkpoints):
    """Przetwarza pojedynczy sensor (paginacja)."""
    sensor_id, sensor_name = sensor_info
    last_date = checkpoints.get(str(sensor_id), "2016-01-01T00:00:00Z")

    print(f"\n--- Sensor: {sensor_name} ({sensor_id}) od {last_date} ---")

    for page in range(1, 51):  # Limit 50 stron
        try:
            response = client.measurements.list(
                sensors_id=int(sensor_id),
                datetime_from=last_date,
                page=page,
                limit=1000
                )
            if not response.results:
                break

            print(f"Strona {page}: pobrano {len(response.results)} rekordów. Zapisuję do DB...", sep="", end="")
            new_last_date = save_to_cassandra(session, insert_stmt, response.results, sensor_id, sensor_name)

            # Aktualizacja checkpointu po każdej stronie
            if new_last_date > last_date:
                last_date = new_last_date
                checkpoints[str(sensor_id)] = last_date
                save_checkpoint(checkpoints)
                print("Done.")
            time.sleep(1.2)  # Rate limiting
        except Exception as e:
            print(f"Błąd API/DB na stronie {page}: {e}")
            break


# === URUCHOMIENIE ===

def main():
    if not OPENAQ_API_KEY:
        print("Brak klucza OpenAQ!")
        return

    session, cluster = get_cassandra_session()
    insert_stmt = session.prepare("""
                                  INSERT INTO measurements (station_id, name, value, unit, parameter, measure_date)
                                  VALUES (?, ?, ?, ?, ?, ?)
                                  """)

    try:
        checkpoints = load_checkpoints()
        with open(SENSORS_FILE, 'r') as f:
            sensors = [tuple(l.strip().split(";")) for l in f if l.strip() and not l.startswith('#')]

        client = OpenAQ(api_key=OPENAQ_API_KEY)
        for sensor_data in sensors:
            process_sensor(client, session, insert_stmt, sensor_data, checkpoints)

    finally:
        cluster.shutdown()
        print("\nZakończono.")

main()