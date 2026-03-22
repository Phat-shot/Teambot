# ⚽ TeamBot

Matrix-Bot zur automatischen Mannschaftsaufstellung beim wöchentlichen Kick.

---

## Features

| Feature | Details |
|---|---|
| 🗳️ **Wöchentlicher Vote** | Samstag 12:00 – Bot postet automatisch eine Abstimmung |
| ✅ **Emoji-Reaktionen** | Spieler reagieren mit ✅/❌ auf die Vote-Nachricht |
| ⚽ **Team-Generierung** | Sonntag 09:00 automatisch *oder* manuell per `!team` |
| ⚖️ **Score-Balancing** | Teams werden nach gewichtetem Score optimal ausgeglichen |
| 📊 **Score-Berechnung** | 50% Gesamt · 30% letzte 3 Monate · 20% letztes Match |
| 🌐 **Web-API** | FastAPI-Endpunkte für spätere Weboberfläche vorbereitet |

---

## Score-System

Jeder Spieler hat drei Scores (0–10, Schrittweite 0,01):

| Score | Emoji | Beschreibung |
|---|---|---|
| `offensive` | ⚔️ | Offensivstärke |
| `defensive` | 🛡️ | Defensivstärke |
| `goalkeeper` | 🧤 | Torwartqualität |

Für das **Team-Balancing** wird nur der gewichtete **Hauptscore** (Rolle) verwendet.

### Score-Neuberechnung nach Match

Nach `!ergebnis 3:2` wird der Hauptscore jedes Spielers neu berechnet:

```
neuer_score = Ø_gesamt × 0.50
            + Ø_letzte_3_Monate × 0.30
            + letztes_Match × 0.20
```

**Match-Score** aus Tordifferenz: `score = clamp(5 + tordifferenz, 0, 10)`  
→ Gewonnen +3 → 8,0 | Unentschieden → 5,0 | Verloren −3 → 2,0

---

## Setup

### 1. Konfiguration

```bash
cp config.yml.example config.yml
# config.yml anpassen (Homeserver, User-ID, Passwort, Raum-ID, Admins)
```

### 2. Lokal starten (Entwicklung)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 3. Docker (Produktion)

```bash
# Nur Bot:
docker compose up -d teambot

# Bot + Web-API:
docker compose --profile api up -d
```

---

## Bot-Befehle

### Alle Nutzer

| Befehl | Beschreibung |
|---|---|
| `!team` | Teams aus aktuellem Vote generieren |
| `!spieler` | Spielerliste mit Scores anzeigen |
| `!scores` | Detaillierte Score-Tabelle |

### Admin-Befehle

| Befehl | Beispiel |
|---|---|
| Spieler hinzufügen | `!spieler add @max:matrix.org Max offensive` |
| Score setzen | `!spieler set @max:matrix.org offensive 7.5` |
| Hauptrolle ändern | `!spieler role @max:matrix.org goalkeeper` |
| Spieler deaktivieren | `!spieler del @max:matrix.org` |
| Ergebnis eintragen | `!ergebnis 3:2` |
| Vote manuell starten | `!vote` |
| Hilfe | `!help` |

---

## Wöchentlicher Ablauf

```
Samstag 12:00  →  Bot postet "Kicken Morgen, 23.03.2025 um 10:00"
                   Spieler reagieren mit ✅ oder ❌

Sonntag 09:00  →  Bot generiert automatisch die Teams
                   (alternativ: !team manuell)

Nach dem Spiel →  Admin tippt: !ergebnis 3:2
                   Bot postet Ergebnis + aktualisiert Scores
```

---

## Web-API (Phase 2)

Wenn die API aktiviert ist (`docker compose --profile api up`):

```
GET http://localhost:8080/players        → Alle Spieler
GET http://localhost:8080/players/1      → Spieler #1
GET http://localhost:8080/matches/last   → Letztes Match
GET http://localhost:8080/health         → Status
```

---

## Datenbankstruktur

```
players             – Spieler + 3 Scores + Hauptrolle
matches             – Matchergebnisse
match_participations – Score-Protokoll pro Spieler pro Match
votes               – Abstimmungsnachrichten
vote_responses      – Reaktionen der Spieler
```

Die SQLite-Datenbank liegt unter `data/teambot.db` und wird per Docker-Volume persistiert.
