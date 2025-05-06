----------intento del filtro que se creo con la linea donde se quedo--------------archivo filtro_estado.py
import os
import sys
import re
from collections import defaultdict
from insertar import Logger
from state_manager import LogStateManager


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
    with open(file_path, 'r', encoding='utf-8') as file:
        return sum(1 for line in file if line.startswith('# Bloque encontrado'))

# === Filtro 1 (Extracción de bloques de log)===
def extraer_bloques_log(input_path: str, state_manager: LogStateManager = None) -> list:
    bloques = []
    start_offset = 0
    current_inode = os.stat(input_path).st_ino if state_manager else None
    
    if state_manager:
        start_offset = state_manager.get_last_position(input_path)
        print(f"⚡ Continuando desde byte offset: {start_offset}")

    with open(input_path, 'r', encoding='utf-8') as file_in:
        if start_offset > 0:
            file_in.seek(start_offset)
        
        bloque_actual = []
        en_bloque = False
        linea_inicio = None
        total_lineas = 0  # Contador local de líneas procesadas

        for linea in file_in:
            total_lineas += 1
            if es_inicio_log(linea):
                if en_bloque:  
                    bloques.append({
                        'linea_inicio': linea_inicio,
                        'contenido': "".join(bloque_actual)
                    })
                bloque_actual = [linea]
                en_bloque = True
                linea_inicio = total_lineas + start_offset  # Ajuste por offset
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

        # Guardar estado si se usa el manager
        if state_manager:
            state_manager.save_state(
                file_path=input_path,
                inode=current_inode,
                offset=file_in.tell(),
                line_number=total_lineas + start_offset
            )
    
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
    from state_manager import LogStateManager  # Importar el manager

    id_proceso = ProcesosLogger.iniciar_proceso(
        idEmpresa=1,
        operador=0
    )

    if id_proceso == -1:
        print("❌ No se pudo iniciar el proceso de logs")
        exit(1)

    input_original = "C:/Users/klever.robalino/Desktop/Proyecto-Mutualista/backend-asistente/agentes/logs/logs_files/prueba2.txt"
    state_manager = LogStateManager()  # Instancia del manager
    
    try:
        bloques = extraer_bloques_log(input_original, state_manager)  # Pasa el manager
        reporte = generar_reporte_logs(bloques)
        total_logs = len(bloques)
        
        print("✅ Proceso completo:")
        print(f"- Bloques nuevos procesados: {total_logs}")
        print(f"- Offset guardado: {state_manager.get_last_position(input_original)}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        total_logs = 0
    finally:
        ProcesosLogger.finalizar_proceso(
            idAuditoria=id_proceso,
            totalLogs=total_logs
        )
