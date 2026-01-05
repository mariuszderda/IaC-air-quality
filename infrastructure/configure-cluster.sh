#!/bin/bash
set -e # Przerwij skrypt w przypadku błędu

INVENTORY_FILE="gcp_inventory.ini"
CONFIG_PLAYBOOK="playbooks/configure-cassandra-playbook.yml"

# --- Walidacja ---
if [ ! -f "$INVENTORY_FILE" ]; then
    echo "Błąd: Plik inwentarza '$INVENTORY_FILE' nie został znaleziony."
    exit 1
fi

# Wybierz PIERWSZY host z inwentarza (publiczny IP lub nazwa)
SEED_HOST=$(grep -v '^\[' "$INVENTORY_FILE" | head -n 1 | awk '{print $1}')

if [ -z "$SEED_HOST" ]; then
    echo "Błąd: Nie można znaleźć żadnych hostów w pliku inwentarza."
    exit 1
fi

echo "Wybrano pierwszy host ($SEED_HOST) jako potencjalny seed."
echo "Pobieranie jego WEWNĘTRZNEGO adresu IP..."

# Użyj Ansible, aby połączyć się z tym jednym hostem i pobrać jego wewnętrzny IP
# Używamy polecenia 'hostname -I', które jest niezawodne
INTERNAL_SEED_IP=$(ansible -i "$INVENTORY_FILE" "$SEED_HOST" -m shell -a "hostname -I | awk '{print \$1}'" | grep -oE "\b([0-9]{1,3}\.){3}[0-9]{1,3}\b")

if [ -z "$INTERNAL_SEED_IP" ]; then
    echo "Błąd: Nie udało się pobrać wewnętrznego IP dla hosta $SEED_HOST."
    exit 1
fi

echo "Uzyskano wewnętrzny IP seeda: $INTERNAL_SEED_IP"
echo "Rozpoczynanie konfiguracji klastra na WSZYSTKICH węzłach..."
echo ""

# Uruchom główny playbook konfiguracyjny, przekazując WEWNĘTRZNY IP jako seed
ansible-playbook -i "$INVENTORY_FILE" "$CONFIG_PLAYBOOK" --extra-vars "cassandra_seeds=$INTERNAL_SEED_IP"

if [ $? -ne 0 ]; then
    echo "Błąd: Konfiguracja klastra Cassandra nie powiodła się."
    exit 1
fi

echo "====================================================================="
echo "== SUKCES!"
echo "== Klaster Cassandra został skonfigurowany."
echo "====================================================================="
