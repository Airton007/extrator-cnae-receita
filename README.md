# 📍 Análise e Mapeamento Espacial de Empresas de Base Tecnológica (CNAEs)

Pipeline em Python para **extração, tratamento, classificação e análise espacial de empresas brasileiras** a partir dos dados abertos da Receita Federal do Brasil (RFB).

O projeto permite selecionar empresas por **CNAE**, realizar a higienização das informações cadastrais, classificar as empresas por setor e tipo de mercado e, posteriormente, analisar sua **distribuição e concentração geográfica** no Brasil por meio dos indicadores **CR4 e HHI**.

---

## 🎯 Objetivo

O projeto foi desenvolvido para construir uma base estruturada de empresas relacionadas à **Engenharia Física, Hard Tech, Pesquisa e Desenvolvimento, eletrônica, semicondutores, equipamentos eletromédicos e infraestrutura elétrica**.

A partir dos dados públicos da Receita Federal, o pipeline executa as seguintes etapas:

1. **Extração** dos dados brutos da Receita Federal;
2. **Filtragem** de estabelecimentos ativos por CNAE;
3. **Consolidação** das bases de Estabelecimentos, Empresas, Municípios e Simples/MEI;
4. **Classificação** das empresas por setor e tipo de mercado;
5. **Higienização** de UF e CEP;
6. **Correção e recuperação** de informações geográficas;
7. **Análise espacial** da distribuição das empresas;
8. **Cálculo dos indicadores CR4 e HHI**;
9. **Geração de dashboard estático**;
10. **Geração de mapa interativo** em HTML.

---

# 🚀 Funcionalidades

## 📊 Extração e consolidação dos dados

* Processamento dos arquivos públicos da Receita Federal em formato `.zip`;
* Leitura dos arquivos de Estabelecimentos em **stream**, sem necessidade de extração prévia dos CSVs;
* Processamento paralelo utilizando `ProcessPoolExecutor`;
* Filtragem inicial por CNAE diretamente nos bytes dos arquivos;
* Seleção de estabelecimentos com **Situação Cadastral Ativa (`02`)**;
* Cruzamento com as bases de:

  * Estabelecimentos;
  * Empresas;
  * Municípios;
  * Simples Nacional / MEI;
* Consolidação utilizando **DuckDB**;
* Exportação da base consolidada em **Parquet com compressão ZSTD**.

O processamento paralelo e a filtragem inicial em bytes são utilizados para reduzir o custo de processamento dos grandes arquivos da Receita Federal.

---

## 🏷️ Seleção e classificação por CNAE

A etapa de classificação permite alterar o universo da pesquisa modificando apenas a lista `CNAES_ALVO`.

Atualmente, os CNAEs utilizados na análise principal são:

| CNAE      | Descrição                                                                               |
| --------- | --------------------------------------------------------------------------------------- |
| `7210000` | Pesquisa e desenvolvimento experimental em ciências físicas e naturais                  |
| `2660400` | Fabricação de aparelhos eletromédicos e eletroterapêuticos e equipamentos de irradiação |
| `2610800` | Fabricação de componentes eletrônicos e semicondutores                                  |
| `2731700` | Fabricação de aparelhos e equipamentos para distribuição e controle de energia elétrica |

Esses quatro códigos são os atualmente selecionados pelo script de classificação e utilizados na análise espacial.

Para incluir novos CNAE nas análises, é necessário adicioná-lo às respectivas configurações dos scripts.

---

# 🛠️ Tecnologias utilizadas

### Linguagem

* **Python 3.10+**

### Processamento e manipulação de dados

* `Pandas`, `NumPy`  `DuckDB`

### Análise espacial

* `GeoPandas`, `Folium`, `Branca`

### Visualização

* `Matplotlib`, `GridSpec`

### Dados geográficos

O módulo espacial utiliza:

* GeoJSON dos estados brasileiros;
* Coordenadas de municípios;
* OpenStreetMap;
* CartoDB Positron;
* CartoDB Voyager.

---

# 📂 Estrutura do projeto

```text
extrator-cnae-receita/
│
├── data/
│   ├── raw/
│   │   └── 2026-08/
│   │       └── Arquivos ZIP da Receita Federal
│   │
│   ├── processed/
│   │   └── base_engenharia_fisica.parquet
│   │
│   └── temp/
│       └── Arquivos temporários
│
├── outputs/
│   ├── relatorios/
│   │   ├── relatorio_empresas.xlsx
│   │   └── relatorio_empresas_higienizado_completo.xlsx
│   │
│   ├── mapas/
│   │
│   └── resultados_espaciais/
│       ├── estatisticas_polarizacao_cnaes.xlsx
│       ├── dashboard_nacional_cnaes.png
│       └── mapa_interativo_empresas.html
│
├── src/
│   ├── etl/
│   │   ├── 1_1_gerar_base_empresas_rfb.py
│   │   └── 2_2_corrigir_ufs_planilha.py
│   │
│   ├── analysis/
│   │   └── 2_1_classificar_e_gerar_excel.py
│   │
│   └── spatial/
│       └── 3_1_analise_espacial_empresas.py
│
├── .gitignore
├── pyvenv.cfg
└── requirements.txt
```

---

# 🔄 Pipeline de processamento

O fluxo principal do projeto pode ser representado da seguinte forma:

                                         ```text
                                         Dados públicos da Receita Federal
                                                         │
                                                         ▼
                                         ┌───────────────────────────────┐
                                         │ 1. Extração e consolidação    │
                                         │ 1_1_gerar_base_empresas_rfb   │
                                         └───────────────┬───────────────┘
                                                         │
                                                         ▼
                                         base_engenharia_fisica.parquet
                                                         │
                                                         ▼
                                         ┌───────────────────────────────┐
                                         │ 2. Seleção e classificação    │
                                         │ 2_1_classificar_e_gerar_excel │
                                         └───────────────┬───────────────┘
                                                         │
                                                         ▼
                                         relatorio_empresas.xlsx
                                                         │
                                                         ▼
                                         ┌───────────────────────────────┐
                                         │ 3. Higienização geográfica    │
                                         │ 2_2_corrigir_ufs_planilha     │
                                         └───────────────┬───────────────┘
                                                         │
                                                         ▼
                                         relatorio_empresas_higienizado_completo.xlsx
                                                         │
                                                         ▼
                                         ┌───────────────────────────────┐
                                         │ 4. Análise espacial           │
                                         │ 3_1_analise_espacial_empresas │
                                         └───────────────┬───────────────┘
                                                         │
                                                 ┌───────┴────────┐
                                                 ▼                ▼
                                             Dashboard       Mapa interativo
                                               PNG                HTML
                                                 │                │
                                                 └───────┬────────┘
                                                         ▼
                                                 CR4 / HHI / Distribuição
                                         ```

---

# 📥 1. Extração e consolidação dos dados da Receita Federal

O script:

```text
src/etl/1_1_gerar_base_empresas_rfb.py
```

processa os arquivos públicos da Receita Federal e gera uma base consolidada em Parquet.

## Entrada

Os arquivos `.zip` devem estar preferencialmente em:

```text
data/raw/2026-08/
```

O script também possui fallback para procurar os arquivos diretamente em:

```text
data/raw/
```

### Arquivos utilizados

| Base                    | Informações                                                                |
| ----------------------- | -------------------------------------------------------------------------- |
| `Estabelecimentos*.zip` | CNPJ, endereço, telefone, e-mail, CNAE, UF, município e situação cadastral |
| `Municipios.zip`        | Código do município e nome da cidade                                       |
| `Empresas*.zip`         | Razão social, capital social e porte                                       |
| `Simples.zip`           | Opção pelo Simples Nacional e MEI                                          |

O script seleciona inicialmente estabelecimentos com situação cadastral ativa (`02`) e realiza posteriormente os cruzamentos entre as bases.

## Saída

```text
data/processed/base_engenharia_fisica.parquet
```

O arquivo é gravado utilizando **Parquet + ZSTD**, permitindo uma leitura eficiente nas etapas seguintes.

## Execução

A partir da raiz do projeto:

```bash
python src/etl/1_1_gerar_base_empresas_rfb.py
```

---

# 🏷️ 2. Seleção e classificação das empresas

O script:

```text
src/analysis/2_1_classificar_e_gerar_excel.py
```

carrega a base Parquet e seleciona os CNAEs definidos em:

```python
CNAES_ALVO = [
    "7210000",
    "2660400",
    "2610800",
    "2731700",
]
```

A lista pode ser modificada para alterar o universo da pesquisa.

O script também classifica as empresas em:

### Setor

* Eletrônica e componentes;
* Equipamentos elétricos;
* Máquinas e equipamentos;
* Manutenção e instalação industrial;
* Engenharia e serviços técnicos;
* Pesquisa e desenvolvimento;
* Outros setores.

### Tipo de mercado

* P&D;
* B2B / Industrial;
* B2B / Pequeno Prestador;
* B2B / Serviços Técnicos;
* B2B / Profissional Autônomo;
* Outros.

A classificação é baseada principalmente na divisão do CNAE e na condição de MEI.

## Entrada

```text
data/processed/base_engenharia_fisica.parquet
```

## Saída

```text
outputs/relatorios/relatorio_empresas.xlsx
```

## Execução

```bash
python src/analysis/2_1_classificar_e_gerar_excel.py
```

---

# 🧹 3. Higienização e correção geográfica

O script:

```text
src/etl/2_2_corrigir_ufs_planilha.py
```

realiza a preparação das informações geográficas para as análises posteriores.

As principais operações são:

* Padronização das UFs;
* Padronização dos CEPs;
* Validação da UF utilizando o CEP;
* Correção de UFs incompatíveis com o CEP;
* Inferência da UF a partir do endereço quando não há CEP válido;
* Recuperação de CEPs ausentes utilizando o **ViaCEP**;
* Utilização de cache para evitar consultas repetidas;
* Geração de relatório do processamento.

Essas operações estão definidas diretamente no fluxo de higienização do script.

## Entrada

```text
outputs/relatorios/relatorio_empresas.xlsx
```

## Saída

```text
outputs/relatorios/relatorio_empresas_higienizado_completo.xlsx
```

## Execução

```bash
python src/etl/2_2_corrigir_ufs_planilha.py
```

### 🌐 Internet necessária

Essa etapa utiliza o serviço **ViaCEP** para tentar recuperar CEPs ausentes.

Portanto, uma conexão com a internet é necessária para essa funcionalidade.

---

# 🗺️ 4. Análise espacial

O script:

```text
src/spatial/3_1_analise_espacial_empresas.py
```

realiza a análise espacial das empresas selecionadas.

O script pode carregar os dados a partir do:

```text
data/processed/base_engenharia_fisica.parquet
```

ou, como alternativa, utilizar:

```text
outputs/relatorios/relatorio_empresas_higienizado_completo.xlsx
```

O carregamento prioriza o Parquet quando ele está disponível.

---

## 📈 Indicadores de concentração

### CR4

O **CR4** representa a participação conjunta dos quatro estados com maior número de empresas para cada CNAE analisado.

No código, o indicador é calculado como:

```text
CR4 = participação dos 4 estados com maior número de empresas
```

e apresentado em porcentagem.

### HHI

O **HHI (Herfindahl-Hirschman Index)** é calculado a partir da participação relativa de cada estado:

```text
HHI = Σ participação²
```

O script calcula os dois indicadores separadamente para cada CNAE.

## Saída dos indicadores

```text
outputs/resultados_espaciais/estatisticas_polarizacao_cnaes.xlsx
```

---

# 📊 Dashboard nacional

O pipeline gera um dashboard estático em:

```text
outputs/resultados_espaciais/dashboard_nacional_cnaes.png
```

O dashboard possui:

* Mapa coroplético do Brasil;
* Quantidade de empresas por estado;
* Distribuição das empresas por CNAE;
* Ranking dos estados;
* Tabela com os 10 estados com maior quantidade de empresas;
* Informações gerais da base;
* Indicadores de concentração espacial.

O arquivo é exportado em **300 DPI**.

---

# 🌎 Mapa interativo

O projeto também gera um mapa interativo utilizando **Folium**:

```text
outputs/resultados_espaciais/mapa_interativo_empresas.html
```

O mapa possui:

* OpenStreetMap como mapa-base;
* CartoDB Positron;
* CartoDB Voyager;
* Controle de camadas;
* Uma camada independente para cada CNAE;
* Clustering de empresas;
* Marcadores dimensionados de acordo com a quantidade de empresas no município;
* Popups com informações cadastrais;
* Nome fantasia;
* Razão social;
* CNPJ;
* Porte;
* E-mail;
* Endereço;
* Legenda executiva com indicadores gerais.

As empresas são agrupadas por **município e UF**, e as coordenadas dos municípios são obtidas a partir de uma base externa, com fallback para centróides estaduais quando necessário.

---

# ⚠️ Erro 403 ao carregar o mapa do OpenStreetMap

Ao abrir diretamente, com duplo clique, o arquivo `.html` gerado pelo projeto, o mapa-base pode não carregar corretamente.

Em determinadas situações, o navegador pode apresentar um erro:

```text
403 - Access Denied
```

Isso pode ocorrer porque o arquivo está sendo aberto utilizando:

```text
file://
```

em vez de ser servido por HTTP.

Esse problema não significa necessariamente que os dados, marcadores ou funcionalidades do mapa estejam incorretos.

---

## ✅ Solução: servidor HTTP local

Caso o mapa-base não seja carregado corretamente, execute o HTML através de um servidor HTTP local.

Abra um terminal na pasta onde está o arquivo:

```bash
python -m http.server 8000
```

Depois abra:

```text
http://localhost:8000
```

Clique no arquivo:

```text
mapa_interativo_empresas.html
```

O endereço final será semelhante a:

```text
http://localhost:8000/mapa_interativo_empresas.html
```

em vez de:

```text
file:///.../mapa_interativo_empresas.html
```

### Passo a passo

1. Execute o pipeline;
2. Localize o arquivo `mapa_interativo_empresas.html`;
3. Abra um terminal nessa pasta;
4. Execute:

```bash
python -m http.server 8000
```

5. Abra o navegador;
6. Acesse:

```text
http://localhost:8000
```

7. Clique no arquivo HTML.

Para encerrar o servidor:

```text
Ctrl + C
```

---

## 🌐 Requisito de internet

O servidor local apenas disponibiliza o arquivo HTML no computador.

O mapa ainda depende de recursos externos para funcionar completamente, incluindo os mapas-base e dados geográficos utilizados pelo módulo espacial.

Portanto:

| Situação                     | Resultado                                              |
| ---------------------------- | ------------------------------------------------------ |
| Duplo clique → `file://`     | ⚠️ Pode ocorrer problema no carregamento dos mapas     |
| `python -m http.server 8000` | ✅ Forma recomendada                                    |
| `http://localhost:8000`      | ✅ HTML servido corretamente                            |
| Sem internet                 | ⚠️ Recursos externos e mapas-base não serão carregados |

> **Em caso de erro 403 no mapa-base, primeiro tente executar o arquivo HTML utilizando um servidor local com `python -m http.server 8000`. Não é necessário alterar o código apenas por causa desse erro.**

---

# ▶️ Execução completa

Depois de configurar o ambiente e colocar os arquivos da Receita Federal em `data/raw/2026-08/`, execute as etapas na seguinte ordem:

### 1. Gerar a base consolidada

```bash
python src/etl/1_1_gerar_base_empresas_rfb.py
```

### 2. Selecionar e classificar as empresas

```bash
python src/analysis/2_1_classificar_e_gerar_excel.py
```

### 3. Higienizar UF e CEP

```bash
python src/etl/2_2_corrigir_ufs_planilha.py
```

### 4. Gerar análise espacial, dashboard e mapa

```bash
python src/spatial/3_1_analise_espacial_empresas.py
```

Ao final, os principais resultados estarão em:

```text
outputs/
├── relatorios/
│   ├── relatorio_empresas.xlsx
│   └── relatorio_empresas_higienizado_completo.xlsx
│
└── resultados_espaciais/
    ├── estatisticas_polarizacao_cnaes.xlsx
    ├── dashboard_nacional_cnaes.png
    └── mapa_interativo_empresas.html
```

---

# 📌 Resumo do pipeline

| Etapa               | Script                             | Entrada principal | Saída principal                                |
| ------------------- | ---------------------------------- | ----------------- | ---------------------------------------------- |
| 1. ETL              | `1_1_gerar_base_empresas_rfb.py`   | ZIPs da RFB       | `base_engenharia_fisica.parquet`               |
| 2. Classificação    | `2_1_classificar_e_gerar_excel.py` | Parquet           | `relatorio_empresas.xlsx`                      |
| 3. Higienização     | `2_2_corrigir_ufs_planilha.py`     | Excel             | `relatorio_empresas_higienizado_completo.xlsx` |
| 4. Análise espacial | `3_1_analise_espacial_empresas.py` | Parquet/Excel     | Dashboard, estatísticas e mapa                 |

---

# 📚 Dados

Os dados empresariais utilizados neste projeto são provenientes dos **dados abertos da Receita Federal do Brasil**.

O projeto não distribui os arquivos brutos da Receita Federal no repositório. Eles devem ser obtidos separadamente e colocados no diretório:

```text
data/raw/
```

Os arquivos brutos e bases de grande volume devem permanecer fora do controle de versão, conforme as regras definidas no `.gitignore`.

---

# 🔬 Aplicações

A base produzida pelo projeto pode ser utilizada para investigar, entre outros aspectos:

* Distribuição espacial de empresas de base tecnológica;
* Concentração regional de atividades de P&D;
* Distribuição da indústria eletrônica e de semicondutores;
* Distribuição de empresas relacionadas a equipamentos eletromédicos;
* Distribuição de empresas relacionadas a equipamentos elétricos;
* Concentração empresarial por estado;
* Estrutura de porte das empresas;
* Distribuição por município;
* Comparação entre diferentes CNAEs;
* Identificação de regiões com maior concentração de empresas relacionadas à Engenharia Física e Hard Tech.

---

# 📄 Licença

Defina aqui a licença do projeto, caso aplicável.

Exemplo:

```text
MIT License
```

---

# 👤 Autor

**Airton de Franca Ferreira**

Projeto desenvolvido para análise de empresas relacionadas à **Engenharia Física, Hard Tech e setores tecnológicos associados**, utilizando dados públicos da Receita Federal do Brasil.
