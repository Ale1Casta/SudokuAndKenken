from __future__ import annotations

import random
from typing import List, Optional, Sequence, Tuple

from z3 import *

from puzzler.core import create_int_grid, model_to_grid, has_second_solution
from puzzler.sudoku.model import _add_classic_sudoku_constraints, add_clues


# ── Finestre extra ────────────────────────────────────────────────────────────

# Le 4 regioni 3x3 aggiuntive dell'Hyper Sudoku 9x9 (indici 0-based).
# Sono sfalsate rispetto ai box standard: si trovano "tra" i box classici.
#
#  Box standard: righe 0-2, 3-5, 6-8 × colonne 0-2, 3-5, 6-8
#  Finestre hyper: centrate su righe 1-3, 5-7 × colonne 1-3, 5-7
#
_HYPER_WINDOWS: List[List[Tuple[int, int]]] = [
    [(r, c) for r in range(1, 4) for c in range(1, 4)],  # in alto a sinistra
    [(r, c) for r in range(1, 4) for c in range(5, 8)],  # in alto a destra
    [(r, c) for r in range(5, 8) for c in range(1, 4)],  # in basso a sinistra
    [(r, c) for r in range(5, 8) for c in range(5, 8)],  # in basso a destra
]


def get_windows() -> List[List[Tuple[int, int]]]:
    """Ritorna le 4 finestre extra (utile per la visualizzazione del puzzle)."""
    return [list(w) for w in _HYPER_WINDOWS]


# ── Modello Z3 ────────────────────────────────────────────────────────────────

def build_hyper_model(n: int = 9) -> Tuple[Solver, List[List]]:
    """
    Crea un solver Z3 per Hyper Sudoku 9x9.

    Vincoli aggiuntivi rispetto al Sudoku classico:
      - 4 regioni 3x3 "sfalsate" (finestre) devono avere valori distinti,
        per un totale di +4 Distinct.

    Solo n=9 è supportato (le finestre sono specifiche del 9x9).
    """
    assert n == 9, "Hyper Sudoku supporta solo n=9"
    X, domain = create_int_grid("hyp", n, 1, n)
    s = Solver()
    s.add(*domain)
    _add_classic_sudoku_constraints(s, X)
    # +4 Distinct per le finestre hyper
    for window in _HYPER_WINDOWS:
        s.add(Distinct([X[r][c] for r, c in window]))
    return s, X


# ── Solver pubblico ───────────────────────────────────────────────────────────

def solve_hyper(
    puzzle: Optional[Sequence[Sequence[int]]] = None,
    n: int = 9,
) -> Optional[List[List[int]]]:
    """
    Risolve un Hyper Sudoku 9x9.
    puzzle=None → cerca una soluzione qualsiasi.
    Ritorna None se UNSAT.
    """
    s, X = build_hyper_model(n)
    if puzzle is not None:
        add_clues(s, X, puzzle)
    return model_to_grid(s.model(), X) if s.check() == sat else None


# ── Unicità ───────────────────────────────────────────────────────────────────

def _check_unique_hyper(clues: List[List[int]]) -> bool:
    s, X = build_hyper_model(9)
    add_clues(s, X, clues)
    has_two, _, _2 = has_second_solution(s, X)
    return not has_two


# ── Generazione ───────────────────────────────────────────────────────────────

def generate_puzzle(
    n: int = 9,
    seed: Optional[int] = None,
    difficulty: str = "medium",
) -> Tuple[List[List[int]], List[List[int]]]:
    """
    Genera un puzzle Hyper Sudoku 9x9.

    La soluzione viene generata con Z3 forzando anche i vincoli delle
    finestre hyper (non tutte le soluzioni Sudoku classiche li rispettano).

    difficulty:
      - "easy"   → ~55% celle visibili
      - "medium" → ~35% celle visibili
      - "hard"   → algoritmo minimale (rimuove il massimo possibile)

    Solo n=9 supportato.
    """
    assert n == 9, "Hyper Sudoku supporta solo n=9"
    if seed is not None:
        random.seed(seed)

    digits = list(range(1, 10))
    random.shuffle(digits)
    s, X = build_hyper_model(9)
    for c, v in enumerate(digits):
        s.add(X[0][c] == v)
    assert s.check() == sat, "Impossibile generare soluzione per Hyper Sudoku"
    solution = model_to_grid(s.model(), X)

    puzzle = [row[:] for row in solution]
    cells = [(r, c) for r in range(9) for c in range(9)]
    random.shuffle(cells)

    if difficulty == "hard":
        for r, c in cells:
            backup = puzzle[r][c]
            puzzle[r][c] = 0
            if not _check_unique_hyper(puzzle):
                puzzle[r][c] = backup
    else:
        target_pct = 0.55 if difficulty == "easy" else 0.35
        max_remove = 81 - int(81 * target_pct)
        removed = 0
        for r, c in cells:
            if removed >= max_remove:
                break
            backup = puzzle[r][c]
            puzzle[r][c] = 0
            if _check_unique_hyper(puzzle):
                removed += 1
            else:
                puzzle[r][c] = backup

    return puzzle, solution
