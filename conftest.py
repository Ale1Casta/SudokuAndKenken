"""
conftest.py — configurazione globale pytest.

Aggiunge la ROOT del progetto a sys.path in modo che gli import assoluti
funzionino correttamente sia con `pytest` dalla root sia da sottodirectory.

Pacchetti disponibili dopo l'aggiunta al path:
  puzzler.core            — utilità Z3 condivise (create_int_grid, has_second_solution, …)
  puzzler.sudoku          — Sudoku classico 4x4 / 9x9 / 16x16
  puzzler.kenken          — KenKen nxn
  puzzler.diagonal        — Diagonal Sudoku (variante: +2 Distinct sulle diagonali)
  puzzler.hyper           — Hyper Sudoku   (variante: +4 Distinct sulle finestre, solo 9x9)
  puzzler.nonconsecutive  — Nonconsecutive Sudoku (variante: |a-b|≠1 per celle adiacenti, solo 9x9)
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
