import os
import sys
import re
from collections import defaultdict
from insertar import Logger
from state_manager import LogStateManager
from metodos_loprocesos import ProcesosLogger



#Configuración inicial y conexión con OpenAI
os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from consumos.consulta_ia_openai import Consulta_ia_openai
from modelo.loProcesos import LoProcesos
from config import db, init_app
from flask import Flask
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
def extraer_bloques_log(input_path: str, id_proceso: int, state_manager: LogStateManager = None) -> list:
    """
    Nueva versión que trabaja por rangos de bytes y se sincroniza con lo_procesos.
    """
    bloques = []
    proceso = db.session.get(LoProcesos, id_proceso)
    
    if not proceso:
        raise ValueError(f"Proceso {id_proceso} no encontrado en BD")

    # Obtener último byte procesado (de BD o estado local)
    byte_inicio = proceso.ultimo_byte_procesado
    if state_manager:
        byte_inicio = max(byte_inicio, state_manager.get_last_byte(input_path))

    # Calcular nuevo chunk (ej: 1MB o hasta EOF)
    file_size = os.path.getsize(input_path)
    byte_fin = min(byte_inicio + (1024 * 1024), file_size)  # 1MB chunks

    # Reservar el rango en BD
    proceso.ultimo_byte_reservado = byte_fin
    db.session.commit()

    print(f"⚡ Procesando bytes {byte_inicio}-{byte_fin} de {file_size}")

    with open(input_path, 'rb') as file:
        file.seek(byte_inicio)
        data = file.read(byte_fin - byte_inicio).decode('utf-8', errors='ignore')
        
        # Procesamiento de bloques (similar al original pero con ajuste de offsets)
        bloque_actual = []
        en_bloque = False
        
        for linea in data.splitlines(keepends=True):
            if es_inicio_log(linea):
                if en_bloque and bloque_actual:
                    bloques.append({
                        'contenido': ''.join(bloque_actual),
                        'byte_inicio': byte_inicio  # Guardamos posición inicial
                    })
                bloque_actual = [linea]
                en_bloque = True
            elif en_bloque:
                bloque_actual.append(linea)
            
            byte_inicio += len(linea.encode('utf-8'))  # Actualizar posición en bytes

        if en_bloque and bloque_actual:
            bloques.append({
                'contenido': ''.join(bloque_actual),
                'byte_inicio': byte_inicio - sum(len(l.encode('utf-8')) for l in bloque_actual)
            })

    # Actualizar estado
    if state_manager:
        state_manager.save_state(input_path, byte_fin)
    
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
# En filtro_asincrono.py (modifica la parte principal)
if __name__ == "__main__":
    # Suprime mensajes de certificado (opcional)
    import logging
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Crea la aplicación Flask
    app = Flask(__name__)
    
    # Configura la aplicación
    init_app(app)
    
    # Usa el contexto de aplicación
    with app.app_context():
        try:
            # Tu código existente aquí...
            id_proceso = ProcesosLogger.iniciar_proceso(
                idEmpresa=1,
                operador=0,
                ruta_archivo="logs_files/prueb.txt",  # Asegúrate que esta ruta es correcta
                byte_inicio=0
            )
            
            if id_proceso == -1:
                raise RuntimeError("No se pudo iniciar el proceso")

            state_manager = LogStateManager()
            bloques = extraer_bloques_log("logs_files/prueb.txt", id_proceso, state_manager)
            reporte = generar_reporte_logs(bloques)
            
            ProcesosLogger.finalizar_proceso(
                idAuditoria=id_proceso,
                totalLogs=len(bloques),
                byte_fin=state_manager.get_last_byte("logs_files/prueb.txt")
            )
            
            print(f"✅ Procesados {len(bloques)} bloques")

        except Exception as e:
            print(f"❌ Error crítico: {str(e)}")
            db.session.rollback()
            sys.exit(1)
