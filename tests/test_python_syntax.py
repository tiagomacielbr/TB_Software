import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "interface_clientes.py",
    ROOT / "banco.py",
    ROOT / "clientes.py",
)


class TestSintaxePython(unittest.TestCase):
    def test_fontes_ativas_sao_sintaticamente_validas(self):
        for source in SOURCES:
            with self.subTest(ficheiro=source.name):
                ast.parse(source.read_text(encoding="utf-8"), filename=str(source))


if __name__ == "__main__":
    unittest.main()
