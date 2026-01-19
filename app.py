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
# FUNÇÃO: LER LINHA DO KML
# ===============================
def ler_linha_kml(uploaded_file):
    try:
        conteudo = uploaded_file.read()
        parser = etree.XMLParser(recover=True, encoding='utf-8')
        tree = etree.fromstring(conteudo, parser=parser)
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        coords_text = tree.xpath(".//kml:LineString/kml:coordinates", namespaces=ns)
        if not coords_text: return None
        coords = []
        for p in coords_text[0].text.strip().split():
            partes = p.split(",")
            if len(partes) >= 2:
                coords.append((float(partes[0]), float(partes[1])))
        return LineString(coords)
    except: return None

# ===============================
# FUNÇÃO: GERAR ESTACAS
# ===============================
def gerar_estacas(linha, est_ini, m_ini, est_fim, espacamento=20):
    lon0, lat0 = linha.coords[0]
    zona = int((lon0 + 180) / 6) + 1
    epsg = 32700 + zona if lat0 < 0 else 32600 + zona
    proj = Transformer.from_crs(4326, epsg, always_xy=True)
    inv = Transformer.from_crs(epsg, 4326, always_xy=True)
    linha_utm = LineString([proj.transform(*c) for c in linha.coords])
    
    dist_total = (est_fim - est_ini) * 20
    distancias = np.arange(m_ini, dist_total + 0.1, espacamento)
    
    dados = []
    for d in distancias:
        ponto = linha_utm.interpolate(d)
        lon, lat = inv.transform(ponto.x, ponto.y)
        e_num = est_ini + int(d // 20)
        resto = int(d % 20)
        dados.append({"Estaca": f"E{e_num}+{resto:02d}", "Lat": lat, "Lon": lon})
    return pd.DataFrame(dados)

# ===============================
# INTERFACE STREAMLIT
# ===============================
st.set_page_config(layout="wide")
st.title("🛰️ Estaqueamento com Satélite Google/Esri")

file = st.file_uploader("Arraste o KML aqui", type="kml")

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
        # MAPA INTERATIVO (FOLIUM)
        # ===============================
        # Criar o mapa centralizado nas estacas
        m = folium.Map(
            location=[df["Lat"].mean(), df["Lon"].mean()],
            zoom_start=15,
            control_scale=True
        )

        # Adicionar Camada de Satélite (Google)
        google_satellite = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
        folium.TileLayer(
            tiles=google_satellite,
            attr="Google Satellite",
            name="Google Satellite",
            overlay=False,
            control=True
        ).add_to(m)

        # Adicionar as estacas como pontos (CircleMarker)
        # Usando apenas uma amostra se houver milhares de pontos para não travar o navegador
        amostra = df.iloc[::1] # Você pode mudar para ::5 para mostrar de 5 em 5 se ficar lento
        
        for _, row in amostra.iterrows():
            folium.CircleMarker(
                location=[row["Lat"], row["Lon"]],
                radius=4,
                color="yellow",
                fill=True,
                fill_color="red",
                fill_opacity=0.8,
                tooltip=row["Estaca"]
            ).add_to(m)

        # Renderizar o mapa no Streamlit
        st_folium(m, width="100%", height=600)

        # Download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 Baixar Excel", output.getvalue(), "estacas.xlsx")
