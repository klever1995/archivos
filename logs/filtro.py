import re
from collections import defaultdict

# ----------------------------
# Filtro 1: Extracción de bloques de error
# ----------------------------
def es_inicio_error(linea: str) -> bool:
    return ("ERROR" in linea) and bool(re.match(r"\d{2}:\d{2}:\d{2},\d{3}", linea))

def extraer_bloques_error(input_path: str, output_path: str) -> None:
    """Filtro 1: Extrae bloques de error y los guarda en un archivo temporal."""
    with open(input_path, 'r', encoding='utf-8') as file_in, \
         open(output_path, 'w', encoding='utf-8') as file_out:
        
        bloque = []
        en_error = False

        for linea in file_in:
            if es_inicio_error(linea):
                if en_error:  # Guardar bloque anterior
                    file_out.write("".join(bloque) + "\n\n")
                bloque = [linea]
                en_error = True
            elif en_error:
                if linea.startswith(("   ", "\t", "at ")):  # Stack trace
                    bloque.append(linea)
                else:  # Fin del bloque
                    file_out.write("".join(bloque) + "\n\n")
                    en_error = False

# ----------------------------
# Filtro 2: Conteo y reporte de errores
# ----------------------------
def generar_reporte_errores(input_path: str, output_path: str) -> None:
    """Filtro 2 corregido: Extrae timestamps y tipos de error exactos."""
    reporte = defaultdict(lambda: {'count': 0, 'timestamps': []})
    
    with open(input_path, 'r', encoding='utf-8') as file:
        contenido = file.read()
        # Separar bloques más robustamente (considera diferentes formatos)
        bloques = [b.strip() for b in contenido.split('\n\n') if b.strip()]
        
    for bloque in bloques:
        # Extrae timestamp (ahora con formato más flexible)
        timestamp_match = re.search(
            r'^(\d{2}:\d{2}:\d{2},\d{3})',  # Ej: 00:00:57,569
            bloque
        )
        timestamp = timestamp_match.group(1) if timestamp_match else "NO_TIMESTAMP"
        
        # Extrae el tipo de error (toda la línea inicial sin timestamp)
        lineas = bloque.split('\n')
        primera_linea = lineas[0]
        
        # Elimina solo el timestamp si existe
        tipo_error = re.sub(r'^\d{2}:\d{2}:\d{2},\d{3}\s*', '', primera_linea)
        tipo_error = tipo_error.strip()
        
        if tipo_error:  # Solo procesa si encontró un error válido
            reporte[tipo_error]['count'] += 1
            reporte[tipo_error]['timestamps'].append(timestamp)
    
    # Guarda el reporte mejorado
    with open(output_path, 'w', encoding='utf-8') as file:
        for tipo, datos in sorted(reporte.items(), key=lambda x: -x[1]['count']):
            file.write(f"=== {tipo} ===\n")
            file.write(f"Total: {datos['count']} ocurrencias\n")
            
            # Muestra solo los primeros 10 timestamps para evitar saturación
            timestamps = datos['timestamps'][:10] if len(datos['timestamps']) > 10 else datos['timestamps']
            file.write("Horarios:\n- " + "\n- ".join(timestamps))
            
            if len(datos['timestamps']) > 10:
                file.write(f"\n... y {len(datos['timestamps']) - 10} más")
            file.write("\n\n")

# ----------------------------
# Ejecución (Flujo principal)
# ----------------------------
if __name__ == "__main__":
    # Configuración de archivos (ajusta rutas según necesites)
    input_original = "C:/Users/Klever/Downloads/server/server.log"
    output_filtro1 = "filtro1_bloques.txt"
    output_filtro2 = "filtro2_reporte.txt"
    
    # Ejecutar filtros en secuencia
    extraer_bloques_error(input_original, output_filtro1)
    generar_reporte_errores(output_filtro1, output_filtro2)
    
    print("✅ Proceso completo:")
    print(f"- Bloques de error extraídos en: {output_filtro1}")
    print(f"- Reporte de errores generado en: {output_filtro2}")