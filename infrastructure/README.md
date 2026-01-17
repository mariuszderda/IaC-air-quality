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
│   └── configure-cassandra-playbook.yml  # Nowy playbook do konfiguracji
├── inventory
├── README.md
├── roles/
│   ├── cassandra_node/
│   └── gcp_vm/
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

### Etap 3b: Skonfiguruj serwer FTP (opcjonalnie)

Jeśli utworzyłeś maszynę w grupie `ftp`, uruchom playbook konfiguracyjny, podając dane dla nowego użytkownika, który będzie używany do połączeń FTP.

```bash
ansible-playbook -i gcp_inventory.ini playbooks/configure-ftp-playbook.yml --extra-vars "ftp_user=nazwa_uzytkownika ftp_password=haslo_dla_ftp"
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
