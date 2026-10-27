import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clientes import nif_valido


def gerar_nif_sintetico():
    """Gera um identificador sintético para testar apenas o algoritmo de checksum."""
    for base in range(10_000_000, 10_000_100):
        soma = sum(int(base_txt) * (9 - indice)
                   for indice, base_txt in enumerate(str(base)))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        candidato = f"{base}{digito}"
        if nif_valido(candidato):
            return candidato
    raise AssertionError("Não foi possível gerar um NIF sintético de teste.")


class TestValidacaoNIF(unittest.TestCase):
    def test_aceita_numero_com_checksum_correto(self):
        self.assertTrue(nif_valido(gerar_nif_sintetico()))

    def test_rejeita_numero_com_digito_de_controle_alterado(self):
        valido = gerar_nif_sintetico()
        ultimo = (int(valido[-1]) + 1) % 10
        self.assertFalse(nif_valido(valido[:-1] + str(ultimo)))

    def test_rejeita_comprimento_incorreto(self):
        self.assertFalse(nif_valido("12345678"))
        self.assertFalse(nif_valido("1234567890"))

    def test_rejeita_letras(self):
        self.assertFalse(nif_valido("12345678A"))


if __name__ == "__main__":
    unittest.main()
