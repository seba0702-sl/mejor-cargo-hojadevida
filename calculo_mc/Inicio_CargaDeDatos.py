import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import StringIO
from components.cortes import consolidar_periodos_continuos, corte_con_licencias
from services.constants import (
    niveles_dict,
    niveles_dictpdf,
    CODIGOS_VALIDOS,
    ENCABEZADOS_LIC,
    ENCABEZADOS_VIDA,
)

st.set_page_config(page_title="Inicio - Carga de datos", layout="wide")
st.title("SISTEMA PARA CALCULO Y ELECCION MEJOR CARGO")


def normalizar_fechas(df):
    hoy = pd.Timestamp.today().normalize()

    def parse_fecha(x):

        if pd.isna(x):
            return pd.NaT

        if isinstance(x, pd.Timestamp):
            return x.normalize()

        if isinstance(x, (int, float)) and x > 30000:
            return (
            pd.to_datetime("1899-12-30")
            + pd.to_timedelta(int(x), unit="D")
        )

        x = str(x).strip()

        if x.upper() == "HOY":
            return hoy

    # -----------------------------
    # Excel -> AAAA-MM-DD
    # -----------------------------
        if re.match(r"^\d{4}-\d{2}-\d{2}", x):
            return pd.to_datetime(x, format="%Y-%m-%d %H:%M:%S", errors="coerce")

    # -----------------------------
    # Pegado/PDF -> DD/MM/AAAA
    # -----------------------------
        if re.match(r"^\d{2}/\d{2}/\d{4}", x):
            return pd.to_datetime(x, format="%d/%m/%Y", errors="coerce")

    # -----------------------------
    # Último recurso
    # -----------------------------
        return pd.to_datetime(x, dayfirst=True, errors="coerce")

    for col in ["DESDE", "HASTA"]:
        if col in df.columns:
            df[col] = df[col].apply(parse_fecha)

    return df


def normalizar_df(df, encabezados):
    df = df.copy()

    if all(col in df.columns for col in encabezados):
        return df

    if len(df.columns) == len(encabezados):
        df.columns = encabezados
        return df

    df = df.iloc[:, : len(encabezados)]
    df.columns = encabezados
    return df


def cargar_hoja_excel(archivo, nombre_hoja, encabezados=None):
    try:
        df = pd.read_excel(
    archivo,
    sheet_name=nombre_hoja,
    header=None,
    dtype=str,
    engine="openpyxl"
)

        if encabezados is not None:
            df = df.iloc[:, : len(encabezados)]
            df.columns = encabezados
        else:
            df.columns = [f"col_{i}" for i in range(df.shape[1])]

        df = df.dropna(how="all")
        df = normalizar_fechas(df)

        return df

    except Exception as e:
        raise ValueError(f"Error al cargar la hoja '{nombre_hoja}': {e}")


def cargar_hoja_pegada(texto, encabezados):
    sep = "\t" if "\t" in texto else ","
    df = pd.read_csv(StringIO(texto), sep=sep, header=None, dtype=str)
    df = normalizar_df(df, encabezados)
    df = normalizar_fechas(df)
    return df


def detectar_nivel_en_linea(texto, niveles):
    texto = str(texto).upper()

    for nivel, palabras in niveles.items():
        for p in palabras:
            if re.search(rf"\b{re.escape(p.upper())}\b", texto):
                return nivel

    return None


def detectar_nivel_desde_escuela(escuela):
    esc = str(escuela or "").upper()
    esc = (
        esc.replace("Á", "A")
           .replace("É", "E")
           .replace("Í", "I")
           .replace("Ó", "O")
           .replace("Ú", "U")
    )
    esc = re.sub(r"\s+", " ", esc).strip()

    # ADULTO
    if any(x in esc for x in [
        "C. E. N. S",
        "C.E.N.S",
        "C E N S",
        "CENS",
        "CENTRO DE FORM. PROF",
        "CENTRO DE FORMACION PROF",
        "FORMACION PROFESIONAL",
        "CFP",
        "ADULTOS",
        "CENTRO EDUCATIVO NIVEL SECUNDARIO","DM", "CENS", "DF", "DS", "MF", "ADULTOS", "ADULTO", "CFP", "CFL",
    ]):
        return "Adulto"

    # SECUNDARIA
    if any(x in esc for x in [
        "ESC. DE ENS. MEDIA",
        "ESC DE ENS MEDIA",
        "ESCUELA DE EDUCACION MEDIA",
        "ESC. DE EDUC. SECUNDARIA",
        "ESC DE EDUC SECUNDARIA",
        "ESCUELA DE EDUCACION SECUNDARIA",
        "ESC. SECUNDARIA BASICA",
        "ESCUELA SECUNDARIA BASICA",
        "ESC. SECUND. TECNICA",
        "ESCUELA DE EDUCACION SECUNDARIA TECNICA",
        "MM","MS", "ES", "ESB", "MT", "BS", "MA", "MC", "AS",
    ]):
        return "Secundaria"

    # INICIAL
    if any(x in esc for x in [
        "JARDIN",
        "JARDIN DE INFANTES",
        "JARDIN MATERNAL",
        "INICIAL",
        "PREESCOLAR",
        "JI","JS",
        "JU",
        "JM",
        "JV",
    ]):
        return "Inicial"

    # SUPERIOR
    if any(x in esc for x in [
        "INSTITUTO SUPERIOR",
        "INSTITUTO",
        "SUPERIOR",
        "INST. SUP.",
        "INST SUPERIOR",
        "CEF",
        "CENTRO DE EDUC. FISICA",
        "FC","IS", "AA", "AT", "AF", "AV", "AC", "AD", "AM", "AP", "FC",
    ]):
        return "Superior"

    # ESPECIAL
    if any(x in esc for x in [
        "ESPECIAL",
        "ESC. ESP.",
        "ESP.",
        "CENTRO DE FORMACION INTEGRAL",
        "CFI","EE", "EL", "CFI", "ET", "ESPECIAL",
    ]):
        return "Especial"

    # PRIMARIA
    if any(x in esc for x in [
        "ESCUELA PRIMARIA",
        "EDUCACION PRIMARIA",
        "PRIMARIA BASICA",
        "PRIMARIA",
        "E.P.",
        "EP N",
        "ESCUELA PRIMARIA BASICA",
        "PP","PP", "EP", "PA", "DA", "DC", "DE",
    ]):
        return "Primaria"

    return ""
def detectar_tipo_carga_desde_fila(escuela, cargo, nivel=""):
    """
    Decide si la carga de la fila va a HORAS_CATEDRA o MODULOS
    usando NIVEL / ESCUELA / CARGO.
    """
    txt = " ".join([
        str(nivel or ""),
        str(escuela or ""),
        str(cargo or "")
    ]).upper()

    txt = (
        txt.replace("Á", "A")
           .replace("É", "E")
           .replace("Í", "I")
           .replace("Ó", "O")
           .replace("Ú", "U")
    )
    txt = re.sub(r"\s+", " ", txt).strip()

    # -----------------------------------------
    # MODULOS
    # -----------------------------------------
    if any(x in txt for x in [
        "MODULO",
        "MODULOS",
        "HORAS MODULO",
        "HS. MODULO",
        "PROFESOR HS. MODULO",
    ]):
        return "MODULOS"

    # -----------------------------------------
    # HORAS CATEDRA
    # -----------------------------------------
    if any(x in txt for x in [
        "HORAS DE CATEDRA",
        "HORAS CATEDRA",
        "HS. CATEDRA",
        "HS CATEDRA",
        "CAT.",
        "CATEDRA",
        "CATEDRAS",
        "HORAS",
        "INSTRUCTOR"
    ]):
        return "HORAS_CATEDRA"

    return ""


def completar_carga_y_nivel_hoja_vida(df):
    """
    Completa NIVEL, HORAS_CATEDRA y MODULOS para hoja de vida
    venga de Excel, pegado o PDF.
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    df.columns = df.columns.astype(str).str.upper().str.strip()

    # asegurar columnas
    # NIVEL (texto)
    if "NIVEL" not in df.columns:
        df["NIVEL"] = ""

# HORAS_CATEDRA (numérico)
    if "HORAS_CATEDRA" not in df.columns:
        df["HORAS_CATEDRA"] = pd.Series(
        0,
        index=df.index,
        dtype="Int64"
    )
    else:
        df["HORAS_CATEDRA"] = pd.to_numeric(
        df["HORAS_CATEDRA"],
        errors="coerce"
    ).fillna(0).astype("Int64")

# MODULOS (numérico)
    if "MODULOS" not in df.columns:
        df["MODULOS"] = pd.Series(
        0,
        index=df.index,
        dtype="Int64"
    )
    else:
        df["MODULOS"] = pd.to_numeric(
        df["MODULOS"],
        errors="coerce"
    ).fillna(0).astype("Int64")
    #st.write("TIPOS DENTRO DE completar_carga_y_nivel_hoja_vida")
    #st.write(df[["NIVEL","HORAS_CATEDRA","MODULOS"]].dtypes)
    col_escuela = next((c for c in df.columns if "ESCUELA" in c), None)
    col_cargo = next((c for c in df.columns if "CARGO" in c), None)
    col_carga = next((c for c in df.columns if "CARGA" in c), None)

    if col_escuela is None:
        return df

    # -----------------------------------------
    # NIVEL
    # -----------------------------------------
    for i in df.index:
        escuela = df.at[i, col_escuela] if col_escuela in df.columns else ""
        cargo = df.at[i, col_cargo] if col_cargo in df.columns else ""

        nivel_actual = str(df.at[i, "NIVEL"]).strip() if "NIVEL" in df.columns else ""

        if not nivel_actual:
            df.at[i, "NIVEL"] = detectar_nivel_desde_escuela(escuela)

    # -----------------------------------------
    # HORAS_CATEDRA / MODULOS
    # -----------------------------------------
    if col_carga is not None:
        for i in df.index:
            carga = pd.to_numeric(df.at[i, col_carga], errors="coerce")
            if pd.isna(carga):
                continue

            carga = int(carga)

            escuela = df.at[i, col_escuela] if col_escuela in df.columns else ""
            cargo = df.at[i, col_cargo] if col_cargo in df.columns else ""
            nivel = df.at[i, "NIVEL"] if "NIVEL" in df.columns else ""

            tipo = detectar_tipo_carga_desde_fila(escuela, cargo, nivel)

            if tipo == "MODULOS":
                df.at[i, "MODULOS"] = int(carga)

            elif tipo == "HORAS_CATEDRA":
                df.at[i, "HORAS_CATEDRA"] = int(carga)

    return df

def extraer_datos_diegep(pdf_file):
    data_vida, data_licencias = [], []

    with pdfplumber.open(pdf_file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    empleador_match = re.search(r"EMPLEADOR:([^\n]+)", text)
    empleador = empleador_match.group(1).strip() if empleador_match else "DIEGEP"

    encabezado_match = re.search(
        r"SERVICIOS PRESTADOS REMUNERADOS CON APORTES\s*\n([^\n]+)",
        text,
        re.I,
    )

    linea_nivel = encabezado_match.group(1).strip().upper() if encabezado_match else ""
    nivel_global = detectar_nivel_en_linea(linea_nivel, niveles_dictpdf)

    historial_match = re.search(
        r"HISTORIAL DE PER[IÍ]ODOS LABORALES(.*?)(?:PER[IÍ]ODO LICENCIA|Firmar)",
        text,
        re.S,
    )

    lineas = [
        linea.strip()
        for linea in (historial_match.group(1) if historial_match else "").splitlines()
        if linea.strip()
    ]

    for linea in lineas:
        if not (
            re.search(r"\(\d+\)", linea)
            and re.search(r"\d{2}/\d{2}/\d{4}", linea)
        ):
            continue

        fechas = re.findall(r"\d{2}/\d{2}/\d{4}", linea)

        if len(fechas) < 2:
            continue

        f1 = pd.to_datetime(fechas[0], dayfirst=True, errors="coerce")
        f2 = pd.to_datetime(fechas[1], dayfirst=True, errors="coerce")

        desde = f1.strftime("%d/%m/%Y") if not pd.isna(f1) else ""
        hasta = f2.strftime("%d/%m/%Y") if not pd.isna(f2) else ""

        cargo_match = re.search(r"([A-ZÁÉÍÓÚÑa-z\s\.\-]+)\s*\((\d+)\)", linea)

        if not cargo_match:
            continue

        cargo = cargo_match.group(1).strip()
        secuencia = cargo_match.group(2)

        if nivel_global:
            escuela_final = f"{empleador} - {nivel_global}"
        else:
            escuela_final = empleador

        horas_match = re.search(r"\b(\d{1,2})\s*(?:HS|HORAS)?\b", linea)
        carga_horaria = horas_match.group(1) if horas_match else ""

        data_vida.append([secuencia, escuela_final, cargo, carga_horaria, desde, hasta])

    df_vida = pd.DataFrame(
        data_vida,
        columns=["SECUENCIA", "ESCUELA", "CARGO", "CARGA HORARIA", "DESDE", "HASTA"],
    ).drop_duplicates(subset=["SECUENCIA", "DESDE", "HASTA"])

    df_lic = pd.DataFrame(
        data_licencias,
        columns=[
            "SECUENCIA",
            "ESTABLECIMIENTO",
            "CARGA HORARIA",
            "DESDE",
            "HASTA",
            "ENCUADRE",
        ],
    ).drop_duplicates(subset=["DESDE", "HASTA", "ENCUADRE"])

    df_vida = normalizar_fechas(df_vida)
    df_lic = normalizar_fechas(df_lic)

    return df_vida, df_lic


def extraer_certificacion_dgcye(pdf_file):
    import pdfplumber
    import pandas as pd
    import re

    def normalizar_texto(s):
        s = str(s or "").upper()
        s = (
            s.replace("Á", "A")
             .replace("É", "E")
             .replace("Í", "I")
             .replace("Ó", "O")
             .replace("Ú", "U")
        )
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def extraer_nivel_pdf_desde_establecimiento(escuela):
        esc = str(escuela or "").strip()
        esc_norm = normalizar_texto(esc)

        patrones = [
            "ESC. DE EDUC. SECUNDARIA",
            "ESC. DE ENS. MEDIA",
            "ESC. SECUNDARIA BASICA",
            "ESC. SECUND. TECNICA",
            "C. E. N. S.",
            "C.E.N.S.",
            "CENS",
            "CENTRO DE FORM. PROF.",
            "CENTRO DE FORMACION PROF.",
            "JARDIN DE INFANTES",
            "JARDIN MATERNAL",
            "ESCUELA PRIMARIA",
            "INSTITUTO SUPERIOR",
            "INSTITUTO",
            "SUPERIOR",
            "ESPECIAL",
            "ESP.",
            "PRIMARIA",
        ]

        for patron in sorted(patrones, key=len, reverse=True):
            if normalizar_texto(patron) in esc_norm:
                return patron

        partes = re.split(r"\s*-\s*", esc, maxsplit=1)
        if partes and partes[0].strip():
            return partes[0].strip()

        return ""

    def homologar_nivel(nivel_pdf, escuela):
        niv = normalizar_texto(nivel_pdf)
        esc = normalizar_texto(escuela)

        if any(x in niv for x in [
            "C. E. N. S", "C.E.N.S", "C E N S", "CENS",
            "CENTRO DE FORM. PROF", "CENTRO DE FORMACION PROF",
            "FORMACION PROFESIONAL",
        ]):
            return "Adulto"

        if any(x in esc for x in [
            "C. E. N. S", "C.E.N.S", "C E N S", "CENS",
            "ADULTOS", "CFP", "CENTRO DE FORM. PROF",
            "CENTRO DE FORMACION PROF", "FORMACION PROFESIONAL",
            "CENTRO EDUCATIVO NIVEL SECUNDARIO",
        ]):
            return "Adulto"

        if any(x in niv for x in [
            "ESC. DE ENS. MEDIA",
            "ESC. DE EDUC. SECUNDARIA",
            "ESC. SECUNDARIA BASICA",
            "ESC. SECUND. TECNICA",
        ]):
            return "Secundaria"

        if any(x in esc for x in [
            "ESC. DE ENS. MEDIA",
            "ESC DE ENS MEDIA",
            "ESCUELA DE EDUCACION MEDIA",
            "ESC. DE EDUC. SECUNDARIA",
            "ESC DE EDUC SECUNDARIA",
            "ESCUELA DE EDUCACION SECUNDARIA",
            "ESC. SECUNDARIA BASICA",
            "ESC. SECUND. TECNICA",
            "ESCUELA DE EDUCACION SECUNDARIA TECNICA",
            "MM", "MS",
        ]):
            return "Secundaria"

        if any(x in niv for x in [
            "JARDIN DE INFANTES",
            "JARDIN MATERNAL",
            "INICIAL",
        ]):
            return "Inicial"

        if any(x in esc for x in [
            "JARDIN",
            "JARDIN DE INFANTES",
            "INICIAL",
            "PREESCOLAR",
            "JI",
        ]):
            return "Inicial"

        if any(x in niv for x in [
            "INSTITUTO SUPERIOR",
            "INSTITUTO",
            "SUPERIOR",
        ]):
            return "Superior"

        if any(x in esc for x in [
            "INSTITUTO",
            "SUPERIOR",
            "INST. SUP.",
            "INST SUPERIOR",
            "CEF",
            "CENTRO DE EDUC. FISICA",
            "FC",
        ]):
            return "Superior"

        if any(x in niv for x in ["ESPECIAL", "ESP."]):
            return "Especial"

        if any(x in esc for x in [
            "ESPECIAL",
            "ESC. ESP.",
            "CENTRO DE FORMACION INTEGRAL",
            "CFI",
        ]):
            return "Especial"

        if any(x in niv for x in ["ESCUELA PRIMARIA", "PRIMARIA"]):
            return "Primaria"

        if any(x in esc for x in [
            "ESCUELA PRIMARIA",
            "EDUCACION PRIMARIA",
            "PRIMARIA BASICA",
            "EP N",
            "E.P. N",
            "PP",
            "ESCUELA PRIMARIA BASICA",
        ]):
            return "Primaria"

        return ""

    def repartir_carga_por_tipo(carga, nivel_ensenanza_pdf):
        """
        Si el NIVEL ENSEÑANZA del PDF dice HORAS MODULO -> va a MODULOS
        Si dice HORAS CATEDRA -> va a HORAS_CATEDRA
        """
        carga_num = pd.to_numeric(carga, errors="coerce")
        if pd.isna(carga_num):
            return "", ""

        carga_num = int(carga_num)
        nivel_txt = normalizar_texto(nivel_ensenanza_pdf)

        horas_catedra = ""
        modulos = ""

        if "HORAS MODULO" in nivel_txt:
            modulos = carga_num
        elif "HORAS DE CATEDRA" in nivel_txt:
            horas_catedra = carga_num

        return horas_catedra, modulos

    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto += "\n" + (pagina.extract_text() or "")

    ini = texto.find("HISTORIAL DE PERÍODOS LABORALES")
    if ini == -1:
        ini = texto.find("HISTORIAL DE PERIODOS LABORALES")

    if ini == -1:
        return pd.DataFrame(columns=[
            "SECUENCIA",
            "NIVEL_ENSENANZA_PDF",
            "NIVEL_PDF",
            "NIVEL",
            "ESCUELA",
            "CARGO",
            "CARGA HORARIA",
            "HORAS_CATEDRA",
            "MODULOS",
            "DESDE",
            "HASTA",
        ])

    # ---------------------------------------------------------
    # FIN DEL HISTORIAL
    # ---------------------------------------------------------
    candidatos_fin = []
    for marca in [
        "CESE DEFINITIVO",
        "CARGO DE MAYOR JERARQUÍA",
        "CARGO DE MAYOR JERARQUIA",
        "El empleador extiende la presente certificación",
    ]:
        pos = texto.find(marca, ini)
        if pos != -1:
            candidatos_fin.append(pos)

    fin = min(candidatos_fin) if candidatos_fin else len(texto)

    historial = texto[ini:fin]
    lineas = historial.splitlines()

    filas = []

    textos_ignorar = [
        "HISTORIAL DE PERÍODOS LABORALES",
        "HISTORIAL DE PERIODOS LABORALES",
        "CUIL:",
        "APELLIDO Y NOMBRE:",
        "CÓD. EMPLEADOR:",
        "COD. EMPLEADOR:",
        "EMPLEADOR:",
        "NIVEL ENSEÑANZA",
        "ESTABLECIMIENTO",
        "CARGO HORAS DESDE HASTA",
        "AÑOS MESES DIAS",
        "AÑOS MESES DÍAS",
        "TOTAL DE SERVICIOS",
        "TOTAL DE SERVICIOS DOCENTES",
        "TOTAL DE SERVICIOS DOCENTES TITULARES",
        "TOTAL DE SERVICIOS DOCENTES SUPLENTES",
        "CARGO DE MAYOR JERARQUÍA",
        "CARGO DE MAYOR JERARQUIA",
        "BONIFICACIONES",
        "DESCUENTOS PRACTICADOS",
        "TIPO DE SERVICIO",
        "LICENCIAS",
        "SERVICIOS DOCENTES TITULARES",
        "SERVICIOS DOCENTES SUPLENTES Y/O PROVISIONALES",
        "SERVICIOS PRESTADOS REMUNERADOS",
        "AGRUPAMIENTO",
        "OTRAS BONIFICACIONES",
        "DESIGNACIÓN:",
        "DESIGNACION:",
        "CARGO NUMERO DE CARGO",
        "NUMERO DE CARGO:",
        "FECHA DEL ACTA",
    ]

    palabras_cargo = [
        "ENCARGADO DE MEDIOS DE APOYO TEC. PEDAGOGICOS",
        "ENCARGADO DE MEDIOS DE APOYO TÉC. PEDAGÓGICOS",
        "PROFESOR HS. MODULO MEDIA",
        "PROFESOR HS. MÓDULO MEDIA",
        "PROFESOR HS. MODULO EGB",
        "PROFESOR HS. MÓDULO EGB",
        "PROFESOR DE EDUCACION FISICA",
        "PROFESOR DE EDUCACIÓN FÍSICA",
        "MAESTRO DE SECCION",
        "MAESTRO DE GRADO",
        "VICE DIRECTOR",
        "VICEDIRECTOR",
        "PROSECRETARIO",
        "SUBREGENTE",
        "BIBLIOTECARIO",
        "SECRETARIO",
        "PRECEPTOR",
        "DIRECTOR",
        "REGENTE",
        "PROFESOR",
        "MAESTRO",
        "JEFE",
    ]
    palabras_cargo = sorted(palabras_cargo, key=len, reverse=True)

    prefijos_no_establecimiento = [
        "ENSEÑANZA TECNICA Y FORMACION PROFESIONAL; ARTISTICA; SUPERIOR; MEDIA; AGRARIA; SECUNDARIA",
        "ENSEÑANZA TÉCNICA Y FORMACIÓN PROFESIONAL; ARTÍSTICA; SUPERIOR; MEDIA; AGRARIA; SECUNDARIA",
        "HORAS DE CATEDRA"
        "HORAS CATEDRA",
        "HORAS MODULO",
        "PREESCOLAR",
        "PRIMARIA",
        "SECUNDARIA",
        "SUPERIOR",
        "ESPECIAL",
        "ADULTOS",
        "INICIAL",
        "INSTRUCTOR"
    ]
    prefijos_no_establecimiento = sorted(prefijos_no_establecimiento, key=len, reverse=True)

    for linea in lineas:
        linea = re.sub(r"\s+", " ", linea).strip()
        if not linea:
            continue

        linea_upper = normalizar_texto(linea)

        if any(normalizar_texto(t) in linea_upper for t in textos_ignorar):
            continue

        sec_match = re.search(r"\((\d+)\)", linea)
        fechas = re.findall(r"\d{2}/\d{2}/\d{4}", linea)

        if not sec_match or len(fechas) < 2:
            continue

        secuencia = sec_match.group(1)
        desde = fechas[0]
        hasta = fechas[1]

        idx_seq = linea.find(f"({secuencia})")
        if idx_seq == -1:
            continue

        antes_seq = linea[:idx_seq].strip()
        despues_seq = linea[idx_seq + len(f"({secuencia})"):].strip()

        # ---------------------------------------------------------
        # CARGA HORARIA: número que está después de (secuencia)
        # ---------------------------------------------------------
        carga = ""
        m_carga = re.match(r"(\d{1,2})\s+\d{2}/\d{2}/\d{4}", despues_seq)
        if m_carga:
            carga = m_carga.group(1)

        texto_base = antes_seq
        texto_norm = normalizar_texto(texto_base)

        nivel_ensenanza_pdf = ""
        resto = texto_base

        for pref in prefijos_no_establecimiento:
            pref_norm = normalizar_texto(pref)
            if texto_norm.startswith(pref_norm):
                nivel_ensenanza_pdf = pref
                resto = texto_base[len(pref):].strip(" -")
                break

        resto_upper = normalizar_texto(resto)
        pos_cargo = -1

        for palabra in palabras_cargo:
            palabra_norm = normalizar_texto(palabra)
            p = resto_upper.rfind(palabra_norm)
            if p > pos_cargo:
                pos_cargo = p

        if pos_cargo != -1:
            escuela = resto[:pos_cargo].strip(" -")
            cargo = resto[pos_cargo:].strip(" -")
        else:
            escuela = resto.strip(" -")
            cargo = ""

        escuela = re.sub(r"\s+", " ", escuela).strip(" -")
        cargo = re.sub(r"\s+", " ", cargo).strip(" -")
        cargo = re.sub(r"\s*\(\d+\)\s*$", "", cargo).strip()

        nivel_pdf = extraer_nivel_pdf_desde_establecimiento(escuela)
        nivel = homologar_nivel(nivel_pdf, escuela)

        horas_catedra, modulos = repartir_carga_por_tipo(carga, nivel_ensenanza_pdf)

        filas.append({
            "SECUENCIA": secuencia,
            "NIVEL_ENSENANZA_PDF": nivel_ensenanza_pdf,
            "NIVEL_PDF": nivel_pdf,
            "NIVEL": nivel,
            "ESCUELA": escuela,
            "CARGO": cargo,
            "CARGA HORARIA": carga,
            "HORAS_CATEDRA": horas_catedra,
            "MODULOS": modulos,
            "DESDE": desde,
            "HASTA": hasta,
        })

    df = pd.DataFrame(filas, columns=[
        "SECUENCIA",
        "NIVEL_ENSENANZA_PDF",
        "NIVEL_PDF",
        "NIVEL",
        "ESCUELA",
        "CARGO",
        "CARGA HORARIA",
        "HORAS_CATEDRA",
        "MODULOS",
        "DESDE",
        "HASTA",
    ])

    if df.empty:
        return df

    df = df.drop_duplicates().copy()
    df["SECUENCIA"] = pd.to_numeric(df["SECUENCIA"], errors="coerce")
    df["DESDE"] = pd.to_datetime(df["DESDE"], dayfirst=True, errors="coerce")
    df["HASTA"] = pd.to_datetime(df["HASTA"], dayfirst=True, errors="coerce")

    df = df.sort_values(["DESDE", "SECUENCIA"], na_position="last").reset_index(drop=True)
    return df


def main():
    st.title("Ficha de Carga de Datos")

    st.subheader("Datos personales del docente")

    datos_guardados = st.session_state.get("datos_personales", {})

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        nombre = st.text_input(
            "Nombre y apellido",
            value=datos_guardados.get("Nombre y apellido", ""),
            key="nombre_input",
        )

    with col2:
        edad = st.number_input(
            "Edad",
            min_value=0,
            max_value=120,
            step=1,
            value=datos_guardados.get("Edad", 0),
            key="edad_input",
        )

    with col3:
        cuil = st.text_input(
            "CUIL",
            value=datos_guardados.get("CUIL", ""),
            key="cuil_input",
        )

    with col4:
        clave_abc = st.text_input(
            "Clave ABC",
            value=datos_guardados.get("Clave ABC", ""),
            key="clave_abc_input",
        )

    with col5:
        fecha_nacimiento_guardada = datos_guardados.get("Fecha de nacimiento", None)

        if fecha_nacimiento_guardada:
            fecha_nacimiento_default = pd.to_datetime(fecha_nacimiento_guardada).date()
        else:
            fecha_nacimiento_default = None

        fecha_nacimiento = st.date_input(
            "Fecha de nacimiento *",
            value=fecha_nacimiento_default,
            min_value=pd.to_datetime("1900-01-01").date(),
            max_value=pd.Timestamp.today().date(),
            format="DD/MM/YYYY",
            key="fecha_nacimiento_input",
        )

    with col6:
        fecha_cese_guardada = datos_guardados.get("Fecha de cese", None)

        if fecha_cese_guardada:
            fecha_cese_default = pd.to_datetime(fecha_cese_guardada).date()
        else:
            fecha_cese_default = None

        fecha_cese = st.date_input(
            "Fecha de cese *",
            value=fecha_cese_default,
            min_value=pd.to_datetime("1900-01-01").date(),
            max_value=pd.to_datetime("2100-12-31").date(),
            format="DD/MM/YYYY",
            key="fecha_cese_input",
        )

    st.markdown("---")
    st.subheader(
        "Pegado de Datos - aca podes copiar y pegar directamente de hoja de vida desde la plataforma abc"
    )

    col_vida, col_lic = st.columns(2)

    with col_vida:
        texto_vida = st.text_area("Hoja de Vida", height=250)

    with col_lic:
        texto_lic = st.text_area("Licencias", height=250)

    st.markdown("---")
    st.subheader(
        "Carga desde Excel - esta opcion es si tenes la hoja de vida y licencias desde un archivo excel"
    )

    archivo_excel = st.file_uploader("Subir archivo Excel", type=["xlsx", "ods"])

    archivo_certificacion = st.file_uploader(
        "Subir Certificacion Digital DGCyE",
        type=["pdf"],
        help="Certificacion Digital de Servicios emitida por DGCyE",
    )

    st.markdown("---")
    st.subheader("Servicios adicionales")

    tiene_pdf = st.radio(
        "Desea agregar servicios desde PDF - Municipio/Diegep?",
        ["No", "Si"],
        horizontal=True,
    )

    archivos_pdf = None

    if tiene_pdf == "Si":
        archivos_pdf = st.file_uploader(
            "Subir uno o mas PDF",
            type=["pdf"],
            accept_multiple_files=True,
        )

    st.markdown("---")
    st.subheader("Servicios con aportes en ANSES (Informativo)")

    for key, default in [
        ("tiene_anses", "No"),
        ("anses_comunes", False),
        ("anses_monotributo", False),
        ("anses_detalle", ""),
        ("servicios_anses", []),
        ("advertencia_anses", False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    st.session_state["tiene_anses"] = st.radio(
        "Posee servicios con aportes en ANSES?",
        ["No", "Si"],
        horizontal=True,
        index=0 if st.session_state["tiene_anses"] == "No" else 1,
        key="tiene_anses_radio",
    )

    servicios_anses = []

    if st.session_state["tiene_anses"] == "Si":
        st.warning(
            "Revisar simultaneidad con servicios ANSES al momento del analisis jubilatorio."
        )

        col_a, col_b = st.columns(2)

        with col_a:
            st.session_state["anses_comunes"] = st.checkbox(
                "Servicios comunes (relacion de dependencia)",
                value=st.session_state["anses_comunes"],
                key="anses_comunes_checkbox",
            )

        with col_b:
            st.session_state["anses_monotributo"] = st.checkbox(
                "Monotributo / Autonomo",
                value=st.session_state["anses_monotributo"],
                key="anses_monotributo_checkbox",
            )

        if st.session_state["anses_comunes"]:
            servicios_anses.append("Servicios comunes")

        if st.session_state["anses_monotributo"]:
            servicios_anses.append("Monotributo/Autonomo")

        st.session_state["anses_detalle"] = st.text_area(
            "Detalle adicional ANSES (opcional)",
            value=st.session_state["anses_detalle"],
            height=100,
            key="anses_detalle_textarea",
        )

        st.session_state["advertencia_anses"] = (
            "Revisar Servicios ANSES por rol de caja otorgante o simultaneidades"
        )
    else:
        st.session_state["anses_detalle"] = ""
        st.session_state["advertencia_anses"] = False

    st.markdown(
        """
<style>
div.stButton {
    display: flex;
    justify-content: center;
    margin-top: 30px;
    margin-bottom: 30px;
}

div.stButton > button {
    padding: 25px 70px;
    font-size: 32px;
    font-weight: bold;
    border-radius: 20px;
}
</style>
""",
        unsafe_allow_html=True,
    )

    procesar = st.button("PROCESAR DATOS", use_container_width=True)

    if procesar:
        if fecha_nacimiento is None or fecha_cese is None:
            st.error(
                "Debe cargar la Fecha de nacimiento y la Fecha de cese para procesar los datos."
            )
            st.stop()

        if fecha_cese <= fecha_nacimiento:
            st.error("La Fecha de cese debe ser posterior a la Fecha de nacimiento.")
            st.stop()

        st.session_state["datos_personales"] = {
            "Nombre y apellido": nombre,
            "Edad": edad,
            "CUIL": cuil,
            "Clave ABC": clave_abc,
            "Fecha de nacimiento": fecha_nacimiento,
            "Fecha de cese": fecha_cese,
        }

        st.session_state["servicios_anses"] = servicios_anses
        st.session_state["info_anses"] = {
            "tiene_anses": st.session_state.get("tiene_anses", "No"),
            "tipos_servicio": servicios_anses,
            "detalle": st.session_state.get("anses_detalle", ""),
            "advertencia_simultaneidad": st.session_state.get(
                "advertencia_anses", ""
            ),
        }

        st.success("Procesando datos...")

        hoja_vida = pd.DataFrame()
        hoja_licencias = pd.DataFrame()

        if archivo_certificacion:
            try:
                hoja_vida_cert = extraer_certificacion_dgcye(archivo_certificacion)
                hoja_vida = pd.concat(
                    [hoja_vida, hoja_vida_cert],
                    ignore_index=True,
                )

                st.success(
                    f"Certificacion DGCyE cargada: {len(hoja_vida_cert)} registros"
                )

            except Exception as e:
                st.error(f"Error procesando certificacion DGCyE: {e}")

        if archivo_excel:
            try:
                hoja_vida_excel = cargar_hoja_excel(
                    archivo_excel,
                    "Hoja1",
                    ENCABEZADOS_VIDA,
                )

                hoja_licencias_excel = cargar_hoja_excel(
                    archivo_excel,
                    "Hoja2",
                    ENCABEZADOS_LIC,
                )

                hoja_vida = pd.concat(
                    [hoja_vida, hoja_vida_excel],
                    ignore_index=True,
                )

                hoja_licencias = pd.concat(
                    [hoja_licencias, hoja_licencias_excel],
                    ignore_index=True,
                )

                st.success("Datos cargados desde Excel")

            except Exception as e:
                st.error(f"Error al leer el Excel: {e}")

        if texto_vida.strip():
            hoja_vida_texto = cargar_hoja_pegada(texto_vida, ENCABEZADOS_VIDA)
            hoja_vida = pd.concat([hoja_vida, hoja_vida_texto], ignore_index=True)

        if texto_lic.strip():
            hoja_lic_texto = cargar_hoja_pegada(texto_lic, ENCABEZADOS_LIC)
            hoja_licencias = pd.concat(
                [hoja_licencias, hoja_lic_texto],
                ignore_index=True,
            )

        if hoja_licencias.empty:
            hoja_licencias = pd.DataFrame(columns=ENCABEZADOS_LIC)

        if archivos_pdf:
            for pdf in archivos_pdf:
                try:
                    hoja_vida_pdf, hoja_licencias_pdf = extraer_datos_diegep(pdf)

                    hoja_vida = pd.concat(
                        [hoja_vida, hoja_vida_pdf],
                        ignore_index=True,
                    )

                    hoja_licencias = pd.concat(
                        [hoja_licencias, hoja_licencias_pdf],
                        ignore_index=True,
                    )

                except Exception as e:
                    st.error(f"Error al leer el PDF {pdf.name}: {e}")

        if not hoja_vida.empty:
    # =========================================================
    # COMPLETAR NIVEL + HORAS_CATEDRA + MODULOS
    # para Excel / Pegado / PDF
    # =========================================================
           
            hoja_vida = completar_carga_y_nivel_hoja_vida(hoja_vida)

            df_periodos = corte_con_licencias(
        hoja_vida,
        hoja_licencias,
        CODIGOS_VALIDOS,
        )
            df_consolidado = consolidar_periodos_continuos(df_periodos)

            # =========================================================
            # COMPLETAR NIVEL DESDE ESCUELA EN EL CONSOLIDADO
            # =========================================================
            if "ESCUELA" in df_consolidado.columns:
                if "NIVEL" not in df_consolidado.columns:
                    df_consolidado["NIVEL"] = ""

                mask_sin_nivel = df_consolidado["NIVEL"].astype(str).str.strip().eq("")
                df_consolidado.loc[mask_sin_nivel, "NIVEL"] = (
                    df_consolidado.loc[mask_sin_nivel, "ESCUELA"]
                    .apply(detectar_nivel_desde_escuela)
                )

            df_consolidado_filtrado = df_consolidado.copy()

            st.session_state["df_periodos"] = df_periodos
            st.session_state["df_consolidado"] = df_consolidado
            st.session_state["df_consolidado_filtrado"] = df_consolidado_filtrado
            st.session_state["hoja_licencias"] = hoja_licencias
            st.session_state["codigos_validos"] = CODIGOS_VALIDOS

            st.success("Procesamiento finalizado correctamente")
        else:
            st.warning("No se cargaron datos de hoja de vida para procesar.")


if __name__ == "__main__":
    main()