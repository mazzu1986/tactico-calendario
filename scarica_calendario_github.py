"""
Scarica calendario — versione per GitHub Actions.

Stessa logica di scarica_calendario_locale.py, adattata per girare sui
server di GitHub invece che sul Mac (cosi' funziona anche se il Mac e'
spento). Scrive il risultato in data/ dentro questo stesso repository;
il workflow GitHub Actions si occupa poi di fare commit + push.

Variabili richieste (impostate come GitHub Actions secret):
    FOOTBALL_DATA_API_KEY
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import requests

from leghe import LEGHE

API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
BASE_URL = "https://api.football-data.org/v4/competitions/{fd_code}/matches?status=SCHEDULED,TIMED"

OUTPUT_DIR = "data"


def scarica_calendario(fd_code: str) -> tuple[list, str | None]:
    if not API_KEY:
        return [], "FOOTBALL_DATA_API_KEY non trovata (secret non impostato su GitHub)."
    headers = {"X-Auth-Token": API_KEY}
    url = BASE_URL.format(fd_code=fd_code)
    try:
        r = requests.get(url, headers=headers, timeout=15)
    except Exception as e:
        return [], f"Errore di connessione: {e}"
    if r.status_code == 403:
        return [], "Chiave API non valida."
    if r.status_code == 429:
        return [], "Limite di richieste football-data.org raggiunto, riprova tra poco."
    if r.status_code != 200:
        return [], f"Errore API: {r.status_code}"
    matches = r.json().get("matches", [])
    if not matches:
        return [], None
    prossima_giornata = min(m["matchday"] for m in matches if m.get("matchday"))
    return [m for m in matches if m.get("matchday") == prossima_giornata], None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ora = datetime.now(timezone.utc)

    campionati = []
    for nome_lega, info in LEGHE.items():
        print(f"Scarico calendario: {nome_lega}...")
        partite_fd, errore = scarica_calendario(info["fd_code"])
        voce = {
            "lega": nome_lega,
            "fd_code": info["fd_code"],
            "errore": errore,
            "giornata": partite_fd[0].get("matchday") if partite_fd else None,
            "partite": [
                {
                    "casa_fd": m["homeTeam"]["name"],
                    "trasferta_fd": m["awayTeam"]["name"],
                    "data": m.get("utcDate", "")[:10],
                    "ora_utc": m.get("utcDate", "")[11:16],
                }
                for m in partite_fd
            ],
        }
        campionati.append(voce)
        if errore:
            print(f"  -> errore: {errore}")
        else:
            print(f"  -> {len(partite_fd)} partite trovate")

    output = {"generato_il_utc": ora.isoformat(), "campionati": campionati}

    timestamp = ora.strftime("%Y-%m-%d")
    path_dated = os.path.join(OUTPUT_DIR, f"calendario_raw_{timestamp}.json")
    path_latest = os.path.join(OUTPUT_DIR, "calendario_raw_latest.json")

    with open(path_dated, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    with open(path_latest, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSalvato: {path_dated}")
    print(f"Salvato: {path_latest}")


if __name__ == "__main__":
    main()
