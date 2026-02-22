import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, time, date
import requests
import pytz

# --- CONFIGURACIÓN ---
FINNHUB_API_KEY = 'd6d2nn1r01qgk7mkblh0d6d2nn1r01qgk7mkblhg'
ZONA_HORARIA = pytz.timezone('Europe/Madrid')

st.set_page_config(page_title="Monitor XSP Táctico", layout="wide")
st.title("📊 Monitor Táctico XSP 0DTE")

# BARRA LATERAL
st.sidebar.header("Configuración de Cuenta")
capital = st.sidebar.number_input("Capital de la Cuenta (€)", min_value=100.0, value=25000.0, step=500.0)

def check_noticias_tactico(api_key):
    eventos_prohibidos = ["CPI", "FED", "FOMC", "NFP", "POWELL", "PPI", "INTEREST RATE", "JOBLESS"]
    hoy = str(date.today())
    url = f"https://finnhub.io{hoy}&to={hoy}&token={api_key}"
    estado_noticias = {"bloqueo": False, "tipo": "NORMAL", "eventos": []}
    try:
        response = requests.get(url)
        data = response.json().get('economicCalendar', [])
        for ev in data:
            if ev['country'] == 'US' and ev['impact'] == 'high':
                nombre = ev['event'].upper()
                if any(k in nombre for k in eventos_prohibidos):
                    hora_utc = datetime.strptime(ev['time'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc)
                    hora_es = hora_utc.astimezone(ZONA_HORARIA).time()
                    estado_noticias["eventos"].append(f"{ev['event']} ({hora_es.strftime('%H:%M')})")
                    if hora_es < time(15, 30): estado_noticias["tipo"] = "PRE_MERCADO"
                    elif hora_es > time(19, 30): estado_noticias["tipo"] = "TARDE_FED"
                    else: estado_noticias["bloqueo"] = True
        return estado_noticias
    except: return estado_noticias

def obtener_datos():
    tickers = {"XSP": "^XSP", "VIX": "^VIX", "VIX9D": "^VIX9D", "VVIX": "^VVIX", "VIX1D": "^VIX1D"}
    vals = {}
    for k, v in tickers.items():
        t = yf.Ticker(v)
        df = t.history(period="1d", interval="1m")
        if not df.empty:
            vals[k] = {"actual": df['Close'].iloc[-1], "apertura": df['Open'].iloc[0]}
        else: vals[k] = {"actual": 0, "apertura": 0}
    return vals

# EJECUCIÓN
if st.button('🚀 Analizar Mercado'):
    ahora = datetime.now(ZONA_HORARIA).time()
    if ahora < time(16, 15):
        st.warning("⚠️ No son las 16:15 todavía. Los datos de confirmación no son definitivos.")

    noticias = check_noticias_tactico(FINNHUB_API_KEY)
    
    # Mostrar Noticias
    if noticias["eventos"]:
        with st.expander("🔔 Eventos Críticos Hoy", expanded=True):
            for ev in noticias["eventos"]: st.write(f"• {ev}")
    
    if noticias["bloqueo"]:
        st.error("🚫 BLOQUEO TOTAL: Noticia en horario operativo. NO OPERAR.")
    else:
        with st.spinner('Calculando tramos...'):
            d = obtener_datos()
            xsp, vix, vvix = d["XSP"]["actual"], d["VIX"]["actual"], d["VVIX"]["actual"]
            rango_ap = abs((xsp - d["XSP"]["apertura"]) / d["XSP"]["apertura"] * 100) if d["XSP"]["apertura"] != 0 else 0

            # Métricas Principales
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("XSP", f"{xsp:.2f}", f"{rango_ap:.2f}%")
            c2.metric("VIX", f"{vix:.2f}")
            c3.metric("VVIX", f"{vvix:.2f}")
            c4.metric("VIX1D", f"{d['VIX1D']['actual']:.2f}")

            # Cálculo de gestión
            ancho_alas = 5
            riesgo_neto_contrato = (ancho_alas * (2/3)) * 100 
            num_contratos = max(1, int((capital * 0.02) // riesgo_neto_contrato))
            beneficio_obj = num_contratos * (ancho_alas / 3) * 100

            st.divider()

            # LÓGICA DE ESTRATEGIA
            if noticias["tipo"] == "TARDE_FED":
                st.success(f"🎯 TRAMO 1 (ESPECIAL): IRON CONDOR PRE-FED")
                st.error(f"⚠️ CERRAR POSICIÓN ANTES DE LAS 19:30 ESP (Noticia tarde)")
                st.write(f"**Beneficio Objetivo:** {beneficio_obj:.2f}€ | **Contratos:** {num_contratos}")
            
            elif noticias["tipo"] == "PRE_MERCADO":
                st.info(f"🎯 TRAMO 2 (POST-NOTICIA): SPREAD VERTICAL")
                dir_t = "ALCISTA (Vender Put)" if xsp > d["XSP"]["apertura"] else "BAJISTA (Vender Call)"
                st.write(f"**Dirección:** {dir_t} | **Beneficio Objetivo:** {beneficio_obj:.2f}€")

            elif d["VIX1D"]["actual"] < d["VIX9D"]["actual"] < vix and vix < 16 and vvix < 88 and rango_ap < 0.40:
                st.success(f"🎯 TRAMO 1: IRON CONDOR ESTÁNDAR (Calma)")
                st.write(f"**Beneficio Objetivo:** {beneficio_obj:.2f}€ | **Contratos:** {num_contratos}")

            elif d["VIX1D"]["actual"] > d["VIX9D"]["actual"] or vvix > 105 or rango_ap > 0.75:
                st.info(f"🎯 TRAMO 2: SPREAD VERTICAL (Tendencia)")
                st.write(f"**Beneficio Objetivo:** {beneficio_obj:.2f}€ | **Contratos:** {num_contratos}")
            
            else:
                st.warning("⚖️ SIN SEÑAL CLARA: El mercado no cumple parámetros de alta probabilidad.")

st.sidebar.caption("Datos con 15 min de retraso (Yahoo Finance)")
      
