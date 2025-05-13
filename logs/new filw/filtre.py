-------------este es el filtreo---------------- archivo filtro asincrionico.py
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
def extraer_bloques_log(chunk: str, offset_linea: int = 0) -> list:
    """Procesa un chunk de texto y devuelve bloques de log con offset correcto"""
    bloques = []
    lineas = chunk.splitlines(keepends=True)  # Mantener saltos de línea
    bloque_actual = []
    en_bloque = False
    linea_inicio = None

    for i, linea in enumerate(lineas, start=offset_linea):
        if es_inicio_log(linea):
            if en_bloque:  
                bloques.append({
                    'linea_inicio': linea_inicio,
                    'contenido': "".join(bloque_actual)
                })
            bloque_actual = [linea]
            en_bloque = True
            linea_inicio = i
        elif en_bloque:
            if linea.startswith(("   ", "\t", "at ")):
                bloque_actual.append(linea)
            else:
                bloques.append({
                    'linea_inicio': linea_inicio,
                    'contenido': "".join(bloque_actual)
                })
                en_bloque = False
                bloque_actual = []

    if en_bloque and bloque_actual:
        bloques.append({
            'linea_inicio': linea_inicio,
            'contenido': "".join(bloque_actual)
        })
    
    return bloques

# === Filtro 2 (Generación de reporte)===
def generar_reporte_logs(bloques: list) -> dict:
    reporte = defaultdict(lambda: {
        'count': 0,
        'lineas': [],
        'nivel': '',
        'categoria': '',
        'componente': '',
        'hilo': '',
        'mensaje': '',
        'mensaje_normalizado': ''
    })

    
    for bloque in bloques:
        
        lineas_bloque = bloque['contenido'].split('\n')
        procesar_bloque(lineas_bloque, str(bloque['linea_inicio']), reporte)

    insertar_logs_a_bd(reporte)
    return reporte  

#Guardar los logs procesados y el proceso en la base de datos
def insertar_logs_a_bd(reporte):
    total_insertados = 0
    consulta = Consulta_ia_openai()
    
    for (nivel, categoria, _), datos in reporte.items():
        try:
            # Verificar si el log ya existe (para TODOS los niveles)
            if not Logger.existe_error_en_bd(datos['mensaje_normalizado'], nivel):
                respuesta_openai = None
                
                # Solo consultar OpenAI para errores
                if nivel == 'ERROR':
                    mensaje_para_ia = limitar_longitud(datos['mensaje_normalizado'], max_len=2000)
                    respuesta_openai = consulta.interpretar_logs(mensaje_para_ia)
                    print(f"🔍 Solución OpenAI para error: {respuesta_openai[:100]}...")
                
                # Insertar el log (todos los niveles)
                Logger.insertar_log(
                    idEmpresa=1,
                    operador=0,
                    mensaje=datos['mensaje_normalizado'],
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
                print(f"✅ Log insertado: {nivel} - {datos['mensaje_normalizado'][:100]}...")
            else:
                print(f"⚠️ Log duplicado (no insertado): {nivel} - {datos['mensaje_normalizado'][:100]}...")
                
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
    
    # Aplica el mismo truncamiento que usarás después
    mensaje_normalizado = limitar_longitud(mensaje_normalizado, 2000)  # <--- Clave consistente

    if "FTP MKDIR" in mensaje_normalizado:
        mensaje_normalizado = re.sub(r'FTP MKDIR.*?ERROR', 'FTP MKDIR [DIRECTORIO] ERROR', mensaje_normalizado)

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
    import os
    
    ARCHIVO_LOG = "C:/Users/Klever/Desktop/Proyecto Mutualista/backend-asistente/agentes/logs/logs_files/prueba21.txt"
    
    # 1. Validar que el archivo exista
    if not os.path.exists(ARCHIVO_LOG):
        print(f"❌ Archivo no encontrado: {ARCHIVO_LOG}")
        exit(1)

    # 2. Reservar bloque de bytes
    bloque = ProcesosLogger.reservar_bloque(
        ruta_archivo=ARCHIVO_LOG,
        idEmpresa=1,
        operador=0,
        bloque_size=1048576  # 1MB
    )
    
    if not bloque:
        print("❌ No hay bytes nuevos por procesar o error al reservar bloque.")
        exit(1)

    # ¡Nuevo mensaje de inicio! Muestra el rango ANTES de procesar
    print(f"🔍 Iniciando procesamiento (bytes {bloque['byte_inicio']}-{bloque['byte_fin']})...")

    try:
        # 3. Procesar SOLO el chunk reservado con manejo de bordes
        with open(ARCHIVO_LOG, 'rb') as f:
            f.seek(bloque['byte_inicio'])
            chunk = f.read(bloque['byte_fin'] - bloque['byte_inicio'] + 1).decode('utf-8', errors='ignore')
        
        # 4. Extraer bloques de log manteniendo el offset correcto
        bloques_procesados = extraer_bloques_log(chunk, offset_linea=0)
        
        # 5. Generar reporte e insertar en BD
        reporte = generar_reporte_logs(bloques_procesados)
        total_logs = sum(datos['count'] for datos in reporte.values())
        
        # Mensaje final (se mantiene igual)
        print(f"✅ Procesados {total_logs} logs (bytes {bloque['byte_inicio']}-{bloque['byte_fin']})")
        
    except Exception as e:
        print(f"❌ Error procesando bloque: {str(e)}")
        ProcesosLogger.marcar_error(bloque['idAuditoria'])
        exit(1)
        
    finally:
        # 6. Actualizar estado (incluso si falla)
        ProcesosLogger.finalizar_proceso(
            idAuditoria=bloque['idAuditoria'],
            totalLogs=total_logs if 'total_logs' in locals() else 0,
            ultimo_byte=bloque['byte_fin']
        )
