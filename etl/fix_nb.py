import json

path = 'data_visualization.ipynb'

try:
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Brutalna naprawa: usuwamy linie, które sed zostawił niedokończone
    fixed_lines = []
    for line in lines:
        if '"image/png":' in line and line.strip().endswith(':'):
            # Naprawiamy ucięty klucz obrazka
            fixed_lines.append(line.replace(':', ': "",'))
        else:
            fixed_lines.append(line)

    content = "".join(fixed_lines)
    # Dodatkowa naprawa brakujących przecinków/klamerek
    import re

    content = re.sub(r',\s*([\]}])', r'\1', content)

    data = json.loads(content)

    # Czyścimy outputs i problematyczne metadane
    for cell in data.get('cells', []):
        if 'outputs' in cell:
            cell['outputs'] = []
        if 'metadata' in cell:
            # Usuwamy śmieci od JetBrains (DataSpell/PyCharm)
            cell['metadata'] = {k: v for k, v in cell['metadata'].items() if 'jet' not in k}

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print("✅ Notebook naprawiony i wyczyszczony!")
except Exception as e:
    print(f"❌ Błąd krytyczny: {e}")