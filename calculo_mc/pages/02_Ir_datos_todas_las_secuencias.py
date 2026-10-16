import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_plotly_events import plotly_events
from io import BytesIO
import re
from itertools import combinations

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

if "df_simultaneo_real_02" not in st.session_state:
    st.session_state["df_simultaneo_real_02"] = pd.DataFrame()

if "df_mejor_cargo_detalle_02" not in st.session_state:
    st.session_state["df_mejor_cargo_detalle_02"] = pd.DataFrame()

if "df_simultaneo_detalle_02" not in st.session_state:
    st.session_state["df_simultaneo_detalle_02"] = pd.DataFrame()

if "opcion_mejor_cargo_02" not in st.session_state:
    st.session_state["opcion_mejor_cargo_02"] = 0

if "opcion_simultaneo_02" not in st.session_state:
    st.session_state["opcion_simultaneo_02"] = 0

if "franja_36_inicio_02" not in st.session_state:
    st.session_state["franja_36_inicio_02"] = None

# ---------------------------------
# NORMALIZACION DE FECHAS
# ---------------------------------
if "HASTA" in df.columns:
    df["HASTA"] = df["HASTA"].replace("HOY", pd.Timestamp.today())

df["DESDE"] = pd.to_datetime(df["DESDE"], errors="coerce", dayfirst=True)
df["HASTA"] = pd.to_datetime(df["HASTA"], errors="coerce", dayfirst=True)

df = df.dropna(subset=["DESDE", "HASTA"]).copy()
df = df.reset_index(drop=False).rename(columns={"index": "ORIGEN_ID"})

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


def calcular_opciones_mejor_cargo(df_mejor, df_consolidado=None, limite=5):
    """Genera las mejores combinaciones de secuencias con 36 meses o más."""
    if df_mejor is None or df_mejor.empty:
        return []

    trayectorias = (
        df_mejor.assign(
            DESDE=pd.to_datetime(df_mejor["DESDE"], errors="coerce"),
            HASTA=pd.to_datetime(df_mejor["HASTA"], errors="coerce")
        )
        .groupby("SECUENCIA", as_index=False)
        .agg(DESDE=("DESDE", "min"), HASTA=("HASTA", "max"))
    )

    if trayectorias.empty:
        return []

    candidatos = []
    registros = list(trayectorias.itertuples(index=False))
    minimo_participantes = 1 if len(registros) == 1 else 2
    for cantidad in range(minimo_participantes, len(registros) + 1):
        for grupo in combinations(registros, cantidad):
            desde = max(fila.DESDE for fila in grupo)
            hasta = min(fila.HASTA for fila in grupo)
            fin_36_meses = desde + pd.DateOffset(months=36) - pd.Timedelta(days=1)
            if hasta < fin_36_meses:
                continue

            incluidas = [str(fila.SECUENCIA) for fila in grupo]
            excluidas = [
                str(secuencia) for secuencia in trayectorias["SECUENCIA"]
                if str(secuencia) not in incluidas
            ]
            candidatos.append({
                "DESDE_COMUN": desde,
                "HASTA_COMUN": hasta,
                "HAY_SOLAPE": True,
                "CUMPLE_36M": True,
                "DIAS_COMUN": (hasta - desde).days + 1,
                "MESES_COMUN": round(((hasta - desde).days + 1) / 30.44, 1),
                "SECUENCIAS_INCLUIDAS": incluidas,
                "SECUENCIAS_EXCLUIDAS": excluidas,
            })

    candidatos.sort(
        key=lambda c: (len(c["SECUENCIAS_INCLUIDAS"]), c["DIAS_COMUN"], c["DESDE_COMUN"]),
        reverse=True,
    )
    if df_consolidado is None:
        return candidatos[:limite]

    mejor_por_firma = {}
    for candidato in candidatos:
        firma = firma_carga_alternativa(df_mejor, df_consolidado, candidato)
        actual = mejor_por_firma.get(firma)
        if actual is None or (
            candidato["DIAS_COMUN"], len(candidato["SECUENCIAS_INCLUIDAS"])
        ) > (
            actual["DIAS_COMUN"], len(actual["SECUENCIAS_INCLUIDAS"])
        ):
            mejor_por_firma[firma] = candidato

    alternativas = list(mejor_por_firma.values())
    for alternativa in alternativas:
        alternativa.update(
            perfil_valor_alternativa(df_mejor, df_consolidado, alternativa)
        )

    alternativas.sort(
        key=lambda c: (
            c["PRIORIDAD_CARGO"],
            c["TOTAL_MODULOS"] + c["TOTAL_HORAS"],
            c["TOTAL_MODULOS"],
            c["TOTAL_HORAS"],
            len(c["SECUENCIAS_INCLUIDAS"]),
            c["DIAS_COMUN"],
        ),
        reverse=True,
    )
    return alternativas[:limite]


def calcular_tramo_comun_mejor(df_mejor, indice_opcion=0, df_consolidado=None):
    opciones = calcular_opciones_mejor_cargo(df_mejor, df_consolidado)
    if not opciones:
        return {
            "DESDE_COMUN": pd.NaT,
            "HASTA_COMUN": pd.NaT,
            "HAY_SOLAPE": False,
            "CUMPLE_36M": False,
            "DIAS_COMUN": 0,
            "MESES_COMUN": 0,
            "SECUENCIAS_INCLUIDAS": [],
            "SECUENCIAS_EXCLUIDAS": [],
        }
    return opciones[min(max(indice_opcion, 0), len(opciones) - 1)]


def _normalizar_carga_efectiva(df_tabla):
    out = completar_horas_modulos_para_export(df_tabla)
    if out.empty:
        return out

    out["TIPO_CARGA_EFECTIVA"] = out.apply(
        lambda r: "MODULOS" if r["MODULOS"] > 0 else (
            "HORAS_CATEDRA" if r["HORAS_CATEDRA"] > 0 else "SIN_CARGA"
        ),
        axis=1,
    )
    out["CARGA_EFECTIVA"] = out.apply(
        lambda r: r["MODULOS"] if r["MODULOS"] > 0 else r["HORAS_CATEDRA"],
        axis=1,
    )
    return out


def prioridad_calidad_cargo(cargo):
    texto = str(cargo or "").upper()
    if "VICEDIRECT" in texto or "VICE DIRECT" in texto:
        return 500, "Vicedirector/a"
    if "DIRECTOR" in texto:
        return 600, "Director/a"
    if "INICIAL" in texto or "JARDIN" in texto:
        return 400, "Maestro/a de Inicial"
    if "MAESTR" in texto and "GRADO" in texto:
        return 350, "Maestro/a de Grado"
    if "PRECEPTOR" in texto:
        return 300, "Preceptor/a"
    return 0, "Sin prioridad especial"


def perfil_valor_alternativa(df_barras, df_consolidado, tramo):
    ids_origen = set()
    for ids in df_barras.get("ORIGEN_IDS", pd.Series(dtype=object)):
        if isinstance(ids, (list, tuple, set)):
            ids_origen.update(ids)
    detalle = (
        df_consolidado[df_consolidado["ORIGEN_ID"].isin(ids_origen)].copy()
        if ids_origen else df_consolidado.copy()
    )
    detalle = detalle[
        detalle["SECUENCIA"].astype(str).isin(tramo["SECUENCIAS_INCLUIDAS"])
        & (detalle["DESDE"] <= tramo["HASTA_COMUN"])
        & (detalle["HASTA"] >= tramo["DESDE_COMUN"])
    ].copy()
    if detalle.empty:
        return {
            "TOTAL_HORAS": 0.0, "TOTAL_MODULOS": 0.0,
            "PRIORIDAD_CARGO": 0, "CARGO_PRIORITARIO": "Sin datos",
        }

    detalle = _normalizar_carga_efectiva(detalle).sort_values(
        ["SECUENCIA", "CARGA_EFECTIVA", "DESDE"], ascending=[True, True, False]
    )
    elegida = detalle.groupby("SECUENCIA", as_index=False).first()
    horas = pd.to_numeric(elegida["HORAS_CATEDRA"], errors="coerce").fillna(0).sum()
    modulos = pd.to_numeric(elegida["MODULOS"], errors="coerce").fillna(0).sum()
    prioridades = [prioridad_calidad_cargo(cargo) for cargo in elegida.get("CARGO", [])]
    prioridad, cargo_prioritario = max(prioridades, default=(0, "Sin prioridad especial"))
    return {
        "TOTAL_HORAS": round(float(horas), 4),
        "TOTAL_MODULOS": round(float(modulos), 4),
        "PRIORIDAD_CARGO": prioridad,
        "CARGO_PRIORITARIO": cargo_prioritario,
    }


def firma_carga_alternativa(df_barras, df_consolidado, tramo):
    perfil = perfil_valor_alternativa(df_barras, df_consolidado, tramo)
    return (
        perfil["PRIORIDAD_CARGO"], perfil["TOTAL_HORAS"], perfil["TOTAL_MODULOS"]
    )


def reconstruir_detalle_seleccion(df_barras, df_consolidado, indice_opcion=0):
    if df_barras is None or df_barras.empty:
        return pd.DataFrame(), None

    tramo = calcular_tramo_comun_mejor(df_barras, indice_opcion, df_consolidado)
    if tramo is None or not tramo["HAY_SOLAPE"]:
        return pd.DataFrame(), tramo

    ids_origen = set()
    for ids in df_barras.get("ORIGEN_IDS", pd.Series(dtype=object)):
        if isinstance(ids, (list, tuple, set)):
            ids_origen.update(ids)

    if ids_origen:
        detalle = df_consolidado[df_consolidado["ORIGEN_ID"].isin(ids_origen)].copy()
    else:
        partes = []
        for _, barra in df_barras.iterrows():
            partes.append(df_consolidado[
                (df_consolidado["SECUENCIA"].astype(str) == str(barra["SECUENCIA"]))
                & (df_consolidado["DESDE"] <= barra["HASTA"])
                & (df_consolidado["HASTA"] >= barra["DESDE"])
            ])
        detalle = pd.concat(partes, ignore_index=False).drop_duplicates("ORIGEN_ID") if partes else pd.DataFrame()

    detalle = detalle[
        (detalle["DESDE"] <= tramo["HASTA_COMUN"])
        & (detalle["HASTA"] >= tramo["DESDE_COMUN"])
        & (detalle["SECUENCIA"].astype(str).isin(tramo["SECUENCIAS_INCLUIDAS"]))
    ].copy()
    if detalle.empty:
        return detalle, tramo

    detalle = _normalizar_carga_efectiva(detalle)
    detalle["DESDE_COMUN"] = tramo["DESDE_COMUN"]
    detalle["HASTA_COMUN"] = tramo["HASTA_COMUN"]
    detalle["BARRAS_SELECCIONADAS"] = " / ".join(sorted(df_barras["BAR_ID"].astype(str).unique()))
    return detalle.sort_values(["SECUENCIA", "DESDE", "HASTA"]), tramo


def construir_mejor_cargo_real(df_barras, df_consolidado, indice_opcion=0):
    detalle, tramo = reconstruir_detalle_seleccion(df_barras, df_consolidado, indice_opcion)
    if detalle.empty or tramo is None:
        return pd.DataFrame()

    candidatos = detalle.sort_values(
        ["SECUENCIA", "CARGA_EFECTIVA", "DESDE"],
        ascending=[True, True, False],
    )
    resumen = candidatos.groupby("SECUENCIA", as_index=False).first()
    resumen["DESDE_COMUN"] = tramo["DESDE_COMUN"]
    resumen["HASTA_COMUN"] = tramo["HASTA_COMUN"]
    resumen["DIAS_COMUN"] = tramo["DIAS_COMUN"]
    resumen["MESES_COMUN"] = tramo["MESES_COMUN"]
    resumen["HAY_SOLAPE"] = tramo["HAY_SOLAPE"]
    cantidades = detalle.groupby("SECUENCIA")["ORIGEN_ID"].size()
    resumen["CANT_FILAS_RECONSTRUIDAS"] = resumen["SECUENCIA"].map(cantidades).fillna(0).astype(int)
    return resumen


def extraer_horas_modulos_desde_cargo(cargo_texto):
    if pd.isna(cargo_texto):
        return 0.0, 0.0

    txt = str(cargo_texto).upper().strip()
    txt = txt.replace(",", ".")

    horas = 0.0
    modulos = 0.0

    patrones_mod = [
        r'(\d+(?:\.\d+)?)\s*MOD(?:\.|ULO|ULOS)?\b',
        r'\bMOD(?:\.|ULO|ULOS)?\s*(\d+(?:\.\d+)?)'
    ]

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


def _totales_carga(df_detalle, df_resumen):
    fuente = df_resumen if df_resumen is not None and not df_resumen.empty else df_detalle
    if fuente is None or fuente.empty:
        return 0, 0
    fuente = completar_horas_modulos_para_export(fuente)
    return (
        pd.to_numeric(fuente.get("HORAS_CATEDRA", 0), errors="coerce").fillna(0).sum(),
        pd.to_numeric(fuente.get("MODULOS", 0), errors="coerce").fillna(0).sum(),
    )


def metricas_seleccion(df_resumen):
    horas, modulos = _totales_carga(pd.DataFrame(), df_resumen)
    if df_resumen is None or df_resumen.empty:
        return horas, modulos, []
    cargos = [
        str(cargo) for cargo in df_resumen.get("CARGO", pd.Series(dtype=object)).dropna().unique()
        if str(cargo).strip()
    ]
    return horas, modulos, cargos


def exportar_excel(
    df_mejor, df_sim, df_resumen, df_resumen_sim,
    opciones_mejor=None, df_barras_mejor=None, df_consolidado=None,
    opciones_sim=None, df_barras_sim=None,
):
    output = BytesIO()

    # MEJOR CARGO
    if df_mejor is not None and not df_mejor.empty:
        df_mejor_exp = formatear_tabla(df_mejor).copy()
        df_mejor_exp = completar_horas_modulos_para_export(df_mejor_exp)

        if "NIVEL" in df_mejor_exp.columns:
            df_mejor_exp = df_mejor_exp.drop(columns=["NIVEL"])

        df_mejor_exp = reordenar_columnas_export(df_mejor_exp)
        total_horas_mejor, total_modulos_mejor = _totales_carga(df_mejor, df_resumen)

        fila_total_mejor = {col: "" for col in df_mejor_exp.columns}
        if "CARGO" in df_mejor_exp.columns:
            fila_total_mejor["CARGO"] = "TOTAL"
        elif len(df_mejor_exp.columns) > 0:
            fila_total_mejor[df_mejor_exp.columns[0]] = "TOTAL"

        if "HORAS_CATEDRA" in df_mejor_exp.columns:
            fila_total_mejor["HORAS_CATEDRA"] = total_horas_mejor
        if "MODULOS" in df_mejor_exp.columns:
            fila_total_mejor["MODULOS"] = total_modulos_mejor

        df_mejor_exp = pd.concat([df_mejor_exp, pd.DataFrame([fila_total_mejor])], ignore_index=True)
    else:
        df_mejor_exp = pd.DataFrame({"INFO": ["Sin datos"]})
        total_horas_mejor, total_modulos_mejor = 0, 0

    # SIMULTANEO
    if df_sim is not None and not df_sim.empty:
        df_sim_exp = formatear_tabla(df_sim).copy()
        df_sim_exp = completar_horas_modulos_para_export(df_sim_exp)

        if "NIVEL" in df_sim_exp.columns:
            df_sim_exp = df_sim_exp.drop(columns=["NIVEL"])

        df_sim_exp = reordenar_columnas_export(df_sim_exp)
        total_horas_sim, total_modulos_sim = _totales_carga(df_sim, df_resumen_sim)

        fila_total_sim = {col: "" for col in df_sim_exp.columns}
        if "CARGO" in df_sim_exp.columns:
            fila_total_sim["CARGO"] = "TOTAL"
        elif len(df_sim_exp.columns) > 0:
            fila_total_sim[df_sim_exp.columns[0]] = "TOTAL"

        if "HORAS_CATEDRA" in df_sim_exp.columns:
            fila_total_sim["HORAS_CATEDRA"] = total_horas_sim
        if "MODULOS" in df_sim_exp.columns:
            fila_total_sim["MODULOS"] = total_modulos_sim

        df_sim_exp = pd.concat([df_sim_exp, pd.DataFrame([fila_total_sim])], ignore_index=True)
    else:
        df_sim_exp = pd.DataFrame({"INFO": ["Sin datos"]})
        total_horas_sim, total_modulos_sim = 0, 0

    # RESUMEN
    if df_resumen is not None and not df_resumen.empty:
        df_resumen_exp = formatear_tabla(df_resumen).copy()

        if "NIVELES_ORIGEN" in df_resumen_exp.columns:
            df_resumen_exp = df_resumen_exp.drop(columns=["NIVELES_ORIGEN"])

        if "DESDE_COMUN" in df_resumen_exp.columns:
            df_resumen_exp = df_resumen_exp.rename(columns={"DESDE_COMUN": "DESDE_MEJOR_CARGO"})
        if "HASTA_COMUN" in df_resumen_exp.columns:
            df_resumen_exp = df_resumen_exp.rename(columns={"HASTA_COMUN": "HASTA_MEJOR_CARGO"})

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

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_mejor_exp.to_excel(writer, index=False, sheet_name="mejor_cargo")
        df_sim_exp.to_excel(writer, index=False, sheet_name="simultaneo")
        df_resumen_exp.to_excel(writer, index=False, sheet_name="resumen_mejor_cargo")

        if opciones_mejor and df_barras_mejor is not None and df_consolidado is not None:
            resumen_opciones = []
            for indice, opcion in enumerate(opciones_mejor, start=1):
                detalle_opcion, _ = reconstruir_detalle_seleccion(df_barras_mejor, df_consolidado, indice - 1)
                resumen_opcion = construir_mejor_cargo_real(df_barras_mejor, df_consolidado, indice - 1)
                detalle_export = reordenar_columnas_export(completar_horas_modulos_para_export(formatear_tabla(detalle_opcion)))
                detalle_export.to_excel(writer, index=False, sheet_name=f"mejor_opcion_{indice}")

                horas, modulos, cargos = metricas_seleccion(resumen_opcion)
                resumen_opciones.append({
                    "OPCION": indice,
                    "SECUENCIAS_INCLUIDAS": " / ".join(opcion["SECUENCIAS_INCLUIDAS"]),
                    "SECUENCIAS_EXCLUIDAS": " / ".join(opcion["SECUENCIAS_EXCLUIDAS"]),
                    "DESDE_MEJOR_CARGO": opcion["DESDE_COMUN"],
                    "HASTA_MEJOR_CARGO": opcion["HASTA_COMUN"],
                    "MESES_COMUN": opcion["MESES_COMUN"],
                    "TOTAL_HORAS_CATEDRA": horas,
                    "TOTAL_MODULOS": modulos,
                    "CARGO_PRIORITARIO": opcion.get("CARGO_PRIORITARIO", ""),
                    "PRIORIDAD_CARGO": opcion.get("PRIORIDAD_CARGO", 0),
                    "CARGOS_ELEGIDOS": " / ".join(cargos),
                })
            pd.DataFrame(resumen_opciones).to_excel(writer, index=False, sheet_name="resumen_alternativas")

        if opciones_sim and df_barras_sim is not None and df_consolidado is not None:
            resumen_opciones_sim = []
            for indice, opcion in enumerate(opciones_sim, start=1):
                detalle_opcion, _ = reconstruir_detalle_seleccion(df_barras_sim, df_consolidado, indice - 1)
                resumen_opcion = construir_mejor_cargo_real(df_barras_sim, df_consolidado, indice - 1)
                detalle_export = reordenar_columnas_export(completar_horas_modulos_para_export(formatear_tabla(detalle_opcion)))
                detalle_export.to_excel(writer, index=False, sheet_name=f"sim_opcion_{indice}")

                horas, modulos, cargos = metricas_seleccion(resumen_opcion)
                resumen_opciones_sim.append({
                    "OPCION": indice,
                    "SECUENCIAS_INCLUIDAS": " / ".join(opcion["SECUENCIAS_INCLUIDAS"]),
                    "SECUENCIAS_EXCLUIDAS": " / ".join(opcion["SECUENCIAS_EXCLUIDAS"]),
                    "DESDE_SIMULTANEO": opcion["DESDE_COMUN"],
                    "HASTA_SIMULTANEO": opcion["HASTA_COMUN"],
                    "MESES_COMUN": opcion["MESES_COMUN"],
                    "TOTAL_HORAS_CATEDRA": horas,
                    "TOTAL_MODULOS": modulos,
                    "CARGO_PRIORITARIO": opcion.get("CARGO_PRIORITARIO", ""),
                    "PRIORIDAD_CARGO": opcion.get("PRIORIDAD_CARGO", 0),
                    "CARGOS_ELEGIDOS": " / ".join(cargos),
                })
            pd.DataFrame(resumen_opciones_sim).to_excel(writer, index=False, sheet_name="resumen_alt_sim")

    output.seek(0)
    return output.getvalue()


def exportar_excel_opcion_activa(df_mejor_detalle, df_sim_detalle, df_resumen_mejor, df_resumen_sim):
    output = BytesIO()

    if df_mejor_detalle is not None and not df_mejor_detalle.empty:
        df_mejor_exp = formatear_tabla(df_mejor_detalle).copy()
        df_mejor_exp = completar_horas_modulos_para_export(df_mejor_exp)

        if "NIVEL" in df_mejor_exp.columns:
            df_mejor_exp = df_mejor_exp.drop(columns=["NIVEL"])

        df_mejor_exp = reordenar_columnas_export(df_mejor_exp)
        total_horas_mejor, total_modulos_mejor = _totales_carga(df_mejor_detalle, df_resumen_mejor)

        fila_total_mejor = {col: "" for col in df_mejor_exp.columns}
        if "CARGO" in df_mejor_exp.columns:
            fila_total_mejor["CARGO"] = "TOTAL"
        elif len(df_mejor_exp.columns) > 0:
            fila_total_mejor[df_mejor_exp.columns[0]] = "TOTAL"

        if "HORAS_CATEDRA" in df_mejor_exp.columns:
            fila_total_mejor["HORAS_CATEDRA"] = total_horas_mejor
        if "MODULOS" in df_mejor_exp.columns:
            fila_total_mejor["MODULOS"] = total_modulos_mejor

        df_mejor_exp = pd.concat([df_mejor_exp, pd.DataFrame([fila_total_mejor])], ignore_index=True)
    else:
        df_mejor_exp = pd.DataFrame({"INFO": ["Sin datos"]})
        total_horas_mejor, total_modulos_mejor = 0, 0

    if df_sim_detalle is not None and not df_sim_detalle.empty:
        df_sim_exp = formatear_tabla(df_sim_detalle).copy()
        df_sim_exp = completar_horas_modulos_para_export(df_sim_exp)

        if "NIVEL" in df_sim_exp.columns:
            df_sim_exp = df_sim_exp.drop(columns=["NIVEL"])

        df_sim_exp = reordenar_columnas_export(df_sim_exp)
        total_horas_sim, total_modulos_sim = _totales_carga(df_sim_detalle, df_resumen_sim)

        fila_total_sim = {col: "" for col in df_sim_exp.columns}
        if "CARGO" in df_sim_exp.columns:
            fila_total_sim["CARGO"] = "TOTAL"
        elif len(df_sim_exp.columns) > 0:
            fila_total_sim[df_sim_exp.columns[0]] = "TOTAL"

        if "HORAS_CATEDRA" in df_sim_exp.columns:
            fila_total_sim["HORAS_CATEDRA"] = total_horas_sim
        if "MODULOS" in df_sim_exp.columns:
            fila_total_sim["MODULOS"] = total_modulos_sim

        df_sim_exp = pd.concat([df_sim_exp, pd.DataFrame([fila_total_sim])], ignore_index=True)
    else:
        df_sim_exp = pd.DataFrame({"INFO": ["Sin datos"]})
        total_horas_sim, total_modulos_sim = 0, 0

    if df_resumen_mejor is not None and not df_resumen_mejor.empty:
        df_resumen_exp = formatear_tabla(df_resumen_mejor).copy()

        if "NIVELES_ORIGEN" in df_resumen_exp.columns:
            df_resumen_exp = df_resumen_exp.drop(columns=["NIVELES_ORIGEN"])
        if "DESDE_COMUN" in df_resumen_exp.columns:
            df_resumen_exp = df_resumen_exp.rename(columns={"DESDE_COMUN": "DESDE_MEJOR_CARGO"})
        if "HASTA_COMUN" in df_resumen_exp.columns:
            df_resumen_exp = df_resumen_exp.rename(columns={"HASTA_COMUN": "HASTA_MEJOR_CARGO"})

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

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_mejor_exp.to_excel(writer, index=False, sheet_name="mejor_cargo")
        df_sim_exp.to_excel(writer, index=False, sheet_name="simultaneo")
        df_resumen_exp.to_excel(writer, index=False, sheet_name="resumen_mejor_cargo")

    output.seek(0)
    return output.getvalue()


def consolidar_periodos(df_in):
    if df_in.empty:
        return pd.DataFrame()

    df = df_in.copy()

    df["HORAS_CATEDRA"] = pd.to_numeric(df.get("HORAS_CATEDRA", 0), errors="coerce").fillna(0)
    df["MODULOS"] = pd.to_numeric(df.get("MODULOS", 0), errors="coerce").fillna(0)

    if "CARGO" in df.columns:
        for idx in df.index:
            horas = float(df.at[idx, "HORAS_CATEDRA"])
            modulos = float(df.at[idx, "MODULOS"])

            hs, mods = extraer_horas_modulos_desde_cargo(df.at[idx, "CARGO"])
            if horas <= 0 and hs > 0:
                df.at[idx, "HORAS_CATEDRA"] = hs
            if modulos <= 0 and mods > 0:
                df.at[idx, "MODULOS"] = mods

    df = df.sort_values(["SECUENCIA", "DESDE"]).reset_index(drop=True)

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

            continuidad = desde <= fin + pd.Timedelta(days=1)
            misma_carga = (horas == horas_actual and modulos == modulos_actual)

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
                    "BAR_ID": f"{secuencia}|{inicio:%Y-%m-%d}|{fin:%Y-%m-%d}",
                    "SECUENCIA": str(secuencia),
                    "NIVEL": nivel,
                    "DESDE": inicio,
                    "HASTA": fin,
                    "ESCUELA": " / ".join(escuelas),
                    "CARGO": " / ".join(cargos),
                    "HORAS_CATEDRA": horas_actual,
                    "MODULOS": modulos_actual,
                    "HISTORIAL_HORAS": historial_horas.copy(),
                    "HISTORIAL_MODULOS": historial_modulos.copy(),
                    "DIAS": dias,
                    "MESES_APROX": meses,
                    "CUMPLE_36M": meses >= 36
                })

                inicio = desde
                fin = hasta
                horas_actual = horas
                modulos_actual = modulos
                cargos = [cargo]
                escuelas = [escuela]
                historial_horas = [horas]
                historial_modulos = [modulos]

        if inicio is not None:
            dias = (fin - inicio).days + 1
            meses = round(dias / 30.44, 1)

            filas.append({
                "BAR_ID": f"{secuencia}|{inicio:%Y-%m-%d}|{fin:%Y-%m-%d}",
                "SECUENCIA": str(secuencia),
                "NIVEL": nivel,
                "DESDE": inicio,
                "HASTA": fin,
                "ESCUELA": " / ".join(escuelas),
                "CARGO": " / ".join(cargos),
                "HORAS_CATEDRA": horas_actual,
                "MODULOS": modulos_actual,
                "HISTORIAL_HORAS": historial_horas.copy(),
                "HISTORIAL_MODULOS": historial_modulos.copy(),
                "DIAS": dias,
                "MESES_APROX": meses,
                "CUMPLE_36M": meses >= 36
            })

    out = pd.DataFrame(filas)

    if out.empty:
        return out

    out["ORIGEN_IDS"] = out.apply(
        lambda barra: df.loc[
            (df["SECUENCIA"].astype(str) == str(barra["SECUENCIA"]))
            & (df["DESDE"] <= barra["HASTA"])
            & (df["HASTA"] >= barra["DESDE"]),
            "ORIGEN_ID",
        ].tolist(),
        axis=1,
    )

    return out.sort_values(["SECUENCIA", "DESDE"]).reset_index(drop=True)


# ---------------------------------
# SELECTOR DE NIVEL Y GRAFICO
# ---------------------------------
st.subheader("Linea de tiempo")

niveles_disponibles = sorted(df["NIVEL"].fillna("Sin Nivel").astype(str).unique().tolist())
opciones_nivel = ["Todos los niveles"] + niveles_disponibles

nivel_sel = st.selectbox("Nivel a visualizar", opciones_nivel, index=0)

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

# Franja móvil
DIAS_FRANJA_36M = 1095
max_inicio_franja = fecha_max - pd.Timedelta(days=DIAS_FRANJA_36M - 1)
st.markdown("#### Franja móvil de 36 meses")
if max_inicio_franja >= fecha_min:
    inicio_guardado = st.session_state["franja_36_inicio_02"]
    if inicio_guardado is None or not (fecha_min <= pd.Timestamp(inicio_guardado) <= max_inicio_franja):
        inicio_guardado = fecha_min
    inicio_franja = pd.Timestamp(st.slider(
        "Mover inicio de la franja",
        min_value=fecha_min.date(), max_value=max_inicio_franja.date(),
        value=pd.Timestamp(inicio_guardado).date(), format="DD/MM/YYYY",
    ))
else:
    inicio_franja = fecha_min
    st.info("El período visible tiene menos de 1.095 días; la franja comienza en la primera fecha disponible.")

st.session_state["franja_36_inicio_02"] = inicio_franja
fin_franja = inicio_franja + pd.Timedelta(days=DIAS_FRANJA_36M - 1)
df_franja = df_plot[(df_plot["DESDE"] <= fin_franja) & (df_plot["HASTA"] >= inicio_franja)].copy()
st.caption(
    f"Franja activa: {inicio_franja.strftime('%d/%m/%Y')} a {fin_franja.strftime('%d/%m/%Y')} "
    f"· {len(df_franja)} barras que la intersectan."
)

# ---------------------------------
# GRAFICO PLOTLY
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

fig.add_vrect(
    x0=inicio_franja,
    x1=fin_franja,
    fillcolor="#f4b942",
    opacity=0.18,
    line_width=2,
    line_color="#b87800",
    annotation_text="36 meses / 1.095 días",
    annotation_position="top left",
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

fc1, fc2 = st.columns(2)
with fc1:
    if st.button("Agregar franja a Mejor Cargo", use_container_width=True):
        tabla = st.session_state["seleccion_mejor_cargo_02"]
        for _, barra in df_franja.iterrows():
            tabla = agregar_a_tabla(tabla, barra.to_frame().T)
        st.session_state["seleccion_mejor_cargo_02"] = tabla
        st.rerun()

with fc2:
    if st.button("Agregar franja a Simultáneo", use_container_width=True):
        tabla = st.session_state["seleccion_simultaneo_02"]
        for _, barra in df_franja.iterrows():
            tabla = agregar_a_tabla(tabla, barra.to_frame().T)
        st.session_state["seleccion_simultaneo_02"] = tabla
        st.rerun()

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
# TABLAS DE SELECCION Y PROCESAMIENTO
# ---------------------------------
st.markdown("---")
st.subheader("Selecciones en construcción")

tab_mejor, tab_sim, tab_export = st.tabs(["Mejor Cargo", "Simultáneo", "Exportar"])

df_mejor_barras = st.session_state["seleccion_mejor_cargo_02"].copy()
opciones_mejor = calcular_opciones_mejor_cargo(df_mejor_barras, df, limite=5)
indice_mejor = min(st.session_state["opcion_mejor_cargo_02"], max(len(opciones_mejor) - 1, 0))
st.session_state["opcion_mejor_cargo_02"] = indice_mejor

df_mejor_detalle, tramo_mejor = reconstruir_detalle_seleccion(df_mejor_barras, df, indice_mejor)
df_mejor_real = construir_mejor_cargo_real(df_mejor_barras, df, indice_mejor)
st.session_state["df_mejor_cargo_detalle_02"] = df_mejor_detalle.copy()
st.session_state["df_mejor_cargo_real_02"] = df_mejor_real.copy()

df_sim_barras = st.session_state["seleccion_simultaneo_02"].copy()
opciones_sim = calcular_opciones_mejor_cargo(df_sim_barras, df, limite=5)
indice_sim = min(st.session_state["opcion_simultaneo_02"], max(len(opciones_sim) - 1, 0))
st.session_state["opcion_simultaneo_02"] = indice_sim

df_sim_detalle, tramo_sim = reconstruir_detalle_seleccion(df_sim_barras, df, indice_sim)
df_sim_real = construir_mejor_cargo_real(df_sim_barras, df, indice_sim)
st.session_state["df_simultaneo_detalle_02"] = df_sim_detalle.copy()
st.session_state["df_simultaneo_real_02"] = df_sim_real.copy()

# ---------------------------------
# TAB MEJOR CARGO
# ---------------------------------
with tab_mejor:
    df_mejor = df_mejor_barras.copy()

    if df_mejor.empty:
        st.info("Todavía no agregaste barras a Mejor Cargo.")
        st.session_state["df_mejor_cargo_real_02"] = pd.DataFrame()
    else:
        tramo = tramo_mejor

        if opciones_mejor:
            etiquetas_opciones = [
                (
                    f"Opción {i + 1}: secuencias {', '.join(opcion['SECUENCIAS_INCLUIDAS'])} "
                    f"| {opcion['DESDE_COMUN'].strftime('%d/%m/%Y')} a "
                    f"{opcion['HASTA_COMUN'].strftime('%d/%m/%Y')} "
                    f"({opcion['MESES_COMUN']} meses) | "
                    f"{opcion.get('CARGO_PRIORITARIO', '')}: "
                    f"{opcion.get('TOTAL_MODULOS', 0):g} módulos, "
                    f"{opcion.get('TOTAL_HORAS', 0):g} hs"
                )
                for i, opcion in enumerate(opciones_mejor)
            ]
            st.selectbox(
                "Posibles Mejores Cargos (elegí el que querés usar)",
                options=range(len(etiquetas_opciones)),
                format_func=lambda i: etiquetas_opciones[i],
                key="opcion_mejor_cargo_02",
            )

        horas_mejor, modulos_mejor, cargos_mejor = metricas_seleccion(df_mejor_real)
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.metric("Total módulos", f"{modulos_mejor:g}")
        with mc2:
            st.metric("Total horas cátedra", f"{horas_mejor:g}")
        with mc3:
            st.metric("Cargos elegidos", len(cargos_mejor))
        if cargos_mejor:
            st.caption("Cargos de la alternativa: " + " | ".join(cargos_mejor))

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
                fecha_desde_str = "-" if pd.isna(tramo["DESDE_COMUN"]) else tramo["DESDE_COMUN"].strftime("%d/%m/%Y")
                st.metric("Desde común", fecha_desde_str)
            with c2:
                fecha_hasta_str = "-" if pd.isna(tramo["HASTA_COMUN"]) else tramo["HASTA_COMUN"].strftime("%d/%m/%Y")
                st.metric("Hasta común", fecha_hasta_str)
            with c3:
                st.metric("Días comunes", tramo["DIAS_COMUN"])
            with c4:
                st.metric("Meses comunes", tramo["MESES_COMUN"])

            if tramo["HAY_SOLAPE"]:
                st.success("Se encontró un tramo común de 36 meses.")
                if tramo.get("SECUENCIAS_EXCLUIDAS"):
                    st.info(
                        "Se excluyeron del período de 36 meses las secuencias: "
                        + ", ".join(tramo["SECUENCIAS_EXCLUIDAS"])
                    )
            else:
                st.error("No existe un período común de 36 meses entre las barras seleccionadas.")

        st.markdown("### Filas originales reconstruidas para el tramo común")
        if df_mejor_detalle.empty:
            st.info("No hay filas originales que integren el tramo común.")
        else:
            columnas_detalle = [
                "SECUENCIA", "NIVEL", "DESDE", "HASTA", "ESCUELA", "CARGO",
                "HORAS_CATEDRA", "MODULOS", "TIPO_CARGA_EFECTIVA", "CARGA_EFECTIVA"
            ]
            columnas_detalle = [c for c in columnas_detalle if c in df_mejor_detalle.columns]
            st.dataframe(formatear_tabla(df_mejor_detalle[columnas_detalle]), use_container_width=True, height=240)

        st.markdown("### Menor carga elegida por secuencia")
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
            st.session_state["df_mejor_cargo_detalle_02"] = pd.DataFrame()
            st.session_state["opcion_mejor_cargo_02"] = 0
            st.rerun()

# ---------------------------------
# TAB SIMULTANEO
# ---------------------------------
with tab_sim:
    df_sim = df_sim_barras.copy()

    if df_sim.empty:
        st.info("Todavía no agregaste barras a Simultáneo.")
    else:
        if opciones_sim:
            etiquetas_sim = [
                (
                    f"Opción {i + 1}: secuencias {', '.join(opcion['SECUENCIAS_INCLUIDAS'])} "
                    f"| {opcion['DESDE_COMUN'].strftime('%d/%m/%Y')} a "
                    f"{opcion['HASTA_COMUN'].strftime('%d/%m/%Y')} "
                    f"({opcion['MESES_COMUN']} meses) | "
                    f"{opcion.get('CARGO_PRIORITARIO', '')}: "
                    f"{opcion.get('TOTAL_MODULOS', 0):g} módulos, "
                    f"{opcion.get('TOTAL_HORAS', 0):g} hs"
                )
                for i, opcion in enumerate(opciones_sim)
            ]
            st.selectbox(
                "Posibles Simultáneos (elegí el que querés usar)",
                options=range(len(etiquetas_sim)),
                format_func=lambda i: etiquetas_sim[i],
                key="opcion_simultaneo_02",
            )

        horas_sim, modulos_sim, cargos_sim = metricas_seleccion(df_sim_real)
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            st.metric("Total módulos simultáneos", f"{modulos_sim:g}")
        with sc2:
            st.metric("Total horas cátedra simultáneas", f"{horas_sim:g}")
        with sc3:
            st.metric("Cargos simultáneos", len(cargos_sim))
        if cargos_sim:
            st.caption("Cargos simultáneos elegidos: " + " | ".join(cargos_sim))

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

        st.markdown("### Filas originales reconstruidas para el tramo común")
        if tramo_sim is not None and not tramo_sim["HAY_SOLAPE"]:
            st.error("Las barras seleccionadas no tienen tramo común.")
        elif df_sim_detalle.empty:
            st.info("No hay filas originales que integren el tramo común.")
        else:
            columnas_detalle = [
                "SECUENCIA", "NIVEL", "DESDE", "HASTA", "ESCUELA", "CARGO",
                "HORAS_CATEDRA", "MODULOS", "TIPO_CARGA_EFECTIVA", "CARGA_EFECTIVA"
            ]
            columnas_detalle = [c for c in columnas_detalle if c in df_sim_detalle.columns]
            st.dataframe(formatear_tabla(df_sim_detalle[columnas_detalle]), use_container_width=True, height=240)

        st.markdown("### Menor carga elegida por secuencia")
        if not df_sim_real.empty:
            st.dataframe(formatear_tabla(df_sim_real), use_container_width=True, height=180)

        if st.button("Limpiar Simultáneo", use_container_width=True):
            st.session_state["seleccion_simultaneo_02"] = pd.DataFrame()
            st.session_state["df_simultaneo_detalle_02"] = pd.DataFrame()
            st.session_state["df_simultaneo_real_02"] = pd.DataFrame()
            st.session_state["opcion_simultaneo_02"] = 0
            st.rerun()

# ---------------------------------
# TAB EXPORTAR
# ---------------------------------
with tab_export:
    st.markdown("### Exportar selección")

    df_resumen_export = st.session_state["df_mejor_cargo_real_02"].copy()

    if df_resumen_export is not None and not df_resumen_export.empty:
        df_resumen_preview = df_resumen_export.copy()
        if "DESDE_COMUN" in df_resumen_preview.columns:
            df_resumen_preview = df_resumen_preview.rename(columns={"DESDE_COMUN": "DESDE_MEJOR_CARGO"})
        if "HASTA_COMUN" in df_resumen_preview.columns:
            df_resumen_preview = df_resumen_preview.rename(columns={"HASTA_COMUN": "HASTA_MEJOR_CARGO"})
        if "NIVELES_ORIGEN" in df_resumen_preview.columns:
            df_resumen_preview = df_resumen_preview.drop(columns=["NIVELES_ORIGEN"])

        st.markdown("#### Resumen del mejor cargo a exportar (opción seleccionada actualmente)")
        st.dataframe(
            formatear_tabla(df_resumen_preview),
            use_container_width=True,
            height=180
        )

    # Excel Completo
    excel_bytes_completo = exportar_excel(
        st.session_state["df_mejor_cargo_detalle_02"],
        st.session_state["df_simultaneo_detalle_02"],
        st.session_state["df_mejor_cargo_real_02"],
        st.session_state["df_simultaneo_real_02"],
        opciones_mejor=opciones_mejor,
        df_barras_mejor=df_mejor_barras,
        df_consolidado=df,
        opciones_sim=opciones_sim,
        df_barras_sim=df_sim_barras,
    )

    # Excel Opcion Activa
    excel_bytes_activa = exportar_excel_opcion_activa(
        st.session_state["df_mejor_cargo_detalle_02"],
        st.session_state["df_simultaneo_detalle_02"],
        st.session_state["df_mejor_cargo_real_02"],
        st.session_state["df_simultaneo_real_02"],
    )

    exp_col1, exp_col2 = st.columns(2)

    with exp_col1:
        st.download_button(
            label="Descargar solo OPCIÓN SELECCIONADA",
            data=excel_bytes_activa,
            file_name="seleccion_opcion_activa.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Descarga un Excel únicamente con las pestañas de la opción elegida actualmente en los selectores."
        )

    with exp_col2:
        st.download_button(
            label="Descargar TODO (todas las alternativas)",
            data=excel_bytes_completo,
            file_name="seleccion_todas_las_alternativas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Descarga el Excel completo con pestañas adicionales para todas las combinaciones posibles calculadas."
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