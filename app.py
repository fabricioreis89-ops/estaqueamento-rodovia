import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from shapely.geometry import LineString
from lxml import etree
from pyproj import Transformer
import io

# ===============================
# 1. FUNÇÕES DE PROCESSAMENTO
# ===============================

def ler_linha_kml(uploaded_file):
    """Lê o arquivo KML e extrai a geometria da estrada."""
    try:
        conteudo = uploaded_file.read()
        # O parser 'recover' ignora erros de sintaxe comuns em KMLs do Google Earth
        parser = etree.XMLParser(recover=True, encoding='utf-8')
        tree = etree.fromstring(conteudo, parser=parser)
        
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        coords_text = tree.xpath(".//kml:LineString/kml:coordinates", namespaces=ns)
        
        if not coords_text:
            return None

        coords = []
        for linha in coords_text[0].text.strip().split():
            partes = linha.split(",")
            if len(partes) >= 2:
                coords.append((float(partes[0]), float(partes[1])))
        
        return LineString(coords)
    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        return None

def gerar_estacas(linha, est_ini, m_ini, est_fim, espacamento=20):
    """Calcula as estacas intermediárias ao longo do traçado."""
    # Define zona UTM automaticamente para cálculos de distância
    lon0, lat0 = linha.coords[0]
    zona = int((lon0 + 180) / 6) + 1
    epsg = 32700 + zona if lat0 < 0 else 32600 + zona
    
    proj = Transformer.from_crs(4326, epsg, always_xy=True)
    inv = Transformer.from_crs(epsg, 4326, always_xy=True)
    
    linha_utm = LineString([proj.transform(*c) for c in linha.coords])
    
    # Distância total acumulada com base nas estacas informadas
    dist_fim_total = (est_fim - est_ini) * 20
    distancias = np.arange(m_ini, dist_fim_total + 0.1, espacamento)
    
    dados = []
    for d in distancias:
        ponto = linha_utm.interpolate(d)
        lon, lat = inv.transform(ponto.x, ponto.y)
        e_atual = est_ini + int(d // 20)
        resto = int(d % 20)
        
        dados.append({
            "Estaca": f"E{e_atual}+{resto:02d}",
            "Lat": lat,
            "Lon": lon,
            "UTM_E": round(ponto.x, 2),
            "UTM_N": round(ponto.y, 2)
        })
    
    return pd.DataFrame(dados)

# ===============================
# 2. CONFIGURAÇÃO DA INTERFACE
# ===============================

st.set_page_config(layout="wide", page_title="Sistema de Estaqueamento")

st.title("🛣️ Estaqueamento de Rodovias com Busca Interativa")
st.markdown("---")

# Barra lateral para inputs
st.sidebar.header("Configurações")
uploaded_file = st.sidebar.file_uploader("Carregue o traçado (KML)", type="kml")

col1, col2, col3 = st.sidebar.columns(3)
with col1: e_ini = st.number_input("Estaca Inicial", value=853)
with col2: m_ini = st.number_input("Metro (+)", value=16)
with col3: e_fim = st.number_input("Estaca Final", value=2777)

if uploaded_file:
    linha = ler_linha_kml(uploaded_file)
    
    if linha:
        df = gerar_estacas(linha, e_ini, m_ini, e_fim)
        
        # 🔍 FUNCIONALIDADE DE BUSCA
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Localizar Estaca")
        opcoes = ["--- Selecione uma estaca ---"] + df["Estaca"].tolist()
        estaca_alvo = st.sidebar.selectbox("Ir para:", opcoes)

        # Determinar centro do mapa
        if estaca_alvo != "--- Selecione uma estaca ---":
            ponto_alvo = df[df["Estaca"] == estaca_alvo].iloc[0]
            centro = [ponto_alvo["Lat"], ponto_alvo["Lon"]]
            zoom_init = 18 # Zoom aproximado para busca
        else:
            centro = [df["Lat"].mean(), df["Lon"].mean()]
            zoom_init = 14

        # ===============================
        # 3. CONSTRUÇÃO DO MAPA (FOLIUM)
        # ===============================
        
        # Cria o mapa base com tiles de satélite do Google
        m = folium.Map(location=centro, zoom_start=zoom_init, control_scale=True)
        
        google_sat = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
        folium.TileLayer(tiles=google_sat, attr="Google", name="Satélite").add_to(m)

        # Injetar CSS para animação de "pulse" (piscando)
        css_pulse = """
        <style>
        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            70% { transform: scale(2.5); opacity: 0; }
            100% { transform: scale(1); opacity: 0; }
        }
        .pulser {
            width: 15px; height: 15px;
            background: #00ffff; border-radius: 50%;
            animation: pulse 1.5s infinite;
        }
        </style>
        """
        m.get_root().header.add_child(folium.Element(css_pulse))

        # Adicionar pontos das estacas
        for _, row in df.iterrows():
            folium.CircleMarker(
                location=[row["Lat"], row["Lon"]],
                radius=3, color="yellow", fill=True, fill_color="red",
                fill_opacity=0.8, tooltip=row["Estaca"]
            ).add_to(m)

        # Adicionar destaque se houver busca ativa
        if estaca_alvo != "--- Selecione uma estaca ---":
            folium.Marker(
                location=centro,
                icon=folium.DivIcon(html='<div class="pulser"></div>')
            ).add_to(m)
            folium.Marker(
                location=centro,
                popup=f"Localizado: {estaca_alvo}",
                icon=folium.Icon(color="cadetblue", icon="info-sign")
            ).add_to(m)

        # Exibir o mapa
        st_folium(m, width="100%", height=650)

        # Botão de Download
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 Baixar Planilha das Estacas", buffer.getvalue(), "estaqueamento.xlsx")

    else:
        st.error("O arquivo KML não contém um LineString válido.")
