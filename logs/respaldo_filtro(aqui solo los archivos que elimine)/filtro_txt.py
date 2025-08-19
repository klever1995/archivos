import os
import sys
import re
from collections import defaultdict
from insertar import Logger

#Configuración inicial y conexión con OpenAI
os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from consumos.consulta_ia_openai import Consulta_ia_openai

# === Configuraciones ===

# Prioridades y categorías para clasificación de logs
PRIORIDAD = ['ERROR', 'WARN', 'INFO', 'DEBUG', 'UNKNOWN']

CATEGORIAS = {
    'start_send': re.compile(r'inicia envio', re.IGNORECASE),
    'end_send': re.compile(r'fin envio', re.IGNORECASE),
    'ftp_error': re.compile(r'FTP.*ERROR', re.IGNORECASE),
    'general_error': re.compile(r'ERROR', re.IGNORECASE),
}

# Métodos básicos para procesamiento de logs
def es_inicio_log(linea: str) -> bool:
    return bool(re.match(r"\d{2}:\d{2}:\d{2},\d{3}", linea))

#Método que extrae el componente/servicio del mensaje de log
def extraer_componente(linea: str) -> str:
    match = re.search(r'\b(?:ERROR|WARN|INFO|DEBUG)\s+\[([^\]]+)\]', linea)
    return match.group(1).strip() if match else "desconocido"

#Extrae el nombre del hilo de ejecución
def extraer_hilo(linea: str) -> str:
    match = re.search(r'\(([^)]+)\)', linea)
    return match.group(1).strip() if match else "main"

#Identifica el nivel del log
def extraer_nivel(linea: str) -> str:
    niveles = ['ERROR', 'WARN', 'INFO', 'DEBUG']
    for nivel in niveles:
        if f' {nivel} ' in linea:
            return nivel
    return 'UNKNOWN'

#Clasifica el mensaje según las categorías predefinidas
def categorizar_mensaje(texto: str) -> str:
    for categoria, patron in CATEGORIAS.items():
        if patron.search(texto):
            return categoria
    return 'otros'

#Recorta textos muy largos
def limitar_longitud(texto: str, max_len=30000):
    return texto if len(texto) <= max_len else texto[:max_len] + '...'

#Devuelve prioridad numérica para ordenar logs
def prioridad_nivel(nivel):
    return PRIORIDAD.index(nivel) if nivel in PRIORIDAD else len(PRIORIDAD)

#Contar bloques de log en archivo procesado
def contar_logs_procesados(file_path: str) -> int:
    """Cuenta la cantidad de bloques de log procesados"""
    with open(file_path, 'r', encoding='utf-8') as file:
        return sum(1 for line in file if line.startswith('# Bloque encontrado'))

# === Filtro 1 (Extracción de bloques de log)===
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
                    file_out.write(f"# Bloque encontrado en la línea {linea_inicio}\n")
                    file_out.write("".join(bloque) + "\n\n")
                bloque = [linea]
                en_bloque = True
                linea_inicio = numero_linea
            elif en_bloque:
                if linea.startswith(("   ", "\t", "at ")):
                    bloque.append(linea)
                else:
                    file_out.write(f"# Bloque encontrado en la línea {linea_inicio}\n")
                    file_out.write("".join(bloque) + "\n\n")
                    en_bloque = False
                    bloque = []

        if en_bloque:
            file_out.write(f"# Bloque encontrado en la línea {linea_inicio}\n")
            file_out.write("".join(bloque) + "\n\n")

# === Filtro 2 (Generación de reporte)===
def generar_reporte_logs(input_path: str, output_path: str) -> None:
    reporte = defaultdict(lambda: {
        'count': 0,
        'lineas': [],
        'nivel': '',
        'categoria': '',
        'componente': '',
        'hilo': '',
        'mensaje': ''
    })

    with open(input_path, 'r', encoding='utf-8') as file:
        lineas = file.readlines()

        bloque_actual = []
        for i, linea in enumerate(lineas, 1):
            match = re.match(r'# Bloque encontrado en la línea (\d+)', linea.strip())
            if match:
                if bloque_actual:
                    procesar_bloque(bloque_actual, match.group(1), reporte)
                bloque_actual = []
            elif not linea.strip().startswith("#"):
                bloque_actual.append(linea)

        if bloque_actual:
            procesar_bloque(bloque_actual, str(len(lineas)), reporte)

# Insertar en BD solo los logs agrupados del reporte final
    insertar_logs_a_bd(reporte)

    with open(output_path, 'w', encoding='utf-8') as file:
        for (_, _, _), datos in sorted(
            reporte.items(), 
            key=lambda x: (prioridad_nivel(x[1]['nivel']), -x[1]['count'])
        ):
            file.write(f"=== {datos['mensaje']} ===\n")
            file.write(f"Nivel: {datos['nivel']} | Categoría: {datos['categoria']}\n")
            file.write(f"Componente: {datos['componente']} | Hilo: {datos['hilo']}\n")
            file.write(f"Total: {datos['count']} ocurrencias\n")
            file.write("\nLíneas:\n- " + ", ".join(datos['lineas']) + "\n\n")

#Guardar los logs procesados y el proceso en la base de datos
def insertar_logs_a_bd(reporte):
    total_insertados = 0
    consulta = Consulta_ia_openai()
    
    for (nivel, categoria, _), datos in reporte.items():
        try:
            respuesta_openai = None
            
            if nivel == 'ERROR':
                if not Logger.existe_error_en_bd(datos['mensaje_normalizado']):
                    respuesta_openai = consulta.interpretar_logs(datos['mensaje_normalizado'])
                    print(f"🔍 Solución OpenAI para error: {respuesta_openai[:100]}...")
                    
                    Logger.insertar_log(
                        idEmpresa=1,
                        operador=0,
                        mensaje=limitar_longitud(datos['mensaje_normalizado']),
                        nivel=nivel,
                        componente=datos['componente'],
                        hilo=datos['hilo'],
                        categoria=categoria,
                        estado='ACTIVO',
                        lineas=datos['lineas'],
                        ocurrencias=datos['count'],
                        respuestaOpenai=respuesta_openai
                    )
                    total_insertados += 1
                else:
                    print(f"⚠️ Error duplicado: {datos['mensaje_normalizado'][:100]}...")
            else:
                Logger.insertar_log(
                    idEmpresa=1,
                    operador=0,
                    mensaje=limitar_longitud(datos['mensaje_normalizado']),
                    nivel=nivel,
                    componente=datos['componente'],
                    hilo=datos['hilo'],
                    categoria=categoria,
                    estado='ACTIVO',
                    lineas=datos['lineas'],
                    ocurrencias=datos['count'],
                    respuestaOpenai=None
                )
                total_insertados += 1
                
        except Exception as e:
            print(f"❌ Error insertando log: {str(e)}")
    
    return total_insertados

#Analizar un bloque de log y actualizar el reporte
def procesar_bloque(bloque_actual, linea_inicio, reporte):
    mensaje_completo = "".join(bloque_actual).strip()
    nivel = extraer_nivel(mensaje_completo)
    categoria = categorizar_mensaje(mensaje_completo)
    componente = extraer_componente(mensaje_completo)
    hilo = extraer_hilo(mensaje_completo)

    mensaje_normalizado = re.sub(r'^\d{2}:\d{2}:\d{2},\d{3}\s*', '', mensaje_completo).strip()

    if "FTP MKDIR" in mensaje_normalizado:
        pass

    clave = (nivel, categoria, mensaje_normalizado)
    reporte[clave].update({
        'count': reporte[clave]['count'] + 1,
        'lineas': reporte[clave]['lineas'] + [linea_inicio],
        'nivel': nivel,
        'categoria': categoria,
        'componente': componente,
        'hilo': hilo,
        'mensaje': mensaje_completo,
        'mensaje_normalizado': mensaje_normalizado 
    })

# ----------------------------
# Ejecución (Flujo principal)
# ----------------------------
if __name__ == "__main__":

    from metodos_loprocesos import ProcesosLogger
    
    # Registrar inicio del proceso
    id_proceso = ProcesosLogger.iniciar_proceso(
        idEmpresa=1, # 1 el ID de la empresa real
        operador=0  # O el ID del operador real
    )

    if id_proceso == -1:
        print("❌ No se pudo iniciar el proceso de logs")
        exit(1)

    input_original = "C:/Users/klever.robalino/Desktop/Proyecto-Mutualista/backend-asistente/agentes/logs/logs_files/prueba.txt"
    output_filtro1 = "C:/Users/klever.robalino/Desktop/Proyecto-Mutualista/backend-asistente/agentes/logs/logs_files/filtro1_bloques.txt"
    output_filtro2 = "C:/Users/klever.robalino/Desktop/Proyecto-Mutualista/backend-asistente/agentes/logs/logs_files/filtro2_reporte.txt"

    try:
        # Ejecutar el procesamiento
        extraer_bloques_log(input_original, output_filtro1)
        generar_reporte_logs(output_filtro1, output_filtro2)
        
        # Contar logs procesados (necesitarás implementar esto)
        total_logs = contar_logs_procesados(output_filtro1)
        
        print("✅ Proceso completo:")
        print(f"- Bloques de log extraídos en: {output_filtro1}")
        print(f"- Reporte agrupado generado en: {output_filtro2}")
        
    except Exception as e:
        print(f"❌ Error durante el procesamiento: {str(e)}")
        total_logs = 0
    finally:
        # Siempre registrar el final del proceso
        ProcesosLogger.finalizar_proceso(
            idAuditoria=id_proceso,
            totalLogs=total_logs
        )
