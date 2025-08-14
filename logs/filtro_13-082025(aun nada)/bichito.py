#!/usr/bin/env python3
import os
import sys
import socket
import logging
from collections import defaultdict
import concurrent.futures
import re
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
from websocket_server import manager
import asyncio
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import init_app, db
from flask import Flask
from modelo.loAccesosremotos import loAccesosremotos
from modelo.asEmpresa import asEmpresa
from modelo.loServidores import loServidores
from insertar import Logger
from metodos_loprocesos import ProcesosLogger
from logs_remotos import insertar_logs_remotos

# Configuración Flask y logging
app = Flask(__name__)
init_app(app)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def procesar_archivo_remoto(ruta_archivo: str, id_servidor: int) -> bool:
    import time
    start_total = time.perf_counter()
    
    with app.app_context():
        print(f"🚀 Procesando log: {ruta_archivo} (Servidor ID: {id_servidor})")
        try:
            # Debug: Tiempo de reservar_bloque
            start = time.perf_counter()
            bloque = ProcesosLogger.reservar_bloque(
                ruta_archivo=ruta_archivo,
                idEmpresa=1,
                operador=0,
                idServidor=id_servidor,
                bloque_size=5048576
            )
            logger.info(f"⏱️ [DEBUG] reservar_bloque: {time.perf_counter() - start:.4f}s")

            if not bloque:
                logger.info("No hay nuevos datos para procesar")
                return True

            id_auditoria = bloque['idAuditoria']
            byte_inicio = bloque['byte_inicio']
            byte_fin = bloque['byte_fin']

            # Debug: Tiempo de leer_chunk_local_para_pruebas
            start = time.perf_counter()
            contenido = leer_chunk_local_para_pruebas(ruta_archivo, byte_inicio, byte_fin)
            logger.info(f"⏱️ [DEBUG] leer_chunk_local: {time.perf_counter() - start:.4f}s | Bytes: {byte_fin - byte_inicio}")

            # Debug: Tiempo de extraer_bloques_log
            start = time.perf_counter()
            bloques = extraer_bloques_log(contenido, byte_inicio, ruta_archivo)
            logger.info(f"⏱️ [DEBUG] extraer_bloques_log: {time.perf_counter() - start:.4f}s | Bloques: {len(bloques)}")

            # Debug: Tiempo de generar_reporte_basico
            start = time.perf_counter()
            reporte = generar_reporte_basico(bloques)
            logger.info(f"⏱️ [DEBUG] generar_reporte_basico: {time.perf_counter() - start:.4f}s")

            # Debug: Tiempo de insertar_logs_remotos
            start = time.perf_counter()
            total = insertar_logs_remotos(reporte, id_servidor, id_auditoria)
            logger.info(f"⏱️ [DEBUG] insertar_logs_remotos: {time.perf_counter() - start:.4f}s | Logs: {total}")

            # Debug: Tiempo de finalizar_proceso
            start = time.perf_counter()
            ProcesosLogger.finalizar_proceso(
                idAuditoria=id_auditoria,
                totalLogs=total,
                ultimo_byte=byte_fin
            )
            logger.info(f"⏱️ [DEBUG] finalizar_proceso: {time.perf_counter() - start:.4f}s")

            logger.info(f"✅ Proceso completado. Logs insertados: {total} (Bytes: {byte_inicio}-{byte_fin})")
            print(f"✅ Procesamiento finalizado: {ruta_archivo} (Servidor ID: {id_servidor}) - Total logs: {total}")
            
            # Tiempo total
            logger.info(f"⏱️ [DEBUG] TIEMPO TOTAL: {time.perf_counter() - start_total:.4f}s")
            
            # 🚀 Enviar mensaje al frontend SOLO al finalizar el proceso
            try:
                mensaje_ws = {
                    "tipo": "proceso_finalizado",
                    "mensaje": "✅ Proceso completado en backend",
                    "rutaArchivo": ruta_archivo,
                    "idServidor": id_servidor,
                    "totalLogs": total
                }
                asyncio.run(manager.send_json_message(mensaje_ws, id_empresa=1))
                logger.info("📢 Mensaje de finalización enviado al frontend vía WebSocket")
            except Exception as e_ws:
                logger.error(f"❌ Error enviando mensaje WebSocket: {str(e_ws)}")
            
            return True

        except Exception as e:
            logger.error(f"Error procesando {ruta_archivo}: {str(e)}", exc_info=True)
            print(f"❌ Error al procesar: {ruta_archivo} (Servidor ID: {id_servidor}) - {str(e)}")
            if 'id_auditoria' in locals():
                ProcesosLogger.marcar_error(id_auditoria)
            return False

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
    """Función wrapper para procesamiento paralelo seguro"""
    try:
        print(f"\nIniciando procesamiento paralelo para: {servidor.nombreServidor}")
        resultado = procesar_archivo_remoto(servidor.ruta, servidor.idServidor)
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
