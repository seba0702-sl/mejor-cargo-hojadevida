import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="60 Meses Alternados por Nivel", layout="wide")

st.title("Calculo de 60 Meses Alternados por Nivel")

# =====================================================
# SESSION STATE
# =====================================================

if "seleccion_grupos" not in st.session_state:
    st.session_state.seleccion_grupos = {}

# =====================================================
# FUNCIONES DE APOYO
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


def dias_de_grupo(g):
    return (g["fecha_hasta"] - g["fecha_desde"]).days + 1


def meses_aprox_de_grupo(g):
    return dias_de_grupo(g) // 30


def calcular_acumulado_bruto(df_nivel):
    df_nivel = df_nivel.sort_values("DESDE")
    total_dias = ((df_nivel["HASTA"] - df_nivel["DESDE"]).dt.days + 1).sum()
    meses = total_dias // 30
    dias_rest = total_dias % 30
    return meses, dias_rest


# =====================================================
# VALIDACION
# =====================================================

if "df_consolidado_filtrado" not in st.session_state:
    st.warning("Primero debe cargar los datos.")
    st.stop()

df = st.session_state["df_consolidado_filtrado"].copy()

df["DESDE"] = pd.to_datetime(df["DESDE"], errors="coerce")
df["HASTA"] = pd.to_datetime(df["HASTA"], errors="coerce")
df = df.dropna(subset=["DESDE", "HASTA"])

df.sort_values("DESDE", inplace=True)
df.reset_index(drop=True, inplace=True)

# =====================================================
# NIVEL
# =====================================================

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
        return None
    escuela = str(escuela).upper()
    for nivel, codigos in niveles_dict.items():
        if any(cod in escuela for cod in codigos):
            return nivel
    return None


df["NIVEL"] = df["ESCUELA"].apply(detectar_nivel)

# =====================================================
# CARGA HORARIA
# =====================================================

columna_carga_numerica = df.columns[9]
df[columna_carga_numerica] = pd.to_numeric(
    df[columna_carga_numerica], errors="coerce"
).fillna(0)

texto = df["CARGO"].str.upper().fillna("")

df["MODULOS"] = df[columna_carga_numerica].where(texto.str.contains("MOD"), 0)
df["HORAS_CATEDRA"] = df[columna_carga_numerica].where(
    texto.str.contains("HORA|CATEDRA|INSTRUCTOR|HS"), 0
)

# =====================================================
# ALGORITMO DE GRUPOS POR INTERSECCION
# =====================================================


def generar_grupos_interseccion(df_nivel):
    df_nivel = df_nivel.sort_values(by=["SECUENCIA", "DESDE", "HASTA"]).reset_index(
        drop=True
    )

    grupos = []
    grupos_unicos = set()

    for i in range(len(df_nivel)):
        base = df_nivel.iloc[i]

        secuencias_usadas = {base["SECUENCIA"]}
        grupo = [base]

        desde_max = base["DESDE"]
        hasta_min = base["HASTA"]

        for j in range(len(df_nivel)):
            if i == j:
                continue

            fila = df_nivel.iloc[j]

            if fila["SECUENCIA"] in secuencias_usadas:
                continue

            nuevo_desde = max(desde_max, fila["DESDE"])
            nuevo_hasta = min(hasta_min, fila["HASTA"])

            if nuevo_desde <= nuevo_hasta:
                grupo.append(fila)
                secuencias_usadas.add(fila["SECUENCIA"])
                desde_max = nuevo_desde
                hasta_min = nuevo_hasta

        anios, meses, dias = calcular_antiguedad_exacta(desde_max, hasta_min)

        if anios > 0 or meses > 0 or dias > 0:
            secuencias_ordenadas = tuple(sorted(map(str, secuencias_usadas)))
            clave = (secuencias_ordenadas, desde_max, hasta_min)

            if clave in grupos_unicos:
                continue

            grupos_unicos.add(clave)
            df_grupo = pd.DataFrame(grupo)

            grupos.append(
                {
                    "grupo_df": df_grupo,
                    "fecha_desde": pd.to_datetime(desde_max),
                    "fecha_hasta": pd.to_datetime(hasta_min),
                    "anios": anios,
                    "meses": meses,
                    "dias": dias,
                    "modulos": df_grupo["MODULOS"].sum(),
                    "horas": df_grupo["HORAS_CATEDRA"].sum(),
                }
            )

    return grupos


# =====================================================
# LIMPIEZA DE SELECCION FINAL
# =====================================================


def limpiar_grupos_superpuestos(lista_grupos):
    if not lista_grupos:
        return []

    grupos_ordenados = sorted(lista_grupos, key=lambda x: x["fecha_desde"])
    finales = []
    puntero_fecha = None

    for g in grupos_ordenados:
        g_copia = g.copy()
        inicio, fin = g_copia["fecha_desde"], g_copia["fecha_hasta"]

        if puntero_fecha is not None and inicio <= puntero_fecha:
            inicio = puntero_fecha + pd.Timedelta(days=1)
            if inicio > fin:
                continue

        anios, meses, dias = calcular_antiguedad_exacta(inicio, fin)

        if anios > 0 or meses > 0 or dias > 0:
            g_copia["fecha_desde"] = inicio
            g_copia["anios_exactos"] = anios
            g_copia["meses_exactos"] = meses
            g_copia["dias_exactos"] = dias
            finales.append(g_copia)
            puntero_fecha = fin

    return finales


# =====================================================
# FILTROS
# =====================================================

st.markdown("---")
st.subheader("Filtros de seleccion")

col1, col2, col3 = st.columns(3)

min_modulos = col1.number_input("Minimo Modulos", 0, 1000, 0)
min_horas = col2.number_input("Minimo Horas Catedra", 0, 1000, 0)
min_meses = col3.number_input("Minimo meses aproximados", 0, 200, 0)

usar_filtro = st.checkbox("Aplicar filtros", value=False)


@st.cache_data
def generar_grupos_por_nivel(df):
    resultado = {}
    for nivel in df["NIVEL"].dropna().unique():
        df_nivel = df[df["NIVEL"] == nivel].copy()
        resultado[nivel] = generar_grupos_interseccion(df_nivel)
    return resultado


# =====================================================
# INTERFAZ
# =====================================================

st.markdown("---")
st.subheader("Analisis por Nivel")

niveles_encontrados = sorted(df["NIVEL"].dropna().unique())
grupos_seleccionados = []

grupos_por_nivel = generar_grupos_por_nivel(df)

if niveles_encontrados:
    tabs = st.tabs(niveles_encontrados)

    for idx, nivel in enumerate(niveles_encontrados):
        with tabs[idx]:
            df_nivel = df[df["NIVEL"] == nivel]
            meses_bruto, dias_bruto = calcular_acumulado_bruto(df_nivel)
            st.info(f"Tiempo acumulado bruto del nivel: {meses_bruto}m {dias_bruto}d")

            grupos = grupos_por_nivel[nivel]

            if usar_filtro:
                grupos = [
                    g
                    for g in grupos
                    if g["modulos"] >= min_modulos
                    and g["horas"] >= min_horas
                    and meses_aprox_de_grupo(g) >= min_meses
                ]

            modo_orden = st.selectbox(
                f"Ordenar grupos ({nivel})",
                [
                    "Mas modulos",
                    "Mas horas catedra",
                    "Mayor duracion",
                    "Mas recientes",
                    "Mas antiguos",
                ],
                key=f"orden_{nivel}",
            )

            if modo_orden == "Mas modulos":
                grupos = sorted(
                    grupos,
                    key=lambda x: (x["modulos"], dias_de_grupo(x), x["horas"]),
                    reverse=True,
                )
            elif modo_orden == "Mas horas catedra":
                grupos = sorted(
                    grupos,
                    key=lambda x: (x["horas"], dias_de_grupo(x), x["modulos"]),
                    reverse=True,
                )
            elif modo_orden == "Mayor duracion":
                grupos = sorted(
                    grupos,
                    key=lambda x: (dias_de_grupo(x), x["modulos"], x["horas"]),
                    reverse=True,
                )
            elif modo_orden == "Mas recientes":
                grupos = sorted(grupos, key=lambda x: x["fecha_desde"], reverse=True)
            elif modo_orden == "Mas antiguos":
                grupos = sorted(grupos, key=lambda x: x["fecha_desde"])

            max_mostrar = st.slider(
                f"Cantidad de grupos a mostrar ({nivel})",
                10,
                200,
                50,
                key=f"slider_{nivel}",
            )

            key_select_all = f"select_all_{nivel}"
            seleccionar_todos = st.checkbox(
                f"Seleccionar todos los visibles ({nivel})", key=key_select_all
            )

            estado_aplicado = st.session_state.get(f"{key_select_all}_aplicado", False)

            if seleccionar_todos and not estado_aplicado:
                for g in grupos[:max_mostrar]:
                    secuencias = tuple(sorted(g["grupo_df"]["SECUENCIA"].astype(str)))
                    key_checkbox = (
                        f"{nivel}_{secuencias}_{g['fecha_desde']}_{g['fecha_hasta']}"
                    )
                    st.session_state.seleccion_grupos[key_checkbox] = True

                st.session_state[f"{key_select_all}_aplicado"] = True
                st.rerun()

            elif not seleccionar_todos and estado_aplicado:
                for g in grupos[:max_mostrar]:
                    secuencias = tuple(sorted(g["grupo_df"]["SECUENCIA"].astype(str)))
                    key_checkbox = (
                        f"{nivel}_{secuencias}_{g['fecha_desde']}_{g['fecha_hasta']}"
                    )
                    st.session_state.seleccion_grupos[key_checkbox] = False

                st.session_state[f"{key_select_all}_aplicado"] = False
                st.rerun()

            for i, g in enumerate(grupos[:max_mostrar], 1):
                secuencias = tuple(sorted(g["grupo_df"]["SECUENCIA"].astype(str)))
                secuencias_txt = ", ".join(
                    sorted(g["grupo_df"]["SECUENCIA"].astype(str).unique())
                )
                key_checkbox = (
                    f"{nivel}_{secuencias}_{g['fecha_desde']}_{g['fecha_hasta']}"
                )

                duracion_dias = dias_de_grupo(g)
                duracion_meses = duracion_dias // 30

                col_check, col_info = st.columns([0.08, 0.92])

                seleccionado = col_check.checkbox(
                    "",
                    key=key_checkbox,
                    value=st.session_state.seleccion_grupos.get(key_checkbox, False),
                )

                st.session_state.seleccion_grupos[key_checkbox] = seleccionado

                titulo = (
                    f"Grupo {i} | {duracion_meses}m aprox | "
                    f"Mod: {int(g['modulos'])} | Hs: {int(g['horas'])} | "
                    f"Sec: {secuencias_txt}"
                )

                with col_info.expander(titulo):
                    st.write(
                        f"{g['fecha_desde'].strftime('%d/%m/%Y')} -> "
                        f"{g['fecha_hasta'].strftime('%d/%m/%Y')}"
                    )
                    st.write(f"Duracion real: {g['anios']}a {g['meses']}m {g['dias']}d")
                    st.dataframe(g["grupo_df"], use_container_width=True)

                if st.session_state.seleccion_grupos.get(key_checkbox, False):
                    grupos_seleccionados.append({**g, "nivel": nivel})

# =====================================================
# RESULTADOS + EXPORT
# =====================================================

st.markdown("---")
st.subheader("Resumen del Tiempo Conformado")

if grupos_seleccionados:
    st.markdown("### Grupos seleccionados sin limpiar")

    seleccionados_vista = []

    for idx, g in enumerate(
        sorted(grupos_seleccionados, key=lambda x: x["fecha_desde"]), 1
    ):
        dias = dias_de_grupo(g)
        seleccionados_vista.append(
            {
                "Grupo": idx,
                "Nivel": g["nivel"],
                "Desde": g["fecha_desde"].strftime("%d/%m/%Y"),
                "Hasta": g["fecha_hasta"].strftime("%d/%m/%Y"),
                "Meses aprox": dias // 30,
                "Dias": dias,
                "Modulos": int(g["modulos"]),
                "Horas": int(g["horas"]),
                "Secuencias": ", ".join(
                    sorted(g["grupo_df"]["SECUENCIA"].astype(str).unique())
                ),
            }
        )

    st.dataframe(pd.DataFrame(seleccionados_vista), use_container_width=True)

grupos_validados = limpiar_grupos_superpuestos(grupos_seleccionados)

output = io.BytesIO()

with pd.ExcelWriter(output, engine="openpyxl") as writer:
    if grupos_validados:
        resumen_final = []
        total_dias = 0

        for idx, g in enumerate(grupos_validados, 1):
            dias_grupo = (g["fecha_hasta"] - g["fecha_desde"]).days + 1
            total_dias += dias_grupo

            resumen_final.append(
                {
                    "Grupo": idx,
                    "Nivel": g["nivel"],
                    "Desde": g["fecha_desde"].strftime("%d/%m/%Y"),
                    "Hasta": g["fecha_hasta"].strftime("%d/%m/%Y"),
                    "Tiempo": (
                        f"{g['anios_exactos']}a "
                        f"{g['meses_exactos']}m "
                        f"{g['dias_exactos']}d"
                    ),
                    "Anios": g["anios_exactos"],
                    "Meses": g["meses_exactos"],
                    "Dias": g["dias_exactos"],
                    "Modulos": g["modulos"],
                    "Horas": g["horas"],
                }
            )

        anios_total = total_dias // 365
        resto = total_dias % 365
        meses_total = resto // 30
        dias_total = resto % 30
        meses_total_aprox = total_dias // 30

        min_mod = min(g["modulos"] for g in grupos_validados)
        min_hs = min(g["horas"] for g in grupos_validados)

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Tiempo Conformado",
            f"{anios_total}a {meses_total}m {dias_total}d",
            delta=(
                f"{meses_total_aprox - 60}m"
                if meses_total_aprox >= 60
                else f"Faltan {60 - meses_total_aprox}m"
            ),
        )

        col2.metric("Minimo Modulos", int(min_mod))
        col3.metric("Minimo Horas", int(min_hs))

        df_resumen = pd.DataFrame(resumen_final)

        fila_total = pd.DataFrame(
            [
                {
                    "Grupo": "TOTAL",
                    "Nivel": "-",
                    "Desde": "-",
                    "Hasta": "-",
                    "Tiempo": f"{anios_total}a {meses_total}m {dias_total}d",
                    "Anios": anios_total,
                    "Meses": meses_total,
                    "Dias": dias_total,
                    "Modulos": min_mod,
                    "Horas": min_hs,
                }
            ]
        )

        df_resumen = pd.concat([df_resumen, fila_total], ignore_index=True)

        st.markdown("### Seleccion final sin superposiciones")
        st.dataframe(df_resumen, use_container_width=True)

        df_resumen.to_excel(writer, sheet_name="Resumen", index=False)

        for i, g in enumerate(grupos_validados, 1):
            df_temp = g["grupo_df"].copy()

            df_temp["DESDE"] = pd.to_datetime(df_temp["DESDE"]).dt.strftime("%d/%m/%Y")
            df_temp["HASTA"] = pd.to_datetime(df_temp["HASTA"]).dt.strftime("%d/%m/%Y")

            anios, meses, dias = calcular_antiguedad_exacta(
                g["fecha_desde"], g["fecha_hasta"]
            )

            info_grupo = pd.DataFrame(
                [
                    ["Fecha Desde Maxima", g["fecha_desde"].strftime("%d/%m/%Y")],
                    ["Fecha Hasta Minima", g["fecha_hasta"].strftime("%d/%m/%Y")],
                    ["Duracion", f"{anios}a {meses}m {dias}d"],
                    ["Modulos Totales", g["modulos"]],
                    ["Horas Totales", g["horas"]],
                ],
                columns=["Concepto", "Valor"],
            )

            info_grupo.to_excel(writer, sheet_name=f"Grupo_{i}", index=False)
            df_temp.to_excel(writer, sheet_name=f"Grupo_{i}", startrow=7, index=False)

    else:
        st.info("Selecciona grupos para generar resultados.")
        pd.DataFrame({"Info": ["Sin datos"]}).to_excel(
            writer, sheet_name="Sin_datos", index=False
        )

# =====================================================
# BOTON DESCARGA
# =====================================================

st.download_button(
    "Descargar Excel",
    data=output.getvalue(),
    file_name="60_meses_interseccion_manual.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)