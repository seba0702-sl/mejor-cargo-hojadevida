import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Calculo de computos", layout="wide")

st.title("Calculo de computos jubilatorios")

if "df_consolidado" not in st.session_state:
    st.warning("Primero carga y procesa los datos en la pagina principal.")
    st.stop()

datos_personales = st.session_state.get("datos_personales", {})

fecha_nacimiento = datos_personales.get("Fecha de nacimiento")
fecha_cese = datos_personales.get("Fecha de cese")

if not fecha_nacimiento or not fecha_cese:
    st.warning("Falta cargar Fecha de nacimiento y Fecha de cese en la pagina principal.")
    st.stop()

fecha_nacimiento = pd.to_datetime(fecha_nacimiento)
fecha_cese = pd.to_datetime(fecha_cese)

df = st.session_state["df_consolidado"].copy()

df["DESDE"] = pd.to_datetime(df["DESDE"], errors="coerce", dayfirst=True)
df["HASTA"] = pd.to_datetime(df["HASTA"], errors="coerce", dayfirst=True)
df = df.dropna(subset=["DESDE", "HASTA"]).sort_values("DESDE")

if df.empty:
    st.warning("No hay servicios cargados para calcular.")
    st.stop()


def formato_amd(rd):
    return f"{rd.years} años, {rd.months} meses, {rd.days} dias"


def calcular_servicios_unificados(df_servicios):
    periodos = []

    for _, row in df_servicios.iterrows():
        inicio = row["DESDE"]
        fin = row["HASTA"]

        if pd.notna(inicio) and pd.notna(fin):
            periodos.append((inicio, fin))

    if not periodos:
        return 0, relativedelta(pd.Timestamp("2000-01-01"), pd.Timestamp("2000-01-01"))

    periodos = sorted(periodos, key=lambda x: x[0])

    merged = []
    current_start, current_end = periodos[0]

    for start, end in periodos[1:]:
        if start <= current_end + pd.Timedelta(days=1):
            current_end = max(current_end, end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = start, end

    merged.append((current_start, current_end))

    total_days = 0

    for inicio, fin in merged:
        total_days += (fin - inicio).days

    base = pd.Timestamp("2000-01-01")
    rd = relativedelta(base + pd.Timedelta(days=total_days), base)

    return total_days, rd


def dias_equivalentes_anios(anios):
    base = pd.Timestamp("2000-01-01")
    return (base + pd.DateOffset(years=anios) - base).days


edad_al_cese = relativedelta(fecha_cese, fecha_nacimiento)

fecha_minima_edad = fecha_nacimiento + pd.DateOffset(years=50)
fecha_edad_75 = fecha_nacimiento + pd.DateOffset(years=53)
fecha_edad_80 = fecha_nacimiento + pd.DateOffset(years=55)

if fecha_cese >= fecha_minima_edad:
    excedente_edad = relativedelta(fecha_cese, fecha_minima_edad)
else:
    excedente_edad = None

total_dias_servicios, servicios = calcular_servicios_unificados(df)
info_anses = st.session_state.get("info_anses", {})
tiene_anses = str(info_anses.get("tiene_anses", "No")).lower() in ["si", "sí", "true"]

otros_servicios_prorrateo = st.checkbox(
    "Tiene otros servicios reconocidos / prorrateo que completan el minimo jubilatorio",
    value=tiene_anses,
)
dias_25 = dias_equivalentes_anios(25)
dias_28 = dias_equivalentes_anios(28)
dias_30 = dias_equivalentes_anios(30)

if total_dias_servicios >= dias_25:
    base = pd.Timestamp("2000-01-01")
    excedente_servicios = relativedelta(
        base + pd.Timedelta(days=total_dias_servicios - dias_25),
        base,
    )
else:
    excedente_servicios = None

cumple_edad_minima = fecha_cese >= fecha_minima_edad
cumple_servicios_minimos = total_dias_servicios >= dias_25

cumple_70 = (
    cumple_edad_minima
    and (
        cumple_servicios_minimos
        or otros_servicios_prorrateo
    )
)

cumple_75 = fecha_cese >= fecha_edad_75 and total_dias_servicios >= dias_28
cumple_80 = fecha_cese >= fecha_edad_80 and total_dias_servicios >= dias_30
if cumple_80:
    porcentaje = "80%"
    detalle = "Excede 5 años de edad y 5 años de servicios."
elif cumple_75:
    porcentaje = "75%"
    detalle = "Excede 3 años de edad y 3 años de servicios."
elif cumple_70:
    porcentaje = "70%"
    if cumple_servicios_minimos:
        detalle = "Cumple edad minima y servicios minimos."
    else:
        detalle = (
            "Cumple edad minima. El 70% se considera por otros servicios "
            "reconocidos / prorrateo informado."
        )
else:
    porcentaje = "No cumple"
    detalle = "No alcanza la edad minima de 50 años."

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Porcentaje estimado", porcentaje)

with col2:
    st.metric("Edad al cese", formato_amd(edad_al_cese))

with col3:
    st.metric("Servicios computados", formato_amd(servicios))

st.markdown("---")

tabla = pd.DataFrame([
    {
        "Concepto": "Edad",
        "Dato calculado": formato_amd(edad_al_cese),
        "Minimo requerido": "50 años, 0 meses, 0 dias",
        "Excedente": formato_amd(excedente_edad) if excedente_edad else "No cumple minimo",
    },
    {
        "Concepto": "Servicios",
        "Dato calculado": formato_amd(servicios),
        "Minimo requerido": "25 años, 0 meses, 0 dias",
        "Excedente": formato_amd(excedente_servicios) if excedente_servicios else "No cumple minimo",
    },
])

st.dataframe(tabla, use_container_width=True, hide_index=True)

st.markdown("### Comparativa")

comparativa = pd.DataFrame([
    {
        "Porcentaje": "70%",
        "Edad requerida": "50 años",
        "Servicios requeridos": "25 años",
        "Resultado": "Cumple" if cumple_70 else "No cumple",
    },
    {
        "Porcentaje": "75%",
        "Edad requerida": "53 años",
        "Servicios requeridos": "28 años",
        "Resultado": "Cumple" if cumple_75 else "No cumple",
    },
    {
        "Porcentaje": "80%",
        "Edad requerida": "55 años",
        "Servicios requeridos": "30 años",
        "Resultado": "Cumple" if cumple_80 else "No cumple",
    },
])

st.dataframe(comparativa, use_container_width=True, hide_index=True)

st.info(detalle)

st.caption(
    "Calculo orientativo basado en fecha de nacimiento, fecha de cese y servicios cargados en hoja de vida."
)