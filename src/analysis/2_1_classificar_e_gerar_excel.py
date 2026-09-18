"""
Seleção e classificação de empresas por CNAE.

O programa:
1. Lê a base consolidada em Parquet.
2. Seleciona somente os CNAEs definidos em CNAES_ALVO.
3. Classifica as empresas em categorias gerais de mercado.
4. Exporta os resultados para Excel.

Para alterar o universo da pesquisa:
    basta modificar a lista CNAES_ALVO.

Entrada:
    data/processed/base_engenharia_fisica.parquet

Saída:
    outputs/relatorios/relatorio_empresas.xlsx
"""
from pathlib import Path
import time
import duckdb

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================
inicio = time.time()

# Caminhos do projeto
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ARQUIVO_PARQUET = BASE_DIR / "data" / "processed" / "base_engenharia_fisica.parquet"
ARQUIVO_SAIDA = BASE_DIR / "outputs" / "relatorios" / "relatorio_empresas.xlsx"

# ============================================================================
# CONFIGURAÇÃO: altere somente esta lista para mudar os CNAEs analisados
# ============================================================================
CNAES_ALVO = [
    "7210000",
    "2660400",
    "2610800",
    "2731700",
]

# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================
def normalizar_cnae(cnae):
    if cnae is None:
        return ""
    return str(cnae).strip().replace(".", "")

def classificar_setor(cnae):
    """Classifica o setor usando os dois primeiros dígitos do CNAE."""
    divisao = normalizar_cnae(cnae)[:2]

    setores = {
        "26": "Eletrônica e componentes",
        "27": "Equipamentos elétricos",
        "28": "Máquinas e equipamentos",
        "33": "Manutenção e instalação industrial",
        "71": "Engenharia e serviços técnicos",
        "72": "Pesquisa e desenvolvimento",
    }

    return setores.get(divisao, "Outros setores")

def classificar_mercado(cnae, eh_mei):
    """Cria uma classificação analítica de mercado."""
    divisao = normalizar_cnae(cnae)[:2]

    if divisao == "72":
        return "P&D"

    if divisao in {"26", "27", "28", "33"}:
        return "B2B / Pequeno Prestador" if eh_mei else "B2B / Industrial"

    if divisao == "71":
        return "B2B / Profissional Autônomo" if eh_mei else "B2B / Serviços Técnicos"

    return "Outros"

# ==============================================================================
# VERIFICAÇÃO
# ==============================================================================
if not ARQUIVO_PARQUET.exists():
    raise FileNotFoundError(f"Arquivo não encontrado:\n{ARQUIVO_PARQUET}")

if not CNAES_ALVO:
    raise ValueError("A lista CNAES_ALVO está vazia.")

CNAES_ALVO = list(dict.fromkeys(normalizar_cnae(cnae) for cnae in CNAES_ALVO))


# ==============================================================================
# INÍCIO
# ==============================================================================
print("Iniciando processamento...")
print(f"CNAEs selecionados: {', '.join(CNAES_ALVO)}")

# ==============================================================================
# DUCKDB
# ==============================================================================
con = duckdb.connect()


# ==============================================================================
# CONSTRUÇÃO DO FILTRO
# ==============================================================================
lista_cnaes = ", ".join(f"'{cnae}'" for cnae in CNAES_ALVO)


# ==============================================================================
# SELEÇÃO
# ==============================================================================

query = f"""
SELECT
    cnpj,
    razao_social,
    nome_fantasia,
    tipo,
    porte,
    opcao_simples,
    opcao_mei,
    capital_social,
    data_abertura,
    cnae_fiscal_principal,
    cnae_fiscal_secundaria,
    uf,
    cidade,
    cep,
    endereco_completo,
    telefone,
    correio_eletronico
FROM '{ARQUIVO_PARQUET.as_posix()}'
WHERE cnae_fiscal_principal IN ({lista_cnaes})
"""

print("Selecionando empresas...")
df = con.execute(query).df()

print(f"Empresas encontradas: {len(df):,}")

# ==============================================================================
# CLASSIFICAÇÃO
# ==============================================================================
print("\nClassificando empresas...")

df["cnae_fiscal_principal"] = df["cnae_fiscal_principal"].apply(normalizar_cnae)

df["setor"] = df["cnae_fiscal_principal"].apply(classificar_setor)

df["eh_mei"] = (
    df["opcao_mei"]
    .astype(str)
    .str.upper()
    .str.strip()
    .eq("S")
)

df["tipo_mercado"] = df.apply(
    lambda row: classificar_mercado(
        row["cnae_fiscal_principal"],
        row["eh_mei"]
    ),
    axis=1
)


# ==============================================================================
# PERFIL DA EMPRESA
# ==============================================================================

def gerar_perfil(row):
    mercado = row["tipo_mercado"]
    porte = str(row["porte"]).strip()

    if mercado == "P&D":
        return "Pesquisa e Desenvolvimento"

    if mercado == "B2B / Industrial":
        if porte == "Empresa de Pequeno Porte (EPP)":
            return "B2B Industrial / EPP"
        if porte == "Demais":
            return "B2B Industrial / Corporativo"
        return "B2B Industrial"

    return mercado

df["perfil_mercado"] = df.apply(gerar_perfil, axis=1)

df.drop(columns=["eh_mei"], inplace=True)

# ==============================================================================
# ORGANIZAÇÃO DAS COLUNAS
# ==============================================================================
colunas = [
    "cnpj",
    "razao_social",
    "nome_fantasia",
    "cnae_fiscal_principal",
    "setor",
    "tipo_mercado",
    "perfil_mercado",
    "tipo",
    "porte",
    "opcao_simples",
    "opcao_mei",
    "capital_social",
    "data_abertura",
    "cnae_fiscal_secundaria",
    "uf",
    "cidade",
    "cep",
    "endereco_completo",
    "telefone",
    "correio_eletronico",
]

colunas = [coluna for coluna in colunas if coluna in df.columns]
df_export = df[colunas]


# ==============================================================================
# ORDENAÇÃO
# ==============================================================================
df_export = df_export.sort_values(
    by=["cnae_fiscal_principal", "data_abertura"],
    ascending=[True, False]
)

# ==============================================================================
# EXPORTAÇÃO
# ==============================================================================

print("\nExportando Excel...")
ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
df_export.to_excel(ARQUIVO_SAIDA, index=False)

# ==============================================================================
# RELATÓRIO
# ==============================================================================
print("\nEmpresas por CNAE:")
for cnae, quantidade in df_export["cnae_fiscal_principal"].value_counts().sort_index().items():
    print(f"  {cnae}: {quantidade:,}")

print("\nEmpresas por setor:")
for setor, quantidade in df_export["setor"].value_counts().items():
    print(f"  {setor}: {quantidade:,}")

print("\nEmpresas por tipo de mercado:")
for tipo, quantidade in df_export["tipo_mercado"].value_counts().items():
    print(f"  {tipo}: {quantidade:,}")

print("\n" + "=" * 60)
print("Processamento concluído!")
print(f"Total de empresas: {len(df_export):,}")
print(f"Tempo: {time.time() - inicio:.2f} segundos")
print(f"Arquivo: {ARQUIVO_SAIDA}")
print("=" * 60)

con.close()