"""
web/server.py — Backend FastAPI per Logic Puzzles
Avvio: cd web && uvicorn server:app --reload --host 0.0.0.0 --port 8000
Accesso da telefono sulla stessa rete: http://<IP-del-PC>:8000
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Rende importabile il package puzzler dalla root del progetto
sys.path.insert(0, str(Path(__file__).parent.parent))

app = FastAPI(title="Logic Puzzles API")

# ── Difficulty params KenKen ──────────────────────────────────────────────────
_KK = {
    "easy":   dict(max_cage_size_factor=0.6, singleton_rate=0.05),
    "medium": dict(max_cage_size_factor=0.4, singleton_rate=0.15),
    "hard":   None,
}

# ── Request model ─────────────────────────────────────────────────────────────
class GenRequest(BaseModel):
    game: str
    n: int
    difficulty: str
    seed: Optional[int] = None

# ── Endpoint generazione ──────────────────────────────────────────────────────
@app.post("/api/generate")
async def generate(req: GenRequest):
    seed = req.seed if req.seed is not None else random.randint(0, 99_999)
    t0 = time.time()
    cages = None

    if req.game == "sudoku":
        from puzzler.sudoku import generate_puzzle
        puzzle, solution = generate_puzzle(req.n, seed=seed, difficulty=req.difficulty)

    elif req.game == "kenken":
        from puzzler.kenken import generate_kenken_puzzle, generate_minimal_kenken_puzzle
        if req.difficulty == "hard":
            max_cage = max(2, int(req.n * 0.4))
            solution, raw = generate_minimal_kenken_puzzle(req.n, max_cage_size=max_cage, seed=seed)
        else:
            p = _KK[req.difficulty]
            max_cage = max(2, int(req.n * p["max_cage_size_factor"]))
            solution, raw = generate_kenken_puzzle(
                req.n, max_cage_size=max_cage,
                singleton_rate=p["singleton_rate"], seed=seed,
            )
        puzzle = [[0] * req.n for _ in range(req.n)]
        # Converti tuple → liste per JSON
        cages = [
            {"op": c["op"], "target": c["target"],
             "cells": [list(cell) for cell in c["cells"]]}
            for c in raw
        ]

    elif req.game == "diagonal":
        from puzzler.diagonal import generate_diagonal_puzzle
        puzzle, solution = generate_diagonal_puzzle(req.n, seed=seed, difficulty=req.difficulty)

    elif req.game == "hyper":
        from puzzler.hyper import generate_hyper_puzzle
        puzzle, solution = generate_hyper_puzzle(req.n, seed=seed, difficulty=req.difficulty)

    elif req.game == "nonconsecutive":
        from puzzler.nonconsecutive import generate_nonconsecutive_puzzle
        puzzle, solution = generate_nonconsecutive_puzzle(req.n, seed=seed, difficulty=req.difficulty)

    else:
        return {"error": f"Gioco sconosciuto: {req.game}"}

    return {
        "puzzle":   puzzle,
        "solution": solution,
        "cages":    cages,
        "elapsed":  round(time.time() - t0, 2),
        "seed":     seed,
    }

# ── File statici ──────────────────────────────────────────────────────────────
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

@app.get("/")
async def root():
    return FileResponse(str(STATIC / "index.html"))

@app.get("/manifest.json")
async def manifest():
    return FileResponse(str(STATIC / "manifest.json"))

@app.get("/sw.js")
async def sw():
    return FileResponse(str(STATIC / "sw.js"))
