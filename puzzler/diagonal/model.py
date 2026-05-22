from __future__ import annotations

import random
from typing import List, Optional, Sequence, Tuple

from z3 import *

from puzzler.core import create_int_grid, model_to_grid, has_second_solution
from puzzler.sudoku.model import _add_classic_sudoku_constraints, add_clues


# ── Modello Z3 ────────────────────────────────────────────────────────────────

def build_diagonal_model(n: int = 9) -> Tuple[Solver, List[List]]:
    """
    Crea un solver Z3 per Diagonal (X) Sudoku NxN.

    Vincoli aggiuntivi rispetto al Sudoku classico:
      - Diagonale principale  (0,0)→(n-1,n-1) : valori tutti distinti
      - Diagonale secondaria  (0,n-1)→(n-1,0) : valori tutti distinti

    Questi due vincoli extra rendono il puzzle più vincolato, consentendo
    in genere di rimuovere più celle mantenendo l'unicità della soluzione.
    """
    X, domain = create_int_grid("diag", n, 1, n)
    s = Solver()
    s.add(*domain)
    _add_classic_sudoku_constraints(s, X)
    # +2 Distinct per le diagonali
    s.add(Distinct([X[i][i]       for i in range(n)]))
    s.add(Distinct([X[i][n-1-i]  for i in range(n)]))
    return s, X


# ── Solver pubblico ───────────────────────────────────────────────────────────

def solve_diagonal(
    puzzle: Optional[Sequence[Sequence[int]]] = None,
    n: int = 9,
) -> Optional[List[List[int]]]:
    """
    Risolve un Diagonal Sudoku NxN.
    puzzle=None → cerca una soluzione qualsiasi.
    Ritorna None se UNSAT.
    """
    s, X = build_diagonal_model(n)
    if puzzle is not None:
        add_clues(s, X, puzzle)
    return model_to_grid(s.model(), X) if s.check() == sat else None


# ── Unicità ───────────────────────────────────────────────────────────────────

def _check_unique_diag(clues: List[List[int]], n: int) -> bool:
    s, X = build_diagonal_model(n)
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
    Genera un puzzle Diagonal Sudoku NxN.

    La soluzione viene generata con Z3 usando i vincoli diagonali (non
    tutte le soluzioni Sudoku classiche soddisfano i vincoli diagonali).

    difficulty:
      - "easy"   → ~55% celle visibili
      - "medium" → ~35% celle visibili
      - "hard"   → algoritmo minimale (rimuove il massimo possibile)

    Supporto: n = 4, 9 (Z3).
    """
    if seed is not None:
        random.seed(seed)

    # Genera soluzione completa rispettando i vincoli diagonali
    digits = list(range(1, n + 1))
    random.shuffle(digits)
    s, X = build_diagonal_model(n)
    for c, v in enumerate(digits):
        s.add(X[0][c] == v)
    assert s.check() == sat, "Impossibile generare soluzione per Diagonal Sudoku"
    solution = model_to_grid(s.model(), X)

    puzzle = [row[:] for row in solution]
    cells = [(r, c) for r in range(n) for c in range(n)]
    random.shuffle(cells)

    if difficulty == "hard":
        # Minimale: rimuovi quante più celle possibile
        for r, c in cells:
            backup = puzzle[r][c]
            puzzle[r][c] = 0
            if not _check_unique_diag(puzzle, n):
                puzzle[r][c] = backup
    else:
        target_pct = 0.55 if difficulty == "easy" else 0.35
        max_remove = n * n - int(n * n * target_pct)
        removed = 0
        for r, c in cells:
            if removed >= max_remove:
                break
            backup = puzzle[r][c]
            puzzle[r][c] = 0
            if _check_unique_diag(puzzle, n):
                removed += 1
            else:
                puzzle[r][c] = backup

    return puzzle, solution
