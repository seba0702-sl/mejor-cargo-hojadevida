import streamlit as st
import pandas as pd
import plotly.express as px

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

# ---------------------------------
# NORMALIZACION DE FECHAS
# ---------------------------------
df["HASTA"] = df["HASTA"].replace("HOY", pd.Timestamp.today())

df["DESDE"] = pd.to_datetime(df["DESDE"], errors="coerce", dayfirst=True)
df["HASTA"] = pd.to_datetime(df["HASTA"], errors="coerce", dayfirst=True)

df = df.dropna(subset=["DESDE", "HASTA"])

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


def consolidar_periodos(df):
    df = df.sort_values(["SECUENCIA", "DESDE"])
    filas = []

    for secuencia, grupo in df.groupby("SECUENCIA"):
        inicio = None
        fin = None
        escuelas = set()
        cargos = set()

        for _, row in grupo.iterrows():
            if inicio is None:
                inicio = row["DESDE"]
                fin = row["HASTA"]

                if "ESCUELA" in row and pd.notna(row["ESCUELA"]):
                    escuelas.add(str(row["ESCUELA"]))

                if "CARGO" in row and pd.notna(row["CARGO"]):
                    cargos.add(str(row["CARGO"]))

                continue

            if row["DESDE"] <= fin + pd.Timedelta(days=1):
                fin = max(fin, row["HASTA"])

                if "ESCUELA" in row and pd.notna(row["ESCUELA"]):
                    escuelas.add(str(row["ESCUELA"]))

                if "CARGO" in row and pd.notna(row["CARGO"]):
                    cargos.add(str(row["CARGO"]))

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

                if "ESCUELA" in row and pd.notna(row["ESCUELA"]):
                    escuelas.add(str(row["ESCUELA"]))

                if "CARGO" in row and pd.notna(row["CARGO"]):
                    cargos.add(str(row["CARGO"]))

        filas.append({
            "SECUENCIA": secuencia,
            "DESDE": inicio,
            "HASTA": fin,
            "ESCUELA": " / ".join(sorted(escuelas)),
            "CARGO": " / ".join(sorted(cargos)),
        })

    return pd.DataFrame(filas)


# ---------------------------------
# LINEA DE TIEMPO POR NIVEL
# ---------------------------------
st.subheader("Linea de tiempo por nivel (limpio)")

df["DESDE"] = pd.to_datetime(df["DESDE"], errors="coerce", dayfirst=True)
df["HASTA"] = pd.to_datetime(df["HASTA"], errors="coerce", dayfirst=True)

niveles = sorted(df["NIVEL"].dropna().unique())
tabs = st.tabs(niveles)

for i, nivel in enumerate(niveles):

    with tabs[i]:

        df_nivel = df[df["NIVEL"] == nivel].copy()

        if df_nivel.empty:
            st.info("Sin datos")
            continue

        df_plot = consolidar_periodos(df_nivel)

        if df_plot.empty:
            st.info("Sin datos para graficar")
            continue

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

        fig.update_xaxes(
            range=[fecha_min - margen, fecha_max + margen]
        )

        fig.update_layout(
            height=max(500, len(df_plot["SECUENCIA"].unique()) * 30),
            showlegend=False,
            bargap=0.2,
            hoverlabel_align="left",
            template="plotly_white",
            xaxis_title="Periodo",
            yaxis_title="Secuencia",
        )

        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------
# TABLA DETALLE
# ---------------------------------
with st.expander("Ver datos del Gantt"):
    st.dataframe(
        df.sort_values(["SECUENCIA", "DESDE"]),
        use_container_width=True,
        height=450
    )


# ---------------------------------
# INFO FINAL
# ---------------------------------
st.caption(
    "Este Gantt muestra TODAS las secuencias disponibles en los datos consolidados, "
    "sin aplicar ningun filtro."
)