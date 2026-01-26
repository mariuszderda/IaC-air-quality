# Infrastruktura jako kod (IaC) z użyciem Ansible

## 1. Cel i zakres

Ten moduł zawiera kod Ansible odpowiedzialny za automatyczne tworzenie i konfigurację całej infrastruktury potrzebnej do działania platformy do analizy jakości powietrza w chmurze Google Cloud Platform (GCP).

Główne zadania realizowane przez Ansible:
-   **Tworzenie sieci**: Automatyczne tworzenie dedykowanej sieci VPC wraz z niezbędnymi regułami firewalla.
-   **Provisioning maszyn wirtualnych**: Dynamiczne tworzenie instancji VM dla klastra Cassandra oraz dla hosta ETL/FTP.
-   **Konfiguracja klastra Cassandra**: Instalacja, konfiguracja i uruchomienie wielowęzłowego, odpornego na awarie klastra Apache Cassandra.
-   **Konfiguracja hosta ETL**: Przygotowanie dedykowanej maszyny do uruchamiania procesów ETL, w tym instalacja Pythona, Sparka, i narzędzi pomocniczych.
-   **Automatyzacja zadań**: Planowanie i automatyzacja cyklicznych zadań ETL za pomocą crona (lub jako przygotowanie pod deployment Airflow).

## 2. Struktura i role Ansible

Projekt jest zorganizowany w sposób modularny, z wykorzystaniem ról Ansible, aby zapewnić reużywalność i czytelność kodu.

```
infrastructure/
├── ansible.cfg
├── configure-cluster.sh
├── gcp_inventory.ini       # tworzony automatycznie
├── inventory
├── klucz-serwisowy.json    # UWAGA! klucz należy wygenerować
├── playbooks
│   ├── add-node-playbook.yml
│   ├── check-cassandra-cluster-playbook.yml
│   ├── configure-cassandra-playbook.yml
│   ├── configure-cron-playbook.yml
│   ├── configure-etl-host-playbook.yml
│   ├── create-schema-playbook.yml
│   ├── network-playbook.yml
│   ├── optimization-cassandra-playbook.yml
│   ├── secure-cassandra-playbook.yml
│   └── vm-playbook.yml
├── README.md
├── roles
│   ├── cassandra_node
│   │   ├── defaults
│   │   ├── handlers
│   │   ├── tasks
│   │   └── templates
│   └── gcp_vm
│       ├── defaults
│       └── tasks
└── vars
    └── main.yml
```

-   `playbooks/`: Katalog zawierający główne playbooki, które orkiestrują całym procesem.
-   `roles/`:
    -   `gcp_vm`: Rola odpowiedzialna za tworzenie i zarządzanie maszynami wirtualnymi w GCP.
    -   `cassandra_node`: Rola dedykowana do instalacji i konfiguracji pojedynczego węzła Cassandra.
-   `vars/main.yml`: Plik z głównymi zmiennymi, takimi jak region GCP, typ maszyn czy nazwy zasobów.
-   `gcp_inventory.ini`: Dynamicznie generowany plik inwentarza, zawierający adresy IP nowo utworzonych maszyn.

## 3. Przepływ pracy i uruchamianie

Proces tworzenia infrastruktury został podzielony na logiczne etapy, realizowane przez dedykowane playbooki.

### Etap 1: Przygotowanie sieci (jednorazowo)

Ten playbook tworzy sieć VPC i reguły firewalla. Należy go uruchomić tylko raz dla danego środowiska.
```bash
ansible-playbook playbooks/network-playbook.yml
```

### Etap 2: Tworzenie maszyn wirtualnych (wielokrotnie)

Playbook `vm-playbook.yml` służy do tworzenia pojedynczej maszyny wirtualnej. Uruchamia się go wielokrotnie – raz dla każdego węzła klastra Cassandra i raz dla hosta ETL.

-   **Tworzenie węzłów Cassandra**: Domyślnie, maszyny są dodawane do grupy `database`.
    ```bash
    # Stwórz pierwszy węzeł
    ansible-playbook playbooks/vm-playbook.yml --extra-vars "gcp_instance_name=cassandra-node-1 gcp_external_ip_name=cassandra-ip-1"

    # Stwórz drugi węzeł
    ansible-playbook playbooks/vm-playbook.yml --extra-vars "gcp_instance_name=cassandra-node-2 gcp_external_ip_name=cassandra-ip-2"
    ```

-   **Tworzenie hosta ETL/Airflow**: Użyj zmiennej `ftp=true` (nazwa historyczna, można ją zmienić na `etl=true`), aby dodać maszynę do grupy `ftp`.
    ```bash
    ansible-playbook playbooks/vm-playbook.yml --extra-vars "gcp_instance_name=etl-host-1 gcp_external_ip_name=etl-ip-1 ftp=true"
    ```

### Etap 3: Konfiguracja usług

Po utworzeniu maszyn i wygenerowaniu inwentarza `gcp_inventory.ini`, można przystąpić do konfiguracji usług.

-   **Konfiguracja klastra Cassandra**:
    ```bash
    ansible-playbook -i gcp_inventory.ini playbooks/configure-cassandra-playbook.yml
    ```
    Playbook automatycznie wykrywa wewnętrzne adresy IP maszyn i używa pierwszego z nich jako "seed" dla reszty klastra.

-   **Konfiguracja hosta ETL**:
    ```bash
    ansible-playbook -i gcp_inventory.ini playbooks/configure-etl-host-playbook.yml
    ```

### Etap 4: Operacje na działającym klastrze

-   **Dodawanie nowego węzła do klastra**:
    1.  Stwórz nową maszynę (Etap 2).
    2.  Uruchom dedykowany playbook, ograniczając jego wykonanie tylko do nowego węzła za pomocą flagi `--limit`.
       ```bash
       ansible-playbook -i gcp_inventory.ini playbooks/add-node-playbook.yml --limit=<NAZWA_NOWEGO_WĘZŁA>
       ```

-   **Inicjalizacja schematu bazy danych**:
    Po pierwszym skonfigurowaniu klastra, utwórz `keyspace` i tabele.
    ```bash
    ansible-playbook -i gcp_inventory.ini playbooks/create-schema-playbook.yml
    ```

-   **Zabezpieczenie klastra**:
    Włącz uwierzytelnianie, stwórz nowego superużytkownika (dane z `.env`) i zablokuj domyślne konto `cassandra`.
    ```bash
    ansible-playbook -i gcp_inventory.ini playbooks/secure-cassandra-playbook.yml
    ```

-   **Wdrożenie i zaplanowanie zadań ETL**:
    Skopiuj skrypty ETL na hosta i skonfiguruj zadania cron.
    ```bash
    ansible-playbook -i gcp_inventory.ini playbooks/configure-cron-playbook.yml
    ```

## 4. Wymagania

-   Zainstalowany Ansible.
-   Konto w Google Cloud Platform z uprawnieniami do tworzenia zasobów.
-   Wygenerowany klucz konta serwisowego GCP (`klucz-serwisowy.json`).
-   Skonfigurowany dostęp SSH do maszyn (klucz prywatny).

Dzięki takiemu podejściu, cała platforma – od maszyn wirtualnych, przez bazę danych, aż po orkiestrator zadań – jest w pełni definiowalna i odtwarzalna za pomocą kodu.

