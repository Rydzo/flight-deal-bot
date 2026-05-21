"""Skrypt do parsowania pliku tekstowego z lotniskami i generowania airports.json."""

import json
import re
from pathlib import Path


def parse_airports_file(filepath: str) -> list[dict]:
    """Parsuje plik tekstowy z lotniskami i zwraca listę słowników.

    Każdy wpis zawiera kod IATA, nazwę lotniska i kraj.

    Args:
        filepath: Ścieżka do pliku tekstowego z lotniskami.

    Returns:
        Lista słowników z kluczami: code, name, country.
    """
    airports: list[dict] = []
    pattern = re.compile(r'^\d+\.\s+\[([A-Z]{3,4})\]\s+(.+?)\s+-\s+(.+)$')

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            match = pattern.match(line)
            if match:
                code = match.group(1)
                name = match.group(2).strip()
                country = match.group(3).strip()
                airports.append({
                    'code': code,
                    'name': name,
                    'country': country
                })
            else:
                # Linie, które nie pasują do wzorca (np. '[Lhasa]', '[Chetumal]')
                print(f"Pominięto linię (nie pasuje do wzorca): {line}")

    return airports


def main() -> None:
    """Główna funkcja parsująca lotniska i zapisująca do JSON."""
    project_root = Path(__file__).resolve().parent.parent
    txt_path = project_root / 'najczestsze_lotniska_swiata.txt'
    json_path = project_root / 'data' / 'airports.json'

    # Upewnij się, że katalog data/ istnieje
    json_path.parent.mkdir(parents=True, exist_ok=True)

    airports = parse_airports_file(str(txt_path))

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(airports, f, ensure_ascii=False, indent=2)

    print(f"Zapisano {len(airports)} lotnisk do {json_path}")


if __name__ == '__main__':
    main()
