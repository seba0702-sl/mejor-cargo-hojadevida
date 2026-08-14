import streamlit as st
import pandas as pd

# ---------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# ---------------------------------
st.set_page_config(
    page_title="Ir Tabla de datos cargados",
    layout="wide"
)

st.title("📋 Resumen de datos procesados")

# ---------------------------------
# VALIDACIÓN DE DATOS
# ---------------------------------
if "df_consolidado" not in st.session_state:
    st.warning("⚠️ Primero cargá y procesá los datos en la página principal.")
    st.stop()

df_consolidado = st.session_state["df_consolidado"]
df_periodos = st.session_state.get("df_periodos")
hoja_licencias = st.session_state.get("hoja_licencias")

# ---------------------------------
# MÉTRICAS GENERALES
# ---------------------------------
st.subheader("📊 Métricas generales")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Periodos totales", len(df_consolidado))

with col2:
    st.metric(
        "Secuencias únicas",
        df_consolidado["SECUENCIA"].astype(str).nunique()
        if "SECUENCIA" in df_consolidado.columns else 0
    )

with col3:
    st.metric(
        "Fecha mínima",
        pd.to_datetime(df_consolidado["DESDE"], errors="coerce").min().strftime("%d/%m/%Y")
        if "DESDE" in df_consolidado.columns else "-"
    )

with col4:
    st.metric(
        "Fecha máxima",
        pd.to_datetime(df_consolidado["HASTA"], errors="coerce").max().strftime("%d/%m/%Y")
        if "HASTA" in df_consolidado.columns else "-"
    )

st.markdown("---")

# ---------------------------------
# TABLA 1 — PERIODOS CONSOLIDADOS
# ---------------------------------
st.subheader("🧩 Periodos consolidados")

st.dataframe(
    df_consolidado,
    use_container_width=True,
    height=450
)

# ---------------------------------
# TABLA 2 — PERIODOS CON CORTE
# ---------------------------------
if df_periodos is not None:
    st.markdown("---")
    st.subheader("✂️ Periodos con licencias aplicadas")

    st.dataframe(
        df_periodos,
        use_container_width=True,
        height=450
    )

# ---------------------------------
# TABLA 3 — LICENCIAS
# ---------------------------------
if hoja_licencias is not None and not hoja_licencias.empty:
    st.markdown("---")
    st.subheader("🟥 Licencias cargadas")

    st.dataframe(
        hoja_licencias,
        use_container_width=True,
        height=350
    )

# ---------------------------------
# INFO FINAL
# ---------------------------------
st.caption(
    "ℹ️ Esta página es solo de visualización. "
    "Los datos se cargan y procesan exclusivamente en la página principal."
)
