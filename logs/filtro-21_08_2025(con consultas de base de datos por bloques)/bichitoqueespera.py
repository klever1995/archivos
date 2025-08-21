#!/usr/bin/env python3
import os
import sys
import socket
import logging
from collections import defaultdict
import time

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

def procesar_archivo_remoto_continuo(ruta_archivo: str, id_servidor: int) -> bool:
    """
    Procesamiento continuo que espera 60 segundos cuando no encuentra logs
    """
    ejecucion_activa = True
    
    while ejecucion_activa:
        start_total = time.perf_counter()
        
        with app.app_context():
            try:
                bloque = ProcesosLogger.reservar_bloque(
                    ruta_archivo=ruta_archivo,
                    idEmpresa=1,
                    operador=0,
                    idServidor=id_servidor,
                    bloque_size=5048576
                )

                if not bloque:
                    logger.info("⏳ No se encontraron logs nuevos, esperando 60 segundos...")
                    time.sleep(60)  # Espera fija de 1 minuto
                    continue

                # ... (todo el resto del procesamiento se mantiene igual)
                id_auditoria = bloque['idAuditoria']
                byte_inicio = bloque['byte_inicio']
                byte_fin = bloque['byte_fin']

                contenido = leer_chunk_local_para_pruebas(ruta_archivo, byte_inicio, byte_fin)
                bloques = extraer_bloques_log(contenido, byte_inicio, ruta_archivo)
                reporte = generar_reporte_basico(bloques)
                total = insertar_logs_remotos(reporte, id_servidor, id_auditoria)

                ProcesosLogger.finalizar_proceso(
                    idAuditoria=id_auditoria,
                    totalLogs=total,
                    ultimo_byte=byte_fin
                )

                if total == 0:
                    logger.info("⏳ Bloque procesado con 0 logs, esperando 60 segundos...")
                    time.sleep(60)  # También espera si el bloque tiene 0 logs
                else:
                    logger.info(f"✅ Procesado bloque: {total} logs (Bytes: {byte_inicio}-{byte_fin})")
                    time.sleep(1)  # Pequeña pausa entre bloques con logs

            except Exception as e:
                logger.error(f"Error en iteración: {str(e)}", exc_info=True)
                time.sleep(10)  # Pausa más corta en caso de error
                continue

    return True

def leer_chunk_local_para_pruebas(ruta: str, byte_inicio: int, byte_fin: int) -> str:
    try:
        with open(ruta, 'rb') as f:
            f.seek(byte_inicio)
            return f.read(byte_fin - byte_inicio + 1).decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Error leyendo chunk local: {str(e)}")
        raise

def extraer_bloques_log(chunk: str, byte_inicio: int = 0, ruta_archivo: str = None) -> list:
    import time  # Añadir al inicio del archivo si no existe
    start_total = time.perf_counter()
    
    bloques = []
    bloque_actual = []
    linea_inicio = None
    
    # Debug: Tiempo de cálculo de líneas previas
    lineas_previas = 0
    if byte_inicio > 0 and ruta_archivo:
        try:
            start = time.perf_counter()
            with open(ruta_archivo, 'rb') as f:
                f.seek(0)
                lineas_previas = f.read(byte_inicio).decode('utf-8', errors='ignore').count('\n')
            logger.info(f"⏱️ [DEBUG] calcular_lineas_previas: {time.perf_counter() - start:.4f}s | Líneas: {lineas_previas}")
        except Exception as e:
            logger.error(f"Error calculando líneas previas: {str(e)}")
            lineas_previas = 0

    # Debug: Tiempo de splitlines
    start = time.perf_counter()
    lineas = chunk.splitlines(keepends=True)
    logger.info(f"⏱️ [DEBUG] splitlines: {time.perf_counter() - start:.4f}s | Líneas: {len(lineas)}")

    # Procesamiento principal
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

    logger.info(f"⏱️ [DEBUG] bucle_principal: {time.perf_counter() - start_loop:.4f}s | "
               f"Líneas: {lineas_procesadas} | Bloques: {len(bloques)} | "
               f"Descartados: {bloques_descartados}")

    # Bloque final
    if bloque_actual and Logger.extraer_nivel(bloque_actual[0]) not in ['INFO', 'DEBUG']:
        bloques.append({
            'linea_inicio': linea_inicio,
            'contenido': ''.join(bloque_actual)
        })

    logger.info(f"⏱️ [DEBUG] TIEMPO TOTAL extraer_bloques_log: {time.perf_counter() - start_total:.4f}s | "
               f"Bloques finales: {len(bloques)}")
    return bloques

def generar_reporte_basico(bloques: list) -> dict:
    import time  # Añadir al inicio del archivo si no existe
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

    # Debug: Contadores
    bloques_procesados = 0
    start_procesamiento = time.perf_counter()

    for bloque in bloques:
        bloques_procesados += 1
        linea_inicio = bloque['linea_inicio']
        
        # Debug: Tiempo por bloque individual
        start_bloque = time.perf_counter()
        Logger.procesar_bloque(
            bloque_actual=bloque['contenido'].splitlines(keepends=True),
            linea_inicio=str(linea_inicio),
            reporte=reporte
        )
        tiempo_bloque = time.perf_counter() - start_bloque
        
        # Log cada 100 bloques para no saturar
        if bloques_procesados % 100 == 0:
            logger.info(f"⏱️ [DEBUG] Bloque {bloques_procesados}: {tiempo_bloque:.4f}s")

    # Métricas finales
    tiempo_total = time.perf_counter() - start_procesamiento
    logger.info(f"⏱️ [DEBUG] Procesamiento de bloques: {tiempo_total:.4f}s | "
               f"Total bloques: {bloques_procesados} | "
               f"Avg por bloque: {tiempo_total/bloques_procesados if bloques_procesados > 0 else 0:.6f}s")

    logger.info(f"⏱️ [DEBUG] TIEMPO TOTAL generar_reporte_basico: {time.perf_counter() - start_total:.4f}s | "
               f"Entradas únicas en reporte: {len(reporte)}")
    return reporte

def procesar_servidor(servidor):
    try:
        print(f"\nIniciando procesamiento continuo para: {servidor.nombreServidor}")
        resultado = procesar_archivo_remoto_continuo(servidor.ruta, servidor.idServidor)
        return (servidor.nombreServidor, resultado)
    except Exception as e:
        logger.error(f"Error en hilo para {servidor.nombreServidor}: {str(e)}")
        return (servidor.nombreServidor, False)

def main():
    try:
        hostname_actual = socket.gethostname()
        print(f"🖥️ Hostname detectado: {hostname_actual}")

        with app.app_context():
            acceso = (
                db.session.query(loAccesosremotos)
                .filter(loAccesosremotos.hostname == hostname_actual)
                .filter(loAccesosremotos.activo == 1)
                .first()
            )

            if not acceso:
                print("❌ No hay configuración para este host en la BD o no está activo")
                return

            servidores = (
                db.session.query(loServidores)
                .filter(loServidores.idAccesoRemoto == acceso.idAcceso)
                .all()
            )

            print(f"🔢 Número de servidores asociados a {hostname_actual}: {len(servidores)}")

            for idx, servidor in enumerate(servidores, 1):
                print(f"{idx}. {servidor.nombreServidor} - Ruta: {servidor.ruta}")

            # Pedir al usuario si quiere procesar todos o uno solo
            opcion = input("\n¿Deseas procesar todos los servidores? (s/n): ").strip().lower()
            servidores_a_procesar = servidores

            if opcion == 'n':
                seleccion = input("Ingresa el número del servidor a procesar: ").strip()
                if not seleccion.isdigit() or int(seleccion) < 1 or int(seleccion) > len(servidores):
                    print("Selección inválida. Terminando ejecución.")
                    return
                servidores_a_procesar = [servidores[int(seleccion) - 1]]

            # Procesamiento paralelo seguro
            with ThreadPoolExecutor(max_workers=min(4, len(servidores_a_procesar))) as executor:
                resultados = list(executor.map(procesar_servidor, servidores_a_procesar))
                
                # Mostrar resumen
                print("\n=== RESUMEN DE PROCESAMIENTO ===")
                exitos = sum(1 for _, resultado in resultados if resultado)
                fallos = len(resultados) - exitos
                
                for nombre, resultado in resultados:
                    estado = "✅ ÉXITO" if resultado else "❌ FALLÓ"
                    print(f"{estado}: {nombre}")
                
                print(f"\nTotal: {exitos} exitos, {fallos} fallos")

    except Exception as e:
        print(f"🔥 Error crítico: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
