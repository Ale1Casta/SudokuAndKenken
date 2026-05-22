from __future__ import annotations

from typing import List, Tuple, Optional

from z3 import Int, Solver, ModelRef, And, Or, sat


def create_int_grid(name: str, n: int, lo: int, hi: int):
    """
    Crea una griglia n x n di variabili Int di Z3 con dominio [lo, hi].
    Ritorna (X, constraints) dove:
      - X è una lista di liste di variabili
      - constraints è una lista di vincoli di dominio
    """
    X = [[Int(f"{name}_{r}_{c}") for c in range(n)] for r in range(n)]
    domain_constraints = [
        And(X[r][c] >= lo, X[r][c] <= hi)
        for r in range(n)
        for c in range(n)
    ]
    return X, domain_constraints


def model_to_grid(model: ModelRef, X) -> List[List[int]]:
    """Trasforma un modello Z3 in una griglia di int Python."""
    n = len(X)
    return [[model.evaluate(X[r][c]).as_long() for c in range(n)] for r in range(n)]


def has_second_solution(
    s: Solver,  # <-- accetta Solver già pronto con vincoli
    X,
) -> Tuple[bool, Optional[List[List[int]]], Optional[List[List[int]]]]:
    """
    Dato un Solver già configurato con i vincoli del puzzle, verifica se
    esiste una seconda soluzione diversa dalla prima.

    Ritorna (has_two, first_grid, second_grid):
      - has_two=True  → soluzione NON unica
      - has_two=False → soluzione unica (o UNSAT)
      - first_grid    → prima soluzione trovata, None se UNSAT
      - second_grid   → seconda soluzione, None se unica o UNSAT

    Usa push/pop per non modificare permanentemente il solver.
    """
    if s.check() != sat:
        return False, None, None

    m1 = s.model()
    first = model_to_grid(m1, X)

    # vincolo: almeno una cella diversa dalla prima soluzione
    n = len(X)
    diff_clause = Or([
        X[r][c] != m1.evaluate(X[r][c])
        for r in range(n)
        for c in range(n)
    ])

    s.push()
    s.add(diff_clause)
    has_two = s.check() == sat
    second = model_to_grid(s.model(), X) if has_two else None
    s.pop()

    return has_two, first, second

