from __future__ import annotations

import sys
import time as _time
import random
from typing import List, Tuple, Sequence, Optional

from z3 import *

from puzzler.core import *


# ── Costruzione modello ───────────────────────────────────────────────────────

def _add_classic_sudoku_constraints(s: Solver, X) -> None:
    """
    Aggiunge i vincoli classici di Sudoku:
    - Distinct su righe
    - Distinct su colonne
    - Distinct su box sqrt(n) x sqrt(n)
    """
    n = len(X)
    box = int(n ** 0.5)
    assert box * box == n, "Solo Sudoku con box quadrati (es. 4, 9, 16)."

    for r in range(n):
        s.add(Distinct(X[r]))

    for c in range(n):
        s.add(Distinct([X[r][c] for r in range(n)]))

    for br in range(box):
        for bc in range(box):
            cells = [
                X[br * box + r][bc * box + c]
                for r in range(box)
                for c in range(box)
            ]
            s.add(Distinct(cells))


def build_sudoku_model(n: int = 9) -> Tuple[Solver, List[List]]:
    """
    Crea un solver Z3 con i vincoli base di un Sudoku NxN.
    Ritorna (solver, X) dove X e' la griglia di variabili.
    """
    X, constraints = create_int_grid("x", n, 1, n)
    s = Solver()
    s.add(*constraints)
    _add_classic_sudoku_constraints(s, X)
    return s, X


def add_clues(s: Solver, X, grid: Sequence[Sequence[int]], zero_is_empty: bool = True) -> None:
    """
    Aggiunge al solver i vincoli corrispondenti agli indizi (clues) di una griglia.
    Con zero_is_empty=True, lo 0 indica cella vuota.
    """
    n = len(X)
    assert len(grid) == n and all(len(row) == n for row in grid), "Grid size mismatch."

    for r in range(n):
        for c in range(n):
            val = grid[r][c]
            if zero_is_empty and val == 0:
                continue
            if not zero_is_empty and val is None:
                continue
            s.add(X[r][c] == int(val))


# ── Solver pubblico ───────────────────────────────────────────────────────────

def solve_sudoku(grid: Optional[Sequence[Sequence[int]]] = None, n: int = 9) -> Optional[List[List[int]]]:
    """
    Risolve un Sudoku NxN:
    - se grid=None, risolve un Sudoku puramente "astratto" (senza indizi);
    - se grid e' fornita, aggiunge i vincoli agli indizi e prova a risolvere.

    Ritorna la soluzione come griglia di int, oppure None se UNSAT.
    """
    s, X = build_sudoku_model(n)
    if grid is not None:
        add_clues(s, X, grid)
    if s.check() != sat:
        return None
    return model_to_grid(s.model(), X)


# ── Unicita' ──────────────────────────────────────────────────────────────────

def is_puzzle_unique(solution: List[List[int]], clues_grid: List[List[int]], n: int) -> bool:
    """
    Controlla se un puzzle con dati indizi ha soluzione UNICA.
    Esposto pubblicamente per i test; usato anche internamente da generate_*.
    Usa Z3. Per n=16 usare _check_unique che smista sul backtracker.
    """
    s, X = build_sudoku_model(n)
    add_clues(s, X, clues_grid)
    has_two, _, _2 = has_second_solution(s, X)
    return not has_two


def _is_unique_backtracking(
    grid: List[List[int]], n: int, time_limit: Optional[float] = None
) -> Optional[bool]:
    """
    Verifica unicita' tramite backtracking ITERATIVO Python puro, senza Z3.

    Conta le soluzioni trovate fermandosi a 2: se ne trova piu' di una il
    puzzle non e' unico. Molto piu' veloce di Z3 per n=16.

    Tecnica: backtracking iterativo (stack esplicito, nessuna ricorsione) con:
      - MRV (Minimum Remaining Values): ad ogni passo sceglie la cella con
        meno valori ammissibili, riducendo drasticamente lo spazio di ricerca.
      - Forward checking: dopo ogni assegnazione aggiorna il dominio dei peer
        e fa backtrack immediato se una cella rimane senza candidati.
      - Bitmask per i domini: operazioni su insiemi in O(1).
      - Snapshot del dominio: ripristino O(celle vuote) al backtrack.

    time_limit: se fornito (secondi), il check si interrompe e ritorna None
    quando il budget e' esaurito. Il chiamante interpreta None come
    "incerto -> non rimuovere la cella" (approccio conservativo).

    Usata internamente da _check_unique quando n == 16.
    """
    box = int(n ** 0.5)
    full = (1 << n) - 1  # bitmask con tutti n bit a 1

    def bi(r: int, c: int) -> int:
        return (r // box) * box + (c // box)

    # Peers: per ogni cella, insieme delle celle nella stessa riga/col/box
    peers: dict = {}
    for r in range(n):
        for c in range(n):
            s: set = set()
            for c2 in range(n):
                if c2 != c: s.add((r, c2))
            for r2 in range(n):
                if r2 != r: s.add((r2, c))
            br, bc = (r // box) * box, (c // box) * box
            for dr in range(box):
                for dc in range(box):
                    r2, c2 = br + dr, bc + dc
                    if (r2, c2) != (r, c): s.add((r2, c2))
            peers[(r, c)] = s

    work = [row[:] for row in grid]
    rows_used = [0] * n
    cols_used = [0] * n
    boxes_used = [0] * n

    for r in range(n):
        for c in range(n):
            v = work[r][c]
            if v != 0:
                bit = 1 << (v - 1)
                rows_used[r] |= bit
                cols_used[c] |= bit
                boxes_used[bi(r, c)] |= bit

    # domain[r][c] = bitmask dei valori ancora ammissibili per la cella
    domain = [[0] * n for _ in range(n)]
    for r in range(n):
        for c in range(n):
            if work[r][c] == 0:
                domain[r][c] = full & ~(rows_used[r] | cols_used[c] | boxes_used[bi(r, c)])

    # Insieme mutabile delle celle ancora vuote
    empty_set: set = {(r, c) for r in range(n) for c in range(n) if work[r][c] == 0}

    def pick_mrv() -> Tuple[Optional[Tuple[int, int]], int]:
        best = None
        best_free = n + 2
        for (r, c) in empty_set:
            free = bin(domain[r][c]).count('1')
            if free < best_free:
                best_free = free
                best = (r, c)
                if best_free == 0:
                    break
        return best, best_free

    def bitmask_to_values(mask: int) -> List[int]:
        vals = []
        tmp = mask
        while tmp:
            lsb = tmp & (-tmp)
            vals.append(lsb.bit_length())
            tmp ^= lsb
        return vals

    def assign(r: int, c: int, v: int) -> bool:
        """Assegna v a (r,c), propaga forward checking. False = dead-end."""
        bit = 1 << (v - 1)
        work[r][c] = v
        rows_used[r] |= bit
        cols_used[c] |= bit
        boxes_used[bi(r, c)] |= bit
        empty_set.discard((r, c))
        for (r2, c2) in peers[(r, c)]:
            if (r2, c2) in empty_set:
                domain[r2][c2] &= ~bit
                if domain[r2][c2] == 0:
                    return False
        return True

    def unassign(r: int, c: int, dom_snap: dict,
                 rows_snap: List[int], cols_snap: List[int], boxes_snap: List[int]) -> None:
        """Ripristina lo stato completo prima dell'assegnazione."""
        work[r][c] = 0
        rows_used[:] = rows_snap
        cols_used[:] = cols_snap
        boxes_used[:] = boxes_snap
        empty_set.add((r, c))
        for (r2, c2), d in dom_snap.items():
            domain[r2][c2] = d

    solutions = [0]
    deadline: Optional[float] = (
        _time.monotonic() + time_limit if time_limit is not None else None
    )
    _iter = 0  # contatore per throttle del check di scadenza

    # Stack: ogni frame = [r, c, cands, ci, dom_snap, rows_snap, cols_snap, boxes_snap]
    #   r, c       = cella scelta con MRV
    #   cands      = lista valori candidati al momento della scelta
    #   ci         = indice del prossimo valore da provare
    #   *_snap     = snapshot dello stato per il ripristino
    stack: list = []

    def push_frame() -> bool:
        """Sceglie la prossima cella MRV e crea un frame. False = dead-end."""
        cell, free = pick_mrv()
        if cell is None or free == 0:
            return False
        r, c = cell
        cands = bitmask_to_values(domain[r][c])
        dom_snap = {(r2, c2): domain[r2][c2] for (r2, c2) in empty_set}
        stack.append([r, c, cands, 0,
                      dom_snap,
                      rows_used[:], cols_used[:], boxes_used[:]])
        return True

    if not push_frame():
        return False

    while stack:
        # Controllo scadenza ogni 8192 iterazioni per limitare overhead
        _iter += 1
        if deadline is not None and (_iter & 0x1FFF) == 0:
            if _time.monotonic() > deadline:
                return None  # budget esaurito: risultato ignoto

        frame = stack[-1]
        r, c, cands, ci, dom_snap, rows_snap, cols_snap, boxes_snap = frame

        # Ripristina se c'era un'assegnazione precedente su questo frame
        if work[r][c] != 0:
            unassign(r, c, dom_snap, rows_snap, cols_snap, boxes_snap)

        if ci >= len(cands):
            stack.pop()
            continue

        v = cands[ci]
        frame[3] += 1  # avanza indice candidati

        ok = assign(r, c, v)
        if not ok:
            # Dead-end: ripristina e prova il valore successivo
            unassign(r, c, dom_snap, rows_snap, cols_snap, boxes_snap)
            continue

        if not empty_set:
            # Soluzione trovata
            solutions[0] += 1
            if solutions[0] >= 2:
                return False  # non unica, interrompi
            unassign(r, c, dom_snap, rows_snap, cols_snap, boxes_snap)
        else:
            if not push_frame():
                # Dead-end al livello successivo
                unassign(r, c, dom_snap, rows_snap, cols_snap, boxes_snap)

    return solutions[0] == 1


# ── Generazione soluzione completa — metodo Z3 (originale) ───────────────────

def generate_full_solution(n: int, seed: Optional[int] = None) -> List[List[int]]:
    """
    Genera una soluzione completa valida random per un Sudoku NxN tramite Z3.

    Strategia: ancora la prima riga con una permutazione casuale di 1..n e
    lascia a Z3 il completamento. Garantisce:
      - validita' per i box (Z3 forza i vincoli)
      - diversita' tra seed diversi (prima riga diversa -> soluzione diversa)
      - riproducibilita' con lo stesso seed

    Metodo originale: usato per n=4 e n=9.
    Per n=16 usare generate_full_solution_backtracking (molto piu' veloce).
    """
    if seed is not None:
        random.seed(seed)

    digits = list(range(1, n + 1))
    random.shuffle(digits)

    s, X = build_sudoku_model(n)
    for c, v in enumerate(digits):
        s.add(X[0][c] == v)

    assert s.check() == sat
    return model_to_grid(s.model(), X)


# ── Generazione soluzione completa — metodo backtracking (alternativo) ────────

def generate_full_solution_backtracking(n: int, seed: Optional[int] = None) -> List[List[int]]:
    """
    Genera una soluzione completa valida random per un Sudoku NxN tramite
    backtracking Python con euristica MRV (Minimum Remaining Values).

    Metodo alternativo a generate_full_solution (che usa Z3): progettato
    per n=16 dove Z3 impiega minuti per la sola generazione, mentre questo
    termina in < 1 secondo.

    Algoritmo:
      - Ad ogni passo sceglie la cella vuota con il minor numero di valori
        ammissibili (MRV), riducendo drasticamente i backtrack necessari.
      - I valori vengono provati in ordine casuale (controllato dal seed)
        per garantire diversita' e riproducibilita'.
      - Mantiene set incrementali per righe, colonne e box: ogni
        assegnazione/rimozione e' O(1).

    Usato automaticamente da generate_puzzle e generate_minimal_puzzle
    quando n == 16.
    """
    if seed is not None:
        random.seed(seed)

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, n * n + 500))

    box = int(n ** 0.5)
    grid = [[0] * n for _ in range(n)]

    rows  = [set() for _ in range(n)]
    cols  = [set() for _ in range(n)]
    boxes = [set() for _ in range(n)]

    def bi(r: int, c: int) -> int:
        return (r // box) * box + (c // box)

    def candidates(r: int, c: int) -> list:
        used = rows[r] | cols[c] | boxes[bi(r, c)]
        vals = [v for v in range(1, n + 1) if v not in used]
        random.shuffle(vals)
        return vals

    # Lista mutabile con swap in-place per MRV (evita copie O(n^2))
    empty = [(r, c) for r in range(n) for c in range(n)]

    def solve(depth: int) -> bool:
        if depth == len(empty):
            return True

        # MRV: cella con meno candidati
        best = depth
        best_n = n + 1
        for i in range(depth, len(empty)):
            r2, c2 = empty[i]
            used_count = len(rows[r2] | cols[c2] | boxes[bi(r2, c2)])
            free = n - used_count
            if free < best_n:
                best_n = free
                best = i
                if best_n == 0:
                    return False

        empty[depth], empty[best] = empty[best], empty[depth]
        r, c = empty[depth]

        for v in candidates(r, c):
            grid[r][c] = v
            rows[r].add(v); cols[c].add(v); boxes[bi(r, c)].add(v)
            if solve(depth + 1):
                return True
            grid[r][c] = 0
            rows[r].discard(v); cols[c].discard(v); boxes[bi(r, c)].discard(v)

        empty[depth], empty[best] = empty[best], empty[depth]
        return False

    try:
        ok = solve(0)
    finally:
        sys.setrecursionlimit(old_limit)

    assert ok, "Backtracking fallito (non dovrebbe mai accadere)"
    return grid


# ── Dispatcher interni ────────────────────────────────────────────────────────

def _pick_solution_method(n: int, seed: Optional[int]) -> List[List[int]]:
    """
    Seleziona automaticamente il metodo di generazione della soluzione:
      - n == 16 -> backtracking Python (generate_full_solution_backtracking)
      - altrimenti -> Z3 (generate_full_solution)
    """
    # Lo stato random e' gia' inizializzato dal chiamante con random.seed(seed).
    # Le funzioni interne NON devono ricevere seed, altrimenti resetterebbero
    # lo stato random a meta' della generazione del puzzle.
    if n == 16:
        return generate_full_solution_backtracking(n, seed=None)
    return generate_full_solution(n, seed=None)


def _check_unique(clues_grid: List[List[int]], n: int,
                  time_limit: Optional[float] = None) -> bool:
    """
    Seleziona automaticamente il metodo di verifica unicita':
      - n == 16 -> backtracking Python (_is_unique_backtracking)
      - altrimenti -> Z3

    time_limit (secondi) viene inoltrato a _is_unique_backtracking per n==16.
    Se il backtracker va in timeout (ritorna None) si considera la cella
    non rimovibile (approccio conservativo: meglio un clue in piu' che un
    puzzle non unico).
    """
    if n == 16:
        result = _is_unique_backtracking(clues_grid, n, time_limit=time_limit)
        return result is True  # None (timeout) o False -> mantieni la cella
    s, X = build_sudoku_model(n)
    add_clues(s, X, clues_grid)
    has_two, _, _2 = has_second_solution(s, X)
    return not has_two


# ── Generatori di puzzle ──────────────────────────────────────────────────────

def generate_minimal_puzzle(n: int, seed: Optional[int] = None) -> Tuple[List[List[int]], List[List[int]]]:
    """
    Rimuove il massimo numero di celle preservando l'unicita' della soluzione.
    Ritorna (puzzle, solution).

    Per n=16 usa backtracking Python sia per la generazione della soluzione
    che per la verifica dell'unicita', rendendo il 16x16 praticabile.
    Per n=16 applica un time_limit di 3s per check per evitare tempi di
    generazione eccessivi: le celle con check troppo lenti vengono mantenute.
    """
    if seed is not None:
        random.seed(seed)

    solution = _pick_solution_method(n, seed)
    puzzle = [row[:] for row in solution]

    cells = [(r, c) for r in range(n) for c in range(n)]
    random.shuffle(cells)

    time_limit = 3.0 if n == 16 else None

    for r, c in cells:
        backup = puzzle[r][c]
        puzzle[r][c] = 0
        if not _check_unique(puzzle, n, time_limit=time_limit):
            puzzle[r][c] = backup

    return puzzle, solution


def generate_puzzle(n: int, seed: Optional[int] = None, difficulty: str = "medium") -> Tuple[List[List[int]], List[List[int]]]:
    """
    Genera un puzzle Sudoku NxN con difficolta' specificata.

    Difficolta' per n <= 9:
      - "easy"   -> ~55% celle visibili
      - "medium" -> ~35% celle visibili
      - "hard"   -> algoritmo minimal

    Difficolta' per n == 16:
      Il check di unicita' scala esponenzialmente con le celle vuote.
      Per mantenere tempi di generazione ragionevoli si usano percentuali
      piu' alte e un time_limit per check:
      - "easy"   -> ~55% celle visibili (140 clue), nessun limite
      - "medium" -> ~47% celle visibili (~120 clue), 1s per check
      - "hard"   -> algoritmo minimal con 3s per check (~112-115 clue)

    Per n=16 la verifica dell'unicita' usa backtracking Python invece di Z3.
    """
    if seed is not None:
        random.seed(seed)

    if difficulty == "hard" and n != 16:
        # Per n <= 9 il minimal e' rapido con Z3; per n==16 si usa il
        # approccio a target per evitare tempi di generazione eccessivi.
        # Lo stato random e' gia' inizializzato sopra con random.seed(seed).
        return generate_minimal_puzzle(n, seed=None)

    solution = _pick_solution_method(n, seed)
    puzzle = [row[:] for row in solution]

    if n == 16:
        # Per 16x16 il check di unicita' scala esponenzialmente.
        # Usiamo percentuali piu' alte e un time_limit per check:
        #   easy   -> 55% (~140 clue), nessun limite      (<  5s)
        #   medium -> 47% (~120 clue), 0.5s per check     (< 30s)
        #   hard   -> 43% (~110 clue), 0.5s per check     (< 60s)
        _pct = {"easy": 0.55, "medium": 0.47, "hard": 0.43}
        target_pct = _pct[difficulty]
        time_limit = None if difficulty == "easy" else 0.5
    else:
        target_pct = 0.55 if difficulty == "easy" else 0.35
        time_limit = None

    target_clues = int(n * n * target_pct)
    max_remove = n * n - target_clues

    positions = [(r, c) for r in range(n) for c in range(n)]
    random.shuffle(positions)

    removed = 0
    for r, c in positions:
        if removed >= max_remove:
            break

        backup = puzzle[r][c]
        puzzle[r][c] = 0

        if _check_unique(puzzle, n, time_limit=time_limit):
            removed += 1
        else:
            puzzle[r][c] = backup

    return puzzle, solution
