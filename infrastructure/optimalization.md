Oto kompletny plik konfiguracyjny zebranymi wszystkimi zmianami (trwałymi i tymczasowymi), które omówiliśmy. Jest gotowy do zapisania jako `cassandra_tuning.md` i dołączenia do sprawozdania.

```markdown
# Dokumentacja Optymalizacji Węzła Apache Cassandra

**Cel:** Tuning wydajnościowy systemu operacyjnego Linux (RHEL/Rocky) oraz konfiguracja JVM (Java 11) dla bazy danych Cassandra na środowisku wirtualnym.

---

## 1. Konfiguracja Systemu Operacyjnego (OS Tuning)

### 1.1. Parametry Jądra (Sysctl)
**Plik:** `/etc/sysctl.conf`
*Zmiany trwałe (wymagają `sudo sysctl -p` lub restartu).*

```ini
# --- Optymalizacja Pamięci Wirtualnej ---
# Ograniczenie swapowania (zalecane 0-1 dla baz danych)
vm.swappiness = 1

# Wymagane przez Cassandrę do obsługi Memory Mapped Files
vm.max_map_count = 1048575

# Wyłączenie agresywnego odzyskiwania pamięci w architekturze NUMA
vm.zone_reclaim_mode = 0

# --- Optymalizacja Sieci (TCP) ---
# Zwiększenie buforów dla połączeń między węzłami
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_window_scaling = 1

```

### 1.2. Limity Zasobów (Ulimits)

**Plik:** `/etc/security/limits.conf`
*Zwiększenie limitów dla użytkownika `cassandra`.*

```text
cassandra - memlock unlimited
cassandra - nofile 100000
cassandra - nproc 32768
cassandra - as unlimited

```

### 1.3. System Plików (Mount Options)

**Plik:** `/etc/fstab`
*Zmiana opcji montowania dla partycji z danymi (`/`).*

* **Zmiana:** Dodanie flagi `noatime` do istniejących opcji.
* **Przykład:**
```text
/dev/mapper/rl-root   /   xfs   defaults,noatime   0 0

```



---

## 2. Konfiguracja Serwera Cassandra

### 2.1. Główna konfiguracja

**Plik:** `/etc/cassandra/cassandra.yaml`

```yaml
# --- Optymalizacja Kompaktyzacji (Compaction) ---
# Ograniczenie współbieżności dla środowiska wirtualnego (oszczędność CPU)
concurrent_compactors: 2

# Wyłączenie lejka przepustowości (dla szybkich dysków SSD/NVMe)
compaction_throughput_mb_per_sec: 0

# --- Topologia ---
# Zmiana Snitcha na takiego, który czyta plik konfiguracyjny rackdc
endpoint_snitch: GossipingPropertyFileSnitch

```

### 2.2. Topologia (Rack Awareness)

**Plik:** `/etc/cassandra/cassandra-rackdc.properties`

```properties
# Definicja lokalizacji węzła
dc=DC1
rack=RACK1  # (Dla węzłów 3 i 4 ustawić: rack=RACK2)

```

---

## 3. Konfiguracja JVM (Java 11)

**Plik:** `/etc/cassandra/jvm11-server.options`
*(Uwaga: Edytujemy plik dla Java 11, bo ta wersja jest wykryta w systemie).*

### 3.1. Pamięć Sterty (Heap Memory)

Ustawienie sztywnej granicy pamięci, aby uniknąć narzutu na realokację.
*(Wartość 2G dobrana dla maszyny 4GB RAM).*

```text
-Xms4G
-Xmx4G

```

### 3.2. Garbage Collector (G1GC)

Przejście z przestarzałego CMS na nowszy G1GC.

1. **Włącz G1GC** (usuń znak `#`):
```text
-XX:+UseG1GC

```


2. **Wyłącz CMS** (dodaj znak `#` przed każdą linią w sekcji CMS):
```text
#-XX:+UseConcMarkSweepGC
#-XX:+UseParNewGC
#-XX:+CMSParallelRemarkEnabled
# ... (zakomentuj wszystkie parametry CMS)

```



---

## 4. Działania "Runtime" (Po restarcie systemu)

Te ustawienia nie zapisują się automatycznie lub są specyficzne dla środowiska testowego (Lab/VM). Należy je wykonać po każdym restarcie (`reboot`).

### 4.1. Uruchomienie SWAP (Tylko dla testów obciążeniowych)

Ponieważ klient (`cassandra-stress`) i serwer działają na tej samej maszynie, włączenie SWAP jest konieczne, aby uniknąć błędu OOM Killer.

```bash
# Jeśli plik /swapfile istnieje:
sudo swapon /swapfile

# Weryfikacja:
swapon --show

```

### 4.2. Optymalizacja Dysku (Read-Ahead)

Zmniejszenie wyprzedzającego odczytu do 32KB (optymalne dla losowych odczytów bazy).

```bash
# Dla partycji systemowej/danych:
sudo blockdev --setra 64 /dev/mapper/rl-root

# Weryfikacja:
sudo blockdev --getra /dev/mapper/rl-root
# Oczekiwany wynik: 64

```

---

## 5. Procedura Testowa (Benchmark)

Aby test był wiarygodny, należy wykonać poniższe kroki w podanej kolejności.

1. **Weryfikacja statusu klastra:**
```bash
nodetool status
# Oczekiwany stan: UN (Up/Normal) dla wszystkich węzłów

```


2. **Wyczyszczenie Cache Systemu Operacyjnego (Cold Cache):**
*Usuwa z RAMu pliki załadowane podczas poprzednich testów.*
```bash
sync; sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'

```


3. **Uruchomienie Testu (Cassandra Stress):**
*Używamy zmniejszonej liczby wątków (10-20), aby nie przeciążyć pamięci RAM.*
```bash
cassandra-stress write n=1000000 -rate threads=20 -node <ADRES_IP_NODA>

```


4. **Analiza Wyników:**
* Porównać **Latency 99th percentile** oraz **Latency Max** z wynikami przed tuningiem.
* Spodziewany efekt: Znacząca redukcja maksymalnych opóźnień (większa stabilność).



```

```