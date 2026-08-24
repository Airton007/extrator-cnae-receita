import pandas as pd
import requests
import time

# Exemplo de CNAE (ex: 7210-0/00 - Pesquisa e desenvolvimento experimental em ciências físicas e naturais)
CNAE_ALVO = "7210000" 

# Lista de CNPJs para consulta/teste
cnpjs_para_consultar = [
    "33000167000101", # Exemplo 1
    "00396895000125", # Exemplo 2 (Embrapa)
    "60701190000104"  # Exemplo 3
]

empresas_filtradas = []

print("Iniciando consulta via BrasilAPI...")

for cnpj in cnpjs_para_consultar:
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        
        # Pega o CNAE principal
        cnae_principal = str(data.get("cnae_fiscal", ""))
        
        # Opcional: Verifica também os CNAEs secundários
        cnaes_secundarios = [str(item["codigo"]) for item in data.get("cnaes_secundarios", [])]
        
        # Verifica se o CNAE alvo está na empresa
        if CNAE_ALVO in cnae_principal or CNAE_ALVO in cnaes_secundarios:
            empresas_filtradas.append({
                "CNPJ": data.get("cnpj"),
                "Razão Social": data.get("razao_social"),
                "Nome Fantasia": data.get("nome_fantasia"),
                "CNAE Principal": cnae_principal,
                "Descrição CNAE": data.get("cnae_fiscal_descricao"),
                "UF": data.get("uf"),
                "Municipio": data.get("municipio"),
                "Logradouro": data.get("logradouro"),
                "Telefone": data.get("ddd_telefone_1"),
                "E-mail": data.get("email")
            })
            print(f"[MATCH] Empresa encontrada: {data.get('razao_social')}")
    else:
        print(f"Erro ao consultar CNPJ {cnpj}: Status {response.status_code}")
    
    # Respeita o limite de requisições da API
    time.sleep(1)

# Exporta para Excel
if empresas_filtradas:
    df = pd.DataFrame(empresas_filtradas)
    df.to_excel("empresas_por_cnae.xlsx", index=False)
    print("\nArquivo 'empresas_por_cnae.xlsx' gerado com sucesso!")
else:
    print("\nNenhuma empresa encontrada para o CNAE especificado.")