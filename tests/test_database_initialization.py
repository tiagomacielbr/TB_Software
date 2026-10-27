import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import banco


class TestInicializacaoBanco(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "teste" / "tb_test.db"
        self.env_patch = patch.dict(os.environ, {"TB_SOFTWARE_DB_PATH": str(self.db_path)})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_cria_tabelas_base_sem_utilizador_ou_senha_padrao(self):
        caminho = banco.inicializar_banco()
        self.assertEqual(caminho, self.db_path.resolve())
        con, cur = banco.conectar_banco()
        self.addCleanup(con.close)
        tabelas = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"clientes", "usuarios", "configuracoes_app"}.issubset(tabelas))
        self.assertEqual(cur.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0], 0)

    def test_criar_banco_pode_ser_chamado_mais_de_uma_vez_sem_apagar_dados(self):
        banco.inicializar_banco()
        con, cur = banco.conectar_banco()
        cur.execute("INSERT INTO clientes (nome, nif, endereco, telefone, cidade) VALUES (?, ?, ?, ?, ?)",
                    ("Cliente Teste", "", "Rua Teste", "910000000", "Porto"))
        con.commit()
        con.close()
        banco.inicializar_banco()
        con, cur = banco.conectar_banco()
        self.addCleanup(con.close)
        self.assertEqual(cur.execute("SELECT nome FROM clientes").fetchone()[0], "Cliente Teste")

    def test_nome_e_slogan_ficam_guardados(self):
        banco.inicializar_banco()
        banco.guardar_configuracoes_empresa("Empresa de Teste", "Slogan de Teste")
        valores = banco.carregar_configuracoes_empresa()
        self.assertEqual(valores["nome_empresa"], "Empresa de Teste")
        self.assertEqual(valores["slogan_empresa"], "Slogan de Teste")

    def test_configuracao_rejeita_valores_vazios(self):
        banco.inicializar_banco()
        with self.assertRaises(ValueError):
            banco.guardar_configuracoes_empresa("", "Slogan")


if __name__ == "__main__":
    unittest.main()
