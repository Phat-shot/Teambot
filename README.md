# ⚽ TeamBot

Matrix-Bot für die wöchentliche Fußball-Teamaufstellung. Erstellt automatisch ausgeglichene Teams via Snake-Draft, verwaltet Torwart-Meldungen und berechnet Spieler-Rankings nach jedem Spiel neu.

Zwei Räume: ein **Hauptraum** für alle Spieler (Vote, Ankündigungen) und ein **Admin-Raum** für die Teamverwaltung.

---

## Features

| Feature | Details |
|---|---|
| 🗳️ **Wöchentlicher Vote** | Samstag 12:00 – Bot postet automatisch einen Poll |
| ✅ **Abstimmung** | Spieler stimmen per nativen Matrix-Poll (auch via WA-Bridge) ab |
| 🥅 **GK-Meldung** | Mit 🥅-Reaktion auf den Vote-Poll als Torwart melden |
| 🩹 **Angeschlagen** | Mit 🩹-Reaktion melden – wird beim Matching herabgestuft |
| 👤 **Gäste** | Mit 1️⃣–9️⃣-Reaktion auf den Vote-Poll Gäste hinzufügen |
| 🔃 **Team-Tausch** | Mit 🔃-Reaktion auf die Team-Ankündigung ins andere Team wechseln |
| ⚽ **Snake-Draft** | Teams werden fair via Snake-Draft nach Spieler-Ranking aufgeteilt |
| 🛠️ **Admin-Team-Poll** | Nach `!team` erscheint Poll in Admin-Gruppe zur interaktiven Bearbeitung |
| 🤖 **Interaktives Menü** | `!cmd` öffnet geführtes Poll-Menü im Admin-Raum |

---

## Räume & Berechtigungen

| Raum | Wer | Was |
|---|---|---|
| **Hauptraum** | Alle Spieler | Vote abstimmen, Reaktionen, Ankündigungen empfangen |
| **Admin-Raum** | Admins | Alle Befehle, Team-Poll, interaktives Menü |

Im Hauptraum gibt es keine Befehle – alles läuft über Reaktionen auf den Vote-Poll.

---

## Spieler-Aktionen im Hauptraum

Reaktionen auf den **Vote-Poll** (samstags gepostet):

| Reaktion | Aktion |
|---|---|
| Poll-Antwort „✅ Dabei" | Zusage – im Poll-UI antippen/anklicken |
| Poll-Antwort „❌ Nicht dabei" | Absage – im Poll-UI antippen/anklicken |
| 🥅 | Als Torwart melden – nur wer sich meldet wird als GK eingesetzt |
| 🩹 | Angeschlagen melden – wird beim Team-Matching herabgestuft |
| 1️⃣–9️⃣ | N Gäste hinzufügen (z.B. 2️⃣ → „[User]s Gast 1", „[User]s Gast 2") |

Reaktion auf die **Team-Ankündigung**:

| Reaktion | Aktion |
|---|---|
| 🔃 | Ins andere Team wechseln – automatischer Tausch mit ähnlich eingestuftem Gegenspieler |

Wer zum ersten Mal ✅ klickt und noch nicht registriert ist, wird automatisch angelegt und im Admin-Raum gemeldet.

---

## Admin-Team-Poll

Nach jedem `!team`-Aufruf postet der Bot automatisch einen Poll in den **Admin-Raum**. Der Poll listet alle Spieler mit Team-Zugehörigkeit (🟡 / 🌈) als Antworten.

**Ablauf:** Spieler im Poll auswählen (Multi-Select), dann mit Emoji reagieren:

| Reaktion | Aktion |
|---|---|
| 🔃 | Selektierte Spieler ins andere Team wechseln |
| 🥅 | Selektierte Spieler als Torwart setzen |
| 1️⃣–9️⃣ | N Gäste hinzufügen, fair auf beide Teams verteilt |
| 📣 | Aktuelles Team in Hauptgruppe ankündigen |

Nach jeder Aktion: alter Poll gelöscht, neuer Poll gepostet, Hauptraum automatisch aktualisiert.

---

## Admin-Befehle (nur im Admin-Raum)

| Befehl | Beschreibung |
|---|---|
| `!team` | Neuen Team-Vorschlag generieren (A, B, C, …) |
| `!team A` | Vorschlag A aktivieren |
| `!team vote` | Alle Vorschläge zur Abstimmung stellen |
| `!vote` | Wöchentlichen Vote sofort starten |
| `!vote status` | Aktuelle Zusagen aus der DB anzeigen |
| `!result 3:2` | Ergebnis eintragen und Rankings neu berechnen |
| `!help` | Alle Befehle anzeigen |
| `!player` | Spielerliste mit Rankings |
| `!player add @user:server [Name] [gk]` | Spieler anlegen |
| `!player set Name 7.5` | Spieler-Ranking manuell setzen |
| `!player gk Name` | GK-Bevorzugung ein/aus |
| `!player del Name` | Spieler deaktivieren |
| `!name 0042 Neuer Name` | Spieler über interne ID umbenennen |
| `!match [N]` | Letzte 5 (oder N) Ergebnisse |
| `!match change Name1 [Name2]` | Spieler tauschen oder verschieben |
| `!match gk Name` | Spieler als Torwart seines Teams setzen |
| `!match switched Name` | Wertung ein-/ausschalten (Toggle) |
| `!match guest "Name" [Score]` | Gastspieler manuell hinzufügen |
| `!cmd` | Geführtes Poll-Menü starten |

---

## Team-Aufstellung

### Spieler-Ranking

Jeder Spieler hat ein internes Ranking das vom Admin vorab gesetzt wird. Dieses wird nach jedem Spieltag anhand der Ergebnisse automatisch angepasst. Das Ranking ist nur für Admins sichtbar und wird nicht im Hauptraum angezeigt.

Gäste spielen mit einem Standard-Ranking. Wer sich mit 🩹 als angeschlagen meldet wird für diesen Spieltag beim Matching herabgestuft – das Basis-Ranking bleibt unverändert.

### Snake-Draft

Die Teamaufteilung folgt dem Snake-Draft-Prinzip:

1. Alle Spieler werden nach ihrem Ranking sortiert (bester zuerst).
2. Torwart-Plätze werden zuerst vergeben – nur an Spieler die sich explizit mit 🥅 gemeldet haben. Wer sich nicht meldet, wird nicht als Torwart eingesetzt. Das Team entscheidet dann vor Ort.
3. Die verbleibenden Feldspieler werden abwechselnd verteilt: Pick 1 → 🟡 Gelb, Pick 2 → 🌈 Bunt, Pick 3 → 🟡 Gelb, Pick 4 → 🌈 Bunt, … Bei ungerader Spielerzahl bekommt 🌈 Bunt den letzten Spieler.
4. Gäste werden nach Möglichkeit ins gleiche Team wie ihr Mitbringer gesetzt.

Weitere Vorschläge (B, C, …) können mit `!team` generiert und verglichen werden.

### Manuelle Anpassungen

Im Admin-Team-Poll können Spieler zwischen den Teams verschoben, Torwarte gesetzt und Gäste hinzugefügt werden. Jede Änderung wird sofort im Hauptraum aktualisiert.

---

## Wöchentlicher Ablauf

```
Samstag 12:00  →  Bot postet Poll „Kicken Sonntag, DD.MM.YYYY um 10:00"
                   Im Poll „✅ Dabei" / „❌ Nicht dabei" antippen
                   🥅 = als Torwart melden (Emoji-Reaktion auf den Poll)
                   🩹 = angeschlagen melden (Emoji-Reaktion auf den Poll)
                   1️⃣–9️⃣ = Gäste hinzufügen (Emoji-Reaktion auf den Poll)

Sonntag 09:00  →  Bot generiert automatisch Vorschlag A via Snake-Draft
                   → Admin-Team-Poll erscheint in Admin-Gruppe
                   Spieler auswählen + 🔃/🥅/1️⃣–9️⃣ reagieren
                   !team für weitere Vorschläge B, C, …

📣-Reaktion      →  Team wird in Hauptgruppe angekündigt
🔃-Reaktion      →  Spieler wechselt Team (Reaktion auf Team-Nachricht im Hauptraum)

Nach dem Spiel →  Admin: !result 3:2
                   Bot postet Ergebnis in Haupt- und Admin-Raum
                   Rankings werden automatisch neu berechnet
```

---

## Setup

### 1. Repository klonen

```bash
git clone https://github.com/Phat-shot/Teambot.git
cd Teambot
```

### 2. Räume anlegen

Zwei Matrix-Räume – **beide ohne E2E-Verschlüsselung**:
- **Hauptraum** – für alle Spieler
- **Admin-Raum** – nur für Admins

### 3. Konfiguration

```bash
cp config.yml.example config.yml
nano config.yml
```

| Feld | Beschreibung |
|---|---|
| `homeserver` | URL des Matrix-Homeservers |
| `user_id` | Matrix-ID des Bot-Accounts |
| `password` | Passwort des Bot-Accounts |
| `room_id` | Raum-ID des Hauptraums |
| `admin_room_id` | Raum-ID des Admin-Raums |
| `poll_sender_id` | Matrix-ID eines WA-Bridge-Users (optional) |
| `poll_sender_password` | Passwort dieses Users (optional) |

`poll_sender_id/password`: Workaround für mautrix-whatsapp – Polls und Hauptraum-Nachrichten werden über diesen Account gesendet, sodass kein `!wa set-relay` nötig ist.

### 4. Starten

```bash
docker compose pull teambot && docker compose up -d teambot
```

### 5. Bot einladen

Admin-Raum: `/invite @teambot:example.org`
Hauptraum: `/invite @teambot:example.org` (optional – poll_sender muss Mitglied sein)

---

## Datenbankstruktur

```
players              – Spieler mit internem Ranking (#0001–#9999)
matches              – Matchergebnisse
match_participations – Bewertung pro Spieler pro Match
votes                – Vote-Events (Matrix Event-IDs)
vote_responses       – Abstimmungs-Antworten
gk_requests          – 🥅-Meldungen pro Vote
injured_requests     – 🩹-Meldungen pro Vote
```
