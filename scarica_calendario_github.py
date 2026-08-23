"""
Scarica calendario — versione per GitHub Actions.

Stessa logica di scarica_calendario_locale.py, adattata per girare sui
server di GitHub invece che sul Mac (cosi' funziona anche se il Mac e'
spento). Scrive il risultato in data/ dentro questo stesso repository;
il workflow GitHub Actions si occupa poi di fare commit + push.

Come funziona la scelta delle partite (finestra di date, non "giornata"):
Scarica tutte le partite di ogni campionato comprese in una finestra di
date centrata su oggi (di default: ultimi FINESTRA_GIORNI_INDIETRO giorni
+ prossimi FINESTRA_GIORNI_AVANTI), qualunque sia il loro stato (quindi
anche quelle gia' giocate/in corso, con punteggio) e qualunque sia il
numero di giornata a cui appartengono.

Perche' non piu' per "giornata singola": alcuni campionati rinviano
partite a causa di impegni europei (Champions/Europa League), e quando
succede la giornata successiva puo' iniziare mentre quella precedente non
e' ancora del tutto conclusa (es. La Liga: Real Madrid/Barcellona
recuperano una partita di giornata 1 mentre le altre squadre giocano gia'
la giornata 2). Con la sola logica "giornata piu' bassa tra le partite
non finite" si rischiava di restare bloccati sulla giornata vecchia senza
accorgersi che una nuova era gia' iniziata altrove. La finestra di date
non ha questo problema: mostra semplicemente tutto cio' che succede
vicino a oggi, a prescindere dal numero di giornata.

Variabili richieste (impostate come GitHub Actions secret):
    FOOTBALL_DATA_API_KEY
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import requests

from leghe import LEGHE

API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
URL_FINESTRA = (
    "https://api.football-data.org/v4/competitions/{fd_code}/matches"
    "?dateFrom={data_da}&dateTo={data_a}"
)

FINESTRA_GIORNI_INDIETRO = 3
FINESTRA_GIORNI_AVANTI = 10

OUTPUT_DIR = "data"


def scarica_calendario(fd_code: str, data_da: str, data_a: str) -> tuple[list, str | None]:
    if not API_KEY:
        return [], "FOOTBALL_DATA_API_KEY non trovata (secret non impostato su GitHub)."
    headers = {"X-Auth-Token": API_KEY}
    url = URL_FINESTRA.format(fd_code=fd_code, data_da=data_da, data_a=data_a)
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
    return r.json().get("matches", []), None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ora = datetime.now(timezone.utc)
    data_da = (ora - timedelta(days=FINESTRA_GIORNI_INDIETRO)).strftime("%Y-%m-%d")
    data_a = (ora + timedelta(days=FINESTRA_GIORNI_AVANTI)).strftime("%Y-%m-%d")

    campionati = []
    for nome_lega, info in LEGHE.items():
        print(f"Scarico calendario: {nome_lega}...")
        partite_fd, errore = scarica_calendario(info["fd_code"], data_da, data_a)
        giornate_presenti = sorted({m["matchday"] for m in partite_fd if m.get("matchday")})
        voce = {
            "lega": nome_lega,
            "fd_code": info["fd_code"],
            "errore": errore,
            "giornate_presenti": giornate_presenti,  # puo' contenere piu' di un numero (vedi nota sopra)
            "giornata": giornate_presenti[0] if giornate_presenti else None,  # per retrocompatibilita'
            "partite": [
                {
                    "casa_fd": m["homeTeam"]["name"],
                    "trasferta_fd": m["awayTeam"]["name"],
                    "data": m.get("utcDate", "")[:10],
                    "ora_utc": m.get("utcDate", "")[11:16],
                    "giornata": m.get("matchday"),
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
            print(f"  -> {len(partite_fd)} partite trovate (giornate: {giornate_presenti})")

    output = {
        "generato_il_utc": ora.isoformat(),
        "finestra_data_da": data_da,
        "finestra_data_a": data_a,
        "campionati": campionati,
    }

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
