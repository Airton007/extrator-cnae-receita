"""
Pipeline ETL para Extração e Consolidação de Dados da Receita Federal (RFB).

Processa os arquivos ZIP brutos da Receita Federal em paralelo, filtrando
estabelecimentos ativos com base nos CNAEs-alvo relacionados à Engenharia
Física e áreas de tecnologia associadas.

Os dados selecionados de Estabelecimentos são posteriormente cruzados com
as bases de Empresas, Simples/MEI e Municípios, permitindo obter informações
como razão social, porte, situação cadastral e localização.

Etapas do processo:
    1. Leitura em stream dos arquivos de Estabelecimentos e filtragem por CNAE.
    2. Seleção de estabelecimentos com situação cadastral ativa ('02').
    3. Carregamento dos dados de Municípios.
    4. Cruzamento dos CNPJs com as bases de Empresas e Simples/MEI.
    5. Consolidação dos dados por meio de JOINs SQL no DuckDB.
    6. Exportação da base final em formato Parquet comprimido com ZSTD.

Entrada:
    data/raw/2026-08/
        Arquivos ZIP brutos da Receita Federal.

Saída:
    data/processed/base_engenharia_fisica.parquet
"""

import glob
import os
from pathlib import Path
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
import duckdb
import pandas as pd

tempo_inicio = time.time()

# ==============================================================================
# CONFIGURAÇÃO DE CAMINHOS (PATHLIB)
# ==============================================================================
# Localiza a raiz do repositório (subindo 2 níveis a partir de src/etl/processar_dados_rfb.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Pastas de dados e saída
PASTA_DADOS = BASE_DIR / "data" / "raw" / "2026-08"
ARQUIVO_PARQUET = BASE_DIR / "data" / "processed" / "base_engenharia_fisica.parquet"

# ==============================================================================
# DESCRIÇÃO DOS CNAES ALVO (ENGENHARIA FÍSICA / HARD TECH / P&D / INDÚSTRIA)
# ==============================================================================
MAPA_CNAES_DESCRICAO = {
    # --- Pesquisa, Desenvolvimento e Radiação ---
    "7210000": "Pesquisa e desenvolvimento experimental em ciências físicas e naturais",
    "2660400": "Fabricação de aparelhos eletromédicos e eletroterapêuticos e equipamentos de irradiação",
    # --- Semicondutores, Fotônica e Telecomunicações ---
    "2610800": "Fabricação de componentes eletrônicos e semicondutores",
    "2731700": "Fabricação de aparelhos e equipamentos para distribuição e controle de energia elétrica",
    # --- Metrologia, Instrumentação e Controle de Processos ---
    "3312103": "Manutenção e reparação de aparelhos eletromédicos e eletroterapêuticos e equipamentos de irradiação",
}

# CNAEs Alvo em bytes para verificação ultra-rápida em stream
CNAES_ALVO_BYTES = {cnae.encode("utf-8") for cnae in MAPA_CNAES_DESCRICAO.keys()}

COLUNAS_ESTAB = [
    "cnpj_basico",
    "cnpj_ordem",
    "cnpj_dv",
    "matriz_filial",
    "nome_fantasia",
    "situacao_cadastral",
    "data_situacao_cadastral",
    "motivo_situacao",
    "cidade_exterior",
    "pais",
    "data_inicio_atividade",
    "cnae_principal",
    "cnae_secundaria",
    "tipo_logradouro",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "cep",
    "uf",
    "municipio",
    "ddd_1",
    "telefone_1",
    "ddd_2",
    "telefone_2",
    "ddd_fax",
    "fax",
    "correio_eletronico",
    "situacao_especial",
    "data_situacao_especial",
]


def processar_estab_zip(caminho_zip):
    """Lê um arquivo .zip em stream rápido e filtra apenas as linhas com os CNAEs."""
    linhas_filtradas = []
    with zipfile.ZipFile(caminho_zip) as z:
        nome_arquivo = z.namelist()[0]
        with z.open(nome_arquivo) as f:
            for linha in f:
                # 1. Filtro rápido de texto em bytes
                if not any(cnae in linha for cnae in CNAES_ALVO_BYTES):
                    continue

                # Decodifica apenas a linha relevante
                partes = (
                    linha.decode("latin1", errors="ignore")
                    .replace('"', "")
                    .strip()
                    .split(";")
                )
                if len(partes) >= 12 and partes[5] == "02":  # Apenas ativas
                    linhas_filtradas.append(partes[:30])

    if linhas_filtradas:
        df = pd.DataFrame(linhas_filtradas)
        # Garante 30 colunas
        while df.shape[1] < 30:
            df[df.shape[1]] = ""
        df = df.iloc[:, :30]
        df.columns = COLUNAS_ESTAB
        return df
    return pd.DataFrame(columns=COLUNAS_ESTAB)


def main():
    print(
        f"Iniciando Extração com Multiprocessamento Paralelo na pasta '{PASTA_DADOS}'...\n"
    )

    # Busca arquivos no diretório 2026-08 ou fallback na pasta de dados bruta geral
    arquivos_estab = sorted(
        glob.glob(os.path.join(PASTA_DADOS, "Estabelecimentos*.zip"))
    )
    if not arquivos_estab:
        arquivos_estab = sorted(
            glob.glob(os.path.join(BASE_DIR / "data" / "raw", "Estabelecimentos*.zip"))
        )

    print(
        f"1/4. Processando {len(arquivos_estab)} arquivos de Estabelecimentos em paralelo nos núcleos da CPU..."
    )

    # Processa todos os arquivos zip ao mesmo tempo
    dfs_estab = []
    with ProcessPoolExecutor() as executor:
        resultados = list(executor.map(processar_estab_zip, arquivos_estab))
        for res in resultados:
            if not res.empty:
                dfs_estab.append(res)

    if not dfs_estab:
        print("Nenhuma empresa com os CNAEs alvo foi encontrada.")
        return

    df_estab = pd.concat(dfs_estab, ignore_index=True)
    df_estab["cnpj"] = (
        df_estab["cnpj_basico"] + df_estab["cnpj_ordem"] + df_estab["cnpj_dv"]
    )
    df_estab["tipo"] = (
        df_estab["matriz_filial"]
        .map({"1": "Matriz", "2": "Filial"})
        .fillna("Matriz")
    )
    df_estab["municipio"] = (
        df_estab["municipio"].astype(str).str.strip().str.zfill(4)
    )
    df_estab["telefone"] = df_estab["ddd_1"].fillna("") + df_estab[
        "telefone_1"
    ].fillna("")
    df_estab["endereco_completo"] = (
        df_estab["tipo_logradouro"].fillna("")
        + " "
        + df_estab["logradouro"].fillna("")
        + ", "
        + df_estab["numero"].fillna("")
        + " - "
        + df_estab["bairro"].fillna("")
    ).str.strip()
    df_estab["data_abertura"] = pd.to_datetime(
        df_estab["data_inicio_atividade"], format="%Y%m%d", errors="coerce"
    ).dt.strftime("%d/%m/%Y")

    print(f"-> {len(df_estab)} estabelecimentos ativos encontrados.")
    cnpjs_set = set(df_estab["cnpj_basico"].unique())

    # 2. Municípios
    print("2/4. Carregando municípios...")
    arqs_mun = sorted(
        glob.glob(os.path.join(PASTA_DADOS, "Municipios.zip"))
    ) or sorted(
        glob.glob(os.path.join(BASE_DIR / "data" / "raw", "Municipios.zip"))
    )
    df_mun = pd.DataFrame(columns=["cod_municipio", "nome_cidade"])
    if arqs_mun:
        with zipfile.ZipFile(arqs_mun[0]) as z:
            with z.open(z.namelist()[0]) as f:
                df_mun = pd.read_csv(
                    f, sep=";", header=None, dtype=str, encoding="latin1"
                )
                df_mun = df_mun.iloc[:, [0, 1]]
                df_mun.columns = ["cod_municipio", "nome_cidade"]
                df_mun["cod_municipio"] = (
                    df_mun["cod_municipio"].str.strip().str.zfill(4)
                )
                df_mun["nome_cidade"] = df_mun["nome_cidade"].str.strip()

    # 3. Empresas (Razão Social e Porte)
    print("3/4. Buscando Razão Social e Porte...")
    arqs_emp = sorted(
        glob.glob(os.path.join(PASTA_DADOS, "Empresas*.zip"))
    ) or sorted(
        glob.glob(os.path.join(BASE_DIR / "data" / "raw", "Empresas*.zip"))
    )
    emp_lista = []
    for arq in arqs_emp:
        with zipfile.ZipFile(arq) as z:
            with z.open(z.namelist()[0]) as f:
                for chunk in pd.read_csv(
                    f,
                    sep=";",
                    header=None,
                    dtype=str,
                    encoding="latin1",
                    chunksize=250000,
                    on_bad_lines="skip",
                ):
                    match = chunk[chunk[0].isin(cnpjs_set)]
                    if not match.empty:
                        emp_lista.append(match.iloc[:, [0, 1, 4, 5]])

    df_emp = pd.DataFrame(
        columns=["cnpj_basico", "razao_social", "capital_social", "porte"]
    )
    if emp_lista:
        df_emp = pd.concat(emp_lista, ignore_index=True).drop_duplicates(0)
        df_emp.columns = [
            "cnpj_basico",
            "razao_social",
            "capital_social",
            "porte_cod",
        ]
        df_emp["porte"] = (
            df_emp["porte_cod"]
            .map(
                {
                    "01": "Micro Empresa (ME)",
                    "03": "Empresa de Pequeno Porte (EPP)",
                    "05": "Demais",
                }
            )
            .fillna("Não Informado")
        )

    # 4. Simples / MEI
    print("4/4. Buscando Simples / MEI...")
    arqs_simples = sorted(
        glob.glob(os.path.join(PASTA_DADOS, "Simples.zip"))
    ) or sorted(
        glob.glob(os.path.join(BASE_DIR / "data" / "raw", "Simples.zip"))
    )
    df_simples = pd.DataFrame(
        columns=["cnpj_basico", "opcao_simples", "opcao_mei"]
    )
    if arqs_simples:
        simples_lista = []
        with zipfile.ZipFile(arqs_simples[0]) as z:
            with z.open(z.namelist()[0]) as f:
                for chunk in pd.read_csv(
                    f,
                    sep=";",
                    header=None,
                    dtype=str,
                    encoding="latin1",
                    chunksize=250000,
                    on_bad_lines="skip",
                ):
                    match = chunk[chunk[0].isin(cnpjs_set)]
                    if not match.empty:
                        simples_lista.append(match.iloc[:, [0, 1, 4]])
        if simples_lista:
            df_simples = (
                pd.concat(simples_lista, ignore_index=True).drop_duplicates(0)
            )
            df_simples.columns = ["cnpj_basico", "opcao_simples", "opcao_mei"]

    # 5. Consolidação e Salvamento via DuckDB
    con = duckdb.connect()
    con.register("tab_estab", df_estab)
    con.register("tab_emp", df_emp)
    con.register("tab_simples", df_simples)
    con.register("tab_municipios", df_mun)

    # Garante que a pasta de destino exista
    ARQUIVO_PARQUET.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nGravando '{ARQUIVO_PARQUET}'...")

    con.execute(f"""
    COPY (
        SELECT 
            e.cnpj,
            emp.razao_social,
            e.nome_fantasia,
            e.tipo,
            COALESCE(emp.porte, 'Não Informado') AS porte,
            COALESCE(s.opcao_simples, '') AS opcao_simples,
            COALESCE(s.opcao_mei, '') AS opcao_mei,
            emp.capital_social,
            e.data_abertura,
            e.cnae_principal AS cnae_fiscal_principal,
            e.cnae_secundaria AS cnae_fiscal_secundaria,
            e.uf,
            COALESCE(m.nome_cidade, e.municipio) AS cidade,
            e.cep,
            e.endereco_completo,
            e.telefone,
            e.correio_eletronico
        FROM tab_estab e
        LEFT JOIN tab_emp emp ON e.cnpj_basico = emp.cnpj_basico
        LEFT JOIN tab_simples s ON e.cnpj_basico = s.cnpj_basico
        LEFT JOIN tab_municipios m ON e.municipio = m.cod_municipio
    ) TO '{ARQUIVO_PARQUET.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """)

    tempo_total = time.time() - tempo_inicio
    print("=" * 50)
    print(
        f"Sucesso! Base consolidada '{ARQUIVO_PARQUET}' criada em {tempo_total // 60:.0f}m {tempo_total % 60:.2f}s."
    )
    print("=" * 50)


if __name__ == "__main__":
    main()