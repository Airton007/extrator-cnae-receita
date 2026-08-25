import pandas as pd
import zipfile

# Carrega o dicionário de conversão Código -> Nome do Município
with zipfile.ZipFile("Municipios.zip") as z:
    nome_csv = z.namelist()[0]
    with z.open(nome_csv) as f:
        df_mun = pd.read_csv(
            f, 
            sep=";", 
            header=None, 
            names=["codigo", "nome_municipio"], 
            dtype=str, 
            encoding="latin1"
        )
        mapa_municipios = dict(zip(df_mun["codigo"], df_mun["nome_municipio"]))

# Exemplo de conversão:
# Se o código for '6213', o retorno será 'SAO PAULO'
codigo = "6213"
cidade_nome = mapa_municipios.get(codigo, "Desconhecido")
print(f"Código {codigo} -> {cidade_nome}")