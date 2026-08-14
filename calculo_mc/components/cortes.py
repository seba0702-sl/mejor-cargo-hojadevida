import pandas as pd


############################################
# 2️⃣ FUNCIÓN PARA EL CORTE DE LICENCIAS
############################################
# Corta los periodos de la hoja de vida según las licencias válidas.
# Pasos:
# 1. Normaliza nombres de columnas y convierte fechas a datetime.
# 2. Reemplaza "HOY" por la fecha actual.
# 3. Filtra licencias solo por secuencia y por códigos válidos.
# 4. Para cada periodo:
#       • Identifica si las licencias se superponen.
#       • Divide el periodo excluyendo cada rango de licencia.
#       • Calcula días, años, meses y días restantes.
# 5. Devuelve una tabla con todos los cortes resultantes por secuencia.
# Esta función es el corazón del cálculo de periodos reales trabajados.
def corte_con_licencias(hoja_vida, hoja_licencias, CODIGOS_VALIDOS):

    # Normalizar nombres de columnas
    hoja_vida.columns = hoja_vida.columns.astype(str).str.upper().str.strip()
    hoja_licencias.columns = hoja_licencias.columns.str.upper().str.strip()

    # Identificación de columnas
    col_secuencia = next((c for c in hoja_vida.columns if "SECUENCIA" in c), None)
    col_escuela = next((c for c in hoja_vida.columns if "ESCUELA" in c), None)
    col_cargo = next((c for c in hoja_vida.columns if "CARGO" in c), None)
    col_desde = next((c for c in hoja_vida.columns if "DESDE" in c), None)
    col_hasta = next((c for c in hoja_vida.columns if "HASTA" in c), None)
    col_carga = next((c for c in hoja_vida.columns if "CARGA" in c), None)

    columnas_faltantes = [
        name
        for name, val in {
            "SECUENCIA": col_secuencia,
            "ESCUELA": col_escuela,
            "CARGO": col_cargo,
            "DESDE": col_desde,
            "HASTA": col_hasta,
            "CARGA HORARIA": col_carga,
        }.items()
        if val is None
    ]

    if columnas_faltantes:
        raise KeyError(f"Faltan columnas en hoja_vida: {', '.join(columnas_faltantes)}")

    hoy = pd.Timestamp.today().normalize()

    # Normalizar fechas
    hoja_vida[col_desde] = pd.to_datetime(
        hoja_vida[col_desde], dayfirst=True, errors="coerce"
    )
    hoja_vida[col_hasta] = hoja_vida[col_hasta].replace("HOY", hoy)
    hoja_vida[col_hasta] = pd.to_datetime(
        hoja_vida[col_hasta], dayfirst=True, errors="coerce"
    )

    hoja_licencias["DESDE"] = pd.to_datetime(
        hoja_licencias["DESDE"], dayfirst=True, errors="coerce"
    )
    hoja_licencias["HASTA"] = hoja_licencias["HASTA"].replace("HOY", hoy)
    hoja_licencias["HASTA"] = pd.to_datetime(
        hoja_licencias["HASTA"], dayfirst=True, errors="coerce"
    )

    # Normalizar CODIGOS_VALIDOS como string
    CODIGOS_VALIDOS = [str(c).strip() for c in CODIGOS_VALIDOS]

    nueva_tabla = []

    for _, fila in hoja_vida.iterrows():

        secuencia = fila[col_secuencia]
        escuela = fila[col_escuela]
        cargo = fila[col_cargo]
        carga_horaria = fila[col_carga]
        fecha_desde = fila[col_desde]
        fecha_hasta = fila[col_hasta]

        # Reemplazar fechas faltantes
        if pd.isna(fecha_desde) and pd.isna(fecha_hasta):
            fecha_desde = fecha_hasta = hoy
        elif pd.isna(fecha_desde):
            fecha_desde = fecha_hasta
        elif pd.isna(fecha_hasta):
            fecha_hasta = fecha_desde

        # Corregir fechas invertidas
        if fecha_desde > fecha_hasta:
            fecha_desde, fecha_hasta = fecha_hasta, fecha_desde

            # ------------------------------------------
        # 🔒 PDF: si la secuencia es >= 1000, NO cortar
        # ------------------------------------------
        if str(secuencia).isdigit() and int(secuencia) >= 1000:
            # Si falta alguna fecha se corrige igual que en el resto
            if pd.isna(fecha_desde) and pd.isna(fecha_hasta):
                fecha_desde = fecha_hasta = hoy
            elif pd.isna(fecha_desde):
                fecha_desde = fecha_hasta
            elif pd.isna(fecha_hasta):
                fecha_hasta = fecha_desde

            # Corregir fechas invertidas
            if fecha_desde > fecha_hasta:
                fecha_desde, fecha_hasta = fecha_hasta, fecha_desde

            diff = (fecha_hasta - fecha_desde).days + 1

            nueva_tabla.append(
                [
                    secuencia,
                    cargo,
                    fecha_desde,
                    fecha_hasta,
                    diff,
                    diff // 365,
                    (diff % 365) // 30,
                    (diff % 365) % 30,
                    escuela,
                    carga_horaria,
                ]
            )
            continue

        # Filtrar licencias
        licencias_rel = hoja_licencias[
            (hoja_licencias["SECUENCIA"] == secuencia)
            & (hoja_licencias["ENCUADRE"].astype(str).isin(CODIGOS_VALIDOS))
        ]
        if "ESCUELA" in hoja_licencias.columns:
            licencias_rel = licencias_rel[licencias_rel["ESCUELA"] == escuela]

        periodos_cortados = [
            (d["DESDE"], d["HASTA"]) for _, d in licencias_rel.iterrows()
        ]
        # Validar fechas
        if pd.isna(fecha_desde) and not pd.isna(fecha_hasta):
            fecha_desde = fecha_hasta - pd.Timedelta(days=int(fila.get("DIAS", 0)) - 1)
        elif pd.isna(fecha_hasta) and not pd.isna(fecha_desde):
            fecha_hasta = fecha_desde + pd.Timedelta(days=int(fila.get("DIAS", 0)) - 1)
        elif pd.isna(fecha_desde) and pd.isna(fecha_hasta):
            fecha_desde = fecha_hasta = hoy  # fallback
        # Si no hay licencias, agregar todo
        if not periodos_cortados:
            diff = (fecha_hasta - fecha_desde).days + 1
            nueva_tabla.append(
                [
                    secuencia,
                    cargo,
                    fecha_desde,
                    fecha_hasta,
                    diff,
                    diff // 365,
                    (diff % 365) // 30,
                    (diff % 365) % 30,
                    escuela,
                    carga_horaria,
                ]
            )
            continue

        # Intersección de licencias
        lic_dentro = [
            (max(fecha_desde, d), min(fecha_hasta, h))
            for (d, h) in periodos_cortados
            if fecha_hasta >= d and fecha_desde <= h
        ]
        lic_dentro.sort(key=lambda x: x[0])
        inicio = fecha_desde

        for lic_desde, lic_hasta in lic_dentro:
            # Excluir día de licencia
            nuevo_hasta = lic_desde - pd.Timedelta(days=1)
            if inicio <= nuevo_hasta:
                diff = (nuevo_hasta - inicio).days + 1
                nueva_tabla.append(
                    [
                        secuencia,
                        cargo,
                        inicio,
                        nuevo_hasta,
                        diff,
                        diff // 365,
                        (diff % 365) // 30,
                        (diff % 365) % 30,
                        escuela,
                        carga_horaria,
                    ]
                )
            inicio = lic_hasta + pd.Timedelta(days=1)

        # Último tramo
        if inicio <= fecha_hasta:
            diff = (fecha_hasta - inicio).days + 1
            nueva_tabla.append(
                [
                    secuencia,
                    cargo,
                    inicio,
                    fecha_hasta,
                    diff,
                    diff // 365,
                    (diff % 365) // 30,
                    (diff % 365) % 30,
                    escuela,
                    carga_horaria,
                ]
            )

    columnas = [
        "SECUENCIA",
        "CARGO",
        "DESDE",
        "HASTA",
        "DIAS",
        "AÑOS",
        "MESES",
        "DIAS_RESTANTES",
        "ESCUELA",
        "CARGA HORARIA",
    ]
    return pd.DataFrame(nueva_tabla, columns=columnas)


import pandas as pd



############################################
# 3️⃣ CONSOLIDAR PERÍODOS (CORREGIDO)
############################################
# Consolida períodos continuos o adyacentes por SECUENCIA.
# Regla de continuidad: un periodo comienza el día siguiente al anterior.
# Pasos:
# 1. Convierte fechas y elimina filas con fechas no válidas.
# 2. Ordena por secuencia y fecha DESDE.
# 3. Agrupa secuencias y acumula días si los periodos son consecutivos.
# 4. Marca con CONSOLIDADO=True los grupos que superan el umbral (1095 días = 3 años).
# 5. Devuelve un DataFrame con los periodos etiquetados.
# Usado para detectar bloques de trabajo largos o continuos.
def consolidar_periodos_continuos(df_periodos, umbral_dias=1095):

    if df_periodos.empty:
        return pd.DataFrame()

    df = df_periodos.copy()

    # Siempre a datetime
    df["DESDE"] = pd.to_datetime(df["DESDE"], dayfirst=True, errors="coerce")
    df["HASTA"] = pd.to_datetime(df["HASTA"], dayfirst=True, errors="coerce")

    df = df.dropna(subset=["DESDE", "HASTA"])
    df = df.sort_values(["SECUENCIA", "DESDE"])

    resultado = []

    for secuencia, grupo in df.groupby("SECUENCIA"):

        # ----------------------------------------
        # 🔵 PDF: si la secuencia >= 1000 → pasar tal cual
        # ----------------------------------------
        if str(secuencia).isdigit() and int(secuencia) >= 1000:
            for _, fila in grupo.iterrows():
                fila2 = fila.copy()
                fila2["CONSOLIDADO"] = True  # SIEMPRE consolidado
                resultado.append(fila2)
            continue

        # ----------------------------------------
        # 🔵 Lógica normal (Excel / pegados)
        # ----------------------------------------
        acumulado = []
        dias_total = 0
        fin = None

        for _, fila in grupo.iterrows():
            inicio = fila["DESDE"]
            final = fila["HASTA"]

            if not acumulado:
                acumulado = [fila]
                dias_total = fila["DIAS"]
                fin = final
                continue

            # Si son continuos
            if inicio <= fin + pd.Timedelta(days=1):
                acumulado.append(fila)
                dias_total += fila["DIAS"]
                fin = max(fin, final)
            else:
                # Cerrar acumulado
                for r in acumulado:
                    r2 = r.copy()
                    r2["CONSOLIDADO"] = dias_total >= umbral_dias
                    resultado.append(r2)

                acumulado = [fila]
                dias_total = fila["DIAS"]
                fin = final

        # Último acumulado
        if acumulado:
            for r in acumulado:
                r2 = r.copy()
                r2["CONSOLIDADO"] = dias_total >= umbral_dias
                resultado.append(r2)

    return pd.DataFrame(resultado).sort_values(["SECUENCIA", "DESDE"])
