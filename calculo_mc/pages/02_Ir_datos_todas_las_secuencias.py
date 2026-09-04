import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_plotly_events import plotly_events
from io import BytesIO
import re

pd.options.display.date_dayfirst = True

# ---------------------------------
# CONFIGURACION
# ---------------------------------
st.set_page_config(
    page_title="Ir a grafico y tabla todos las secuencias",
    layout="wide"
)

st.title("Datos de todas las Secuencias")

# ---------------------------------
# VALIDACION
# ---------------------------------
if "df_consolidado" not in st.session_state:
    st.warning("Primero carga y procesa los datos en la pagina principal.")
    st.stop()

df = st.session_state["df_consolidado"].copy()

if df.empty:
    st.warning("df_consolidado está vacío.")
    st.stop()

# ---------------------------------
# SESSION STATE
# ---------------------------------
if "barra_seleccionada_02" not in st.session_state:
    st.session_state["barra_seleccionada_02"] = None

if "seleccion_mejor_cargo_02" not in st.session_state:
    st.session_state["seleccion_mejor_cargo_02"] = pd.DataFrame()

if "seleccion_simultaneo_02" not in st.session_state:
    st.session_state["seleccion_simultaneo_02"] = pd.DataFrame()

if "df_mejor_cargo_real_02" not in st.session_state:
    st.session_state["df_mejor_cargo_real_02"] = pd.DataFrame()

# ---------------------------------
# NORMALIZACION DE FECHAS
# ---------------------------------
if "HASTA" in df.columns:
    df["HASTA"] = df["HASTA"].replace("HOY", pd.Timestamp.today())

df["DESDE"] = pd.to_datetime(df["DESDE"], errors="coerce", dayfirst=True)
df["HASTA"] = pd.to_datetime(df["HASTA"], errors="coerce", dayfirst=True)

df = df.dropna(subset=["DESDE", "HASTA"]).copy()

# ---------------------------------
# NORMALIZAR COLUMNAS DE CARGA
# ---------------------------------
if "HORAS_CATEDRA" not in df.columns:
    if "HORAS CATEDRA" in df.columns:
        df["HORAS_CATEDRA"] = pd.to_numeric(df["HORAS CATEDRA"], errors="coerce").fillna(0)
    else:
        df["HORAS_CATEDRA"] = 0

if "MODULOS" not in df.columns:
    df["MODULOS"] = 0

df["HORAS_CATEDRA"] = pd.to_numeric(df["HORAS_CATEDRA"], errors="coerce").fillna(0)
df["MODULOS"] = pd.to_numeric(df["MODULOS"], errors="coerce").fillna(0)

# ---------------------------------
# CREAR NIVEL SI NO EXISTE
# ---------------------------------
if "NIVEL" not in df.columns:
    niveles_dict = {
        "Inicial": ["JI", "JS", "JU", "JM", "JV"],
        "Primaria": ["PP", "EP", "PA", "DA", "DC", "DE"],
        "Especial": ["EE", "EL", "CFI", "ET", "ESPECIAL"],
        "Secundaria": ["MM", "MS", "ES", "ESB", "MT", "BS", "MA", "MC", "AS"],
        "Adulto": ["DM", "CENS", "DF", "DS", "MF", "ADULTOS", "ADULTO", "CFP", "CFL"],
        "Superior": ["IS", "AA", "AT", "AF", "AV", "AC", "AD", "AM", "AP", "FC"],
    }

    def detectar_nivel(escuela):
        if pd.isna(escuela):
            return "Sin Nivel"

        escuela = str(escuela).upper()

        for nivel, codigos in niveles_dict.items():
            if any(cod in escuela for cod in codigos):
                return nivel

        return "Sin Nivel"

    df["NIVEL"] = df["ESCUELA"].apply(detectar_nivel)

# ---------------------------------
# HELPERS
# ---------------------------------
def agregar_a_tabla(df_tabla, fila):
    if fila is None or fila.empty:
        return df_tabla

    fila = fila.copy()

    if df_tabla is None or df_tabla.empty:
        return fila.reset_index(drop=True)

    bar_id = str(fila.iloc[0]["BAR_ID"])
    existentes = df_tabla["BAR_ID"].astype(str).tolist()

    if bar_id in existentes:
        return df_tabla

    return pd.concat([df_tabla, fila], ignore_index=True)


def quitar_de_tabla(df_tabla, bar_id):
    if df_tabla is None or df_tabla.empty:
        return pd.DataFrame()
    return df_tabla[df_tabla["BAR_ID"].astype(str) != str(bar_id)].copy().reset_index(drop=True)


def formatear_tabla(df_):
    if df_ is None or df_.empty:
        return df_
    out = df_.copy()
    for col in ["DESDE", "HASTA", "DESDE_COMUN", "HASTA_COMUN", "DESDE_MEJOR_CARGO", "HASTA_MEJOR_CARGO"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%d/%m/%Y")
    return out


def calcular_tramo_comun_mejor(df_mejor):
    if df_mejor is None or df_mejor.empty:
        return None

    desde_comun = pd.to_datetime(df_mejor["DESDE"]).max()
    hasta_comun = pd.to_datetime(df_mejor["HASTA"]).min()

    if pd.isna(desde_comun) or pd.isna(hasta_comun):
        return None

    hay_solape = desde_comun <= hasta_comun
    dias = (hasta_comun - desde_comun).days + 1 if hay_solape else 0
    meses = round(dias / 30.44, 1) if hay_solape else 0

    return {
        "DESDE_COMUN": desde_comun,
        "HASTA_COMUN": hasta_comun,
        "HAY_SOLAPE": hay_solape,
        "DIAS_COMUN": dias,
        "MESES_COMUN": meses
    }


def construir_mejor_cargo_real(df_mejor):

    if df_mejor is None or df_mejor.empty:
        return pd.DataFrame()

    tramo = calcular_tramo_comun_mejor(df_mejor)

    if tramo is None:
        return pd.DataFrame()

    desde = tramo["DESDE_COMUN"]
    hasta = tramo["HASTA_COMUN"]

    # Buscar la fila vigente durante el período común
    vigente = df_mejor[
        (pd.to_datetime(df_mejor["DESDE"]) <= desde) &
        (pd.to_datetime(df_mejor["HASTA"]) >= desde)
    ].copy()

    if vigente.empty:
        vigente = df_mejor[
            (pd.to_datetime(df_mejor["DESDE"]) <= hasta) &
            (pd.to_datetime(df_mejor["HASTA"]) >= hasta)
        ].copy()

    if vigente.empty:
        vigente = (
            df_mejor
            .sort_values("DESDE")
            .iloc[[0]]
        )

    fila_vigente = vigente.iloc[0]

    fila = {

        "SECUENCIAS_ORIGEN":
            " / ".join(sorted(set(df_mejor["SECUENCIA"].astype(str)))),

        "NIVELES_ORIGEN":
            " / ".join(sorted(set(df_mejor["NIVEL"].astype(str))))
            if "NIVEL" in df_mejor.columns else "",

        "DESDE_COMUN": desde,
        "HASTA_COMUN": hasta,

        "HAY_SOLAPE": tramo["HAY_SOLAPE"],
        "DIAS_COMUN": tramo["DIAS_COMUN"],
        "MESES_COMUN": tramo["MESES_COMUN"],

        "BARRAS_ORIGEN":
            " / ".join(sorted(set(df_mejor["BAR_ID"].astype(str)))),

        # SOLO EL CARGO VIGENTE
        "CARGO": fila_vigente.get("CARGO", ""),
        "ESCUELA": fila_vigente.get("ESCUELA", ""),
        "HORAS_CATEDRA": fila_vigente.get("HORAS_CATEDRA", 0),
        "MODULOS": fila_vigente.get("MODULOS", 0),

        "CANT_BARRAS": len(df_mejor),
    }

    return pd.DataFrame([fila])


def extraer_horas_modulos_desde_cargo(cargo_texto):
    """
    Busca en el texto de CARGO valores de horas cátedra o módulos.

    Reglas:
    - Si aparece MOD., MODULO, MODULOS => el número va a MODULOS
    - Si aparece HS. CATEDRA, HS CATEDRA, CAT., CATEDRAS, HORAS => el número va a HORAS_CATEDRA

    Devuelve: (horas_detectadas, modulos_detectados)
    """
    if pd.isna(cargo_texto):
        return 0.0, 0.0

    txt = str(cargo_texto).upper().strip()
    txt = txt.replace(",", ".")

    horas = 0.0
    modulos = 0.0

    # MODULOS
    patrones_mod = [
        r'(\d+(?:\.\d+)?)\s*MOD(?:\.|ULO|ULOS)?\b',
        r'\bMOD(?:\.|ULO|ULOS)?\s*(\d+(?:\.\d+)?)'
    ]

    # HORAS CATEDRA
    patrones_hs = [
        r'(\d+(?:\.\d+)?)\s*HS?\.?\s*CATEDRA\S*\b',
        r'(\d+(?:\.\d+)?)\s*CAT(?:\.|EDRA|EDRAS)?\b',
        r'(\d+(?:\.\d+)?)\s*HORAS?\b',
        r'\bHS?\.?\s*CATEDRA\S*\s*(\d+(?:\.\d+)?)',
        r'\bCAT(?:\.|EDRA|EDRAS)?\s*(\d+(?:\.\d+)?)',
        r'\bHORAS?\s*(\d+(?:\.\d+)?)'
    ]

    for pat in patrones_mod:
        m = re.search(pat, txt, flags=re.IGNORECASE)
        if m:
            try:
                modulos = float(m.group(1))
                break
            except:
                pass

    for pat in patrones_hs:
        m = re.search(pat, txt, flags=re.IGNORECASE)
        if m:
            try:
                horas = float(m.group(1))
                break
            except:
                pass

    return horas, modulos


def completar_horas_modulos_para_export(df_tabla):
    """
    Completa HORAS_CATEDRA y MODULOS para exportación:
    - si ya vienen con valor > 0, los respeta
    - si vienen vacíos o 0, intenta extraerlos desde CARGO
    """
    if df_tabla is None or df_tabla.empty:
        return pd.DataFrame()

    out = df_tabla.copy()

    if "HORAS_CATEDRA" not in out.columns:
        out["HORAS_CATEDRA"] = 0.0
    if "MODULOS" not in out.columns:
        out["MODULOS"] = 0.0

    out["HORAS_CATEDRA"] = pd.to_numeric(out["HORAS_CATEDRA"], errors="coerce").fillna(0.0)
    out["MODULOS"] = pd.to_numeric(out["MODULOS"], errors="coerce").fillna(0.0)

    for idx in out.index:
        cargo = out.at[idx, "CARGO"] if "CARGO" in out.columns else ""
        horas_detectadas, modulos_detectados = extraer_horas_modulos_desde_cargo(cargo)

        if float(out.at[idx, "HORAS_CATEDRA"]) <= 0 and horas_detectadas > 0:
            out.at[idx, "HORAS_CATEDRA"] = horas_detectadas

        if float(out.at[idx, "MODULOS"]) <= 0 and modulos_detectados > 0:
            out.at[idx, "MODULOS"] = modulos_detectados

    return out


def reordenar_columnas_export(df_tabla):
    """
    Fuerza el orden de columnas del export para que:
    G = HORAS_CATEDRA
    H = MODULOS

    Orden final:
    A BAR_ID
    B SECUENCIA
    C DESDE
    D HASTA
    E ESCUELA
    F CARGO
    G HORAS_CATEDRA
    H MODULOS
    I DIAS
    J MESES_APROX
    K CUMPLE_36M
    + resto de columnas al final
    """
    if df_tabla is None or df_tabla.empty:
        return df_tabla

    df_out = df_tabla.copy()

    columnas_base = [
        "BAR_ID",
        "SECUENCIA",
        "DESDE",
        "HASTA",
        "ESCUELA",
        "CARGO",
        "HORAS_CATEDRA",
        "MODULOS",
        "DIAS",
        "MESES_APROX",
        "CUMPLE_36M",
    ]

    columnas_presentes = [c for c in columnas_base if c in df_out.columns]
    columnas_restantes = [c for c in df_out.columns if c not in columnas_presentes]

    return df_out[columnas_presentes + columnas_restantes]


def exportar_excel(df_mejor, df_sim, df_resumen):
    output = BytesIO()

    # -----------------------------------
    # PREPARAR MEJOR CARGO
    # -----------------------------------
    if df_mejor is not None and not df_mejor.empty:
        df_mejor_exp = formatear_tabla(df_mejor).copy()
        df_mejor_exp = completar_horas_modulos_para_export(df_mejor_exp)

        if "NIVEL" in df_mejor_exp.columns:
            df_mejor_exp = df_mejor_exp.drop(columns=["NIVEL"])

        df_mejor_exp = reordenar_columnas_export(df_mejor_exp)

        total_horas_mejor = pd.to_numeric(
            df_mejor_exp.get("HORAS_CATEDRA", 0), errors="coerce"
        ).fillna(0).sum()

        total_modulos_mejor = pd.to_numeric(
            df_mejor_exp.get("MODULOS", 0), errors="coerce"
        ).fillna(0).sum()

        fila_total_mejor = {col: "" for col in df_mejor_exp.columns}
        if "CARGO" in df_mejor_exp.columns:
            fila_total_mejor["CARGO"] = "TOTAL"
        elif len(df_mejor_exp.columns) > 0:
            fila_total_mejor[df_mejor_exp.columns[0]] = "TOTAL"

        if "HORAS_CATEDRA" in df_mejor_exp.columns:
            fila_total_mejor["HORAS_CATEDRA"] = total_horas_mejor
        if "MODULOS" in df_mejor_exp.columns:
            fila_total_mejor["MODULOS"] = total_modulos_mejor

        df_mejor_exp = pd.concat(
            [df_mejor_exp, pd.DataFrame([fila_total_mejor])],
            ignore_index=True
        )

    else:
        df_mejor_exp = pd.DataFrame({"INFO": ["Sin datos"]})
        total_horas_mejor = 0
        total_modulos_mejor = 0

    # -----------------------------------
    # PREPARAR SIMULTANEO
    # -----------------------------------
    if df_sim is not None and not df_sim.empty:
        df_sim_exp = formatear_tabla(df_sim).copy()
        df_sim_exp = completar_horas_modulos_para_export(df_sim_exp)

        if "NIVEL" in df_sim_exp.columns:
            df_sim_exp = df_sim_exp.drop(columns=["NIVEL"])

        df_sim_exp = reordenar_columnas_export(df_sim_exp)

        total_horas_sim = pd.to_numeric(
            df_sim_exp.get("HORAS_CATEDRA", 0), errors="coerce"
        ).fillna(0).sum()

        total_modulos_sim = pd.to_numeric(
            df_sim_exp.get("MODULOS", 0), errors="coerce"
        ).fillna(0).sum()

        fila_total_sim = {col: "" for col in df_sim_exp.columns}
        if "CARGO" in df_sim_exp.columns:
            fila_total_sim["CARGO"] = "TOTAL"
        elif len(df_sim_exp.columns) > 0:
            fila_total_sim[df_sim_exp.columns[0]] = "TOTAL"

        if "HORAS_CATEDRA" in df_sim_exp.columns:
            fila_total_sim["HORAS_CATEDRA"] = total_horas_sim
        if "MODULOS" in df_sim_exp.columns:
            fila_total_sim["MODULOS"] = total_modulos_sim

        df_sim_exp = pd.concat(
            [df_sim_exp, pd.DataFrame([fila_total_sim])],
            ignore_index=True
        )

    else:
        df_sim_exp = pd.DataFrame({"INFO": ["Sin datos"]})
        total_horas_sim = 0
        total_modulos_sim = 0

    # -----------------------------------
    # PREPARAR RESUMEN
    # -----------------------------------
    if df_resumen is not None and not df_resumen.empty:
        df_resumen_exp = formatear_tabla(df_resumen).copy()

        if "NIVELES_ORIGEN" in df_resumen_exp.columns:
            df_resumen_exp = df_resumen_exp.drop(columns=["NIVELES_ORIGEN"])

        # Renombrar período del mejor cargo
        if "DESDE_COMUN" in df_resumen_exp.columns:
            df_resumen_exp = df_resumen_exp.rename(
                columns={"DESDE_COMUN": "DESDE_MEJOR_CARGO"}
            )
        if "HASTA_COMUN" in df_resumen_exp.columns:
            df_resumen_exp = df_resumen_exp.rename(
                columns={"HASTA_COMUN": "HASTA_MEJOR_CARGO"}
            )

        # Agregar totales
        df_resumen_exp["HORAS_CATEDRA_MEJOR_CARGO"] = total_horas_mejor
        df_resumen_exp["MODULOS_MEJOR_CARGO"] = total_modulos_mejor
        df_resumen_exp["HORAS_CATEDRA_SIMULTANEO"] = total_horas_sim
        df_resumen_exp["MODULOS_SIMULTANEO"] = total_modulos_sim

    else:
        df_resumen_exp = pd.DataFrame([{
            "DESDE_MEJOR_CARGO": "",
            "HASTA_MEJOR_CARGO": "",
            "HORAS_CATEDRA_MEJOR_CARGO": total_horas_mejor,
            "MODULOS_MEJOR_CARGO": total_modulos_mejor,
            "HORAS_CATEDRA_SIMULTANEO": total_horas_sim,
            "MODULOS_SIMULTANEO": total_modulos_sim
        }])

    # -----------------------------------
    # EXPORTAR
    # -----------------------------------
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_mejor_exp.to_excel(writer, index=False, sheet_name="mejor_cargo_barras")
        df_sim_exp.to_excel(writer, index=False, sheet_name="simultaneo_barras")
        df_resumen_exp.to_excel(writer, index=False, sheet_name="resumen_mejor_cargo")

    output.seek(0)
    return output.getvalue()


def consolidar_periodos(df_in):
    """
    Consolida períodos continuos por SECUENCIA.

    Una barra continúa únicamente si:

    - no hay corte de fechas
    - la carga (HORAS_CATEDRA/MODULOS) es la misma

    Si cambia la carga comienza una barra nueva.
    """

    if df_in.empty:
        return pd.DataFrame()

    df = df_in.copy()

    df["HORAS_CATEDRA"] = (
        pd.to_numeric(df.get("HORAS_CATEDRA", 0), errors="coerce")
        .fillna(0)
    )

    df["MODULOS"] = (
        pd.to_numeric(df.get("MODULOS", 0), errors="coerce")
        .fillna(0)
    )

    # Si la carga no vino informada intenta obtenerla desde el texto del cargo
    if "CARGO" in df.columns:
        for idx in df.index:

            horas = float(df.at[idx, "HORAS_CATEDRA"])
            modulos = float(df.at[idx, "MODULOS"])

            if horas == 0 and modulos == 0:

                hs, mods = extraer_horas_modulos_desde_cargo(
                    df.at[idx, "CARGO"]
                )

                df.at[idx, "HORAS_CATEDRA"] = hs
                df.at[idx, "MODULOS"] = mods

    df = (
        df.sort_values(["SECUENCIA", "DESDE"])
        .reset_index(drop=True)
    )

    filas = []

    for secuencia, grupo in df.groupby("SECUENCIA"):

        grupo = grupo.sort_values("DESDE")

        inicio = None
        fin = None

        horas_actual = 0.0
        modulos_actual = 0.0

        nivel = ""

        if "NIVEL" in grupo.columns:
            s = grupo["NIVEL"].dropna()
            if not s.empty:
                nivel = str(s.iloc[0])

        cargos = []
        escuelas = []

        historial_horas = []
        historial_modulos = []

        for _, row in grupo.iterrows():

            desde = row["DESDE"]
            hasta = row["HASTA"]

            horas = float(row["HORAS_CATEDRA"])
            modulos = float(row["MODULOS"])

            cargo = str(row.get("CARGO", "")).strip()
            escuela = str(row.get("ESCUELA", "")).strip()

            if inicio is None:

                inicio = desde
                fin = hasta

                horas_actual = horas
                modulos_actual = modulos

                cargos = [cargo]
                escuelas = [escuela]

                historial_horas = [horas]
                historial_modulos = [modulos]

                continue

            continuidad = (
                desde <= fin + pd.Timedelta(days=1)
            )

            misma_carga = (
                horas == horas_actual
                and
                modulos == modulos_actual
            )

            if continuidad and misma_carga:

                fin = max(fin, hasta)

                if cargo not in cargos:
                    cargos.append(cargo)

                if escuela not in escuelas:
                    escuelas.append(escuela)

                historial_horas.append(horas)
                historial_modulos.append(modulos)

            else:

                dias = (fin - inicio).days + 1
                meses = round(dias / 30.44, 1)

                filas.append({

                    "BAR_ID":
                        f"{secuencia}|{inicio:%Y-%m-%d}|{fin:%Y-%m-%d}",

                    "SECUENCIA": str(secuencia),

                    "NIVEL": nivel,

                    "DESDE": inicio,
                    "HASTA": fin,

                    "ESCUELA":
                        " / ".join(escuelas),

                    "CARGO":
                        " / ".join(cargos),

                    "HORAS_CATEDRA":
                        horas_actual,

                    "MODULOS":
                        modulos_actual,

                    "HISTORIAL_HORAS":
                        historial_horas.copy(),

                    "HISTORIAL_MODULOS":
                        historial_modulos.copy(),

                    "DIAS":
                        dias,

                    "MESES_APROX":
                        meses,

                    "CUMPLE_36M":
                        meses >= 36
                })

                # Nueva barra

                inicio = desde
                fin = hasta

                horas_actual = horas
                modulos_actual = modulos

                cargos = [cargo]
                escuelas = [escuela]

                historial_horas = [horas]
                historial_modulos = [modulos]

        # Última barra

        if inicio is not None:

            dias = (fin - inicio).days + 1
            meses = round(dias / 30.44, 1)

            filas.append({

                "BAR_ID":
                    f"{secuencia}|{inicio:%Y-%m-%d}|{fin:%Y-%m-%d}",

                "SECUENCIA": str(secuencia),

                "NIVEL": nivel,

                "DESDE": inicio,
                "HASTA": fin,

                "ESCUELA":
                    " / ".join(escuelas),

                "CARGO":
                    " / ".join(cargos),

                "HORAS_CATEDRA":
                    horas_actual,

                "MODULOS":
                    modulos_actual,

                "HISTORIAL_HORAS":
                    historial_horas.copy(),

                "HISTORIAL_MODULOS":
                    historial_modulos.copy(),

                "DIAS":
                    dias,

                "MESES_APROX":
                    meses,

                "CUMPLE_36M":
                    meses >= 36
            })

    out = pd.DataFrame(filas)

    if out.empty:
        return out

    return (
        out
        .sort_values(["SECUENCIA", "DESDE"])
        .reset_index(drop=True)
    )

# ---------------------------------
# SELECTOR DE NIVEL (LIVIANO)
# ---------------------------------
st.subheader("Linea de tiempo")

niveles_disponibles = sorted(df["NIVEL"].fillna("Sin Nivel").astype(str).unique().tolist())
opciones_nivel = ["Todos los niveles"] + niveles_disponibles

nivel_sel = st.selectbox(
    "Nivel a visualizar",
    opciones_nivel,
    index=0
)

if nivel_sel == "Todos los niveles":
    df_filtrado = df.copy()
    titulo_grafico = "Todos los niveles"
else:
    df_filtrado = df[df["NIVEL"].astype(str) == nivel_sel].copy()
    titulo_grafico = f"Nivel: {nivel_sel}"

if df_filtrado.empty:
    st.info("No hay datos para la selección elegida.")
    st.stop()

df_plot = consolidar_periodos(df_filtrado)

if df_plot.empty:
    st.info("No hay datos consolidados para graficar.")
    st.stop()

# ---------------------------------
# ESTADO DE COLOR DE BARRAS
# ---------------------------------
mejor_ids = set()
sim_ids = set()

if not st.session_state["seleccion_mejor_cargo_02"].empty:
    mejor_ids = set(st.session_state["seleccion_mejor_cargo_02"]["BAR_ID"].astype(str).tolist())

if not st.session_state["seleccion_simultaneo_02"].empty:
    sim_ids = set(st.session_state["seleccion_simultaneo_02"]["BAR_ID"].astype(str).tolist())

def estado_barra(row):
    bar_id = str(row["BAR_ID"])
    if bar_id in mejor_ids:
        return "MEJOR_CARGO"
    if bar_id in sim_ids:
        return "SIMULTANEO"
    if bool(row["CUMPLE_36M"]):
        return "CUMPLE_36M"
    return "NORMAL"

df_plot["ESTADO_BARRA"] = df_plot.apply(estado_barra, axis=1)

df_plot["DESDE_HOVER"] = df_plot["DESDE"].dt.strftime("%d/%m/%Y")
df_plot["HASTA_HOVER"] = df_plot["HASTA"].dt.strftime("%d/%m/%Y")

fecha_min = df_plot["DESDE"].min()
fecha_max = df_plot["HASTA"].max()
margen = pd.Timedelta(days=30)

# ---------------------------------
# GRAFICO ORIGINAL PARCHEADO
# ---------------------------------
st.markdown(f"### {titulo_grafico}")

fig = px.timeline(
    df_plot,
    x_start="DESDE",
    x_end="HASTA",
    y="SECUENCIA",
    color="ESTADO_BARRA",
    color_discrete_map={
        "CUMPLE_36M": "#2ca02c",   # verde
        "NORMAL": "#1f77b4",       # azul
        "MEJOR_CARGO": "#ff7f0e",  # naranja
        "SIMULTANEO": "#9467bd"    # violeta
    },
    custom_data=[
        "BAR_ID",
        "SECUENCIA",
        "NIVEL",
        "ESCUELA",
        "CARGO",
        "DESDE_HOVER",
        "HASTA_HOVER",
        "DIAS",
        "MESES_APROX",
        "HORAS_CATEDRA",
        "MODULOS",
        "CUMPLE_36M"
    ],
)

fig.update_traces(
    hovertemplate=
        "<b>Secuencia:</b> %{customdata[1]}<br>"
        "<b>Nivel:</b> %{customdata[2]}<br>"
        "<b>Escuela:</b> %{customdata[3]}<br>"
        "<b>Cargo:</b> %{customdata[4]}<br>"
        "<b>Desde:</b> %{customdata[5]}<br>"
        "<b>Hasta:</b> %{customdata[6]}<br>"
        "<b>Días:</b> %{customdata[7]}<br>"
        "<b>Meses aprox:</b> %{customdata[8]}<br>"
        "<b>Horas cátedra:</b> %{customdata[9]}<br>"
        "<b>Módulos:</b> %{customdata[10]}<br>"
        "<b>36 meses o más:</b> %{customdata[11]}"
        "<extra></extra>"
)

fig.update_yaxes(autorange="reversed")
fig.update_xaxes(range=[fecha_min - margen, fecha_max + margen])

fig.update_layout(
    height=max(500, len(df_plot["SECUENCIA"].unique()) * 30),
    showlegend=True,
    hoverlabel_align="left",
    template="plotly_white",
    xaxis_title="Periodo",
    yaxis_title="Secuencia",
    legend_title_text="Estado"
)

selected_points = plotly_events(
    fig,
    click_event=True,
    select_event=False,
    hover_event=False,
    override_height=max(500, len(df_plot["SECUENCIA"].unique()) * 30),
    key=f"plot_{nivel_sel}"
)

st.caption("Verde = barra con 36 meses o más | Naranja = Mejor Cargo | Violeta = Simultáneo")

# ---------------------------------
# CAPTURAR BARRA SELECCIONADA
# ---------------------------------
if selected_points:
    try:
        point = selected_points[0]
        curve_number = point.get("curveNumber")
        point_index = point.get("pointIndex")

        if curve_number is not None and point_index is not None:
            trace = fig.data[curve_number]

            if hasattr(trace, "customdata") and trace.customdata is not None:
                if point_index < len(trace.customdata):
                    bar_id = trace.customdata[point_index][0]

                    fila_sel = df_plot[df_plot["BAR_ID"].astype(str) == str(bar_id)].copy()
                    if not fila_sel.empty:
                        st.session_state["barra_seleccionada_02"] = fila_sel.iloc[0].to_dict()
    except Exception as e:
        st.warning(f"No se pudo capturar la barra seleccionada: {e}")

# ---------------------------------
# PANEL DE BARRA SELECCIONADA
# ---------------------------------
st.markdown("---")
st.subheader("Barra seleccionada")

barra_sel = st.session_state["barra_seleccionada_02"]

if barra_sel is None:
    st.info("Tocá una barra del gráfico para seleccionarla.")
else:
    fila_barra = pd.DataFrame([barra_sel]).copy()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("Secuencia", barra_sel.get("SECUENCIA", "-"))
    with c2:
        st.metric("Desde", pd.to_datetime(barra_sel.get("DESDE")).strftime("%d/%m/%Y") if pd.notna(barra_sel.get("DESDE")) else "-")
    with c3:
        st.metric("Hasta", pd.to_datetime(barra_sel.get("HASTA")).strftime("%d/%m/%Y") if pd.notna(barra_sel.get("HASTA")) else "-")
    with c4:
        st.metric("Meses aprox", barra_sel.get("MESES_APROX", 0))
    with c5:
        st.metric("Horas cátedra", barra_sel.get("HORAS_CATEDRA", 0))
    with c6:
        st.metric("Módulos", barra_sel.get("MODULOS", 0))

    st.markdown(f"**Nivel:** {barra_sel.get('NIVEL', '')}")
    st.markdown(f"**Cargo:** {barra_sel.get('CARGO', '')}")
    st.markdown(f"**Escuela:** {barra_sel.get('ESCUELA', '')}")
    st.markdown(f"**BAR_ID:** `{barra_sel.get('BAR_ID', '')}`")

    b1, b2, b3 = st.columns(3)

    with b1:
        if st.button("Agregar a Mejor Cargo", use_container_width=True):
            st.session_state["seleccion_mejor_cargo_02"] = agregar_a_tabla(
                st.session_state["seleccion_mejor_cargo_02"],
                fila_barra
            )
            st.rerun()

    with b2:
        if st.button("Agregar a Simultáneo", use_container_width=True):
            st.session_state["seleccion_simultaneo_02"] = agregar_a_tabla(
                st.session_state["seleccion_simultaneo_02"],
                fila_barra
            )
            st.rerun()

    with b3:
        if st.button("Quitar de selecciones", use_container_width=True):
            bar_id = barra_sel.get("BAR_ID")
            st.session_state["seleccion_mejor_cargo_02"] = quitar_de_tabla(
                st.session_state["seleccion_mejor_cargo_02"], bar_id
            )
            st.session_state["seleccion_simultaneo_02"] = quitar_de_tabla(
                st.session_state["seleccion_simultaneo_02"], bar_id
            )
            st.rerun()

# ---------------------------------
# TABLAS DE SELECCION
# ---------------------------------
st.markdown("---")
st.subheader("Selecciones en construcción")

tab_mejor, tab_sim, tab_export = st.tabs(["Mejor Cargo", "Simultáneo", "Exportar"])

# ---------------------------------
# TAB MEJOR CARGO
# ---------------------------------
with tab_mejor:
    df_mejor = st.session_state["seleccion_mejor_cargo_02"].copy()

    if df_mejor.empty:
        st.info("Todavía no agregaste barras a Mejor Cargo.")
        st.session_state["df_mejor_cargo_real_02"] = pd.DataFrame()
    else:
        tramo = calcular_tramo_comun_mejor(df_mejor)
        df_mejor_real = construir_mejor_cargo_real(df_mejor)
        st.session_state["df_mejor_cargo_real_02"] = df_mejor_real.copy()

        st.markdown("### Barras elegidas para Mejor Cargo")
        mostrar_cols = [
            "BAR_ID", "SECUENCIA", "NIVEL", "DESDE", "HASTA",
            "ESCUELA", "CARGO", "DIAS", "MESES_APROX",
            "HORAS_CATEDRA", "MODULOS", "CUMPLE_36M"
        ]
        mostrar_cols = [c for c in mostrar_cols if c in df_mejor.columns]

        st.dataframe(
            formatear_tabla(df_mejor[mostrar_cols].copy()),
            use_container_width=True,
            height=280
        )

        st.markdown("### Tramo común del Mejor Cargo")
        if tramo is None:
            st.warning("No se pudo calcular el tramo común.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Desde común", tramo["DESDE_COMUN"].strftime("%d/%m/%Y"))
            with c2:
                st.metric("Hasta común", tramo["HASTA_COMUN"].strftime("%d/%m/%Y"))
            with c3:
                st.metric("Días comunes", tramo["DIAS_COMUN"])
            with c4:
                st.metric("Meses comunes", tramo["MESES_COMUN"])

            if tramo["HAY_SOLAPE"]:
                st.success("Las barras seleccionadas tienen tramo común.")
            else:
                st.error("Las barras seleccionadas NO tienen tramo común (DESDE mayor > HASTA menor).")

        st.markdown("### Mejor Cargo real armado desde la selección")
        if df_mejor_real.empty:
            st.info("No se pudo construir el mejor cargo real.")
        else:
            st.dataframe(
                formatear_tabla(df_mejor_real),
                use_container_width=True,
                height=180
            )

        if st.button("Limpiar Mejor Cargo", use_container_width=True):
            st.session_state["seleccion_mejor_cargo_02"] = pd.DataFrame()
            st.session_state["df_mejor_cargo_real_02"] = pd.DataFrame()
            st.rerun()

# ---------------------------------
# TAB SIMULTANEO
# ---------------------------------
with tab_sim:
    df_sim = st.session_state["seleccion_simultaneo_02"].copy()

    if df_sim.empty:
        st.info("Todavía no agregaste barras a Simultáneo.")
    else:
        mostrar_cols = [
            "BAR_ID", "SECUENCIA", "NIVEL", "DESDE", "HASTA",
            "ESCUELA", "CARGO", "DIAS", "MESES_APROX",
            "HORAS_CATEDRA", "MODULOS", "CUMPLE_36M"
        ]
        mostrar_cols = [c for c in mostrar_cols if c in df_sim.columns]

        st.dataframe(
            formatear_tabla(df_sim[mostrar_cols].copy()),
            use_container_width=True,
            height=300
        )

        if st.button("Limpiar Simultáneo", use_container_width=True):
            st.session_state["seleccion_simultaneo_02"] = pd.DataFrame()
            st.rerun()

# ---------------------------------
# TAB EXPORTAR
# ---------------------------------
with tab_export:
    st.markdown("### Exportar selección actual")

    # Mostrar resumen rápido en pantalla antes de exportar
    df_resumen_export = st.session_state["df_mejor_cargo_real_02"].copy()

    if df_resumen_export is not None and not df_resumen_export.empty:
        df_resumen_preview = df_resumen_export.copy()
        if "DESDE_COMUN" in df_resumen_preview.columns:
            df_resumen_preview = df_resumen_preview.rename(columns={"DESDE_COMUN": "DESDE_MEJOR_CARGO"})
        if "HASTA_COMUN" in df_resumen_preview.columns:
            df_resumen_preview = df_resumen_preview.rename(columns={"HASTA_COMUN": "HASTA_MEJOR_CARGO"})
        if "NIVELES_ORIGEN" in df_resumen_preview.columns:
            df_resumen_preview = df_resumen_preview.drop(columns=["NIVELES_ORIGEN"])

        st.markdown("#### Resumen del mejor cargo a exportar")
        st.dataframe(
            formatear_tabla(df_resumen_preview),
            use_container_width=True,
            height=180
        )

    excel_bytes = exportar_excel(
        st.session_state["seleccion_mejor_cargo_02"],
        st.session_state["seleccion_simultaneo_02"],
        st.session_state["df_mejor_cargo_real_02"]
    )

    st.download_button(
        label="Descargar Excel de selección",
        data=excel_bytes,
        file_name="seleccion_mejor_cargo_y_simultaneos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# ---------------------------------
# TABLA DETALLE GENERAL
# ---------------------------------
with st.expander("Ver datos del consolidado"):
    st.dataframe(
        df.sort_values(["SECUENCIA", "DESDE"]),
        use_container_width=True,
        height=450
    )

# ---------------------------------
# INFO FINAL
# ---------------------------------
st.caption(
    "Versión liviana: un único gráfico con selector de nivel (incluye Todos los niveles), "
    "manteniendo selección de barras para Mejor Cargo y Simultáneo, con exportación completa."
)