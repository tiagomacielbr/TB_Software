import sqlite3

from banco import conectar_banco
from banco import confirmar_operacao

# ==================================================
#                CADASTRAR CLIENTE
# ==================================================
def cadastrar_clientes():

    print("\n===== NOVO CLIENTE =====")

    if not confirmar_operacao(
        "Deseja cadastrar um novo cliente?"
    ):

        return

    # ==================================================
    #                    NOME
    # ==================================================

    nome = pedir_novo_nome()

    if nome is None:
        return

    # ==================================================
    #                     NIF
    # ==================================================

    while True:

        nif = pedir_nif()

        if nif is None:
            return

        if nif_disponivel(nif):

            break

        print("\nNIF já cadastrado!")

        if not confirmar_operacao(
            "Deseja tentar outro NIF?"
        ):

            return

    # ==================================================
    #                  ENDEREÇO
    # ==================================================

    endereco = pedir_endereco()

    if endereco is None:
        return

    # ==================================================
    #                  TELEFONE
    # ==================================================

    while True:

        telefone = pedir_telefone()

        if telefone is None:
            return

        if telefone_disponivel(telefone):

            break

        print("\nTelefone já cadastrado!")

        if not confirmar_operacao(
            "Deseja tentar outro telefone?"
        ):

            return

    # ==================================================
    #                   CIDADE
    # ==================================================

    cidade = pedir_cidade()

    if cidade is None:
        return

    # ==================================================
    #             MOSTRAR DADOS
    # ==================================================

    print("\n===== CONFIRMAR CADASTRO =====")

    print(f"Nome:      {nome}")
    print(f"NIF:       {nif}")
    print(f"Endereço:  {endereco}")
    print(f"Telefone:  {telefone}")
    print(f"Cidade:    {cidade}")

    if not confirmar_operacao(
        "\nDeseja cadastrar este cliente?"
    ):

        print("\nCadastro cancelado.")

        return

    # ==================================================
    #                  GRAVAR BANCO
    # ==================================================

    conexao, cursor = conectar_banco()

    if conexao is None:
        return

    try:

        cursor.execute("""
            INSERT INTO clientes
            (nome, nif, endereco, telefone, cidade)
            VALUES (?, ?, ?, ?, ?)
        """, (
            nome,
            nif,
            endereco,
            telefone,
            cidade
        ))

        conexao.commit()

        print("\nCliente cadastrado com sucesso!")

    except sqlite3.IntegrityError:

        print(
            "\nErro: NIF ou telefone já cadastrado!"
        )

        conexao.rollback()

    except sqlite3.Error as erro:

        print(
            f"\nErro ao cadastrar cliente: {erro}"
        )

        conexao.rollback()

    finally:

        conexao.close()


# ==================================================
#                    LISTAR CLIENTES
# ==================================================
def listar_clientes():

    if not confirmar_operacao(
        "Deseja continuar?"
    ):

        return

    conexao, cursor = conectar_banco()

    if conexao is None:
        return

    try:

        cursor.execute("""
            SELECT *
            FROM clientes
            ORDER BY id
        """)

        clientes = cursor.fetchall()

    except sqlite3.Error as erro:

        print(
            f"Erro ao listar clientes: {erro}"
        )

        return

    finally:

        conexao.close()

    if len(clientes) == 0:

        print("\nNenhum cliente cadastrado!")

        return

    print("\n===== CLIENTES CADASTRADOS =====")

    for numero, cliente in enumerate(
        clientes,
        start=1
    ):

        print("\n--------------------------")

        print(f"Nº do cadastro: {numero}")
        print(f"ID:             {cliente[0]}")
        print(f"Nome:           {cliente[1]}")
        print(f"NIF:            {cliente[2]}")
        print(f"Endereço:       {cliente[3]}")
        print(f"Telefone:       {cliente[4]}")
        print(f"Cidade:         {cliente[5]}")


# ==================================================
#                PROCURAR CLIENTES
# ==================================================
def procurar_clientes():

    if not confirmar_operacao(
        "Deseja continuar?"
    ):

        return

    conexao, cursor = conectar_banco()

    if conexao is None:
        return

    try:

        while True:

            print("\n===== PROCURAR CLIENTE =====")

            print("1 - Procurar por nome")
            print("2 - Procurar por NIF")
            print("3 - Procurar por telefone")
            print("4 - Procurar por cidade")
            print("0 - Voltar")

            opcao = input(
                "Digite uma opção: "
            ).strip()

            if opcao == "1":

                procurar_por_nome(cursor)

            elif opcao == "2":

                procurar_por_nif(cursor)

            elif opcao == "3":

                procurar_por_telefone(cursor)

            elif opcao == "4":

                procurar_por_cidade(cursor)

            elif opcao == "0":

                return

            else:

                print("\nOpção inválida!")

    finally:

        conexao.close()


# ==================================================
#                  EXCLUIR CLIENTE
# ==================================================
def excluir_clientes():

    print("\n===== EXCLUIR CLIENTE =====")

    if not confirmar_operacao(
        "Deseja excluir um cliente?"
    ):

        return

    nif = pedir_nif()

    if nif is None:
        return

    conexao, cursor = conectar_banco()

    if conexao is None:
        return

    try:

        cursor.execute("""
            SELECT *
            FROM clientes
            WHERE nif = ?
        """, (nif,))

        cliente = cursor.fetchone()

        if cliente is None:

            print("\nCliente não encontrado!")

            return

        print("\n===== CLIENTE ENCONTRADO =====")

        mostrar_cliente(cliente)

        if not confirmar_operacao(
            "\nDeseja realmente excluir este cliente?"
        ):

            print("\nCliente não excluído.")

            return

        cursor.execute("""
            DELETE FROM clientes
            WHERE id = ?
        """, (cliente[0],))

        conexao.commit()

        print(
            "\nCliente excluído com sucesso!"
        )

    except sqlite3.Error as erro:

        print(
            f"\nErro ao excluir cliente: {erro}"
        )

        conexao.rollback()

    finally:

        conexao.close()


# ==================================================
#                  ALTERAR CLIENTE
# ==================================================
def alterar_clientes():

    print("\n===== ALTERAR CLIENTE =====")

    if not confirmar_operacao(
        "Deseja alterar um cliente?"
    ):

        return

    nif = pedir_nif()

    if nif is None:
        return

    conexao, cursor = conectar_banco()

    if conexao is None:
        return

    try:

        cursor.execute("""
            SELECT *
            FROM clientes
            WHERE nif = ?
        """, (nif,))

        cliente = cursor.fetchone()

        if cliente is None:

            print("\nCliente não encontrado!")

            return

        id_cliente = cliente[0]

        print("\n===== CLIENTE ENCONTRADO =====")

        mostrar_cliente(cliente)

        while True:

            print("\n===== O QUE DESEJA ALTERAR? =====")

            print("1 - Nome")
            print("2 - NIF")
            print("3 - Endereço")
            print("4 - Telefone")
            print("5 - Cidade")
            print("0 - Voltar")

            opcao = input(
                "Digite uma opção: "
            ).strip()

            if opcao == "1":

                novo_nome = pedir_novo_nome()

                if novo_nome is None:
                    continue

                print(
                    f"\nNovo nome: {novo_nome}"
                )

                if not confirmar_operacao(
                    "Confirmar alteração do nome?"
                ):

                    print("\nAlteração cancelada.")

                    continue

                cursor.execute("""
                    UPDATE clientes
                    SET nome = ?
                    WHERE id = ?
                """, (
                    novo_nome,
                    id_cliente
                ))

                conexao.commit()

                print(
                    "\nNome alterado com sucesso!"
                )

                mostrar_cliente_atualizado(
                    cursor,
                    id_cliente
                )

            elif opcao == "2":

                novo_nif = pedir_nif()

                if novo_nif is None:
                    continue

                if not nif_disponivel_para_alteracao(
                    novo_nif,
                    id_cliente
                ):

                    print(
                        "\nEsse NIF já está cadastrado "
                        "para outro cliente!"
                    )

                    continue

                print(
                    f"\nNovo NIF: {novo_nif}"
                )

                if not confirmar_operacao(
                    "Confirmar alteração do NIF?"
                ):

                    print("\nAlteração cancelada.")

                    continue

                cursor.execute("""
                    UPDATE clientes
                    SET nif = ?
                    WHERE id = ?
                """, (
                    novo_nif,
                    id_cliente
                ))

                conexao.commit()

                print(
                    "\nNIF alterado com sucesso!"
                )

                mostrar_cliente_atualizado(
                    cursor,
                    id_cliente
                )

            elif opcao == "3":

                novo_endereco = pedir_endereco()

                if novo_endereco is None:
                    continue

                print(
                    f"\nNovo endereço: {novo_endereco}"
                )

                if not confirmar_operacao(
                    "Confirmar alteração do endereço?"
                ):

                    print("\nAlteração cancelada.")

                    continue

                cursor.execute("""
                    UPDATE clientes
                    SET endereco = ?
                    WHERE id = ?
                """, (
                    novo_endereco,
                    id_cliente
                ))

                conexao.commit()

                print(
                    "\nEndereço alterado com sucesso!"
                )

                mostrar_cliente_atualizado(
                    cursor,
                    id_cliente
                )

            elif opcao == "4":

                while True:

                    novo_telefone = pedir_telefone()

                    if novo_telefone is None:
                        break

                    if telefone_disponivel_para_alteracao(
                        novo_telefone,
                        id_cliente
                    ):

                        break

                    print(
                        "\nEsse telefone já está cadastrado "
                        "para outro cliente!"
                    )

                    if not confirmar_operacao(
                        "Deseja tentar novamente?"
                    ):

                        novo_telefone = None

                        break

                if novo_telefone is None:
                    continue

                print(
                    f"\nNovo telefone: {novo_telefone}"
                )

                if not confirmar_operacao(
                    "Confirmar alteração do telefone?"
                ):

                    print("\nAlteração cancelada.")

                    continue

                cursor.execute("""
                    UPDATE clientes
                    SET telefone = ?
                    WHERE id = ?
                """, (
                    novo_telefone,
                    id_cliente
                ))

                conexao.commit()

                print(
                    "\nTelefone alterado com sucesso!"
                )

                mostrar_cliente_atualizado(
                    cursor,
                    id_cliente
                )

            elif opcao == "5":

                nova_cidade = pedir_cidade()

                if nova_cidade is None:
                    continue

                print(
                    f"\nNova cidade: {nova_cidade}"
                )

                if not confirmar_operacao(
                    "Confirmar alteração da cidade?"
                ):

                    print("\nAlteração cancelada.")

                    continue

                cursor.execute("""
                    UPDATE clientes
                    SET cidade = ?
                    WHERE id = ?
                """, (
                    nova_cidade,
                    id_cliente
                ))

                conexao.commit()

                print(
                    "\nCidade alterada com sucesso!"
                )

                mostrar_cliente_atualizado(
                    cursor,
                    id_cliente
                )

            elif opcao == "0":

                return

            else:

                print("\nOpção inválida!")

    except sqlite3.Error as erro:

        print(
            f"\nErro ao alterar cliente: {erro}"
        )

        conexao.rollback()

    finally:

        conexao.close()


# ==================================================
#                  PEDIR NOVO NOME
# ==================================================
def pedir_novo_nome():

    while True:

        nome = input(
            "Digite novo nome do cliente: "
        ).strip()

        if nome.replace(" ", "").isalpha():

            return nome.title()

        print(
            "Nome inválido! Digite somente letras."
        )

        if not confirmar_operacao(
            "Deseja tentar novamente?"
        ):

            return None


# ==================================================
#                  PEDIR NIF
# ==================================================
def pedir_nif():

    while True:

        nif = input(
            "Digite o NIF do cliente: "
        ).strip()

        nif = nif.replace(" ", "")
        nif = nif.replace(".", "")
        nif = nif.replace("-", "")

        if nif.isdigit() and len(nif) == 9:

            if nif_valido(nif):

                return nif

            print("\nNIF inválido!")

        else:

            print(
                "\nNIF inválido! "
                "Digite exatamente 9 números."
            )

        if not confirmar_operacao(
            "Deseja tentar novamente?"
        ):

            return None


# ==================================================
#                 PEDIR ENDEREÇO
# ==================================================
def pedir_endereco():

    while True:

        endereco = input(
            "Digite o endereço: "
        ).strip()

        if endereco:

            return endereco.title()

        print(
            "Endereço não pode ficar vazio!"
        )

        if not confirmar_operacao(
            "Deseja tentar novamente?"
        ):

            return None


# ==================================================
#                 PEDIR TELEFONE
# ==================================================
def pedir_telefone():

    while True:

        telefone = input(
            "Digite o telefone do cliente: "
        ).strip()

        telefone = telefone.replace(" ", "")
        telefone = telefone.replace("-", "")
        telefone = telefone.replace("(", "")
        telefone = telefone.replace(")", "")

        if telefone.isdigit():

            if len(telefone) < 9:

                print(
                    "Telefone inválido! "
                    "Digite pelo menos 9 números."
                )

            else:

                return telefone

        else:

            print(
                "Telefone inválido! "
                "Digite somente números."
            )

        if not confirmar_operacao(
            "Deseja tentar novamente?"
        ):

            return None


# ==================================================
#                  PEDIR CIDADE
# ==================================================
def pedir_cidade():

    while True:

        cidade = input(
            "Digite a cidade: "
        ).strip()

        if cidade.replace(" ", "").isalpha():

            return cidade.title()

        print(
            "Cidade inválida! "
            "Digite somente letras."
        )

        if not confirmar_operacao(
            "Deseja tentar novamente?"
        ):

            return None


# ==================================================
#            VERIFICAR TELEFONE DISPONÍVEL
# ==================================================
def telefone_disponivel(telefone):

    conexao, cursor = conectar_banco()

    if conexao is None:
        return False

    try:

        cursor.execute("""
            SELECT id
            FROM clientes
            WHERE telefone = ?
        """, (telefone,))

        cliente = cursor.fetchone()

        return cliente is None

    except sqlite3.Error as erro:

        print(
            f"Erro ao verificar telefone: {erro}"
        )

        return False

    finally:

        conexao.close()


# ==================================================
#       TELEFONE DISPONÍVEL PARA ALTERAÇÃO
# ==================================================
def telefone_disponivel_para_alteracao(
    telefone,
    id_cliente
):

    conexao, cursor = conectar_banco()

    if conexao is None:
        return False

    try:

        cursor.execute("""
            SELECT id
            FROM clientes
            WHERE telefone = ?
            AND id != ?
        """, (
            telefone,
            id_cliente
        ))

        cliente = cursor.fetchone()

        return cliente is None

    except sqlite3.Error as erro:

        print(
            f"Erro ao verificar telefone: {erro}"
        )

        return False

    finally:

        conexao.close()


# ==================================================
#              PROCURAR POR NOME
# ==================================================
def procurar_por_nome(cursor):

    print("\n--- PESQUISA POR NOME ---")

    nome = input(
        "Digite nome do cliente: "
    ).strip()

    if not nome:
        return

    try:

        cursor.execute("""
            SELECT *
            FROM clientes
            WHERE nome LIKE ?
            ORDER BY nome
        """, (
            f"%{nome}%",
        ))

        clientes = cursor.fetchall()

        mostrar_clientes(clientes)

    except sqlite3.Error as erro:

        print(
            f"Erro na pesquisa: {erro}"
        )


# ==================================================
#                PROCURAR POR NIF
# ==================================================
def procurar_por_nif(cursor):

    print("\n--- PESQUISA POR NIF ---")

    nif = pedir_nif()

    if nif is None:
        return

    try:

        cursor.execute("""
            SELECT *
            FROM clientes
            WHERE nif = ?
        """, (nif,))

        clientes = cursor.fetchall()

        mostrar_clientes(clientes)

    except sqlite3.Error as erro:

        print(
            f"Erro na pesquisa: {erro}"
        )


# ==================================================
#            PROCURAR POR TELEFONE
# ==================================================
def procurar_por_telefone(cursor):

    print(
        "\n--- PESQUISA POR TELEFONE ---"
    )

    telefone = pedir_telefone()

    if telefone is None:
        return

    try:

        cursor.execute("""
            SELECT *
            FROM clientes
            WHERE telefone = ?
        """, (telefone,))

        clientes = cursor.fetchall()

        mostrar_clientes(clientes)

    except sqlite3.Error as erro:

        print(
            f"Erro na pesquisa: {erro}"
        )


# ==================================================
#              PROCURAR POR CIDADE
# ==================================================
def procurar_por_cidade(cursor):

    print(
        "\n--- PESQUISA POR CIDADE ---"
    )

    cidade = input(
        "Digite a cidade: "
    ).strip()

    if not cidade:
        return

    try:

        cursor.execute("""
            SELECT *
            FROM clientes
            WHERE cidade LIKE ?
            ORDER BY nome
        """, (
            f"%{cidade}%",
        ))

        clientes = cursor.fetchall()

        mostrar_clientes(clientes)

    except sqlite3.Error as erro:

        print(
            f"Erro na pesquisa: {erro}"
        )


# ==================================================
#                 MOSTRAR CLIENTE
# ==================================================
def mostrar_cliente(cliente):

    print("--------------------------")

    print(f"ID:        {cliente[0]}")
    print(f"Nome:      {cliente[1]}")
    print(f"NIF:       {cliente[2]}")
    print(f"Endereço:  {cliente[3]}")
    print(f"Telefone:  {cliente[4]}")
    print(f"Cidade:    {cliente[5]}")


# ==================================================
#                 MOSTRAR CLIENTES
# ==================================================
def mostrar_clientes(clientes):

    if len(clientes) == 0:

        print(
            "\nNenhum cliente encontrado!"
        )

        return

    print(
        "\n===== RESULTADO DA PESQUISA ====="
    )

    for cliente in clientes:

        mostrar_cliente(cliente)

    print("\n--------------------------")

    print(
        f"Total de clientes encontrados: "
        f"{len(clientes)}"
    )


# ==================================================
#          MOSTRAR CLIENTE ATUALIZADO
# ==================================================
def mostrar_cliente_atualizado(
    cursor,
    id_cliente
):

    try:

        cursor.execute("""
            SELECT *
            FROM clientes
            WHERE id = ?
        """, (id_cliente,))

        cliente = cursor.fetchone()

        if cliente is not None:

            print(
                "\n===== DADOS ATUALIZADOS ====="
            )

            mostrar_cliente(cliente)

    except sqlite3.Error as erro:

        print(
            f"Erro ao mostrar cliente: {erro}"
        )


# ==================================================
#       NIF DISPONÍVEL PARA ALTERAÇÃO
# ==================================================
def nif_disponivel_para_alteracao(
    nif,
    id_cliente
):

    conexao, cursor = conectar_banco()

    if conexao is None:
        return False

    try:

        cursor.execute("""
            SELECT id
            FROM clientes
            WHERE nif = ?
            AND id != ?
        """, (
            nif,
            id_cliente
        ))

        cliente = cursor.fetchone()

        return cliente is None

    except sqlite3.Error as erro:

        print(
            f"Erro ao verificar NIF: {erro}"
        )

        return False

    finally:

        conexao.close()


# ==================================================
#              VERIFICAR NIF DISPONÍVEL
# ==================================================
def nif_disponivel(nif):

    conexao, cursor = conectar_banco()

    if conexao is None:
        return False

    try:

        cursor.execute("""
            SELECT id
            FROM clientes
            WHERE nif = ?
        """, (nif,))

        cliente = cursor.fetchone()

        return cliente is None

    except sqlite3.Error as erro:

        print(
            f"Erro ao verificar NIF: {erro}"
        )

        return False

    finally:

        conexao.close()


# ==================================================
#                  VALIDAR NIF
# ==================================================
def nif_valido(nif):

    if not nif.isdigit() or len(nif) != 9:

        return False

    if nif[0] == "0":

        return False

    soma = 0

    for i in range(8):

        soma += int(nif[i]) * (9 - i)

    resto = soma % 11

    if resto < 2:

        digito_controle = 0

    else:

        digito_controle = 11 - resto

    if int(nif[8]) != digito_controle:

        return False

    return True