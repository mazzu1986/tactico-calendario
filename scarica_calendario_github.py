"""
Scarica calendario — versione per GitHub Actions.

Stessa logica di scarica_calendario_locale.py, adattata per girare sui
server di GitHub invece che sul Mac (cosi' funziona anche se il Mac e'
spento). Scrive il risultato in data/ dentro questo stesso repository;
il workflow GitHub Actions si occupa poi di fare commit + push.

Come funziona la scelta della giornata:
1. Cerca tra le partite ancora "SCHEDULED" o "TIMED" (non ancora finite)
   quella con il matchday piu' basso: quella e' la "giornata corrente".
2. Scarica TUTTE le partite di quel matchday, indipendentemente dallo
   stato (quindi anche quelle gia' giocate, con il punteggio finale).
   Cosi' la giornata resta visibile per intero finche' non e' davvero
   conclusa (tutte le partite finite): solo a quel punto il passo 1
   trovera' come "giornata corrente" quella successiva.

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
URL_PROSSIME = "https://api.football-data.org/v4/competitions/{fd_code}/matches?status=SCHEDULED,TIMED"
URL_GIORNATA = "https://api.football-data.org/v4/competitions/{fd_code}/matches?matchday={giornata}"

OUTPUT_DIR = "data"


def _get(url: str, headers: dict) -> tuple[dict | None, str | None]:
    try:
        r = requests.get(url, headers=headers, timeout=15)
    except Exception as e:
        return None, f"Errore di connessione: {e}"
    if r.status_code == 403:
        return None, "Chiave API non valida."
    if r.status_code == 429:
        return None, "Limite di richieste football-data.org raggiunto, riprova tra poco."
    if r.status_code != 200:
        return None, f"Errore API: {r.status_code}"
    return r.json(), None


def scarica_calendario(fd_code: str) -> tuple[list, str | None]:
    if not API_KEY:
        return [], "FOOTBALL_DATA_API_KEY non trovata (secret non impostato su GitHub)."
    headers = {"X-Auth-Token": API_KEY}

    # 1) individua la giornata corrente guardando solo le partite non ancora finite
    dati, errore = _get(URL_PROSSIME.format(fd_code=fd_code), headers)
    if errore:
        return [], errore
    prossime = dati.get("matches", [])
    if not prossime:
        return [], None  # nessuna partita in programma al momento (stagione ferma/finita)
    giornata = min(m["matchday"] for m in prossime if m.get("matchday"))

    # 2) scarica TUTTE le partite di quella giornata, comprese quelle gia' giocate
    dati_giornata, errore = _get(URL_GIORNATA.format(fd_code=fd_code, giornata=giornata), headers)
    if errore:
        return [], errore
    return dati_giornata.get("matches", []), None


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
                    "stato": m.get("status"),
                    "gol_casa": ((m.get("score") or {}).get("fullTime") or {}).get("home"),
                    "gol_trasferta": ((m.get("score") or {}).get("fullTime") or {}).get("away"),
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
