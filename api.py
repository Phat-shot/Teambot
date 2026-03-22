"""
Web-API für TeamBot – abrufbar per Browser/App.
Startet separat: uvicorn api:app --host 0.0.0.0 --port 8080

Geplante Endpunkte (Phase 2):
  GET  /players          – Alle Spieler
  GET  /players/{id}     – Einzelspieler inkl. Score-History
  GET  /matches          – Letzte Matches
  GET  /matches/{id}     – Matchdetails
  POST /matches          – Match manuell eintragen (API-Key gesichert)
"""

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db import Database

DB_PATH = os.getenv("DB_PATH", "data/teambot.db")

app = FastAPI(
    title="TeamBot API",
    description="Spielerdaten & Matchhistorie",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

db = Database(DB_PATH)


@app.on_event("startup")
async def startup():
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    await db.close()


@app.get("/players", summary="Alle aktiven Spieler")
async def get_players():
    return await db.get_all_players(active_only=True)


@app.get("/players/{player_id}", summary="Einzelspieler")
async def get_player(player_id: int):
    p = await db.get_player_by_id(player_id)
    if not p:
        raise HTTPException(status_code=404, detail="Spieler nicht gefunden")
    return p


@app.get("/matches/last", summary="Letztes Match")
async def get_last_match():
    m = await db.get_last_match()
    if not m:
        raise HTTPException(status_code=404, detail="Kein Match vorhanden")
    return m


@app.get("/health")
async def health():
    return {"status": "ok"}
