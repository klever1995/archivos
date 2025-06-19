import sys
import os
import hashlib
from flask import Flask
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import init_app, db 
from modelo.loProcesos import LoProcesos
from datetime import datetime

app = Flask(__name__)
init_app(app)

class ProcesosLogger:

    @staticmethod
    def iniciar_proceso(idEmpresa: int, operador: int, idServidor: int = None) -> int:
        """Registra el inicio de un nuevo proceso, opcionalmente asociado a un servidor."""
        with app.app_context():
            try:
                nuevo_proceso = LoProcesos(
                    idEmpresa=idEmpresa,
                    operador=operador,
                    idServidor=idServidor,
                    fechaInicio=datetime.now(),
                    totalLogsProcesados=0,
                    estado='PROCESANDO'
                )
                db.session.add(nuevo_proceso)
                db.session.commit()
                print("✅ Proceso iniciado correctamente.")
                return nuevo_proceso.idAuditoria
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error al iniciar proceso: {e}")
                return -1

    @staticmethod
    def finalizar_proceso(idAuditoria: int, totalLogs: int, ultimo_byte: int) -> bool:
        """Marca el fin de un proceso y actualiza métricas de forma ATÓMICA."""
        with app.app_context():
            db.session.begin()  # Inicia transacción explícita
            try:
                proceso = LoProcesos.query.get(idAuditoria)
                if proceso:
                    proceso.fechaFin = datetime.now()
                    proceso.totalLogsProcesados = totalLogs
                    proceso.ultimo_byte_procesado = ultimo_byte
                    proceso.estado = 'COMPLETADO'
                    db.session.commit()  # Confirmar cambios
                    print(f"✅ Proceso {idAuditoria} finalizado y persistido en DB.")
                    return True
                return False
            except Exception as e:
                db.session.rollback()  # Revertir en caso de error
                print(f"❌ Error al finalizar proceso {idAuditoria}: {e}")
                return False

    @staticmethod
    def calcular_checksum(ruta_archivo: str) -> str:
        """Genera SHA-256 del archivo."""
        hash_sha256 = hashlib.sha256()
        with open(ruta_archivo, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    @staticmethod
    def reservar_bloque(
        ruta_archivo: str,
        idEmpresa: int,
        operador: int,
        idServidor: int = None,
        bloque_size: int = None,
        forzar_completo: bool = False
    ) -> dict:

        with app.app_context():
            try:
                checksum = ProcesosLogger.calcular_checksum(ruta_archivo)
                tamano_archivo = os.path.getsize(ruta_archivo)
                
                # Manejo especial para archivos pequeños cuando se fuerza completo
                if forzar_completo or tamano_archivo < 1024:  # Consideramos pequeño <1KB
                    # Verificar si ya está completo
                    ultimo_proceso = db.session.query(LoProcesos).filter(
                        LoProcesos.archivo == ruta_archivo,
                        LoProcesos.estado.in_(['COMPLETADO', 'PROCESANDO']),
                        LoProcesos.idServidor == idServidor if idServidor else True
                    ).order_by(LoProcesos.byte_fin.desc()).first()

                    if ultimo_proceso and ultimo_proceso.byte_fin >= tamano_archivo:
                        return None  # Ya está completo

                    # Crear bloque completo
                    nuevo_proceso = LoProcesos(
                        idEmpresa=idEmpresa,
                        operador=operador,
                        idServidor=idServidor,
                        archivo=ruta_archivo,
                        byte_inicio=0,
                        byte_fin=tamano_archivo,
                        estado='PROCESANDO',
                        checksum=checksum,
                        bloque_size=tamano_archivo,
                        fechaInicio=datetime.now()
                    )
                    db.session.add(nuevo_proceso)
                    db.session.commit()
                    return {
                        'idAuditoria': nuevo_proceso.idAuditoria,
                        'byte_inicio': 0,
                        'byte_fin': tamano_archivo,
                        'bloque_size': tamano_archivo
                    }

                # Tamaño de bloque fijo (10MB máximo)
                if bloque_size is None:
                    if tamano_archivo <= 1048576:  # Si es <= 1MB, procesar completo
                        return ProcesosLogger.reservar_bloque(
                            ruta_archivo, idEmpresa, operador, idServidor, 
                            bloque_size=tamano_archivo, 
                            forzar_completo=True
                        )
                    bloque_size = 10485760  # 10MB fijos

                db.session.begin()

                # Filtra por ruta + servidor (si existe)
                query = db.session.query(LoProcesos).filter(
                    LoProcesos.archivo == ruta_archivo,
                    LoProcesos.estado.in_(['COMPLETADO', 'PROCESANDO'])
                )
                if idServidor:
                    query = query.filter(LoProcesos.idServidor == idServidor)

                ultimo_proceso = query.order_by(LoProcesos.byte_fin.desc()).with_for_update().first()
                byte_inicio = ultimo_proceso.byte_fin + 1 if ultimo_proceso else 0

                # Si el archivo ya está completo
                if byte_inicio >= tamano_archivo:
                    byte_fin = ultimo_proceso.byte_fin if ultimo_proceso else 0
                    nuevo_proceso = LoProcesos(
                        idEmpresa=idEmpresa,
                        operador=operador,
                        idServidor=idServidor,
                        archivo=ruta_archivo,
                        byte_inicio=byte_fin,
                        byte_fin=byte_fin,
                        estado='COMPLETADO',
                        checksum=checksum,
                        totalLogsProcesados=0,
                        fechaInicio=datetime.now(),
                        fechaFin=datetime.now()
                    )
                    db.session.add(nuevo_proceso)
                    db.session.commit()
                    return None  # No hay bloques nuevos

                # Ajusta byte_fin dinámicamente (sin superar el tamaño del archivo)
                byte_fin = min(byte_inicio + bloque_size - 1, tamano_archivo)

                # Si el bloque residual es muy pequeño (<1MB), lo incluimos en el bloque actual
                if (tamano_archivo - byte_fin) < 1048576:
                    byte_fin = tamano_archivo - 1

                nuevo_proceso = LoProcesos(
                    idEmpresa=idEmpresa,
                    operador=operador,
                    idServidor=idServidor,
                    archivo=ruta_archivo,
                    byte_inicio=byte_inicio,
                    byte_fin=byte_fin,
                    estado='PROCESANDO',
                    checksum=checksum,
                    bloque_size=bloque_size,
                    fechaInicio=datetime.now()
                )
                db.session.add(nuevo_proceso)
                db.session.commit()
                return {
                    'idAuditoria': nuevo_proceso.idAuditoria,
                    'byte_inicio': byte_inicio,
                    'byte_fin': byte_fin,
                    'bloque_size': bloque_size
                }

            except Exception as e:
                db.session.rollback()
                logger.error(f"❌ Error reservando bloque: {e}")

                # Reduce el bloque a la mitad y reintenta (mínimo 1MB)
                if bloque_size is not None:
                    nuevo_bloque_size = max(bloque_size // 2, 1048576)
                    logger.info(f"🔧 Reduciendo bloque de {bloque_size} a {nuevo_bloque_size} por error")
                    return ProcesosLogger.reservar_bloque(
                        ruta_archivo, idEmpresa, operador, idServidor, nuevo_bloque_size
                    )
                return None

    @staticmethod
    def marcar_error(idAuditoria: int):
        """Marca un proceso como fallido."""
        with app.app_context():
            proceso = LoProcesos.query.get(idAuditoria)
            if proceso:
                proceso.estado = 'FALLIDO'
                db.session.commit()

    @staticmethod
    def obtener_ultimo_byte_procesado(ruta_archivo: str, idServidor: int = None) -> int:
        """Obtiene el último byte procesado para un archivo (y servidor, si se especifica)."""
        with app.app_context():
            try:
                query = db.session.query(LoProcesos).filter(
                    LoProcesos.archivo == ruta_archivo,
                    LoProcesos.estado == 'COMPLETADO'
                )
                if idServidor:
                    query = query.filter(LoProcesos.idServidor == idServidor)

                ultimo_proceso = query.order_by(LoProcesos.byte_fin.desc()).first()
                return ultimo_proceso.byte_fin if ultimo_proceso else 0
            except Exception as e:
                print(f"❌ Error obteniendo último byte: {e}")
                return 0
