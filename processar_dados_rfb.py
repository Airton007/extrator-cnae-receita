import pandas as pd
import zipfile
import glob
import os
import time

# Início do cronômetro total
tempo_inicio_total = time.time()

# 1. CNAEs de Engenharia Física
CNAES_ALVO = {

   # "7210000", # P&D em Ciências Físicas
    "2610800", # Fabricação de Componentes Eletrônicos
    "2651500", # Aparelhos de Medida, Teste e Controle
    "2660400", # Aparelhos Eletromédicos e Radiação (Física Médica)
    "2670101", # Equipamentos Ópticos e Laser
   # "2670102", # Aparelhos Fotográficos/Sensores
   # "2399199", # Cerâmicas de Alta Performance
   # "2710401", # Tecnologia de Geradores/Solar
    "3250701", # Instrumentos de Laboratório/Médicos
    "2833000", # Automação Agrícola (Máquinas)
    "3041500", # Indústria Aeroespacial
    "3042300"  # Motores e Turbinas Aeroespaciais
}

MAPA_PORTE = {
    "00": "Não Informado", "01": "Micro Empresa (ME)", 
    "03": "Empresa de Pequeno Porte (EPP)", "05": "Demais"
}
MAPA_TIPO = {"1": "Matriz", "2": "Filial"}

COLUNAS_ESTAB = [
    "cnpj_basico", "cnpj_ordem", "cnpj_dv", "identificador_matriz_filial",
    "nome_fantasia", "situacao_cadastral", "data_situacao_cadastral",
    "motivo_situacao_cadastral", "nome_cidade_exterior", "pais",
    "data_inicio_atividade", "cnae_fiscal_principal", "cnae_fiscal_secundaria",
    "tipo_logradouro", "logradouro", "numero", "complemento", "bairro",
    "cep", "uf", "municipio", "ddd_1", "telefone_1", "ddd_2", "telefone_2",
    "ddd_fax", "fax", "correio_eletronico", "situacao_especial", "data_situacao_especial"
]

COLUNAS_EMP = [
    "cnpj_basico", "razao_social", "natureza_juridica", 
    "qualificacao_responsavel", "capital_social", "porte_empresa", 
    "ente_federativo_responsavel"
]

COLUNAS_SIMPLES = [
    "cnpj_basico", "opcao_simples", "data_opcao_simples", "data_exclusao_simples",
    "opcao_mei", "data_opcao_mei", "data_exclusao_mei"
]

# ==========================================
# 1. Carregar Dicionário de Municípios
# ==========================================
mapa_municipios = {}
if os.path.exists("Municipios.zip"):
    print("Carregando Municipios.zip...")
    with zipfile.ZipFile("Municipios.zip") as z:
        with z.open(z.namelist()[0]) as f:
            df_mun = pd.read_csv(f, sep=";", header=None, names=["codigo", "nome"], dtype=str, encoding="latin1")
            df_mun["codigo"] = df_mun["codigo"].str.strip().str.zfill(4)
            mapa_municipios = dict(zip(df_mun["codigo"], df_mun["nome"]))
elif os.path.exists("Municipios.csv"):
    print("Carregando Municipios.csv...")
    df_mun = pd.read_csv("Municipios.csv", sep=";", header=None, names=["codigo", "nome"], dtype=str, encoding="latin1")
    df_mun["codigo"] = df_mun["codigo"].str.strip().str.zfill(4)
    mapa_municipios = dict(zip(df_mun["codigo"], df_mun["nome"]))

# ==========================================
# 2. Filtrar Estabelecimentos por CNAE
# ==========================================
estab_filtrados = []
print("Filtrando estabelecimentos por CNAE...")
for arq in sorted(glob.glob("Estabelecimentos*.zip")):
    with zipfile.ZipFile(arq) as z:
        with z.open(z.namelist()[0]) as f:
            for chunk in pd.read_csv(f, sep=";", header=None, names=COLUNAS_ESTAB, dtype=str, encoding="latin1", chunksize=100000):
                chunk_ativas = chunk[chunk["situacao_cadastral"] == "02"]
                m_pri = chunk_ativas["cnae_fiscal_principal"].isin(CNAES_ALVO)
                m_sec = chunk_ativas["cnae_fiscal_secundaria"].fillna("").apply(lambda s: any(c in s for c in CNAES_ALVO))
                matches = chunk_ativas[m_pri | m_sec]
                if not matches.empty:
                    estab_filtrados.append(matches)

if not estab_filtrados:
    print("Nenhum estabelecimento encontrado com os CNAEs alvo.")
    exit()

df_estab = pd.concat(estab_filtrados, ignore_index=True)
cnpjs_basicos = set(df_estab["cnpj_basico"].unique())

# ==========================================
# 3. Buscar Dados de Empresas (Razão Social e Porte)
# ==========================================
emp_filtradas = []
print("Buscando Razões Sociais em Empresas*.zip...")
for arq in sorted(glob.glob("Empresas*.zip")):
    with zipfile.ZipFile(arq) as z:
        with z.open(z.namelist()[0]) as f:
            for chunk in pd.read_csv(f, sep=";", header=None, names=COLUNAS_EMP, dtype=str, encoding="latin1", chunksize=100000):
                match = chunk[chunk["cnpj_basico"].isin(cnpjs_basicos)]
                if not match.empty:
                    emp_filtradas.append(match[["cnpj_basico", "razao_social", "capital_social", "porte_empresa"]])

df_emp = pd.concat(emp_filtradas, ignore_index=True).drop_duplicates("cnpj_basico") if emp_filtradas else pd.DataFrame()

# ==========================================
# 4. Buscar Simples Nacional / MEI
# ==========================================
df_simples_res = pd.DataFrame()
if os.path.exists("Simples.zip"):
    print("Buscando Simples Nacional / MEI...")
    with zipfile.ZipFile("Simples.zip") as z:
        with z.open(z.namelist()[0]) as f:
            for chunk in pd.read_csv(f, sep=";", header=None, names=COLUNAS_SIMPLES, dtype=str, encoding="latin1", chunksize=100000):
                match = chunk[chunk["cnpj_basico"].isin(cnpjs_basicos)]
                if not match.empty:
                    df_simples_res = pd.concat([df_simples_res, match[["cnpj_basico", "opcao_simples", "opcao_mei"]]], ignore_index=True)

# ==========================================
# 5. Consolidação e Formatação
# ==========================================
print("Consolidando dados...")
df_final = df_estab.merge(df_emp, on="cnpj_basico", how="left")
if not df_simples_res.empty:
    df_final = df_final.merge(df_simples_res.drop_duplicates("cnpj_basico"), on="cnpj_basico", how="left")
else:
    df_final["opcao_simples"] = ""
    df_final["opcao_mei"] = ""

df_final["cnpj"] = df_final["cnpj_basico"] + df_final["cnpj_ordem"] + df_final["cnpj_dv"]
df_final["tipo"] = df_final["identificador_matriz_filial"].map(MAPA_TIPO).fillna("Matriz")
df_final["porte"] = df_final["porte_empresa"].map(MAPA_PORTE).fillna("Não Informado")
df_final["cidade"] = df_final["municipio"].astype(str).str.strip().str.zfill(4).map(mapa_municipios).fillna(df_final["municipio"])
df_final["telefone"] = df_final["ddd_1"].fillna("") + df_final["telefone_1"].fillna("")
df_final["endereco_completo"] = (
    df_final["tipo_logradouro"].fillna("") + " " + 
    df_final["logradouro"].fillna("") + ", " + 
    df_final["numero"].fillna("") + " - " + 
    df_final["bairro"].fillna("")
).str.strip()
df_final["data_abertura"] = pd.to_datetime(df_final["data_inicio_atividade"], format="%Y%m%d", errors="coerce").dt.strftime("%d/%m/%Y")

# Colunas finais organizadas
colunas_exportacao = [
    "cnpj", "razao_social", "nome_fantasia", "tipo", "porte",
    "opcao_simples", "opcao_mei", "capital_social",
    "data_abertura", "cnae_fiscal_principal", "cnae_fiscal_secundaria",
    "uf", "cidade", "cep", "endereco_completo", "telefone", "correio_eletronico"
]

df_export = df_final[colunas_exportacao].drop_duplicates(subset=["cnpj"])
df_export.to_excel("relatorio_completo_empresas_rfb.xlsx", index=False)

tempo_total = time.time() - tempo_inicio_total
minutos = int(tempo_total // 60)
segundos = tempo_total % 60

print("\n" + "="*50)
print(f"Processamento concluído com sucesso!")
print(f"Total de empresas exportadas: {len(df_export)}")
print(f"Tempo total decorrido: {minutos}m {segundos:.2f}s ({tempo_total:.2f} segundos)")
print("="*50)