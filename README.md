# ⚽ TeamBot

Matrix-Bot für die wöchentliche Fußball-Teamaufstellung. Erstellt automatisch ausgeglichene Teams auf Basis von Spieler-Scores, verwaltet die Torwart-Zuweisung und berechnet Scores nach jedem Spiel neu.

---

## Features

| Feature | Details |
|---|---|
| 🗳️ **Wöchentlicher Vote** | Samstag 12:00 – Bot postet automatisch einen Poll |
| ✅ **Abstimmung** | Spieler stimmen per nativen Matrix-Poll ab (✅ Dabei / ❌ Nicht dabei) |
| 🧤 **GK-Meldung** | Spieler melden sich mit `!gk` freiwillig als Torwart |
| ⚽ **Team-Generierung** | Sonntag 09:00 automatisch oder per `!team` |
| ⚖️ **Score-Balancing** | Teams werden nach Spieler-Scores optimal ausgeglichen |
| 🔄 **Score-Berechnung** | 50 % Gesamt · 30 % letzte 3 Monate · 20 % letztes Match |
| 🌐 **Web-API** | FastAPI-Endpunkte für spätere Weboberfläche bereits vorbereitet |

---

## Score-System

Jeder Spieler hat zwei Scores (0–10, Schrittweite 0,01):

| Score | Beschreibung |
|---|---|
| `field` | Feldspieler-Stärke – wird für das Team-Balancing verwendet |
| `gk` | Torwart-Qualität – wird nur für die GK-Zuweisung und GK-Wertung verwendet |

### Torwart-Zuweisung (automatisch bei `!team`)

1. **Freiwillige** – Spieler die `!gk` geschrieben haben, sortiert nach GK-Score
2. **GK-fähige Spieler** – Spieler mit aktivierter GK-Fähigkeit, sortiert nach GK-Score
3. **Fallback** – schwächster Feldspieler (niedrigster `field`-Score) pro Team

### Score-Neuberechnung nach `!result`

```
neuer_score = Ø_gesamt × 0,50
            + Ø_letzte_3_Monate × 0,30
            + letztes_Match × 0,20
```

Feldspieler und GKs werden **getrennt** bewertet:
- `field`-Score wird nur aktualisiert wenn der Spieler als Feldspieler gespielt hat
- `gk`-Score wird nur aktualisiert wenn der Spieler als Torwart gespielt hat

**Match-Score** aus Tordifferenz: `score = clamp(5 + tordifferenz, 0, 10)`
Beispiel: gewonnen +3 → 8,0 · Unentschieden → 5,0 · verloren −3 → 2,0

---

## Befehle

### Für alle Nutzer

| Befehl | Beschreibung |
|---|---|
| `!player` | Spielerliste mit Feld- und GK-Score |
| `!match [N]` | Letzte 5 (oder N) Ergebnisse |
| `!gk` | Als Torwart für dieses Spiel melden |
| `!kein_gk` | GK-Meldung zurückziehen |
| `!team` | Teams aus dem aktuellen Vote generieren |
| `!help` | Alle Befehle anzeigen |

### Admin – Spieler-Stammdaten

| Befehl | Beschreibung |
|---|---|
| `!player add @user:server Name` | Spieler anlegen |
| `!player add @user:server Name gk` | Spieler anlegen (Torwart-fähig) |
| `!player set @user:server 7.5` | Feldspieler-Score setzen (Standard) |
| `!player set @user:server field 7.5` | Feldspieler-Score setzen (explizit) |
| `!player set @user:server gk 8.0` | Torwart-Score setzen |
| `!player gk @user:server` | GK-Fähigkeit ein/aus (Score bleibt erhalten) |
| `!player del @user:server` | Spieler deaktivieren |

### Admin – Aktuelles Spiel (nach `!team`)

| Befehl | Beschreibung |
|---|---|
| `!match change Name1 Name2` | Zwei Spieler zwischen den Teams tauschen |
| `!match change Name` | Spieler ins andere Team verschieben |
| `!match gk Name` | Spieler als Torwart seines Teams setzen |
| `!match switched Name` | Spieler von Score-Wertung aus-/einschließen (Toggle) |

> Wenn ein Torwart per `!match change` verschoben wird, übernimmt automatisch der schwächste Feldspieler des verlassenen Teams die GK-Position.

### Admin – Ergebnis & Vote

| Befehl | Beschreibung |
|---|---|
| `!result 3:2` | Ergebnis eintragen und Scores neu berechnen |
| `!vote` | Wöchentlichen Vote sofort starten |

---

## Wöchentlicher Ablauf

```
Samstag 12:00  →  Bot postet Poll "Kicken Morgen, 23.03.2025 um 10:00"
                   Spieler stimmen mit ✅ / ❌ ab
                   Wer Torwart spielen möchte: !gk schreiben

Sonntag 09:00  →  Bot generiert automatisch die Teams
                   (oder manuell per !team)

Bei Bedarf     →  Admin korrigiert mit !match change / !match gk

Nach dem Spiel →  Admin: !result 3:2
                   Bot postet Ergebnis und aktualisiert alle Scores
```

---

## Setup

### 1. Repository klonen

```bash
git clone https://github.com/Phat-shot/Teambot.git
cd Teambot
```

### 2. Konfiguration anlegen

```bash
cp config.yml.example config.yml
nano config.yml
```

| Feld | Beispiel | Beschreibung |
|---|---|---|
| `homeserver` | `https://matrix.example.org` | URL des Matrix-Homeservers |
| `user_id` | `@teambot:example.org` | Matrix-ID des Bot-Accounts |
| `password` | `geheimes-pw` | Passwort des Bot-Accounts |
| `room_id` | `!abc123:example.org` | Interne Raum-ID (Einstellungen → Erweitert) |
| `admin_users` | `@du:example.org` | Matrix-IDs der Admins |

> ⚠️ Den Bot-Account **nicht** verschlüsseln – Bot-Räume sollten ohne E2E-Verschlüsselung betrieben werden.

### 3. Starten (Docker)

```bash
# Nur Bot:
docker compose up -d teambot

# Bot + Web-API:
docker compose --profile api up -d
```

### 4. Bot in Raum einladen

Im Matrix-Client: `/invite @teambot:example.org`

Der Bot tritt automatisch bei und schreibt eine Begrüßung.

### 5. Ersten Spieler anlegen

```
!player add @deinname:example.org Name
```

---

## Web-API (Phase 2)

Wenn die API aktiviert ist (`docker compose --profile api up`):

```
GET http://localhost:8080/players        → Alle aktiven Spieler
GET http://localhost:8080/players/1      → Einzelspieler
GET http://localhost:8080/matches/last   → Letztes Match
GET http://localhost:8080/health         → Status
```

---

## Datenbankstruktur

```
players              – Spieler, field-Score, GK-Score, GK-Fähigkeit
matches              – Matchergebnisse inkl. Torwart-IDs
match_participations – Score-Protokoll pro Spieler/Match (GK-Flag)
votes                – Abstimmungsnachrichten (Matrix Event-IDs)
vote_responses       – Abstimmungs-Antworten der Spieler
gk_requests          – !gk Meldungen pro Vote
```

Die SQLite-Datenbank liegt unter `data/teambot.db` und wird per Docker-Volume persistiert. Beim Update auf eine neue Version wird die Datenbank automatisch migriert – keine Datenverluste.

---

## Entwicklung

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Konfiguration anlegen (wird interaktiv erstellt falls nicht vorhanden):
python main.py

# Lokaler Selbsttest (ohne Matrix-Verbindung):
python test_local.py
```
