# ============================================================
# COMPONENTS / CHARTS
# ============================================================
# Funciones puras de graficos y calculo
# NO Streamlit UI
# Devuelven figuras Plotly
# Reutilizables desde pages/*
# ============================================================

import pandas as pd
import plotly.express as px
from dateutil.relativedelta import relativedelta


# ============================================================
# HELPERS
# ============================================================

def _normalizar_fechas(df):
    df = df.copy()

    if "HASTA" in df.columns:
        df["HASTA"] = df["HASTA"].replace("HOY", pd.Timestamp.today().normalize())

    df["DESDE"] = pd.to_datetime(df["DESDE"], dayfirst=True, errors="coerce")
    df["HASTA"] = pd.to_datetime(df["HASTA"], dayfirst=True, errors="coerce")

    return df.dropna(subset=["DESDE", "HASTA"])


def _columna_o_vacio(df, columna):
    if columna in df.columns:
        return df[columna].fillna("").astype(str)
    return ""


# ============================================================
# 1. GANTT POR SECUENCIA
# ============================================================

def generar_grafico_interactivo_secuencia(
    df,
    licencias=None,
    codigos_validos=None,
    secuencias_validas=None,
):
    df = _normalizar_fechas(df)

    if df.empty:
        return px.timeline(title="Gantt por secuencia historica")

    # --- Etiqueta combinada ---
    if "ORIGEN" in df.columns:
        df["SECUENCIA_ORIGEN"] = (
            df["SECUENCIA"].astype(str) + " (" + df["ORIGEN"].astype(str) + ")"
        )
    else:
        df["SECUENCIA_ORIGEN"] = df["SECUENCIA"].astype(str)

    df["ESCUELA_HOVER"] = _columna_o_vacio(df, "ESCUELA")
    df["CARGO_HOVER"] = _columna_o_vacio(df, "CARGO")
    df["ORIGEN_HOVER"] = _columna_o_vacio(df, "ORIGEN")
    df["DESDE_HOVER"] = df["DESDE"].dt.strftime("%d/%m/%Y")
    df["HASTA_HOVER"] = df["HASTA"].dt.strftime("%d/%m/%Y")

    # --- Gantt base ---
    fig = px.timeline(
        df,
        x_start="DESDE",
        x_end="HASTA",
        y="SECUENCIA_ORIGEN",
        color="CARGO" if "CARGO" in df.columns else "SECUENCIA",
        custom_data=[
            "SECUENCIA",
            "ORIGEN_HOVER",
            "ESCUELA_HOVER",
            "CARGO_HOVER",
            "DESDE_HOVER",
            "HASTA_HOVER",
        ],
        title="Gantt por secuencia historica",
    )

    fig.update_traces(
        hovertemplate=
            "<b>Secuencia:</b> %{customdata[0]}<br>"
            "<b>Origen:</b> %{customdata[1]}<br>"
            "<b>Escuela:</b> %{customdata[2]}<br>"
            "<b>Cargo:</b> %{customdata[3]}<br>"
            "<b>Desde:</b> %{customdata[4]}<br>"
            "<b>Hasta:</b> %{customdata[5]}"
            "<extra></extra>"
    )

    fig.update_yaxes(autorange="reversed")

    fig.update_layout(
        xaxis_title="Periodo",
        yaxis_title="Secuencia",
        hoverlabel_align="left",
        template="plotly_white",
        height=650,
    )

    # --- Lineas de licencias ---
    if (
        licencias is not None
        and codigos_validos is not None
        and secuencias_validas is not None
    ):
        lic = licencias.copy()
        lic = lic[
            (lic["ENCUADRE"].isin(codigos_validos))
            & (lic["SECUENCIA"].astype(str).isin(secuencias_validas))
        ]

        for _, row in lic.iterrows():
            for col in ["DESDE", "HASTA"]:
                fecha = pd.to_datetime(row[col], errors="coerce", dayfirst=True)

                if pd.notna(fecha):
                    fig.add_shape(
                        type="line",
                        x0=fecha,
                        x1=fecha,
                        y0=0,
                        y1=1,
                        xref="x",
                        yref="paper",
                        line=dict(color="red", width=1.5, dash="dot"),
                    )

    return fig


# ============================================================
# 2. GANTT CONSOLIDADO - RANGO 36 MESES
# ============================================================

def preparar_rango_36_meses(df_consolidado, fecha_inicio):
    """
    Devuelve el DF filtrado que intersecta el rango de 36 meses.
    """
    fecha_inicio = pd.to_datetime(fecha_inicio)
    fecha_fin = fecha_inicio + pd.DateOffset(months=36)

    df = df_consolidado.copy()
    df["DESDE"] = pd.to_datetime(df["DESDE"], errors="coerce", dayfirst=True)
    df["HASTA"] = pd.to_datetime(df["HASTA"], errors="coerce", dayfirst=True)

    return df[
        (df["HASTA"] >= fecha_inicio)
        & (df["DESDE"] <= fecha_fin)
    ].copy(), fecha_fin


# ============================================================
# 3. LINEA DE TIEMPO POR NIVEL LIMPIO
# ============================================================

def consolidar_periodos_por_secuencia(df):
    """
    Une periodos solapados o continuos por SECUENCIA.
    Conserva datos de ESCUELA y CARGO para mostrarlos en el tooltip.
    """
    df = _normalizar_fechas(df)
    df = df.sort_values(["SECUENCIA", "DESDE"])

    filas = []

    for secuencia, grupo in df.groupby("SECUENCIA"):
        inicio = None
        fin = None
        escuelas = set()
        cargos = set()

        for _, row in grupo.iterrows():
            escuela = str(row["ESCUELA"]) if "ESCUELA" in grupo.columns and pd.notna(row.get("ESCUELA")) else ""
            cargo = str(row["CARGO"]) if "CARGO" in grupo.columns and pd.notna(row.get("CARGO")) else ""

            if inicio is None:
                inicio = row["DESDE"]
                fin = row["HASTA"]

                if escuela:
                    escuelas.add(escuela)
                if cargo:
                    cargos.add(cargo)

                continue

            if row["DESDE"] <= fin + pd.Timedelta(days=1):
                fin = max(fin, row["HASTA"])

                if escuela:
                    escuelas.add(escuela)
                if cargo:
                    cargos.add(cargo)

            else:
                filas.append({
                    "SECUENCIA": secuencia,
                    "DESDE": inicio,
                    "HASTA": fin,
                    "ESCUELA": " / ".join(sorted(escuelas)),
                    "CARGO": " / ".join(sorted(cargos)),
                })

                inicio = row["DESDE"]
                fin = row["HASTA"]
                escuelas = set()
                cargos = set()

                if escuela:
                    escuelas.add(escuela)
                if cargo:
                    cargos.add(cargo)

        filas.append({
            "SECUENCIA": secuencia,
            "DESDE": inicio,
            "HASTA": fin,
            "ESCUELA": " / ".join(sorted(escuelas)),
            "CARGO": " / ".join(sorted(cargos)),
        })

    return pd.DataFrame(filas)


def generar_linea_tiempo_por_nivel_limpio(df_nivel):
    """
    Grafico para la pestana 'Linea de tiempo por nivel (limpio)'.
    """
    df_plot = consolidar_periodos_por_secuencia(df_nivel)

    if df_plot.empty:
        return px.timeline(title="Linea de tiempo por nivel"), df_plot

    df_plot["DESDE_HOVER"] = df_plot["DESDE"].dt.strftime("%d/%m/%Y")
    df_plot["HASTA_HOVER"] = df_plot["HASTA"].dt.strftime("%d/%m/%Y")

    fecha_min = df_plot["DESDE"].min()
    fecha_max = df_plot["HASTA"].max()
    margen = pd.Timedelta(days=30)

    fig = px.timeline(
        df_plot,
        x_start="DESDE",
        x_end="HASTA",
        y="SECUENCIA",
        color="SECUENCIA",
        custom_data=[
            "SECUENCIA",
            "ESCUELA",
            "CARGO",
            "DESDE_HOVER",
            "HASTA_HOVER",
        ],
    )

    fig.update_traces(
        hovertemplate=
            "<b>Secuencia:</b> %{customdata[0]}<br>"
            "<b>Escuela:</b> %{customdata[1]}<br>"
            "<b>Cargo:</b> %{customdata[2]}<br>"
            "<b>Desde:</b> %{customdata[3]}<br>"
            "<b>Hasta:</b> %{customdata[4]}"
            "<extra></extra>"
    )

    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(range=[fecha_min - margen, fecha_max + margen])

    fig.update_layout(
        height=max(500, len(df_plot["SECUENCIA"].unique()) * 30),
        showlegend=False,
        bargap=0.2,
        hoverlabel_align="left",
        template="plotly_white",
        xaxis_title="Periodo",
        yaxis_title="Secuencia",
    )

    return fig, df_plot


# ============================================================
# 4. ANTIGUEDAD TOTAL UNIFICADA
# ============================================================

def calcular_antiguedad_total(df):
    """
    Calcula antiguedad total unificando solapamientos.
    """
    df = df.copy()
    df["DESDE"] = pd.to_datetime(df["DESDE"], errors="coerce", dayfirst=True)
    df["HASTA"] = pd.to_datetime(df["HASTA"], errors="coerce", dayfirst=True)
    df["HASTA"] = df["HASTA"].fillna(pd.Timestamp.today().normalize())
    df = df.dropna(subset=["DESDE", "HASTA"]).sort_values("DESDE")

    if df.empty:
        return 0, 0, 0

    merged = []
    start, end = df.iloc[0]["DESDE"], df.iloc[0]["HASTA"]

    for _, row in df.iloc[1:].iterrows():
        if row["DESDE"] <= end:
            end = max(end, row["HASTA"])
        else:
            merged.append((start, end))
            start, end = row["DESDE"], row["HASTA"]

    merged.append((start, end))

    inicio = merged[0][0]
    fin = merged[-1][1]

    rd = relativedelta(fin, inicio)

    return rd.years, rd.months, rd.days