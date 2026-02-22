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

def calcular_niveles(precio, vix, delta_target):
    # Cálculo basado en volatilidad implícita (VIX) para 1 día
    sigma_1d = (vix / 100) / (252**0.5)
    # Delta 5 (aprox 1.65s) | Delta 3 (aprox 1.88s)
    mult = 1.65 if delta_target == 5 else 1.88
    distancia = precio * sigma_1d * mult
    
    ancho = 3 if vix < 14 else 5
    
    vendido_up = round(precio + distancia)
    comprado_up = vendido_up + ancho
    vendido_down = round(precio - distancia)
    comprado_down = vendido_down - ancho
    
    return {
        "v_up": vendido_up, "c_up": comprado_up,
        "v_down": vendido_down, "c_down": comprado_down,
        "ancho": ancho, "dist": round(distancia, 2)
    }

# EJECUCIÓN
if st.button('🚀 Analizar Mercado'):
    ahora = datetime.now(ZONA_HORARIA).time()
    if ahora < time(16, 15):
        st.warning("⚠️ No son las 16:15 todavía. Los datos de confirmación no son definitivos.")

    noticias = check_noticias_tactico(FINNHUB_API_KEY)
    
    if noticias["eventos"]:
        with st.expander("🔔 Eventos Críticos Hoy", expanded=True):
            for ev in noticias["eventos"]: st.write(f"• {ev}")
    
    if noticias["bloqueo"]:
        st.error("🚫 BLOQUEO TOTAL: Noticia en horario operativo. NO OPERAR.")
    else:
        with st.spinner('Calculando tramos y strikes...'):
            d = obtener_datos()
            xsp, vix, vvix = d["XSP"]["actual"], d["VIX"]["actual"], d["VVIX"]["actual"]
            rango_ap = abs((xsp - d["XSP"]["apertura"]) / d["XSP"]["apertura"] * 100) if d["XSP"]["apertura"] != 0 else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("XSP", f"{xsp:.2f}", f"{rango_ap:.2f}%")
            c2.metric("VIX", f"{vix:.2f}")
            c3.metric("VVIX", f"{vvix:.2f}")
            c4.metric("VIX1D", f"{d['VIX1D']['actual']:.2f}")

            st.divider()

            # LÓGICA DE ESTRATEGIA
            if noticias["tipo"] == "TARDE_FED" or (d["VIX1D"]["actual"] < d["VIX9D"]["actual"] < vix and vix < 16 and vvix < 88 and rango_ap < 0.40):
                n = calcular_niveles(xsp, vix, 5)
                riesgo_neto = (n["ancho"] * (2/3)) * 100 
                num_contratos = max(1, int((capital * 0.02) // riesgo_neto))
                beneficio_obj = num_contratos * (n["ancho"] / 3) * 100

                st.success(f"🎯 TRAMO 1: IRON CONDOR (Delta 5)")
                if noticias["tipo"] == "TARDE_FED": st.error("⚠️ CERRAR ANTES DE LAS 19:30 ESP (FED Hoy)")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.info(f"**Lado CALL (Arriba)**\n\n• Vender: **{n['v_up']}**\n\n• Comprar: **{n['c_up']}**")
                with col_b:
                    st.info(f"**Lado PUT (Abajo)**\n\n• Vender: **{n['v_down']}**\n\n• Comprar: **{n['c_down']}**")
                
                st.write(f"**Detalles:** Distancia {n['dist']} pts | Alas {n['ancho']} pts | Contratos: {num_contratos} | **Beneficio: {beneficio_obj:.2f}€**")

            elif noticias["tipo"] == "PRE_MERCADO" or (d["VIX1D"]["actual"] > d["VIX9D"]["actual"] or vvix > 105 or rango_ap > 0.75):
                n = calcular_niveles(xsp, vix, 3)
                riesgo_neto = (n["ancho"] * (2/3)) * 100
                num_contratos = max(1, int((capital * 0.02) // riesgo_neto))
                beneficio_obj = num_contratos * (n["ancho"] / 3) * 100
                
                es_alcista = xsp > d["XSP"]["apertura"]
                st.info(f"🎯 TRAMO 2: SPREAD VERTICAL (Delta 3)")
                
                if es_alcista:
                    st.success(f"**Bull Put Spread (Alcista)**\n\n• Vender: **{n['v_down']}** | Comprar: **{n['c_down']}**")
                else:
                    st.error(f"**Bear Call Spread (Bajista)**\n\n• Vender: **{n['v_up']}** | Comprar: **{n['c_up']}**")
                
                st.write(f"**Detalles:** Distancia {n['dist']} pts | Alas {n['ancho']} pts | Contratos: {num_contratos} | **Beneficio: {beneficio_obj:.2f}€**")

            else:
                st.warning("⚖️ SIN SEÑAL CLARA: El mercado no cumple parámetros de alta probabilidad.")

st.sidebar.caption("Monitor XSP 0DTE - Datos Yahoo Finance")
