# =========================================================
# ENCABEZADOS ESPERADOS
# =========================================================

ENCABEZADOS_VIDA = [
    "SECUENCIA",
    "ESCUELA",
    "CARGO",
    "CARGA HORARIA",
    "DESDE",
    "HASTA",
    "SIT. REV",
    "TURNO",
    "REG. ESTATURARIO",
]
ENCABEZADOS_LIC = [
    "SECUENCIA",
    "ESTABLECIMIENTO",
    "CARGA HORARIA",
    "DESDE",
    "HASTA",
    "ENCUADRE",
]

CODIGOS_VALIDOS = [
    "22",
    "1257",
    "114O1",
    "114O4",
    "114D111",
    "115D1",
    "115C1",
    #"115B1",
    "1252",
    "CAUSAS PARTICULARES",
    "114F1",
]
niveles_dict = {
    "Inicial": [
        "JI",
        "JS",
        "JU",
        "JM",
        "JV",
    ],
    "Primaria": ["PP", "EP", "PA", "DA", "DC", "DE"],
    "Especial": ["EE", "EL", "CFI", "ET", "ESPECIAL"],
    "Secundaria": ["MM", "MS", "ES", "ESB", "MT", "BS", "MA", "MC", "AS"],
    "Adulto": ["DM", "CENS", "DF", "DS", "MF", "ADULTOS", "ADULTO", "CFP", "CFL"],
    "Superior": ["IS", "AA", "AT", "AF", "AV", "AC", "AD", "AM", "AP", "FC"],
}

niveles_dictpdf = {
    "Inicial": [
        "JARDIN",
        "INICIAL",
        "JARDíN",
        "Inicial",
        "jardin",
        "maternal",
        "inicial",
    ],
    "Primaria": ["PRIMARIA", "primaria", "Primaria"],
    "Especial": ["ESPECIAL", "especial", "Especial"],
    "Secundaria": [
        "SECUNDARIA",
        "MEDIA",
        "POLIMODAL",
        "Secundaria",
        "polimodal",
        "media",
    ],
    "Adulto": ["ADULTOS", "ADULTO", "Adulto", "adulto"],
    "Superior": [
        "SUPERIOR",
        "TERCIARIO",
        "superior",
        "terciario",
        "Superior",
        "Terciario",
    ]
}



