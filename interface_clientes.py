
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import sqlite3
import hashlib
import hmac
import secrets
import csv
import os
import sys
import zipfile
import ctypes
from ctypes import wintypes
import re
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

import clientes
from banco import (
    conectar_banco, inicializar_banco, carregar_configuracoes_empresa,
    guardar_configuracoes_empresa,
)


# ============================================================
#     REUTILIZAÇÃO DE JANELAS JÁ ABERTAS
# ============================================================
_JANELAS_ABERTAS = {}
ATUALIZAR_DASHBOARD_CALLBACK = None
USUARIO_AUDITORIA_ATUAL = None
PBKDF2_ITERACOES = 260_000

# Ícones usados no menu lateral.
# Os ficheiros ficam em assets/icones_menu.
MENU_ICONES_PASTA = "icones_menu"
MENU_ICONE_LARGURA = 22
MENU_ICONE_ALTURA = 22

MENU_ICONES = {
    "inicio": "inicio.png",
    "relatorios": "relatorios.png",
    "lembretes": "lembretes.png",
    "utilizadores": "utilizadores.png",
    "dados_seguranca": "dados_seguranca.png",
    "configuracoes": "configuracoes.png",
    "trocar_utilizador": "trocar_utilizador.png",
    "sair": "sair.png",
}

_AVISO_LEMBRETES_TABELA = None


def criar_hash_senha(senha, iteracoes=PBKDF2_ITERACOES):
    """Cria um hash de senha PBKDF2 com salt aleatório."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(senha).encode("utf-8"), salt, int(iteracoes))
    return f"pbkdf2_sha256${int(iteracoes)}${salt.hex()}${digest.hex()}"



def criar_hash_codigo_recuperacao(codigo):
    """Cria um hash PBKDF2 para o código de recuperação."""
    return criar_hash_senha(codigo)


def gerar_codigo_recuperacao():
    """Gera um código de recuperação curto, legível e de uso único."""
    partes = [secrets.token_hex(3).upper(), secrets.token_hex(3).upper()]
    return "-".join(partes)


def garantir_campos_recuperacao():
    """Adiciona os campos de recuperação a bases existentes sem apagar dados."""
    con = None
    try:
        con, cur = conectar_banco()
        if con is None:
            return
        cur.execute("PRAGMA table_info(usuarios)")
        colunas = {linha[1] for linha in cur.fetchall()}
        if "codigo_recuperacao" not in colunas:
            cur.execute("ALTER TABLE usuarios ADD COLUMN codigo_recuperacao TEXT")
        if "codigo_recuperacao_criado_em" not in colunas:
            cur.execute("ALTER TABLE usuarios ADD COLUMN codigo_recuperacao_criado_em TEXT")
        con.commit()
    except sqlite3.Error as erro:
        if con:
            con.rollback()
        print(f"Aviso: não foi possível preparar a recuperação de senha: {erro}")
    finally:
        if con:
            con.close()


def configurar_codigo_recuperacao(usuario_logado, parent):
    """Permite ao utilizador autenticado criar um novo código de recuperação."""
    janela = tk.Toplevel(parent)
    aplicar_icone_janela(janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Código de recuperação")
    janela.geometry("480x430")
    centralizar_janela_na_area_util(janela, 480, 430)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)
    janela.transient(parent)
    janela.grab_set()

    tk.Label(janela, text="CÓDIGO DE RECUPERAÇÃO", font=FONTE_15_NEGRITO,
             bg=COR_FUNDO, fg=COR_PRINCIPAL).pack(pady=(20, 8))
    tk.Label(janela,
             text="Confirme a sua senha para gerar um novo código.\nGuarde-o num local seguro. O código anterior será invalidado.",
             font=FONTE_9, bg=COR_FUNDO, fg=COR_SECUNDARIA,
             justify="center").pack(padx=25, pady=(0, 15))

    quadro = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro.pack(fill="x", padx=28, pady=5)
    tk.Label(quadro, text="Senha atual:", font=FONTE_9_NEGRITO,
             bg=COR_PAINEL, fg=COR_TEXTO).pack(anchor="w", padx=15, pady=(14, 5))
    entrada = tk.Entry(quadro, font=FONTE_10, show="*", width=35)
    entrada.pack(fill="x", padx=15, pady=(0, 15), ipady=4)

    estado = {"codigo": None}

    def gerar():
        senha = entrada.get()
        if not senha:
            messagebox.showerror("Segurança", "Introduza a sua senha atual.", parent=janela)
            return
        con = None
        try:
            con, cur = conectar_banco()
            cur.execute("SELECT senha, COALESCE(ativo, 1) FROM usuarios WHERE usuario = ?", (usuario_logado,))
            linha = cur.fetchone()
            if not linha or int(linha[1] or 0) != 1:
                raise RuntimeError("A conta não está disponível.")
            ok, _ = verificar_hash_senha(senha, linha[0])
            if not ok:
                messagebox.showerror("Segurança", "A senha atual está incorreta.", parent=janela)
                return
            codigo = gerar_codigo_recuperacao()
            cur.execute("UPDATE usuarios SET codigo_recuperacao = ?, codigo_recuperacao_criado_em = ? WHERE usuario = ?",
                        (criar_hash_codigo_recuperacao(codigo), datetime.now().isoformat(timespec="seconds"), usuario_logado))
            con.commit()
            estado["codigo"] = codigo
        except (sqlite3.Error, RuntimeError) as erro:
            if con:
                con.rollback()
            messagebox.showerror("Segurança", str(erro), parent=janela)
            return
        finally:
            if con:
                con.close()
        janela.destroy()
        mostrar_codigo_recuperacao(parent, codigo)

    tk.Button(janela, text="Gerar novo código", command=gerar,
              font=FONTE_9_NEGRITO, bg=COR_BOTAO, fg="white", relief="flat",
              cursor="hand2", padx=18, pady=7).pack(pady=12)
    tk.Button(janela, text="Cancelar", command=janela.destroy,
              font=FONTE_9_NEGRITO, bg="#e8eef5", fg=COR_TEXTO, relief="flat",
              cursor="hand2", padx=18, pady=7).pack()
    entrada.focus_set()


def mostrar_codigo_recuperacao(parent, codigo):
    """Mostra o código uma vez e permite copiá-lo para a área de transferência."""
    janela = tk.Toplevel(parent)
    aplicar_icone_janela(janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Código de recuperação")
    janela.geometry("480x300")
    centralizar_janela_na_area_util(janela, 480, 300)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)
    janela.transient(parent)
    janela.grab_set()

    tk.Label(janela, text="SEU CÓDIGO DE RECUPERAÇÃO", font=FONTE_15_NEGRITO,
             bg=COR_FUNDO, fg=COR_PRINCIPAL).pack(pady=(22, 8))
    tk.Label(janela, text="Guarde este código. Ele será usado caso se esqueça da senha.",
             font=FONTE_9, bg=COR_FUNDO, fg=COR_SECUNDARIA).pack(pady=(0, 15))
    campo = tk.Entry(janela, font=("Segoe UI", 18, "bold"), justify="center", width=18)
    campo.insert(0, codigo)
    campo.configure(state="readonly")
    campo.pack(pady=5, ipady=6)

    def copiar():
        janela.clipboard_clear()
        janela.clipboard_append(codigo)
        janela.update()
        messagebox.showinfo("Código", "Código copiado para a área de transferência.", parent=janela)

    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(pady=20)
    tk.Button(botoes, text="Copiar código", command=copiar, font=FONTE_9_NEGRITO,
              bg=COR_BOTAO, fg="white", relief="flat", cursor="hand2", padx=18, pady=7).pack(side="left", padx=5)
    tk.Button(botoes, text="Fechar", command=janela.destroy, font=FONTE_9_NEGRITO,
              bg="#e8eef5", fg=COR_TEXTO, relief="flat", cursor="hand2", padx=18, pady=7).pack(side="left", padx=5)


def recuperar_senha(parent):
    """Redefine a senha usando um código de recuperação de uso único."""
    janela = tk.Toplevel(parent)
    aplicar_icone_janela(janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Recuperar senha")
    janela.geometry("480x520")
    centralizar_janela_na_area_util(janela, 480, 520)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)
    janela.transient(parent)
    janela.grab_set()

    tk.Label(janela, text="RECUPERAR SENHA", font=FONTE_15_NEGRITO,
             bg=COR_FUNDO, fg=COR_PRINCIPAL).pack(pady=(20, 5))
    tk.Label(janela, text="Use o código de recuperação criado anteriormente.", font=FONTE_9,
             bg=COR_FUNDO, fg=COR_SECUNDARIA).pack(pady=(0, 15))

    quadro = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro.pack(fill="x", padx=28, pady=5)
    campos = []
    for texto, segredo in (("Utilizador:", False), ("Código de recuperação:", False), ("Nova senha:", True), ("Confirmar nova senha:", True)):
        tk.Label(quadro, text=texto, font=FONTE_9_NEGRITO, bg=COR_PAINEL, fg=COR_TEXTO).pack(anchor="w", padx=15, pady=(10, 4))
        entrada = tk.Entry(quadro, font=FONTE_10, show="*" if segredo else "", width=35)
        entrada.pack(fill="x", padx=15, pady=(0, 5), ipady=3)
        campos.append(entrada)
    entrada_usuario_rec, entrada_codigo, entrada_nova, entrada_conf = campos

    def confirmar():
        usuario = entrada_usuario_rec.get().strip()
        codigo = entrada_codigo.get().strip().upper()
        nova = entrada_nova.get()
        conf = entrada_conf.get()
        if not usuario or not codigo or not nova or not conf:
            messagebox.showerror("Recuperação", "Preencha todos os campos.", parent=janela)
            return
        if len(nova) < 10:
            messagebox.showerror("Recuperação", "A nova senha deve ter pelo menos 10 caracteres.", parent=janela)
            return
        if nova != conf:
            messagebox.showerror("Recuperação", "As novas senhas não coincidem.", parent=janela)
            return
        con = None
        try:
            con, cur = conectar_banco()
            cur.execute("SELECT codigo_recuperacao, COALESCE(ativo, 1) FROM usuarios WHERE usuario = ?", (usuario,))
            linha = cur.fetchone()
            if not linha or not linha[0] or int(linha[1] or 0) != 1:
                raise RuntimeError("Utilizador ou código de recuperação inválido.")
            valido, _ = verificar_hash_senha(codigo, linha[0])
            if not valido:
                raise RuntimeError("Utilizador ou código de recuperação inválido.")
            cur.execute("UPDATE usuarios SET senha = ?, codigo_recuperacao = NULL, codigo_recuperacao_criado_em = NULL WHERE usuario = ?",
                        (criar_hash_senha(nova), usuario))
            con.commit()
        except (sqlite3.Error, RuntimeError) as erro:
            if con:
                con.rollback()
            messagebox.showerror("Recuperação", str(erro), parent=janela)
            return
        finally:
            if con:
                con.close()
        messagebox.showinfo("Recuperação", "Senha redefinida com sucesso. Pode iniciar sessão.", parent=parent)
        janela.destroy()

    tk.Button(janela, text="Redefinir senha", command=confirmar, font=FONTE_9_NEGRITO,
              bg=COR_BOTAO, fg="white", relief="flat", cursor="hand2", padx=18, pady=7).pack(pady=12)
    tk.Button(janela, text="Cancelar", command=janela.destroy, font=FONTE_9_NEGRITO,
              bg="#e8eef5", fg=COR_TEXTO, relief="flat", cursor="hand2", padx=18, pady=7).pack()
    entrada_usuario_rec.focus_set()

def verificar_hash_senha(senha, hash_guardado):
    """Devolve (válida, hash_legado). Aceita SHA-256 antigo para migração gradual."""
    if not hash_guardado:
        return False, False
    valor = str(hash_guardado).strip()
    if valor.startswith("pbkdf2_sha256$"):
        try:
            algoritmo, iteracoes_txt, salt_hex, digest_hex = valor.split("$", 3)
            iteracoes = int(iteracoes_txt)
            if algoritmo != "pbkdf2_sha256" or not (100_000 <= iteracoes <= 2_000_000):
                return False, False
            salt = bytes.fromhex(salt_hex)
            esperado = bytes.fromhex(digest_hex)
            calculado = hashlib.pbkdf2_hmac("sha256", str(senha).encode("utf-8"), salt, iteracoes)
            return hmac.compare_digest(calculado, esperado), False
        except (ValueError, TypeError):
            return False, False

    # Formato antigo: SHA-256 simples (64 caracteres hexadecimais).
    if re.fullmatch(r"[0-9a-fA-F]{64}", valor):
        legado = hashlib.sha256(str(senha).encode("utf-8")).hexdigest()
        valido = hmac.compare_digest(legado.lower(), valor.lower())
        return valido, valido
    return False, False


def _criar_tabela_auditoria_cursor(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT NOT NULL,
            usuario TEXT NOT NULL,
            acao TEXT NOT NULL,
            cliente_id INTEGER,
            detalhes TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auditoria_data ON auditoria(data_hora)")


def atualizar_tabela_auditoria():
    con = None
    try:
        con, cur = conectar_banco()
        if con is None:
            return
        _criar_tabela_auditoria_cursor(cur)
        con.commit()
    except sqlite3.Error as erro:
        print(f"Não foi possível preparar o histórico de auditoria: {erro}")
    finally:
        if con:
            con.close()


def _inserir_auditoria(cursor, acao, cliente_id=None, detalhes="", usuario=None):
    """Insere auditoria na mesma transação da operação de negócio."""
    _criar_tabela_auditoria_cursor(cursor)
    ator = usuario or USUARIO_AUDITORIA_ATUAL or "Sistema"
    cursor.execute(
        "INSERT INTO auditoria (data_hora, usuario, acao, cliente_id, detalhes) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(ator), str(acao), cliente_id, str(detalhes or "")[:1000])
    )


def registar_auditoria(acao, cliente_id=None, detalhes="", usuario=None):
    """Regista evento sem permitir que uma falha no histórico interrompa a operação principal."""
    con = None
    try:
        con, cur = conectar_banco()
        if con is None:
            return
        _inserir_auditoria(cur, acao, cliente_id, detalhes, usuario)
        con.commit()
    except sqlite3.Error as erro:
        if con:
            try:
                con.rollback()
            except sqlite3.Error:
                pass
        print(f"Não foi possível registar auditoria ({acao}): {erro}")
    finally:
        if con:
            con.close()


def atualizar_tabelas_atendimento_lembretes():
    """Prepara tabelas de atendimento e lembretes e migra datas de cadastro conhecidas."""
    con = None
    try:
        con, cur = conectar_banco()
        if con is None:
            return
        cur.execute("PRAGMA table_info(clientes)")
        colunas_clientes = {str(row[1]).casefold() for row in cur.fetchall()}
        if "data_cadastro" not in colunas_clientes:
            cur.execute("ALTER TABLE clientes ADD COLUMN data_cadastro TEXT")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS historico_atendimento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                data_hora TEXT NOT NULL,
                usuario TEXT NOT NULL,
                tipo TEXT NOT NULL,
                descricao TEXT NOT NULL,
                proximo_contacto TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_atendimento_cliente_data ON historico_atendimento(cliente_id, data_hora)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lembretes_clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                descricao TEXT,
                data_vencimento TEXT NOT NULL,
                hora_vencimento TEXT NOT NULL DEFAULT '09:00',
                status TEXT NOT NULL DEFAULT 'Pendente',
                criado_em TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                concluido_em TEXT,
                ultimo_aviso_em TEXT,
                ultimo_resumo_inicio_em TEXT,
                adiar_ate TEXT
            )
        """)
        cur.execute("PRAGMA table_info(lembretes_clientes)")
        colunas_lembretes = {str(row[1]).casefold() for row in cur.fetchall()}
        novas_colunas_lembrete = {
            "hora_vencimento": "TEXT NOT NULL DEFAULT '09:00'",
            "ultimo_aviso_em": "TEXT",
            "ultimo_resumo_inicio_em": "TEXT",
            "adiar_ate": "TEXT",
        }
        for coluna, definicao in novas_colunas_lembrete.items():
            if coluna not in colunas_lembretes:
                cur.execute(f"ALTER TABLE lembretes_clientes ADD COLUMN {coluna} {definicao}")
        cur.execute("UPDATE lembretes_clientes SET hora_vencimento = '09:00' WHERE hora_vencimento IS NULL OR TRIM(hora_vencimento) = ''")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lembretes_vencimento ON lembretes_clientes(status, data_vencimento, hora_vencimento)")

        # Se o histórico de auditoria já indicar a data de cadastro, preserva-a.
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auditoria'")
        if cur.fetchone():
            cur.execute("""
                UPDATE clientes
                SET data_cadastro = (
                    SELECT substr(a.data_hora, 1, 10)
                    FROM auditoria a
                    WHERE a.cliente_id = clientes.id
                      AND a.acao = 'Cliente cadastrado'
                    ORDER BY a.id ASC LIMIT 1
                )
                WHERE (data_cadastro IS NULL OR TRIM(data_cadastro) = '')
                  AND EXISTS (
                    SELECT 1 FROM auditoria a
                    WHERE a.cliente_id = clientes.id AND a.acao = 'Cliente cadastrado'
                  )
            """)
        con.commit()
    except sqlite3.Error as erro:
        if con:
            try:
                con.rollback()
            except sqlite3.Error:
                pass
        print(f"Não foi possível preparar atendimento/lembretes: {erro}")
    finally:
        if con:
            con.close()


def _normalizar_chave_duplicidade(valor):
    return re.sub(r"\s+", " ", str(valor or "").strip()).casefold()


def _normalizar_digitos_duplicidade(valor):
    return re.sub(r"\D", "", str(valor or ""))


def procurar_possiveis_duplicados(nome, nif, passaporte, telefone, movel, email, pais, ignorar_id=None):
    """Deteta sinais de duplicação sem bloquear automaticamente registos legítimos."""
    resultado = []
    con = None
    nome_n = _normalizar_chave_duplicidade(nome)
    pais_n = _normalizar_chave_duplicidade(pais)
    email_n = _normalizar_chave_duplicidade(email)
    digitos_candidatos = {
        _normalizar_digitos_duplicidade(telefone),
        _normalizar_digitos_duplicidade(movel),
    } - {""}
    nif_n = re.sub(r"[\s.-]", "", str(nif or "")).upper()
    pass_n = re.sub(r"[\s-]", "", str(passaporte or "")).upper()
    try:
        con, cur = conectar_banco()
        if con is None:
            return resultado
        cur.execute("SELECT id, nome, nif, passaporte, telefone, movel, email, pais FROM clientes")
        for cid, c_nome, c_nif, c_pass, c_tel, c_movel, c_email, c_pais in cur.fetchall():
            if ignorar_id is not None and str(cid) == str(ignorar_id):
                continue
            motivos = []
            c_nome_n = _normalizar_chave_duplicidade(c_nome)
            c_pais_n = _normalizar_chave_duplicidade(c_pais)
            if nome_n and c_nome_n == nome_n:
                motivos.append("nome igual" + (" e país igual" if pais_n == c_pais_n else ""))
            if email_n and email_n == _normalizar_chave_duplicidade(c_email):
                motivos.append("e-mail igual")
            digitos_existentes = {
                _normalizar_digitos_duplicidade(c_tel),
                _normalizar_digitos_duplicidade(c_movel),
            } - {""}
            if digitos_candidatos & digitos_existentes:
                motivos.append("telefone/telemóvel igual")
            c_nif_n = re.sub(r"[\s.-]", "", str(c_nif or "")).upper()
            c_pass_n = re.sub(r"[\s-]", "", str(c_pass or "")).upper()
            if nif_n and c_nif_n == nif_n:
                motivos.append("identificação fiscal igual")
            if pass_n and c_pass_n == pass_n and pais_n == c_pais_n:
                motivos.append("passaporte igual no mesmo país")
            if motivos:
                resultado.append((cid, str(c_nome or "(sem nome)"), motivos))
            if len(resultado) >= 10:
                break
    except sqlite3.Error as erro:
        print(f"Não foi possível verificar possíveis duplicados: {erro}")
    finally:
        if con:
            con.close()
    return resultado


def confirmar_sem_duplicado(parent, duplicados):
    """Pede confirmação quando há possíveis duplicados, sem bloquear o utilizador."""
    if not duplicados:
        return True
    linhas = []
    for cid, nome, motivos in duplicados[:6]:
        linhas.append(f"• ID {cid} — {nome}: {', '.join(motivos)}")
    if len(duplicados) > 6:
        linhas.append(f"... e mais {len(duplicados) - 6} possível(is) registo(s).")
    return messagebox.askyesno(
        "Possível cliente duplicado",
        "Foram encontrados registos com dados semelhantes:\n\n"
        + "\n".join(linhas)
        + "\n\nSe tiver a certeza de que é outro cliente, deseja continuar?",
        parent=parent
    )


def _obter_caminho_banco(conexao):
    cursor = conexao.cursor()
    cursor.execute("PRAGMA database_list")
    for _seq, nome, ficheiro in cursor.fetchall():
        if str(nome).lower() == "main" and ficheiro:
            return Path(ficheiro).expanduser().resolve()
    raise RuntimeError("Não foi possível determinar o caminho do banco SQLite (base em memória ou caminho indisponível).")


def _executar_backup_para(destino):
    """Cria backup consistente através da API nativa de backup do SQLite."""
    origem_con = None
    destino_con = None
    temporario = None
    destino = Path(destino).expanduser().resolve()
    try:
        origem_con, _cursor = conectar_banco()
        if origem_con is None:
            raise RuntimeError("Não foi possível conectar ao banco de dados.")
        origem_path = _obter_caminho_banco(origem_con)
        if destino == origem_path:
            raise ValueError("O arquivo de backup não pode substituir diretamente o banco de dados em uso.")
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_name(destino.name + ".tmp")
        if temporario.exists():
            temporario.unlink()
        destino_con = sqlite3.connect(str(temporario))
        origem_con.backup(destino_con)
        destino_con.commit()
        resultado = destino_con.execute("PRAGMA integrity_check").fetchone()
        if not resultado or str(resultado[0]).lower() != "ok":
            raise sqlite3.DatabaseError("A verificação de integridade do backup falhou.")
        destino_con.close()
        destino_con = None
        origem_con.close()
        origem_con = None
        os.replace(temporario, destino)
        return destino
    finally:
        if destino_con:
            destino_con.close()
        if origem_con:
            origem_con.close()
        if temporario and temporario.exists():
            try:
                temporario.unlink()
            except OSError:
                pass


def criar_backup_automatico(rotulo="automatico"):
    """Cria backup automático no diretório backups_tb_software, mantendo os 30 mais recentes."""
    con = None
    try:
        con, _cur = conectar_banco()
        if con is None:
            return None
        caminho_bd = _obter_caminho_banco(con)
        con.close()
        con = None
        diretorio = caminho_bd.parent / "backups_tb_software"
        diretorio.mkdir(parents=True, exist_ok=True)
        marca_tempo = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        destino = diretorio / f"backup_{rotulo}_{marca_tempo}.sqlite3"
        caminho_backup = _executar_backup_para(destino)
        registar_auditoria("Cópia de segurança criada", detalhes=caminho_backup.name)
        backups = sorted(
            diretorio.glob("backup_*.sqlite3"),
            key=lambda item: item.stat().st_mtime,
            reverse=True
        )
        for antigo in backups[30:]:
            try:
                antigo.unlink()
            except OSError:
                pass
        return caminho_backup
    except (sqlite3.Error, OSError, RuntimeError, ValueError) as erro:
        print(f"Backup automático não concluído: {erro}")
        return None
    finally:
        if con:
            con.close()


def _validar_ficheiro_backup(caminho):
    caminho = Path(caminho).expanduser().resolve()
    if not caminho.is_file():
        raise FileNotFoundError("O arquivo de backup selecionado não existe.")
    con = None
    try:
        con = sqlite3.connect(str(caminho))
        integridade = con.execute("PRAGMA integrity_check").fetchone()
        if not integridade or str(integridade[0]).lower() != "ok":
            raise sqlite3.DatabaseError("O arquivo selecionado não passou na verificação de integridade.")
        tabelas = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"clientes", "usuarios"}.issubset(tabelas):
            raise sqlite3.DatabaseError("O arquivo não parece ser uma cópia válida do TB Software.")
    finally:
        if con:
            con.close()
    return caminho


def restaurar_backup(caminho_backup):
    """Restaura backup validado; cria cópia preventiva e tenta recuperá-la se falhar."""
    caminho_backup = _validar_ficheiro_backup(caminho_backup)
    con_atual = None
    try:
        con_atual, _cur = conectar_banco()
        if con_atual is None:
            raise RuntimeError("Não foi possível conectar ao banco de dados atual.")
        caminho_bd = _obter_caminho_banco(con_atual)
    finally:
        if con_atual:
            con_atual.close()

    if caminho_backup == caminho_bd:
        raise ValueError("Seleciona um arquivo de backup diferente do banco de dados em uso.")

    diretorio = caminho_bd.parent / "backups_tb_software"
    diretorio.mkdir(parents=True, exist_ok=True)
    pre_restauro = diretorio / f"backup_pre_restauro_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.sqlite3"
    _executar_backup_para(pre_restauro)

    fonte = None
    destino = None
    try:
        fonte = sqlite3.connect(str(caminho_backup))
        destino, _cur = conectar_banco()
        if destino is None:
            raise RuntimeError("Não foi possível abrir o banco de dados atual.")
        fonte.backup(destino)
        destino.commit()
        integridade = destino.execute("PRAGMA integrity_check").fetchone()
        if not integridade or str(integridade[0]).lower() != "ok":
            raise sqlite3.DatabaseError("A base restaurada não passou na verificação de integridade.")
    except Exception:
        if destino:
            destino.close()
            destino = None
        # Recuperação de segurança se o restauro não concluir corretamente.
        try:
            fonte_previa = sqlite3.connect(str(pre_restauro))
            conexao_recuperacao = sqlite3.connect(str(caminho_bd))
            fonte_previa.backup(conexao_recuperacao)
            conexao_recuperacao.commit()
            conexao_recuperacao.close()
            fonte_previa.close()
        except Exception as erro_recuperacao:
            print(f"Atenção: recuperação automática após erro também falhou: {erro_recuperacao}")
        raise
    finally:
        if fonte:
            fonte.close()
        if destino:
            destino.close()

    # Aplicar migrações para que também sejam aceites cópias anteriores à coluna Passaporte.
    atualizar_tabela_clientes()
    atualizar_tabela_usuarios()
    atualizar_tabela_auditoria()
    atualizar_tabelas_atendimento_lembretes()
    registar_auditoria("Base de dados restaurada", detalhes=f"Origem: {caminho_backup.name}; cópia preventiva: {pre_restauro.name}")
    return pre_restauro


def focar_janela_aberta(chave):
    """Traz uma janela existente para a frente ou devolve None."""
    janela_existente = _JANELAS_ABERTAS.get(chave)
    if janela_existente is None:
        return None

    try:
        if not janela_existente.winfo_exists():
            _JANELAS_ABERTAS.pop(chave, None)
            return None
        if janela_existente.state() in ("iconic", "withdrawn"):
            janela_existente.deiconify()
        janela_existente.lift()
        janela_existente.focus_force()
        return janela_existente
    except tk.TclError:
        _JANELAS_ABERTAS.pop(chave, None)
        return None


def registar_janela_aberta(chave, janela):
    """Regista uma janela e limpa o registo quando ela for fechada."""
    _JANELAS_ABERTAS[chave] = janela

    def ao_destruir(event):
        if event.widget is janela and _JANELAS_ABERTAS.get(chave) is janela:
            _JANELAS_ABERTAS.pop(chave, None)

    janela.bind("<Destroy>", ao_destruir, add="+")
    return janela


# ============================================================
#         POSICIONAMENTO DAS JANELAS NA ÁREA ÚTIL DO WINDOWS
# ============================================================
def centralizar_janela_na_area_util(janela, largura=None, altura=None, margem=8):
    """Centraliza a janela e limita a sua área exterior à área útil do Windows.

    Atenção: geometry() do Tkinter define a área cliente, não inclui o título
    nem as molduras do Windows. Por isso, reservamos espaço extra para essas
    decorações antes de calcular a altura/largura final. Isso evita que janelas
    altas invadam a barra de tarefas em monitores com pouca altura útil.
    """
    try:
        # Usar dimensões explícitas ou a geometria pedida; nunca aceitar 1x1
        # como tamanho verdadeiro enquanto o Tk ainda está a construir a janela.
        if largura is None or altura is None:
            match = re.match(r"^\s*(\d+)x(\d+)", janela.geometry())
            if match:
                if largura is None:
                    largura = int(match.group(1))
                if altura is None:
                    altura = int(match.group(2))
            else:
                janela.update_idletasks()
                if largura is None:
                    largura = int(janela.winfo_reqwidth())
                if altura is None:
                    altura = int(janela.winfo_reqheight())

        largura = int(largura)
        altura = int(altura)
        if largura < 200:
            largura = max(320, int(janela.winfo_reqwidth()))
        if altura < 200:
            altura = max(240, int(janela.winfo_reqheight()))

        # Fallback para as dimensões indicadas pelo Tkinter.
        screen_w = max(320, int(janela.winfo_screenwidth()))
        screen_h = max(240, int(janela.winfo_screenheight()))
        left, top = 0, 0
        work_w, work_h = screen_w, screen_h
        plataforma_windows = False

        # No Windows, SPI_GETWORKAREA devolve a área de trabalho sem a barra
        # de tarefas. Reservamos ainda espaço para título e molduras da janela.
        try:
            user32 = ctypes.windll.user32
            plataforma_windows = True
            rect = wintypes.RECT()
            ok = user32.SystemParametersInfoW(
                0x0030, 0, ctypes.byref(rect), 0  # SPI_GETWORKAREA
            )
            if ok:
                candidate_w = int(rect.right - rect.left)
                candidate_h = int(rect.bottom - rect.top)
                if candidate_w >= 320 and candidate_h >= 240:
                    left, top = int(rect.left), int(rect.top)
                    work_w, work_h = candidate_w, candidate_h
        except (AttributeError, OSError, TypeError, ValueError):
            pass

        margin = max(0, int(margem))
        available_w = max(1, work_w - 2 * margin)
        available_h = max(1, work_h - 2 * margin)

        # geometry() usa as dimensões interiores da janela. Estes valores
        # reservam o espaço exterior (barra de título e moldura); são aplicados
        # só no Windows, e a altura extra é deliberadamente conservadora.
        decoration_w = 20 if plataforma_windows else 0
        decoration_h = 48 if plataforma_windows else 0
        max_client_w = max(1, available_w - decoration_w)
        max_client_h = max(1, available_h - decoration_h)

        # Reduzir apenas se a janela (incluindo as molduras) não couber.
        final_w = min(largura, max_client_w)
        final_h = min(altura, max_client_h)
        outer_w = final_w + decoration_w
        outer_h = final_h + decoration_h

        # Centrar usando a dimensão exterior, não apenas a área cliente.
        x = left + margin + max(0, (available_w - outer_w) // 2)
        y = top + margin + max(0, (available_h - outer_h) // 2)

        # Definir tamanho e posição juntos, antes de a janela ser apresentada.
        janela.geometry(f"{final_w}x{final_h}+{x}+{y}")

        # Também limitar eventuais redimensionamentos manuais.
        try:
            janela.maxsize(max_client_w, max_client_h)
        except tk.TclError:
            pass
    except (tk.TclError, ValueError, TypeError, AttributeError):
        # Não interromper a aplicação nem definir uma geometria minúscula.
        return


def criar_area_formulario_rolavel(parent, fundo_canvas=None):
    """Cria uma área verticalmente rolável, com cartão que acompanha a largura."""
    fundo = fundo_canvas or COR_FUNDO
    exterior = tk.Frame(parent, bg=fundo)

    canvas = tk.Canvas(
        exterior,
        bg=fundo,
        highlightthickness=0,
        borderwidth=0
    )
    # Não mostrar barra de rolagem nestas duas telas; a roda do rato continua
    # a percorrer o conteúdo quando for necessário.
    canvas.pack(side="left", fill="both", expand=True)

    conteudo = tk.Frame(
        canvas,
        bg=COR_PAINEL,
        bd=1,
        relief="solid"
    )
    id_conteudo = canvas.create_window(
        (0, 0),
        window=conteudo,
        anchor="nw"
    )

    def atualizar_regiao(event=None):
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except tk.TclError:
            pass

    def ajustar_largura(event):
        try:
            canvas.itemconfigure(id_conteudo, width=max(1, event.width))
        except tk.TclError:
            pass

    def rolar_com_roda(event):
        if getattr(event, "delta", 0):
            canvas.yview_scroll(-1 * int(event.delta / 120), "units")
            return "break"

    conteudo.bind("<Configure>", atualizar_regiao)
    canvas.bind("<Configure>", ajustar_largura)
    canvas.bind("<MouseWheel>", rolar_com_roda)
    conteudo.bind("<MouseWheel>", rolar_com_roda)

    return exterior, canvas, conteudo


# ============================================================
#                  CONFIGURAÇÃO VISUAL
# ============================================================

COR_FUNDO = "#f3f6fa"
COR_PAINEL = "#ffffff"
COR_PRINCIPAL = "#022c53"
COR_BOTAO = "#126dcc"
COR_BOTAO_TEXTO = "#ffffff"
COR_TEXTO = "#16263d"
COR_SECUNDARIA = "#536273"

# ============================================================
#                 TEMAS CLARO / ESCURO
# ============================================================
TEMA_ATUAL = "Claro"

PALETA_TEMA_CLARO = {
    "fundo": "#f3f6fa",
    "painel": "#ffffff",
    "principal": "#022c53",
    "botao": "#126dcc",
    "texto_botao": "#ffffff",
    "texto": "#16263d",
    "secundaria": "#536273",
}

PALETA_TEMA_ESCURO = {
    "fundo": "#171c24",
    "painel": "#222a35",
    "principal": "#022c53",
    "botao": "#2476cc",
    "texto_botao": "#ffffff",
    "texto": "#e7edf5",
    "secundaria": "#aab5c4",
}


def definir_paleta_tema(tema):
    """Atualiza as cores usadas por janelas criadas a partir deste momento."""
    global TEMA_ATUAL
    global COR_FUNDO, COR_PAINEL, COR_PRINCIPAL, COR_BOTAO
    global COR_BOTAO_TEXTO, COR_TEXTO, COR_SECUNDARIA

    TEMA_ATUAL = "Escuro" if str(tema).strip().lower() == "escuro" else "Claro"
    paleta = PALETA_TEMA_ESCURO if TEMA_ATUAL == "Escuro" else PALETA_TEMA_CLARO
    COR_FUNDO = paleta["fundo"]
    COR_PAINEL = paleta["painel"]
    COR_PRINCIPAL = paleta["principal"]
    COR_BOTAO = paleta["botao"]
    COR_BOTAO_TEXTO = paleta["texto_botao"]
    COR_TEXTO = paleta["texto"]
    COR_SECUNDARIA = paleta["secundaria"]


def _normalizar_cor_base(cor, atributo):
    """Converte uma cor atual para a sua cor-base clara antes de a guardar."""
    if cor is None:
        return None
    valor = str(cor).strip().lower()
    tipo = "bg" if atributo in ("bg", "activebackground", "highlightbackground", "troughcolor", "selectbackground") else "fg"
    if TEMA_ATUAL == "Escuro":
        inverso_bg = {
            "#171c24": "#f3f6fa",
            "#222a35": "#ffffff",
            "#252f3d": "#f5f8fc",
            "#303a49": "#e8eef5",
        }
        inverso_fg = {
            "#e7edf5": "#16263d",
            "#aab5c4": "#536273",
            "#70b7ff": "#022c53",
        }
        return (inverso_bg if tipo == "bg" else inverso_fg).get(valor, cor)
    return cor


def _cor_para_tema(cor_base, atributo):
    if cor_base is None:
        return None
    valor = str(cor_base).strip().lower()
    tipo = "bg" if atributo in ("bg", "activebackground", "highlightbackground", "troughcolor", "selectbackground") else "fg"
    if TEMA_ATUAL == "Claro":
        return cor_base
    if tipo == "bg":
        mapa = {
            "#f3f6fa": "#171c24",
            "white": "#222a35",
            "#ffffff": "#222a35",
            "#f5f8fc": "#252f3d",
            "#e7f0f9": "#303a49",
            "#e8eef5": "#303a49",
        }
        return mapa.get(valor, cor_base)
    mapa = {
        "#16263d": "#e7edf5",
        "#536273": "#aab5c4",
        "#022c53": "#70b7ff",
        "black": "#e7edf5",
    }
    return mapa.get(valor, cor_base)


def aplicar_tema_janela(janela):
    """Aplica o tema a widgets Tk existentes, preservando cores de destaque."""
    try:
        if not janela.winfo_exists():
            return
    except tk.TclError:
        return

    propriedades = (
        "bg", "fg", "activebackground", "activeforeground",
        "highlightbackground", "highlightcolor", "insertbackground",
        "selectbackground", "selectforeground", "troughcolor"
    )
    pendentes = [janela]
    while pendentes:
        widget = pendentes.pop()
        try:
            pendentes.extend(widget.winfo_children())
        except (tk.TclError, AttributeError):
            pass

        for atributo in propriedades:
            try:
                cor_atual = widget.cget(atributo)
            except (tk.TclError, TypeError):
                continue
            nome_base = f"_tb_cor_base_{atributo}"
            if not hasattr(widget, nome_base):
                setattr(widget, nome_base, _normalizar_cor_base(cor_atual, atributo))
            cor_base = getattr(widget, nome_base)
            nova_cor = _cor_para_tema(cor_base, atributo)
            if nova_cor is not None and str(nova_cor) != str(cor_atual):
                try:
                    widget.configure(**{atributo: nova_cor})
                except (tk.TclError, TypeError):
                    pass


def registrar_tema_janela(janela):
    """Aplica o tema quando a janela e os seus widgets já estiverem construídos."""
    try:
        janela.bind(
            "<Map>",
            lambda evento, w=janela: aplicar_tema_janela(w),
            add="+"
        )
        janela.after_idle(lambda w=janela: aplicar_tema_janela(w))
    except tk.TclError:
        pass


def definir_tema(tema, root=None):
    """Define o tema e atualiza a interface já aberta."""
    definir_paleta_tema(tema)
    try:
        configurar_estilos()
    except (tk.TclError, RuntimeError):
        pass
    if root is None:
        root = getattr(tk, "_default_root", None)
    if root is not None:
        aplicar_tema_janela(root)


def obter_tema_usuario(usuario):
    con = None
    try:
        con, cur = conectar_banco()
        if con is None:
            return "Claro"
        cur.execute("SELECT COALESCE(tema, 'Claro') FROM usuarios WHERE usuario = ?", (usuario,))
        row = cur.fetchone()
        return "Escuro" if row and str(row[0]).strip().lower() == "escuro" else "Claro"
    except sqlite3.Error:
        return "Claro"
    finally:
        if con:
            con.close()

# ============================================================
#                    TAMANHO DOS ÍCONES
# ============================================================
# Altere somente este número para aumentar ou diminuir
# os ícones do Dashboard.
#
# Exemplos:
#   40 = menor
#   50 = atual
#   60 = maior
#   72 = tamanho original dos PNGs enviados
TAMANHO_ICONE = 50


def aplicar_icone_janela(janela):
    """Aplica o ícone padrão TB Software a qualquer janela Tkinter."""
    try:
        pasta_programa = Path(__file__).resolve().parent
        icone_path = pasta_programa / "assets" / "TB_Software.ico"
        if icone_path.exists():
            janela.iconbitmap(str(icone_path))
    except Exception:
        # O ícone é apenas visual; falhar aqui não deve impedir a aplicação de abrir.
        pass


# ============================================================
#                     TAMANHO DO LOGO
# ============================================================
# Altere estes dois valores para aumentar/diminuir o logo.
TAMANHO_LOGO_LARGURA = 200
TAMANHO_LOGO_ALTURA = 100

# ============================================================
#                    CONFIGURAÇÃO DAS FONTES
# ============================================================
# Você pode alterar as fontes do sistema aqui, sem precisar
# procurar várias linhas ao longo do programa.
#
# Exemplo:
#   FONTE_PADRAO = "Arial"
# ou mantenha "Segoe UI" para o visual atual.
FONTE_PADRAO = "Segoe UI"

# Tamanho e estilo de cada grupo de texto.
FONTE_8 = (FONTE_PADRAO, 8)
FONTE_8_NEGRITO = (FONTE_PADRAO, 8, "bold")
FONTE_9 = (FONTE_PADRAO, 9)
FONTE_9_NEGRITO = (FONTE_PADRAO, 9, "bold")
FONTE_10 = (FONTE_PADRAO, 10)
FONTE_10_NEGRITO = (FONTE_PADRAO, 10, "bold")
FONTE_12_NEGRITO = (FONTE_PADRAO, 12, "bold")
FONTE_14_NEGRITO = (FONTE_PADRAO, 14, "bold")
FONTE_15_NEGRITO = (FONTE_PADRAO, 15, "bold")
FONTE_16_NEGRITO = (FONTE_PADRAO, 16, "bold")
FONTE_17_NEGRITO = (FONTE_PADRAO, 17, "bold")
FONTE_18_NEGRITO = (FONTE_PADRAO, 18, "bold")
FONTE_20_NEGRITO = (FONTE_PADRAO, 20, "bold")
FONTE_21_NEGRITO = (FONTE_PADRAO, 21, "bold")
FONTE_22_NEGRITO = (FONTE_PADRAO, 22, "bold")
FONTE_27_NEGRITO = (FONTE_PADRAO, 27, "bold")








# ============================================================
#                    IDENTIDADE TB SOFTWARE
# ============================================================

NOME_EMPRESA = "TB Software"
SLOGAN_EMPRESA = "Soluções que facilitam seu trabalho"

config_empresa = carregar_configuracoes_empresa()

NOME_EMPRESA = config_empresa.get(
    "nome_empresa",
    NOME_EMPRESA
)

SLOGAN_EMPRESA = config_empresa.get(
    "slogan_empresa",
    SLOGAN_EMPRESA
)



def criar_rodape(parent, versao="v1.0"):
    """Rodapé padrão com relógio que para corretamente ao fechar a janela."""
    rodape = tk.Frame(parent, bg=COR_PRINCIPAL, height=28)
    rodape.pack(side="bottom", fill="x")
    rodape.pack_propagate(False)

    tk.Label(
        rodape,
        text=f"{NOME_EMPRESA} | {SLOGAN_EMPRESA}",
        font=FONTE_8_NEGRITO,
        bg=COR_PRINCIPAL, fg="white"
    ).pack(side="left", padx=10)

    hora_label = tk.Label(
        rodape,
        font=FONTE_8,
        bg=COR_PRINCIPAL, fg="white"
    )
    hora_label.pack(side="right", padx=10)

    tk.Label(
        rodape,
        text=versao,
        font=FONTE_8,
        bg=COR_PRINCIPAL, fg="white"
    ).pack(side="right", padx=(0, 4))

    # O temporizador é registado no mesmo widget (parent) que o cancela.
    # Se o after for registado no rodapé e cancelado pela janela-pai, o Tkinter
    # pode tentar apagar o mesmo comando Tcl duas vezes ao destruir o login.
    estado_relogio = {"after_id": None, "parado": False}

    def parar_relogio(event=None):
        if event is not None and event.widget not in (parent, rodape):
            return

        estado_relogio["parado"] = True
        after_id = estado_relogio["after_id"]
        estado_relogio["after_id"] = None

        if after_id is not None:
            # Importante: o temporizador é sempre agendado em parent, portanto
            # só parent.after_cancel deve removê-lo e limpar o comando Tcl.
            try:
                parent.after_cancel(after_id)
            except (tk.TclError, AttributeError):
                pass

    def atualizar_relogio():
        estado_relogio["after_id"] = None
        if estado_relogio["parado"]:
            return

        try:
            if not parent.winfo_exists() or not rodape.winfo_exists() or not hora_label.winfo_exists():
                parar_relogio()
                return

            from datetime import datetime
            agora = datetime.now().astimezone()
            hora_label.config(text=f"{agora:%d/%m/%Y}    {agora:%H:%M:%S}")

            if not estado_relogio["parado"] and parent.winfo_exists() and rodape.winfo_exists():
                # Agendar no mesmo widget que ficará responsável por cancelar.
                estado_relogio["after_id"] = parent.after(1000, atualizar_relogio)
        except tk.TclError:
            # A janela pode ter começado a fechar entre as verificações.
            parar_relogio()

    # O rodapé é destruído antes do parent. Nesse momento parent ainda pode
    # cancelar com segurança o after que ele próprio registou.
    try:
        rodape.bind("<Destroy>", parar_relogio, add="+")
        parent.bind("<Destroy>", parar_relogio, add="+")
    except tk.TclError:
        estado_relogio["parado"] = True

    atualizar_relogio()
    return rodape



def configurar_estilos():
    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    fundo_cabecalho = "#303a49" if TEMA_ATUAL == "Escuro" else "#e7f0f9"
    selecao_tabela = "#354a63" if TEMA_ATUAL == "Escuro" else "#cfe3f8"

    estilo.configure(
        "TCombobox",
        fieldbackground=COR_PAINEL,
        background=COR_PAINEL,
        foreground=COR_TEXTO,
        padding=3
    )

    estilo.map(
        "TCombobox",
        fieldbackground=[("readonly", COR_PAINEL)],
        foreground=[("readonly", COR_TEXTO)]
    )

    estilo.configure(
        "Treeview",
        background=COR_PAINEL,
        foreground=COR_TEXTO,
        rowheight=30,
        fieldbackground=COR_PAINEL,
        font=FONTE_9
    )

    estilo.configure(
        "Treeview.Heading",
        background=fundo_cabecalho,
        foreground=COR_TEXTO,
        font=FONTE_9_NEGRITO,
        padding=6
    )

    estilo.map(
        "Treeview",
        background=[("selected", selecao_tabela)],
        foreground=[("selected", COR_TEXTO)]
    )

# ============================================================
#             ATUALIZAR ESTRUTURA DA TABELA CLIENTES
# ============================================================

def _separar_definicoes_sqlite(sql_tabela):
    """Separa as definições de colunas/constraints preservando parênteses e aspas."""
    abre = sql_tabela.find("(")
    if abre < 0:
        raise sqlite3.DatabaseError("Definição da tabela clientes inesperada.")

    quote = None
    fecha = None
    depth = 0
    i = abre
    while i < len(sql_tabela):
        ch = sql_tabela[i]
        if quote:
            if quote == "]":
                if ch == "]":
                    quote = None
            elif ch == quote:
                # Aspas duplicadas dentro de identificadores/strings são escapes SQL.
                if i + 1 < len(sql_tabela) and sql_tabela[i + 1] == quote:
                    i += 1
                else:
                    quote = None
        else:
            if ch in ("'", '"', "`"):
                quote = ch
            elif ch == "[":
                quote = "]"
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    fecha = i
                    break
        i += 1

    if fecha is None:
        raise sqlite3.DatabaseError("Parênteses da tabela clientes não correspondem.")

    corpo = sql_tabela[abre + 1:fecha]
    sufixo = sql_tabela[fecha + 1:]
    partes = []
    inicio = 0
    depth = 0
    quote = None
    i = 0
    while i < len(corpo):
        ch = corpo[i]
        if quote:
            if quote == "]":
                if ch == "]":
                    quote = None
            elif ch == quote:
                if i + 1 < len(corpo) and corpo[i + 1] == quote:
                    i += 1
                else:
                    quote = None
        else:
            if ch in ("'", '"', "`"):
                quote = ch
            elif ch == "[":
                quote = "]"
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                partes.append(corpo[inicio:i].strip())
                inicio = i + 1
        i += 1
    final = corpo[inicio:].strip()
    if final:
        partes.append(final)
    return sql_tabela[:abre], partes, sufixo


def _nome_definicao_sqlite(definicao):
    match = re.match(r"""\s*(?:"((?:[^"]|"")+)"|`([^`]+)`|\[([^\]]+)\]|([A-Za-z_][A-Za-z0-9_]*))""", definicao)
    if not match:
        return ""
    return next((part for part in match.groups() if part is not None), "").replace('""', '"')


def _tornar_nif_opcional_se_necessario(conexao, cursor):
    """Retira NOT NULL de nif, preservando dados e índices, se a base antiga o exigir."""
    cursor.execute("PRAGMA table_info(clientes)")
    info = cursor.fetchall()
    coluna_nif = next((col for col in info if str(col[1]).lower() == "nif"), None)
    if coluna_nif is None or int(coluna_nif[3] or 0) == 0:
        return

    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='clientes'")
    row_sql = cursor.fetchone()
    if not row_sql or not row_sql[0]:
        raise sqlite3.DatabaseError("Não foi possível ler a estrutura da tabela clientes para tornar o NIF opcional.")

    sql_original = row_sql[0]
    prefixo, definicoes, sufixo = _separar_definicoes_sqlite(sql_original)
    novas_definicoes = []
    alterou = False
    for definicao in definicoes:
        if _nome_definicao_sqlite(definicao).casefold() == "nif":
            nova_definicao = re.sub(r"\s+NOT\s+NULL\b", "", definicao, flags=re.IGNORECASE)
            if nova_definicao != definicao:
                definicao = nova_definicao
                alterou = True
        novas_definicoes.append(definicao)
    if not alterou:
        # PRAGMA reportou NOT NULL, mas a declaração não foi reconhecida: falhar de forma segura.
        raise sqlite3.DatabaseError("Não foi possível adaptar a coluna NIF para aceitar clientes internacionais sem NIF.")

    prefixo_nova = re.sub(
        r"(?is)(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)(?:\"clientes\"|`clientes`|\[clientes\]|clientes)\s*$",
        r'\1"__clientes_migracao_passaporte"',
        prefixo.strip(),
        count=1
    )
    if prefixo_nova == prefixo.strip():
        raise sqlite3.DatabaseError("Não foi possível preparar a migração segura da tabela clientes.")
    sql_nova = prefixo_nova + " (\n    " + ",\n    ".join(novas_definicoes) + "\n)" + sufixo

    # Preservar índices e gatilhos definidos separadamente na tabela original.
    cursor.execute("""
        SELECT type, name, sql FROM sqlite_master
        WHERE tbl_name = 'clientes' AND type IN ('index', 'trigger') AND sql IS NOT NULL
        ORDER BY CASE type WHEN 'index' THEN 0 ELSE 1 END, name
    """)
    objetos_sql = cursor.fetchall()

    nomes_colunas = [col[1] for col in info]
    colunas_sql = ", ".join('"' + nome.replace('"', '""') + '"' for nome in nomes_colunas)
    seq_antigo = None
    try:
        cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = 'clientes'")
        seq_row = cursor.fetchone()
        seq_antigo = int(seq_row[0]) if seq_row else None
    except sqlite3.Error:
        seq_antigo = None

    # PRAGMA foreign_keys só pode ser alterado fora de uma transação.
    conexao.commit()
    cursor.execute("PRAGMA foreign_keys = OFF")
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute('DROP TABLE IF EXISTS "__clientes_migracao_passaporte"')
        cursor.execute(sql_nova)
        cursor.execute(
            f'INSERT INTO "__clientes_migracao_passaporte" ({colunas_sql}) SELECT {colunas_sql} FROM "clientes"'
        )
        cursor.execute('DROP TABLE "clientes"')
        cursor.execute('ALTER TABLE "__clientes_migracao_passaporte" RENAME TO "clientes"')

        for _tipo, _nome, sql_objeto in objetos_sql:
            cursor.execute(sql_objeto)

        if seq_antigo is not None:
            try:
                cursor.execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'clientes'", (seq_antigo,))
                if cursor.rowcount == 0:
                    cursor.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('clientes', ?)", (seq_antigo,))
            except sqlite3.Error:
                pass

        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error:
            pass


def atualizar_tabela_clientes():
    """Migra a tabela de clientes, incluindo passaporte e NIF opcional."""
    conexao = None
    novos_campos = {
        "tipo_cliente": "TEXT",
        "data_nascimento": "TEXT",
        "nacionalidade": "TEXT",
        "movel": "TEXT",
        "email": "TEXT",
        "codigo_postal": "TEXT",
        "pais": "TEXT",
        "passaporte": "TEXT",
        "data_cadastro": "TEXT"
    }

    try:
        conexao, cursor = conectar_banco()
        if conexao is None:
            return

        cursor.execute("PRAGMA table_info(clientes)")
        existentes = {str(coluna[1]).lower() for coluna in cursor.fetchall()}
        for nome_coluna, tipo in novos_campos.items():
            if nome_coluna.lower() not in existentes:
                cursor.execute(f"ALTER TABLE clientes ADD COLUMN {nome_coluna} {tipo}")
        conexao.commit()

        _tornar_nif_opcional_se_necessario(conexao, cursor)
        conexao.commit()
    except (sqlite3.Error, ValueError, TypeError) as erro:
        if conexao:
            try:
                conexao.rollback()
            except sqlite3.Error:
                pass
        print(f"Erro ao atualizar tabela clientes: {erro}")
    finally:
        if conexao:
            conexao.close()


# ============================================================
#             ATUALIZAR ESTRUTURA DOS UTILIZADORES
# ============================================================

def atualizar_tabela_usuarios():
    """Garante que a tabela usuarios tenha um perfil de acesso."""
    conexao = None

    try:
        conexao, cursor = conectar_banco()

        if conexao is None:
            return

        cursor.execute("PRAGMA table_info(usuarios)")
        colunas = {coluna[1] for coluna in cursor.fetchall()}

        if "perfil" not in colunas:
            cursor.execute(
                "ALTER TABLE usuarios ADD COLUMN perfil TEXT DEFAULT 'Utilizador'"
            )

        if "ativo" not in colunas:
            cursor.execute(
                "ALTER TABLE usuarios ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1"
            )

        if "tema" not in colunas:
            cursor.execute(
                "ALTER TABLE usuarios ADD COLUMN tema TEXT NOT NULL DEFAULT 'Claro'"
            )

        # Normaliza os dados existentes e protege a conta principal.
        cursor.execute(
            "UPDATE usuarios SET perfil = 'Administrador' WHERE LOWER(usuario) = 'admin'"
        )
        cursor.execute(
            "UPDATE usuarios SET perfil = 'Utilizador' WHERE perfil IS NULL OR TRIM(perfil) = ''"
        )
        cursor.execute("UPDATE usuarios SET ativo = 1 WHERE ativo IS NULL")
        cursor.execute("UPDATE usuarios SET tema = 'Claro' WHERE tema IS NULL OR TRIM(tema) = ''")
        cursor.execute("UPDATE usuarios SET tema = 'Claro' WHERE LOWER(tema) NOT IN ('claro', 'escuro')")
        cursor.execute("UPDATE usuarios SET ativo = 1 WHERE LOWER(usuario) = 'admin'")

        conexao.commit()

    except sqlite3.Error as erro:
        print(f"Erro ao atualizar tabela usuarios: {erro}")

    finally:
        if conexao:
            conexao.close()


def obter_perfil_usuario(usuario):
    """Retorna o perfil do utilizador, ou None se ele não existir."""
    conexao = None

    try:
        conexao, cursor = conectar_banco()
        if conexao is None:
            return None

        cursor.execute(
            "SELECT COALESCE(perfil, 'Utilizador'), COALESCE(ativo, 1) FROM usuarios WHERE usuario = ?",
            (usuario,)
        )
        resultado = cursor.fetchone()
        if not resultado or int(resultado[1] or 0) != 1:
            return None
        return resultado[0]

    except sqlite3.Error:
        return None

    finally:
        if conexao:
            conexao.close()


def autenticar_autorizador(usuario, senha):
    """Valida uma conta Administrador ativa e migra hashes antigos após validação."""
    if not usuario or not senha:
        return None
    con = None
    try:
        con, cur = conectar_banco()
        if con is None:
            return None
        cur.execute("""
            SELECT perfil, COALESCE(ativo, 1), senha
            FROM usuarios WHERE usuario = ?
        """, (usuario,))
        resultado = cur.fetchone()
        if not resultado:
            return None
        perfil, ativo, hash_guardado = resultado
        senha_ok, legado = verificar_hash_senha(senha, hash_guardado)
        if not senha_ok or int(ativo or 0) != 1:
            return None
        if legado:
            cur.execute("UPDATE usuarios SET senha = ? WHERE usuario = ?", (criar_hash_senha(senha), usuario))
            con.commit()
        return "Administrador" if str(perfil or "Utilizador") == "Administrador" else None
    except sqlite3.Error:
        return None
    finally:
        if con:
            con.close()

def solicitar_autorizacao(parent, acao):
    """Abre a janela de autorização para ações administrativas."""
    janela = tk.Toplevel(parent)
    aplicar_icone_janela(janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Autorização")
    janela.geometry("500x390")
    centralizar_janela_na_area_util(janela, 500, 390)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)
    janela.transient(parent)
    janela.grab_set()

    tk.Label(
        janela,
        text="AUTORIZAÇÃO NECESSÁRIA",
        font=FONTE_18_NEGRITO,
        bg=COR_FUNDO,
        fg=COR_PRINCIPAL
    ).pack(pady=(14, 6))

    tk.Label(
        janela,
        text=acao,
        font=FONTE_9,
        bg=COR_FUNDO,
        fg=COR_SECUNDARIA,
        wraplength=370,
        justify="center"
    ).pack(pady=(0, 8))

    quadro = tk.Frame(janela, bg="white", bd=1, relief="solid")
    quadro.pack(fill="x", padx=28, pady=4)

    tk.Label(
        quadro,
        text="Utilizador responsável:",
        font=FONTE_9_NEGRITO,
        bg="white",
        fg=COR_TEXTO
    ).grid(row=0, column=0, sticky="w", padx=16, pady=(13, 5))

    entrada_usuario = tk.Entry(quadro, font=FONTE_10)
    entrada_usuario.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8), ipady=3)

    tk.Label(
        quadro,
        text="Senha:",
        font=FONTE_9_NEGRITO,
        bg="white",
        fg=COR_TEXTO
    ).grid(row=2, column=0, sticky="w", padx=16, pady=(4, 5))

    entrada_senha = tk.Entry(quadro, font=FONTE_10, show="*")
    entrada_senha.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 6), ipady=3)
    tk.Button(quadro, text="Esqueci a senha", command=lambda: recuperar_senha(janela_login),
              font=FONTE_9_NEGRITO, bg="white", fg=COR_BOTAO, relief="flat",
              cursor="hand2", bd=0).grid(row=4, column=0, sticky="e", padx=16, pady=(0, 10))
    quadro.columnconfigure(0, weight=1)

    resultado = {"autorizado": False, "perfil": None}

    def confirmar():
        usuario = entrada_usuario.get().strip()
        senha = entrada_senha.get()
        perfil = autenticar_autorizador(usuario, senha)

        if perfil is None:
            messagebox.showerror(
                "Acesso negado",
                "Apenas um Administrador ativo pode autorizar esta alteração.",
                parent=janela
            )
            entrada_senha.delete(0, tk.END)
            entrada_senha.focus_set()
            return

        resultado["autorizado"] = True
        resultado["perfil"] = perfil
        janela.destroy()

    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(fill="x", padx=28, pady=(10, 14))

    tk.Button(
        botoes,
        text="Autorizar",
        command=confirmar,
        font=FONTE_9_NEGRITO,
        bg=COR_BOTAO,
        fg="white",
        relief="flat",
        cursor="hand2",
        padx=18,
        pady=6
    ).pack(side="left")

    tk.Button(
        botoes,
        text="Cancelar",
        command=janela.destroy,
        font=FONTE_9_NEGRITO,
        bg="#e8eef5",
        fg=COR_TEXTO,
        relief="flat",
        cursor="hand2",
        padx=18,
        pady=6
    ).pack(side="right")

    entrada_usuario.focus_set()
    janela.bind("<Return>", lambda event: confirmar())
    janela.wait_window()

    return resultado


# ============================================================
#                    USUÁRIO LOGADO
# ============================================================

usuario_logado = None


# ============================================================
#                       LOGIN
# ============================================================

def verificar_login():
    global usuario_logado, USUARIO_AUDITORIA_ATUAL
    usuario = entrada_usuario.get().strip()
    senha = entrada_senha.get()

    if not usuario or not senha:
        messagebox.showerror("Login", "Introduza o utilizador e a senha.", parent=janela_login)
        return

    conexao = None
    try:
        conexao, cursor = conectar_banco()
        if conexao is None:
            messagebox.showerror("Erro", "Não foi possível conectar ao banco de dados.", parent=janela_login)
            return

        cursor.execute("""
            SELECT COALESCE(perfil, 'Utilizador'), COALESCE(ativo, 1),
                   COALESCE(tema, 'Claro'), senha
            FROM usuarios WHERE usuario = ?
        """, (usuario,))
        usuario_encontrado = cursor.fetchone()

        if not usuario_encontrado:
            messagebox.showerror("Erro", "Utilizador ou senha incorretos!", parent=janela_login)
            return

        perfil, ativo, tema, hash_guardado = usuario_encontrado
        senha_ok, hash_legado = verificar_hash_senha(senha, hash_guardado)
        if not senha_ok:
            messagebox.showerror("Erro", "Utilizador ou senha incorretos!", parent=janela_login)
            entrada_senha.delete(0, tk.END)
            entrada_senha.focus_set()
            return

        # As instalações antigas podem conter o hash conhecido de admin/1234.
        # Obrigar a substituí-lo evita manter uma senha padrão depois da atualização.
        hash_senha_padrao_antigo = hashlib.sha256("1234".encode("utf-8")).hexdigest()
        usa_senha_padrao_antiga = (
            usuario.casefold() == "admin"
            and hmac.compare_digest(str(hash_guardado or "").lower(), hash_senha_padrao_antigo)
        )
        if usa_senha_padrao_antiga:
            # Fechar a ligação de leitura antes da caixa que grava a nova senha.
            conexao.close()
            conexao = None
            solicitar_substituicao_senha_padrao(janela_login, usuario)
            # A senha foi ou não foi alterada numa janela própria; voltar ao login
            # evita continuar com a conexão antiga e obriga a introduzir a nova senha.
            entrada_senha.delete(0, tk.END)
            entrada_senha.focus_set()
            return

        if int(ativo or 0) != 1:
            messagebox.showerror(
                "Conta bloqueada", "Esta conta está bloqueada. Contacte o Administrador.",
                parent=janela_login
            )
            return

        if hash_legado:
            cursor.execute(
                "UPDATE usuarios SET senha = ? WHERE usuario = ?",
                (criar_hash_senha(senha), usuario)
            )
        conexao.commit()
    except sqlite3.Error as erro:
        messagebox.showerror("Erro", f"Erro ao acessar o banco de dados:\n{erro}", parent=janela_login)
        return
    finally:
        if conexao:
            conexao.close()

    usuario_logado = usuario
    USUARIO_AUDITORIA_ATUAL = usuario
    registar_auditoria("Login bem-sucedido", detalhes="Sessão iniciada")
    # A cópia é criada automaticamente após login, sem bloquear a entrada caso o backup falhe.
    criar_backup_automatico()
    janela_login.destroy()
    janela_principal(usuario, tema)

# ============================================================
#                  JANELA PRINCIPAL
# ============================================================


def abrir_historico_atendimento_cliente(parent, cliente_id, cliente_nome):
    """Consulta e regista contactos/observações associados a um cliente."""
    chave = f"atendimento_cliente:{cliente_id}"
    existente = focar_janela_aberta(chave)
    if existente is not None:
        return existente

    janela = tk.Toplevel(parent)

    aplicar_icone_janela(janela)
    registar_janela_aberta(chave, janela)
    registrar_tema_janela(janela)
    janela.title(f"TB Software - Atendimento: {cliente_nome}")
    janela.geometry("900x520")
    centralizar_janela_na_area_util(janela, 900, 520)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)

    tk.Label(janela, text=f"Histórico de atendimento — {cliente_nome}",
             font=FONTE_15_NEGRITO, bg=COR_FUNDO, fg=COR_PRINCIPAL).pack(
                 anchor="w", padx=18, pady=(12, 4))
    tk.Label(janela, text="Regista chamadas, e-mails, reuniões, pedidos e observações.",
             font=FONTE_9, bg=COR_FUNDO, fg=COR_SECUNDARIA).pack(
                 anchor="w", padx=18, pady=(0, 8))

    frame_tabela = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    frame_tabela.pack(fill="both", expand=True, padx=18, pady=5)
    colunas = ("data", "tipo", "usuario", "proximo", "descricao")
    tabela = ttk.Treeview(frame_tabela, columns=colunas, show="headings", height=12)
    for col, titulo, largura in (
        ("data", "Data/hora", 140), ("tipo", "Tipo", 110),
        ("usuario", "Utilizador", 110), ("proximo", "Próximo contacto", 125),
        ("descricao", "Observação", 380)
    ):
        tabela.heading(col, text=titulo)
        tabela.column(col, width=largura, anchor="w")
    barra = ttk.Scrollbar(frame_tabela, orient="vertical", command=tabela.yview)
    tabela.configure(yscrollcommand=barra.set)
    tabela.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")

    def recarregar():
        for item in tabela.get_children():
            tabela.delete(item)
        con = None
        try:
            con, cur = conectar_banco()
            cur.execute("""
                SELECT data_hora, tipo, usuario, proximo_contacto, descricao
                FROM historico_atendimento WHERE cliente_id = ?
                ORDER BY data_hora DESC, id DESC
            """, (cliente_id,))
            for registo in cur.fetchall():
                data_hora, tipo, usuario, proximo, descricao = registo
                if proximo:
                    try:
                        proximo = datetime.strptime(proximo, "%Y-%m-%d").strftime("%d/%m/%Y")
                    except ValueError:
                        pass
                tabela.insert("", "end", values=(data_hora, tipo, usuario, proximo or "—", descricao))
        except sqlite3.Error as erro:
            messagebox.showerror("Histórico de atendimento", f"Não foi possível carregar os registos:\n{erro}", parent=janela)
        finally:
            if con:
                con.close()

    def novo_registo():
        editor = tk.Toplevel(janela)
        aplicar_icone_janela(editor)
        registrar_tema_janela(editor)
        editor.title("Novo registo de atendimento")
        editor.geometry("520x430")
        centralizar_janela_na_area_util(editor, 520, 430)
        editor.resizable(False, False)
        editor.configure(bg=COR_FUNDO)
        editor.transient(janela)
        editor.grab_set()

        tk.Label(editor, text="NOVO REGISTO DE ATENDIMENTO", font=FONTE_14_NEGRITO,
                 bg=COR_FUNDO, fg=COR_PRINCIPAL).pack(pady=(14, 8))
        formulario = tk.Frame(editor, bg=COR_PAINEL, bd=1, relief="solid")
        formulario.pack(fill="both", expand=True, padx=20, pady=5)
        tk.Label(formulario, text="Tipo de contacto", font=FONTE_9_NEGRITO,
                 bg=COR_PAINEL, fg=COR_TEXTO).pack(anchor="w", padx=14, pady=(12, 4))
        tipo_var = tk.StringVar(value="Observação")
        combo_tipo = ttk.Combobox(formulario, textvariable=tipo_var,
                                  values=("Telefone", "E-mail", "Reunião", "Pedido", "Observação"),
                                  state="readonly", font=FONTE_9)
        combo_tipo.pack(fill="x", padx=14)
        tk.Label(formulario, text="Descrição / notas *", font=FONTE_9_NEGRITO,
                 bg=COR_PAINEL, fg=COR_TEXTO).pack(anchor="w", padx=14, pady=(10, 4))
        texto = tk.Text(formulario, height=7, wrap="word", font=FONTE_9)
        texto.pack(fill="both", expand=True, padx=14)
        tk.Label(formulario, text="Próximo contacto (DD/MM/AAAA, opcional)", font=FONTE_9_NEGRITO,
                 bg=COR_PAINEL, fg=COR_TEXTO).pack(anchor="w", padx=14, pady=(10, 4))
        entrada_data = tk.Entry(formulario, font=FONTE_9)
        entrada_data.pack(fill="x", padx=14, pady=(0, 12))

        def guardar():
            descricao = texto.get("1.0", "end-1c").strip()
            data_txt = entrada_data.get().strip()
            if not descricao:
                messagebox.showerror("Dados em falta", "Escreve uma descrição para o registo.", parent=editor)
                texto.focus_set()
                return
            data_iso = None
            if data_txt:
                try:
                    data_iso = datetime.strptime(data_txt, "%d/%m/%Y").date().isoformat()
                except ValueError:
                    messagebox.showerror("Data inválida", "Usa o formato DD/MM/AAAA e uma data válida.", parent=editor)
                    entrada_data.focus_set()
                    return
            con = None
            try:
                con, cur = conectar_banco()
                cur.execute("""
                    INSERT INTO historico_atendimento
                        (cliente_id, data_hora, usuario, tipo, descricao, proximo_contacto)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (cliente_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      USUARIO_AUDITORIA_ATUAL or "Sistema", tipo_var.get(), descricao[:4000], data_iso))
                _inserir_auditoria(cur, "Atendimento registado", cliente_id=cliente_id,
                                   detalhes=f"Tipo: {tipo_var.get()}; nota de atendimento adicionada")
                con.commit()
                editor.destroy()
                recarregar()
            except sqlite3.Error as erro:
                if con:
                    con.rollback()
                messagebox.showerror("Erro", f"Não foi possível guardar o registo:\n{erro}", parent=editor)
            finally:
                if con:
                    con.close()

        botoes = tk.Frame(editor, bg=COR_FUNDO)
        botoes.pack(fill="x", padx=20, pady=(5, 12))
        tk.Button(botoes, text="Guardar", command=guardar, font=FONTE_9_NEGRITO,
                  bg=COR_BOTAO, fg="white", relief="flat", padx=16, pady=5).pack(side="left")
        tk.Button(botoes, text="Cancelar", command=editor.destroy, font=FONTE_9_NEGRITO,
                  bg="#e8eef5", fg=COR_TEXTO, relief="flat", padx=16, pady=5).pack(side="right")

    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(fill="x", padx=18, pady=(4, 7))
    tk.Button(botoes, text="Novo registo", command=novo_registo, font=FONTE_9_NEGRITO,
              bg=COR_BOTAO, fg="white", relief="flat", padx=16, pady=6).pack(side="left")
    tk.Button(botoes, text="Fechar", command=janela.destroy, font=FONTE_9_NEGRITO,
              bg="#e8eef5", fg=COR_TEXTO, relief="flat", padx=16, pady=6).pack(side="right")
    criar_rodape(janela)
    recarregar()
    return janela



def _caminho_arranque_windows():
    """Caminho do script de arranque automático para o utilizador atual do Windows."""
    if os.name != "nt":
        return None
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    pasta = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return pasta / "TB_Software_Arranque.vbs"


def arranque_windows_ativo():
    caminho = _caminho_arranque_windows()
    return bool(caminho and caminho.is_file())


def configurar_arranque_windows(ativar):
    """Ativa/desativa o arranque após login no Windows através de um VBS sem consola."""
    caminho = _caminho_arranque_windows()
    if caminho is None:
        raise OSError("O arranque automático está disponível apenas no Windows com a pasta APPDATA definida.")

    if not ativar:
        if caminho.exists():
            caminho.unlink()
        return False

    script = Path(__file__).resolve()
    python_exe = Path(sys.executable).resolve()
    pythonw = python_exe.with_name("pythonw.exe")
    if not pythonw.is_file():
        # Fallback para uma instalação personalizada que não tenha pythonw.exe.
        pythonw = python_exe

    def vbs_quoted(valor):
        return '"' + str(valor).replace('"', '""') + '"'

    comando = f'"{pythonw}" "{script}"'
    conteudo = (
        'Set WshShell = CreateObject("WScript.Shell")\r\n'
        f'WshShell.CurrentDirectory = {vbs_quoted(script.parent)}\r\n'
        f'WshShell.Run {vbs_quoted(comando)}, 0, False\r\n'
    )
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8")
    return True


def _datetime_lembrete(data_iso, hora_txt="09:00"):
    """Converte data/hora de lembrete para datetime local, com fallback seguro."""
    hora_txt = str(hora_txt or "09:00").strip()
    try:
        return datetime.strptime(f"{data_iso} {hora_txt}", "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        try:
            return datetime.strptime(f"{data_iso} 09:00", "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return datetime.max


def _datetime_opcional(valor):
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d %H:%M:%S") if valor else None
    except (ValueError, TypeError):
        try:
            return datetime.fromisoformat(str(valor)) if valor else None
        except (ValueError, TypeError):
            return None


def obter_notificacoes_lembretes(inicio=False):
    """Devolve (resumo_inicio, avisos_vencidos), marcando avisos para evitar repetição."""
    agora = datetime.now().replace(microsecond=0)
    agora_txt = agora.strftime("%Y-%m-%d %H:%M:%S")
    hoje_txt = agora.date().isoformat()
    resumo = []
    avisos = []
    con = None
    try:
        con, cur = conectar_banco()
        if con is None:
            return resumo, avisos
        cur.execute("""
            SELECT l.id, l.cliente_id, COALESCE(c.nome, '(cliente removido)'),
                   l.titulo, COALESCE(l.descricao, ''), l.data_vencimento,
                   COALESCE(l.hora_vencimento, '09:00'), l.status,
                   COALESCE(l.ultimo_aviso_em, ''),
                   COALESCE(l.ultimo_resumo_inicio_em, ''),
                   COALESCE(l.adiar_ate, '')
            FROM lembretes_clientes l
            LEFT JOIN clientes c ON c.id = l.cliente_id
            WHERE l.status = 'Pendente'
            ORDER BY l.data_vencimento, COALESCE(l.hora_vencimento, '09:00'), l.id
        """)
        linhas = cur.fetchall()
        if inicio:
            for rid, cid, nome, titulo, descricao, data_iso, hora, status, ultimo_aviso, ultimo_resumo, adiar_ate in linhas:
                devido = _datetime_lembrete(data_iso, hora)
                adiado = _datetime_opcional(adiar_ate)
                ultimo = _datetime_opcional(ultimo_aviso)
                resumo_dia = str(ultimo_resumo or "")[:10]
                # No início, incluir lembretes de hoje e atrasados, uma vez por dia.
                if devido.date() > agora.date() or resumo_dia == hoje_txt:
                    continue
                if adiado and adiado > agora:
                    continue
                # Se o aviso exato já apareceu hoje, não o repetir no resumo de arranque.
                if ultimo and ultimo.date() == agora.date() and ultimo >= devido:
                    continue
                resumo.append({
                    "id": int(rid), "cliente_id": cid, "cliente": str(nome or "(cliente removido)"),
                    "titulo": str(titulo or ""), "descricao": str(descricao or ""),
                    "data": str(data_iso or ""), "hora": str(hora or "09:00"),
                    "tipo": "inicio"
                })
                cur.execute(
                    "UPDATE lembretes_clientes SET ultimo_resumo_inicio_em = ? WHERE id = ?",
                    (hoje_txt, rid)
                )
                # Os lembretes que já venceram ficam marcados como avisados para o ciclo
                # seguinte não abrir uma segunda janela logo após o resumo de arranque.
                if devido <= agora:
                    cur.execute(
                        "UPDATE lembretes_clientes SET ultimo_aviso_em = ?, adiar_ate = NULL WHERE id = ?",
                        (agora_txt, rid)
                    )
            con.commit()

        # Verificar os lembretes cuja hora já chegou. O aviso repete no máximo uma vez
        # por dia para um vencimento em atraso; a opção Adiar força nova notificação
        # quando o período de adiamento expirar.
        cur.execute("""
            SELECT l.id, l.cliente_id, COALESCE(c.nome, '(cliente removido)'),
                   l.titulo, COALESCE(l.descricao, ''), l.data_vencimento,
                   COALESCE(l.hora_vencimento, '09:00'),
                   COALESCE(l.ultimo_aviso_em, ''), COALESCE(l.adiar_ate, '')
            FROM lembretes_clientes l
            LEFT JOIN clientes c ON c.id = l.cliente_id
            WHERE l.status = 'Pendente'
            ORDER BY l.data_vencimento, COALESCE(l.hora_vencimento, '09:00'), l.id
        """)
        for rid, cid, nome, titulo, descricao, data_iso, hora, ultimo_aviso, adiar_ate in cur.fetchall():
            devido = _datetime_lembrete(data_iso, hora)
            if devido > agora:
                continue
            ultimo = _datetime_opcional(ultimo_aviso)
            adiado = _datetime_opcional(adiar_ate)
            if adiado is not None:
                if adiado > agora:
                    continue
                deve_avisar = True
            else:
                deve_avisar = (
                    ultimo is None
                    or ultimo.date() < agora.date()
                    or ultimo < devido
                )
            if not deve_avisar:
                continue
            avisos.append({
                "id": int(rid), "cliente_id": cid, "cliente": str(nome or "(cliente removido)"),
                "titulo": str(titulo or ""), "descricao": str(descricao or ""),
                "data": str(data_iso or ""), "hora": str(hora or "09:00"),
                "tipo": "vencido"
            })
            cur.execute(
                "UPDATE lembretes_clientes SET ultimo_aviso_em = ?, adiar_ate = NULL WHERE id = ?",
                (agora_txt, rid)
            )
        if resumo or avisos:
            _inserir_auditoria(cur, "Notificação de lembretes", detalhes=f"Resumo de início: {len(resumo)}; avisos por hora: {len(avisos)}")
        con.commit()
    except (sqlite3.Error, OSError, ValueError) as erro:
        if con:
            try:
                con.rollback()
            except sqlite3.Error:
                pass
        print(f"Não foi possível verificar lembretes automaticamente: {erro}")
        return [], []
    finally:
        if con:
            con.close()
    return resumo, avisos


def mostrar_aviso_lembretes(parent, usuario_logado, itens, resumo_inicio=False):
    """Mostra uma janela de aviso com ações para ver, adiar ou concluir os lembretes."""
    global _AVISO_LEMBRETES_TABELA
    if not itens:
        return
    existente = focar_janela_aberta("aviso_lembretes")
    if existente is None:
        janela = tk.Toplevel(parent)
        aplicar_icone_janela(janela)
        registar_janela_aberta("aviso_lembretes", janela)
        registrar_tema_janela(janela)
        janela.title("TB Software - Lembretes" if not resumo_inicio else "TB Software - Lembretes de hoje")
        janela.geometry("760x450")
        centralizar_janela_na_area_util(janela, 760, 450)
        janela.resizable(False, False)
        janela.configure(bg=COR_FUNDO)

        titulo_ui = "Lembretes para hoje e atrasados" if resumo_inicio else "Chegou a hora de tratar destes lembretes"
        tk.Label(janela, text=titulo_ui, font=FONTE_15_NEGRITO, bg=COR_FUNDO, fg=COR_PRINCIPAL).pack(
            anchor="w", padx=18, pady=(12, 4)
        )
        tk.Label(janela, text="Seleciona um ou mais registos para adiar por uma hora ou marcar como concluídos.",
                 font=FONTE_9, bg=COR_FUNDO, fg=COR_SECUNDARIA).pack(anchor="w", padx=18, pady=(0, 8))

        quadro = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
        quadro.pack(fill="both", expand=True, padx=18, pady=5)
        colunas = ("id", "cliente", "tarefa", "vencimento", "descricao")
        tabela = ttk.Treeview(quadro, columns=colunas, show="headings", height=10, selectmode="extended")
        for col, rotulo, largura in (
            ("id", "ID", 44), ("cliente", "Cliente", 190), ("tarefa", "Tarefa", 180),
            ("vencimento", "Data e hora", 125), ("descricao", "Descrição", 180)
        ):
            tabela.heading(col, text=rotulo)
            tabela.column(col, width=largura, anchor="w")
        barra = ttk.Scrollbar(quadro, orient="vertical", command=tabela.yview)
        tabela.configure(yscrollcommand=barra.set)
        tabela.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        _AVISO_LEMBRETES_TABELA = tabela

        def ids_selecionados():
            return [str(tabela.item(iid, "values")[0]) for iid in tabela.selection()]

        def fechar():
            global _AVISO_LEMBRETES_TABELA
            _AVISO_LEMBRETES_TABELA = None
            try:
                janela.destroy()
            except tk.TclError:
                pass

        def abrir_lista():
            fechar()
            abrir_lembretes(parent, usuario_logado)

        def adiar_selecionados():
            ids = ids_selecionados()
            if not ids:
                messagebox.showinfo("Lembretes", "Seleciona pelo menos um lembrete para adiar.", parent=janela)
                return
            adiamento = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            agora_txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            con = None
            try:
                con, cur = conectar_banco()
                if con is None or cur is None:
                    messagebox.showerror("Lembretes", "Não foi possível conectar à base de dados.", parent=janela)
                    return
                cur.executemany(
                    "UPDATE lembretes_clientes SET adiar_ate = ?, ultimo_aviso_em = ? WHERE id = ? AND status = 'Pendente'",
                    [(adiamento, agora_txt, rid) for rid in ids]
                )
                _inserir_auditoria(cur, "Lembretes adiados", detalhes=f"IDs: {', '.join(ids)}; até {adiamento}")
                con.commit()
                for iid in list(tabela.get_children()):
                    if str(tabela.item(iid, "values")[0]) in ids:
                        tabela.delete(iid)
                if not tabela.get_children():
                    fechar()
            except sqlite3.Error as erro:
                if con:
                    con.rollback()
                messagebox.showerror("Lembretes", f"Não foi possível adiar os lembretes:\n{erro}", parent=janela)
            finally:
                if con:
                    con.close()

        def concluir_selecionados():
            ids = ids_selecionados()
            if not ids:
                messagebox.showinfo("Lembretes", "Seleciona pelo menos um lembrete para concluir.", parent=janela)
                return
            agora_txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            con = None
            try:
                con, cur = conectar_banco()
                if con is None or cur is None:
                    messagebox.showerror("Lembretes", "Não foi possível conectar à base de dados.", parent=janela)
                    return
                cur.executemany(
                    "UPDATE lembretes_clientes SET status = 'Concluído', concluido_em = ?, adiar_ate = NULL WHERE id = ? AND status = 'Pendente'",
                    [(agora_txt, rid) for rid in ids]
                )
                _inserir_auditoria(cur, "Lembretes concluídos", detalhes=f"IDs: {', '.join(ids)}")
                con.commit()
                for iid in list(tabela.get_children()):
                    if str(tabela.item(iid, "values")[0]) in ids:
                        tabela.delete(iid)
                if not tabela.get_children():
                    fechar()
            except sqlite3.Error as erro:
                if con:
                    con.rollback()
                messagebox.showerror("Lembretes", f"Não foi possível concluir os lembretes:\n{erro}", parent=janela)
            finally:
                if con:
                    con.close()

        botoes = tk.Frame(janela, bg=COR_FUNDO)
        botoes.pack(fill="x", padx=18, pady=(5, 8))
        tk.Button(botoes, text="Ver lembretes", command=abrir_lista, font=FONTE_9_NEGRITO,
                  bg=COR_BOTAO, fg="white", relief="flat", padx=12, pady=6).pack(side="left", padx=(0, 5))
        tk.Button(botoes, text="Adiar 1 hora", command=adiar_selecionados, font=FONTE_9_NEGRITO,
                  bg=COR_PRINCIPAL, fg="white", relief="flat", padx=12, pady=6).pack(side="left", padx=5)
        tk.Button(botoes, text="Marcar concluído", command=concluir_selecionados, font=FONTE_9_NEGRITO,
                  bg="#198754", fg="white", relief="flat", padx=12, pady=6).pack(side="left", padx=5)
        tk.Button(botoes, text="Fechar", command=fechar, font=FONTE_9_NEGRITO,
                  bg="#e8eef5", fg=COR_TEXTO, relief="flat", padx=14, pady=6).pack(side="right")
        criar_rodape(janela)
    else:
        janela = existente
        tabela = _AVISO_LEMBRETES_TABELA
        if tabela is None:
            return

    # Acrescenta apenas os lembretes ainda não apresentados nesta janela.
    existentes_ids = {str(tabela.item(iid, "values")[0]) for iid in tabela.get_children()}
    for item in itens:
        rid = str(item["id"])
        if rid in existentes_ids:
            continue
        try:
            devido = _datetime_lembrete(item.get("data"), item.get("hora", "09:00"))
            devido_ui = devido.strftime("%d/%m/%Y %H:%M") if devido != datetime.max else f"{item.get('data', '')} {item.get('hora', '')}"
        except Exception:
            devido_ui = f"{item.get('data', '')} {item.get('hora', '')}"
        tabela.insert("", "end", values=(rid, item.get("cliente", ""), item.get("titulo", ""), devido_ui, item.get("descricao", "")))
        existentes_ids.add(rid)
    try:
        janela.lift()
        janela.focus_force()
    except tk.TclError:
        pass


def monitorar_lembretes_agendados(janela, usuario_logado, inicio=False):
    """Executa o resumo após login e continua a verificar lembretes a cada minuto."""
    try:
        if not janela.winfo_exists():
            return
    except tk.TclError:
        return
    resumo, avisos = obter_notificacoes_lembretes(inicio=inicio)
    if resumo:
        mostrar_aviso_lembretes(janela, usuario_logado, resumo, resumo_inicio=True)
    if avisos:
        mostrar_aviso_lembretes(janela, usuario_logado, avisos, resumo_inicio=False)
    try:
        # Resolver o utilizador no momento da execução para respeitar a troca de sessão.
        janela.after(60_000, lambda w=janela: monitorar_lembretes_agendados(
            w, USUARIO_AUDITORIA_ATUAL or usuario_logado, inicio=False
        ))
    except tk.TclError:
        pass


def abrir_lembretes(parent, usuario_logado):
    """Lista, cria, conclui e elimina lembretes associados a clientes."""
    existente = focar_janela_aberta("lembretes_clientes")
    if existente is not None:
        return existente

    janela = tk.Toplevel(parent)

    aplicar_icone_janela(janela)
    registar_janela_aberta("lembretes_clientes", janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Lembretes e tarefas")
    janela.geometry("960x590")
    centralizar_janela_na_area_util(janela, 960, 590)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)

    tk.Label(janela, text="Lembretes e tarefas de clientes", font=FONTE_15_NEGRITO,
             bg=COR_FUNDO, fg=COR_PRINCIPAL).pack(anchor="w", padx=18, pady=(12, 4))
    tk.Label(janela, text="Regista contactos futuros e acompanha tarefas pendentes ou concluídas.",
             font=FONTE_9, bg=COR_FUNDO, fg=COR_SECUNDARIA).pack(anchor="w", padx=18, pady=(0, 8))

    linha_filtro = tk.Frame(janela, bg=COR_FUNDO)
    linha_filtro.pack(fill="x", padx=18, pady=(0, 5))
    tk.Label(linha_filtro, text="Mostrar:", font=FONTE_9_NEGRITO, bg=COR_FUNDO, fg=COR_TEXTO).pack(side="left", padx=(0, 6))
    filtro_estado = tk.StringVar(value="Todos")
    combo_estado = ttk.Combobox(linha_filtro, textvariable=filtro_estado,
                                values=("Todos", "Pendentes", "Vencidos", "Concluídos", "Cancelados"),
                                state="readonly", width=14, font=FONTE_9)
    combo_estado.pack(side="left")

    arranque_var = tk.BooleanVar(value=arranque_windows_ativo())

    def alternar_arranque_windows():
        pedido = bool(arranque_var.get())
        try:
            ativo = configurar_arranque_windows(pedido)
            arranque_var.set(ativo)
            texto = (
                "O TB Software será iniciado automaticamente quando entrares no Windows."
                if ativo else "O arranque automático do TB Software foi desativado."
            )
            messagebox.showinfo("Arranque do Windows", texto, parent=janela)
        except (OSError, RuntimeError) as erro:
            arranque_var.set(arranque_windows_ativo())
            messagebox.showerror("Arranque do Windows", f"Não foi possível alterar o arranque automático:\n{erro}", parent=janela)

    tk.Checkbutton(
        linha_filtro,
        text="Iniciar com o Windows (para receber avisos)",
        variable=arranque_var,
        command=alternar_arranque_windows,
        font=FONTE_9,
        bg=COR_FUNDO,
        fg=COR_TEXTO,
        activebackground=COR_FUNDO,
        selectcolor=COR_PAINEL
    ).pack(side="left", padx=(18, 0))

    frame_tabela = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    frame_tabela.pack(fill="both", expand=True, padx=18, pady=5)
    colunas = ("id", "cliente", "titulo", "vencimento", "estado", "responsavel", "descricao")
    tabela = ttk.Treeview(frame_tabela, columns=colunas, show="headings", height=12)
    for col, titulo, largura in (
        ("id", "ID", 42), ("cliente", "Cliente", 160), ("titulo", "Tarefa", 160),
        ("vencimento", "Data / hora", 135), ("estado", "Estado", 90),
        ("responsavel", "Criado por", 100), ("descricao", "Descrição", 260)
    ):
        tabela.heading(col, text=titulo)
        tabela.column(col, width=largura, anchor="w")
    barra = ttk.Scrollbar(frame_tabela, orient="vertical", command=tabela.yview)
    tabela.configure(yscrollcommand=barra.set)
    tabela.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")

    def recarregar():
        for item in tabela.get_children():
            tabela.delete(item)
        con = None
        try:
            con, cur = conectar_banco()
            cur.execute("""
                SELECT l.id, c.nome, l.titulo, l.data_vencimento, l.status,
                       l.criado_por, COALESCE(l.descricao, ''), COALESCE(l.hora_vencimento, '09:00')
                FROM lembretes_clientes l
                LEFT JOIN clientes c ON c.id = l.cliente_id
                ORDER BY CASE WHEN l.status='Pendente' THEN 0 ELSE 1 END,
                         l.data_vencimento ASC, COALESCE(l.hora_vencimento, '09:00') ASC, l.id DESC
            """)
            agora_local = datetime.now()
            filtro = filtro_estado.get()
            for rid, nome, titulo, vencimento, status, criador, descricao, hora_vencimento in cur.fetchall():
                estado_ui = status
                try:
                    data_hora_vencimento = datetime.strptime(
                        f"{vencimento} {hora_vencimento or '09:00'}", "%Y-%m-%d %H:%M"
                    )
                except (ValueError, TypeError):
                    data_hora_vencimento = datetime.max
                if status == "Pendente" and data_hora_vencimento < agora_local:
                    estado_ui = "Vencido"
                if filtro == "Pendentes" and (status != "Pendente" or estado_ui == "Vencido"):
                    continue
                if filtro == "Vencidos" and estado_ui != "Vencido":
                    continue
                if filtro == "Concluídos" and status != "Concluído":
                    continue
                if filtro == "Cancelados" and status != "Cancelado":
                    continue
                try:
                    vencimento_ui = data_hora_vencimento.strftime("%d/%m/%Y %H:%M")
                except (ValueError, TypeError):
                    vencimento_ui = f"{vencimento or ''} {hora_vencimento or ''}".strip()
                tabela.insert("", "end", values=(rid, nome or "(cliente removido)", titulo, vencimento_ui,
                                                    estado_ui, criador, descricao))
        except sqlite3.Error as erro:
            messagebox.showerror("Lembretes", f"Não foi possível carregar as tarefas:\n{erro}", parent=janela)
        finally:
            if con:
                con.close()

    def novo_lembrete():
        con = None
        try:
            con, cur = conectar_banco()
            cur.execute("SELECT id, nome FROM clientes ORDER BY nome COLLATE NOCASE")
            clientes_disponiveis = cur.fetchall()
        except sqlite3.Error as erro:
            messagebox.showerror("Lembretes", f"Não foi possível carregar os clientes:\n{erro}", parent=janela)
            return
        finally:
            if con:
                con.close()
        if not clientes_disponiveis:
            messagebox.showinfo("Lembretes", "Cadastra primeiro um cliente para poder associar uma tarefa.", parent=janela)
            return

        editor = tk.Toplevel(janela)

        aplicar_icone_janela(editor)
        registrar_tema_janela(editor)
        editor.title("Novo lembrete")
        editor.geometry("540x510")
        centralizar_janela_na_area_util(editor, 540, 510)
        editor.resizable(False, False)
        editor.configure(bg=COR_FUNDO)
        editor.transient(janela)
        editor.grab_set()
        tk.Label(editor, text="NOVO LEMBRETE", font=FONTE_14_NEGRITO,
                 bg=COR_FUNDO, fg=COR_PRINCIPAL).pack(pady=(14, 8))
        form = tk.Frame(editor, bg=COR_PAINEL, bd=1, relief="solid")
        form.pack(fill="both", expand=True, padx=20, pady=5)
        form.columnconfigure(0, weight=1)
        tk.Label(form, text="Cliente *", font=FONTE_9_NEGRITO, bg=COR_PAINEL, fg=COR_TEXTO).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))
        escolhas = [f"{cid} — {nome}" for cid, nome in clientes_disponiveis]
        mapa = {f"{cid} — {nome}": cid for cid, nome in clientes_disponiveis}
        cliente_var = tk.StringVar(value=escolhas[0])
        combo_cliente = ttk.Combobox(form, textvariable=cliente_var, values=escolhas, state="readonly", font=FONTE_9)
        combo_cliente.grid(row=1, column=0, sticky="ew", padx=14)
        tk.Label(form, text="Tarefa / assunto *", font=FONTE_9_NEGRITO, bg=COR_PAINEL, fg=COR_TEXTO).grid(row=2, column=0, sticky="w", padx=14, pady=(9, 4))
        entrada_titulo = tk.Entry(form, font=FONTE_9)
        entrada_titulo.grid(row=3, column=0, sticky="ew", padx=14)
        tk.Label(form, text="Data de vencimento (DD/MM/AAAA) *", font=FONTE_9_NEGRITO, bg=COR_PAINEL, fg=COR_TEXTO).grid(row=4, column=0, sticky="w", padx=14, pady=(9, 4))
        entrada_data = tk.Entry(form, font=FONTE_9)
        entrada_data.grid(row=5, column=0, sticky="ew", padx=14)
        entrada_data.insert(0, date.today().strftime("%d/%m/%Y"))
        tk.Label(form, text="Hora do aviso (HH:MM) *", font=FONTE_9_NEGRITO, bg=COR_PAINEL, fg=COR_TEXTO).grid(row=6, column=0, sticky="w", padx=14, pady=(9, 4))
        entrada_hora = tk.Entry(form, font=FONTE_9)
        entrada_hora.grid(row=7, column=0, sticky="ew", padx=14)
        entrada_hora.insert(0, "09:00")
        tk.Label(form, text="Descrição (opcional)", font=FONTE_9_NEGRITO, bg=COR_PAINEL, fg=COR_TEXTO).grid(row=8, column=0, sticky="w", padx=14, pady=(9, 4))
        texto = tk.Text(form, height=3, wrap="word", font=FONTE_9)
        texto.grid(row=9, column=0, sticky="nsew", padx=14, pady=(0, 12))
        form.rowconfigure(9, weight=1)

        def guardar():
            nome_cliente = cliente_var.get().strip()
            titulo = entrada_titulo.get().strip()
            data_txt = entrada_data.get().strip()
            hora_txt = entrada_hora.get().strip()
            descricao = texto.get("1.0", "end-1c").strip()
            if nome_cliente not in mapa or not titulo:
                messagebox.showerror("Lembrete", "Seleciona um cliente e escreve o assunto da tarefa.", parent=editor)
                return
            try:
                data_iso = datetime.strptime(data_txt, "%d/%m/%Y").date().isoformat()
            except ValueError:
                messagebox.showerror("Data inválida", "Introduz uma data válida no formato DD/MM/AAAA.", parent=editor)
                entrada_data.focus_set()
                return
            try:
                hora_obj = datetime.strptime(hora_txt, "%H:%M")
                if hora_obj.strftime("%H:%M") != hora_txt:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Hora inválida", "Introduz uma hora válida no formato HH:MM, por exemplo 14:30.", parent=editor)
                entrada_hora.focus_set()
                return
            con2 = None
            try:
                con2, cur2 = conectar_banco()
                cur2.execute("""
                    INSERT INTO lembretes_clientes
                        (cliente_id, titulo, descricao, data_vencimento, hora_vencimento,
                         status, criado_em, criado_por)
                    VALUES (?, ?, ?, ?, ?, 'Pendente', ?, ?)
                """, (mapa[nome_cliente], titulo[:160], descricao[:3000], data_iso, hora_txt,
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S"), usuario_logado or "Sistema"))
                _inserir_auditoria(cur2, "Lembrete criado", cliente_id=mapa[nome_cliente], detalhes=f"Tarefa: {titulo}")
                con2.commit()
                editor.destroy()
                recarregar()
            except sqlite3.Error as erro:
                if con2:
                    con2.rollback()
                messagebox.showerror("Erro", f"Não foi possível guardar o lembrete:\n{erro}", parent=editor)
            finally:
                if con2:
                    con2.close()

        botoes_editor = tk.Frame(editor, bg=COR_FUNDO)
        botoes_editor.pack(fill="x", padx=20, pady=(5, 12))
        tk.Button(botoes_editor, text="Guardar", command=guardar, font=FONTE_9_NEGRITO,
                  bg=COR_BOTAO, fg="white", relief="flat", padx=16, pady=5).pack(side="left")
        tk.Button(botoes_editor, text="Cancelar", command=editor.destroy, font=FONTE_9_NEGRITO,
                  bg="#e8eef5", fg=COR_TEXTO, relief="flat", padx=16, pady=5).pack(side="right")

    def obter_id_selecionado():
        selecao = tabela.selection()
        if not selecao:
            messagebox.showwarning("Lembretes", "Seleciona um lembrete primeiro.", parent=janela)
            return None
        return str(tabela.item(selecao[0], "values")[0])

    def alternar_conclusao():
        rid = obter_id_selecionado()
        if rid is None:
            return
        valores = tabela.item(tabela.selection()[0], "values")
        estado_atual = str(valores[4])
        novo_status = "Pendente" if estado_atual == "Concluído" else "Concluído"
        con = None
        try:
            con, cur = conectar_banco()
            cur.execute("UPDATE lembretes_clientes SET status=?, concluido_em=? WHERE id=?",
                        (novo_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S") if novo_status == "Concluído" else None, rid))
            _inserir_auditoria(cur, "Lembrete atualizado", detalhes=f"ID {rid}; estado {novo_status}")
            con.commit()
            recarregar()
        except sqlite3.Error as erro:
            if con:
                con.rollback()
            messagebox.showerror("Erro", f"Não foi possível atualizar o lembrete:\n{erro}", parent=janela)
        finally:
            if con:
                con.close()

    def excluir_lembrete():
        rid = obter_id_selecionado()
        if rid is None:
            return
        if not messagebox.askyesno("Excluir lembrete", "Desejas excluir o lembrete selecionado?", parent=janela):
            return
        con = None
        try:
            con, cur = conectar_banco()
            cur.execute("DELETE FROM lembretes_clientes WHERE id=?", (rid,))
            _inserir_auditoria(cur, "Lembrete excluído", detalhes=f"ID {rid}")
            con.commit()
            recarregar()
        except sqlite3.Error as erro:
            if con:
                con.rollback()
            messagebox.showerror("Erro", f"Não foi possível excluir o lembrete:\n{erro}", parent=janela)
        finally:
            if con:
                con.close()

    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(fill="x", padx=18, pady=(4, 5))
    tk.Button(botoes, text="Novo lembrete", command=novo_lembrete, font=FONTE_9_NEGRITO,
              bg=COR_BOTAO, fg="white", relief="flat", padx=12, pady=6).pack(side="left", padx=(0, 5))
    tk.Button(botoes, text="Concluir / reabrir", command=alternar_conclusao, font=FONTE_9_NEGRITO,
              bg=COR_PRINCIPAL, fg="white", relief="flat", padx=12, pady=6).pack(side="left", padx=5)
    tk.Button(botoes, text="Excluir", command=excluir_lembrete, font=FONTE_9_NEGRITO,
              bg="#b93131", fg="white", relief="flat", padx=12, pady=6).pack(side="left", padx=5)
    tk.Button(botoes, text="Fechar", command=janela.destroy, font=FONTE_9_NEGRITO,
              bg="#e8eef5", fg=COR_TEXTO, relief="flat", padx=16, pady=6).pack(side="right")
    combo_estado.bind("<<ComboboxSelected>>", lambda _e: recarregar())
    criar_rodape(janela)
    recarregar()
    return janela


def abrir_relatorios(parent):
    existente = focar_janela_aberta("relatorios")
    if existente is not None:
        return existente

    janela = tk.Toplevel(parent)

    aplicar_icone_janela(janela)
    registar_janela_aberta("relatorios", janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Relatórios")
    janela.geometry("980x780")
    centralizar_janela_na_area_util(janela, 980, 780)
    janela.resizable(True, True)
    janela.configure(bg=COR_FUNDO)

    tk.Label(janela, text="Relatórios e indicadores", font=FONTE_14_NEGRITO,
             bg=COR_FUNDO, fg=COR_PRINCIPAL).pack(anchor="w", padx=18, pady=(10, 3))
    tk.Label(janela, text="Filtra os cadastros por período e consulta a distribuição dos clientes.",
             font=FONTE_8, bg=COR_FUNDO, fg=COR_SECUNDARIA).pack(anchor="w", padx=18, pady=(0, 5))

    filtros = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    filtros.pack(fill="x", padx=18, pady=(2, 6))
    tk.Label(filtros, text="Desde (DD/MM/AAAA):", font=FONTE_8_NEGRITO,
             bg=COR_PAINEL, fg=COR_TEXTO).pack(side="left", padx=(12, 5), pady=7)
    entrada_inicio = tk.Entry(filtros, width=12, font=FONTE_8)
    entrada_inicio.pack(side="left", pady=7)
    tk.Label(filtros, text="Até (DD/MM/AAAA):", font=FONTE_8_NEGRITO,
             bg=COR_PAINEL, fg=COR_TEXTO).pack(side="left", padx=(12, 5), pady=7)
    entrada_fim = tk.Entry(filtros, width=12, font=FONTE_8)
    entrada_fim.pack(side="left", pady=7)
    aviso_datas = tk.Label(filtros, text="Sem datas = todos os clientes", font=FONTE_8,
                           bg=COR_PAINEL, fg=COR_SECUNDARIA)
    aviso_datas.pack(side="left", padx=12, pady=7)

    cards_frame = tk.Frame(janela, bg=COR_FUNDO)
    cards_frame.pack(fill="x", padx=18, pady=(0, 5))
    cards = {}
    for col, titulo, cor in (
        (0, "Total de clientes", "#126dcc"),
        (1, "Particulares", "#159b70"),
        (2, "Empresas", "#e88916"),
    ):
        card = tk.Frame(cards_frame, bg=COR_PAINEL, bd=1, relief="solid")
        card.grid(row=0, column=col, sticky="nsew", padx=4)
        cards_frame.columnconfigure(col, weight=1)
        valor = tk.Label(card, text="0", font=FONTE_20_NEGRITO, bg=COR_PAINEL, fg=cor)
        valor.pack(pady=(7, 0))
        tk.Label(card, text=titulo, font=FONTE_8_NEGRITO, bg=COR_PAINEL, fg=COR_TEXTO).pack(pady=(0, 7))
        cards[titulo] = valor

    graficos = tk.Frame(janela, bg=COR_FUNDO)
    graficos.pack(fill="x", padx=18, pady=(1, 5))
    graficos.columnconfigure(0, weight=1, uniform="graficos")
    graficos.columnconfigure(1, weight=1, uniform="graficos")
    graficos.columnconfigure(2, weight=1, uniform="graficos")
    canvases = {}
    for coluna, chave, titulo in (
        (0, "paises", "Clientes por país"),
        (1, "tipos", "Clientes por tipo"),
        (2, "meses", "Novos clientes por mês"),
    ):
        moldura = tk.Frame(graficos, bg=COR_PAINEL, bd=1, relief="solid")
        moldura.grid(row=0, column=coluna, sticky="nsew", padx=4)
        canvas = tk.Canvas(moldura, height=128, bg=COR_PAINEL, highlightthickness=0, borderwidth=0)
        canvas.pack(fill="both", expand=True, padx=4, pady=3)
        canvases[chave] = (canvas, titulo)

    tk.Label(janela, text="Clientes por localidade", font=FONTE_9_NEGRITO,
             bg=COR_FUNDO, fg=COR_TEXTO).pack(anchor="w", padx=21, pady=(2, 3))
    frame_tabela = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    frame_tabela.pack(fill="both", expand=True, padx=18, pady=(0, 5))
    tabela = ttk.Treeview(frame_tabela, columns=("localidade", "pais", "quantidade"),
                          show="headings", height=4)
    for coluna, titulo, largura in (("localidade", "Localidade", 340), ("pais", "País", 260), ("quantidade", "Clientes", 100)):
        tabela.heading(coluna, text=titulo)
        tabela.column(coluna, width=largura, anchor="w" if coluna != "quantidade" else "center")
    barra = ttk.Scrollbar(frame_tabela, orient="vertical", command=tabela.yview)
    tabela.configure(yscrollcommand=barra.set)
    tabela.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
    barra.pack(side="right", fill="y", pady=4, padx=(0, 4))

    rodape_texto = tk.Label(janela,
        text="Clientes antigos sem data de cadastro conhecida aparecem nos totais gerais, mas não entram em períodos filtrados.",
        font=FONTE_8, bg=COR_FUNDO, fg=COR_SECUNDARIA, anchor="w")
    rodape_texto.pack(fill="x", padx=20, pady=(0, 2))
    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(fill="x", padx=18, pady=(0, 4))
    criar_rodape(janela)

    dados_graficos = {"paises": [], "tipos": [], "meses": []}

    def desenhar_grafico(chave):
        canvas, titulo = canvases[chave]
        canvas.delete("all")
        largura = max(220, canvas.winfo_width())
        altura = max(100, canvas.winfo_height())
        canvas.create_text(10, 7, text=titulo, anchor="nw", fill=COR_TEXTO, font=FONTE_8_NEGRITO)
        dados = dados_graficos.get(chave, [])
        if not dados:
            canvas.create_text(largura // 2, altura // 2, text="Sem dados para mostrar", fill=COR_SECUNDARIA, font=FONTE_8)
            return
        dados = dados[-6:] if chave == "meses" else dados[:5]
        max_val = max((int(v) for _l, v in dados), default=0) or 1
        label_w = min(96, max(62, largura // 3))
        bar_left = label_w + 8
        bar_right = largura - 32
        bar_max = max(5, bar_right - bar_left)
        row_h = max(14, (altura - 27) // max(1, len(dados)))
        for i, (rotulo, valor) in enumerate(dados):
            y = 25 + i * row_h
            label = str(rotulo)
            if len(label) > 15:
                label = label[:14] + "…"
            canvas.create_text(5, y + row_h / 2, text=label, anchor="w", fill=COR_TEXTO, font=FONTE_8)
            bar_w = int(bar_max * int(valor) / max_val)
            canvas.create_rectangle(bar_left, y + 3, bar_left + bar_w, y + row_h - 3,
                                    fill=COR_BOTAO, outline="")
            canvas.create_text(min(largura - 18, bar_left + bar_w + 15), y + row_h / 2,
                               text=str(valor), anchor="w", fill=COR_TEXTO, font=FONTE_8)

    def ler_data_filtro(entrada, rotulo):
        texto = entrada.get().strip()
        if not texto:
            return None
        try:
            return datetime.strptime(texto, "%d/%m/%Y").date().isoformat()
        except ValueError:
            raise ValueError(f"A data '{rotulo}' deve ser válida e estar no formato DD/MM/AAAA.")

    def atualizar_relatorio():
        try:
            inicio_iso = ler_data_filtro(entrada_inicio, "Desde")
            fim_iso = ler_data_filtro(entrada_fim, "Até")
            if inicio_iso and fim_iso and inicio_iso > fim_iso:
                raise ValueError("A data inicial não pode ser posterior à data final.")
        except ValueError as erro:
            messagebox.showerror("Período inválido", str(erro), parent=janela)
            return

        clausulas = []
        parametros = []
        if inicio_iso:
            clausulas.append("date(data_cadastro) >= date(?)")
            parametros.append(inicio_iso)
        if fim_iso:
            clausulas.append("date(data_cadastro) <= date(?)")
            parametros.append(fim_iso)
        where = (" WHERE " + " AND ".join(clausulas)) if clausulas else ""
        con = None
        try:
            con, cur = conectar_banco()
            cur.execute(f"SELECT COUNT(*) FROM clientes{where}", parametros)
            total = int(cur.fetchone()[0] or 0)
            cur.execute(f"""SELECT COALESCE(tipo_cliente, 'Particular'), COUNT(*)
                            FROM clientes{where} GROUP BY COALESCE(tipo_cliente, 'Particular')""", parametros)
            por_tipo = {str(t): int(q) for t, q in cur.fetchall()}
            particulares = sum(q for t, q in por_tipo.items() if t.casefold() != "empresa")
            empresas = por_tipo.get("Empresa", 0)
            cur.execute(f"""SELECT COALESCE(NULLIF(TRIM(pais), ''), 'Não informado'), COUNT(*)
                            FROM clientes{where}
                            GROUP BY COALESCE(NULLIF(TRIM(pais), ''), 'Não informado')
                            ORDER BY COUNT(*) DESC, 1 COLLATE NOCASE""", parametros)
            por_pais = [(str(label), int(q)) for label, q in cur.fetchall()]
            cur.execute(f"""SELECT COALESCE(NULLIF(TRIM(cidade), ''), 'Não informado'),
                                   COALESCE(NULLIF(TRIM(pais), ''), 'Não informado'), COUNT(*)
                            FROM clientes{where}
                            GROUP BY COALESCE(NULLIF(TRIM(cidade), ''), 'Não informado'),
                                     COALESCE(NULLIF(TRIM(pais), ''), 'Não informado')
                            ORDER BY COUNT(*) DESC, 1 COLLATE NOCASE""", parametros)
            por_localidade = cur.fetchall()
            cur.execute(f"""SELECT substr(data_cadastro, 1, 7), COUNT(*)
                            FROM clientes{where}{' AND ' if where else ' WHERE '}data_cadastro IS NOT NULL AND TRIM(data_cadastro) != ''
                            GROUP BY substr(data_cadastro, 1, 7) ORDER BY substr(data_cadastro, 1, 7)""", parametros)
            por_mes = {str(m): int(q) for m, q in cur.fetchall() if m}
        except sqlite3.Error as erro:
            messagebox.showerror("Relatórios", f"Não foi possível atualizar os relatórios:\n{erro}", parent=janela)
            return
        finally:
            if con:
                con.close()

        cards["Total de clientes"].config(text=str(total))
        cards["Particulares"].config(text=str(particulares))
        cards["Empresas"].config(text=str(empresas))
        dados_graficos["paises"] = por_pais[:5]
        dados_graficos["tipos"] = [("Particulares", particulares), ("Empresas", empresas)]

        if inicio_iso or fim_iso:
            meses = sorted(por_mes.items())[-6:]
        else:
            hoje = date.today()
            indices = []
            for offset in range(5, -1, -1):
                numero = hoje.year * 12 + (hoje.month - 1) - offset
                ano, mes0 = divmod(numero, 12)
                indices.append(f"{ano:04d}-{mes0 + 1:02d}")
            meses = [(m, por_mes.get(m, 0)) for m in indices]
        def rotulo_mes(iso_mes):
            try:
                return datetime.strptime(iso_mes, "%Y-%m").strftime("%m/%y")
            except ValueError:
                return iso_mes
        dados_graficos["meses"] = [(rotulo_mes(m), q) for m, q in meses]

        for item in tabela.get_children():
            tabela.delete(item)
        for localidade, pais, quantidade in por_localidade:
            tabela.insert("", "end", values=(localidade, pais, quantidade))
        aviso_datas.config(text=("Período aplicado" if inicio_iso or fim_iso else "Sem datas = todos os clientes"))
        for chave in canvases:
            desenhar_grafico(chave)

    def limpar_periodo():
        entrada_inicio.delete(0, tk.END)
        entrada_fim.delete(0, tk.END)
        atualizar_relatorio()

    tk.Button(filtros, text="Aplicar", command=atualizar_relatorio,
              font=FONTE_8_NEGRITO, bg=COR_BOTAO, fg="white", relief="flat", padx=10, pady=4).pack(side="left", padx=(12, 4), pady=4)
    tk.Button(filtros, text="Limpar", command=limpar_periodo,
              font=FONTE_8_NEGRITO, bg="#e8eef5", fg=COR_TEXTO, relief="flat", padx=10, pady=4).pack(side="left", padx=4, pady=4)
    tk.Button(botoes, text="Atualizar", command=atualizar_relatorio,
              font=FONTE_9_NEGRITO, bg=COR_BOTAO, fg="white", relief="flat", padx=14, pady=5).pack(side="left")
    tk.Button(botoes, text="Fechar", command=janela.destroy,
              font=FONTE_9_NEGRITO, bg="#e8eef5", fg=COR_TEXTO, relief="flat", padx=18, pady=5).pack(side="right")
    for chave, (canvas, _titulo) in canvases.items():
        canvas.bind("<Configure>", lambda _e, k=chave: desenhar_grafico(k), add="+")
    atualizar_relatorio()
    return janela



def obter_registos_clientes_exportacao():
    """Retorna cabeçalhos e dados normalizados para CSV, Excel e PDF."""
    cabecalhos = (
        "ID", "Nome", "Identificação Fiscal", "Passaporte", "Tipo de Cliente",
        "Morada", "Telefone", "Localidade", "Data de Nascimento", "Nacionalidade",
        "Telemóvel", "Email", "Código Postal", "País"
    )
    con = None
    try:
        con, cur = conectar_banco()
        if con is None:
            raise RuntimeError("Não foi possível conectar ao banco de dados.")
        cur.execute("""
            SELECT id, nome, nif, passaporte, COALESCE(tipo_cliente, 'Particular'),
                   endereco, telefone, cidade, data_nascimento, nacionalidade,
                   movel, email, codigo_postal, pais
            FROM clientes ORDER BY nome COLLATE NOCASE
        """)
        dados = cur.fetchall()
        return cabecalhos, dados
    finally:
        if con:
            con.close()



def _nome_coluna_excel(numero):
    nome = ""
    while numero:
        numero, resto = divmod(numero - 1, 26)
        nome = chr(65 + resto) + nome
    return nome


def _xml_seguro(valor):
    from xml.sax.saxutils import escape
    texto = "" if valor is None else str(valor)
    texto = "".join(ch for ch in texto if ch in "\t\n\r" or ord(ch) >= 32)
    return escape(texto)


def _escrever_excel_xlsx_basico(caminho, cabecalhos, registos):
    """Cria um .xlsx válido apenas com a biblioteca standard, caso openpyxl não esteja instalado."""
    total_linhas = len(registos) + 1
    total_colunas = len(cabecalhos)
    ultima_coluna = _nome_coluna_excel(total_colunas)
    linhas_xml = []
    linhas = [cabecalhos, *registos]
    for num_linha, linha in enumerate(linhas, start=1):
        celulas = []
        for num_coluna, valor in enumerate(linha, start=1):
            ref = f"{_nome_coluna_excel(num_coluna)}{num_linha}"
            estilo = ' s="1"' if num_linha == 1 else ""
            texto = _xml_seguro(valor)
            celulas.append(
                f'<c r="{ref}" t="inlineStr"{estilo}><is><t xml:space="preserve">{texto}</t></is></c>'
            )
        linhas_xml.append(f'<row r="{num_linha}">{"".join(celulas)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="A1:{ultima_coluna}{max(1,total_linhas)}"/>'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'<sheetData>{"".join(linhas_xml)}</sheetData>'
        f'<autoFilter ref="A1:{ultima_coluna}{max(1,total_linhas)}"/>'
        '</worksheet>'
    )
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
      <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
      <Default Extension="xml" ContentType="application/xml"/>
      <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
      <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
      <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
    </Types>"""
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
      <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
    </Relationships>"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
      <bookViews><workbookView/></bookViews><sheets><sheet name="Clientes" sheetId="1" r:id="rId1"/></sheets>
    </workbook>"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
      <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
      <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
    </Relationships>"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>
      <fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF022C53"/><bgColor indexed="64"/></patternFill></fill></fills>
      <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
      <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
      <cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="1" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>
      <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
    </styleSheet>"""
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as arquivo:
        arquivo.writestr("[Content_Types].xml", content_types)
        arquivo.writestr("_rels/.rels", root_rels)
        arquivo.writestr("xl/workbook.xml", workbook)
        arquivo.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        arquivo.writestr("xl/worksheets/sheet1.xml", sheet)
        arquivo.writestr("xl/styles.xml", styles)


def _escrever_pdf_basico(caminho, cabecalhos, registos):
    """Gera um PDF simples paginado sem dependências externas."""
    largura, altura = 842, 595  # A4 horizontal em pontos
    colunas = (0, 1, 2, 3, 6, 7, 13, 4)
    titulos = [cabecalhos[i] for i in colunas]
    larguras = [30, 170, 88, 90, 88, 112, 90, 74]
    x_inicial = 25
    def pdf_text(texto):
        # Helvetica com WinAnsiEncoding representa acentos portugueses.
        return str(texto or "").encode("cp1252", errors="replace").hex().upper()
    paginas_conteudo = []
    por_pagina = 39
    blocos = [registos[i:i + por_pagina] for i in range(0, len(registos), por_pagina)] or [[]]
    for num_pagina, bloco in enumerate(blocos, start=1):
        c = ["q", "0.95 0.96 0.98 rg", "0 0 842 595 re f", "Q"]
        c.extend(["BT /F2 16 Tf 25 560 Td <" + pdf_text("TB Software - Relatório de Clientes") + "> Tj ET"])
        subtitulo = f"Gerado em {datetime.now():%d/%m/%Y %H:%M} | Total: {len(registos)} clientes | Página {num_pagina}/{len(blocos)}"
        c.append("BT /F1 8 Tf 25 543 Td <" + pdf_text(subtitulo) + "> Tj ET")
        y_header = 522
        c.extend(["0.008 0.173 0.325 rg", f"{x_inicial} {y_header-5} 792 19 re f"])
        x = x_inicial
        for idx, (titulo, w) in enumerate(zip(titulos, larguras)):
            c.append(f"BT /F2 7 Tf {x+3} {y_header+2} Td <{pdf_text(titulo[:23])}> Tj ET")
            x += w
        y = 501
        for row_index, row in enumerate(bloco):
            if row_index % 2 == 0:
                c.extend(["0.88 0.91 0.94 rg", f"{x_inicial} {y-4} 792 12 re f"])
            x = x_inicial
            for col_idx, w in zip(colunas, larguras):
                valor = str(row[col_idx] or "")
                max_chars = max(4, int(w / 4.1))
                if len(valor) > max_chars:
                    valor = valor[:max_chars-1] + "…"
                c.append(f"BT /F1 6.7 Tf {x+3} {y} Td <{pdf_text(valor)}> Tj ET")
                x += w
            y -= 12
        c.append("BT /F1 7 Tf 25 18 Td <" + pdf_text("TB Software | Relatório de clientes") + "> Tj ET")
        paginas_conteudo.append("\n".join(c).encode("ascii"))

    objetos = []
    # Reservar objetos para catálogo, páginas e fontes; depois páginas/conteúdos.
    objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    filhos = []
    primeiro_id = 5
    for i in range(len(paginas_conteudo)):
        filhos.append(f"{primeiro_id + i*2} 0 R")
    objetos.append((f"<< /Type /Pages /Kids [{' '.join(filhos)}] /Count {len(paginas_conteudo)} >>").encode("ascii"))
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    for i, conteudo in enumerate(paginas_conteudo):
        page_id = 5 + i*2
        stream_id = page_id + 1
        objetos.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {largura} {altura}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {stream_id} 0 R >>").encode("ascii"))
        objetos.append(b"<< /Length " + str(len(conteudo)).encode("ascii") + b" >>\nstream\n" + conteudo + b"\nendstream")
    saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for numero, objeto in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida.extend(f"{numero} 0 obj\n".encode("ascii"))
        saida.extend(objeto)
        saida.extend(b"\nendobj\n")
    xref = len(saida)
    saida.extend(f"xref\n0 {len(objetos)+1}\n".encode("ascii"))
    saida.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        saida.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    saida.extend(f"trailer\n<< /Size {len(objetos)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    Path(caminho).write_bytes(saida)


def _exportar_pdf_relatorio(caminho, cabecalhos, registos):
    """Usa reportlab se instalado, com fallback integrado caso contrário."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from xml.sax.saxutils import escape
    except ImportError:
        _escrever_pdf_basico(caminho, cabecalhos, registos)
        return

    indices = (0, 1, 2, 3, 6, 7, 13, 4)
    cabecalhos_pdf = [cabecalhos[i] for i in indices]
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloTB", parent=estilos["Title"], fontName="Helvetica-Bold",
        fontSize=15, leading=18, alignment=TA_CENTER, textColor=colors.HexColor("#022c53")
    )
    pequeno = ParagraphStyle("CelulaTB", parent=estilos["BodyText"], fontName="Helvetica", fontSize=6.5, leading=8)
    dados_pdf = [[Paragraph(escape(str(v or "")), pequeno) for v in cabecalhos_pdf]]
    for registo in registos:
        dados_pdf.append([Paragraph(escape(str(registo[i] or "")), pequeno) for i in indices])
    documento = SimpleDocTemplate(
        caminho, pagesize=landscape(A4), leftMargin=18, rightMargin=18,
        topMargin=25, bottomMargin=25, title="Relatório de Clientes - TB Software"
    )
    tabela = Table(dados_pdf, repeatRows=1, colWidths=[28, 150, 70, 82, 78, 105, 72, 65])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#022c53")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c7d1dd")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6fa")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    documento.build([
        Paragraph("TB Software — Relatório de Clientes", titulo), Spacer(1, 5),
        Paragraph(f"Gerado em {datetime.now():%d/%m/%Y %H:%M} · Total de clientes: {len(registos)}", estilos["Normal"]),
        Spacer(1, 10), tabela
    ])


def _gerar_pdf_ficha_cliente(caminho, titulo, campos):
    """Gera uma ficha individual em PDF, sem exigir bibliotecas externas."""
    import textwrap

    largura_pagina, altura_pagina = 595, 842  # A4 vertical em pontos

    def texto_pdf(valor):
        return str(valor or "").encode("cp1252", errors="replace").hex().upper()

    linhas_campos = []
    for rotulo, valor in campos:
        texto_valor = str(valor).strip() if valor is not None else ""
        if not texto_valor:
            texto_valor = "—"
        linhas_valor = textwrap.wrap(
            texto_valor, width=54, break_long_words=True, break_on_hyphens=False
        ) or ["—"]
        linhas_campos.append((str(rotulo), linhas_valor))

    paginas = []
    comandos = []
    y = 755
    linha_faixa = 0

    def iniciar_pagina(numero_pagina):
        # A marca-d'água é desenhada primeiro, em cinzento muito claro,
        # para ficar atrás dos dados e não prejudicar a leitura.
        return [
            "q", "1 1 1 rg", f"0 0 {largura_pagina} {altura_pagina} re f", "Q",
            "q", "0.91 0.93 0.95 rg",
            "BT /F2 47 Tf 0.819 0.574 -0.574 0.819 78 335 Tm <" + texto_pdf("TB SOFTWARE") + "> Tj ET",
            "BT /F1 13 Tf 0.819 0.574 -0.574 0.819 176 320 Tm <" + texto_pdf("SOLUCOES QUE FACILITAM SEU TRABALHO") + "> Tj ET",
            "Q",
            "0.008 0.173 0.325 rg", "35 786 525 32 re f",
            "1 1 1 rg",
            "BT /F2 14 Tf 45 798 Td <" + texto_pdf(titulo) + "> Tj ET",
            "0.20 0.24 0.30 rg",
            "BT /F1 8 Tf 37 771 Td <" + texto_pdf(f"TB Software | Gerado em {datetime.now():%d/%m/%Y %H:%M}") + "> Tj ET",
        ]

    comandos = iniciar_pagina(1)
    pagina = 1
    for rotulo, linhas_valor in linhas_campos:
        altura_linha = 18 + (len(linhas_valor) - 1) * 11
        if y - altura_linha < 55:
            comandos.append("0.20 0.24 0.30 rg")
            comandos.append("BT /F1 7 Tf 37 25 Td <" + texto_pdf(f"Página {pagina}") + "> Tj ET")
            paginas.append("\n".join(comandos).encode("ascii"))
            pagina += 1
            comandos = iniciar_pagina(pagina)
            y = 755
            linha_faixa = 0

        if linha_faixa % 2 == 0:
            comandos.extend(["0.94 0.96 0.98 rg", f"38 {y-altura_linha+1} 519 {altura_linha} re f"])
        # Repõe uma cor escura depois de desenhar a faixa, evitando texto invisível.
        comandos.append("0.10 0.14 0.20 rg")
        comandos.append(f"BT /F2 8 Tf 46 {y-11} Td <{texto_pdf(rotulo)}> Tj ET")
        for indice, linha_valor in enumerate(linhas_valor):
            baseline = y - 11 - indice * 11
            comandos.append(f"BT /F1 9 Tf 178 {baseline} Td <{texto_pdf(linha_valor)}> Tj ET")
        y -= altura_linha + 2
        linha_faixa += 1

    comandos.append("0.20 0.24 0.30 rg")
    comandos.append("BT /F1 7 Tf 37 25 Td <" + texto_pdf(f"Página {pagina}") + "> Tj ET")
    paginas.append("\n".join(comandos).encode("ascii"))

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    ids_paginas = [5 + i * 2 for i in range(len(paginas))]
    objetos[1] = (f"<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in ids_paginas)}] /Count {len(paginas)} >>").encode("ascii")
    for idx, conteudo in enumerate(paginas):
        id_pagina = 5 + idx * 2
        id_stream = id_pagina + 1
        objetos.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {largura_pagina} {altura_pagina}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {id_stream} 0 R >>").encode("ascii"))
        objetos.append(b"<< /Length " + str(len(conteudo)).encode("ascii") + b" >>\nstream\n" + conteudo + b"\nendstream")

    saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for numero, objeto in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida.extend(f"{numero} 0 obj\n".encode("ascii"))
        saida.extend(objeto)
        saida.extend(b"\nendobj\n")
    xref = len(saida)
    saida.extend(f"xref\n0 {len(objetos)+1}\n".encode("ascii"))
    saida.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        saida.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    saida.extend(f"trailer\n<< /Size {len(objetos)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    Path(caminho).write_bytes(saida)


def _campos_ficha_cliente(cliente, completa=True):
    """Monta os campos da ficha completa ou resumida a partir do registo SQL."""
    campos = [
        ("ID", cliente[0]),
        ("Nome", cliente[1]),
        ("Identificação fiscal / NIF", cliente[2]),
        ("Passaporte", cliente[13] if len(cliente) > 13 else ""),
        ("Morada", cliente[3]),
        ("Telefone", cliente[4]),
        ("Localidade", cliente[5]),
        ("Tipo de cliente", cliente[6]),
        ("Data de nascimento", data_nascimento_para_tela(cliente[7]) if cliente[7] else ""),
        ("Nacionalidade", cliente[8]),
        ("Telemóvel", cliente[9]),
        ("E-mail", cliente[10]),
        ("Código postal", cliente[11]),
        ("País", cliente[12]),
    ]
    if completa:
        return campos
    campos_principais = {
        "ID", "Nome", "Identificação fiscal / NIF", "Passaporte",
        "Tipo de cliente", "Telefone", "Telemóvel", "E-mail",
        "Morada", "Localidade", "Código postal", "País"
    }
    return [(rotulo, valor) for rotulo, valor in campos if rotulo in campos_principais]


def abrir_dialogo_imprimir_cliente(parent, cliente):
    """Gera ficha completa/resumida em PDF, permite guardar ou enviar para impressão."""
    if not cliente:
        messagebox.showwarning("Imprimir cliente", "Selecione ou pesquise um cliente primeiro.", parent=parent)
        return

    janela = tk.Toplevel(parent)

    aplicar_icone_janela(janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Imprimir Cliente")
    janela.geometry("480x320")
    centralizar_janela_na_area_util(janela, 480, 320)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)
    janela.transient(parent)
    janela.grab_set()

    tk.Label(
        janela, text="IMPRIMIR CLIENTE", font=FONTE_15_NEGRITO,
        bg=COR_FUNDO, fg=COR_PRINCIPAL
    ).pack(pady=(16, 5))
    tk.Label(
        janela, text=f"Cliente: {cliente[1] or 'Sem nome'}", font=FONTE_9_NEGRITO,
        bg=COR_FUNDO, fg=COR_TEXTO, wraplength=420
    ).pack(pady=(0, 10))

    modo = tk.StringVar(value="completa")
    quadro = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro.pack(fill="x", padx=22, pady=4)
    tk.Radiobutton(
        quadro, text="Ficha completa — todos os dados cadastrados", variable=modo,
        value="completa", font=FONTE_9, bg=COR_PAINEL, fg=COR_TEXTO,
        activebackground=COR_PAINEL, selectcolor=COR_PAINEL, anchor="w"
    ).pack(fill="x", padx=12, pady=(10, 5))
    tk.Radiobutton(
        quadro, text="Dados principais — ficha resumida", variable=modo,
        value="principais", font=FONTE_9, bg=COR_PAINEL, fg=COR_TEXTO,
        activebackground=COR_PAINEL, selectcolor=COR_PAINEL, anchor="w"
    ).pack(fill="x", padx=12, pady=(5, 10))

    tk.Label(
        janela, text="Escolha o tipo de ficha e depois guardar o PDF ou enviar para impressão.",
        font=FONTE_8, bg=COR_FUNDO, fg=COR_SECUNDARIA, wraplength=430
    ).pack(pady=(6, 4))

    def preparar_pdf(enviar_impressao=False):
        completa = modo.get() == "completa"
        campos_impressao = _campos_ficha_cliente(cliente, completa=completa)
        base_nome = re.sub(r"[^A-Za-z0-9_-]+", "_", str(cliente[1] or "cliente")).strip("_")[:60] or "cliente"
        initialfile = f"Ficha_{base_nome}_{cliente[0]}_{'completa' if completa else 'resumida'}.pdf"
        caminho = filedialog.asksaveasfilename(
            parent=janela,
            title="Guardar ficha em PDF antes de imprimir" if enviar_impressao else "Guardar ficha em PDF",
            initialfile=initialfile,
            defaultextension=".pdf",
            filetypes=[("Documento PDF", "*.pdf")]
        )
        if not caminho:
            return

        titulo = "Ficha Completa do Cliente" if completa else "Dados Principais do Cliente"
        try:
            _gerar_pdf_ficha_cliente(caminho, titulo, campos_impressao)
            registar_auditoria(
                "Ficha de cliente preparada para impressão" if enviar_impressao else "Ficha de cliente guardada em PDF",
                cliente_id=cliente[0],
                detalhes=f"Tipo: {'completa' if completa else 'dados principais'}; ficheiro: {Path(caminho).name}"
            )
            janela.destroy()
            caminho_absoluto = str(Path(caminho).resolve())

            if enviar_impressao:
                try:
                    # No Windows, solicita a ação 'print' ao programa associado ao PDF.
                    os.startfile(caminho_absoluto, "print")
                    messagebox.showinfo(
                        "Impressão solicitada",
                        "O pedido de impressão foi enviado ao programa associado aos PDFs. "
                        "Se a impressora não iniciar, abre o PDF e utiliza Ctrl+P para confirmar a impressora.",
                        parent=parent
                    )
                except (AttributeError, OSError) as erro_impressao:
                    try:
                        os.startfile(caminho_absoluto)
                    except (AttributeError, OSError):
                        pass
                    messagebox.showwarning(
                        "Impressão manual necessária",
                        f"O PDF foi guardado em:\n{caminho}\n\n"
                        "Não foi possível enviar automaticamente para a impressora. "
                        "Abre o ficheiro e utiliza Ctrl+P.\n\nDetalhe: " + str(erro_impressao),
                        parent=parent
                    )
            else:
                try:
                    os.startfile(caminho_absoluto)
                    messagebox.showinfo(
                        "PDF pronto",
                        f"A ficha foi guardada em:\n{caminho}\n\nO PDF foi aberto. Para imprimir, utiliza Ctrl+P.",
                        parent=parent
                    )
                except (AttributeError, OSError) as erro_abertura:
                    messagebox.showinfo(
                        "PDF criado",
                        f"A ficha foi guardada em:\n{caminho}\n\n"
                        f"Abre o PDF manualmente para consultar ou imprimir.\n{erro_abertura}",
                        parent=parent
                    )
        except Exception as erro:
            messagebox.showerror("Erro ao preparar impressão", f"Não foi possível gerar a ficha PDF:\n{erro}", parent=janela)

    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(fill="x", padx=22, pady=(10, 12))
    tk.Button(
        botoes, text="Imprimir", command=lambda: preparar_pdf(True), font=FONTE_9_NEGRITO,
        bg=COR_BOTAO, fg="white", relief="flat", cursor="hand2", padx=14, pady=5
    ).pack(side="left", padx=(0, 6))
    tk.Button(
        botoes, text="Guardar PDF", command=lambda: preparar_pdf(False), font=FONTE_9_NEGRITO,
        bg=COR_PRINCIPAL, fg="white", relief="flat", cursor="hand2", padx=14, pady=5
    ).pack(side="left", padx=6)
    tk.Button(
        botoes, text="Cancelar", command=janela.destroy, font=FONTE_9_NEGRITO,
        bg="#e8eef5", fg=COR_TEXTO, relief="flat", cursor="hand2", padx=14, pady=5
    ).pack(side="right")

def exportar_clientes(formato, parent):
    """Exporta a lista de clientes em CSV, XLSX ou PDF."""
    extensoes = {"CSV": ".csv", "Excel": ".xlsx", "PDF": ".pdf"}
    extensao = extensoes[formato]
    caminho = filedialog.asksaveasfilename(
        parent=parent,
        title=f"Exportar clientes para {formato}",
        initialfile=f"clientes_TB_Software_{datetime.now():%Y%m%d}{extensao}",
        defaultextension=extensao,
        filetypes=[(f"Ficheiro {formato}", f"*{extensao}")]
    )
    if not caminho:
        return

    try:
        cabecalhos, registos = obter_registos_clientes_exportacao()
        if formato == "CSV":
            with open(caminho, "w", newline="", encoding="utf-8-sig") as ficheiro:
                escritor = csv.writer(ficheiro, delimiter=";")
                escritor.writerow(cabecalhos)
                escritor.writerows(registos)
        elif formato == "Excel":
            try:
                from openpyxl import Workbook
                from openpyxl.styles import Font, PatternFill, Alignment
                from openpyxl.utils import get_column_letter
            except ImportError:
                _escrever_excel_xlsx_basico(caminho, cabecalhos, registos)
            else:
                livro = Workbook()
                folha = livro.active
                folha.title = "Clientes"
                folha.append(list(cabecalhos))
                for celula in folha[1]:
                    celula.font = Font(bold=True, color="FFFFFF")
                    celula.fill = PatternFill("solid", fgColor="022C53")
                    celula.alignment = Alignment(wrap_text=True)
                for registo in registos:
                    folha.append(["" if valor is None else valor for valor in registo])
                folha.freeze_panes = "A2"
                folha.auto_filter.ref = folha.dimensions
                for coluna in folha.columns:
                    letra = get_column_letter(coluna[0].column)
                    largura = max((len(str(c.value or "")) for c in coluna), default=10)
                    folha.column_dimensions[letra].width = min(max(largura + 2, 12), 38)
                livro.save(caminho)
        else:
            _exportar_pdf_relatorio(caminho, cabecalhos, registos)
        registar_auditoria("Exportação de clientes", detalhes=f"Formato: {formato}; registos: {len(registos)}")
        messagebox.showinfo("Exportação concluída", f"Foram exportados {len(registos)} clientes.\n\nFicheiro:\n{caminho}", parent=parent)
    except Exception as erro:
        # Uma falha de exportação deve ser mostrada ao utilizador sem fechar a aplicação.
        messagebox.showerror("Erro ao exportar", str(erro), parent=parent)


def abrir_historico_auditoria(parent, usuario_logado):
    if obter_perfil_usuario(usuario_logado) != "Administrador":
        messagebox.showerror("Acesso negado", "Apenas o Administrador pode consultar o histórico.", parent=parent)
        return
    existente = focar_janela_aberta("historico_auditoria")
    if existente is not None:
        return existente

    janela = tk.Toplevel(parent)

    aplicar_icone_janela(janela)
    registar_janela_aberta("historico_auditoria", janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Histórico de Alterações")
    janela.geometry("900x520")
    centralizar_janela_na_area_util(janela, 900, 520)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)

    # Reservar primeiro o espaço inferior para rodapé e botão Fechar.
    # A tabela é criada depois e ocupa apenas a área restante.
    criar_rodape(janela)

    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(side="bottom", fill="x", padx=18, pady=(4, 7))
    tk.Button(
        botoes,
        text="Fechar",
        command=janela.destroy,
        font=FONTE_9_NEGRITO,
        bg="#e8eef5",
        fg=COR_TEXTO,
        relief="flat",
        padx=18,
        pady=5
    ).pack(side="right")

    tk.Label(
        janela,
        text="Histórico de alterações",
        font=FONTE_15_NEGRITO,
        bg=COR_FUNDO,
        fg=COR_PRINCIPAL
    ).pack(anchor="w", padx=18, pady=(12, 6))
    tk.Label(
        janela,
        text="Regista operações importantes e quem as executou.",
        font=FONTE_9,
        bg=COR_FUNDO,
        fg=COR_SECUNDARIA
    ).pack(anchor="w", padx=18, pady=(0, 8))

    frame = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    frame.pack(fill="both", expand=True, padx=18, pady=5)

    colunas = ("data", "usuario", "acao", "cliente", "detalhes")
    tabela = ttk.Treeview(frame, columns=colunas, show="headings", height=15)
    for chave, rotulo in zip(colunas, ("Data/hora", "Utilizador", "Ação", "ID Cliente", "Detalhes")):
        tabela.heading(chave, text=rotulo)
    for chave, largura in (("data", 145), ("usuario", 120), ("acao", 180), ("cliente", 80), ("detalhes", 330)):
        tabela.column(chave, width=largura, anchor="w")

    barra = ttk.Scrollbar(frame, orient="vertical", command=tabela.yview)
    tabela.configure(yscrollcommand=barra.set)
    tabela.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")

    con = None
    try:
        con, cur = conectar_banco()
        _criar_tabela_auditoria_cursor(cur)
        cur.execute("SELECT data_hora, usuario, acao, cliente_id, detalhes FROM auditoria ORDER BY id DESC LIMIT 2000")
        for row in cur.fetchall():
            tabela.insert("", "end", values=tuple("" if valor is None else valor for valor in row))
    except sqlite3.Error as erro:
        messagebox.showerror("Histórico", f"Não foi possível carregar o histórico:\n{erro}", parent=janela)
    finally:
        if con:
            con.close()


def abrir_dados_seguranca(parent, usuario_logado):
    existente = focar_janela_aberta("dados_seguranca")
    if existente is not None:
        return existente
    janela = tk.Toplevel(parent)
    aplicar_icone_janela(janela)
    registar_janela_aberta("dados_seguranca", janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Dados e Segurança")
    janela.geometry("740x560")
    centralizar_janela_na_area_util(janela, 740, 560)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)
    admin = obter_perfil_usuario(usuario_logado) == "Administrador"

    # Cabeçalho com acesso direto ao histórico, sempre no topo da janela.
    cabecalho = tk.Frame(janela, bg=COR_FUNDO)
    cabecalho.pack(fill="x", padx=18, pady=(12, 8))
    tk.Label(cabecalho, text="Dados e Segurança", font=FONTE_16_NEGRITO,
             bg=COR_FUNDO, fg=COR_PRINCIPAL).pack(side="left", anchor="w")
    tk.Button(
        cabecalho,
        text="Ver histórico",
        command=lambda: abrir_historico_auditoria(parent, usuario_logado),
        font=FONTE_9_NEGRITO,
        bg=COR_PRINCIPAL,
        fg="white",
        relief="flat",
        cursor="hand2",
        padx=14,
        pady=5,
        state="normal" if admin else "disabled"
    ).pack(side="right")

    quadro_exportar = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro_exportar.pack(fill="x", padx=18, pady=6)
    tk.Label(quadro_exportar, text="Exportar clientes", font=FONTE_10_NEGRITO,
             bg=COR_PAINEL, fg=COR_TEXTO).pack(anchor="w", padx=14, pady=(10, 5))
    linha_exportar = tk.Frame(quadro_exportar, bg=COR_PAINEL)
    linha_exportar.pack(fill="x", padx=12, pady=(0, 10))
    for texto, formato in (("Exportar CSV", "CSV"), ("Exportar Excel", "Excel"), ("Exportar PDF", "PDF")):
        tk.Button(linha_exportar, text=texto, command=lambda f=formato: exportar_clientes(f, janela),
                  font=FONTE_9_NEGRITO, bg=COR_BOTAO, fg="white", relief="flat",
                  cursor="hand2", padx=12, pady=6).pack(side="left", padx=5)

    quadro_backup = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro_backup.pack(fill="x", padx=18, pady=6)
    tk.Label(quadro_backup, text="Cópias de segurança", font=FONTE_10_NEGRITO,
             bg=COR_PAINEL, fg=COR_TEXTO).pack(anchor="w", padx=14, pady=(10, 4))
    tk.Label(quadro_backup,
             text="O programa cria cópias automáticas ao iniciar sessão e conserva até 30 das mais recentes.",
             font=FONTE_8, bg=COR_PAINEL, fg=COR_SECUNDARIA, wraplength=660, justify="left").pack(anchor="w", padx=14, pady=(0, 7))
    linha_backup = tk.Frame(quadro_backup, bg=COR_PAINEL)
    linha_backup.pack(fill="x", padx=12, pady=(0, 10))

    def backup_manual():
        caminho = filedialog.asksaveasfilename(
            parent=janela, title="Guardar cópia de segurança", defaultextension=".sqlite3",
            initialfile=f"TB_Software_backup_{datetime.now():%Y%m%d_%H%M%S}.sqlite3",
            filetypes=[("Base de dados SQLite", "*.sqlite3 *.db *.sqlite"), ("Todos os ficheiros", "*.*")]
        )
        if not caminho:
            return
        try:
            resultado = _executar_backup_para(caminho)
            registar_auditoria("Cópia de segurança manual", detalhes=resultado.name)
            messagebox.showinfo("Backup concluído", f"Cópia criada e verificada:\n{resultado}", parent=janela)
        except (sqlite3.Error, OSError, RuntimeError, ValueError) as erro:
            messagebox.showerror("Erro no backup", str(erro), parent=janela)

    def restaurar_manual():
        caminho = filedialog.askopenfilename(
            parent=janela, title="Selecionar cópia para restaurar",
            filetypes=[("Cópias SQLite", "*.sqlite3 *.db *.sqlite"), ("Todos os ficheiros", "*.*")]
        )
        if not caminho:
            return
        try:
            caminho_validado = _validar_ficheiro_backup(caminho)
        except (OSError, sqlite3.Error) as erro:
            messagebox.showerror("Backup inválido", str(erro), parent=janela)
            return
        confirmar = messagebox.askyesno(
            "Confirmar restauro",
            "ATENÇÃO: o restauro substitui os dados atuais pelos dados da cópia selecionada.\n\n"
            "Será criada primeiro uma cópia preventiva do banco atual.\n\nDeseja continuar?",
            parent=janela
        )
        if not confirmar:
            return
        try:
            previa = restaurar_backup(caminho_validado)
            # Fechar janelas secundárias com dados carregados da base anterior.
            for widget in parent.winfo_children():
                if isinstance(widget, tk.Toplevel) and widget is not janela:
                    try:
                        widget.destroy()
                    except tk.TclError:
                        pass
            janela.destroy()
            callback = ATUALIZAR_DASHBOARD_CALLBACK
            if callable(callback):
                callback()
            messagebox.showinfo(
                "Restauro concluído",
                f"A base de dados foi restaurada.\nCópia preventiva guardada em:\n{previa}",
                parent=parent
            )
        except (sqlite3.Error, OSError, RuntimeError, ValueError, FileNotFoundError) as erro:
            messagebox.showerror("Erro ao restaurar", f"Não foi possível restaurar a cópia:\n{erro}", parent=janela)

    btn_backup = tk.Button(linha_backup, text="Criar cópia agora", command=backup_manual,
                           font=FONTE_9_NEGRITO, bg=COR_BOTAO, fg="white", relief="flat", padx=12, pady=6)
    btn_backup.pack(side="left", padx=5)
    btn_restaurar = tk.Button(linha_backup, text="Restaurar cópia", command=restaurar_manual,
                              font=FONTE_9_NEGRITO, bg="#a33b38", fg="white", relief="flat", padx=12, pady=6)
    btn_restaurar.pack(side="left", padx=5)
    if not admin:
        btn_backup.configure(state="disabled")
        btn_restaurar.configure(state="disabled")

    quadro_historico = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro_historico.pack(fill="x", padx=18, pady=6)
    tk.Label(quadro_historico, text="Histórico de alterações", font=FONTE_10_NEGRITO,
             bg=COR_PAINEL, fg=COR_TEXTO).pack(anchor="w", padx=14, pady=(10, 4))
    tk.Label(quadro_historico, text="Consulta de cadastros, alterações, exclusões, contas, exportações e backups.",
             font=FONTE_8, bg=COR_PAINEL, fg=COR_SECUNDARIA, wraplength=660, justify="left").pack(anchor="w", padx=14, pady=(0, 7))
    tk.Label(quadro_historico, text="Use o botão 'Ver histórico' no topo desta janela para consultar os registos.",
             font=FONTE_8, bg=COR_PAINEL, fg=COR_SECUNDARIA).pack(anchor="w", padx=14, pady=(0, 10))

    tk.Label(janela, text="A segurança do banco e o histórico são funções exclusivas do Administrador.",
             font=FONTE_8, bg=COR_FUNDO, fg=COR_SECUNDARIA).pack(anchor="w", padx=20, pady=(4, 2))
    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(fill="x", padx=18, pady=(2, 5))
    tk.Button(botoes, text="Fechar", command=janela.destroy, font=FONTE_9_NEGRITO,
              bg="#e8eef5", fg=COR_TEXTO, relief="flat", padx=18, pady=5).pack(side="right")
    criar_rodape(janela)



def abrir_utilizadores(parent, usuario_logado):
    if obter_perfil_usuario(usuario_logado) != "Administrador":
        messagebox.showerror(
            "Acesso negado",
            "Apenas um Administrador pode gerir utilizadores.",
            parent=parent
        )
        return

    existente = focar_janela_aberta("utilizadores")
    if existente is not None:
        return existente

    janela = tk.Toplevel(parent)

    aplicar_icone_janela(janela)
    registar_janela_aberta("utilizadores", janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Utilizadores")
    janela.geometry("760x560")
    centralizar_janela_na_area_util(janela, 760, 560)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)
    criar_rodape(janela)

    tk.Label(
        janela,
        text="👥  Utilizadores",
        font=FONTE_15_NEGRITO,
        bg=COR_FUNDO,
        fg=COR_TEXTO
    ).pack(anchor="w", padx=18, pady=(12, 4))

    tk.Label(
        janela,
        text="Gestão de contas reservada a Administradores.",
        font=FONTE_9,
        bg=COR_FUNDO,
        fg=COR_SECUNDARIA
    ).pack(anchor="w", padx=18, pady=(0, 8))

    quadro = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro.pack(fill="x", padx=18, pady=5)
    quadro.configure(height=235)
    quadro.pack_propagate(False)

    tabela = ttk.Treeview(
        quadro,
        columns=("usuario", "acesso", "estado"),
        show="headings",
        height=8
    )
    tabela.heading("usuario", text="Utilizador")
    tabela.heading("acesso", text="Perfil")
    tabela.heading("estado", text="Estado da conta")
    tabela.column("usuario", width=220)
    tabela.column("acesso", width=180)
    tabela.column("estado", width=180)
    tabela.pack(side="left", fill="both", expand=True, padx=8, pady=8)

    barra = ttk.Scrollbar(quadro, orient="vertical", command=tabela.yview)
    barra.pack(side="right", fill="y", pady=8)
    tabela.configure(yscrollcommand=barra.set)

    usuarios_perfis = {}

    def carregar_utilizadores():
        for item in tabela.get_children():
            tabela.delete(item)
        usuarios_perfis.clear()

        con = None
        try:
            con, cur = conectar_banco()
            cur.execute("""
                SELECT usuario, COALESCE(perfil, 'Utilizador'), COALESCE(ativo, 1)
                FROM usuarios
                ORDER BY usuario COLLATE NOCASE
            """)

            for usuario, perfil, ativo in cur.fetchall():
                estado = "Ativo" if int(ativo or 0) == 1 else "Bloqueado"
                usuarios_perfis[usuario] = perfil
                tabela.insert("", "end", values=(usuario, perfil, estado))

        except sqlite3.Error as erro:
            messagebox.showerror(
                "Erro",
                f"Não foi possível carregar os utilizadores:\n{erro}",
                parent=janela
            )
        finally:
            if con:
                con.close()

    def obter_selecionado():
        selecao = tabela.selection()
        if not selecao:
            messagebox.showwarning(
                "Utilizadores",
                "Selecione um utilizador primeiro.",
                parent=janela
            )
            return None
        valores = tabela.item(selecao[0], "values")
        return (valores[0], valores[1]) if valores else None

    def alterar_utilizador():
        selecionado = obter_selecionado()
        if selecionado is None:
            return

        usuario_alvo, perfil_atual = selecionado

        # Para alterar a conta de outro utilizador, exige autorização.
        autorizacao = solicitar_autorizacao(
            janela,
            f"Autorize a alteração do utilizador '{usuario_alvo}'."
        )

        if not autorizacao["autorizado"]:
            return

        perfil_autorizador = autorizacao["perfil"]

        # A conta principal admin tem proteção adicional.
        if perfil_autorizador != "Administrador":
            messagebox.showerror(
                "Acesso negado",
                "Apenas um Administrador pode alterar contas de utilizadores.",
                parent=janela
            )
            return

        if perfil_autorizador == "Gerente" and usuario_alvo.lower() == "admin":
            messagebox.showerror(
                "Acesso negado",
                "Um Gerente não pode alterar a conta Administrador.",
                parent=janela
            )
            return

        editor = tk.Toplevel(janela)

        aplicar_icone_janela(editor)
        registrar_tema_janela(editor)
        editor.title("TB Software - Alterar Utilizador")
        editor.geometry("470x400")
        centralizar_janela_na_area_util(editor, 470, 400)
        editor.resizable(False, False)
        editor.configure(bg=COR_FUNDO)
        editor.transient(janela)
        editor.grab_set()

        tk.Label(
            editor,
            text="ALTERAR UTILIZADOR",
            font=FONTE_18_NEGRITO,
            bg=COR_FUNDO,
            fg=COR_PRINCIPAL
        ).pack(pady=(16, 8))

        formulario = tk.Frame(editor, bg="white", bd=1, relief="solid")
        formulario.pack(fill="x", padx=24, pady=4)
        formulario.columnconfigure(1, weight=1)

        tk.Label(
            formulario,
            text="Utilizador:",
            font=FONTE_9_NEGRITO,
            bg="white",
            fg=COR_TEXTO
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 6))

        nome_var = tk.StringVar(value=usuario_alvo)
        entrada_nome = tk.Entry(formulario, textvariable=nome_var, font=FONTE_10)
        entrada_nome.grid(row=0, column=1, sticky="ew", padx=14, pady=(14, 6), ipady=3)

        tk.Label(
            formulario,
            text="Nova senha (opcional):",
            font=FONTE_9_NEGRITO,
            bg="white",
            fg=COR_TEXTO
        ).grid(row=1, column=0, sticky="w", padx=14, pady=6)

        entrada_senha = tk.Entry(formulario, font=FONTE_10, show="*")
        entrada_senha.grid(row=1, column=1, sticky="ew", padx=14, pady=6, ipady=3)

        tk.Label(
            formulario,
            text="Confirmar senha:",
            font=FONTE_9_NEGRITO,
            bg="white",
            fg=COR_TEXTO
        ).grid(row=2, column=0, sticky="w", padx=14, pady=6)

        entrada_confirmar = tk.Entry(formulario, font=FONTE_10, show="*")
        entrada_confirmar.grid(row=2, column=1, sticky="ew", padx=14, pady=6, ipady=3)

        tk.Label(
            formulario,
            text="Perfil:",
            font=FONTE_9_NEGRITO,
            bg="white",
            fg=COR_TEXTO
        ).grid(row=3, column=0, sticky="w", padx=14, pady=6)

        perfil_var = tk.StringVar(value=perfil_atual)
        combo_perfil = ttk.Combobox(
            formulario,
            textvariable=perfil_var,
            values=("Utilizador", "Gerente", "Administrador"),
            state="readonly",
            font=FONTE_10
        )
        combo_perfil.grid(row=3, column=1, sticky="ew", padx=14, pady=6, ipady=2)

        if perfil_autorizador == "Gerente":
            combo_perfil.set(perfil_atual)
            combo_perfil.configure(state="disabled")

        tk.Label(
            formulario,
            text="Um Gerente pode alterar utilizadores, mas não pode criar/atribuir Administrador.",
            font=FONTE_8,
            bg="white",
            fg=COR_SECUNDARIA,
            wraplength=400,
            justify="left"
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=14, pady=(4, 14))

        def guardar():
            novo_nome = nome_var.get().strip()
            nova_senha = entrada_senha.get()
            confirmar_senha = entrada_confirmar.get()
            novo_perfil = perfil_var.get().strip() or perfil_atual

            if not novo_nome:
                messagebox.showerror(
                    "Erro",
                    "O utilizador não pode ficar vazio.",
                    parent=editor
                )
                return

            if usuario_alvo.lower() == "admin" and novo_nome.lower() != "admin":
                messagebox.showerror(
                    "Erro",
                    "A conta Administrador (admin) não pode ter o nome alterado.",
                    parent=editor
                )
                return

            if perfil_autorizador == "Gerente" and novo_perfil == "Administrador":
                messagebox.showerror(
                    "Acesso negado",
                    "Um Gerente não pode atribuir o perfil Administrador.",
                    parent=editor
                )
                return

            if nova_senha and nova_senha != confirmar_senha:
                messagebox.showerror(
                    "Erro",
                    "As novas senhas não são iguais.",
                    parent=editor
                )
                return

            if nova_senha and len(nova_senha) < 6:
                messagebox.showerror(
                    "Erro",
                    "A nova senha deve ter pelo menos 6 caracteres.",
                    parent=editor
                )
                return

            senha_hash = None
            if nova_senha:
                senha_hash = criar_hash_senha(nova_senha)

            con = None
            try:
                con, cur = conectar_banco()

                if senha_hash:
                    cur.execute("""
                        UPDATE usuarios
                        SET usuario = ?, senha = ?, perfil = ?
                        WHERE usuario = ?
                    """, (novo_nome, senha_hash, novo_perfil, usuario_alvo))
                else:
                    cur.execute("""
                        UPDATE usuarios
                        SET usuario = ?, perfil = ?
                        WHERE usuario = ?
                    """, (novo_nome, novo_perfil, usuario_alvo))

                _inserir_auditoria(
                    cur, "Utilizador alterado", detalhes=f"Conta '{usuario_alvo}' atualizada"
                )
                con.commit()

                messagebox.showinfo(
                    "Sucesso",
                    "Utilizador alterado com sucesso.",
                    parent=editor
                )

                editor.destroy()
                carregar_utilizadores()

            except sqlite3.IntegrityError:
                if con:
                    con.rollback()
                messagebox.showerror(
                    "Erro",
                    "Esse nome de utilizador já existe.",
                    parent=editor
                )
            except sqlite3.Error as erro:
                if con:
                    con.rollback()
                messagebox.showerror(
                    "Erro",
                    f"Não foi possível alterar o utilizador:\n{erro}",
                    parent=editor
                )
            finally:
                if con:
                    con.close()

        botoes_editor = tk.Frame(editor, bg=COR_FUNDO)
        botoes_editor.pack(fill="x", padx=24, pady=(12, 0))

        tk.Button(
            botoes_editor,
            text="Guardar",
            command=guardar,
            font=FONTE_9_NEGRITO,
            bg=COR_BOTAO,
            fg="white",
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=6
        ).pack(side="left")

        tk.Button(
            botoes_editor,
            text="Cancelar",
            command=editor.destroy,
            font=FONTE_9_NEGRITO,
            bg="#e8eef5",
            fg=COR_TEXTO,
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=6
        ).pack(side="right")

        entrada_senha.focus_set()

    def criar_utilizador():
        """Cria uma conta apenas após autorização de um Administrador."""
        autorizacao = solicitar_autorizacao(
            janela,
            "Autorize a criação de um novo utilizador."
        )

        if not autorizacao["autorizado"]:
            return

        perfil_autorizador = autorizacao["perfil"]

        editor = tk.Toplevel(janela)

        aplicar_icone_janela(editor)
        registrar_tema_janela(editor)
        editor.title("TB Software - Novo Utilizador")
        editor.geometry("470x410")
        centralizar_janela_na_area_util(editor, 470, 410)
        editor.resizable(False, False)
        editor.configure(bg=COR_FUNDO)
        editor.transient(janela)
        editor.grab_set()

        tk.Label(
            editor,
            text="NOVO UTILIZADOR",
            font=FONTE_18_NEGRITO,
            bg=COR_FUNDO,
            fg=COR_PRINCIPAL
        ).pack(pady=(16, 8))

        formulario = tk.Frame(editor, bg="white", bd=1, relief="solid")
        formulario.pack(fill="x", padx=24, pady=4)
        formulario.columnconfigure(1, weight=1)

        tk.Label(
            formulario, text="Utilizador:", font=FONTE_9_NEGRITO,
            bg="white", fg=COR_TEXTO
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 6))

        entrada_novo_usuario = tk.Entry(formulario, font=FONTE_10)
        entrada_novo_usuario.grid(
            row=0, column=1, sticky="ew", padx=14, pady=(14, 6), ipady=3
        )

        tk.Label(
            formulario, text="Senha:", font=FONTE_9_NEGRITO,
            bg="white", fg=COR_TEXTO
        ).grid(row=1, column=0, sticky="w", padx=14, pady=6)

        entrada_nova_senha = tk.Entry(formulario, font=FONTE_10, show="*")
        entrada_nova_senha.grid(
            row=1, column=1, sticky="ew", padx=14, pady=6, ipady=3
        )

        tk.Label(
            formulario, text="Confirmar senha:", font=FONTE_9_NEGRITO,
            bg="white", fg=COR_TEXTO
        ).grid(row=2, column=0, sticky="w", padx=14, pady=6)

        entrada_confirmar_senha = tk.Entry(formulario, font=FONTE_10, show="*")
        entrada_confirmar_senha.grid(
            row=2, column=1, sticky="ew", padx=14, pady=6, ipady=3
        )

        tk.Label(
            formulario, text="Perfil:", font=FONTE_9_NEGRITO,
            bg="white", fg=COR_TEXTO
        ).grid(row=3, column=0, sticky="w", padx=14, pady=6)

        if perfil_autorizador == "Administrador":
            perfis_permitidos = ("Utilizador", "Gerente", "Administrador")
        else:
            # Gerentes não podem criar contas de Administrador.
            perfis_permitidos = ("Utilizador", "Gerente")

        perfil_novo_var = tk.StringVar(value="Utilizador")
        combo_novo_perfil = ttk.Combobox(
            formulario,
            textvariable=perfil_novo_var,
            values=perfis_permitidos,
            state="readonly",
            font=FONTE_10
        )
        combo_novo_perfil.grid(
            row=3, column=1, sticky="ew", padx=14, pady=6, ipady=2
        )

        def guardar_novo_utilizador():
            nome = entrada_novo_usuario.get().strip()
            senha = entrada_nova_senha.get()
            confirmar = entrada_confirmar_senha.get()
            perfil = perfil_novo_var.get().strip()

            if not nome:
                messagebox.showerror(
                    "Novo Utilizador",
                    "Digite o nome do utilizador.",
                    parent=editor
                )
                entrada_novo_usuario.focus_set()
                return

            if not senha:
                messagebox.showerror(
                    "Novo Utilizador",
                    "Digite uma senha.",
                    parent=editor
                )
                entrada_nova_senha.focus_set()
                return

            if len(senha) < 6:
                messagebox.showerror(
                    "Novo Utilizador",
                    "A senha deve ter pelo menos 6 caracteres.",
                    parent=editor
                )
                entrada_nova_senha.focus_set()
                return

            if senha != confirmar:
                messagebox.showerror(
                    "Novo Utilizador",
                    "As senhas não são iguais.",
                    parent=editor
                )
                entrada_confirmar_senha.focus_set()
                return

            if perfil_autorizador == "Gerente" and perfil == "Administrador":
                messagebox.showerror(
                    "Acesso negado",
                    "Um Gerente não pode criar uma conta de Administrador.",
                    parent=editor
                )
                return

            senha_hash = criar_hash_senha(senha)
            con = None

            try:
                con, cur = conectar_banco()
                if con is None:
                    messagebox.showerror(
                        "Erro",
                        "Não foi possível conectar ao banco de dados.",
                        parent=editor
                    )
                    return

                cur.execute(
                    "INSERT INTO usuarios (usuario, senha, perfil) VALUES (?, ?, ?)",
                    (nome, senha_hash, perfil)
                )
                _inserir_auditoria(cur, "Utilizador criado", detalhes=f"Conta '{nome}' criada com perfil {perfil}")
                con.commit()

                messagebox.showinfo(
                    "Sucesso",
                    f"Utilizador '{nome}' criado com sucesso.",
                    parent=editor
                )
                editor.destroy()
                carregar_utilizadores()

            except sqlite3.IntegrityError:
                if con:
                    con.rollback()
                messagebox.showerror(
                    "Novo Utilizador",
                    "Esse nome de utilizador já existe.",
                    parent=editor
                )
                entrada_novo_usuario.focus_set()

            except sqlite3.Error as erro:
                if con:
                    con.rollback()
                messagebox.showerror(
                    "Erro",
                    f"Não foi possível criar o utilizador:\n{erro}",
                    parent=editor
                )

            finally:
                if con:
                    con.close()

        botoes_editor = tk.Frame(editor, bg=COR_FUNDO)
        botoes_editor.pack(fill="x", padx=24, pady=(12, 0))

        tk.Button(
            botoes_editor,
            text="Guardar",
            command=guardar_novo_utilizador,
            font=FONTE_9_NEGRITO,
            bg=COR_BOTAO,
            fg="white",
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=6
        ).pack(side="left")

        tk.Button(
            botoes_editor,
            text="Cancelar",
            command=editor.destroy,
            font=FONTE_9_NEGRITO,
            bg="#e8eef5",
            fg=COR_TEXTO,
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=6
        ).pack(side="right")

        entrada_novo_usuario.focus_set()
        editor.bind("<Return>", lambda event: guardar_novo_utilizador())

    def alternar_bloqueio_utilizador():
        selecionado = obter_selecionado()
        if selecionado is None:
            return

        usuario_alvo, perfil_alvo = selecionado
        selecao = tabela.selection()
        valores_linha = tabela.item(selecao[0], "values") if selecao else ()
        if len(valores_linha) < 3:
            messagebox.showerror("Erro", "Não foi possível ler o estado da conta.", parent=janela)
            return

        if usuario_alvo.lower() == "admin":
            messagebox.showerror(
                "Operação não permitida",
                "A conta principal admin não pode ser bloqueada.",
                parent=janela
            )
            return

        if usuario_alvo.casefold() == usuario_logado.casefold():
            messagebox.showerror(
                "Operação não permitida",
                "Não podes bloquear a conta que estás a utilizar.",
                parent=janela
            )
            return

        ativo_atual = 1 if valores_linha[2] == "Ativo" else 0
        novo_ativo = 0 if ativo_atual else 1
        acao = "bloquear" if novo_ativo == 0 else "desbloquear"
        autorizacao = solicitar_autorizacao(
            janela,
            f"Autorize {acao} a conta '{usuario_alvo}'."
        )
        if not autorizacao["autorizado"]:
            return

        con = None
        try:
            con, cur = conectar_banco()
            cur.execute(
                "UPDATE usuarios SET ativo = ? WHERE usuario = ? AND LOWER(usuario) <> 'admin'",
                (novo_ativo, usuario_alvo)
            )
            if cur.rowcount != 1:
                con.rollback()
                messagebox.showerror("Erro", "Não foi possível alterar o estado da conta.", parent=janela)
                return
            _inserir_auditoria(
                cur, "Conta bloqueada" if novo_ativo == 0 else "Conta desbloqueada",
                detalhes=f"Estado alterado para { 'Ativo' if novo_ativo else 'Bloqueado' }: {usuario_alvo}"
            )
            con.commit()
            estado_novo = "desbloqueada" if novo_ativo else "bloqueada"
            messagebox.showinfo(
                "Estado da conta",
                f"A conta '{usuario_alvo}' foi {estado_novo}.",
                parent=janela
            )
            carregar_utilizadores()
        except sqlite3.Error as erro:
            if con:
                con.rollback()
            messagebox.showerror("Erro", f"Não foi possível alterar a conta:\n{erro}", parent=janela)
        finally:
            if con:
                con.close()

    info = tk.Label(
        janela,
        text=f"Utilizador conectado: {usuario_logado}",
        font=FONTE_9,
        bg=COR_FUNDO,
        fg=COR_SECUNDARIA,
        justify="left"
    )
    info.pack(anchor="w", padx=18, pady=5)

    # Linha de ações administrativas.
    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(fill="x", padx=18, pady=(6, 3))

    tk.Button(
        botoes,
        text="Alterar Utilizador",
        command=alterar_utilizador,
        font=FONTE_9_NEGRITO,
        bg=COR_BOTAO,
        fg="white",
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=12,
        pady=6
    ).pack(side="left", padx=(0, 6))

    tk.Button(
        botoes,
        text="Novo Utilizador",
        command=criar_utilizador,
        font=FONTE_9_NEGRITO,
        bg="#198754",
        fg="white",
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=12,
        pady=6
    ).pack(side="left", padx=6)

    tk.Button(
        botoes,
        text="Bloquear / Desbloquear",
        command=alternar_bloqueio_utilizador,
        font=FONTE_9_NEGRITO,
        bg="#b45309",
        fg="white",
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=10,
        pady=6
    ).pack(side="left", padx=6)

    # Linha pessoal separada para manter todos os botões visíveis.
    botoes_pessoais = tk.Frame(janela, bg=COR_FUNDO)
    botoes_pessoais.pack(fill="x", padx=18, pady=(0, 8))

    tk.Button(
        botoes_pessoais,
        text="Fechar",
        command=janela.destroy,
        font=FONTE_9_NEGRITO,
        bg="#e8eef5",
        fg=COR_TEXTO,
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=16,
        pady=6
    ).pack(side="right")

    tk.Button(
        botoes_pessoais,
        text="Alterar Minha Senha",
        command=lambda: alterar_senha(usuario_logado),
        font=FONTE_9_NEGRITO,
        bg=COR_PRINCIPAL,
        fg="white",
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=12,
        pady=6
    ).pack(side="right", padx=6)

    carregar_utilizadores()



def atualizar_identidade_empresa_na_interface(parent, nome_anterior, slogan_anterior):
    """Atualiza imediatamente os textos da identidade na janela principal."""
    def percorrer(widget):
        try:
            if isinstance(widget, tk.Label):
                texto = str(widget.cget("text"))

                if texto == nome_anterior:
                    widget.config(text=NOME_EMPRESA)
                elif texto == slogan_anterior:
                    widget.config(text=SLOGAN_EMPRESA)
                elif texto == f"{nome_anterior}  •  {slogan_anterior}":
                    widget.config(text=f"{NOME_EMPRESA}  •  {SLOGAN_EMPRESA}")
                elif texto == f"{nome_anterior} | {slogan_anterior}":
                    widget.config(text=f"{NOME_EMPRESA} | {SLOGAN_EMPRESA}")
        except (tk.TclError, AttributeError):
            pass

        try:
            for filho in widget.winfo_children():
                percorrer(filho)
        except (tk.TclError, AttributeError):
            pass

    try:
        percorrer(parent)
    except (tk.TclError, AttributeError):
        pass


def abrir_configuracoes(parent, usuario_logado):
    existente = focar_janela_aberta("configuracoes")
    if existente is not None:
        return existente

    janela = tk.Toplevel(parent)

    aplicar_icone_janela(janela)
    registar_janela_aberta("configuracoes", janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Configurações")
    janela.geometry("600x520")
    centralizar_janela_na_area_util(janela, 600, 520)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)

    tk.Label(
        janela, text="⚙  Configurações",
        font=FONTE_15_NEGRITO, bg=COR_FUNDO, fg=COR_TEXTO
    ).pack(anchor="w", padx=18, pady=(12, 6))

    perfil_atual = obter_perfil_usuario(usuario_logado)
    e_administrador = perfil_atual == "Administrador"

    quadro = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro.pack(fill="x", padx=18, pady=5)

    tk.Label(
        quadro, text="Dados da empresa",
        font=FONTE_10_NEGRITO, bg="white", fg=COR_TEXTO
    ).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(14, 8))

    tk.Label(quadro, text="Nome da empresa:", font=FONTE_9_NEGRITO,
             bg=COR_PAINEL, fg=COR_TEXTO).grid(row=1, column=0, sticky="w", padx=15, pady=5)
    nome_var = tk.StringVar(value=NOME_EMPRESA)
    entrada_nome_empresa = tk.Entry(quadro, textvariable=nome_var, font=FONTE_9,
                                    relief="solid", bd=1)
    entrada_nome_empresa.grid(row=1, column=1, sticky="ew", padx=15, pady=5, ipady=3)

    tk.Label(quadro, text="Slogan:", font=FONTE_9_NEGRITO,
             bg=COR_PAINEL, fg=COR_TEXTO).grid(row=2, column=0, sticky="w", padx=15, pady=5)
    slogan_var = tk.StringVar(value=SLOGAN_EMPRESA)
    entrada_slogan_empresa = tk.Entry(quadro, textvariable=slogan_var, font=FONTE_9,
                                      relief="solid", bd=1)
    entrada_slogan_empresa.grid(row=2, column=1, sticky="ew", padx=15, pady=5, ipady=3)

    tk.Label(
        quadro,
        text="A identidade da empresa só pode ser alterada pelo Administrador.\n"
             "O banco de dados dos clientes não é alterado por esta tela.",
        font=FONTE_9, bg=COR_PAINEL, fg=COR_SECUNDARIA, justify="left"
    ).grid(row=3, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 15))

    if not e_administrador:
        entrada_nome_empresa.configure(state="disabled")
        entrada_slogan_empresa.configure(state="disabled")

    quadro.columnconfigure(1, weight=1)

    quadro_tema = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro_tema.pack(fill="x", padx=18, pady=5)
    tk.Label(
        quadro_tema,
        text="Aparência",
        font=FONTE_10_NEGRITO,
        bg=COR_PAINEL,
        fg=COR_TEXTO
    ).pack(side="left", padx=15, pady=12)

    tema_var = tk.StringVar(value=obter_tema_usuario(usuario_logado))
    combo_tema = ttk.Combobox(
        quadro_tema,
        textvariable=tema_var,
        values=("Claro", "Escuro"),
        state="readonly",
        width=18,
        font=FONTE_10
    )
    combo_tema.pack(side="right", padx=15, pady=12)

    quadro_seguranca = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro_seguranca.pack(fill="x", padx=18, pady=5)
    tk.Label(quadro_seguranca, text="Segurança da conta", font=FONTE_10_NEGRITO,
             bg=COR_PAINEL, fg=COR_TEXTO).pack(side="left", padx=15, pady=10)
    tk.Button(quadro_seguranca, text="Configurar código de recuperação",
              command=lambda: configurar_codigo_recuperacao(usuario_logado, janela),
              font=FONTE_9_NEGRITO, bg=COR_BOTAO, fg="white", relief="flat",
              cursor="hand2", padx=12, pady=6).pack(side="right", padx=8, pady=7)
    tk.Button(quadro_seguranca, text="Alterar senha",
              command=lambda: alterar_senha(usuario_logado),
              font=FONTE_9_NEGRITO, bg="#e8eef5", fg=COR_TEXTO, relief="flat",
              cursor="hand2", padx=12, pady=6).pack(side="right", padx=8, pady=7)

    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(fill="x", padx=18, pady=5)

    def salvar_configuracoes():
        global NOME_EMPRESA, SLOGAN_EMPRESA
        tema_selecionado = "Escuro" if tema_var.get() == "Escuro" else "Claro"
        novo_nome = nome_var.get().strip()
        novo_slogan = slogan_var.get().strip()

        nome_anterior = NOME_EMPRESA
        slogan_anterior = SLOGAN_EMPRESA

        if e_administrador and (not novo_nome or not novo_slogan):
            messagebox.showerror(
                "Configurações",
                "Nome da empresa e slogan não podem ficar vazios.",
                parent=janela
            )
            return

        con = None
        try:
            con, cur = conectar_banco()
            cur.execute(
                "UPDATE usuarios SET tema = ? WHERE usuario = ?",
                (tema_selecionado, usuario_logado)
            )
            if cur.rowcount != 1:
                raise sqlite3.Error("A conta do utilizador não foi encontrada.")
            if e_administrador:
                guardar_configuracoes_empresa(novo_nome, novo_slogan, cursor=cur)

            con.commit()
        except sqlite3.Error as erro:
            if con:
                con.rollback()
            messagebox.showerror(
                "Configurações",
                f"Não foi possível guardar a preferência de tema:\n{erro}",
                parent=janela
            )
            return
        finally:
            if con:
                con.close()

        if e_administrador:
            NOME_EMPRESA = novo_nome
            SLOGAN_EMPRESA = novo_slogan
            atualizar_identidade_empresa_na_interface(
                parent,
                nome_anterior,
                slogan_anterior
            )

        definir_tema(tema_selecionado, root=getattr(tk, "_default_root", parent))
        janela.destroy()
        messagebox.showinfo(
            "Configurações",
            f"Preferência de tema guardada: {tema_selecionado}.",
            parent=parent
        )

    tk.Button(
        botoes, text="Cancelar", command=janela.destroy,
        font=FONTE_9_NEGRITO, bg="#e8eef5", fg=COR_TEXTO,
        relief="flat", bd=0, cursor="hand2", padx=18, pady=6
    ).pack(side="right")

    tk.Button(
        botoes, text="Guardar",
        command=salvar_configuracoes,
        font=FONTE_9_NEGRITO, bg=COR_BOTAO, fg="white",
        relief="flat", bd=0, cursor="hand2", padx=18, pady=6
    ).pack(side="right", padx=7)

    criar_rodape(janela)


def janela_principal(usuario_logado, tema="Claro"):
    global ATUALIZAR_DASHBOARD_CALLBACK
    janela = tk.Tk()
    aplicar_icone_janela(janela)
    definir_paleta_tema(tema)
    janela.title("TB Software - Sistema de Clientes")
    janela.geometry("1000x680")
    centralizar_janela_na_area_util(janela, 1000, 680)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)
    configurar_estilos()
    registrar_tema_janela(janela)

    corpo = tk.Frame(janela, bg=COR_FUNDO)
    corpo.pack(fill="both", expand=True)

    menu = tk.Frame(corpo, bg=COR_PRINCIPAL, width=180)
    menu.pack(side="left", fill="y")
    menu.pack_propagate(False)

    marca = tk.Frame(menu, bg=COR_PRINCIPAL, height=115)
    marca.pack(fill="x")
    marca.pack_propagate(False)

    # Logo principal da aplicação.
    pasta_programa = Path(__file__).resolve().parent
    logo_path = pasta_programa / "assets" / "tb_software_logo.png"
    if logo_path.exists():
        try:
            logo_original = Image.open(logo_path).convert("RGBA")
            logo_original = logo_original.resize(
                (TAMANHO_LOGO_LARGURA, TAMANHO_LOGO_ALTURA),
                Image.Resampling.LANCZOS
            )

            imagem_logo = ImageTk.PhotoImage(logo_original)
            logo = tk.Label(marca, image=imagem_logo, bg=COR_PRINCIPAL)
            logo.image = imagem_logo
            logo.pack(pady=(10, 2), padx=8)
        except Exception:
            tk.Label(
                marca, text="TB Software", font=FONTE_17_NEGRITO,
                bg=COR_PRINCIPAL, fg="white"
            ).pack(pady=(20, 2))
    else:
        tk.Label(
            marca, text="TB Software", font=FONTE_17_NEGRITO,
            bg=COR_PRINCIPAL, fg="white"
        ).pack(pady=(20, 2))

    tk.Frame(menu, bg="#1b73c9", height=2).pack(
        fill="x", padx=14, pady=(0, 10)
    )

    area = tk.Frame(corpo, bg=COR_FUNDO)
    area.pack(side="left", fill="both", expand=True)

    botoes_menu = []

    def limpar_area():
        for widget in area.winfo_children():
            widget.destroy()

    def selecionar(botao):
        for b in botoes_menu:
            b.configure(bg=COR_PRINCIPAL)
        botao.configure(bg=COR_BOTAO)

    imagens_menu_cache = {}

    def carregar_icone_menu(chave):
        """Carrega e redimensiona o PNG configurado para um botão lateral."""
        if chave in imagens_menu_cache:
            return imagens_menu_cache[chave]

        nome_arquivo = MENU_ICONES.get(chave)
        if not nome_arquivo:
            imagens_menu_cache[chave] = None
            return None

        pasta_programa = Path(__file__).resolve().parent
        caminho = pasta_programa / "assets" / MENU_ICONES_PASTA / nome_arquivo
        if caminho is None:
            imagens_menu_cache[chave] = None
            return None

        try:
            if Image is not None and ImageTk is not None:
                with Image.open(caminho) as original:
                    imagem_original = original.convert("RGBA")
                imagem_original.thumbnail(
                    (MENU_ICONE_LARGURA, MENU_ICONE_ALTURA),
                    Image.Resampling.LANCZOS
                )
                # Centra o ícone num quadrado transparente para manter alinhamento.
                tela_icone = Image.new(
                    "RGBA", (MENU_ICONE_LARGURA, MENU_ICONE_ALTURA), (0, 0, 0, 0)
                )
                tela_icone.alpha_composite(
                    imagem_original,
                    ((MENU_ICONE_LARGURA - imagem_original.width) // 2,
                     (MENU_ICONE_ALTURA - imagem_original.height) // 2)
                )
                resultado = ImageTk.PhotoImage(tela_icone)
            else:
                # Alternativa caso Pillow não esteja instalado.
                resultado = tk.PhotoImage(file=str(caminho))
                largura = max(1, resultado.width())
                altura = max(1, resultado.height())
                fator = max(
                    1,
                    (largura + MENU_ICONE_LARGURA - 1) // MENU_ICONE_LARGURA,
                    (altura + MENU_ICONE_ALTURA - 1) // MENU_ICONE_ALTURA,
                )
                if fator > 1:
                    resultado = resultado.subsample(fator, fator)
        except Exception as erro:
            print(f"Não foi possível carregar o ícone '{caminho}': {erro}")
            resultado = None

        imagens_menu_cache[chave] = resultado
        return resultado

    def criar_botao_menu(texto, comando, chave_icone=None):
        imagem = carregar_icone_menu(chave_icone) if chave_icone else None

        botao = tk.Button(
            menu, text=texto, command=comando,
            font=FONTE_9_NEGRITO,
            bg=COR_PRINCIPAL, fg="white",
            activebackground="#126dcc", activeforeground="white",
            relief="flat", bd=0, anchor="w",
            padx=12,
            cursor="hand2",
            image=imagem if imagem is not None else "",
            compound="left",
        )
        if imagem is not None:
            # Mantém uma referência para o Tkinter não libertar a imagem.
            botao.image = imagem
        botao.pack(fill="x", padx=7, pady=2, ipady=7)
        botoes_menu.append(botao)
        return botao

    botao_inicio = None

    def tela_inicial():
        """
        Dashboard da versão 5.2.
        Mantém as funções da 5.1 e altera somente a apresentação:
        - 3 cartões superiores iguais
        - "Acesso rápido" antes dos 3 cartões inferiores
        - cartões inferiores são botões reais e funcionais
        - ícones maiores e nítidos
        """
        limpar_area()
        selecionar(botao_inicio)

        # ====================================================
        # CABEÇALHO
        # ====================================================

        cab = tk.Frame(area, bg=COR_FUNDO)
        cab.pack(fill="x", padx=24, pady=(16, 8))

        tk.Label(
            cab,
            text="Bem-vindo",
            font=FONTE_21_NEGRITO,
            bg=COR_FUNDO,
            fg=COR_TEXTO
        ).pack(anchor="w")

        tk.Label(
            cab,
            text="Sistema de Gestão de Clientes",
            font=FONTE_10,
            bg=COR_FUNDO,
            fg=COR_SECUNDARIA
        ).pack(anchor="w", pady=(1, 0))

        tk.Label(
            cab,
            text=f"Utilizador: {usuario_logado}",
            font=FONTE_9_NEGRITO,
            bg=COR_FUNDO,
            fg=COR_SECUNDARIA
        ).pack(anchor="e")

        # ====================================================
        # CONSULTA DO BANCO
        # ====================================================

        total_clientes = particulares = empresas = 0
        conexao = None

        try:
            conexao, cursor = conectar_banco()

            cursor.execute("SELECT COUNT(*) FROM clientes")
            total_clientes = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT COALESCE(tipo_cliente, 'Particular'), COUNT(*)
                FROM clientes
                GROUP BY COALESCE(tipo_cliente, 'Particular')
            """)

            for tipo, quantidade in cursor.fetchall():
                if tipo == "Empresa":
                    empresas = quantidade
                else:
                    particulares += quantidade

        except sqlite3.Error:
            pass

        finally:
            if conexao:
                conexao.close()

        # ====================================================
        # ÍCONES
        # ====================================================

        def carregar_icone(nome):
            pasta_programa = Path(__file__).resolve().parent
            caminhos = (
                pasta_programa / "assets" / "dashboard" / nome,
                pasta_programa / "assets" / nome,
                pasta_programa / nome,
                pasta_programa / "tb_software_assets" / nome,
            )

            for caminho in caminhos:
                if caminho.exists():
                    try:
                        # Redimensionamento controlado por TAMANHO_ICONE.
                        if Image is not None and ImageTk is not None:
                            imagem_original = Image.open(caminho).convert("RGBA")
                            imagem_original = imagem_original.resize(
                                (TAMANHO_ICONE, TAMANHO_ICONE),
                                Image.Resampling.LANCZOS
                            )

                            imagem = ImageTk.PhotoImage(imagem_original)
                            return imagem

                        # Fallback caso Pillow não esteja instalado.
                        return tk.PhotoImage(file=str(caminho))

                    except Exception:
                        continue

            return None

        icone_clientes = carregar_icone("dashboard_clientes.png")
        icone_particular = carregar_icone("dashboard_particular.png")
        icone_empresa = carregar_icone("dashboard_empresa.png")
        icone_novo = carregar_icone("dashboard_novo.png")
        icone_procurar = carregar_icone("dashboard_procurar.png")

        # ====================================================
        # GRADE DOS CARTÕES
        # ====================================================

        area_cards = tk.Frame(
            area,
            bg=COR_FUNDO
        )
        area_cards.pack(
            fill="x",
            padx=24,
            pady=(3, 0)
        )

        CARD_LARGURA = 205
        CARD_ALTURA = 150
        ESPACO = 8

        for coluna in range(3):
            area_cards.columnconfigure(
                coluna,
                weight=1,
                uniform="cards"
            )

        # ====================================================
        # CARTÃO DE ESTATÍSTICA
        # ====================================================

        def criar_card_estatistica(
            coluna,
            titulo,
            valor,
            imagem,
            cor_valor
        ):
            moldura = tk.Frame(
                area_cards,
                bg=COR_FUNDO,
                width=CARD_LARGURA,
                height=CARD_ALTURA
            )
            moldura.grid(
                row=0,
                column=coluna,
                padx=ESPACO,
                pady=ESPACO,
                sticky="nsew"
            )
            moldura.grid_propagate(False)

            cartao = tk.Frame(
                moldura,
                bg="white",
                bd=1,
                relief="solid"
            )
            cartao.place(
                x=0,
                y=0,
                relwidth=1,
                relheight=1
            )

            if imagem:
                icone = tk.Label(
                    cartao,
                    image=imagem,
                    bg="white"
                )
                icone.image = imagem
                icone.pack(
                    pady=(14, 4)
                )
            else:
                tk.Label(
                    cartao,
                    text="",
                    bg="white"
                ).pack(
                    pady=(28, 4)
                )

            tk.Label(
                cartao,
                text=titulo,
                font=FONTE_10_NEGRITO,
                bg="white",
                fg=COR_TEXTO
            ).pack()

            tk.Label(
                cartao,
                text=str(valor),
                font=FONTE_27_NEGRITO,
                bg="white",
                fg=cor_valor
            ).pack(
                pady=(3, 0)
            )

        criar_card_estatistica(
            0,
            "Total de Clientes",
            total_clientes,
            icone_clientes,
            "#126dcc"
        )

        criar_card_estatistica(
            1,
            "Particulares",
            particulares,
            icone_particular,
            "#159b70"
        )

        criar_card_estatistica(
            2,
            "Empresas",
            empresas,
            icone_empresa,
            "#ef8412"
        )

        # ====================================================
        # ACESSO RÁPIDO
        # ====================================================

        tk.Label(
            area,
            text="Acesso rápido",
            font=FONTE_12_NEGRITO,
            bg=COR_FUNDO,
            fg=COR_TEXTO
        ).pack(
            anchor="w",
            padx=29,
            pady=(12, 5)
        )

        area_rapida = tk.Frame(
            area,
            bg=COR_FUNDO
        )
        area_rapida.pack(
            fill="x",
            padx=24
        )

        for coluna in range(3):
            area_rapida.columnconfigure(
                coluna,
                weight=1,
                uniform="quick"
            )

        # ====================================================
        # BOTÃO-CARTÃO CLICÁVEL
        # ====================================================

        def criar_botao_rapido(
            coluna,
            texto,
            imagem,
            comando
        ):
            moldura = tk.Frame(
                area_rapida,
                bg=COR_FUNDO,
                width=CARD_LARGURA,
                height=CARD_ALTURA
            )
            moldura.grid(
                row=0,
                column=coluna,
                padx=ESPACO,
                pady=ESPACO,
                sticky="nsew"
            )
            moldura.grid_propagate(False)

            botao = tk.Button(
                moldura,
                text=texto,
                image=imagem,
                compound="top",
                command=comando,
                font=FONTE_10_NEGRITO,
                bg="white",
                fg=COR_TEXTO,
                activebackground="#f5f9ff",
                activeforeground=COR_TEXTO,
                relief="solid",
                bd=1,
                cursor="hand2",
                pady=6
            )

            if imagem:
                botao.image = imagem

            botao.place(
                x=0,
                y=0,
                relwidth=1,
                relheight=1
            )

        criar_botao_rapido(
            0,
            "Ver Clientes",
            icone_clientes,
            listar_clientes
        )

        criar_botao_rapido(
            1,
            "Novo Cliente",
            icone_novo,
            cadastrar_cliente
        )

        criar_botao_rapido(
            2,
            "Procurar Cliente",
            icone_procurar,
            procurar_cliente
        )

        tk.Label(
            area,
            text=f"{NOME_EMPRESA}  •  {SLOGAN_EMPRESA}",
            font=FONTE_9,
            bg=COR_FUNDO,
            fg=COR_SECUNDARIA
        ).pack(
            anchor="w",
            padx=29,
            pady=(10, 0)
        )

        janela.after_idle(lambda: aplicar_tema_janela(janela))


    botao_inicio = criar_botao_menu("Início", tela_inicial, "inicio")
    criar_botao_menu(
        "Relatórios",
        lambda: abrir_relatorios(janela),
        "relatorios"
    )
    criar_botao_menu(
        "Lembretes",
        lambda: abrir_lembretes(janela, usuario_logado),
        "lembretes"
    )

    # O botão existe para todos os perfis, mas só fica visível para Administrador.
    botao_utilizadores = criar_botao_menu(
        "Utilizadores",
        lambda: abrir_utilizadores(janela, usuario_logado),
        "utilizadores"
    )
    if obter_perfil_usuario(usuario_logado) != "Administrador":
        botao_utilizadores.pack_forget()

    criar_botao_menu(
        "Dados e Segurança",
        lambda: abrir_dados_seguranca(janela, usuario_logado),
        "dados_seguranca"
    )

    botao_configuracoes = criar_botao_menu(
        "Configurações",
        lambda: abrir_configuracoes(janela, usuario_logado),
        "configuracoes"
    )

    tk.Frame(menu, bg=COR_PRINCIPAL).pack(fill="both", expand=True)

    def trocar_utilizador():
        """Autentica outra conta e muda o utilizador da sessão atual."""
        janela_troca = tk.Toplevel(janela)
        aplicar_icone_janela(janela_troca)
        registrar_tema_janela(janela_troca)
        janela_troca.title("TB Software - Trocar de Utilizador")
        janela_troca.geometry("430x340")
        centralizar_janela_na_area_util(janela_troca, 430, 340)
        janela_troca.resizable(False, False)
        janela_troca.configure(bg=COR_FUNDO)
        janela_troca.transient(janela)
        janela_troca.grab_set()

        tk.Label(
            janela_troca,
            text="TROCAR DE UTILIZADOR",
            font=FONTE_16_NEGRITO,
            bg=COR_FUNDO,
            fg=COR_PRINCIPAL
        ).pack(pady=(18, 8))

        tk.Label(
            janela_troca,
            text="Introduza as credenciais da outra conta.",
            font=FONTE_9,
            bg=COR_FUNDO,
            fg=COR_SECUNDARIA
        ).pack(pady=(0, 10))

        formulario = tk.Frame(janela_troca, bg=COR_PAINEL, bd=1, relief="solid")
        formulario.pack(fill="x", padx=25, pady=4)
        formulario.columnconfigure(0, weight=1)

        tk.Label(
            formulario,
            text="Utilizador:",
            font=FONTE_9_NEGRITO,
            bg=COR_PAINEL,
            fg=COR_TEXTO
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 4))

        entrada_troca_usuario = tk.Entry(formulario, font=FONTE_10)
        entrada_troca_usuario.grid(
            row=1, column=0, sticky="ew", padx=15, pady=(0, 10), ipady=3
        )

        tk.Label(
            formulario,
            text="Senha:",
            font=FONTE_9_NEGRITO,
            bg=COR_PAINEL,
            fg=COR_TEXTO
        ).grid(row=2, column=0, sticky="w", padx=15, pady=(0, 4))

        entrada_troca_senha = tk.Entry(formulario, font=FONTE_10, show="*")
        entrada_troca_senha.grid(
            row=3, column=0, sticky="ew", padx=15, pady=(0, 13), ipady=3
        )

        def confirmar_troca():
            nonlocal usuario_logado, tema

            novo_usuario = entrada_troca_usuario.get().strip()
            nova_senha = entrada_troca_senha.get().strip()
            if not novo_usuario or not nova_senha:
                messagebox.showwarning(
                    "Trocar de Utilizador",
                    "Preencha o utilizador e a senha.",
                    parent=janela_troca
                )
                return

            con = None
            try:
                con, cur = conectar_banco()
                if con is None:
                    messagebox.showerror(
                        "Erro", "Não foi possível conectar ao banco de dados.",
                        parent=janela_troca
                    )
                    return
                cur.execute("""
                    SELECT COALESCE(perfil, 'Utilizador'),
                           COALESCE(ativo, 1),
                           COALESCE(tema, 'Claro'), senha
                    FROM usuarios WHERE usuario = ?
                """, (novo_usuario,))
                resultado = cur.fetchone()
                senha_ok, hash_legado = verificar_hash_senha(
                    nova_senha, resultado[3] if resultado else None
                )
                if resultado and senha_ok and int(resultado[1] or 0) == 1 and hash_legado:
                    cur.execute(
                        "UPDATE usuarios SET senha = ? WHERE usuario = ?",
                        (criar_hash_senha(nova_senha), novo_usuario)
                    )
                    con.commit()
            except sqlite3.Error as erro:
                messagebox.showerror(
                    "Erro",
                    f"Não foi possível validar a conta:\n{erro}",
                    parent=janela_troca
                )
                return
            finally:
                if con:
                    con.close()

            if not resultado or not senha_ok:
                messagebox.showerror(
                    "Acesso negado",
                    "Utilizador ou senha incorretos.",
                    parent=janela_troca
                )
                entrada_troca_senha.delete(0, tk.END)
                entrada_troca_senha.focus_set()
                return

            perfil_novo, ativo_novo, tema_novo, _hash_guardado = resultado
            if int(ativo_novo or 0) != 1:
                messagebox.showerror(
                    "Conta bloqueada",
                    "Esta conta está bloqueada. Contacte o Administrador.",
                    parent=janela_troca
                )
                entrada_troca_senha.delete(0, tk.END)
                entrada_troca_senha.focus_set()
                return

            # Fecha eventuais janelas da conta anterior para não misturar sessões.
            for widget in janela.winfo_children():
                if isinstance(widget, tk.Toplevel) and widget is not janela_troca:
                    try:
                        widget.destroy()
                    except tk.TclError:
                        pass

            janela_troca.destroy()
            usuario_logado = novo_usuario
            global USUARIO_AUDITORIA_ATUAL
            USUARIO_AUDITORIA_ATUAL = novo_usuario
            registar_auditoria("Troca de utilizador", detalhes="Sessão alterada")
            tema = "Escuro" if str(tema_novo).strip().lower() == "escuro" else "Claro"
            definir_tema(tema, root=janela)

            if str(perfil_novo).strip() == "Administrador":
                if not botao_utilizadores.winfo_manager():
                    botao_utilizadores.pack(
                        fill="x", padx=7, pady=2, ipady=7,
                        before=botao_configuracoes
                    )
            else:
                botao_utilizadores.pack_forget()

            tela_inicial()
            messagebox.showinfo(
                "Sessão alterada",
                f"Sessão iniciada como {usuario_logado}.",
                parent=janela
            )

        botoes_troca = tk.Frame(janela_troca, bg=COR_FUNDO)
        botoes_troca.pack(fill="x", padx=25, pady=(10, 14))

        tk.Button(
            botoes_troca,
            text="Confirmar",
            command=confirmar_troca,
            font=FONTE_9_NEGRITO,
            bg=COR_BOTAO,
            fg="white",
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=6
        ).pack(side="left")

        tk.Button(
            botoes_troca,
            text="Cancelar",
            command=janela_troca.destroy,
            font=FONTE_9_NEGRITO,
            bg="#e8eef5",
            fg=COR_TEXTO,
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=6
        ).pack(side="right")

        janela_troca.bind("<Return>", lambda event: confirmar_troca())
        entrada_troca_usuario.focus_set()

    criar_botao_menu("Trocar de Utilizador", trocar_utilizador, "trocar_utilizador")
    criar_botao_menu("Sair", janela.destroy, "sair")

    criar_rodape(janela)

    # Disponibiliza uma atualização imediata do Dashboard após operações
    # que alterem os clientes, sem precisar clicar novamente em Início.
    ATUALIZAR_DASHBOARD_CALLBACK = tela_inicial
    tela_inicial()

    def verificar_sessao_ativa():
        try:
            if not janela.winfo_exists():
                return
        except tk.TclError:
            return

        con = None
        ativo = None
        try:
            con, cur = conectar_banco()
            if con is not None:
                cur.execute(
                    "SELECT COALESCE(ativo, 1) FROM usuarios WHERE usuario = ?",
                    (usuario_logado,)
                )
                row = cur.fetchone()
                ativo = int(row[0] or 0) if row else 0
        except sqlite3.Error:
            # Uma falha momentânea da base não deve fechar uma sessão válida.
            ativo = None
        finally:
            if con:
                con.close()

        if ativo == 0:
            messagebox.showwarning(
                "Sessão encerrada",
                "Esta conta foi bloqueada ou desativada. A sessão será encerrada.",
                parent=janela
            )
            try:
                janela.destroy()
            except tk.TclError:
                pass
            return

        try:
            janela.after(5000, verificar_sessao_ativa)
        except tk.TclError:
            pass

    janela.after(5000, verificar_sessao_ativa)

    # Mostrar resumen al iniciar sesión y después comprobar horarios cada minuto.
    # Se programa en la ventana principal para que el ciclo se detenga al cerrar sesión.
    janela.after(1800, lambda w=janela: monitorar_lembretes_agendados(w, USUARIO_AUDITORIA_ATUAL or usuario_logado, inicio=True))
    janela.mainloop()



# ============================================================
#         FORMATAÇÃO E VALIDAÇÃO DOS CAMPOS DE CLIENTES
# ============================================================
def configurar_validacao_entrada(entrada, regra):
    """Liga validação de teclado/paste a um Entry, sem afetar os dados existentes."""
    comando = entrada.register(regra)
    entrada.configure(validate="key", validatecommand=(comando, "%P"))


def validar_tamanho_entrada(entrada, maximo):
    configurar_validacao_entrada(entrada, lambda proposta, limite=maximo: len(proposta) <= limite)


def validar_proposta_nif(proposta):
    # O identificador fiscal pode conter letras em alguns países.
    return len(proposta) <= 30 and re.fullmatch(r"[A-Za-z0-9 .\-/]*", proposta) is not None


def validar_proposta_passaporte(proposta):
    return len(proposta) <= 24 and re.fullmatch(r"[A-Za-z0-9 -]*", proposta) is not None


def normalizar_identificacao_fiscal(valor, pais):
    """Valida NIF português; noutros países aceita ID fiscal genérico sem alegar validação oficial."""
    valor = str(valor or "").strip().upper()
    if not valor:
        return ""
    if not re.fullmatch(r"[A-Z0-9 .\-/]{1,30}", valor):
        raise ValueError("A identificação fiscal contém caracteres inválidos.")
    normalizado = re.sub(r"[\s.\-/]", "", valor)
    if not normalizado:
        raise ValueError("Introduza uma identificação fiscal válida.")
    if str(pais or "").strip().casefold() == "portugal":
        if not normalizado.isdigit() or not clientes.nif_valido(normalizado):
            raise ValueError("O NIF português deve ter 9 dígitos e ser válido.")
    elif not re.fullmatch(r"[A-Z0-9]{2,30}", normalizado):
        raise ValueError("A identificação fiscal deve conter letras e/ou números.")
    return normalizado


def normalizar_passaporte(valor):
    """Normaliza o número do passaporte sem impor o padrão de um único país."""
    valor = str(valor or "").strip().upper()
    if not valor:
        return ""
    if not re.fullmatch(r"[A-Z0-9 -]{1,24}", valor):
        raise ValueError("O passaporte deve conter apenas letras, números, espaços ou hífen.")
    normalizado = re.sub(r"[\s-]", "", valor)
    if not 4 <= len(normalizado) <= 20:
        raise ValueError("O número do passaporte deve ter entre 4 e 20 caracteres.")
    return normalizado


def normalizar_identificador_pesquisa(valor):
    valor = str(valor or "").strip().upper()
    if not valor:
        return ""
    if not re.fullmatch(r"[A-Z0-9 .\-/]{1,30}", valor):
        raise ValueError("Utilize letras, números, espaços, pontos ou hífen no identificador.")
    normalizado = re.sub(r"[\s.\-/]", "", valor)
    if len(normalizado) < 2:
        raise ValueError("Introduza um NIF ou passaporte válido.")
    return normalizado


def passaporte_disponivel(passaporte, pais, ignorar_id=None):
    """Verifica duplicação do passaporte no mesmo país registado no cliente."""
    if not passaporte:
        return True
    conexao = None
    try:
        conexao, cursor = conectar_banco()
        if conexao is None:
            return False
        query = """
            SELECT id FROM clientes
            WHERE UPPER(REPLACE(REPLACE(COALESCE(passaporte, ''), ' ', ''), '-', '')) = ?
              AND LOWER(COALESCE(pais, '')) = LOWER(?)
        """
        parametros = [passaporte, str(pais or "")]
        if ignorar_id is not None:
            query += " AND id <> ?"
            parametros.append(ignorar_id)
        cursor.execute(query, tuple(parametros))
        return cursor.fetchone() is None
    except sqlite3.Error:
        return False
    finally:
        if conexao:
            conexao.close()


def validar_proposta_data(proposta):
    return len(proposta) <= 10 and re.fullmatch(r"[0-9/]*", proposta) is not None


def validar_proposta_telefone(proposta):
    return len(proposta) <= 22 and re.fullmatch(r"[0-9+ ()-]*", proposta) is not None


def validar_proposta_email(proposta):
    return len(proposta) <= 254 and re.fullmatch(r"[^\s]*", proposta) is not None


def validar_proposta_codigo_postal(proposta):
    return len(proposta) <= 15 and re.fullmatch(r"[A-Za-z0-9 -]*", proposta) is not None


def aplicar_mascara_data(event):
    """Insere automaticamente as barras enquanto se digitam os 8 dígitos da data."""
    entrada = event.widget
    original = entrada.get()
    try:
        cursor_original = entrada.index(tk.INSERT)
    except tk.TclError:
        cursor_original = len(original)

    digitos_antes = sum(1 for c in original[:cursor_original] if c.isdigit())
    cursor_no_fim = cursor_original >= len(original)
    digitos = "".join(c for c in original if c.isdigit())[:8]
    formatado = digitos[:2]
    if len(digitos) > 2:
        formatado += "/" + digitos[2:4]
    if len(digitos) > 4:
        formatado += "/" + digitos[4:8]

    if formatado != original:
        entrada.delete(0, tk.END)
        entrada.insert(0, formatado)
        if cursor_no_fim:
            entrada.icursor(tk.END)
        else:
            if digitos_antes <= 2:
                posicao = digitos_antes
            elif digitos_antes <= 4:
                posicao = digitos_antes + 1
            else:
                posicao = digitos_antes + 2
            entrada.icursor(min(len(formatado), posicao))


def aplicar_mascara_codigo_postal(event, obter_pais):
    """Formata códigos postais de Portugal e Brasil durante a digitação."""
    entrada = event.widget
    pais = str(obter_pais() or "").strip().lower()
    original = entrada.get()
    try:
        cursor_no_fim = entrada.index(tk.INSERT) >= len(original)
    except tk.TclError:
        cursor_no_fim = True

    if pais == "portugal":
        digitos = "".join(c for c in original if c.isdigit())[:7]
        formatado = digitos[:4] + ("-" + digitos[4:] if len(digitos) > 4 else "")
    elif pais == "brasil":
        digitos = "".join(c for c in original if c.isdigit())[:8]
        formatado = digitos[:5] + ("-" + digitos[5:] if len(digitos) > 5 else "")
    else:
        return

    if formatado != original:
        entrada.delete(0, tk.END)
        entrada.insert(0, formatado)
        entrada.icursor(tk.END if cursor_no_fim else len(formatado))


def normalizar_data_nascimento(valor):
    """Valida data opcional e devolve sempre DD/MM/AAAA."""
    valor = str(valor or "").strip()
    if not valor:
        return ""

    if re.fullmatch(r"\d{8}", valor):
        valor = f"{valor[:2]}/{valor[2:4]}/{valor[4:8]}"

    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", valor):
        raise ValueError("A data de nascimento deve estar no formato DD/MM/AAAA.")

    try:
        data = datetime.strptime(valor, "%d/%m/%Y").date()
    except ValueError:
        raise ValueError("A data de nascimento não existe. Verifique dia, mês e ano.")

    if data > date.today():
        raise ValueError("A data de nascimento não pode estar no futuro.")

    return data.strftime("%d/%m/%Y")


def data_nascimento_para_tela(valor):
    """Converte datas antigas (AAAA-MM-DD) ou sem separadores para DD/MM/AAAA."""
    valor = str(valor or "").strip()
    if not valor:
        return ""

    tentativas = (
        (r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d"),
        (r"\d{2}/\d{2}/\d{4}", "%d/%m/%Y"),
        (r"\d{8}", "%d%m%Y"),
    )
    for padrao, formato in tentativas:
        if re.fullmatch(padrao, valor):
            try:
                return datetime.strptime(valor, formato).strftime("%d/%m/%Y")
            except ValueError:
                # Se houver um valor histórico inválido, abre o campo vazio para correção.
                return ""
    return ""


def normalizar_telefone(valor, nome_campo="Telefone", obrigatorio=False):
    """Aceita separadores visuais, mas guarda apenas dígitos (9 a 15)."""
    valor = str(valor or "").strip()
    if not valor:
        if obrigatorio:
            raise ValueError(f"O campo {nome_campo} é obrigatório.")
        return ""

    if not re.fullmatch(r"\+?[0-9][0-9 ()-]*", valor):
        raise ValueError(f"{nome_campo} contém caracteres inválidos. Use números, espaços, +, parênteses ou hífen.")

    digitos = re.sub(r"\D", "", valor)
    if not 9 <= len(digitos) <= 15:
        raise ValueError(f"{nome_campo} deve conter entre 9 e 15 dígitos, incluindo indicativo internacional quando aplicável.")
    return digitos


def email_valido(valor):
    valor = str(valor or "").strip()
    if not valor:
        return True
    if len(valor) > 254:
        return False
    padrao = r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+"
    return re.fullmatch(padrao, valor) is not None


def normalizar_codigo_postal(valor, pais):
    """Valida códigos postais conforme o país selecionado e normaliza o formato."""
    valor = str(valor or "").strip().upper()
    if not valor:
        return ""
    pais = str(pais or "").strip().lower()
    digitos = re.sub(r"\D", "", valor)

    if pais == "portugal":
        if not re.fullmatch(r"\d{4}-?\d{3}", valor):
            raise ValueError("O código postal português deve ter o formato 1234-567.")
        return digitos[:4] + "-" + digitos[4:]
    if pais == "espanha" or pais == "frança":
        if not re.fullmatch(r"\d{5}", valor):
            raise ValueError(f"O código postal de {pais.title()} deve conter 5 dígitos.")
        return valor
    if pais == "brasil":
        if not re.fullmatch(r"\d{5}-?\d{3}", valor):
            raise ValueError("O CEP brasileiro deve ter o formato 12345-678.")
        return digitos[:5] + "-" + digitos[5:]

    if not re.fullmatch(r"[A-Z0-9][A-Z0-9 -]{1,14}", valor) or not any(c.isdigit() for c in valor):
        raise ValueError("Verifique o código postal: utilize letras, números, espaços ou hífen.")
    return valor


def validar_texto_descritivo(valor, campo, maximo):
    valor = " ".join(str(valor or "").split())
    if len(valor) > maximo:
        raise ValueError(f"O campo {campo} não pode ultrapassar {maximo} caracteres.")
    return valor


# ============================================================
#                 CADASTRAR NOVO CLIENTE
# ============================================================

def cadastrar_cliente():

    existente = focar_janela_aberta("novo_cliente")
    if existente is not None:
        return existente

    janela_cadastro = tk.Toplevel()

    aplicar_icone_janela(janela_cadastro)
    janela_cadastro.withdraw()  # Evita aparecer no canto antes de estar posicionada.
    registar_janela_aberta("novo_cliente", janela_cadastro)
    registrar_tema_janela(janela_cadastro)

    janela_cadastro.title(
        "TB Software - Novo Cliente"
    )

    janela_cadastro.geometry(
        "720x640"
    )

    janela_cadastro.resizable(
        False,
        False
    )

    janela_cadastro.configure(
        bg=COR_FUNDO
    )

    # Rodapé e ações ficam fixos; apenas os campos do formulário rolam.
    criar_rodape(janela_cadastro)
    painel_acoes = tk.Frame(janela_cadastro, bg=COR_FUNDO)
    painel_acoes.pack(side="bottom", fill="x", pady=(2, 4))

    tk.Label(
        janela_cadastro,
        text="＋  Novo Cliente",
        font=FONTE_16_NEGRITO,
        bg=COR_FUNDO,
        fg=COR_PRINCIPAL
    ).pack(
        pady=(12, 4)
    )

    tk.Label(
        janela_cadastro,
        text="Preencha os dados do cliente.",
        font=FONTE_8,
        bg=COR_FUNDO,
        fg=COR_SECUNDARIA
    ).pack(
        pady=(0, 5)
    )

    area_rolagem, canvas_formulario, cartao = criar_area_formulario_rolavel(
        janela_cadastro,
        COR_FUNDO
    )
    area_rolagem.pack(
        padx=18,
        pady=(4, 5),
        fill="both",
        expand=True
    )

    def criar_campo(texto, row, column, width=30, colspan=1):

        tk.Label(
            cartao,
            text=texto,
            font=FONTE_8_NEGRITO,
            bg=COR_PAINEL,
            fg=COR_SECUNDARIA
        ).grid(
            row=row,
            column=column,
            columnspan=colspan,
            sticky="w",
            padx=(18, 8),
            pady=(5, 3)
        )

        entrada = tk.Entry(
            cartao,
            width=width,
            font=FONTE_8
        )

        entrada.grid(
            row=row + 1,
            column=column,
            columnspan=colspan,
            sticky="ew",
            padx=(18, 8),
            pady=(0, 5),
            ipady=2
        )

        return entrada

    entrada_nif = criar_campo(
        "NIF / Identificação Fiscal",
        0,
        0,
        width=24
    )

    entrada_nome = criar_campo(
        "Nome *",
        0,
        1,
        width=42
    )

    tk.Label(
        cartao,
        text="Tipo de Cliente",
        font=FONTE_8_NEGRITO,
        bg=COR_PAINEL,
        fg=COR_SECUNDARIA
    ).grid(
        row=2,
        column=0,
        sticky="w",
        padx=(18, 8),
        pady=(7, 4)
    )

    tipo_cliente = tk.StringVar(
        value="Particular"
    )

    combo_tipo = ttk.Combobox(
        cartao,
        textvariable=tipo_cliente,
        values=("Particular", "Empresa"),
        state="readonly",
        font=FONTE_8
    )

    combo_tipo.grid(
        row=3,
        column=0,
        sticky="ew",
        padx=(18, 8),
        pady=(0, 5),
        ipady=2
    )

    data_nascimento = criar_campo(
        "Data de Nascimento (DD/MM/AAAA)",
        2,
        1,
        width=42
    )

    nacionalidade = criar_campo(
        "Nacionalidade",
        4,
        0,
        width=24
    )

    entrada_telefone = criar_campo(
        "Telefone *",
        4,
        1,
        width=42
    )

    movel = criar_campo(
        "Telemóvel",
        6,
        0,
        width=24
    )

    email = criar_campo(
        "Email",
        6,
        1,
        width=42
    )

    tk.Label(
        cartao,
        text="Morada *",
        font=FONTE_8_NEGRITO,
        bg=COR_PAINEL,
        fg=COR_SECUNDARIA
    ).grid(
        row=8,
        column=0,
        columnspan=2,
        sticky="w",
        padx=(18, 8),
        pady=(7, 4)
    )

    entrada_endereco = tk.Entry(
        cartao,
        width=70,
        font=FONTE_9
    )

    entrada_endereco.grid(
        row=9,
        column=0,
        columnspan=2,
        sticky="ew",
        padx=(18, 18),
        pady=(0, 5),
        ipady=2
    )

    codigo_postal = criar_campo(
        "Código Postal",
        10,
        0,
        width=24
    )

    entrada_cidade = criar_campo(
        "Localidade *",
        10,
        1,
        width=42
    )

    tk.Label(
        cartao,
        text="País",
        font=FONTE_8_NEGRITO,
        bg=COR_PAINEL,
        fg=COR_SECUNDARIA
    ).grid(
        row=12,
        column=0,
        sticky="w",
        padx=(18, 8),
        pady=(7, 4)
    )

    pais_var = tk.StringVar(
        value="Portugal"
    )

    combo_pais = ttk.Combobox(
        cartao,
        textvariable=pais_var,
        values=(
            "Portugal",
            "Espanha",
            "França",
            "Brasil",
            "Outro"
        ),
        state="readonly",
        font=FONTE_8
    )

    combo_pais.grid(
        row=13,
        column=0,
        sticky="ew",
        padx=(18, 8),
        pady=(0, 6),
        ipady=2
    )

    passaporte = criar_campo(
        "Passaporte",
        12,
        1,
        width=42
    )

    cartao.columnconfigure(0, weight=1)
    cartao.columnconfigure(1, weight=2)

    # Validadores de entrada: impedem caracteres incompatíveis e limites excessivos.
    configurar_validacao_entrada(entrada_nif, validar_proposta_nif)
    configurar_validacao_entrada(passaporte, validar_proposta_passaporte)
    configurar_validacao_entrada(data_nascimento, validar_proposta_data)
    configurar_validacao_entrada(entrada_telefone, validar_proposta_telefone)
    configurar_validacao_entrada(movel, validar_proposta_telefone)
    configurar_validacao_entrada(email, validar_proposta_email)
    configurar_validacao_entrada(codigo_postal, validar_proposta_codigo_postal)
    for campo, limite in (
        (entrada_nome, 120), (entrada_endereco, 200),
        (nacionalidade, 60), (entrada_cidade, 80)
    ):
        validar_tamanho_entrada(campo, limite)
    data_nascimento.bind("<KeyRelease>", aplicar_mascara_data, add="+")
    codigo_postal.bind(
        "<KeyRelease>",
        lambda evento: aplicar_mascara_codigo_postal(evento, pais_var.get),
        add="+"
    )
    combo_pais.bind(
        "<<ComboboxSelected>>",
        lambda evento: codigo_postal.event_generate("<KeyRelease>"),
        add="+"
    )

    def salvar_cliente():

        nome = validar_texto_descritivo(entrada_nome.get(), "Nome", 120)
        nif_original = entrada_nif.get().strip()
        nif = nif_original
        passaporte_original = passaporte.get().strip()
        passaporte_normalizado = passaporte_original
        endereco = validar_texto_descritivo(entrada_endereco.get(), "Morada", 200)
        telefone_original = entrada_telefone.get().strip()
        telefone = telefone_original
        cidade = validar_texto_descritivo(entrada_cidade.get(), "Localidade", 80)

        tipo = tipo_cliente.get().strip()
        nascimento_original = data_nascimento.get().strip()
        nascimento = nascimento_original
        nac = validar_texto_descritivo(nacionalidade.get(), "Nacionalidade", 60)
        telefone_movel_original = movel.get().strip()
        telefone_movel = telefone_movel_original
        endereco_email = email.get().strip()
        postal_original = codigo_postal.get().strip()
        postal = postal_original
        pais = pais_var.get().strip()

        if not nome or not any(caracter.isalpha() for caracter in nome):
            messagebox.showerror(
                "Erro",
                "Digite um nome válido, contendo pelo menos uma letra.",
                parent=janela_cadastro
            )
            entrada_nome.focus_set()
            return

        if not cidade or not any(caracter.isalpha() for caracter in cidade):
            messagebox.showerror(
                "Erro",
                "Digite uma localidade válida, contendo pelo menos uma letra.",
                parent=janela_cadastro
            )
            entrada_cidade.focus_set()
            return

        try:
            nif = normalizar_identificacao_fiscal(nif_original, pais)
            passaporte_normalizado = normalizar_passaporte(passaporte_original)
        except ValueError as erro:
            messagebox.showerror("Identificação inválida", str(erro), parent=janela_cadastro)
            entrada_nif.focus_set()
            return

        if not nif and not passaporte_normalizado:
            messagebox.showerror(
                "Identificação obrigatória",
                "Preencha a identificação fiscal ou o número do passaporte.",
                parent=janela_cadastro
            )
            entrada_nif.focus_set()
            return

        if nif and not clientes.nif_disponivel(nif):
            messagebox.showerror(
                "Identificação fiscal duplicada",
                "Esta identificação fiscal já está cadastrada.",
                parent=janela_cadastro
            )
            entrada_nif.focus_set()
            return

        if passaporte_normalizado and not passaporte_disponivel(passaporte_normalizado, pais):
            messagebox.showerror(
                "Passaporte duplicado",
                "Este passaporte já está cadastrado para este país.",
                parent=janela_cadastro
            )
            passaporte.focus_set()
            return

        if not endereco:
            messagebox.showerror(
                "Erro",
                "Digite a morada.",
                parent=janela_cadastro
            )
            return

        try:
            telefone = normalizar_telefone(telefone_original, "Telefone", obrigatorio=True)
        except ValueError as erro:
            messagebox.showerror("Telefone inválido", str(erro), parent=janela_cadastro)
            entrada_telefone.focus_set()
            return

        if not clientes.telefone_disponivel(telefone):
            messagebox.showerror(
                "Erro",
                "Este telefone já está cadastrado.",
                parent=janela_cadastro
            )
            return

        if not cidade:
            messagebox.showerror(
                "Erro",
                "Digite a localidade.",
                parent=janela_cadastro
            )
            return

        if not email_valido(endereco_email):
            messagebox.showerror(
                "Email inválido",
                "Introduza um endereço válido, por exemplo nome@dominio.pt.",
                parent=janela_cadastro
            )
            email.focus_set()
            return

        try:
            telefone_movel = normalizar_telefone(telefone_movel_original, "Telemóvel")
            nascimento = normalizar_data_nascimento(nascimento_original)
            postal = normalizar_codigo_postal(postal_original, pais)
        except ValueError as erro:
            messagebox.showerror("Verifique os dados", str(erro), parent=janela_cadastro)
            if "nascimento" in str(erro).lower() or "data" in str(erro).lower():
                data_nascimento.focus_set()
            elif "postal" in str(erro).lower() or "cep" in str(erro).lower() or "código" in str(erro).lower():
                codigo_postal.focus_set()
            else:
                movel.focus_set()
            return

        # Aviso de possíveis duplicados por nome, contactos ou documentos.
        # Identificadores que devem ser únicos já são bloqueados acima; aqui o utilizador decide.
        duplicados = procurar_possiveis_duplicados(
            nome, nif, passaporte_normalizado, telefone, telefone_movel,
            endereco_email, pais
        )
        if not confirmar_sem_duplicado(janela_cadastro, duplicados):
            return

        # Repõe os formatos normalizados nos campos antes da confirmação.
        for campo, valor in (
            (entrada_nif, nif),
            (passaporte, passaporte_normalizado),
            (data_nascimento, nascimento),
            (codigo_postal, postal)
        ):
            campo.delete(0, tk.END)
            campo.insert(0, valor)

        confirmar = messagebox.askyesno(
            "Confirmar cadastro",
            f"Nome: {nome}\n"
            f"NIF / Identificação fiscal: {nif or '-'}\n"
            f"Passaporte: {passaporte_normalizado or '-'}\n"
            f"Tipo: {tipo}\n"
            f"Morada: {endereco}\n"
            f"Telefone: {telefone}\n"
            f"Telemóvel: {telefone_movel or '-'}\n"
            f"Email: {endereco_email or '-'}\n"
            f"Localidade: {cidade}\n"
            f"País: {pais}\n\n"
            "Deseja cadastrar este cliente?",
            parent=janela_cadastro
        )

        if not confirmar:
            return

        conexao = None

        try:

            conexao, cursor = conectar_banco()

            if conexao is None:
                messagebox.showerror(
                    "Erro",
                    "Não foi possível conectar ao banco.",
                    parent=janela_cadastro
                )
                return

            cursor.execute("""
                INSERT INTO clientes (
                    nome,
                    nif,
                    endereco,
                    telefone,
                    cidade,
                    tipo_cliente,
                    data_nascimento,
                    nacionalidade,
                    movel,
                    email,
                    codigo_postal,
                    pais,
                    passaporte,
                    data_cadastro
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nome.title(),
                nif or None,
                endereco.title(),
                telefone,
                cidade.title(),
                tipo,
                nascimento,
                nac,
                telefone_movel,
                endereco_email,
                postal,
                pais,
                passaporte_normalizado or None,
                date.today().isoformat()
            ))

            novo_cliente_id = cursor.lastrowid
            _inserir_auditoria(
                cursor, "Cliente cadastrado", cliente_id=novo_cliente_id,
                detalhes="Novo registo de cliente"
            )
            conexao.commit()

            messagebox.showinfo(
                "Sucesso",
                "Cliente cadastrado com sucesso!",
                parent=janela_cadastro
            )

            janela_cadastro.destroy()

            # Atualiza os cartões do Dashboard imediatamente após gravar
            # o cliente com sucesso (total, particulares e empresas).
            callback_dashboard = ATUALIZAR_DASHBOARD_CALLBACK
            if callable(callback_dashboard):
                try:
                    callback_dashboard()
                except (tk.TclError, sqlite3.Error) as erro_atualizacao:
                    print(f"Não foi possível atualizar o Dashboard: {erro_atualizacao}")

        except sqlite3.IntegrityError:

            if conexao:
                conexao.rollback()

            messagebox.showerror(
                "Erro",
                "Identificação fiscal, passaporte ou telefone já cadastrado.",
                parent=janela_cadastro
            )

        except sqlite3.Error as erro:

            if conexao:
                conexao.rollback()

            messagebox.showerror(
                "Erro",
                f"Erro ao cadastrar cliente:\n{erro}",
                parent=janela_cadastro
            )

        finally:

            if conexao:
                conexao.close()

    def limpar_campos():

        for entrada in (
            entrada_nome,
            entrada_nif,
            entrada_endereco,
            entrada_telefone,
            entrada_cidade,
            data_nascimento,
            nacionalidade,
            movel,
            email,
            codigo_postal,
            passaporte
        ):
            entrada.delete(0, tk.END)

        tipo_cliente.set("Particular")
        pais_var.set("Portugal")
        entrada_nif.focus_set()

    def novo_cliente():
        limpar_campos()

    frame_botoes = tk.Frame(
        painel_acoes,
        bg=COR_FUNDO
    )

    frame_botoes.pack(pady=(2, 4))

    for coluna, texto, cor, comando in (
        (0, "Limpar Campos", COR_SECUNDARIA, limpar_campos),
        (1, "Salvar", COR_BOTAO, salvar_cliente),
        (2, "Novo Cliente", COR_PRINCIPAL, novo_cliente),
    ):

        tk.Button(
            frame_botoes,
            text=texto,
            width=15,
            font=FONTE_9_NEGRITO,
            bg=cor,
            fg="white",
            relief="flat",
            cursor="hand2",
            command=comando
        ).grid(
            row=0,
            column=coluna,
            padx=5,
            ipady=3
        )

    tk.Button(
        painel_acoes,
        text="Cancelar",
        width=15,
        command=janela_cadastro.destroy
    ).pack(pady=(0, 2))

    entrada_nif.focus_set()

    janela_cadastro.bind(
        "<Return>",
        lambda event: salvar_cliente()
    )

    # Posicionar antes de mostrar para não surgir no canto e depois mover.
    centralizar_janela_na_area_util(janela_cadastro, 720, 640)
    janela_cadastro.deiconify()
    janela_cadastro.lift()
    entrada_nif.focus_set()



def listar_clientes():

    existente = focar_janela_aberta("ver_clientes")
    if existente is not None:
        return existente

    janela_lista = tk.Toplevel()

    aplicar_icone_janela(janela_lista)
    registar_janela_aberta("ver_clientes", janela_lista)
    registrar_tema_janela(janela_lista)

    janela_lista.title(
        "TB Software - Clientes"
    )

    janela_lista.geometry(
        "900x530"
    )
    centralizar_janela_na_area_util(janela_lista, 900, 530)

    janela_lista.resizable(
        False,
        False
    )

    janela_lista.configure(
        bg=COR_FUNDO
    )

    tk.Label(
        janela_lista,
        text="CLIENTES CADASTRADOS",
        font=FONTE_14_NEGRITO,
        bg=COR_FUNDO,
        fg=COR_PRINCIPAL
    ).pack(
        pady=(12, 3)
    )

    tk.Label(
        janela_lista,
        text="Consulte todos os clientes cadastrados.",
        font=FONTE_9,
        bg=COR_FUNDO,
        fg=COR_SECUNDARIA
    ).pack(
        pady=(0, 8)
    )

    frame_busca = tk.Frame(
        janela_lista,
        bg=COR_FUNDO
    )

    frame_busca.pack(
        pady=(0, 8)
    )

    tk.Label(
        frame_busca,
        text="Pesquisar:",
        font=FONTE_9_NEGRITO,
        bg=COR_FUNDO,
        fg=COR_TEXTO
    ).pack(
        side="left",
        padx=(0, 6)
    )

    entrada_filtro = tk.Entry(
        frame_busca,
        width=38,
        font=FONTE_9
    )

    entrada_filtro.pack(
        side="left",
        ipady=3
    )

    # Filtros adicionais: tipo de cliente e país, combinados com a pesquisa textual.
    frame_filtros = tk.Frame(janela_lista, bg=COR_FUNDO)
    frame_filtros.pack(pady=(0, 4))

    tk.Label(frame_filtros, text="Tipo:", font=FONTE_8_NEGRITO,
             bg=COR_FUNDO, fg=COR_TEXTO).pack(side="left", padx=(0, 4))
    filtro_tipo_var = tk.StringVar(value="Todos")
    combo_filtro_tipo = ttk.Combobox(
        frame_filtros, textvariable=filtro_tipo_var,
        values=("Todos", "Particular", "Empresa"), state="readonly", width=12
    )
    combo_filtro_tipo.pack(side="left", padx=(0, 12))

    tk.Label(frame_filtros, text="País:", font=FONTE_8_NEGRITO,
             bg=COR_FUNDO, fg=COR_TEXTO).pack(side="left", padx=(0, 4))
    filtro_pais_var = tk.StringVar(value="Todos")
    combo_filtro_pais = ttk.Combobox(
        frame_filtros, textvariable=filtro_pais_var,
        values=("Todos",), state="readonly", width=16
    )
    combo_filtro_pais.pack(side="left", padx=(0, 8))

    def limpar_filtros_lista():
        entrada_filtro.delete(0, tk.END)
        filtro_tipo_var.set("Todos")
        filtro_pais_var.set("Todos")
        atualizar_tabela()

    tk.Button(
        frame_filtros, text="Limpar filtros", command=limpar_filtros_lista,
        font=FONTE_8, relief="flat", cursor="hand2", padx=8
    ).pack(side="left")

    frame_tabela = tk.Frame(
        janela_lista,
        bg=COR_PAINEL,
        bd=1,
        relief="solid"
    )

    frame_tabela.pack(
        padx=18,
        pady=5,
        fill="both",
        expand=False
    )

    colunas = (
        "id",
        "nome",
        "nif",
        "telefone",
        "cidade",
        "tipo",
        "passaporte"
    )

    tabela = ttk.Treeview(
        frame_tabela,
        columns=colunas,
        show="headings",
        height=8
    )

    tabela.heading("id", text="ID")
    tabela.heading("nome", text="Nome")
    tabela.heading("nif", text="NIF")
    tabela.heading("telefone", text="Telefone")
    tabela.heading("cidade", text="Localidade")
    tabela.heading("tipo", text="Tipo")
    tabela.heading("passaporte", text="Passaporte")

    tabela.column("id", width=38, anchor="center")
    tabela.column("nome", width=175)
    tabela.column("nif", width=100)
    tabela.column("telefone", width=95)
    tabela.column("cidade", width=125)
    tabela.column("tipo", width=78)
    tabela.column("passaporte", width=120)

    barra = ttk.Scrollbar(
        frame_tabela,
        orient="vertical",
        command=tabela.yview
    )

    tabela.configure(
        yscrollcommand=barra.set
    )

    tabela.pack(
        side="left",
        fill="both",
        expand=True,
        padx=(5, 0),
        pady=5
    )

    barra.pack(
        side="right",
        fill="y",
        padx=(0, 5),
        pady=5
    )

    clientes_cadastrados = []

    def carregar_clientes():

        conexao = None

        try:

            conexao, cursor = conectar_banco()

            if conexao is None:
                messagebox.showerror(
                    "Erro",
                    "Não foi possível conectar ao banco.",
                    parent=janela_lista
                )
                return

            cursor.execute("""
                SELECT
                    id,
                    nome,
                    nif,
                    endereco,
                    telefone,
                    cidade,
                    tipo_cliente,
                    data_nascimento,
                    nacionalidade,
                    movel,
                    email,
                    codigo_postal,
                    pais,
                    passaporte
                FROM clientes
                ORDER BY nome COLLATE NOCASE
            """)

            clientes_cadastrados.clear()
            clientes_cadastrados.extend(cursor.fetchall())
            paises_disponiveis = sorted(
                {str(c[12]).strip() for c in clientes_cadastrados if str(c[12] or "").strip()},
                key=str.casefold
            )
            combo_filtro_pais.configure(values=("Todos", *paises_disponiveis))
            if filtro_pais_var.get() not in ("Todos", *paises_disponiveis):
                filtro_pais_var.set("Todos")

            atualizar_tabela()

        except sqlite3.Error as erro:

            messagebox.showerror(
                "Erro",
                f"Erro ao listar clientes:\n{erro}",
                parent=janela_lista
            )

        finally:

            if conexao:
                conexao.close()

    def atualizar_tabela(event=None):

        filtro = entrada_filtro.get().strip().lower()

        for item in tabela.get_children():
            tabela.delete(item)

        for cliente in clientes_cadastrados:

            campos_pesquisa = (
                str(cliente[0]), str(cliente[1] or ""), str(cliente[2] or ""),
                str(cliente[3] or ""), str(cliente[4] or ""), str(cliente[5] or ""),
                str(cliente[6] or ""), str(cliente[7] or ""), str(cliente[8] or ""),
                str(cliente[9] or ""), str(cliente[10] or ""), str(cliente[11] or ""),
                str(cliente[12] or ""), str(cliente[13] or "")
            )

            texto_pesquisa = " ".join(campos_pesquisa).casefold()
            tipo_filtro = filtro_tipo_var.get().strip()
            pais_filtro = filtro_pais_var.get().strip()

            if filtro and filtro.casefold() not in texto_pesquisa:
                continue
            if tipo_filtro != "Todos" and str(cliente[6] or "Particular").casefold() != tipo_filtro.casefold():
                continue
            if pais_filtro != "Todos" and str(cliente[12] or "").casefold() != pais_filtro.casefold():
                continue

            tabela.insert(
                "",
                "end",
                values=(
                    cliente[0],
                    cliente[1] or "",
                    cliente[2] or "",
                    cliente[4] or "",
                    cliente[5] or "",
                    cliente[6] or "Particular",
                    cliente[13] or ""
                )
            )

    def imprimir_cliente_selecionado():
        selecao = tabela.selection()
        if not selecao:
            messagebox.showwarning(
                "Imprimir cliente", "Selecione um cliente na tabela primeiro.", parent=janela_lista
            )
            return
        valores = tabela.item(selecao[0], "values")
        if not valores:
            return
        identificador = str(valores[0])
        cliente = next((registo for registo in clientes_cadastrados if str(registo[0]) == identificador), None)
        if cliente is None:
            messagebox.showerror("Imprimir cliente", "Não foi possível obter os dados deste cliente.", parent=janela_lista)
            return
        abrir_dialogo_imprimir_cliente(janela_lista, cliente)

    def abrir_cliente_selecionado(event=None):

        selecao = tabela.selection()

        if not selecao:
            return

        valores = tabela.item(
            selecao[0],
            "values"
        )

        if not valores:
            return

        identificador = valores[2] or (valores[6] if len(valores) > 6 else "")

        if not identificador:
            messagebox.showwarning(
                "Identificação em falta",
                "Este cliente não tem NIF nem passaporte registado.",
                parent=janela_lista
            )
            return

        janela_lista.destroy()

        # Abre a pesquisa já preparada com o NIF ou passaporte selecionado.
        procurar_cliente_com_identificador(identificador)

    def procurar_cliente_com_identificador(identificador):

        # Usa a própria função normal de pesquisa através de uma
        # janela temporária simples para evitar duplicar a lógica.
        procurar_cliente()

        # A janela de procura é a última Toplevel criada.
        janelas = [
            w for w in janela_lista.master.winfo_children()
            if isinstance(w, tk.Toplevel)
        ]

        if not janelas:
            return

        janela_procura = janelas[-1]

        # Localiza a entrada de pesquisa pela ordem dos widgets.
        def preencher():

            for widget in janela_procura.winfo_children():

                if isinstance(widget, tk.Frame):
                    for filho in widget.winfo_children():

                        if isinstance(filho, tk.Entry):
                            filho.insert(0, identificador)
                            filho.event_generate("<Return>")
                            return

        janela_procura.after(
            50,
            preencher
        )

    entrada_filtro.bind("<KeyRelease>", atualizar_tabela)
    combo_filtro_tipo.bind("<<ComboboxSelected>>", atualizar_tabela)
    combo_filtro_pais.bind("<<ComboboxSelected>>", atualizar_tabela)

    tabela.bind(
        "<Double-1>",
        abrir_cliente_selecionado
    )

    tk.Label(
        janela_lista,
        text="Duplo clique em um cliente para abrir os dados.",
        font=FONTE_9,
        bg=COR_FUNDO,
        fg=COR_SECUNDARIA
    ).pack(
        pady=(3, 3)
    )

    frame_botoes = tk.Frame(
        janela_lista,
        bg=COR_FUNDO
    )

    frame_botoes.pack(
        pady=(3, 8)
    )

    tk.Button(
        frame_botoes,
        text="Imprimir",
        width=15,
        font=FONTE_9_NEGRITO,
        bg=COR_PRINCIPAL,
        fg="white",
        relief="flat",
        cursor="hand2",
        command=imprimir_cliente_selecionado
    ).grid(
        row=0,
        column=0,
        padx=5,
        ipady=3
    )

    tk.Button(
        frame_botoes,
        text="Atualizar",
        width=15,
        font=FONTE_9_NEGRITO,
        bg=COR_BOTAO,
        fg="white",
        relief="flat",
        command=carregar_clientes
    ).grid(
        row=0,
        column=1,
        padx=5,
        ipady=3
    )

    tk.Button(
        frame_botoes,
        text="Voltar",
        width=15,
        command=janela_lista.destroy
    ).grid(
        row=0,
        column=2,
        padx=5,
        ipady=3
    )

    criar_rodape(janela_lista)

    carregar_clientes()


# ============================================================
#                  PROCURAR CLIENTE
# ============================================================

def procurar_cliente():

    existente = focar_janela_aberta("procurar_cliente")
    if existente is not None:
        return existente

    janela_procurar = tk.Toplevel()

    aplicar_icone_janela(janela_procurar)
    janela_procurar.withdraw()  # Evita aparecer no canto antes de estar posicionada.
    registar_janela_aberta("procurar_cliente", janela_procurar)
    registrar_tema_janela(janela_procurar)

    janela_procurar.title(
        "TB Software - Procurar Cliente"
    )

    janela_procurar.geometry(
        "700x700"
    )

    janela_procurar.resizable(
        False,
        False
    )

    janela_procurar.configure(
        bg=COR_FUNDO
    )

    # Rodapé e botões são fixos; a ficha do cliente pode ser percorrida.
    criar_rodape(janela_procurar)
    painel_acoes = tk.Frame(janela_procurar, bg=COR_FUNDO)
    painel_acoes.pack(side="bottom", fill="x", pady=(2, 4))

    tk.Label(
        janela_procurar,
        text="⌕  Procurar Cliente",
        font=FONTE_14_NEGRITO,
        bg=COR_FUNDO,
        fg=COR_PRINCIPAL
    ).pack(
        pady=(12, 4)
    )

    tk.Label(
        janela_procurar,
        text="Pesquise pelo NIF / identificação fiscal ou passaporte.",
        font=FONTE_8,
        bg=COR_FUNDO,
        fg=COR_SECUNDARIA
    ).pack(
        pady=(0, 5)
    )

    frame_pesquisa = tk.Frame(
        janela_procurar,
        bg=COR_FUNDO
    )

    frame_pesquisa.pack(
        pady=5
    )

    tk.Label(
        frame_pesquisa,
        text="NIF / Passaporte:",
        font=FONTE_8_NEGRITO,
        bg=COR_FUNDO,
        fg=COR_TEXTO
    ).grid(
        row=0,
        column=0,
        padx=(0, 8)
    )

    entrada_pesquisa = tk.Entry(
        frame_pesquisa,
        width=30,
        font=FONTE_8
    )
    configurar_validacao_entrada(entrada_pesquisa, validar_proposta_nif)

    entrada_pesquisa.grid(
        row=0,
        column=1,
        ipady=3,
        padx=5
    )

    area_rolagem, canvas_formulario, cartao = criar_area_formulario_rolavel(
        janela_procurar,
        COR_FUNDO
    )
    area_rolagem.pack(
        padx=18,
        pady=(4, 5),
        fill="both",
        expand=True
    )

    tk.Label(
        cartao,
        text="ID:",
        font=FONTE_8_NEGRITO,
        bg=COR_PAINEL,
        fg=COR_SECUNDARIA
    ).grid(
        row=0,
        column=0,
        sticky="w",
        padx=(18, 8),
        pady=(12, 5)
    )

    label_id = tk.Label(
        cartao,
        text="-",
        font=FONTE_9_NEGRITO,
        bg=COR_PAINEL,
        fg=COR_PRINCIPAL
    )

    label_id.grid(
        row=0,
        column=1,
        sticky="w",
        padx=5,
        pady=(12, 5)
    )

    campos = {}

    def adicionar_entrada(texto, chave, row, columnspan=2):

        tk.Label(
            cartao,
            text=texto,
            font=FONTE_8_NEGRITO,
            bg=COR_PAINEL,
            fg=COR_SECUNDARIA
        ).grid(
            row=row,
            column=0,
            sticky="w",
            padx=(18, 8),
            pady=4
        )

        entrada = tk.Entry(
            cartao,
            width=42,
            font=FONTE_8,
            state="disabled"
        )

        entrada.grid(
            row=row,
            column=1,
            columnspan=columnspan - 1,
            sticky="ew",
            padx=(5, 18),
            pady=4,
            ipady=2
        )

        campos[chave] = entrada

    adicionar_entrada("Nome:", "nome", 1)
    adicionar_entrada("NIF:", "nif", 2)
    adicionar_entrada("Morada:", "endereco", 3)
    adicionar_entrada("Telefone:", "telefone", 4)
    adicionar_entrada("Localidade:", "cidade", 5)
    adicionar_entrada("Tipo:", "tipo_cliente", 6)
    adicionar_entrada("Data Nascimento (DD/MM/AAAA):", "data_nascimento", 7)
    adicionar_entrada("Nacionalidade:", "nacionalidade", 8)
    adicionar_entrada("Telemóvel:", "movel", 9)
    adicionar_entrada("Email:", "email", 10)
    adicionar_entrada("Código Postal:", "codigo_postal", 11)
    adicionar_entrada("País:", "pais", 12)
    adicionar_entrada("Passaporte:", "passaporte", 13)

    # Os mesmos limites e formatos são aplicados durante a edição de um cliente.
    configurar_validacao_entrada(campos["nif"], validar_proposta_nif)
    configurar_validacao_entrada(campos["passaporte"], validar_proposta_passaporte)
    configurar_validacao_entrada(campos["data_nascimento"], validar_proposta_data)
    configurar_validacao_entrada(campos["telefone"], validar_proposta_telefone)
    configurar_validacao_entrada(campos["movel"], validar_proposta_telefone)
    configurar_validacao_entrada(campos["email"], validar_proposta_email)
    configurar_validacao_entrada(campos["codigo_postal"], validar_proposta_codigo_postal)
    for chave, limite in (("nome", 120), ("endereco", 200), ("cidade", 80), ("nacionalidade", 60), ("pais", 40), ("tipo_cliente", 30), ("passaporte", 24)):
        validar_tamanho_entrada(campos[chave], limite)
    campos["data_nascimento"].bind("<KeyRelease>", aplicar_mascara_data, add="+")
    campos["codigo_postal"].bind(
        "<KeyRelease>",
        lambda evento: aplicar_mascara_codigo_postal(evento, campos["pais"].get),
        add="+"
    )

    cartao.columnconfigure(
        1,
        weight=1
    )

    cliente_atual = [None]

    def alterar_estado_campos(estado):

        for entrada in campos.values():
            entrada.config(
                state=estado
            )

    def abrir_atendimento_atual():
        cliente = cliente_atual[0]
        if cliente is None:
            messagebox.showwarning("Atendimento", "Primeiro pesquisa um cliente.", parent=janela_procurar)
            return
        abrir_historico_atendimento_cliente(janela_procurar, cliente[0], cliente[1])

    def imprimir_cliente_atual():
        cliente = cliente_atual[0]
        if cliente is None:
            messagebox.showwarning(
                "Imprimir cliente", "Primeiro pesquise um cliente.", parent=janela_procurar
            )
            return
        abrir_dialogo_imprimir_cliente(janela_procurar, cliente)

    def limpar_cliente():

        cliente_atual[0] = None

        label_id.config(
            text="-"
        )

        for entrada in campos.values():

            entrada.config(
                state="normal"
            )

            entrada.delete(
                0,
                tk.END
            )

            entrada.config(
                state="disabled"
            )

        botao_salvar.config(
            state="disabled"
        )

        botao_imprimir.config(state="disabled")

        botao_excluir.config(
            state="disabled"
        )
        botao_atendimento.config(state="disabled")

    def pesquisar_cliente():

        identificador_pesquisa = entrada_pesquisa.get().strip()

        if not identificador_pesquisa:
            messagebox.showerror(
                "Identificação em falta",
                "Digite o NIF / identificação fiscal ou o número do passaporte.",
                parent=janela_procurar
            )
            entrada_pesquisa.focus_set()
            return

        try:
            identificador_pesquisa = normalizar_identificador_pesquisa(identificador_pesquisa)
        except ValueError as erro:
            messagebox.showerror("Identificação inválida", str(erro), parent=janela_procurar)
            entrada_pesquisa.focus_set()
            return

        conexao = None

        try:

            conexao, cursor = conectar_banco()

            if conexao is None:
                messagebox.showerror(
                    "Erro",
                    "Não foi possível conectar ao banco.",
                    parent=janela_procurar
                )
                return

            cursor.execute("""
                SELECT
                    id,
                    nome,
                    nif,
                    endereco,
                    telefone,
                    cidade,
                    tipo_cliente,
                    data_nascimento,
                    nacionalidade,
                    movel,
                    email,
                    codigo_postal,
                    pais,
                    passaporte
                FROM clientes
                WHERE UPPER(REPLACE(REPLACE(REPLACE(COALESCE(nif, ''), ' ', ''), '.', ''), '-', '')) = ?
                   OR UPPER(REPLACE(REPLACE(COALESCE(passaporte, ''), ' ', ''), '-', '')) = ?
                LIMIT 1
            """, (identificador_pesquisa, identificador_pesquisa))

            cliente = cursor.fetchone()

            if cliente is None:

                limpar_cliente()

                messagebox.showinfo(
                    "Pesquisa",
                    "Nenhum cliente encontrado.",
                    parent=janela_procurar
                )
                return

            cliente_atual[0] = cliente

            label_id.config(
                text=str(cliente[0])
            )

            valores = {
                "nome": cliente[1],
                "nif": cliente[2],
                "endereco": cliente[3],
                "telefone": cliente[4],
                "cidade": cliente[5],
                "tipo_cliente": cliente[6],
                "data_nascimento": cliente[7],
                "nacionalidade": cliente[8],
                "movel": cliente[9],
                "email": cliente[10],
                "codigo_postal": cliente[11],
                "pais": cliente[12],
                "passaporte": cliente[13]
            }

            alterar_estado_campos("normal")

            for chave, valor in valores.items():

                # Permitir carregar dados históricos mesmo que excedam os limites
                # de digitação; a validação volta a ficar ativa após preencher.
                campos[chave].configure(validate="none")
                campos[chave].delete(
                    0,
                    tk.END
                )

                if chave == "data_nascimento":
                    valor = data_nascimento_para_tela(valor)
                campos[chave].insert(
                    0,
                    "" if valor is None else str(valor)
                )
                campos[chave].configure(validate="key")

            botao_salvar.config(
                state="normal"
            )

            botao_imprimir.config(state="normal")

            botao_excluir.config(
                state="normal" if obter_perfil_usuario(usuario_logado) == "Administrador" else "disabled"
            )
            botao_atendimento.config(state="normal")

        except sqlite3.Error as erro:

            messagebox.showerror(
                "Erro",
                f"Erro ao pesquisar cliente:\n{erro}",
                parent=janela_procurar
            )

        finally:

            if conexao:
                conexao.close()

    def salvar_alteracao():

        cliente = cliente_atual[0]

        if cliente is None:
            messagebox.showerror(
                "Erro",
                "Primeiro pesquise um cliente.",
                parent=janela_procurar
            )
            return

        valores = {
            chave: campos[chave].get().strip()
            for chave in campos
        }

        try:
            nome = validar_texto_descritivo(valores["nome"], "Nome", 120)
            endereco = validar_texto_descritivo(valores["endereco"], "Morada", 200)
            cidade = validar_texto_descritivo(valores["cidade"], "Localidade", 80)
            nif = normalizar_identificacao_fiscal(valores["nif"], valores["pais"])
            passaporte_normalizado = normalizar_passaporte(valores["passaporte"])
            nascimento = normalizar_data_nascimento(valores["data_nascimento"])
            postal = normalizar_codigo_postal(valores["codigo_postal"], valores["pais"])
            telefone = normalizar_telefone(valores["telefone"], "Telefone", obrigatorio=True)
            telefone_movel_normalizado = normalizar_telefone(valores["movel"], "Telemóvel")
        except ValueError as erro:
            messagebox.showerror("Verifique os dados", str(erro), parent=janela_procurar)
            return

        if not nome or not any(caracter.isalpha() for caracter in nome):
            messagebox.showerror("Nome inválido", "Introduza um nome com pelo menos uma letra.", parent=janela_procurar)
            campos["nome"].focus_set()
            return
        if not cidade or not any(caracter.isalpha() for caracter in cidade):
            messagebox.showerror("Localidade inválida", "Introduza uma localidade com pelo menos uma letra.", parent=janela_procurar)
            campos["cidade"].focus_set()
            return
        if not email_valido(valores["email"]):
            messagebox.showerror("Email inválido", "Introduza um endereço válido, por exemplo nome@dominio.pt.", parent=janela_procurar)
            campos["email"].focus_set()
            return

        endereco = validar_texto_descritivo(endereco, "Morada", 200)
        valores["data_nascimento"] = nascimento
        valores["codigo_postal"] = postal
        valores["telefone"] = telefone
        valores["movel"] = telefone_movel_normalizado
        valores["email"] = valores["email"].strip()
        valores["passaporte"] = passaporte_normalizado

        if not nif and not passaporte_normalizado:
            messagebox.showerror(
                "Identificação obrigatória",
                "Preencha a identificação fiscal ou o número do passaporte.",
                parent=janela_procurar
            )
            campos["nif"].focus_set()
            return

        if not nome:
            messagebox.showerror(
                "Erro",
                "O nome não pode ficar vazio.",
                parent=janela_procurar
            )
            return

        if not endereco:
            messagebox.showerror(
                "Erro",
                "A morada não pode ficar vazia.",
                parent=janela_procurar
            )
            return


        if not cidade:
            messagebox.showerror(
                "Erro",
                "A localidade não pode ficar vazia.",
                parent=janela_procurar
            )
            return

        if nif and nif != (cliente[2] or ""):
            if not clientes.nif_disponivel(nif):
                messagebox.showerror(
                    "Identificação fiscal duplicada",
                    "Esta identificação fiscal já está cadastrada.",
                    parent=janela_procurar
                )
                campos["nif"].focus_set()
                return

        passaporte_anterior = re.sub(r"[\s-]", "", str(cliente[13] or "")).upper()
        pais_anterior = str(cliente[12] or "").strip().casefold()
        pais_novo = str(valores["pais"] or "").strip().casefold()
        # Revalidar também se o país do registo mudou, mesmo que o passaporte
        # tenha permanecido igual.
        if passaporte_normalizado and (
            passaporte_normalizado != passaporte_anterior or pais_novo != pais_anterior
        ):
            if not passaporte_disponivel(passaporte_normalizado, valores["pais"], ignorar_id=cliente[0]):
                messagebox.showerror(
                    "Passaporte duplicado",
                    "Este passaporte já está cadastrado para este país.",
                    parent=janela_procurar
                )
                campos["passaporte"].focus_set()
                return

        if telefone != cliente[4]:

            try:

                if not clientes.telefone_disponivel(telefone):
                    messagebox.showerror(
                        "Erro",
                        "Este telefone já está cadastrado.",
                        parent=janela_procurar
                    )
                    return

            except Exception:
                pass


        duplicados = procurar_possiveis_duplicados(
            nome, nif, passaporte_normalizado, telefone,
            telefone_movel_normalizado, valores["email"], valores["pais"],
            ignorar_id=cliente[0]
        )
        if not confirmar_sem_duplicado(janela_procurar, duplicados):
            return

        confirmar = messagebox.askyesno(
            "Confirmar alteração",
            "Deseja salvar as alterações deste cliente?",
            parent=janela_procurar
        )

        if not confirmar:
            return

        conexao = None

        try:

            conexao, cursor = conectar_banco()

            if conexao is None:
                messagebox.showerror(
                    "Erro",
                    "Não foi possível conectar ao banco.",
                    parent=janela_procurar
                )
                return

            cursor.execute("""
                UPDATE clientes
                SET nome = ?,
                    nif = ?,
                    endereco = ?,
                    telefone = ?,
                    cidade = ?,
                    tipo_cliente = ?,
                    data_nascimento = ?,
                    nacionalidade = ?,
                    movel = ?,
                    email = ?,
                    codigo_postal = ?,
                    pais = ?,
                    passaporte = ?
                WHERE id = ?
            """, (
                nome,
                nif or None,
                endereco,
                telefone,
                cidade,
                valores["tipo_cliente"],
                valores["data_nascimento"],
                valores["nacionalidade"],
                valores["movel"],
                valores["email"],
                valores["codigo_postal"],
                valores["pais"],
                passaporte_normalizado or None,
                cliente[0]
            ))

            _inserir_auditoria(
                cursor, "Cliente alterado", cliente_id=cliente[0],
                detalhes="Dados do cliente atualizados"
            )
            conexao.commit()

            cursor.execute("""
                SELECT
                    id,
                    nome,
                    nif,
                    endereco,
                    telefone,
                    cidade,
                    tipo_cliente,
                    data_nascimento,
                    nacionalidade,
                    movel,
                    email,
                    codigo_postal,
                    pais,
                    passaporte
                FROM clientes
                WHERE id = ?
            """, (cliente[0],))

            cliente_atual[0] = cursor.fetchone()
            cliente_novo = cliente_atual[0]

            label_id.config(
                text=str(cliente_novo[0])
            )

            valores_atualizados = {
                "nome": cliente_novo[1],
                "nif": cliente_novo[2],
                "endereco": cliente_novo[3],
                "telefone": cliente_novo[4],
                "cidade": cliente_novo[5],
                "tipo_cliente": cliente_novo[6],
                "data_nascimento": cliente_novo[7],
                "nacionalidade": cliente_novo[8],
                "movel": cliente_novo[9],
                "email": cliente_novo[10],
                "codigo_postal": cliente_novo[11],
                "pais": cliente_novo[12],
                "passaporte": cliente_novo[13]
            }

            alterar_estado_campos("normal")

            for chave, valor in valores_atualizados.items():

                # Permitir carregar dados históricos mesmo que excedam os limites
                # de digitação; a validação volta a ficar ativa após preencher.
                campos[chave].configure(validate="none")
                campos[chave].delete(
                    0,
                    tk.END
                )

                if chave == "data_nascimento":
                    valor = data_nascimento_para_tela(valor)
                campos[chave].insert(
                    0,
                    "" if valor is None else str(valor)
                )
                campos[chave].configure(validate="key")

            botao_salvar.config(
                state="normal"
            )

            botao_excluir.config(
                state="normal" if obter_perfil_usuario(usuario_logado) == "Administrador" else "disabled"
            )

            messagebox.showinfo(
                "Sucesso",
                "Cliente alterado com sucesso!",
                parent=janela_procurar
            )

        except sqlite3.IntegrityError:

            if conexao:
                conexao.rollback()

            messagebox.showerror(
                "Erro",
                "NIF ou telefone já cadastrado.",
                parent=janela_procurar
            )

        except sqlite3.Error as erro:

            if conexao:
                conexao.rollback()

            messagebox.showerror(
                "Erro",
                f"Erro ao alterar cliente:\n{erro}",
                parent=janela_procurar
            )

        finally:

            if conexao:
                conexao.close()

    def excluir_cliente_atual():

        if obter_perfil_usuario(usuario_logado) != "Administrador":
            messagebox.showerror(
                "Acesso negado",
                "Apenas um Administrador pode excluir clientes.",
                parent=janela_procurar
            )
            return

        cliente = cliente_atual[0]

        if cliente is None:
            messagebox.showerror(
                "Erro",
                "Primeiro pesquise um cliente.",
                parent=janela_procurar
            )
            return

        confirmar = messagebox.askyesno(
            "Confirmar exclusão",
            f"ID: {cliente[0]}\n"
            f"Nome: {cliente[1]}\n"
            f"NIF / Identificação fiscal: {cliente[2] or '-'}\n"
            f"Passaporte: {cliente[13] or '-'}\n\n"
            "Deseja realmente excluir este cliente?",
            parent=janela_procurar
        )

        if not confirmar:
            return

        conexao = None

        try:

            conexao, cursor = conectar_banco()

            if conexao is None:
                messagebox.showerror(
                    "Erro",
                    "Não foi possível conectar ao banco.",
                    parent=janela_procurar
                )
                return

            cursor.execute(
                "DELETE FROM clientes WHERE id = ?",
                (cliente[0],)
            )
            # Mantém os registos de atendimento históricos; cancela lembretes pendentes do cliente removido.
            cursor.execute(
                "UPDATE lembretes_clientes SET status='Cancelado' WHERE cliente_id=? AND status='Pendente'",
                (cliente[0],)
            )
            _inserir_auditoria(
                cursor, "Cliente excluído", cliente_id=cliente[0],
                detalhes="Registo de cliente removido"
            )

            conexao.commit()

            limpar_cliente()

            entrada_pesquisa.delete(
                0,
                tk.END
            )

            entrada_pesquisa.focus_set()

            messagebox.showinfo(
                "Sucesso",
                "Cliente excluído com sucesso!",
                parent=janela_procurar
            )

            # Atualiza os cartões do Dashboard imediatamente após a exclusão,
            # sem exigir que o utilizador clique novamente em Início.
            callback_dashboard = ATUALIZAR_DASHBOARD_CALLBACK
            if callable(callback_dashboard):
                try:
                    callback_dashboard()
                except (tk.TclError, sqlite3.Error) as erro_atualizacao:
                    print(f"Não foi possível atualizar o Dashboard após excluir cliente: {erro_atualizacao}")

        except sqlite3.Error as erro:

            if conexao:
                conexao.rollback()

            messagebox.showerror(
                "Erro",
                f"Erro ao excluir cliente:\n{erro}",
                parent=janela_procurar
            )

        finally:

            if conexao:
                conexao.close()

    frame_botoes = tk.Frame(
        painel_acoes,
        bg=COR_FUNDO
    )

    frame_botoes.pack(pady=(2, 4))

    botao_pesquisar = tk.Button(
        frame_botoes,
        text="Pesquisar",
        width=15,
        font=FONTE_9_NEGRITO,
        bg=COR_BOTAO,
        fg="white",
        relief="flat",
        cursor="hand2",
        command=pesquisar_cliente
    )

    botao_pesquisar.grid(
        row=0,
        column=0,
        padx=5,
        ipady=3
    )

    botao_imprimir = tk.Button(
        frame_botoes,
        text="Imprimir",
        width=13,
        font=FONTE_9_NEGRITO,
        bg=COR_PRINCIPAL,
        fg="white",
        relief="flat",
        cursor="hand2",
        state="disabled",
        command=imprimir_cliente_atual
    )

    botao_imprimir.grid(
        row=0,
        column=3,
        padx=5,
        ipady=3
    )

    botao_salvar = tk.Button(
        frame_botoes,
        text="Guardar Alteração",
        width=17,
        font=FONTE_9_NEGRITO,
        bg=COR_BOTAO,
        fg="white",
        relief="flat",
        cursor="hand2",
        state="disabled",
        command=salvar_alteracao
    )

    botao_salvar.grid(
        row=0,
        column=1,
        padx=5,
        ipady=3
    )

    botao_excluir = tk.Button(
        frame_botoes,
        text="Excluir",
        width=14,
        font=FONTE_9_NEGRITO,
        bg="#d83a3a",
        fg="white",
        relief="flat",
        cursor="hand2",
        state="disabled",
        command=excluir_cliente_atual
    )

    botao_excluir.grid(
        row=0,
        column=2,
        padx=5,
        ipady=3
    )

    botao_atendimento = tk.Button(
        frame_botoes,
        text="Histórico de Atendimento",
        width=22,
        font=FONTE_9_NEGRITO,
        bg=COR_PRINCIPAL,
        fg="white",
        relief="flat",
        cursor="hand2",
        state="disabled",
        command=abrir_atendimento_atual
    )
    botao_atendimento.grid(row=1, column=0, columnspan=4, pady=(5, 0), ipady=3)

    tk.Button(
        painel_acoes,
        text="Voltar",
        width=15,
        command=janela_procurar.destroy
    ).pack(pady=(0, 2))

    entrada_pesquisa.focus_set()

    janela_procurar.bind(
        "<Return>",
        lambda event: pesquisar_cliente()
    )

    # Posicionar antes de mostrar; o tamanho adapta-se à área útil do Windows.
    centralizar_janela_na_area_util(janela_procurar, 700, 700)
    janela_procurar.deiconify()
    janela_procurar.lift()
    entrada_pesquisa.focus_set()




# ==================================================
#                 ALTERAR CLIENTE
# ==================================================



# ==================================================
#                 EXCLUIR CLIENTE
# ==================================================



# ==================================================
#                  ALTERAR SENHA
# ==================================================

def alterar_senha(usuario_logado):

    chave_janela = f"alterar_senha:{str(usuario_logado).casefold()}"
    existente = focar_janela_aberta(chave_janela)
    if existente is not None:
        return existente

    janela_senha = tk.Toplevel()

    aplicar_icone_janela(janela_senha)
    registar_janela_aberta(chave_janela, janela_senha)
    registrar_tema_janela(janela_senha)

    janela_senha.title(
        "TB Software - Alterar Senha"
    )

    janela_senha.geometry(
        "450x430"
    )
    centralizar_janela_na_area_util(janela_senha, 450, 430)

    janela_senha.resizable(
        False,
        False
    )

    # ==================================================
    #                     TÍTULO
    # ==================================================

    titulo = tk.Label(
        janela_senha,
        text="ALTERAR SENHA",
        font=FONTE_18_NEGRITO
    )

    titulo.pack(pady=20)

    # ==================================================
    #                  SENHA ATUAL
    # ==================================================

    label_senha_atual = tk.Label(
        janela_senha,
        text="Senha atual:"
    )

    label_senha_atual.pack()

    entrada_senha_atual = tk.Entry(
        janela_senha,
        width=30,
        show="*"
    )

    entrada_senha_atual.pack(pady=5)

    # ==================================================
    #                   NOVA SENHA
    # ==================================================

    label_nova_senha = tk.Label(
        janela_senha,
        text="Nova senha:"
    )

    label_nova_senha.pack()

    entrada_nova_senha = tk.Entry(
        janela_senha,
        width=30,
        show="*"
    )

    entrada_nova_senha.pack(pady=5)

    # ==================================================
    #              CONFIRMAR NOVA SENHA
    # ==================================================

    label_confirmar_senha = tk.Label(
        janela_senha,
        text="Confirmar nova senha:"
    )

    label_confirmar_senha.pack()

    entrada_confirmar_senha = tk.Entry(
        janela_senha,
        width=30,
        show="*"
    )

    entrada_confirmar_senha.pack(pady=5)

    # ==================================================
    #                 SALVAR NOVA SENHA
    # ==================================================

    def salvar_nova_senha():

        senha_atual = entrada_senha_atual.get().strip()

        nova_senha = entrada_nova_senha.get().strip()

        confirmar_senha = entrada_confirmar_senha.get().strip()

        # ==================================================
        #                VALIDAR CAMPOS
        # ==================================================

        if not senha_atual:

            messagebox.showerror(
                "Erro",
                "Digite a senha atual."
            )

            return

        if not nova_senha:

            messagebox.showerror(
                "Erro",
                "Digite a nova senha."
            )

            return

        if not confirmar_senha:

            messagebox.showerror(
                "Erro",
                "Confirme a nova senha."
            )

            return

        # ==================================================
        #             VERIFICAR TAMANHO
        # ==================================================

        if len(nova_senha) < 6:

            messagebox.showerror(
                "Erro",
                "A nova senha deve ter pelo menos 6 caracteres."
            )

            return

        # ==================================================
        #              CONFIRMAR SENHAS
        # ==================================================

        if nova_senha != confirmar_senha:

            messagebox.showerror(
                "Erro",
                "As novas senhas não são iguais."
            )

            return

        # ==================================================
        #          NOVA SENHA DIFERENTE
        # ==================================================

        if nova_senha == senha_atual:

            messagebox.showerror(
                "Erro",
                "A nova senha deve ser diferente da senha atual."
            )

            return

        # ==================================================
        #             CRIAR HASH DA SENHA
        # ==================================================

        nova_senha_hash = criar_hash_senha(nova_senha)

        # ==================================================
        #                  BANCO DE DADOS
        # ==================================================

        try:

            conexao, cursor = conectar_banco()

            if conexao is None:

                messagebox.showerror(
                    "Erro",
                    "Não foi possível conectar ao banco de dados."
                )

                return

            # ==================================================
            #             VERIFICAR SENHA ATUAL
            # ==================================================

            cursor.execute("SELECT senha FROM usuarios WHERE usuario = ?", (usuario_logado,))
            usuario_encontrado = cursor.fetchone()
            senha_ok, _legado = verificar_hash_senha(
                senha_atual, usuario_encontrado[0] if usuario_encontrado else None
            )

            if not senha_ok:
                messagebox.showerror(
                    "Erro", "A senha atual está incorreta.", parent=janela_senha
                )
                return

            # ==================================================
            #                ATUALIZAR SENHA
            # ==================================================

            cursor.execute("""
                UPDATE usuarios
                SET senha = ?
                WHERE usuario = ?
            """, (
                nova_senha_hash,
                usuario_logado
            ))
            _inserir_auditoria(cursor, "Senha alterada", detalhes="O utilizador alterou a própria senha", usuario=usuario_logado)

            conexao.commit()

            conexao.close()

            # ==================================================
            #                    SUCESSO
            # ==================================================

            messagebox.showinfo(
                "Sucesso",
                "Senha alterada com sucesso!"
            )

            janela_senha.destroy()

        except sqlite3.Error as erro:

            messagebox.showerror(
                "Erro",
                f"Erro ao alterar senha:\n{erro}"
            )

    # ==================================================
    #                BOTÃO ALTERAR SENHA
    # ==================================================

    botao_alterar = tk.Button(
        janela_senha,
        text="Alterar Senha",
        width=20,
        command=salvar_nova_senha
    )

    botao_alterar.pack(
        pady=15
    )

    # ==================================================
    #                     BOTÃO VOLTAR
    # ==================================================

    botao_voltar = tk.Button(
        janela_senha,
        text="Voltar",
        width=20,
        command=janela_senha.destroy
    )

    botao_voltar.pack()


# ============================================================
#          SUBSTITUIR A SENHA PADRÃO DE INSTALAÇÕES ANTIGAS
# ============================================================
def solicitar_substituicao_senha_padrao(parent, usuario):
    """Impede a utilização continuada de admin/1234 numa base antiga."""
    janela = tk.Toplevel(parent)
    aplicar_icone_janela(janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Atualização de segurança")
    janela.geometry("470x350")
    centralizar_janela_na_area_util(janela, 470, 350)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)
    janela.transient(parent)
    janela.grab_set()

    tk.Label(
        janela, text="ATUALIZAÇÃO DE SEGURANÇA", font=FONTE_15_NEGRITO,
        bg=COR_FUNDO, fg=COR_PRINCIPAL
    ).pack(pady=(18, 6))
    tk.Label(
        janela,
        text="Esta conta ainda usa a senha padrão antiga. Crie uma nova senha para continuar.",
        font=FONTE_9, bg=COR_FUNDO, fg=COR_SECUNDARIA,
        wraplength=390, justify="center"
    ).pack(padx=20, pady=(0, 10))

    quadro = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro.pack(fill="x", padx=24, pady=4)
    quadro.columnconfigure(0, weight=1)

    tk.Label(quadro, text="Nova senha (mínimo 10 caracteres):", font=FONTE_9_NEGRITO,
             bg=COR_PAINEL, fg=COR_TEXTO).grid(row=0, column=0, sticky="w", padx=14, pady=(11, 4))
    entrada_nova = tk.Entry(quadro, font=FONTE_10, show="*")
    entrada_nova.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8), ipady=3)
    tk.Label(quadro, text="Confirmar nova senha:", font=FONTE_9_NEGRITO,
             bg=COR_PAINEL, fg=COR_TEXTO).grid(row=2, column=0, sticky="w", padx=14, pady=(3, 4))
    entrada_confirmacao = tk.Entry(quadro, font=FONTE_10, show="*")
    entrada_confirmacao.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 12), ipady=3)

    estado = {"alterada": False}

    def guardar_nova_senha():
        nova = entrada_nova.get()
        confirmar = entrada_confirmacao.get()
        if len(nova) < 10:
            messagebox.showerror("Segurança", "A nova senha deve ter pelo menos 10 caracteres.", parent=janela)
            entrada_nova.focus_set()
            return
        if nova != confirmar:
            messagebox.showerror("Segurança", "As duas senhas não coincidem.", parent=janela)
            entrada_confirmacao.delete(0, tk.END)
            entrada_confirmacao.focus_set()
            return

        con = None
        try:
            con, cur = conectar_banco()
            if con is None:
                raise sqlite3.OperationalError("Não foi possível conectar ao banco de dados.")
            hash_antigo = hashlib.sha256("1234".encode("utf-8")).hexdigest()
            cur.execute("BEGIN IMMEDIATE")
            cur.execute("SELECT senha FROM usuarios WHERE usuario = ?", (usuario,))
            linha = cur.fetchone()
            if not linha or not hmac.compare_digest(str(linha[0] or "").lower(), hash_antigo):
                raise RuntimeError("A senha já foi alterada. Feche esta janela e tente iniciar sessão novamente.")
            cur.execute("UPDATE usuarios SET senha = ? WHERE usuario = ?", (criar_hash_senha(nova), usuario))
            _inserir_auditoria(cur, "Senha padrão substituída", detalhes="Atualização obrigatória de credencial antiga", usuario=usuario)
            con.commit()
            estado["alterada"] = True
        except (sqlite3.Error, RuntimeError) as erro:
            if con:
                con.rollback()
            messagebox.showerror("Segurança", str(erro), parent=janela)
            return
        finally:
            if con:
                con.close()
        janela.destroy()
        messagebox.showinfo("Segurança", "Senha atualizada. Pode iniciar sessão com a nova senha.", parent=parent)

    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(fill="x", padx=24, pady=(10, 16))
    tk.Button(botoes, text="Guardar nova senha", command=guardar_nova_senha,
              font=FONTE_9_NEGRITO, bg=COR_BOTAO, fg="white", relief="flat",
              cursor="hand2", padx=12, pady=6).pack(side="left")
    tk.Button(botoes, text="Cancelar", command=janela.destroy,
              font=FONTE_9_NEGRITO, bg="#e8eef5", fg=COR_TEXTO, relief="flat",
              cursor="hand2", padx=14, pady=6).pack(side="right")
    entrada_nova.focus_set()
    janela.wait_window()
    return estado["alterada"]


# ============================================================
#             CONFIGURAÇÃO DO PRIMEIRO ADMINISTRADOR
# ============================================================
def existe_algum_utilizador():
    """Indica se já existe alguma conta no banco de dados."""
    conexao = None
    try:
        conexao, cursor = conectar_banco()
        if conexao is None:
            return False
        cursor.execute("SELECT 1 FROM usuarios LIMIT 1")
        return cursor.fetchone() is not None
    except sqlite3.Error as erro:
        print(f"Não foi possível verificar os utilizadores: {erro}")
        return False
    finally:
        if conexao:
            conexao.close()


def configurar_primeiro_administrador(parent):
    """Pede a criação segura da primeira conta em instalações sem utilizadores."""
    if existe_algum_utilizador():
        return None

    janela = tk.Toplevel(parent)

    aplicar_icone_janela(janela)
    registrar_tema_janela(janela)
    janela.title("TB Software - Configuração inicial")
    janela.geometry("490x470")
    centralizar_janela_na_area_util(janela, 490, 470)
    janela.resizable(False, False)
    janela.configure(bg=COR_FUNDO)
    janela.transient(parent)
    janela.grab_set()

    tk.Label(
        janela, text="CONFIGURAÇÃO INICIAL", font=FONTE_18_NEGRITO,
        bg=COR_FUNDO, fg=COR_PRINCIPAL
    ).pack(pady=(20, 5))
    tk.Label(
        janela,
        text="Crie a conta de Administrador para começar a utilizar o TB Software.",
        font=FONTE_9, bg=COR_FUNDO, fg=COR_SECUNDARIA,
        wraplength=390, justify="center"
    ).pack(padx=22, pady=(0, 12))

    quadro = tk.Frame(janela, bg=COR_PAINEL, bd=1, relief="solid")
    quadro.pack(fill="x", padx=28, pady=5)
    quadro.columnconfigure(0, weight=1)

    def campo(rotulo, row, mostrar=None, valor_inicial=""):
        tk.Label(
            quadro, text=rotulo, font=FONTE_9_NEGRITO,
            bg=COR_PAINEL, fg=COR_TEXTO
        ).grid(row=row, column=0, sticky="w", padx=16, pady=(9, 3))
        entrada = tk.Entry(quadro, font=FONTE_10, show=mostrar or "")
        entrada.grid(row=row + 1, column=0, sticky="ew", padx=16, pady=(0, 5), ipady=3)
        if valor_inicial:
            entrada.insert(0, valor_inicial)
        return entrada

    entrada_usuario_admin = campo("Nome de utilizador:", 0, valor_inicial="admin")
    entrada_senha_admin = campo("Crie uma senha (mínimo 10 caracteres):", 2, mostrar="*")
    entrada_confirmacao_admin = campo("Confirme a senha:", 4, mostrar="*")

    resultado = {"usuario": None}

    def criar_conta():
        utilizador = entrada_usuario_admin.get().strip()
        senha = entrada_senha_admin.get()
        confirmacao = entrada_confirmacao_admin.get()

        if not utilizador or any(ch.isspace() for ch in utilizador):
            messagebox.showerror(
                "Configuração inicial", "O nome de utilizador não pode estar vazio nem conter espaços.",
                parent=janela
            )
            entrada_usuario_admin.focus_set()
            return
        if len(senha) < 10:
            messagebox.showerror(
                "Configuração inicial", "Utilize uma senha com pelo menos 10 caracteres.",
                parent=janela
            )
            entrada_senha_admin.focus_set()
            return
        if senha != confirmacao:
            messagebox.showerror(
                "Configuração inicial", "As duas senhas não coincidem.", parent=janela
            )
            entrada_confirmacao_admin.delete(0, tk.END)
            entrada_confirmacao_admin.focus_set()
            return

        conexao = None
        try:
            conexao, cursor = conectar_banco()
            if conexao is None:
                raise sqlite3.OperationalError("Não foi possível conectar ao banco de dados.")
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT COUNT(*) FROM usuarios")
            if int(cursor.fetchone()[0]) != 0:
                raise RuntimeError("Já existe uma conta. Fecha esta janela e inicia sessão normalmente.")
            cursor.execute(
                """INSERT INTO usuarios (usuario, senha, perfil, ativo, tema)
                   VALUES (?, ?, 'Administrador', 1, 'Claro')""",
                (utilizador, criar_hash_senha(senha)),
            )
            _inserir_auditoria(
                cursor, "Primeiro administrador criado",
                detalhes="Conta inicial configurada localmente", usuario=utilizador
            )
            conexao.commit()
            resultado["usuario"] = utilizador
        except (sqlite3.Error, RuntimeError) as erro:
            if conexao:
                conexao.rollback()
            messagebox.showerror("Configuração inicial", str(erro), parent=janela)
            return
        finally:
            if conexao:
                conexao.close()

        janela.destroy()
        messagebox.showinfo(
            "Configuração concluída",
            "A conta de Administrador foi criada. Agora pode iniciar sessão com a sua nova senha.",
            parent=parent,
        )

    botoes = tk.Frame(janela, bg=COR_FUNDO)
    botoes.pack(fill="x", padx=28, pady=(10, 18))
    tk.Button(
        botoes, text="Criar Administrador", command=criar_conta,
        font=FONTE_9_NEGRITO, bg=COR_BOTAO, fg="white", relief="flat",
        cursor="hand2", padx=16, pady=7
    ).pack(side="left")

    def sair_sem_configurar():
        if messagebox.askyesno(
            "Sair do TB Software",
            "É necessário criar o primeiro Administrador para utilizar a aplicação. Deseja sair?",
            parent=janela,
        ):
            janela.destroy()
            parent.destroy()

    tk.Button(
        botoes, text="Sair", command=sair_sem_configurar,
        font=FONTE_9_NEGRITO, bg="#e8eef5", fg=COR_TEXTO, relief="flat",
        cursor="hand2", padx=18, pady=7
    ).pack(side="right")
    janela.protocol("WM_DELETE_WINDOW", sair_sem_configurar)
    entrada_usuario_admin.focus_set()
    janela.wait_window()
    return resultado["usuario"]


# ============================================================
#                    JANELA DE LOGIN
# ============================================================

# Preparar primeiro as tabelas base. Esta etapa não cria contas padrão nem senhas conhecidas.
inicializar_banco()
atualizar_tabela_clientes()
atualizar_tabela_usuarios()
atualizar_tabela_auditoria()
atualizar_tabelas_atendimento_lembretes()

garantir_campos_recuperacao()
_configuracoes_empresa = carregar_configuracoes_empresa()
NOME_EMPRESA = _configuracoes_empresa.get("nome_empresa", NOME_EMPRESA)
SLOGAN_EMPRESA = _configuracoes_empresa.get("slogan_empresa", SLOGAN_EMPRESA)

janela_login = tk.Tk()

aplicar_icone_janela(janela_login)
# Manter o login oculto enquanto os widgets são criados e posicionados; assim
# o Windows nunca mostra a geometria provisória pequena no canto do ecrã.
janela_login.withdraw()
registrar_tema_janela(janela_login)
janela_login.title("TB Software - Login")
janela_login.geometry("480x560")
janela_login.resizable(False, False)
janela_login.configure(bg=COR_FUNDO)

configurar_estilos()

# Marca
tk.Label(
    janela_login,
    text="TB Software",
    font=FONTE_27_NEGRITO,
    bg=COR_FUNDO,
    fg=COR_PRINCIPAL
).pack(pady=(48, 2))

tk.Label(
    janela_login,
    text=SLOGAN_EMPRESA,
    font=FONTE_10,
    bg=COR_FUNDO,
    fg=COR_SECUNDARIA
).pack(pady=(0, 22))

cartao_login = tk.Frame(
    janela_login,
    bg="white",
    bd=1,
    relief="solid"
)
cartao_login.pack(
    padx=58,
    fill="x"
)

tk.Label(
    cartao_login,
    text="Entrar no sistema",
    font=FONTE_14_NEGRITO,
    bg="white",
    fg=COR_TEXTO
).pack(
    pady=(22, 16)
)

tk.Label(
    cartao_login,
    text="Utilizador",
    font=FONTE_9_NEGRITO,
    bg="white",
    fg=COR_TEXTO
).pack(
    anchor="w",
    padx=28
)

entrada_usuario = tk.Entry(
    cartao_login,
    font=FONTE_10,
    relief="solid",
    bd=1
)
entrada_usuario.pack(
    padx=28,
    pady=(6, 15),
    ipady=4,
    fill="x"
)

tk.Label(
    cartao_login,
    text="Senha",
    font=FONTE_9_NEGRITO,
    bg="white",
    fg=COR_TEXTO
).pack(
    anchor="w",
    padx=28
)

entrada_senha = tk.Entry(
    cartao_login,
    font=FONTE_10,
    show="*",
    relief="solid",
    bd=1
)
entrada_senha.pack(
    padx=28,
    pady=(6, 10),
    ipady=4,
    fill="x"
)

# Recuperação de senha: disponível diretamente na tela de login.
tk.Button(
    cartao_login,
    text="Esqueci a senha",
    command=lambda: recuperar_senha(janela_login),
    font=FONTE_9,
    bg="white",
    fg=COR_PRINCIPAL,
    activebackground="white",
    activeforeground=COR_PRINCIPAL,
    relief="flat",
    cursor="hand2",
    bd=0
).pack(pady=(0, 14))

tk.Button(
    cartao_login,
    text="Entrar",
    font=FONTE_10_NEGRITO,
    bg=COR_BOTAO,
    fg="white",
    activebackground=COR_PRINCIPAL,
    activeforeground="white",
    relief="flat",
    cursor="hand2",
    command=verificar_login
).pack(
    padx=28,
    fill="x",
    ipady=7,
    pady=(0, 20)
)

tk.Label(
    janela_login,
    text="Sistema de Gestão de Clientes",
    font=FONTE_9,
    bg=COR_FUNDO,
    fg=COR_SECUNDARIA
).pack(
    pady=18
)

criar_rodape(janela_login)

janela_login.bind(
    "<Return>",
    lambda event: verificar_login()
)

entrada_usuario.focus_set()

# Posicionar e dimensionar o login antes de o mostrar. O login usa este
# cálculo próprio para preservar os 480x560 em ecrãs normais; só reduz a altura
# se a área útil do Windows for realmente menor, mantendo margem para a barra
# de título e a barra de tarefas.
def posicionar_login_inicial():
    largura_desejada = 480
    altura_desejada = 560
    esquerda, topo = 0, 0
    largura_area = int(janela_login.winfo_screenwidth())
    altura_area = int(janela_login.winfo_screenheight())

    try:
        rect = wintypes.RECT()
        ok = ctypes.windll.user32.SystemParametersInfoW(
            0x0030, 0, ctypes.byref(rect), 0  # SPI_GETWORKAREA
        )
        if ok:
            largura_calculada = int(rect.right - rect.left)
            altura_calculada = int(rect.bottom - rect.top)
            if largura_calculada >= 320 and altura_calculada >= 300:
                esquerda, topo = int(rect.left), int(rect.top)
                largura_area = largura_calculada
                altura_area = altura_calculada
    except (AttributeError, OSError, TypeError, ValueError):
        pass

    # Não subtrair decorações duas vezes: geometry recebe as dimensões da
    # janela Tk, e a reserva abaixo é apenas uma margem de segurança exterior.
    largura_final = min(largura_desejada, max(320, largura_area - 20))
    altura_final = min(altura_desejada, max(280, altura_area - 56))
    x = esquerda + max(8, (largura_area - largura_final) // 2)
    y = topo + max(8, (altura_area - altura_final) // 2)

    janela_login.geometry(
        f"{largura_final}x{altura_final}+{x}+{y}"
    )
    janela_login.update_idletasks()
    janela_login.deiconify()
    janela_login.lift()
    entrada_usuario.focus_set()

# Na primeira execução, configurar uma conta de Administrador sem usar uma senha padrão.
def iniciar_login_com_seguranca():
    # Mostrar e posicionar a raiz primeiro; assim o diálogo modal não fica associado
    # a uma janela principal oculta em certos gestores de janelas do Windows.
    posicionar_login_inicial()
    if not existe_algum_utilizador():
        janela_login.after(150, lambda: configurar_primeiro_administrador(janela_login))

# Garantir que a base está inicializada e só pedir configuração quando não há utilizadores.
janela_login.after_idle(iniciar_login_com_seguranca)

janela_login.mainloop()
