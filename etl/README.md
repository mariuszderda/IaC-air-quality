# Potok ETL do przetwarzania danych o jakości powietrza

## 1. Cel i zadania

Ten moduł odpowiada za kompletny proces ETL (Extract, Transform, Load) danych o jakości powietrza. Jego głównym celem jest cykliczne i niezawodne zasilanie bazy danych Cassandra świeżymi, przetworzonymi i oczyszczonymi danymi, gotowymi do dalszej analizy i wizualizacji.

## 2. Architektura potoku

Potok składa się z trzech głównych skryptów, **obecnie orkiestrowanych przez zadania cron** (konfigurowane za pomocą Ansible), z planami na przyszłą integrację z Apache Airflow:

1.  **`get_locations.py`**: Skrypt pomocniczy, uruchamiany jednorazowo, w celu pobrania identyfikatorów stacji pomiarowych z API OpenAQ dla interesujących nas lokalizacji. Zapisuje on listę stacji do pliku `data/location_list.csv`, który jest następnie wykorzystywany przez główny proces ETL.
2.  **`get_data.py`**: **(Krok 1 - Extract & Load)** Ten skrypt jest sercem procesu pobierania danych. Łączy się z API OpenAQ i pobiera surowe dane pomiarowe dla stacji zdefiniowanych w `location_list.csv`. Wykorzystuje plik `checkpoint.json`, aby pobierać tylko nowe dane, które pojawiły się od ostatniego uruchomienia. Surowe dane są natychmiast ładowane do tabeli `measurements` w bazie Cassandra.
3.  **`agregation.py`**: **(Krok 2 - Transform)** Skrypt ten wykorzystuje moc obliczeniową Apache Spark (za pośrednictwem `pyspark`) do przetwarzania danych. Odczytuje surowe dane z tabeli `measurements`, wykonuje na nich operacje czyszczenia (np. usuwanie wartości odstających i ujemnych), a następnie grupuje je i oblicza średnie dzienne. Wynik jest zapisywany w docelowej tabeli `daily_averages`.
4.  **`data_visualization.ipynb`**: **(Krok 3 - Reporting)** Jupyter Notebook, który może być uruchamiany (np. przez `nbconvert`) w celu wygenerowania raportów i wizualizacji na podstawie danych z tabeli `daily_averages`.

## 3. Struktura danych w Cassandrze

-   **Keyspace**: `air_quality`
-   **Tabela surowych danych**: `measurements`
    -   Przechowuje surowe, godzinowe odczyty z sensorów.
    -   Klucz partycjonowania: `station_id`.
    -   Klucz klastrujący: `measure_date` (sortowanie malejąco).
-   **Tabela zagregowanych danych**: `daily_averages`
    -   Przechowuje przetworzone, średnie dzienne wartości dla każdej stacji i każdego parametru.
    -   Klucz partycjonowania: `station_id`.
    -   Klucz klastrujący: `day` (sortowanie malejąco).

## 4. Technologie

-   **Język programowania**: Python
-   **Biblioteki**:
    -   `openaq`: Klient API OpenAQ.
    -   `cassandra-driver`: Sterownik do bazy danych Cassandra.
    -   `pyspark`: Interfejs Python dla Apache Spark.
    -   `pandas`: Analiza i manipulacja danymi.
    -   `python-dotenv`: Zarządzanie zmiennymi środowiskowymi.
    -   `jupyter`, `matplotlib`: Wizualizacja i raportowanie.

## 5. Uruchamianie

### Wymagania wstępne

-   Działający i dostępny klaster Cassandra.
-   Skonfigurowany plik `.env` z danymi dostępowymi do API i bazy danych.
-   Zainstalowane wszystkie wymagane biblioteki (`pip install -r requirements.txt`).

### Kroki uruchomienia

1.  **Pobranie lokalizacji (jednorazowo)**:
    ```bash
    python etl/get_locations.py
    ```
2.  **Uruchomienie potoku ETL**:
    Proces ETL jest obecnie orkiestrowany za pomocą zadań cron, konfigurowanych przez playbook Ansible `infrastructure/playbooks/configure-cron-playbook.yml`. Ten playbook automatycznie ustawia:

-   Godzinowe pobieranie danych (`get_data.py`).
-   Dzienne agregowanie danych (`agregation.py`).
-   Dzienne generowanie raportów (`data_visualization.ipynb`).

Skrypty można również uruchamiać ręcznie w odpowiedniej kolejności, aby przetestować poszczególne etapy:
    
```bash
    # Krok 1: Pobranie surowych danych
    python etl/get_data.py

    # Krok 2: Agregacja danych przy użyciu Sparka
    python etl/agregation.py
```
**Uwaga**: Uruchomienie `agregation.py oraz get_data.py` wymaga skonfigurowanego środowiska Spark i odpowiednich zmiennych środowiskowych wskazujących na klaster Cassandry (patrz kod skryptu).
