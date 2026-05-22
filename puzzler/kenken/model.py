from __future__ import annotations

import itertools
import random
from functools import reduce
from operator import mul
from typing import *

from z3 import *

from puzzler.core import create_int_grid, model_to_grid, has_second_solution


CageOp = Literal['+', '*', '-', '/']
Cage = Dict[str, Any]

# ── Costanti configurazione ───────────────────────────────────────────────────

_DIRECTIONS = [(0, 1), (1, 0), (0, -1), (-1, 0)]


# ── Modello Z3 ────────────────────────────────────────────────────────────────

def build_kenken_model(n: int, cages: List[Cage]) -> Tuple[Solver, List[List]]:
    """
    Crea modello Z3 per KenKen NxN con gabbie specificate.

    Cage format:
        {
            "op":     "+" | "*" | "-" | "/" | "1",
            "target": int,
            "cells":  [(r, c), ...]   # devono formare un polinomio connesso
        }
    """
    X, domain_c = create_int_grid("k", n, 1, n)
    s = Solver()
    s.add(*domain_c)

    # Latin-square: righe e colonne tutte distinte
    for r in range(n):
        s.add(Distinct(X[r]))
    for c in range(n):
        s.add(Distinct([X[r][c] for r in range(n)]))

    # Vincoli gabbie
    for cage in cages:
        op     = cage["op"]
        target = cage["target"]
        cells  = cage["cells"]

        if op == "1":
            assert len(cells) == 1, "Singleton: esattamente 1 cella"
            r, c = cells[0]
            s.add(X[r][c] == target)

        elif op == "+":
            s.add(sum(X[r][c] for r, c in cells) == target)

        elif op == "*":
            # Enumerazione dei k-tuple ordinati validi: evita moltiplicazione
            # non-lineare in Z3 (molto più lento di aritmetica lineare).
            cell_vars = [X[r][c] for r, c in cells]
            k = len(cells)
            tuples = [
                combo
                for combo in itertools.product(range(1, n + 1), repeat=k)
                if reduce(mul, combo, 1) == target
            ]
            if tuples:
                s.add(Or([
                    And([v == t for v, t in zip(cell_vars, combo)])
                    for combo in tuples
                ]))
            else:
                s.add(BoolVal(False))

        elif op == "-":
            assert len(cells) == 2, "Sottrazione: esattamente 2 celle"
            (r1, c1), (r2, c2) = cells
            s.add(Or(
                X[r1][c1] - X[r2][c2] == target,
                X[r2][c2] - X[r1][c1] == target,
            ))

        elif op == "/":
            assert len(cells) == 2, "Divisione: esattamente 2 celle"
            (r1, c1), (r2, c2) = cells
            a, b = X[r1][c1], X[r2][c2]
            s.add(Or(a == target * b, b == target * a))

        else:
            raise ValueError(f"Operazione non supportata: {op!r}")

    return s, X


# ── Clue per KenKen ───────────────────────────────────────────────────────────

def _add_kenken_clues(s: Solver, X, clues_grid: List[List[int]]) -> None:
    """
    Aggiunge vincoli di cella fissa al solver KenKen.
    0 = cella vuota (ignorata).
    """
    n = len(X)
    for r in range(n):
        for c in range(n):
            v = clues_grid[r][c]
            if v != 0:
                s.add(X[r][c] == v)


# ── Solvers pubblici ──────────────────────────────────────────────────────────

def solve_kenken(n: int, cages: List[Cage]) -> Optional[List[List[int]]]:
    """Risolve KenKen dato n e lista gabbie. Ritorna None se UNSAT."""
    s, X = build_kenken_model(n, cages)
    if s.check() != sat:
        return None
    return model_to_grid(s.model(), X)


def solve_kenken_with_clues(
    n: int,
    cages: List[Cage],
    clues_grid: Optional[List[List[int]]] = None,
) -> Optional[List[List[int]]]:
    """Come solve_kenken ma accetta anche indizi iniziali (griglia parziale)."""
    s, X = build_kenken_model(n, cages)
    if clues_grid:
        _add_kenken_clues(s, X, clues_grid)
    if s.check() != sat:
        return None
    return model_to_grid(s.model(), X)


# ── Generazione soluzione randomizzata ─────────────────────────────────

def generate_full_kenken_solution(n: int, seed: Optional[int] = None) -> List[List[int]]:
    """
    Genera un latin-square NxN randomizzato.

    Per n < 9 usa Z3: ancora la prima riga con una permutazione random e
    lascia a Z3 il completamento (sat garantito per qualsiasi prima riga).

    Per n >= 9 usa un approccio O(n²) senza solver: quadrato ciclico
    L[i][j]=(i+j)%n+1 con permutazioni casuali di righe, colonne e simboli.
    Z3 diventa troppo lento (>20s) per generare latin-square 9x9.
    """
    if seed is not None:
        random.seed(seed)

    if n < 9:
        # Z3-based: randomizza la prima riga e lascia completare il solver
        digits = list(range(1, n + 1))
        random.shuffle(digits)
        s, X = build_kenken_model(n, [])
        for c, v in enumerate(digits):
            s.add(X[0][c] == v)
        assert s.check() == sat
        return model_to_grid(s.model(), X)

    # Cyclic+permutation: O(n²), nessun backtracking
    grid = [[(i + j) % n + 1 for j in range(n)] for i in range(n)]
    rows = list(range(n))
    random.shuffle(rows)
    grid = [grid[r] for r in rows]
    cols = list(range(n))
    random.shuffle(cols)
    grid = [[row[c] for c in cols] for row in grid]
    perm = list(range(1, n + 1))
    random.shuffle(perm)
    sym = {i + 1: perm[i] for i in range(n)}
    return [[sym[v] for v in row] for row in grid]


# ── Partizionamento BFS con garanzia di connettività ──────────────────

def _partition_into_cages(n: int, solution: List[List[int]], max_cage_size: int, singleton_rate: float) -> List[Cage]:
    """
    Partiziona la griglia in gabbie connesse tramite BFS random.
    Ogni cella viene accettata solo se adiacente all'insieme già costruito,
    garantendo connettività del polinomio. (controllo esplicito con
    `_is_adjacent_to_set`).
    """
    unassigned: set = {(r, c) for r in range(n) for c in range(n)}
    cages: List[Cage] = []

    while unassigned:
        start = random.choice(sorted(unassigned))   # sorted per riproducibilità
        unassigned.remove(start)

        if random.random() < singleton_rate:
            cage_cells = [start]
        else:
            cage_cells = [start]
            cage_set   = {start}
            # Frontier iniziale: vicini del seed
            frontier = list(unassigned & _neighbors(start, n))
            random.shuffle(frontier)

            while frontier and len(cage_cells) < max_cage_size:
                cell = frontier.pop()
                # ── connettività ────────────────────────────────────────
                if cell not in unassigned:
                    continue
                if not _is_adjacent_to_set(cell, cage_set, n):
                    # la cella non è più adiacente alla gabbia in crescita
                    continue
                # ────────────────────────────────────────────────────────────

                cage_cells.append(cell)
                cage_set.add(cell)
                unassigned.remove(cell)

                new_nb = list(unassigned & _neighbors(cell, n))
                random.shuffle(new_nb)
                frontier.extend(new_nb)

        cages.append(_make_cage(cage_cells, solution, n))

    return cages



def _make_cage(cells: List[Tuple[int, int]], solution: List[List[int]], n: int) -> Cage:
    """
    Sceglie operazione e target per una gabbia dati i valori della soluzione.

    Operatore scelto casualmente tra quelli validi per bilanciare la
    distribuzione su tutte le dimensioni di griglia:
      - 1 cella  → singleton
      - 2 celle  → scelta uniforme tra gli operatori validi (+, -, /)
      - ≥3 celle → scelta 50/50 tra + e * (entrambi sempre validi)

    Vincoli di validità:
      - /  richiede quoziente intero ≥ 2
      - -  richiede valori distinti (diff > 0)
      - *  prodotto <= n^k per evitare target enormi che rallentano Z3
    """
    values = [solution[r][c] for r, c in cells]

    if len(cells) == 1:
        return {"op": "1", "target": values[0], "cells": cells}

    if len(cells) == 2:
        a, b = sorted(values)
        valid: List[str] = ["+"]
        if b > a:
            valid.append("-")
        if a != 0 and b % a == 0 and b // a >= 2:
            valid.append("/")
        op = random.choice(valid)
        if op == "-":
            return {"op": "-", "target": b - a, "cells": cells}
        if op == "/":
            return {"op": "/", "target": b // a, "cells": cells}
        return {"op": "+", "target": a + b, "cells": cells}

    # 3+ celle: 50/50 tra * e + (evita target enormi con soglia n^k)
    product = reduce(mul, values, 1)
    if product <= n ** len(cells) and random.random() < 0.5:
        return {"op": "*", "target": product, "cells": cells}
    return {"op": "+", "target": sum(values), "cells": cells}


# ── Unicità ───────────────────────────────────────────────────────────────────

def _ensure_unique(
    n: int,
    cages: List[Cage],
    solution: List[List[int]],
) -> List[Cage]:
    """
    Garantisce unicità aggiungendo singleton con solver Z3 incrementale.

    Strategia:
      1. Costruisce il solver UNA VOLTA con i vincoli delle gabbie.
      2. Quando non unico, ottiene la seconda soluzione alternativa.
      3. Sceglie preferibilmente celle dove la seconda soluzione DIFFERISCE
         dalla nostra (ogni pin garantisce di eliminare quella soluzione).
      4. Continua fino all'unicità (Z3 riusa stato interno tra chiamate).
      5. Ricostruisce le gabbie senza duplicati.

    Invariante: ogni cella appartiene esattamente a una gabbia.
    """
    s, X = build_kenken_model(n, cages)
    has_two, _, alt = has_second_solution(s, X)
    if not has_two:
        return cages

    multi_set: set = {
        cell
        for cage in cages
        if len(cage["cells"]) > 1
        for cell in cage["cells"]
    }
    added: List[Tuple[int, int]] = []

    while has_two:
        # Celle multi-cella non ancora pinnate dove alt differisce da solution
        if alt:
            candidates = [
                (r, c) for r, c in multi_set
                if alt[r][c] != solution[r][c]
            ]
        else:
            candidates = list(multi_set)

        if not candidates:
            candidates = list(multi_set)
        if not candidates:
            break

        r, c = random.choice(candidates)
        s.add(X[r][c] == solution[r][c])
        added.append((r, c))
        multi_set.discard((r, c))

        has_two, _, alt = has_second_solution(s, X)

    # Ricostruisce le gabbie: le celle in `added` diventano singleton esplicite;
    # le celle residue di ogni gabbia parzialmente singletonizzata formano
    # nuove gabbie connesse tramite _make_cage (→ nessun duplicato).
    singletonized: set = set(added)
    final_cages: List[Cage] = []

    for cage in cages:
        remaining = [cell for cell in cage["cells"] if cell not in singletonized]
        if len(remaining) == len(cage["cells"]):
            final_cages.append(cage)          # gabbia invariata
        elif remaining:
            for comp in _connected_components(remaining):
                final_cages.append(_make_cage(comp, solution, n))
        # se remaining vuoto: tutta la gabbia è stata singletonizzata → omessa

    for r2, c2 in singletonized:
        final_cages.append({
            "op": "1",
            "target": solution[r2][c2],
            "cells": [(r2, c2)],
        })

    return final_cages


# ── Generatori pubblici ───────────────────────────────────────────────────────

def generate_kenken_puzzle(
    n: int = 4,
    max_cage_size: Optional[int] = None,
    singleton_rate: float = 0.15,
    seed: Optional[int] = None,
) -> Tuple[List[List[int]], List[Cage]]:
    """
    Genera un KenKen NxN con:
      - soluzione diversa ad ogni seed
      - gabbie sempre connesse
      - unicità garantita con intervento minimo

    Parametri
    ---------
    n               : dimensione griglia
    max_cage_size   : dimensione massima gabbia (default: max(2, n // 2))
    singleton_rate  : probabilità di gabbia singleton durante partizionamento
    seed            : seed per riproducibilità
    """
    if max_cage_size is None:
        max_cage_size = max(2, n // 2)

    # Genera la soluzione e inizializza il generatore random con lo stesso seed.
    # generate_full_kenken_solution chiama random.seed(seed) internamente,
    # quindi tutto il resto del codice usa lo stesso stato random.
    solution = generate_full_kenken_solution(n, seed=seed)

    # Partizionamento (usa lo stato random già inizializzato)
    cages = _partition_into_cages(n, solution, max_cage_size, singleton_rate)

    # Garanzia unicità
    cages = _ensure_unique(n, cages, solution)

    all_cells = [cell for cage in cages for cell in cage["cells"]]
    expected = {(r, c) for r in range(n) for c in range(n)}

    assert len(all_cells) == n * n, f"Numero celle errato: {len(all_cells)} != {n*n}"
    assert set(all_cells) == expected, "Le gabbie non coprono esattamente la griglia"

    return solution, cages


def generate_minimal_kenken_puzzle(
    n: int,
    max_cage_size: Optional[int] = None,
    seed: Optional[int] = None,
) -> Tuple[List[List[int]], List[Cage]]:
    """
    Genera un KenKen con il minor numero di gabbie possibile preservando
    l'unicità (difficoltà massima: meno informazione esplicita).

    Strategia:
      1. Parte da n*n singleton (massima informazione).
      2. Prova a fondere coppie adiacenti in ordine casuale.
      3. Accetta la fusione solo se la soluzione resta unica.
      4. Ripete finché nessuna ulteriore fusione è possibile.
    """
    if max_cage_size is None:
        max_cage_size = max(2, n // 2)

    # 1. Soluzione randomizzata
    solution = generate_full_kenken_solution(n, seed=seed)

    # 2. Parti da tutti singleton
    cages: List[Cage] = [
        {"op": "1", "target": solution[r][c], "cells": [(r, c)]}
        for r in range(n)
        for c in range(n)
    ]

    # 3. Fusioni greedy finché possibile
    changed = True
    while changed:
        changed = False
        indices = list(range(len(cages)))
        random.shuffle(indices)

        for i in indices:
            if i >= len(cages):
                continue

            neighbors_j = _find_adjacent_cages(cages, i, n, max_cage_size)
            random.shuffle(neighbors_j)

            for j in neighbors_j:
                merged = _merge_cages(cages[i], cages[j], solution, n)
                candidate = [c for k, c in enumerate(cages) if k != i and k != j] + [merged]

                s, X = build_kenken_model(n, candidate)
                has_two, _, _2 = has_second_solution(s, X)

                if not has_two:
                    cages = candidate
                    changed = True
                    break

            if changed:
                break

    return solution, cages


# ── Helper privati ────────────────────────────────────────────────────────────

def _connected_components(
    cells: List[Tuple[int, int]],
) -> List[List[Tuple[int, int]]]:
    """Restituisce le componenti connesse (4-adiacenza) di un insieme di celle."""
    remaining: set = set(cells)
    components: List[List[Tuple[int, int]]] = []
    while remaining:
        start = next(iter(remaining))
        component: List[Tuple[int, int]] = []
        queue = [start]
        remaining.remove(start)
        while queue:
            r, c = queue.pop()
            component.append((r, c))
            for dr, dc in _DIRECTIONS:
                nb = (r + dr, c + dc)
                if nb in remaining:
                    remaining.remove(nb)
                    queue.append(nb)
        components.append(component)
    return components


def _split_cage_around_cell(
    cage: Cage,
    cell: Tuple[int, int],
    solution: List[List[int]],
    n: int,
) -> List[Cage]:
    """
    Estrae `cell` dalla gabbia creando un singleton e riformando le celle
    residue in una o più gabbie connesse (componenti connesse dei rimanenti).

    Garantisce che ogni cella risultante appartenga esattamente a una gabbia.
    """
    singleton: Cage = {
        "op": "1",
        "target": solution[cell[0]][cell[1]],
        "cells": [cell],
    }
    remaining = [c for c in cage["cells"] if c != cell]
    if not remaining:
        return [singleton]
    components = _connected_components(remaining)
    residual = [_make_cage(comp, solution, n) for comp in components]
    return [singleton] + residual


def _neighbors(cell: Tuple[int, int], n: int) -> set:
    """Vicini validi (dentro griglia) di una cella."""
    r, c = cell
    return {
        (r + dr, c + dc)
        for dr, dc in _DIRECTIONS
        if 0 <= r + dr < n and 0 <= c + dc < n
    }


def _is_adjacent_to_set(cell: Tuple[int, int], cage_set: set, n: int) -> bool:
    """
    Controlla se `cell` è adiacente ad almeno una cella in `cage_set`.
    Usato per garantire connettività del polinomio durante il BFS.
    """
    return bool(_neighbors(cell, n) & cage_set)


def _find_adjacent_cages(
    cages: List[Cage],
    i: int,
    n: int,
    max_cage_size: int,
) -> List[int]:
    """Indici delle gabbie adiacenti a cages[i] con dimensione combinata ≤ max_cage_size."""
    cells_i = set(cages[i]["cells"])
    neighbors_of_i: set = set()
    for r, c in cells_i:
        for dr, dc in _DIRECTIONS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < n and (nr, nc) not in cells_i:
                neighbors_of_i.add((nr, nc))

    return [
        j for j, cage_j in enumerate(cages)
        if j != i
        and len(cages[i]["cells"]) + len(cage_j["cells"]) <= max_cage_size
        and any(cell in neighbors_of_i for cell in cage_j["cells"])
    ]


def _merge_cages(cage_a: Cage, cage_b: Cage, solution: List[List[int]], n: int) -> Cage:
    """Fonde due gabbie ricalcolando operazione e target."""
    return _make_cage(cage_a["cells"] + cage_b["cells"], solution, n)


# ── Stampa ────────────────────────────────────────────────────────────────────

def print_kenken_puzzle(solution: List[List[int]], cages: List[Cage], show_solution: bool = True, compact: bool = False) -> None:
    """
    Stampa KenKen ASCII con target nella prima cella di ogni gabbia.
    """
    n = len(solution)
    puzzle_grid = [["." for _ in range(n)] for _ in range(n)]

    for cage in cages:
        op, target, cells = cage["op"], cage["target"], cage["cells"]
        r0, c0 = cells[0]
        label = f"{target}{op}" if op != "1" else str(target)
        puzzle_grid[r0][c0] = label if not compact else label[-2:]

    print("PUZZLE:")
    for row in puzzle_grid:
        print(" ".join(f"{cell:>4}" for cell in row))

    if show_solution:
        print("\nSOLUZIONE:")
        for row in solution:
            print(" ".join(f"{v:>4}" for v in row))

    print(f"\n{len(cages)} gabbie:")
    for i, cage in enumerate(cages):
        cells_str = ", ".join(f"({r},{c})" for r, c in cage["cells"])
        print(f"  {i:2d}: {cage['target']}{cage['op']:1s} → {cells_str}")

    covered = sum(len(c["cells"]) for c in cages)
    print(f"Copertura: {covered}/{n*n} celle")