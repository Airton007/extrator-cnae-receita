"""
Pipeline de Análise e Mapeamento Espacial de Empresas por CNAE
Autor: Repositório GitHub
Descrição: Pipeline completo de ETL, análise de concentração econômica (CR4, HHI)
e geração de dashboard estático e mapa interativo Folium com legenda executiva.
"""

import os
import re
import time
import unicodedata
import duckdb
import folium
import geopandas as gpd
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from branca.element import MacroElement, Template
from folium.plugins import MarkerCluster
from matplotlib.colors import BoundaryNorm, ListedColormap


# ==============================================================================
# CONFIGURAÇÕES E MAPEAMENTOS DOS 4 CNAEs
# ==============================================================================

DIRETORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = os.path.abspath(
    os.path.join(DIRETORIO_SCRIPT, "..", "..")
)

# Arquivo Parquet gerado pelo pipeline de extração
ARQUIVO_PARQUET = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "base_engenharia_fisica.parquet"
)

# Arquivo Excel gerado pela etapa de higienização
ARQUIVO_EXCEL = os.path.join(
    BASE_DIR,
    "outputs",
    "relatorios",
    "relatorio_empresas_higienizado_completo.xlsx"
)

# Diretório dos resultados desta análise
PASTA_SAIDA = os.path.join(
    BASE_DIR,
    "outputs",
    "resultados_espaciais"
)

os.makedirs(PASTA_SAIDA, exist_ok=True)

MAPA_CNAES = {
    "7210000": "Pesquisa e desenvolvimento experimental em ciências físicas e naturais",
    "2660400": "Fabricação de aparelhos eletromédicos e equipamentos de irradiação",
    "2610800": "Fabricação de componentes eletrônicos e semicondutores",
    "2731700": "Fabricação de aparelhos para distribuição e controle de energia elétrica",
}

CNAES_DESTAQUE = list(MAPA_CNAES.keys())

CORES_CNAE_MARKER = {
    "7210000": "#0284C7",
    "2660400": "#16A34A",
    "2610800": "#EA580C",
    "2731700": "#9333EA",
}

POPULACAO_ESTADOS = {
    "SP": 44411238, "MG": 20538718, "RJ": 16054524, "BA": 14141626, "PR": 11444380,
    "RS": 10882965, "PE": 9058931,  "CE": 8794957,  "PA": 8121025,  "SC": 7610361,
    "MA": 6776699,  "GO": 7056495,  "PB": 3974687,  "ES": 3833712,  "AM": 3941613,
    "RN": 3302729,  "AL": 3127683,  "PI": 3271199,  "MT": 3658649,  "DF": 2817381,
    "MS": 2757013,  "SE": 2210004,  "RO": 1581196,  "TO": 1511460,  "AC": 830018,
    "AP": 733759,   "RR": 636707,
}

CENTROIDES_ESTADOS = {
    "SP": [-23.55, -46.63], "MG": [-19.92, -43.94], "RJ": [-22.90, -43.17],
    "BA": [-12.97, -38.51], "PR": [-25.42, -49.27], "RS": [-30.03, -51.23],
    "PE": [-8.05, -34.88],  "CE": [-3.71, -38.54],  "PA": [-1.45, -48.50],
    "SC": [-27.59, -48.54], "GO": [-16.68, -49.26], "DF": [-15.78, -47.93],
    "ES": [-20.31, -40.33], "PB": [-7.11, -34.86],  "AM": [-3.10, -60.02],
    "MT": [-15.60, -56.09], "RN": [-5.79, -35.20],  "AL": [-9.66, -35.73],
    "PI": [-5.09, -42.80],  "MA": [-2.53, -44.30],  "MS": [-20.44, -54.64],
    "SE": [-10.91, -37.07], "RO": [-8.76, -63.90],  "TO": [-10.18, -48.33],
    "AC": [-9.97, -67.81],  "AP": [0.03, -51.05],   "RR": [2.82, -60.67],
}


def normalizar_texto(texto: str) -> str:
    """Remove acentos, pontuação e espaços para casamento de chaves de municípios."""
    if pd.isna(texto):
        return ""
    norm = unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("ASCII")
    return re.sub(r"[^A-Z0-9]", "", norm.strip().upper())


# ==============================================================================
# 1. CARGA E HIGIENIZAÇÃO DOS DADOS (DUCKDB / EXCEL)
# ==============================================================================
def carregar_dados() -> pd.DataFrame:
    print("1/5. Carregando e limpando os dados de empresas...")
    if os.path.exists(ARQUIVO_PARQUET):
        con = duckdb.connect()
        df = con.execute(f"""
            SELECT 
                cnpj, razao_social, nome_fantasia, 
                COALESCE(porte, 'Não Informado') AS porte,
                REGEXP_REPLACE(cnae_fiscal_principal, '[^0-9]', '', 'g') AS cnae,
                UPPER(TRIM(uf)) AS uf, 
                UPPER(TRIM(cidade)) AS cidade,
                cep, endereco_completo, correio_eletronico
            FROM '{ARQUIVO_PARQUET}'
        """).df()
    elif os.path.exists(ARQUIVO_EXCEL):
        df = pd.read_excel(ARQUIVO_EXCEL)
        df["cnae"] = df["cnae_fiscal_principal"].astype(str).str.replace(r"\D", "", regex=True)
        df["uf"] = df["uf"].astype(str).str.strip().str.upper()
        df["cidade"] = df["cidade"].astype(str).str.strip().str.upper()
        if "porte" not in df.columns:
            df["porte"] = "Não Informado"
        else:
            df["porte"] = df["porte"].fillna("Não Informado")
    else:
        raise FileNotFoundError(f"Nenhum arquivo '{ARQUIVO_PARQUET}' ou '{ARQUIVO_EXCEL}' encontrado.")

    df_filtrado = df[df["cnae"].isin(MAPA_CNAES.keys()) & df["uf"].isin(POPULACAO_ESTADOS.keys())].copy()
    print(f"-> {len(df_filtrado)} empresas ativas carregadas em {df_filtrado['cidade'].nunique()} municípios.")
    return df_filtrado


# ==============================================================================
# 2. OBTENÇÃO DAS MALHAS GEOGRÁFICAS DOS ESTADOS
# ==============================================================================
def carregar_geometrias_estados() -> gpd.GeoDataFrame:
    print("2/5. Obtendo malha geográfica dos Estados (GeoJSON)...")
    url_geo = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
    gdf = gpd.read_file(url_geo)

    if "sigla" in gdf.columns:
        gdf["uf"] = gdf["sigla"].str.upper()
    elif "id" in gdf.columns:
        gdf["uf"] = gdf["id"].str.upper()
    else:
        gdf["uf"] = gdf["name"].str.upper()
    return gdf


# ==============================================================================
# 3. CÁLCULO DOS ÍNDICES ESPACIAIS E DE POLARIZAÇÃO (CR4, HHI)
# ==============================================================================
def calcular_polarizacao(df: pd.DataFrame) -> pd.DataFrame:
    print("3/5. Calculando estatísticas e indicadores de polarização econômica (CR4, HHI)...")
    linhas_stats = []

    for cnae_cod, cnae_desc in MAPA_CNAES.items():
        sub = df[df["cnae"] == cnae_cod]
        total = len(sub)
        if total > 0:
            por_uf = sub["uf"].value_counts()
            part_uf = por_uf / total

            cr4 = part_uf.head(4).sum() * 100
            hhi = (part_uf ** 2).sum()

            linhas_stats.append({
                "cnae": cnae_cod,
                "descricao": cnae_desc,
                "total_empresas": total,
                "top1_estado": por_uf.index[0],
                "participacao_top1_%": round(part_uf.iloc[0] * 100, 2),
                "cr4_%": round(cr4, 2),
                "hhi": round(hhi, 4),
            })

    df_stats = pd.DataFrame(linhas_stats).sort_values("total_empresas", ascending=False)
    caminho_stats = os.path.join(PASTA_SAIDA, "estatisticas_polarizacao_cnaes.xlsx")
    df_stats.to_excel(caminho_stats, index=False)
    print(f"-> Estatísticas exportadas com sucesso: '{caminho_stats}'")
    return df_stats


# ==============================================================================
# 4. GERAÇÃO DO DASHBOARD VISUAL ESTÁTICO (PNG - 300 DPI)
# ==============================================================================
def gerar_dashboard(df: pd.DataFrame, gdf_estados: gpd.GeoDataFrame, df_stats: pd.DataFrame):
    print("4/5. Renderizando Dashboard Nacional Consolidado em PNG...")
    df_dash = df[df["cnae"].isin(CNAES_DESTAQUE)].copy()
    contagem_uf = df_dash["uf"].value_counts().reset_index()
    contagem_uf.columns = ["uf", "total"]

    tabela_cnae_uf = pd.crosstab(df_dash["uf"], df_dash["cnae"])
    for c in CNAES_DESTAQUE:
        if c not in tabela_cnae_uf.columns:
            tabela_cnae_uf[c] = 0
    tabela_cnae_uf["Total"] = tabela_cnae_uf.sum(axis=1)
    tabela_cnae_uf = tabela_cnae_uf.sort_values("Total", ascending=False).head(10).reset_index()

    gdf_mapa = gdf_estados.merge(contagem_uf, on="uf", how="left").fillna({"total": 0})

    fig = plt.figure(figsize=(19, 12), facecolor="#F8FAFC")
    gs = gridspec.GridSpec(3, 3, width_ratios=[1.1, 2.2, 1.4], height_ratios=[1, 1, 0.4], wspace=0.25, hspace=0.3)

    # Título Principal
    fig.text(0.5, 0.95, "DISTRIBUIÇÃO DE EMPRESAS NO BRASIL POR CNAE", fontsize=22, fontweight="bold", color="#0F172A", ha="center")
    fig.text(0.5, 0.925, "Polarização / Distribuição Geográfica das Empresas de Hard Tech", fontsize=13, color="#64748B", ha="center")

    # Painel Lateral Esquerdo (Metadados e Resumo)
    ax_lateral = fig.add_subplot(gs[0:2, 0])
    ax_lateral.axis("off")
    bbox_filtro = dict(boxstyle="round,pad=1", facecolor="white", edgecolor="#E2E8F0", linewidth=1.5)
    texto_filtro = "FILTRO DE CNAEs\n" + "─" * 30 + "\n\n"
    cores_cnae = ["#0284C7", "#16A34A", "#EA580C", "#9333EA"]
    for idx, c in enumerate(CNAES_DESTAQUE):
        texto_filtro += f"■ {c} - {MAPA_CNAES[c][:30]}...\n\n"

    texto_resumo = (
        f"\nRESUMO GERAL\n" + "─" * 30 + "\n\n"
        f"TOTAL DE EMPRESAS:  {len(df_dash):,}\n\n"
        f"ESTADOS COBERTOS:   {df_dash['uf'].nunique()} / 27\n\n"
        f"CIDADES PRESENTES:  {df_dash['cidade'].nunique()}\n\n"
        f"DATA DA ANÁLISE:    {time.strftime('%d/%m/%Y %H:%M')}"
    )
    ax_lateral.text(0.05, 0.95, texto_filtro + texto_resumo, transform=ax_lateral.transAxes,
                    fontsize=10, verticalalignment="top", fontfamily="sans-serif", color="#1E293B", bbox=bbox_filtro)

    # Painel Central (Mapa Coroplético do Brasil)
    ax_mapa = fig.add_subplot(gs[0:2, 1])
    ax_mapa.set_title("Quantidade de Empresas por Estado", fontsize=13, fontweight="bold", pad=15, color="#1E293B")
    faixas = [0, 50, 100, 500, 1000, 2000, 10000]
    cores = ["#DCFCE7", "#86EFAC", "#5EEAD4", "#38BDF8", "#0284C7", "#1E3A8A"]
    cmap = ListedColormap(cores)
    norm = BoundaryNorm(faixas, cmap.N)

    gdf_mapa.plot(column="total", cmap=cmap, norm=norm, linewidth=0.8, edgecolor="#FFFFFF", ax=ax_mapa)
    for _, row in gdf_mapa.iterrows():
        if row.geometry is not None:
            pt = row.geometry.representative_point()
            val = int(row["total"])
            if val > 0:
                ax_mapa.annotate(f"{row['uf']}\n{val}", xy=(pt.x, pt.y), xytext=(0, 0),
                                 textcoords="offset points", ha="center", va="center",
                                 fontsize=8, fontweight="bold", color="#0F172A")
    ax_mapa.axis("off")

    # Painel Superior Direito (Gráfico de Barras por CNAE)
    ax_bar = fig.add_subplot(gs[0, 2])
    ax_bar.set_facecolor("#F8FAFC")
    contagem_cnae = df_dash["cnae"].value_counts().reindex(CNAES_DESTAQUE, fill_value=0)
    rotulos_cnae = [f"{c} - {MAPA_CNAES[c][:20]}..." for c in CNAES_DESTAQUE]
    porcentagens = (contagem_cnae / max(contagem_cnae.sum(), 1)) * 100

    y_pos = np.arange(len(CNAES_DESTAQUE))
    ax_bar.barh(y_pos, contagem_cnae.values, color=cores_cnae, height=0.55, edgecolor="none")
    ax_bar.set_yticks(y_pos)
    ax_bar.set_yticklabels(rotulos_cnae, fontsize=8)
    ax_bar.invert_yaxis()
    ax_bar.set_title("TOTAL DE EMPRESAS POR CNAE", fontsize=11, fontweight="bold", color="#1E293B")
    for s in ["top", "right"]:
        ax_bar.spines[s].set_visible(False)
    ax_bar.spines["left"].set_color("#CBD5E1")
    ax_bar.spines["bottom"].set_color("#CBD5E1")

    for i, v in enumerate(contagem_cnae.values):
        ax_bar.text(v + 30, i, f"{v:,} ({porcentagens.iloc[i]:.1f}%)", va="center", fontsize=8, fontweight="bold", color="#334155")

    # Painel Inferior Direito (Tabela Top 10 Estados)
    ax_tab = fig.add_subplot(gs[1, 2])
    ax_tab.axis("off")
    ax_tab.set_title("DETALHAMENTO POR ESTADO (TOP 10)", fontsize=11, fontweight="bold", pad=10, color="#1E293B")
    colunas_tabela = ["Estado"] + CNAES_DESTAQUE + ["Total"]
    dados_tabela = tabela_cnae_uf[["uf"] + CNAES_DESTAQUE + ["Total"]].values
    tabela = ax_tab.table(cellText=dados_tabela, colLabels=colunas_tabela, loc="center", cellLoc="center")
    tabela.auto_set_font_size(False)
    tabela.set_fontsize(7.5)
    tabela.scale(1, 1.25)
    for (row, col), cell in tabela.get_celld().items():
        if row == 0:
            cell.set_facecolor("#0F172A")
            cell.set_text_props(color="white", weight="bold")
        elif row % 2 == 0:
            cell.set_facecolor("#F1F5F9")

    # Rodapé Analítico
    ax_rodape = fig.add_subplot(gs[2, :])
    ax_rodape.axis("off")
    top1 = df_stats.iloc[0]
    obs_texto = (
        f"Principais Observações Analíticas:\n"
        f"• Concentração Espacial Top-1: O estado de {top1['top1_estado']} lidera com {top1['participacao_top1_%']}% no CNAE {top1['cnae']}.\n"
        f"• Índice CR4 Consolidado: Os 4 maiores estados concentram em média {df_stats['cr4_%'].mean():.1f}% das empresas analisadas.\n"
        f"• Total Processado: {len(df):,} empresas ativas distribuídas nacionalmente."
    )
    ax_rodape.text(0.02, 0.5, obs_texto, fontsize=9.5, color="#334155", va="center",
                    bbox=dict(boxstyle="round,pad=0.8", facecolor="#FFFFFF", edgecolor="#CBD5E1"))

    caminho_dashboard = os.path.join(PASTA_SAIDA, "dashboard_nacional_cnaes.png")
    plt.savefig(caminho_dashboard, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"-> Dashboard exportado com sucesso: '{caminho_dashboard}'")


# ==============================================================================
# 5. GERAÇÃO DO MAPA INTERATIVO FOLIUM (HTML + LEGENDA EXECUTIVA)
# ==============================================================================
def gerar_mapa_interativo(df: pd.DataFrame):
    print("5/5. Construindo Mapa Interativo em HTML com Legenda Executiva Expandida...")
    df_dash = df[df["cnae"].isin(CNAES_DESTAQUE)].copy()

    url_mun = "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/csv/municipios.csv"
    mapa_coords = {}
    try:
        df_coords_mun = pd.read_csv(url_mun)
        df_coords_mun["chave"] = df_coords_mun["nome"].apply(normalizar_texto)
        for _, r in df_coords_mun.iterrows():
            mapa_coords[r["chave"]] = (r["latitude"], r["longitude"])
    except Exception as e:
        print(f"Aviso ao obter base de municípios ({e}). Usando centróides estaduais como fallback.")

    mapa_interativo = folium.Map(location=[-15.78, -47.93], zoom_start=5, tiles="OpenStreetMap")

    folium.TileLayer(
        "CartoDB Positron",
        name="Mapa claro",
        control=True
    ).add_to(mapa_interativo)

    folium.TileLayer(
        "CartoDB Voyager",
        name="Mapa detalhado",
        control=True
    ).add_to(mapa_interativo)


    # Métricas para a legenda executiva
    totais_por_cnae = df_dash["cnae"].value_counts().to_dict()
    total_geral = len(df_dash)
    total_cidades = df_dash["cidade"].nunique()
    total_ufs = df_dash["uf"].nunique()
    top_estados = df_dash["uf"].value_counts().head(3)
    top_est_str = ", ".join([f"{uf} ({qtd})" for uf, qtd in top_estados.items()])

    contagem_porte = df_dash["porte"].astype(str).value_counts()
    qtd_me = contagem_porte.get("Micro Empresa (ME)", 0) + contagem_porte.get("01", 0) + contagem_porte.get("ME", 0)
    qtd_epp = contagem_porte.get("Empresa de Pequeno Porte (EPP)", 0) + contagem_porte.get("03", 0) + contagem_porte.get("EPP", 0)
    qtd_demais = len(df_dash) - (qtd_me + qtd_epp)

    # Injeção das camadas por CNAE com Clustering
    for cnae_cod in CNAES_DESTAQUE:
        sub_cnae = df_dash[df_dash["cnae"] == cnae_cod]
        nome_camada = f"CNAE {cnae_cod} ({len(sub_cnae):,})"
        camada = folium.FeatureGroup(name=nome_camada)
        cluster = MarkerCluster().add_to(camada)

        for (cidade_nome, uf_ref), grupo in sub_cnae.groupby(["cidade", "uf"]):
            qtd_empresas = len(grupo)
            cards_html = ""
            for _, emp in grupo.iterrows():
                nome_exibir = emp.get("nome_fantasia", "")
                if not isinstance(nome_exibir, str) or not nome_exibir.strip():
                    nome_exibir = emp.get("razao_social", "Razão Social não informada")

                cnpj_raw = str(emp.get("cnpj", ""))
                cnpj_fmt = f"{cnpj_raw[:2]}.{cnpj_raw[2:5]}.{cnpj_raw[5:8]}/{cnpj_raw[8:12]}-{cnpj_raw[12:]}" if len(cnpj_raw) == 14 else cnpj_raw

                email = emp.get("correio_eletronico", "")
                email_html = f"<b>E-mail:</b> {email}<br>" if isinstance(email, str) and email.strip() else ""
                end = emp.get("endereco_completo", "")
                end_html = f"<b>Endereço:</b> {end}<br>" if isinstance(end, str) and end.strip() else ""

                cards_html += f"""
                <div style="background:#F8FAFC; border-left:4px solid {CORES_CNAE_MARKER.get(cnae_cod, '#0284C7')}; padding:8px; margin-bottom:8px; border-radius:4px; font-size:11px;">
                    <b style="font-size:12px; color:#0F172A;">{nome_exibir}</b><br>
                    <b>Razão Social:</b> {emp.get('razao_social', '')}<br>
                    <b>CNPJ:</b> {cnpj_fmt}<br>
                    <b>Porte:</b> {emp.get('porte', 'Não Informado')}<br>
                    {email_html}
                    {end_html}
                </div>
                """

            popup_html = f"""
            <div style="font-family: Arial, sans-serif; width:310px; max-height:260px; overflow-y:auto; padding-right:5px;">
                <div style="border-bottom:2px solid #E2E8F0; padding-bottom:6px; margin-bottom:8px;">
                    <h4 style="margin:0; color:#0F172A;">{cidade_nome} - {uf_ref}</h4>
                    <span style="font-size:11px; color:#64748B;">CNAE {cnae_cod} | Total: <b>{qtd_empresas} empresa(s)</b></span>
                </div>
                {cards_html}
            </div>
            """

            chave_busca = normalizar_texto(cidade_nome)
            lat, lon = mapa_coords.get(chave_busca, CENTROIDES_ESTADOS.get(uf_ref, [-15.78, -47.93]))
            cor = CORES_CNAE_MARKER.get(cnae_cod, "#0284C7")

            folium.CircleMarker(
                location=[lat, lon],
                radius=min(max(qtd_empresas * 1.5, 6), 22),
                popup=folium.Popup(popup_html, max_width=340),
                tooltip=f"{cidade_nome}/{uf_ref} — {qtd_empresas} empresa(s)",
                color=cor,
                fill=True,
                fill_color=cor,
                fill_opacity=0.75,
            ).add_to(cluster)

        camada.add_to(mapa_interativo)

    folium.LayerControl(collapsed=False).add_to(mapa_interativo)

    # Injeção do Painel Flutuante de Legenda
    template_legenda_completa = f"""
    {{% macro html(this, kwargs) %}}
    <div id="painel-legenda" style="
        position: fixed; 
        bottom: 25px; 
        left: 25px; 
        width: 330px;
        max-height: 85vh;
        overflow-y: auto;
        background-color: rgba(255, 255, 255, 0.96);
        border: 1px solid #CBD5E1;
        border-radius: 10px;
        z-index: 9999;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        font-size: 11px;
        color: #1E293B;
        padding: 14px 16px;
    ">
        <!-- Cabeçalho -->
        <div style="border-bottom: 2px solid #E2E8F0; padding-bottom: 8px; margin-bottom: 10px;">
            <div style="font-size: 14px; font-weight: 800; color: #0F172A; letter-spacing: -0.3px;">
                Mapeamento de Empresas
            </div>
            <div style="font-size: 11px; color: #64748B;">Engenharia Física & Hard Tech Brasil</div>
        </div>

        <!-- 1. Métricas Gerais (KPIs) -->
        <div style="background: #F1F5F9; border-radius: 6px; padding: 8px 10px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                <span style="color: #475569;">Total de Empresas:</span>
                <b style="color: #0F172A;">{total_geral:,}</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                <span style="color: #475569;">Municípios Atendidos:</span>
                <b>{total_cidades}</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                <span style="color: #475569;">Estados Cobertos:</span>
                <b>{total_ufs} / 27</b>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #475569;">Top 3 Estados:</span>
                <b style="color: #0284C7;">{top_est_str}</b>
            </div>
        </div>

        <!-- 2. Detalhamento por CNAE -->
        <div style="font-weight: 700; color: #334155; margin-bottom: 6px; text-transform: uppercase; font-size: 10px; letter-spacing: 0.5px;">
            Distribuição por Setor (CNAE):
        </div>
        
        <div style="margin-bottom: 6px; padding: 4px 6px; border-radius: 4px; background: #F8FAFC;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center;">
                    <span style="height: 10px; width: 10px; background-color: #0284C7; border-radius: 50%; display: inline-block; margin-right: 6px;"></span>
                    <b>7210000 - P&D Experimental</b>
                </div>
                <span><b>{totais_por_cnae.get('7210000', 0):,}</b> ({totais_por_cnae.get('7210000', 0)/max(total_geral,1)*100:.1f}%)</span>
            </div>
        </div>

        <div style="margin-bottom: 6px; padding: 4px 6px; border-radius: 4px; background: #F8FAFC;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center;">
                    <span style="height: 10px; width: 10px; background-color: #16A34A; border-radius: 50%; display: inline-block; margin-right: 6px;"></span>
                    <b>2660400 - Eletromédicos/Radiação</b>
                </div>
                <span><b>{totais_por_cnae.get('2660400', 0):,}</b> ({totais_por_cnae.get('2660400', 0)/max(total_geral,1)*100:.1f}%)</span>
            </div>
        </div>

        <div style="margin-bottom: 6px; padding: 4px 6px; border-radius: 4px; background: #F8FAFC;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center;">
                    <span style="height: 10px; width: 10px; background-color: #EA580C; border-radius: 50%; display: inline-block; margin-right: 6px;"></span>
                    <b>2610800 - Semicondutores/Chips</b>
                </div>
                <span><b>{totais_por_cnae.get('2610800', 0):,}</b> ({totais_por_cnae.get('2610800', 0)/max(total_geral,1)*100:.1f}%)</span>
            </div>
        </div>

        <div style="margin-bottom: 10px; padding: 4px 6px; border-radius: 4px; background: #F8FAFC;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center;">
                    <span style="height: 10px; width: 10px; background-color: #9333EA; border-radius: 50%; display: inline-block; margin-right: 6px;"></span>
                    <b>2731700 - Energia Elétrica</b>
                </div>
                <span><b>{totais_por_cnae.get('2731700', 0):,}</b> ({totais_por_cnae.get('2731700', 0)/max(total_geral,1)*100:.1f}%)</span>
            </div>
        </div>

        <!-- 3. Porte Empresarial -->
        <div style="font-weight: 700; color: #334155; margin-bottom: 4px; text-transform: uppercase; font-size: 10px; letter-spacing: 0.5px;">
            Estrutura de Porte:
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 10.5px; color: #475569; margin-bottom: 10px; padding: 0 4px;">
            <span>ME: <b>{qtd_me:,}</b></span>
            <span>EPP: <b>{qtd_epp:,}</b></span>
            <span>Demais: <b>{qtd_demais:,}</b></span>
        </div>

        <!-- 4. Escala de Tamanho dos Círculos -->
        <div style="border-top: 1px solid #E2E8F0; padding-top: 8px;">
            <div style="font-weight: 700; color: #334155; margin-bottom: 6px; font-size: 10px; text-transform: uppercase;">
                Concentração no Município:
            </div>
            <div style="display: flex; align-items: flex-end; justify-content: space-around; text-align: center;">
                <div>
                    <div style="height: 8px; width: 8px; background-color: #94A3B8; border-radius: 50%; margin: 0 auto 3px auto;"></div>
                    <span style="font-size: 9.5px; color: #64748B;">1 - 5 emp.</span>
                </div>
                <div>
                    <div style="height: 14px; width: 14px; background-color: #94A3B8; border-radius: 50%; margin: 0 auto 3px auto;"></div>
                    <span style="font-size: 9.5px; color: #64748B;">6 - 25 emp.</span>
                </div>
                <div>
                    <div style="height: 20px; width: 20px; background-color: #94A3B8; border-radius: 50%; margin: 0 auto 3px auto;"></div>
                    <span style="font-size: 9.5px; color: #64748B;">25+ emp.</span>
                </div>
            </div>
        </div>
    </div>
    {{% endmacro %}}
    """

    macro = MacroElement()
    macro._template = Template(template_legenda_completa)
    mapa_interativo.get_root().add_child(macro)

    caminho_mapa_html = os.path.join(PASTA_SAIDA, "mapa_interativo_empresas.html")
    mapa_interativo.save(caminho_mapa_html)
    print(f"-> Mapa interativo com legenda executiva exportado em: '{caminho_mapa_html}'")


# ==============================================================================
# BLOCO DE EXECUÇÃO PRINCIPAL
# ==============================================================================
if __name__ == "__main__":
    df_empresas = carregar_dados()
    gdf_estados = carregar_geometrias_estados()
    df_indicadores = calcular_polarizacao(df_empresas)
    gerar_dashboard(df_empresas, gdf_estados, df_indicadores)
    gerar_mapa_interativo(df_empresas)

    print("\n" + "=" * 60)
    print("PIPELINE ESPACIAL CONCLUÍDO COM SUCESSO!")
    print(f"Resultados gravados no diretório: '{PASTA_SAIDA}/'")
    print("=" * 60)