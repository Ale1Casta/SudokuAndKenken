from __future__ import annotations

import random
from typing import List, Optional, Sequence, Tuple

from z3 import *

from puzzler.core import create_int_grid, model_to_grid, has_second_solution
from puzzler.sudoku.model import _add_classic_sudoku_constraints, add_clues


# ── Modello Z3 ────────────────────────────────────────────────────────────────

def build_nonconsecutive_model(n: int = 9) -> Tuple[Solver, List[List]]:
    """
    Crea un solver Z3 per Nonconsecutive Sudoku NxN.

    Vincolo aggiuntivo rispetto al Sudoku classico:
      - Nessuna coppia di celle ortogonalmente adiacenti (orizzontale o
        verticale) può avere valori consecutivi, cioè |a - b| ≠ 1.

    Questo equivale ad aggiungere, per ogni coppia (a, b) adiacente:
        a - b ≠  1
        a - b ≠ -1
    (entrambi lineari, Z3 li gestisce come aritmetica lineare).

    Nota: n=4 è UNSAT — con valori 1-4 le uniche righe valide sono
    [2,4,1,3] e [3,1,4,2], che risultano sempre consecutive in verticale.
    Supporto: n=9.
    """
    assert n == 9, "Nonconsecutive Sudoku supporta solo n=9 (n=4 è UNSAT)"
    X, domain = create_int_grid("nc", n, 1, n)
    s = Solver()
    s.add(*domain)
    _add_classic_sudoku_constraints(s, X)
    for r in range(n):
        for c in range(n):
            if c + 1 < n:
                s.add(X[r][c]   - X[r][c+1] != 1)
                s.add(X[r][c+1] - X[r][c]   != 1)
            if r + 1 < n:
                s.add(X[r][c]   - X[r+1][c] != 1)
                s.add(X[r+1][c] - X[r][c]   != 1)
    return s, X


# ── Solver pubblico ───────────────────────────────────────────────────────────

def solve_nonconsecutive(
    puzzle: Optional[Sequence[Sequence[int]]] = None,
    n: int = 9,
) -> Optional[List[List[int]]]:
    """
    Risolve un Nonconsecutive Sudoku NxN.
    puzzle=None → cerca una soluzione qualsiasi.
    Ritorna None se UNSAT.
    """
    s, X = build_nonconsecutive_model(n)
    if puzzle is not None:
        add_clues(s, X, puzzle)
    return model_to_grid(s.model(), X) if s.check() == sat else None


# ── Unicità (rebuild) — usato da test e verifiche esterne ─────────────────────

def _check_unique_nc(clues: List[List[int]], n: int) -> bool:
    """Verifica unicità ricostruendo il modello da zero (uso esterno/test)."""
    s, X = build_nonconsecutive_model(n)
    add_clues(s, X, clues)
    has_two, _, _2 = has_second_solution(s, X)
    return not has_two


# ── Unicità (incrementale) — usato internamente dalla generazione ─────────────

def _is_unique_assumptions(
    s: Solver,
    X: List[List],
    assumptions: List,
    n: int,
) -> bool:
    """
    Verifica unicità tramite Z3 assumptions, senza modificare il solver.

    Le assumptions sono vincoli temporanei (clue del puzzle corrente):
    Z3 non le aggiunge permanentemente allo stato del solver, quindi le
    clausole CDCL apprese rimangono tra una chiamata e l'altra (warm start).
    Questo è 5-10x più veloce del rebuild da zero per ogni check.

    Se Z3 va in timeout su uno dei due check, restituisce False
    (comportamento conservativo: la cella viene mantenuta, il puzzle
    rimane sicuramente unico).

    Ritorna True SOLO se Z3 prova definitivamente l'unicità.
    """
    # 1° check: trova la prima soluzione (deve essere sat — la nostra soluzione esiste)
    res1 = s.check(*assumptions)
    if res1 != sat:
        return False  # timeout (unknown) o unsat inatteso → mantieni la cella

    first = model_to_grid(s.model(), X)

    # 2° check: prova a trovare una seconda soluzione diversa dalla prima
    diff = Or([X[r][c] != first[r][c] for r in range(n) for c in range(n)])
    res2 = s.check(*assumptions, diff)

    # unsat → unico; sat → non unico; unknown (timeout) → conservativo
    return res2 == unsat


# ── Generazione ───────────────────────────────────────────────────────────────

def generate_puzzle(
    n: int = 9,
    seed: Optional[int] = None,
    difficulty: str = "medium",
) -> Tuple[List[List[int]], List[List[int]]]:
    """
    Genera un puzzle Nonconsecutive Sudoku 9x9.

    Usa Z3 incrementale con assumptions per tutti i check di unicità:
    il modello base (vincoli nonconsecutive + latin square) viene costruito
    UNA VOLTA, le clue sono passate come assumptions temporanee ad ogni check.
    Z3 riusa le clausole CDCL apprese tra un check e l'altro (warm start).

    difficulty:
      - "easy"   → ~55% celle visibili (~45 indizi)
      - "medium" → ~35% celle visibili (~28 indizi)
      - "hard"   → minimale con timeout 2s per check (~15-22 indizi, <90s).
                   Il timeout è conservativo: se Z3 non riesce a provare
                   l'unicità entro 2s, la cella viene mantenuta. Il puzzle
                   risultante è unico e vicino al minimale.

    Solo n=9 supportato (n=4 è UNSAT, vedi build_nonconsecutive_model).
    """
    assert n == 9, "Nonconsecutive Sudoku supporta solo n=9"
    if seed is not None:
        random.seed(seed)

    # ── 1. Prima riga valida ──────────────────────────────────────────────────
    # La prima riga non può avere coppie orizzontali consecutive
    # (altrimenti il modello è UNSAT immediatamente).
    digits = list(range(1, n + 1))
    while True:
        random.shuffle(digits)
        if all(abs(digits[c] - digits[c + 1]) != 1 for c in range(n - 1)):
            break

    # ── 2. Soluzione completa via Z3 ─────────────────────────────────────────
    s_gen, X_gen = build_nonconsecutive_model(n)
    for c, v in enumerate(digits):
        s_gen.add(X_gen[0][c] == v)
    assert s_gen.check() == sat, "Impossibile generare soluzione per Nonconsecutive Sudoku"
    solution = model_to_grid(s_gen.model(), X_gen)

    # ── 3. Modello incrementale per i check (senza clues) ────────────────────
    s_chk, X_chk = build_nonconsecutive_model(n)

    # Pre-crea le espressioni Z3 per le clues: evita di ricrearle
    # ad ogni iterazione (risparmia tempo di costruzione Z3).
    clue_expr = [
        [X_chk[r][c] == solution[r][c] for c in range(n)]
        for r in range(n)
    ]

    if difficulty == "hard":
        # Timeout per check: se Z3 impiega >2s, la cella viene mantenuta
        # (conservativo). Evita la coda esponenziale del minimale completo.
        s_chk.set("timeout", 2000)

    puzzle = [row[:] for row in solution]
    cells = [(r, c) for r in range(n) for c in range(n)]
    random.shuffle(cells)

    if difficulty == "hard":
        # Prova a rimuovere tutte le celle (minimale); il timeout limita il tempo
        for r, c in cells:
            backup = puzzle[r][c]
            puzzle[r][c] = 0

            assumptions = [
                clue_expr[ri][ci]
                for ri in range(n) for ci in range(n)
                if puzzle[ri][ci] != 0
            ]

            if not _is_unique_assumptions(s_chk, X_chk, assumptions, n):
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

            assumptions = [
                clue_expr[ri][ci]
                for ri in range(n) for ci in range(n)
                if puzzle[ri][ci] != 0
            ]

            if _is_unique_assumptions(s_chk, X_chk, assumptions, n):
                removed += 1
            else:
                puzzle[r][c] = backup

    return puzzle, solution
