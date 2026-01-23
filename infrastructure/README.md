# Projekt Ansible do dynamicznego tworzenia klastra Apache Cassandra w Google Cloud

## 1. Cel projektu

Ten projekt wykorzystuje Ansible do w pełni zautomatyzowanego procesu tworzenia infrastruktury dla klastra Apache Cassandra w GCP. Został zaprojektowany w sposób modularny, aby umożliwić niezależne zarządzanie siecią, maszynami wirtualnymi oraz procesem konfiguracji klastra.

## 2. Architektura i przepływ pracy

Projekt składa się z dedykowanych playbooków:

*   **Katalog `playbooks/`**: Zawiera wszystkie playbooki Ansible.
    *   `network-playbook.yml`: **(Krok 1)** Tworzy sieć VPC i reguły zapory. Uruchamiany tylko raz.
    *   `vm-playbook.yml`: **(Krok 2)** Tworzy pojedynczą maszynę wirtualną z jej własnym statycznym IP. Uruchamiany wielokrotnie dla każdego węzła.
    *   `configure-cassandra-playbook.yml`: **(Krok 3)** Konfiguruje oprogramowanie Cassandra na **wszystkich** maszynach zdefiniowanych w inwentarzu, automatycznie tworząc z nich klaster.

---
## 3. Struktura projektu

```
.
├── playbooks/
│   ├── network-playbook.yml
│   ├── vm-playbook.yml
│   ├── configure-cassandra-playbook.yml
│   ├── configure-ftp-playbook.yml
│   ├── create-schema-playbook.yml      # Nowy playbook do tworzenia schematu bazy danych
│   ├── secure-cassandra-playbook.yml   # Nowy playbook do zabezpieczania klastra Cassandry
├── inventory
├── README.md
├── roles/
│   ├── cassandra_node/
│   └── gcp_vm/                         # Zbędna rola gcp_vms została usunięta
├── vars/
│   └── main.yml
│
├── klucz-serwisowy.json     # (Musisz dodać)
└── gcp_inventory.ini        # (Generowany)
```
---
## 4. Uruchamianie

### Etap 1: Przygotuj sieć (jednorazowo)

```bash
ansible-playbook playbooks/network-playbook.yml
```

### Etap 2: Stwórz maszyny (wielokrotnie)

Uruchom ten playbook dla każdego węzła, który chcesz stworzyć. Domyślnie maszyny są dodawane do grupy `database`. Możesz użyć zmiennych `ftp` lub `http`, aby dodać je do odpowiednich grup.

```bash
# Stwórz pierwszy węzeł (domyślnie w grupie database)
ansible-playbook playbooks/vm-playbook.yml --extra-vars "gcp_instance_name=cassandra-node-1 gcp_external_ip_name=cassandra-ip-1"

# Stwórz drugi węzeł (domyślnie w grupie database)
ansible-playbook playbooks/vm-playbook.yml --extra-vars "gcp_instance_name=cassandra-node-2 gcp_external_ip_name=cassandra-ip-2"

# Stwórz maszynę w grupie ftp
ansible-playbook playbooks/vm-playbook.yml --extra-vars "gcp_instance_name=ftp-node-1 gcp_external_ip_name=ftp-ip-1 ftp=true"

# Stwórz maszynę w grupie http
ansible-playbook playbooks/vm-playbook.yml --extra-vars "gcp_instance_name=http-node-1 gcp_external_ip_name=http-ip-1 http=true"
```
Po wykonaniu tych komend, plik `gcp_inventory.ini` będzie zawierał publiczne IP wszystkich maszyn w odpowiednich grupach.

### Etap 3: Skonfiguruj klaster Cassandra

Teraz, gdy maszyny istnieją, a inwentarz jest gotowy, uruchom nowy playbook konfiguracyjny. On sam zajmie się resztą.

```bash
ansible-playbook -i gcp_inventory.ini playbooks/configure-cassandra-playbook.yml
```

### Etap 3b: Skonfiguruj host ETL (wcześniej serwer FTP)

Jeśli utworzyłeś maszynę w grupie `ftp` (teraz `etl-host`), uruchom playbook konfiguracyjny, podając dane dla użytkownika FTP. Ten użytkownik będzie miał teraz **uprawnienia tylko do odczytu**.

```bash
# Zastąp etl-host-ip-1 adresem IP utworzonej maszyny z grupą ftp
ansible-playbook -i gcp_inventory.ini playbooks/configure-etl-host-playbook.yml --limit etl-host-ip-1
```

**Jak to działa?**
Playbook najpierw połączy się z każdą maszyną, aby pobrać jej **wewnętrzny adres IP**. Następnie, użyje wewnętrznego adresu IP **pierwszej maszyny z listy** jako "seed" i przekaże go do konfiguracji wszystkich pozostałych maszyn, zapewniając, że poprawnie dołączą do klastra.

### Etap 4: Dodawanie nowego węzła do klastra

Gdy Twój klaster już działa i chcesz dodać do niego kolejną maszynę, wykonaj poniższe kroki.

**Krok 1: Stwórz nową maszynę wirtualną**

Użyj znanego już playbooka `vm-playbook.yml`, podając unikalne nazwy dla nowej maszyny i jej IP. To automatycznie doda adres IP nowego węzła do pliku `gcp_inventory.ini`.

```bash
# Stwórz czwarty węzeł
ansible-playbook playbooks/vm-playbook.yml --extra-vars "gcp_instance_name=cassandra-node-4 gcp_external_ip_name=cassandra-ip-4"
```

**Krok 2: Skonfiguruj tylko nowy węzeł**

Teraz użyj nowego playbooka `add-node-playbook.yml`. Jest on specjalnie przygotowany, aby nie naruszać już działających węzłów. Kluczowe jest użycie flagi `--limit`, aby wskazać, że operacje mają dotyczyć **tylko nowej maszyny**.

Musisz podać publiczny adres IP nowej maszyny, który został dodany do `gcp_inventory.ini`.

```bash
# Zastąp <PUBLIC_IP_NOWEGO_WEZLA> adresem IP maszyny cassandra-node-4
ansible-playbook -i gcp_inventory.ini playbooks/add-node-playbook.yml --limit <PUBLIC_IP_NOWEGO_WEZLA>
```

**Jak to działa?**
Playbook `add-node-playbook.yml` wciąż pobiera adres IP "seeda" od pierwszej maszyny w inwentarzu, ale dzięki fladze `--limit` wszystkie zadania konfiguracyjne z roli `cassandra_node` zostaną wykonane **tylko na nowym węźle**. Co najważniejsze, zadania czyszczące dane są pomijane, więc jest to operacja bezpieczna dla istniejącego klastra.

---
### Etap 5: Inicjalizacja schematu bazy danych i zabezpieczenie

Po skonfigurowaniu klastra Cassandra, należy utworzyć schemat bazy danych (keyspace i tabele) oraz zabezpieczyć klaster, zmieniając domyślne dane logowania.

**Krok 1: Inicjalizacja schematu bazy danych**

Uruchom ten playbook, aby stworzyć `keyspace` i tabele wymagane przez aplikację. Playbook ten połączy się z jednym z węzłów Cassandry i wykona skrypt `create_tables.cql`.

```bash
ansible-playbook -i gcp_inventory.ini playbooks/create-schema-playbook.yml
```

**Krok 2: Zabezpieczenie klastra Cassandra (dodanie użytkownika i wyłączenie domyślnego)**

Ten playbook włączy uwierzytelnianie w Cassandrze, utworzy nowego superużytkownika na podstawie podanych danych oraz zablokuje domyślne konto `cassandra`.

**Ważne:** Przed uruchomieniem tego playbooka upewnij się, że w pliku `.env` w głównym katalogu projektu zdefiniowałeś zmienne `DATABASE_USER` i `DATABASE_PASSWORD` z pożądanymi danymi logowania dla nowego użytkownika bazy danych. Playbook automatycznie je wczyta.

```bash
# W przykładzie użyto zmiennych z pliku .env. Możesz je też podać jako extra-vars:
# ansible-playbook -i gcp_inventory.ini playbooks/secure-cassandra-playbook.yml --extra-vars "db_user=moj_user db_pass=moje_haslo"
ansible-playbook -i gcp_inventory.ini playbooks/secure-cassandra-playbook.yml
```
**Jak to działa?**
Playbook najpierw restartuje wszystkie węzły Cassandry z włączonym uwierzytelnianiem. Następnie, korzystając z domyślnego konta `cassandra` (dostępnego tylko raz, tuż po włączeniu uwierzytelniania), tworzy nowego superużytkownika. Na koniec, logując się jako nowo utworzony użytkownik, blokuje domyślne konto `cassandra` dla zwiększenia bezpieczeństwa.

### Uwaga dotycząca logowania SSH dla użytkownika 'databasecassandra'

Maszyny wirtualne GCP domyślnie używają kluczy SSH do uwierzytelniania. Logowanie hasłem jest wyłączone ze względów bezpieczeństwa. Upewnij się, że Twój klucz publiczny SSH jest dodany do metadanych projektu GCP lub do konkretnej instancji, aby umożliwić logowanie jako użytkownik 'databasecassandra'. Jest to użytkownik, który będzie zarządzał środowiskiem ETL i uruchamiał skrypty.
