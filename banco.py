"""Acesso e inicialização da base de dados do TB Software.

Em desenvolvimento, a base de dados fica junto aos módulos Python (e é ignorada
pelo Git). Num executável Windows, fica no perfil do utilizador, em LocalAppData.
Pode definir TB_SOFTWARE_DB_PATH para usar um caminho explícito, sobretudo em testes.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
from pathlib import Path

NOME_BANCO = "banco.db"
VALORES_CONFIGURACAO_PADRAO = {
    "nome_empresa": "TB Software",
    "slogan_empresa": "Soluções que facilitam seu trabalho",
}


def obter_caminho_banco() -> Path:
    """Devolve o caminho estável do SQLite, sem depender da pasta de execução."""
    personalizado = os.environ.get("TB_SOFTWARE_DB_PATH", "").strip()
    if personalizado:
        return Path(personalizado).expanduser().resolve()

    if getattr(sys, "frozen", False):
        base_local = os.environ.get("LOCALAPPDATA")
        pasta_dados = Path(base_local) if base_local else Path.home() / "AppData" / "Local"
        return (pasta_dados / "TB Software" / NOME_BANCO).resolve()

    return (Path(__file__).resolve().parent / NOME_BANCO).resolve()


def criar_hash_senha(senha):
    """Compatibilidade com ferramentas antigas; a aplicação atual usa PBKDF2."""
    return hashlib.sha256(str(senha).encode("utf-8")).hexdigest()


def inicializar_banco():
    """Cria as tabelas mínimas se necessário, sem criar contas ou senhas padrão."""
    caminho = obter_caminho_banco()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = None
    try:
        conexao = sqlite3.connect(str(caminho), timeout=10)
        _configurar_conexao(conexao)
        cursor = conexao.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                nif TEXT,
                endereco TEXT NOT NULL DEFAULT '',
                telefone TEXT NOT NULL DEFAULT '',
                cidade TEXT NOT NULL DEFAULT ''
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                codigo_recuperacao TEXT,
                codigo_recuperacao_criado_em TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracoes_app (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )
        """)
        for chave, valor in VALORES_CONFIGURACAO_PADRAO.items():
            cursor.execute(
                "INSERT OR IGNORE INTO configuracoes_app (chave, valor) VALUES (?, ?)",
                (chave, valor),
            )
        conexao.commit()
        return caminho
    except sqlite3.Error:
        if conexao:
            conexao.rollback()
        raise
    finally:
        if conexao:
            conexao.close()


def criar_banco():
    """Alias mantido para compatibilidade com código legado."""
    return inicializar_banco()


def _configurar_conexao(conexao):
    """Aplica opções seguras e previsíveis a cada ligação SQLite."""
    conexao.execute("PRAGMA busy_timeout = 10000")
    conexao.execute("PRAGMA foreign_keys = ON")
    # Não ativamos WAL: em desenvolvimento a base pode estar dentro do OneDrive,
    # e o modo WAL cria ficheiros auxiliares que podem ser sincronizados separadamente.
    conexao.execute("PRAGMA synchronous = NORMAL")


def conectar_banco():
    """Abre a base de dados configurada; não cria utilizadores automaticamente."""
    try:
        caminho = obter_caminho_banco()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(str(caminho), timeout=10)
        _configurar_conexao(conexao)
        return conexao, conexao.cursor()
    except sqlite3.Error as erro:
        print(f"Erro ao conectar ao banco de dados: {erro}")
        return None, None


def carregar_configuracoes_empresa():
    """Lê nome e slogan persistidos, usando valores padrão quando faltam."""
    resultado = dict(VALORES_CONFIGURACAO_PADRAO)
    conexao = None
    try:
        conexao, cursor = conectar_banco()
        if conexao is None:
            return resultado
        cursor.execute("SELECT chave, valor FROM configuracoes_app")
        for chave, valor in cursor.fetchall():
            if chave in resultado and str(valor or "").strip():
                resultado[chave] = str(valor).strip()
    except sqlite3.Error as erro:
        print(f"Não foi possível carregar as configurações da empresa: {erro}")
    finally:
        if conexao:
            conexao.close()
    return resultado


def guardar_configuracoes_empresa(nome, slogan, cursor=None):
    """Guarda nome e slogan. Aceita um cursor para participar numa transação externa."""
    nome = str(nome or "").strip()
    slogan = str(slogan or "").strip()
    if not nome or not slogan:
        raise ValueError("Nome da empresa e slogan não podem ficar vazios.")

    def gravar(cur):
        cur.executemany(
            """INSERT INTO configuracoes_app (chave, valor) VALUES (?, ?)
               ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor""",
            (("nome_empresa", nome), ("slogan_empresa", slogan)),
        )

    if cursor is not None:
        gravar(cursor)
        return

    conexao = None
    try:
        conexao, cur = conectar_banco()
        if conexao is None:
            raise sqlite3.OperationalError("Não foi possível conectar ao banco de dados.")
        gravar(cur)
        conexao.commit()
    except Exception:
        if conexao:
            conexao.rollback()
        raise
    finally:
        if conexao:
            conexao.close()


def confirmar_operacao(mensagem):
    """Função legada usada pelo módulo de consola clientes.py."""
    while True:
        resposta = input(f"{mensagem} [s/n] ").strip().lower()
        if resposta == "s":
            return True
        if resposta == "n":
            return False
        print("Digite somente s ou n.")
