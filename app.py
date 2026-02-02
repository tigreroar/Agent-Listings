import streamlit as st
import os
import google.generativeai as genai
import pandas as pd
import requests
from dotenv import load_dotenv
from fpdf import FPDF
from PIL import Image
from duckduckgo_search import DDGS

load_dotenv()

# Configuración de API
api_key = os.environ.get("GOOGLE_API_KEY")
maps_key = os.environ.get("MAPS_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

st.set_page_config(page_title="Listings Department", layout="wide")

# --- FUNCIONES COMPARTIDAS ---
def search_web_general(query, max_results=4):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except: return "No se encontraron datos."

def calculate_metrics(df, months=6):
    df.columns = [c.lower().strip() for c in df.columns]
    status_col = next((c for c in df.columns if 'status' in c), None)
    price_col = next((c for c in df.columns if 'list' in c and 'price' in c), None)
    if not status_col or not price_col: return {"error": "Columnas faltantes en CSV"}
    
    sold = df[df[status_col].str.contains('sold|closed', case=False, na=False)].shape[0]
    active = df[df[status_col].str.contains('active', case=False, na=False)].shape[0]
    ar = sold / months
    moi = (active / ar) if ar > 0 else 0
    return {"moi": round(moi, 2), "sold": sold}

# --- INTERFAZ ---
st.sidebar.title("🏘️ Listings Dept.")
agent = st.sidebar.radio("Selecciona Agente:", ["Rick (Strategist)", "Sherlock (Analyst)", "Ava (Copywriter)"])

if agent == "Rick (Strategist)":
    st.title("Rick: Estratega de Propiedades")
    addr = st.text_input("Dirección de la propiedad")
    file = st.file_uploader("Subir MLS CSV", type=["csv"])
    if st.button("Generar Plan") and file and addr:
        df = pd.read_csv(file)
        m = calculate_metrics(df)
        prompt = f"Eres Rick, experto en real estate. Crea una estrategia para {addr} con estos datos: MOI {m['moi']}, Vendidos: {m['sold']}."
        model = genai.GenerativeModel('gemini-2.0-flash')
        st.write(model.generate_content(prompt).text)

elif agent == "Sherlock (Analyst)":
    st.title("Sherlock: Análisis Visual")
    img_file = st.file_uploader("Subir foto de la propiedad", type=["jpg", "png"])
    loc = st.text_input("Ubicación (Ciudad/Zip)")
    if st.button("Analizar") and img_file:
        img = Image.open(img_file)
        model = genai.GenerativeModel('gemini-2.0-flash')
        res = model.generate_content(["Analiza esta imagen de Real Estate buscando desperfectos o valor añadido:", img])
        st.write(res.text)

elif agent == "Ava (Copywriter)":
    st.title("Ava: Copywriting Persuasivo")
    specs = st.text_area("Detalles (Camas, baños, mejoras)")
    if st.button("Escribir Magia"):
        model = genai.GenerativeModel('gemini-2.0-flash')
        res = model.generate_content(f"Escribe una descripción de lujo para esta casa: {specs}")
        st.write(res.text)