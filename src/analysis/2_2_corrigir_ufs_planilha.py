"""
HIGIENIZAÇÃO DE DADOS DE EMPRESAS

Objetivos:
1. Carregar o relatório gerado pela etapa anterior.
2. Padronizar UF e CEP.
3. Validar a UF existente usando o CEP.
4. Corrigir UFs incompatíveis com o CEP.
5. Inferir UF pelo endereço quando o CEP não estiver disponível.
6. Recuperar CEPs ausentes usando o ViaCEP.
7. Utilizar cache para evitar consultas repetidas.
8. Gerar relatório detalhado do processamento.

Entrada:
    outputs/relatorios/relatorio_empresas.xlsx

Saída:
    outputs/relatorios/relatorio_empresas_higienizado_completo.xlsx
"""

import os
import re
import time
import unicodedata
import pandas as pd
import requests


# ==============================================================================
# 1. CONFIGURAÇÃO
# ==============================================================================

DIRETORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = os.path.abspath(
    os.path.join(DIRETORIO_SCRIPT, "..", "..")
)

ARQUIVO_ENTRADA = os.path.join(
    BASE_DIR,
    "outputs",
    "relatorios",
    "relatorio_empresas.xlsx"
)

ARQUIVO_SAIDA = os.path.join(
    BASE_DIR,
    "outputs",
    "relatorios",
    "relatorio_empresas_higienizado_completo.xlsx"
)

TEMPO_INICIO = time.time()

LISTA_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES",
    "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
    "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO"
]


# ==============================================================================
# 2. VERIFICAÇÃO E CARREGAMENTO
# ==============================================================================

print("=" * 70)
print("HIGIENIZAÇÃO DA BASE DE EMPRESAS")
print("=" * 70)

print("\n[1/5] CARREGAMENTO")

if not os.path.exists(ARQUIVO_ENTRADA):
    raise FileNotFoundError(
        f"\nArquivo não encontrado:\n{ARQUIVO_ENTRADA}"
    )

df = pd.read_excel(ARQUIVO_ENTRADA)

print(f"  Registros : {len(df):,}".replace(",", "."))
print(f"  Colunas   : {len(df.columns)}")


# ==============================================================================
# 3. PADRONIZAÇÃO
# ==============================================================================

print("\n[2/5] PADRONIZAÇÃO")

if "uf" not in df.columns:
    df["uf"] = ""

if "cep" not in df.columns:
    df["cep"] = ""

df["uf"] = (
    df["uf"]
    .fillna("")
    .astype(str)
    .str.strip()
    .str.upper()
)

df["cep"] = (
    df["cep"]
    .fillna("")
    .astype(str)
    .str.strip()
    .str.replace(r"\.0$", "", regex=True)
)

# Mantém somente os números do CEP
df["cep"] = df["cep"].apply(
    lambda x: re.sub(r"\D", "", str(x))
)


# ==============================================================================
# 4. FUNÇÕES
# ==============================================================================

def normalizar_texto(texto):
    """Remove acentos e caracteres especiais."""

    if pd.isna(texto):
        return ""

    texto = (
        unicodedata
        .normalize("NFKD", str(texto))
        .encode("ASCII", "ignore")
        .decode("ASCII")
    )

    texto = re.sub(r"[^A-Za-z0-9\s]", " ", texto)

    return re.sub(r"\s+", " ", texto).strip()


def deduzir_uf_por_cep(cep):
    """
    Deduz a UF utilizando o início do CEP.

    Retorna:
        UF válida ou string vazia.
    """

    cep = re.sub(r"\D", "", str(cep))

    if len(cep) != 8:
        return ""

    prefixo = int(cep[:2])

    if 1 <= prefixo <= 19:
        return "SP"

    if 20 <= prefixo <= 28:
        return "RJ"

    if prefixo == 29:
        return "ES"

    if 30 <= prefixo <= 39:
        return "MG"

    if 40 <= prefixo <= 48:
        return "BA"

    if prefixo == 49:
        return "SE"

    if 50 <= prefixo <= 56:
        return "PE"

    if prefixo == 57:
        return "AL"

    if prefixo == 58:
        return "PB"

    if prefixo == 59:
        return "RN"

    if 60 <= prefixo <= 63:
        return "CE"

    if prefixo == 64:
        return "PI"

    if prefixo == 65:
        return "MA"

    if 66 <= prefixo <= 68:
        return "PA"

    if prefixo == 69:
        prefixo3 = int(cep[:3])

        if 690 <= prefixo3 <= 692:
            return "AM"

        if prefixo3 == 693:
            return "RR"

        if prefixo3 == 694:
            return "AM"

        if prefixo3 == 695:
            return "AM"

        if prefixo3 == 696:
            return "AM"

        if prefixo3 == 697:
            return "AM"

        if prefixo3 == 698:
            return "AC"

        if prefixo3 == 699:
            return "AC"

        return ""

    if 70 <= prefixo <= 72:
        return "DF"

    if 73 <= prefixo <= 76:
        return "GO"

    if prefixo == 77:
        return "TO"

    if prefixo == 78:
        prefixo3 = int(cep[:3])

        if 780 <= prefixo3 <= 788:
            return "MT"

        if 789 <= prefixo3 <= 789:
            return "RO"

        return ""

    if prefixo == 79:
        return "MS"

    if 80 <= prefixo <= 87:
        return "PR"

    if 88 <= prefixo <= 89:
        return "SC"

    if 90 <= prefixo <= 99:
        return "RS"

    return ""


def deduzir_uf_por_endereco(endereco):
    """Tenta identificar uma UF no endereço."""

    if pd.isna(endereco):
        return ""

    endereco = str(endereco).upper()

    padrao = (
        r"(?:^|[\s,/-])"
        r"(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|"
        r"PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)"
        r"(?:[\s,/,.-]|$)"
    )

    encontrados = re.findall(padrao, endereco)

    return encontrados[-1] if encontrados else ""


def extrair_nome_rua(endereco):
    """Extrai o provável nome da rua."""

    if pd.isna(endereco):
        return ""

    endereco = normalizar_texto(endereco)

    if not endereco:
        return ""

    # Parte anterior ao número
    partes = re.split(r",|\s+\d+\b", endereco)

    rua = partes[0].strip()

    rua = re.sub(
        r"^(RUA|R|AV|AVENIDA|ALAMEDA|RODOVIA|ROD|"
        r"TRAVESSA|ESTRADA|PRACA|PRACA)\s+",
        "",
        rua,
        flags=re.IGNORECASE
    )

    return rua.strip()


# ==============================================================================
# 5. CORREÇÃO DAS UFs
# ==============================================================================

print("\n[3/5] VALIDAÇÃO E CORREÇÃO DAS UFs")

uf_corrigidas_cep = 0
uf_preenchidas_cep = 0
uf_preenchidas_endereco = 0
uf_sem_informacao = 0

for idx in df.index:

    uf_atual = str(df.at[idx, "uf"]).strip().upper()
    cep = str(df.at[idx, "cep"]).strip()

    # --------------------------------------------------------------------------
    # 1. CEP é a principal fonte para determinar UF
    # --------------------------------------------------------------------------

    uf_cep = deduzir_uf_por_cep(cep)

    if uf_cep:

        # UF vazia
        if uf_atual not in LISTA_UFS:

            df.at[idx, "uf"] = uf_cep
            uf_preenchidas_cep += 1

        # UF existente, mas diferente do CEP
        elif uf_atual != uf_cep:

            df.at[idx, "uf"] = uf_cep
            uf_corrigidas_cep += 1

        continue

    # --------------------------------------------------------------------------
    # 2. Se não existe CEP válido, tenta o endereço
    # --------------------------------------------------------------------------

    endereco = ""

    if "endereco_completo" in df.columns:
        endereco = df.at[idx, "endereco_completo"]

    uf_endereco = deduzir_uf_por_endereco(endereco)

    if uf_endereco and uf_atual not in LISTA_UFS:

        df.at[idx, "uf"] = uf_endereco
        uf_preenchidas_endereco += 1

    elif uf_atual not in LISTA_UFS:

        uf_sem_informacao += 1


print(
    f"  UFs corrigidas pelo CEP       : "
    f"{uf_corrigidas_cep:,}".replace(",", ".")
)

print(
    f"  UFs preenchidas pelo CEP      : "
    f"{uf_preenchidas_cep:,}".replace(",", ".")
)

print(
    f"  UFs preenchidas pelo endereço : "
    f"{uf_preenchidas_endereco:,}".replace(",", ".")
)

print(
    f"  Ainda sem UF                  : "
    f"{uf_sem_informacao:,}".replace(",", ".")
)


# ==============================================================================
# 6. RECUPERAÇÃO DE CEP
# ==============================================================================

print("\n[4/5] RECUPERAÇÃO DOS CEPs")

mascara_sem_cep = df["cep"].apply(
    lambda x: len(re.sub(r"\D", "", str(x))) != 8
)

indices_sem_cep = df.index[mascara_sem_cep]

total_sem_cep = len(indices_sem_cep)

print(
    f"  Registros sem CEP: "
    f"{total_sem_cep:,}".replace(",", ".")
)

ceps_recuperados_rua = 0
ceps_recuperados_bairro = 0
tentativas = 0

# Cache:
# (UF, cidade, termo) -> CEP
CACHE_VIACEP = {}


def consultar_viacep(uf, cidade, termo):
    """Consulta ViaCEP com cache."""

    uf = str(uf).strip().upper()
    cidade = normalizar_texto(cidade)
    termo = normalizar_texto(termo)

    if len(uf) != 2:
        return ""

    if len(cidade) < 3 or len(termo) < 3:
        return ""

    if termo.upper() in {
        "CENTRO",
        "ZONA RURAL",
        "SEDE"
    }:
        return ""

    chave = (uf, cidade.upper(), termo.upper())

    # Evita repetir consultas iguais
    if chave in CACHE_VIACEP:
        return CACHE_VIACEP[chave]

    url = (
        f"https://viacep.com.br/ws/"
        f"{uf}/{cidade}/{termo}/json/"
    )

    try:

        resposta = requests.get(
            url,
            timeout=5
        )

        if resposta.status_code == 200:

            dados = resposta.json()

            if isinstance(dados, list) and dados:

                cep = str(
                    dados[0].get("cep", "")
                ).replace("-", "")

                if len(cep) == 8:

                    CACHE_VIACEP[chave] = cep

                    return cep

    except requests.RequestException:
        pass

    CACHE_VIACEP[chave] = ""

    return ""


for contador, idx in enumerate(indices_sem_cep, start=1):

    uf = df.at[idx, "uf"]

    if uf not in LISTA_UFS:
        continue

    cidade = (
        df.at[idx, "cidade"]
        if "cidade" in df.columns
        else ""
    )

    endereco = (
        df.at[idx, "endereco_completo"]
        if "endereco_completo" in df.columns
        else ""
    )

    bairro = (
        df.at[idx, "bairro"]
        if "bairro" in df.columns
        else ""
    )

    cep_encontrado = ""

    # --------------------------------------------------------------------------
    # PRIMEIRA TENTATIVA: RUA
    # --------------------------------------------------------------------------

    rua = extrair_nome_rua(endereco)

    if rua:

        antes = len(CACHE_VIACEP)

        cep_encontrado = consultar_viacep(
            uf,
            cidade,
            rua
        )

        depois = len(CACHE_VIACEP)

        if depois > antes:
            tentativas += 1

            # Pequeno intervalo somente quando houve consulta real
            time.sleep(0.20)

        if cep_encontrado:
            ceps_recuperados_rua += 1

    # --------------------------------------------------------------------------
    # SEGUNDA TENTATIVA: BAIRRO
    # --------------------------------------------------------------------------

    if not cep_encontrado and pd.notna(bairro):

        bairro = str(bairro).strip()

        if bairro:

            antes = len(CACHE_VIACEP)

            cep_encontrado = consultar_viacep(
                uf,
                cidade,
                bairro
            )

            depois = len(CACHE_VIACEP)

            if depois > antes:
                tentativas += 1
                time.sleep(0.20)

            if cep_encontrado:
                ceps_recuperados_bairro += 1

    if cep_encontrado:

        df.at[idx, "cep"] = cep_encontrado

    # --------------------------------------------------------------------------
    # PROGRESSO
    # --------------------------------------------------------------------------

    if contador % 100 == 0 or contador == total_sem_cep:

        recuperados = (
            ceps_recuperados_rua
            + ceps_recuperados_bairro
        )

        percentual = (
            contador / total_sem_cep * 100
            if total_sem_cep
            else 100
        )

        print(
            f"  Progresso: {contador:,}/{total_sem_cep:,} "
            f"({percentual:.1f}%) | "
            f"Recuperados: {recuperados:,} | "
            f"Consultas novas: {tentativas:,}"
        )


# ==============================================================================
# 7. SALVAMENTO
# ==============================================================================

print("\n[5/5] SALVAMENTO")

os.makedirs(
    os.path.dirname(ARQUIVO_SAIDA),
    exist_ok=True
)

df.to_excel(
    ARQUIVO_SAIDA,
    index=False
)


# ==============================================================================
# 8. RELATÓRIO FINAL
# ==============================================================================

tempo_total = time.time() - TEMPO_INICIO

ceps_recuperados = (
    ceps_recuperados_rua
    + ceps_recuperados_bairro
)

ceps_restantes = total_sem_cep - ceps_recuperados

print("\n" + "=" * 70)
print("RELATÓRIO FINAL")
print("=" * 70)

print(
    f"Empresas processadas       : "
    f"{len(df):,}".replace(",", ".")
)

print(
    f"UFs corrigidas pelo CEP    : "
    f"{uf_corrigidas_cep:,}".replace(",", ".")
)

print(
    f"UFs preenchidas pelo CEP   : "
    f"{uf_preenchidas_cep:,}".replace(",", ".")
)

print(
    f"UFs preenchidas pelo endereço: "
    f"{uf_preenchidas_endereco:,}".replace(",", ".")
)

print(
    f"CEPs recuperados pela rua  : "
    f"{ceps_recuperados_rua:,}".replace(",", ".")
)

print(
    f"CEPs recuperados pelo bairro: "
    f"{ceps_recuperados_bairro:,}".replace(",", ".")
)

print(
    f"CEPs recuperados no total  : "
    f"{ceps_recuperados:,}".replace(",", ".")
)

print(
    f"CEPs ainda ausentes        : "
    f"{ceps_restantes:,}".replace(",", ".")
)

print(
    f"Consultas novas ao ViaCEP  : "
    f"{tentativas:,}".replace(",", ".")
)

print(
    f"Consultas em cache         : "
    f"{max(0, (total_sem_cep * 2) - tentativas):,}".replace(",", ".")
)

print(f"Tempo total                : {tempo_total:.2f} s")

print(f"\nArquivo gerado:")
print(ARQUIVO_SAIDA)

print("=" * 70)
