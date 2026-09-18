import os
import re
import json
import time
import unicodedata
import requests
import duckdb
import pandas as pd
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import ListedColormap, BoundaryNorm
import folium
from folium.plugins import MarkerCluster
from branca.element import Template, MacroElement

# ==============================================================================
# CONFIGURAÇÕES E MAPEAMENTO RESTRITO AOS 4 CNAEs
# ==============================================================================
ARQUIVO_PARQUET = "base_engenharia_fisica.parquet"
ARQUIVO_EXCEL = "relatorio_empresas_higienizado_completo.xlsx"
PASTA_SAIDA = "resultados_espaciais"
os.makedirs(PASTA_SAIDA, exist_ok=True)

MAPA_CNAES = {
    "7210000": "Pesquisa e desenvolvimento experimental em ciências físicas e naturais",
    "2660400": "Fabricação de aparelhos eletromédicos e equipamentos de irradiação",
    "2610800": "Fabricação de componentes eletrônicos e semicondutores",
    "2731700": "Fabricação de aparelhos para distribuição e controle de energia elétrica"
}

cnaes_destaque = list(MAPA_CNAES.keys())

POPULACAO_ESTADOS = {
    "SP": 44411238, "MG": 20538718, "RJ": 16054524, "BA": 14141626, "PR": 11444380,
    "RS": 10882965, "PE": 9058931,  "CE": 8794957,  "PA": 8121025,  "SC": 7610361,
    "MA": 6776699,  "GO": 7056495,  "PB": 3974687,  "ES": 3833712,  "AM": 3941613,
    "RN": 3302729,  "AL": 3127683,  "PI": 3271199,  "MT": 3658649,  "DF": 2817381,
    "MS": 2757013,  "SE": 2210004,  "RO": 1581196,  "TO": 1511460,  "AC": 830018,
    "AP": 733759,   "RR": 636707
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
    "AC": [-9.97, -67.81],  "AP": [0.03, -51.05],   "RR": [2.82, -60.67]
}

# ==============================================================================
# 1. CARGA DOS DADOS (DUCKDB / PARQUET / EXCEL)
# ==============================================================================
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
else:
    raise FileNotFoundError("Nenhum arquivo Parquet ou Excel encontrado.")

df = df[df["cnae"].isin(MAPA_CNAES.keys()) & df["uf"].isin(POPULACAO_ESTADOS.keys())].copy()
print(f"-> {len(df)} empresas ativas carregadas em {df['cidade'].nunique()} municípios.")

# ==============================================================================
# 2. CARGA DAS MALHAS GEOGRÁFICAS DO BRASIL
# ==============================================================================
print("2/5. Obtendo malha geográfica dos Estados...")
URL_GEO_ESTADOS = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
gdf_estados = gpd.read_file(URL_GEO_ESTADOS)

if "sigla" in gdf_estados.columns:
    gdf_estados["uf"] = gdf_estados["sigla"].str.upper()
elif "id" in gdf_estados.columns:
    gdf_estados["uf"] = gdf_estados["id"].str.upper()
else:
    gdf_estados["uf"] = gdf_estados["name"].str.upper()

# ==============================================================================
# 3. CÁLCULO DOS ÍNDICES ESPACIAIS E DE POLARIZAÇÃO (CR4, HHI)
# ==============================================================================
print("3/5. Calculando estatísticas e indicadores de polarização...")

def calcular_indicadores_cnae(df_subset):
    total = len(df_subset)
    if total == 0:
        return {}
    
    por_uf = df_subset["uf"].value_counts()
    part_uf = (por_uf / total)
    
    cr4 = part_uf.head(4).sum() * 100
    hhi = (part_uf ** 2).sum()
    
    top1_uf = por_uf.index[0]
    top1_part = part_uf.iloc[0] * 100
    
    return {
        "total": total,
        "top1_uf": top1_uf,
        "top1_part": top1_part,
        "cr4": cr4,
        "hhi": hhi,
        "distribuicao_uf": por_uf
    }

linhas_stats = []
for cnae_cod, cnae_desc in MAPA_CNAES.items():
    sub = df[df["cnae"] == cnae_cod]
    if len(sub) > 0:
        st = calcular_indicadores_cnae(sub)
        linhas_stats.append({
            "cnae": cnae_cod,
            "descricao": cnae_desc,
            "total_empresas": st["total"],
            "top1_estado": st["top1_uf"],
            "participacao_top1_%": round(st["top1_part"], 2),
            "cr4_%": round(st["cr4"], 2),
            "hhi": round(st["hhi"], 4)
        })

df_stats = pd.DataFrame(linhas_stats).sort_values("total_empresas", ascending=False)
df_stats.to_excel(os.path.join(PASTA_SAIDA, "estatisticas_polarizacao_cnaes.xlsx"), index=False)

# ==============================================================================
# 4. GERAÇÃO DO DASHBOARD VISUAL (ESTÁTICO EM PNG)
# ==============================================================================
print("4/5. Renderizando Dashboard Nacional Consolidado...")

df_dash = df[df["cnae"].isin(cnaes_destaque)].copy()
contagem_uf = df_dash["uf"].value_counts().reset_index()
contagem_uf.columns = ["uf", "total"]

tabela_cnae_uf = pd.crosstab(df_dash["uf"], df_dash["cnae"])
for c in cnaes_destaque:
    if c not in tabela_cnae_uf.columns:
        tabela_cnae_uf[c] = 0
tabela_cnae_uf["Total"] = tabela_cnae_uf.sum(axis=1)
tabela_cnae_uf = tabela_cnae_uf.sort_values("Total", ascending=False).head(10).reset_index()

gdf_mapa = gdf_estados.merge(contagem_uf, on="uf", how="left").fillna({"total": 0})

fig = plt.figure(figsize=(19, 12), facecolor="#F8FAFC")
gs = gridspec.GridSpec(3, 3, width_ratios=[1.1, 2.2, 1.4], height_ratios=[1, 1, 0.4], wspace=0.25, hspace=0.3)

# Cabeçalho
fig.text(0.5, 0.95, "DISTRIBUIÇÃO DE EMPRESAS NO BRASIL POR CNAE", fontsize=22, fontweight="bold", color="#0F172A", ha="center")
fig.text(0.5, 0.925, "Polarização / Distribuição Geográfica das Empresas", fontsize=13, color="#64748B", ha="center")

# Painel Lateral Esquerdo
ax_lateral = fig.add_subplot(gs[0:2, 0])
ax_lateral.axis("off")

bbox_filtro = dict(boxstyle="round,pad=1", facecolor="white", edgecolor="#E2E8F0", linewidth=1.5)
texto_filtro = "FILTRO DE CNAEs\n" + "─"*30 + "\n\n"
cores_cnae = ["#0284C7", "#16A34A", "#EA580C", "#9333EA"]
for idx, c in enumerate(cnaes_destaque):
    texto_filtro += f"■ {c} - {MAPA_CNAES[c][:30]}...\n\n"

texto_resumo = (
    f"\nRESUMO GERAL\n" + "─"*30 + "\n\n"
    f"TOTAL DE EMPRESAS:  {len(df_dash):,}\n\n"
    f"ESTADOS COBERTOS:   {df_dash['uf'].nunique()} / 27\n\n"
    f"CIDADES PRESENTES:  {df_dash['cidade'].nunique()}\n\n"
    f"DATA DA ANÁLISE:    {time.strftime('%d/%m/%Y %H:%M')}"
)
ax_lateral.text(0.05, 0.95, texto_filtro + texto_resumo, transform=ax_lateral.transAxes,
               fontsize=10, verticalalignment="top", fontfamily="sans-serif", color="#1E293B",
               bbox=bbox_filtro)

# Painel Central (Mapa)
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

# Painel Superior Direito (Barras)
ax_bar = fig.add_subplot(gs[0, 2])
ax_bar.set_facecolor="#F8FAFC"
contagem_cnae = df_dash["cnae"].value_counts().reindex(cnaes_destaque, fill_value=0)
rotulos_cnae = [f"{c} - {MAPA_CNAES[c][:20]}..." for c in cnaes_destaque]
porcentagens = (contagem_cnae / max(contagem_cnae.sum(), 1)) * 100

y_pos = np.arange(len(cnaes_destaque))
ax_bar.barh(y_pos, contagem_cnae.values, color=cores_cnae, height=0.55, edgecolor="none")
ax_bar.set_yticks(y_pos)
ax_bar.set_yticklabels(rotulos_cnae, fontsize=8)
ax_bar.invert_yaxis()
ax_bar.set_title("TOTAL DE EMPRESAS POR CNAE", fontsize=11, fontweight="bold", color="#1E293B")
ax_bar.spines['top'].set_visible(False)
ax_bar.spines['right'].set_visible(False)
ax_bar.spines['left'].set_color('#CBD5E1')
ax_bar.spines['bottom'].set_color('#CBD5E1')

for i, v in enumerate(contagem_cnae.values):
    ax_bar.text(v + 30, i, f"{v:,} ({porcentagens.iloc[i]:.1f}%)", va='center', fontsize=8, fontweight='bold', color="#334155")

# Painel Inferior Direito (Tabela)
ax_tab = fig.add_subplot(gs[1, 2])
ax_tab.axis("off")
ax_tab.set_title("DETALHAMENTO POR ESTADO (TOP 10)", fontsize=11, fontweight="bold", pad=10, color="#1E293B")

colunas_tabela = ["Estado"] + cnaes_destaque + ["Total"]
dados_tabela = tabela_cnae_uf[["uf"] + cnaes_destaque + ["Total"]].values

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

# Rodapé
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
# 5. GERAÇÃO DO MAPA INTERATIVO (OPENSTREETMAP + POPUPS + LEGENDA)
# ==============================================================================
print("5/5. Construindo Mapa Interativo em HTML com OpenStreetMap, Popups e Legenda...")

URL_MUNICIPIOS_GEO = "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/csv/municipios.csv"
mapa_coords = {}
try:
    df_coords_mun = pd.read_csv(URL_MUNICIPIOS_GEO)
    def limpar_chave(t):
        if pd.isna(t): return ""
        n = unicodedata.normalize('NFKD', str(t)).encode('ASCII', 'ignore').decode('ASCII')
        return re.sub(r'[^A-Z0-9]', '', n.strip().upper())

    df_coords_mun["chave"] = df_coords_mun["nome"].apply(limpar_chave)
    for _, r in df_coords_mun.iterrows():
        mapa_coords[r["chave"]] = (r["latitude"], r["longitude"])
except Exception:
    pass

mapa_interativo = folium.Map(
    location=[-15.78, -47.93],
    zoom_start=5,
    tiles="OpenStreetMap"
)

CORES_CNAE_MARKER = {
    "7210000": "#0284C7",
    "2660400": "#16A34A",
    "2610800": "#EA580C",
    "2731700": "#9333EA"
}

for cnae_cod in cnaes_destaque:
    sub_cnae = df[df["cnae"] == cnae_cod]
    nome_camada = f"CNAE {cnae_cod} - {MAPA_CNAES.get(cnae_cod, '')[:28]}"
    camada = folium.FeatureGroup(name=nome_camada)
    cluster = MarkerCluster().add_to(camada)
    
    for (cidade_nome, uf_ref), grupo in sub_cnae.groupby(["cidade", "uf"]):
        qtd_empresas = len(grupo)
        
        cards_html = ""
        for _, emp in grupo.iterrows():
            nome_exibir = emp.get("nome_fantasia", "")
            if not isinstance(nome_exibir, str) or not nome_exibir.strip():
                nome_exibir = emp.get("razao_social", "Razão Social não informada")
                
            cnpj_fmt = str(emp.get("cnpj", ""))
            if len(cnpj_fmt) == 14:
                cnpj_fmt = f"{cnpj_fmt[:2]}.{cnpj_fmt[2:5]}.{cnpj_fmt[5:8]}/{cnpj_fmt[8:12]}-{cnpj_fmt[12:]}"
                
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
        <div style="font-family: Arial, sans-serif; width:300px; max-height:260px; overflow-y:auto; padding-right:5px;">
            <div style="border-bottom:2px solid #E2E8F0; padding-bottom:6px; margin-bottom:8px;">
                <h4 style="margin:0; color:#0F172A;">{cidade_nome} - {uf_ref}</h4>
                <span style="font-size:11px; color:#64748B;">CNAE {cnae_cod} | Total: <b>{qtd_empresas} empresa(s)</b></span>
            </div>
            {cards_html}
        </div>
        """

        chave_busca = re.sub(r'[^A-Z0-9]', '', unicodedata.normalize('NFKD', str(cidade_nome)).encode('ASCII', 'ignore').decode('ASCII'))
        lat, lon = mapa_coords.get(chave_busca, CENTROIDES_ESTADOS.get(uf_ref, [-15.78, -47.93]))
        cor = CORES_CNAE_MARKER.get(cnae_cod, "#0284C7")

        folium.CircleMarker(
            location=[lat, lon],
            radius=min(max(qtd_empresas * 1.5, 6), 22),
            popup=folium.Popup(popup_html, max_width=330),
            tooltip=f"{cidade_nome}/{uf_ref} — {qtd_empresas} empresa(s)",
            color=cor,
            fill=True,
            fill_color=cor,
            fill_opacity=0.75
        ).add_to(cluster)

    camada.add_to(mapa_interativo)

folium.LayerControl(collapsed=False).add_to(mapa_interativo)

# Adiciona Legenda Flutuante
template_legenda = """
{% macro html(this, kwargs) %}
<div style="
    position: fixed; 
    bottom: 30px; 
    left: 30px; 
    width: 290px;
    background-color: rgba(255, 255, 255, 0.95);
    border: 2px solid #CBD5E1;
    border-radius: 8px;
    z-index: 9999;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    font-family: Arial, sans-serif;
    font-size: 11px;
    color: #1E293B;
    padding: 12px 14px;
">
    <div style="font-size: 13px; font-weight: bold; border-bottom: 2px solid #E2E8F0; padding-bottom: 6px; margin-bottom: 8px;">
        Legenda do Mapa Interativo
    </div>
    
    <div style="font-weight: bold; margin-bottom: 6px; color: #475569;">Área de Atuação (CNAE):</div>
    <div style="margin-bottom: 4px; display: flex; align-items: center;">
        <span style="height: 12px; width: 12px; background-color: #0284C7; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
        <span><b>7210000:</b> P&D Experimental</span>
    </div>
    <div style="margin-bottom: 4px; display: flex; align-items: center;">
        <span style="height: 12px; width: 12px; background-color: #16A34A; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
        <span><b>2660400:</b> Eletromédicos / Radiação</span>
    </div>
    <div style="margin-bottom: 4px; display: flex; align-items: center;">
        <span style="height: 12px; width: 12px; background-color: #EA580C; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
        <span><b>2610800:</b> Eletrônicos / Semicondutores</span>
    </div>
    <div style="margin-bottom: 8px; display: flex; align-items: center;">
        <span style="height: 12px; width: 12px; background-color: #9333EA; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
        <span><b>2731700:</b> Energia Elétrica / Controle</span>
    </div>

    <div style="border-top: 1px solid #E2E8F0; padding-top: 6px; font-weight: bold; margin-bottom: 6px; color: #475569;">Volume de Empresas por Polo:</div>
    <div style="display: flex; align-items: center; justify-content: space-around; padding: 4px 0;">
        <div style="text-align: center;">
            <div style="height: 8px; width: 8px; background-color: #64748B; border-radius: 50%; margin: 0 auto 3px auto;"></div>
            <span style="font-size: 10px;">1 - 5</span>
        </div>
        <div style="text-align: center;">
            <div style="height: 14px; width: 14px; background-color: #64748B; border-radius: 50%; margin: 0 auto 3px auto;"></div>
            <span style="font-size: 10px;">6 - 20</span>
        </div>
        <div style="text-align: center;">
            <div style="height: 20px; width: 20px; background-color: #64748B; border-radius: 50%; margin: 0 auto 3px auto;"></div>
            <span style="font-size: 10px;">20+</span>
        </div>
    </div>
</div>
{% endmacro %}
"""

macro = MacroElement()
macro._template = Template(template_legenda)
mapa_interativo.get_root().add_child(macro)

caminho_mapa_html = os.path.join(PASTA_SAIDA, "mapa_interativo_empresas.html")
mapa_interativo.save(caminho_mapa_html)
print(f"-> Mapa interativo com detalhes e legenda salvo em: '{caminho_mapa_html}'")

print("\n" + "=" * 60)
print("PIPELINE ESPACIAL CONCLUÍDO COM SUCESSO!")
print(f"Resultados gravados no diretório: '{PASTA_SAIDA}/'")
print("=" * 60)