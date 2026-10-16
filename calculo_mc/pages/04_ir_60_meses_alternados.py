import io

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="60 Meses Alternados por Nivel",
    layout="wide",
)

st.title("60 meses alternados con la mayor carga posible")


# =====================================================
# FUNCIONES
# =====================================================

def calcular_antiguedad_exacta(desde, hasta):
    desde = pd.to_datetime(desde, errors="coerce")
    hasta = pd.to_datetime(hasta, errors="coerce")

    if pd.isna(desde) or pd.isna(hasta) or hasta < desde:
        return 0, 0, 0

    dias_totales = (hasta - desde).days + 1
    anios = dias_totales // 365
    resto = dias_totales % 365
    meses = resto // 30
    dias = resto % 30

    return anios, meses, dias


def detectar_nivel(escuela):
    """
    Respaldo para archivos que no traen la columna NIVEL.
    Si el archivo sí la trae, se usa esa clasificación.
    """
    if pd.isna(escuela):
        return None

    texto = str(escuela).upper()

    # Códigos específicos primero; se evita usar "ES" como coincidencia
    # general porque puede clasificar escuelas de otros niveles por error.
    reglas = [
        ("Inicial", ["JI", "JS", "JU", "JM", "JV"]),
        ("Primaria", [
            "PP", "EP", "PA", "DA", "DC", "DE",
            "ESCUELA PRIMARIA BASICA",
        ]),
        ("Especial", ["EE", "EL", "CFI", "ET", "ESPECIAL"]),
        ("Secundaria", [
            "MM", "MS", "ESB", "MT", "BS", "MA", "MC", "AS",
            "ESC. DE ENS. MEDIA",
            "ESC. SECUND. TECNICA",
            "ESC. SECUNDARIA BASICA",
        ]),
        ("Adulto", [
            "DM", "CENS", "DF", "DS", "MF",
            "ADULTOS", "ADULTO", "CFP", "CFL",
        ]),
        ("Superior", [
            "IS", "AA", "AT", "AF", "AV", "AC", "AD",
            "AM", "AP", "FC", "CENTRO DE EDUC. FISICA", "CEF",
        ]),
    ]

    for nivel, codigos in reglas:
        if any(codigo in texto for codigo in codigos):
            return nivel

    return None


def preparar_datos(df_original):
    df = df_original.copy()

    columnas_fecha = {"DESDE", "HASTA"}
    faltantes = columnas_fecha - set(df.columns)
    if faltantes:
        raise ValueError(
            f"Faltan columnas de fechas: {', '.join(sorted(faltantes))}"
        )

    df["DESDE"] = pd.to_datetime(df["DESDE"], errors="coerce").dt.normalize()
    df["HASTA"] = pd.to_datetime(df["HASTA"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["DESDE", "HASTA"])
    df = df[df["DESDE"] <= df["HASTA"]].copy()

    if "SECUENCIA" not in df.columns:
        df["SECUENCIA"] = df.index.astype(str)

    # Usar el nivel provisto por el archivo cuando exista.
    # Solo intentar inferirlo si NIVEL no está o está vacío.
    if "NIVEL" not in df.columns:
        df["NIVEL"] = df["ESCUELA"].apply(detectar_nivel)
    else:
        nivel_vacio = df["NIVEL"].isna() | (
            df["NIVEL"].astype(str).str.strip() == ""
        )
        if "ESCUELA" in df.columns and nivel_vacio.any():
            df.loc[nivel_vacio, "NIVEL"] = (
                df.loc[nivel_vacio, "ESCUELA"].apply(detectar_nivel)
            )

    # El CSV exportado ya trae estas columnas. No recalcularlas usando
    # df.columns[9]: en ese archivo la columna 9 es ESCUELA.
    if "MODULOS" not in df.columns or "HORAS_CATEDRA" not in df.columns:
        if "CARGA HORARIA" not in df.columns:
            raise ValueError(
                "El archivo debe tener MODULOS y HORAS_CATEDRA, "
                "o una columna CARGA HORARIA."
            )

        carga = pd.to_numeric(
            df["CARGA HORARIA"], errors="coerce"
        ).fillna(0)

        cargo = (
            df["CARGO"].fillna("").astype(str).str.upper()
            if "CARGO" in df.columns
            else pd.Series("", index=df.index)
        )

        if "MODULOS" not in df.columns:
            df["MODULOS"] = carga.where(
                cargo.str.contains("MOD", regex=False), 0
            )

        if "HORAS_CATEDRA" not in df.columns:
            df["HORAS_CATEDRA"] = carga.where(
                cargo.str.contains(
                    r"HORA|CATEDRA|INSTRUCTOR|\bHS\b",
                    regex=True,
                ),
                0,
            )

    df["MODULOS"] = pd.to_numeric(
        df["MODULOS"], errors="coerce"
    ).fillna(0)
    df["HORAS_CATEDRA"] = pd.to_numeric(
        df["HORAS_CATEDRA"], errors="coerce"
    ).fillna(0)

    return df.reset_index(drop=True)


def seleccionar_periodos_60_meses(
    df_nivel,
    meses_objetivo=60,
    minimo_modulos=0,
    minimo_horas=0,
):
    """
    Evalúa cada día del nivel. Un día cuenta como alternado si hay al
    menos dos SECUENCIAS distintas activas.

    Elige hasta meses_objetivo * 30 días, priorizando módulos y luego
    horas cátedra. Devuelve períodos consecutivos seleccionados.
    """
    cantidad_objetivo = int(meses_objetivo) * 30

    if df_nivel.empty:
        return [], 0, 0

    dias_candidatos = []
    fecha = df_nivel["DESDE"].min()
    fecha_final = df_nivel["HASTA"].max()

    while fecha <= fecha_final:
        activas = df_nivel[
            (df_nivel["DESDE"] <= fecha)
            & (df_nivel["HASTA"] >= fecha)
        ].copy()

        if not activas.empty:
            # Evita contar dos veces una secuencia si el archivo contiene
            # filas duplicadas o tramos simultáneos de la misma secuencia.
            activas = activas.sort_values(
                ["SECUENCIA", "MODULOS", "HORAS_CATEDRA"],
                ascending=[True, False, False],
            ).drop_duplicates("SECUENCIA", keep="first")

            if activas["SECUENCIA"].nunique() >= 2:
                modulos = float(activas["MODULOS"].sum())
                horas = float(activas["HORAS_CATEDRA"].sum())

                if (
                    modulos >= minimo_modulos
                    and horas >= minimo_horas
                    and (modulos > 0 or horas > 0)
                ):
                    dias_candidatos.append({
                        "fecha": fecha,
                        "secuencias": tuple(sorted(
                            activas["SECUENCIA"].astype(str)
                        )),
                        "modulos": modulos,
                        "horas": horas,
                        "filas": activas,
                    })

        fecha += pd.Timedelta(days=1)

    if not dias_candidatos:
        return [], 0, 0

    # Ordenar por carga. Los empates favorecen las fechas más antiguas.
    dias_candidatos.sort(
        key=lambda d: (
            d["modulos"],
            d["horas"],
            -d["fecha"].toordinal(),
        ),
        reverse=True,
    )

    elegidos = dias_candidatos[:cantidad_objetivo]
    elegidos.sort(key=lambda d: d["fecha"])

    # Agrupar días elegidos consecutivos cuando tienen igual carga
    # y la misma combinación de secuencias.
    grupos = []
    actual = None

    for dia in elegidos:
        puede_unirse = (
            actual is not None
            and dia["fecha"] == actual["fecha_hasta"] + pd.Timedelta(days=1)
            and dia["secuencias"] == actual["secuencias"]
            and dia["modulos"] == actual["modulos"]
            and dia["horas"] == actual["horas"]
        )

        if not puede_unirse:
            if actual is not None:
                actual["grupo_df"] = (
                    pd.concat(actual.pop("_filas"), ignore_index=True)
                    .drop_duplicates()
                    .reset_index(drop=True)
                )
                grupos.append(actual)

            actual = {
                "fecha_desde": dia["fecha"],
                "fecha_hasta": dia["fecha"],
                "secuencias": dia["secuencias"],
                "modulos": dia["modulos"],
                "horas": dia["horas"],
                "_filas": [dia["filas"]],
            }
        else:
            actual["fecha_hasta"] = dia["fecha"]
            actual["_filas"].append(dia["filas"])

    if actual is not None:
        actual["grupo_df"] = (
            pd.concat(actual.pop("_filas"), ignore_index=True)
            .drop_duplicates()
            .reset_index(drop=True)
        )
        grupos.append(actual)

    dias_seleccionados = len(elegidos)
    meses_aproximados = dias_seleccionados // 30

    return grupos, dias_seleccionados, meses_aproximados


# =====================================================
# CARGA DE DATOS
# =====================================================

if "df_consolidado_filtrado" not in st.session_state:
    st.warning("Primero debe cargar los datos.")
    st.stop()

try:
    df = preparar_datos(st.session_state["df_consolidado_filtrado"])
except ValueError as error:
    st.error(str(error))
    st.stop()

niveles = sorted(df["NIVEL"].dropna().astype(str).unique())

if not niveles:
    st.error("No se pudieron identificar niveles en los datos.")
    st.stop()


# =====================================================
# CONFIGURACIÓN
# =====================================================

st.markdown("---")
st.subheader("Criterios de selección")

nivel_elegido = st.selectbox("Nivel", niveles)

col1, col2, col3 = st.columns(3)

meses_objetivo = col1.number_input(
    "Meses aproximados a reunir",
    min_value=1,
    max_value=200,
    value=60,
    step=1,
)

minimo_modulos = col2.number_input(
    "Mínimo de módulos por día",
    min_value=0,
    max_value=1000,
    value=0,
    step=1,
)

minimo_horas = col3.number_input(
    "Mínimo de horas cátedra por día",
    min_value=0,
    max_value=1000,
    value=0,
    step=1,
)

st.caption(
    "Se priorizan los días con más módulos. Las horas cátedra se usan "
    "como desempate y se informan por separado."
)

df_nivel = df[df["NIVEL"].astype(str) == nivel_elegido].copy()

grupos, dias_seleccionados, meses_aproximados = seleccionar_periodos_60_meses(
    df_nivel,
    meses_objetivo=meses_objetivo,
    minimo_modulos=minimo_modulos,
    minimo_horas=minimo_horas,
)


# =====================================================
# RESULTADO
# =====================================================

st.markdown("---")
st.subheader(f"Selección para {nivel_elegido}")

dias_objetivo = int(meses_objetivo) * 30
dias_faltantes = max(0, dias_objetivo - dias_seleccionados)

m1, m2, m3 = st.columns(3)
m1.metric("Días alternados seleccionados", dias_seleccionados)
m2.metric("Meses aproximados", meses_aproximados)
m3.metric("Días que faltan", dias_faltantes)

if dias_seleccionados < dias_objetivo:
    st.warning(
        "Con los datos y mínimos elegidos no se alcanza el objetivo. "
        "Probá bajar los mínimos de carga o revisá las secuencias y fechas."
    )

if not grupos:
    st.info(
        "No se encontraron días con dos o más secuencias activas y carga "
        "horaria positiva que cumplan los mínimos."
    )
    st.stop()

resumen = []

for numero, grupo in enumerate(grupos, start=1):
    dias = (grupo["fecha_hasta"] - grupo["fecha_desde"]).days + 1
    resumen.append({
        "Período": numero,
        "Desde": grupo["fecha_desde"].strftime("%d/%m/%Y"),
        "Hasta": grupo["fecha_hasta"].strftime("%d/%m/%Y"),
        "Días": dias,
        "Meses aprox.": dias // 30,
        "Módulos": int(grupo["modulos"]),
        "Horas cátedra": int(grupo["horas"]),
        "Secuencias": ", ".join(grupo["secuencias"]),
    })

st.dataframe(
    pd.DataFrame(resumen),
    use_container_width=True,
    hide_index=True,
)

with st.expander("Ver filas que respaldan cada período"):
    for numero, grupo in enumerate(grupos, start=1):
        st.markdown(
            f"**Período {numero}: "
            f"{grupo['fecha_desde']:%d/%m/%Y} al "
            f"{grupo['fecha_hasta']:%d/%m/%Y}**"
        )
        st.dataframe(grupo["grupo_df"], use_container_width=True)


# =====================================================
# EXPORTAR EXCEL
# =====================================================

salida = io.BytesIO()

with pd.ExcelWriter(salida, engine="openpyxl") as writer:
    pd.DataFrame(resumen).to_excel(
        writer,
        sheet_name="Resumen",
        index=False,
    )

    for numero, grupo in enumerate(grupos, start=1):
        nombre_hoja = f"Periodo_{numero}"[:31]
        detalle = grupo["grupo_df"].copy()
        detalle.to_excel(writer, sheet_name=nombre_hoja, index=False)

st.download_button(
    "Descargar selección en Excel",
    data=salida.getvalue(),
    file_name="60_meses_alternados_seleccion.xlsx",
    mime=(
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
)