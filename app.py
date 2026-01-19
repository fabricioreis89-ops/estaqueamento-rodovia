import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide")

st.title("Estaqueamento de Rodovia")

st.write("Upload do eixo da rodovia (KML)")

kml = st.file_uploader("Arquivo KML do eixo", type=["kml"])

if kml:
    st.success("Arquivo carregado com sucesso")
    st.write("Próximo passo: gerar estacas")
