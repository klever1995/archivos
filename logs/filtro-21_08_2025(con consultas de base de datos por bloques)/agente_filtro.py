import os
import sys
import socket
import logging
from collections import defaultdict
import time
import signal
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import init_app, db
from flask import Flask
from modelo.loAccesosremotos import loAccesosremotos
from modelo.asEmpresa import asEmpresa
from modelo.loServidores import loServidores
from analizar_log import Logger
from gestor_procesos import ProcesosLogger
from logs_remotos import insertar_logs_remotos

# Configuración Flask y logging
app = Flask(__name__)
init_app(app)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Control de ejecución global
ejecucion_activa = threading.Event()
ejecucion_activa.set()  

#Método de terminación
def handler_shutdown(signum, frame):
    ejecucion_activa.clear() 
    logger.info("Recibida señal de terminación, finalizando...")

#Método de procesamiento continuo
def procesar_archivo_remoto_continuo(ruta_archivo: str, id_servidor: int, timeout_minutos: int = 60) -> bool:
    global ejecucion_activa
    start_total = time.perf_counter()
    timeout_segundos = timeout_minutos * 60
    ultimo_tamaño = 0
    iteraciones_sin_cambios = 0
    
    with app.app_context():
        logger.info(f"🔄 Iniciando procesamiento continuo: {ruta_archivo}")
        
        while ejecucion_activa.is_set(): 
            # Timeout de seguridad
            if time.perf_counter() - start_total > timeout_segundos:
                logger.info("⏰ Timeout alcanzado, finalizando procesamiento")
                break
                
            try:
                # Verificar existencia del archivo
                if not os.path.exists(ruta_archivo):
                    logger.warning(f"📁 Archivo no encontrado: {ruta_archivo}. Reintentando en 30s...")
   
                    if not ejecucion_activa.wait(30):
                        break
                    continue

                tamaño_actual = os.path.getsize(ruta_archivo)
                # Detección de rotación de archivos
                if tamaño_actual < ultimo_tamaño:
                    logger.info("🔄 Archivo rotado detectado, reiniciando procesamiento desde inicio")
                    ProcesosLogger.reiniciar_procesamiento(ruta_archivo, id_servidor)
                    ultimo_tamaño = 0
                
                # Reservar bloque de procesamiento
                bloque = ProcesosLogger.reservar_bloque(
                    ruta_archivo=ruta_archivo,
                    idEmpresa=1,
                    operador=0,
                    idServidor=id_servidor,
                    bloque_size=5048576 
                )

                if not bloque:

                    iteraciones_sin_cambios += 1
                    if iteraciones_sin_cambios % 10 == 0:
                        logger.info("⏳ Esperando nuevos datos...")

                    if not ejecucion_activa.wait(5):
                        break
                    continue
                # Procesar bloque obtenido
                iteraciones_sin_cambios = 0
                id_auditoria = bloque['idAuditoria']
                byte_inicio = bloque['byte_inicio']
                byte_fin = bloque['byte_fin']
                contenido = leer_chunk_local_para_pruebas(ruta_archivo, byte_inicio, byte_fin)
                bloques = extraer_bloques_log(contenido, byte_inicio, ruta_archivo)
                reporte = generar_reporte_basico(bloques)
                total = insertar_logs_remotos(reporte, id_servidor, id_auditoria)
                # Finalizar proceso y actualizar base
                ProcesosLogger.finalizar_proceso(
                    idAuditoria=id_auditoria,
                    totalLogs=total,
                    ultimo_byte=byte_fin
                )
                
                logger.info(f"✅ Procesado bloque: {total} logs (Bytes: {byte_inicio}-{byte_fin})")
                ultimo_tamaño = byte_fin

                if not ejecucion_activa.wait(1):
                    break
                
            except Exception as e:
                logger.error(f"Error en iteración: {str(e)}", exc_info=True)

                if not ejecucion_activa.wait(10):
                    break
    
    logger.info("🏁 Procesamiento continuo finalizado")
    return True

#Método que lee fragmentos del archivo
def leer_chunk_local_para_pruebas(ruta: str, byte_inicio: int, byte_fin: int) -> str:
    try:
        with open(ruta, 'rb') as f:
            f.seek(byte_inicio)
            return f.read(byte_fin - byte_inicio + 1).decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Error leyendo chunk local: {str(e)}")
        raise

#Método que extrae bloques del chunk leído
def extraer_bloques_log(chunk: str, byte_inicio: int = 0, ruta_archivo: str = None) -> list:
    import time 
    start_total = time.perf_counter()
    
    bloques = []
    bloque_actual = []
    linea_inicio = None

    lineas_previas = 0
    if byte_inicio > 0 and ruta_archivo:
        try:
            start = time.perf_counter()
            with open(ruta_archivo, 'rb') as f:
                f.seek(0)
                lineas_previas = f.read(byte_inicio).decode('utf-8', errors='ignore').count('\n')
        except Exception as e:
            logger.error(f"Error calculando líneas previas: {str(e)}")
            lineas_previas = 0

    start = time.perf_counter()
    lineas = chunk.splitlines(keepends=True)

    start_loop = time.perf_counter()
    lineas_procesadas = 0
    bloques_descartados = 0
    
    for i, linea in enumerate(lineas, start=lineas_previas + 1):
        lineas_procesadas += 1
        if Logger.es_inicio_log(linea):
            nivel = Logger.extraer_nivel(linea)
            if nivel in ['INFO', 'DEBUG']:
                bloques_descartados += 1
                bloque_actual = []
                continue

            if bloque_actual:
                bloques.append({
                    'linea_inicio': linea_inicio,
                    'contenido': ''.join(bloque_actual)
                })
            bloque_actual = [linea]
            linea_inicio = i
        elif bloque_actual:
            if linea.startswith(("   ", "\t", "at ")):
                bloque_actual.append(linea)
            else:
                if bloque_actual:
                    bloques.append({
                        'linea_inicio': linea_inicio,
                        'contenido': ''.join(bloque_actual)
                    })
                bloque_actual = []

    if bloque_actual and Logger.extraer_nivel(bloque_actual[0]) not in ['INFO', 'DEBUG']:
        bloques.append({
            'linea_inicio': linea_inicio,
            'contenido': ''.join(bloque_actual)
        })
        
    return bloques

#Método que genera el reporte de los bloques de logs
def generar_reporte_basico(bloques: list) -> dict:
    import time  
    start_total = time.perf_counter()
    
    reporte = defaultdict(lambda: {
        'count': 0,
        'mensaje_normalizado': '',
        'nivel': '',
        'categoria': '',
        'componente': '',
        'hilo': '',
        'lineas': []
    })

    bloques_procesados = 0
    start_procesamiento = time.perf_counter()

    for bloque in bloques:
        bloques_procesados += 1
        linea_inicio = bloque['linea_inicio']

        start_bloque = time.perf_counter()
        Logger.procesar_bloque(
            bloque_actual=bloque['contenido'].splitlines(keepends=True),
            linea_inicio=str(linea_inicio),
            reporte=reporte
        )
        tiempo_bloque = time.perf_counter() - start_bloque

        if bloques_procesados % 100 == 0:
            logger.info(f"⏱️ [DEBUG] Bloque {bloques_procesados}: {tiempo_bloque:.4f}s")

    tiempo_total = time.perf_counter() - start_procesamiento
    logger.info(f"⏱️ [DEBUG] Procesamiento de bloques: {tiempo_total:.4f}s | "
               f"Total bloques: {bloques_procesados} | "
               f"Avg por bloque: {tiempo_total/bloques_procesados if bloques_procesados > 0 else 0:.6f}s")

    logger.info(f"⏱️ [DEBUG] TIEMPO TOTAL generar_reporte_basico: {time.perf_counter() - start_total:.4f}s | "
               f"Entradas únicas en reporte: {len(reporte)}")
    return reporte

#Método que inicia el procesamiento
def procesar_servidor(servidor):
    try:
        print(f"\nIniciando procesamiento continuo para: {servidor.nombreServidor}")
        resultado = procesar_archivo_remoto_continuo(servidor.ruta, servidor.idServidor, timeout_minutos=1440)  # 24h
        return (servidor.nombreServidor, resultado)
    except Exception as e:
        logger.error(f"Error en hilo para {servidor.nombreServidor}: {str(e)}")
        return (servidor.nombreServidor, False)

#Configuración del procesamiento
def main():
    global ejecucion_activa
    executor = None
    
    try:
        # Detección de hostname
        hostname_actual = socket.gethostname()
        print(f"🖥️ Hostname detectado: {hostname_actual}")

        with app.app_context():
            acceso = (
                # Validar acceso remoto
                db.session.query(loAccesosremotos)
                .filter(loAccesosremotos.hostname == hostname_actual)
                .filter(loAccesosremotos.activo == 1)
                .first()
            )

            if not acceso:
                print("❌ No hay configuración para este host en la BD o no está activo")
                return

            # Obtener servidores asociados
            servidores = (
                db.session.query(loServidores)
                .filter(loServidores.idAccesoRemoto == acceso.idAcceso)
                .all()
            )

            print(f"🔢 Número de servidores asociados a {hostname_actual}: {len(servidores)}")

            for idx, servidor in enumerate(servidores, 1):
                print(f"{idx}. {servidor.nombreServidor} - Ruta: {servidor.ruta}")

            # Selección de servidores a procesar
            opcion = input("\n¿Deseas procesar todos los servidores? (s/n): ").strip().lower()
            servidores_a_procesar = servidores

            if opcion == 'n':
                seleccion = input("Ingresa el número del servidor a procesar: ").strip()
                if not seleccion.isdigit() or int(seleccion) < 1 or int(seleccion) > len(servidores):
                    print("Selección inválida. Terminando ejecución.")
                    return
                servidores_a_procesar = [servidores[int(seleccion) - 1]]

            signal.signal(signal.SIGINT, handler_shutdown)
            signal.signal(signal.SIGTERM, handler_shutdown)
             
            # Ejecución paralela con ThreadPool
            with ThreadPoolExecutor(max_workers=min(4, len(servidores_a_procesar))) as executor:
                futures = [executor.submit(procesar_servidor, servidor) for servidor in servidores_a_procesar]

                # Esperar finalización o señal de stop
                while ejecucion_activa.is_set() and any(not f.done() for f in futures):
                    time.sleep(0.1) 

                # Cancelar futuros pendientes si se recibió señal
                if not ejecucion_activa.is_set():
                    for future in futures:
                        if not future.done():
                            future.cancel()

                # Recopilar resultados
                resultados = []
                for future in futures:
                    try:
                        resultados.append(future.result())
                    except Exception as e:
                        logger.error(f"Error obteniendo resultado: {str(e)}")
                        resultados.append((None, False))

                # Mostrar resumen final
                print("\n=== RESUMEN DE PROCESAMIENTO ===")
                exitos = sum(1 for _, resultado in resultados if resultado)
                fallos = len(resultados) - exitos
                
                for nombre, resultado in resultados:
                    if nombre:
                        estado = "✅ ÉXITO" if resultado else "❌ FALLÓ"
                        print(f"{estado}: {nombre}")
                
                print(f"\nTotal: {exitos} exitos, {fallos} fallos")

    except Exception as e:
        print(f"🔥 Error crítico: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpieza del executor
        if executor:
            executor.shutdown(wait=False)

if __name__ == "__main__":
    main()
