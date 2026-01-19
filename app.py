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
        # Lemos como string para evitar erros de encoding binário
        conteudo = uploaded_file.getvalue().decode("utf-8")
        # O parser 'recover' ignora pequenos erros de sintaxe do KML
        parser = etree.XMLParser(recover=True)
        tree = etree.fromstring(conteudo.encode("utf-8"), parser=parser)

        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        coords_text = tree.xpath(".//kml:LineString/kml:coordinates", namespaces=ns)

        if not coords_text:
            return None

        coords = []
        for ponto in coords_text[0].text.strip().split():
            partes = ponto.split(",")
            if len(partes) >= 2:
                coords.append((float(partes[0]), float(partes[1])))

        return LineString(coords)
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        return None

# ===============================
# FUNÇÃO: GERAR ESTACAS
# ===============================
def gerar_estacas(linha, estaca_inicial, metro_inicial, estaca_final, espacamento=20):
    lon0, lat0 = linha.coords[0]
    zona = int((lon0 + 180) / 6) + 1
    epsg = 32700 + zona if lat0 < 0 else 32600 + zona

    proj = Transformer.from_crs(4326, epsg, always_xy=True)
    inv = Transformer.from_crs(epsg, 4326, always_xy=True)

    linha_utm = LineString([proj.transform(*c) for c in linha.coords])
    
    # Cálculo da distância total baseada nas estacas informadas
    fim_metros = (estaca_final - estaca_inicial) * 20
    distancias = np.arange(metro_inicial, fim_metros + 0.1, espacamento)
    
    dados = []
    for d in distancias:
        ponto = linha_utm.interpolate(d)
        lon, lat = inv.transform(ponto.x, ponto.y)
        estaca_num = estaca_inicial + int(d // 20)
        resto = int(d % 20)
        
        dados.append({
            "Estaca": f"E{estaca_num}+{resto:02d}",
            "Latitude": lat,
            "Longitude": lon
        })
    return pd.DataFrame(dados)

# ===============================
# INTERFACE STREAMLIT
# ===============================
st.set_page_config(layout="wide", page_title="Estaqueamento Rodoviário")
st.title("📍 Estaqueamento Automático com Satélite")

file = st.file_uploader("Arraste o KML aqui", type="kml")

c1, c2, c3 = st.columns(3)
with c1: e_ini = st.number_input("Estaca Inicial", value=853)
with c2: m_ini = st.number_input("Metro Inicial", value=16)
with c3: e_fim = st.number_input("Estaca Final", value=2777)

if file:
    linha = ler_linha_kml(file)
    if linha:
        df = gerar_estacas(linha, e_ini, m_ini, e_fim)
        st.success(f"Foram geradas {len(df)} estacas.")

        # ===============================
        # CONFIGURAÇÃO DO MAPA INTERATIVO
        # ===============================
        view_state = pdk.ViewState(
            latitude=df["Latitude"].mean(),
            longitude=df["Longitude"].mean(),
            zoom=13,
            pitch=0
        )

        # Camada de Pontos (Estacas)
        point_layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="[Longitude, Latitude]",
            get_fill_color=[255, 255, 0], # Amarelo para destacar no satélite
            get_radius=5,                # Raio de 5 metros
            radius_min_pixels=3,         # NÃO vira um borrão quando você tira o zoom
            radius_max_pixels=10,        # Não fica gigante quando você dá zoom
            pickable=True
        )

        # Renderização do Mapa com Satélite
        st.pydeck_chart(pdk.Deck(
            map_style="mapbox://styles/mapbox/satellite-v9", # ATIVA SATÉLITE
            initial_view_state=view_state,
            layers=[point_layer],
            tooltip={"text": "Estaca: {Estaca}"}
        ))

        # Botão de Download
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 Baixar Excel", buffer.getvalue(), "estacas.xlsx")
