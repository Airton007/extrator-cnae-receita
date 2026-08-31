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
