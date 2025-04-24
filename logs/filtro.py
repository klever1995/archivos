import re
from collections import defaultdict

# === Configuraciones ===
PRIORIDAD = ['ERROR', 'WARN', 'INFO', 'DEBUG', 'UNKNOWN']

CATEGORIAS = {
    'start_send': re.compile(r'inicia envio', re.IGNORECASE),
    'end_send': re.compile(r'fin envio', re.IGNORECASE),
    'ftp_error': re.compile(r'FTP.*ERROR', re.IGNORECASE),
    'general_error': re.compile(r'ERROR', re.IGNORECASE),
}

def es_inicio_log(linea: str) -> bool:
    return bool(re.match(r"\d{2}:\d{2}:\d{2},\d{3}", linea))

def extraer_nivel(linea: str) -> str:
    niveles = ['ERROR', 'WARN', 'INFO', 'DEBUG']
    for nivel in niveles:
        if f' {nivel} ' in linea:
            return nivel
    return 'UNKNOWN'

def categorizar_mensaje(texto: str) -> str:
    for categoria, patron in CATEGORIAS.items():
        if patron.search(texto):
            return categoria
    return 'otros'

def limitar_longitud(texto: str, max_len=30000):
    return texto if len(texto) <= max_len else texto[:max_len] + '...'

def prioridad_nivel(nivel):
    return PRIORIDAD.index(nivel) if nivel in PRIORIDAD else len(PRIORIDAD)

# === Filtro 1 ===
def extraer_bloques_log(input_path: str, output_path: str) -> None:
    with open(input_path, 'r', encoding='utf-8') as file_in, \
         open(output_path, 'w', encoding='utf-8') as file_out:
        
        bloque = []
        en_bloque = False
        numero_linea = 0
        linea_inicio = None

        for linea in file_in:
            numero_linea += 1
            if es_inicio_log(linea):
                if en_bloque:
                    # Al finalizar un bloque, lo escribimos completo
                    file_out.write(f"# Bloque encontrado en la línea {linea_inicio}\n")
                    file_out.write("".join(bloque) + "\n\n")
                # Comienza un nuevo bloque
                bloque = [linea]
                en_bloque = True
                linea_inicio = numero_linea
            elif en_bloque:
                # Continuar agregando al bloque si es parte del stack trace o el error
                if linea.startswith(("   ", "\t", "at ")):  # Indica un stack trace
                    bloque.append(linea)
                else:
                    # Si encontramos una línea que no es parte del stack trace, terminamos el bloque
                    file_out.write(f"# Bloque encontrado en la línea {linea_inicio}\n")
                    file_out.write("".join(bloque) + "\n\n")
                    en_bloque = False
                    bloque = []

        # Si quedó un bloque incompleto al final, lo escribimos
        if en_bloque:
            file_out.write(f"# Bloque encontrado en la línea {linea_inicio}\n")
            file_out.write("".join(bloque) + "\n\n")

# === Filtro 2 ===
def generar_reporte_logs(input_path: str, output_path: str) -> None:
    reporte = defaultdict(lambda: {
        'count': 0,
        'lineas': [],
        'nivel': '',
        'categoria': '',
        'mensaje': ''
    })

    with open(input_path, 'r', encoding='utf-8') as file:
        lineas = file.readlines()

        for i, linea in enumerate(lineas, 1):
            match = re.match(r'# Bloque encontrado en la línea (\d+)', linea.strip())
            if match:
                numero_linea = match.group(1)

                if i + 1 < len(lineas):
                    log_line = lineas[i].strip()

                    # Extraer info
                    timestamp_match = re.match(r'^(\d{2}:\d{2}:\d{2},\d{3})\s+(.*?)\s+(.*?)\s+(.*)', log_line)
                    if timestamp_match:
                        _, nivel, _, mensaje = timestamp_match.groups()
                        nivel = nivel.upper().strip()
                    else:
                        nivel = extraer_nivel(log_line)
                        mensaje = re.sub(r'^\d{2}:\d{2}:\d{2},\d{3}\s*', '', log_line)

                    categoria = categorizar_mensaje(mensaje)

                    clave = (nivel, categoria, mensaje)
                    reporte[clave]['count'] += 1
                    reporte[clave]['lineas'].append(numero_linea)
                    reporte[clave]['nivel'] = nivel
                    reporte[clave]['categoria'] = categoria
                    reporte[clave]['mensaje'] = mensaje

    # Guardar reporte ordenado por nivel y frecuencia
    with open(output_path, 'w', encoding='utf-8') as file:
        for (_, _, mensaje), datos in sorted(reporte.items(), key=lambda x: (prioridad_nivel(x[1]['nivel']), -x[1]['count'])):
            file.write(f"=== {limitar_longitud(datos['mensaje'])} ===\n")
            file.write(f"Nivel: {datos['nivel']} | Categoría: {datos['categoria']}\n")
            file.write(f"Total: {datos['count']} ocurrencias\n")
            file.write("\nLíneas:\n- " + ", ".join(datos['lineas']) + "\n\n")




# ----------------------------
# Ejecución (Flujo principal)
# ----------------------------
if __name__ == "__main__":
    # 📁 Configuración de rutas de archivo (ajústalas según tu estructura)
    input_original = "C:/Users/klever.robalino/Desktop/Proyecto-Mutualista/backend-asistente/agentes/logs/logs_files/prueba.txt"
    output_filtro1 = "C:/Users/klever.robalino/Desktop/Proyecto-Mutualista/backend-asistente/agentes/logs/logs_files/filtro1_bloques.txt"
    output_filtro2 = "C:/Users/klever.robalino/Desktop/Proyecto-Mutualista/backend-asistente/agentes/logs/logs_files/filtro2_reporte.txt"

    # 🔍 Paso 1: Extraer bloques (no solo errores ahora)
    extraer_bloques_log(input_original, output_filtro1)

    # 📊 Paso 2: Generar reporte agrupado por nivel, categoría, mensaje
    generar_reporte_logs(output_filtro1, output_filtro2)

    # ✅ Mensaje final
    print("✅ Proceso completo:")
    print(f"- Bloques de log extraídos en: {output_filtro1}")
    print(f"- Reporte agrupado generado en: {output_filtro2}")
