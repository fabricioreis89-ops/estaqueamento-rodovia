import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from shapely.geometry import LineString
from lxml import etree
from pyproj import Transformer
import io

# ===============================
# FUNÇÃO: LER LINHA DO KML (MAIS ROBUSTA)
# ===============================
def ler_linha_kml(uploaded_file):
    try:
        # Lê o conteúdo e usa um parser que ignora erros menores de sintaxe
        conteudo = uploaded_file.read()
        parser = etree.XMLParser(recover=True, encoding='utf-8')
        tree = etree.fromstring(conteudo, parser=parser)

        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        coords_text = tree.xpath(".//kml:LineString/kml:coordinates", namespaces=ns)

        if not coords_text:
            return None

        coords = []
        # Limpeza para garantir que apenas números entrem na lista
        for par in coords_text[0].text.strip().split():
            partes = par.split(",")
            if len(partes) >= 2:
                coords.append((float(partes[0]), float(partes[1])))

        return LineString(coords)
    except Exception as e:
        st.error(f"Erro ao processar o KML: {e}")
        return None

# ===============================
# FUNÇÃO: GERAR ESTACAS
# ===============================
def gerar_estacas(linha, est_ini, m_ini, est_fim, espacamento=20):
    # Definir zona UTM automaticamente
    lon0, lat0 = linha.coords[0]
    zona = int((lon0 + 180) / 6) + 1
    epsg = 32700 + zona if lat0 < 0 else 32600 + zona

    proj = Transformer.from_crs(4326, epsg, always_xy=True)
    inv = Transformer.from_crs(epsg, 4326, always_xy=True)

    linha_utm = LineString([proj.transform(*c) for c in linha.coords])
    
    # Distância total baseada no intervalo de estacas
    dist_total = (est_fim - est_ini) * 20
    distancias = np.arange(m_ini, dist_total + 0.1, espacamento)
    
    dados = []
    for d in distancias:
        ponto = linha_utm.interpolate(d)
        lon, lat = inv.transform(ponto.x, ponto.y)
        e_num = est_ini + int(d // 20)
        resto = int(d % 20)
        
        dados.append({
            "Estaca": f"E{e_num}+{resto:02d}",
            "Latitude": lat,
            "Longitude": lon
        })
    return pd.DataFrame(dados)

# ===============================
# INTERFACE STREAMLIT
# ===============================
st.set_page_config(layout="wide", page_title="Estaqueamento Rodoviário")
st.title("🛰️ Estaqueamento com Imagem de Satélite")

file = st.file_uploader("Carregue o arquivo KML", type="kml")

c1, c2, c3 = st.columns(3)
with c1: e_ini = st.number_input("Estaca Inicial", value=853)
with c2: m_ini = st.number_input("Metro Inicial", value=16)
with c3: e_fim = st.number_input("Estaca Final", value=2777)

if file:
    linha = ler_linha_kml(file)
    if linha:
        df = gerar_estacas(linha, e_ini, m_ini, e_fim)
        st.success(f"{len(df)} estacas geradas.")

        # ===============================
        # CONFIGURAÇÃO DO MAPA (SATÉLITE)
        # ===============================
        view_state = pdk.ViewState(
            latitude=df["Latitude"].mean(),
            longitude=df["Longitude"].mean(),
            zoom=14,
            pitch=0
        )

        # Camada de Pontos (Estacas)
        # Ajustamos radius_min_pixels para os pontos não "sumirem" ou "virarem tripas"
        point_layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="[Longitude, Latitude]",
            get_fill_color=[255, 255, 0], # Amarelo destaca melhor no satélite
            get_radius=5,                # Raio real em metros
            radius_min_pixels=4,         # Garante visibilidade ao tirar o zoom
            radius_max_pixels=8,         # Impede que fiquem gigantes ao dar zoom
            pickable=True
        )

        st.pydeck_chart(pdk.Deck(
            # ATIVA O MODO SATÉLITE
            map_style="mapbox://styles/mapbox/satellite-v9", 
            initial_view_state=view_state,
            layers=[point_layer],
            tooltip={"text": "Estaca: {Estaca}"}
        ))

        # Botão de Download
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 Baixar Planilha Excel", buffer.getvalue(), "estacas.xlsx")
