# 📍 Análise e Mapeamento Espacial de Empresas de Base Tecnológica (CNAEs)

Pipeline em Python para análise espacial, mensuração de concentração econômica (CR4 e HHI) e visualização interativa de empresas brasileiras por código CNAE.

---

## 🚀 Funcionalidades

- **Carga de Alta Performance**: Suporte nativo a arquivos Parquet com **DuckDB** e fallback para Excel.
- **Cálculo de Indicadores Industriais**:
  - **CR4**: Concentração nos 4 principais estados.
  - **HHI (Índice de Herfindahl-Hirschman)**: Medição de polarização geográfica.
- **Dashboard Executivo (`.png`)**: Visão consolidada em alta resolução (300 DPI) com mapa coroplético, ranking e tabela por UF.
- **Mapa Interativo (`.html`)**: Mapa navegável com OpenStreetMap, clustering de pontos, popups com detalhes cadastrais e controle de camadas por CNAE.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem**: Python 3.10+
- **Processamento de Dados**: `DuckDB`, `Pandas`, `NumPy`
- **Análise Espacial**: `GeoPandas`, `Folium`, `Branca`
- **Visualização**: `Matplotlib`, `GridSpec`

---

## 📦 Como Executar

### 1. Clone o repositório
```bash
git clone [https://github.com/seu-usuario/seu-repositorio.git](https://github.com/seu-usuario/seu-repositorio.git)
cd seu-repositorio
```

## 🛠️ Pipeline de Processamento de Dados da Receita Federal (ETL)

O script `1_1_processar_dados_rfb.py` é responsável por extrair, transformar e consolidar os dados abertos públicos da Receita Federal do Brasil (RFB) de forma otimizada para grande volume de dados.

### 🚀 Funcionalidades e Arquitetura

* **Processamento Paralelo em Stream:** Utiliza `concurrent.futures.ProcessPoolExecutor` para distribuir a leitura dos arquivos ZIP de Estabelecimentos entre os núcleos da CPU. A leitura é feita diretamente da memória (stream), dispensando a extração dos arquivos `.csv` para o disco.
* **Filtragem de Baixo Nível (Bytes):** Aplica um filtro primário diretamente nos bytes do arquivo antes da decodificação de texto (`latin1`), reduzindo drastically o uso de memória e tempo de execução.
* **Filtros de Negócio Aplicações:** 
  * Seleciona apenas estabelecimentos pertencentes aos **CNAEs-alvo** (setor de Engenharia Física/Hard Tech).
  * Mantém apenas empresas com **Situação Cadastral Ativa** (`02`).
* **Cruzamento de Bases:** Extrai apenas os registros das tabelas de *Empresas* (Razão Social, Capital Social e Porte) e *Simples/MEI* correspondentes aos CNPJs filtrados na etapa inicial.
* **Consolidação de Alta Performance:** Utiliza a engine do **DuckDB** para registrar os DataFrames em memória, executar a junção relacional (`LEFT JOIN`) e exportar a base tratada final.

### 📂 Arquivos Processados e Saída

| Etapa | Origem dos Dados | Descrição das Informações Extraídas |
| :--- | :--- | :--- |
| **1/4** | `Estabelecimentos*.zip` | CNPJ completo, Endereço, Telefones, E-mail, CNAEs e Situação Cadastral. |
| **2/4** | `Municipios.zip` | Mapeamento entre o código do município da RFB e o Nome da Cidade. |
| **3/4** | `Empresas*.zip` | Razão Social, Capital Social e Código de Porte da empresa. |
| **4/4** | `Simples.zip` | Indicadores de opção pelo Simples Nacional e MEI. |

* **Arquivo de Saída:** `base_engenharia_fisica.parquet` (Compactação ZSTD).

### ⚙️ Como Executar

Garanta que os arquivos `.zip` fornecidos pela Receita Federal estejam dentro do diretório especificado no script (ex: `2026-08/` ou na raiz do projeto) e execute:

```bash
python 1_1_processar_dados_rfb.py


---

### 📂 Estrutura do Repositório

```text
extrator-cnae-receita/
├── data/                       # Arquivos de dados pesados e temporários (ignorados no Git)
│   ├── raw/                    # Dados brutos baixados da Receita Federal
│   │   └── 2026-08/
│   ├── processed/              # Bases de dados consolidadas e limpas
│   │   └── base_engenharia_fisica.parquet
│   └── temp/                   # Arquivos temporários de suporte
│
├── outputs/                    # Resultados, relatórios e visualizações geradas
│   ├── relatorios/             # Planilhas executivas em Excel (.xlsx)
│   ├── mapas/                  # Dashboards e mapas por CNAE (.png)
│   └── resultados_espaciais/   # Mapeamento interativo (.html) e estatísticas
│
├── src/                        # Código-fonte organizado por etapas do pipeline
│   ├── etl/                    # Scripts de extração, limpeza e consolidação
│   │   ├── 1_1_gerar_base_empresas_rfb.py
│   │   └── corregir_ufs_planilha.py
│   ├── analysis/               # Consultas analíticas e classificação B2B
│   │   ├── 2_2_explorar_e_exportar_duckdb.py
│   │   └── 2_classificar_e_gerar_excel.py
│   └── spatial/                # Análise espacial, índices econômicos (CR4/HHI) e mapas
│       ├── analise_espacial_empresas.py
│       └── gerador_mapa_empresas.py
│
├── .gitignore                  # Regras para ignorar arquivos pesados e ambientes
├── pyvenv.cfg                   # Configuração do ambiente virtual Python
└── requirements.txt            # Dependências e bibliotecas do projeto
````

## ⚠️ Erro 403 ao carregar o mapa do OpenStreetMap

Ao abrir diretamente, com duplo clique, o arquivo `.html` gerado pelo
projeto, o mapa-base do OpenStreetMap pode não ser carregado
corretamente. Em alguns casos, o navegador pode apresentar um erro **403
(Access Denied / Access blocked)** no carregamento dos mapas.

### Por que isso acontece?

Quando o arquivo HTML é aberto diretamente, o navegador utiliza o
protocolo:

``` text
file://
```

Nesse modo, o mapa é executado como um arquivo local. As requisições
realizadas pelo mapa para os servidores de tiles do OpenStreetMap não
possuem o mesmo contexto de uma página disponibilizada por HTTP.

Dependendo do navegador e das condições da requisição, o servidor de
tiles pode bloquear esse acesso e retornar um erro **403**.

Esse problema **não significa necessariamente que o código ou os dados
do mapa estejam incorretos**. Os marcadores, dados das empresas,
filtros, legendas e demais elementos do mapa podem estar funcionando
normalmente; o problema está no carregamento do mapa-base a partir de um
arquivo `file://`.

### ✅ Solução

Caso o mapa-base do OpenStreetMap não seja carregado ou apareça um erro
**403**, execute o arquivo HTML através de um **servidor HTTP local**.

Na pasta onde está localizado o arquivo `.html`, abra um terminal e
execute:

``` bash
python -m http.server 8000
```

Depois, abra o navegador e acesse:

``` text
http://localhost:8000
```

Na página que será exibida, clique no arquivo HTML do mapa.

O mapa será então acessado através de:

``` text
http://localhost:8000/arquivo.html
```

em vez de:

``` text
file:///.../arquivo.html
```

### 📌 Passo a passo

1.  Gere o mapa normalmente utilizando o projeto.
2.  Localize a pasta que contém o arquivo `.html`.
3.  Abra um terminal nessa pasta.
4.  Execute:

``` bash
python -m http.server 8000
```

5.  Abra o navegador.
6.  Acesse:

``` text
http://localhost:8000
```

7.  Clique no arquivo `.html` correspondente ao mapa.

Para encerrar o servidor, volte ao terminal e pressione:

``` text
Ctrl + C
```

### 🌐 Requisito de internet

O servidor local apenas disponibiliza o arquivo HTML no computador. O
mapa-base do OpenStreetMap continua sendo carregado pela internet.

Portanto:

-   **Servidor local:** permite que o HTML seja servido corretamente
    pelo navegador.
-   **Internet:** necessária para carregar os tiles do OpenStreetMap.

### Resumo

  Como o HTML é aberto           Resultado
  ------------------------------ ----------------------------------------------------
  Duplo clique → `file://`       ⚠️ Pode ocorrer erro 403 no OpenStreetMap
  `python -m http.server 8000`   ✅ Recomendado
  `http://localhost:8000`        ✅ Mapa carregado corretamente
  Sem internet                   ❌ O mapa-base do OpenStreetMap não será carregado

> **Em caso de erro 403 no mapa-base do OpenStreetMap, não é necessário
> alterar o código do projeto. Primeiro, tente executar o HTML
> utilizando um servidor local com `python -m http.server 8000`.**
