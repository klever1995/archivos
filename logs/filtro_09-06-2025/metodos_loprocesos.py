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
        """Marca el fin de un proceso y actualiza métricas."""
        with app.app_context():
            try:
                proceso = LoProcesos.query.get(idAuditoria)
                if proceso:
                    proceso.fechaFin = datetime.now()
                    proceso.totalLogsProcesados = totalLogs
                    proceso.ultimo_byte_procesado = ultimo_byte
                    proceso.estado = 'COMPLETADO'
                    db.session.commit()
                    print("✅ Proceso finalizado correctamente.")
                    return True
                return False
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error al finalizar proceso: {e}")
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
        bloque_size: int = None  # NEW: Ahora es dinámico
    ) -> dict:
        """
        Reserva un bloque de bytes para procesamiento, con tamaño de bloque dinámico.
        - Si bloque_size es None, calcula un tamaño inicial basado en el archivo (10% o 10MB máximo).
        - Si falla, reduce el bloque a la mitad y reintenta (mínimo 1MB).
        """
        with app.app_context():
            try:
                checksum = ProcesosLogger.calcular_checksum(ruta_archivo)
                tamano_archivo = os.path.getsize(ruta_archivo)

                # NEW: Calcula bloque_size inicial si no se especifica
                if bloque_size is None:
                    bloque_size = min(tamano_archivo // 10, 10485760)  # 10% del archivo o 10MB

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

                # NEW: Si el archivo ya está completo
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

                # NEW: Ajusta byte_fin dinámicamente
                byte_fin = min(byte_inicio + bloque_size - 1, tamano_archivo)

                # NEW: Si el bloque es muy pequeño y queda mucho por procesar, aumenta
                if (byte_fin - byte_inicio) < 1048576 and (tamano_archivo - byte_inicio) > 10485760:
                    nuevo_bloque_size = min(bloque_size * 2, 104857600)  # Duplica (máx 100MB)
                    print(f"🔧 Ajustando bloque de {bloque_size} a {nuevo_bloque_size} bytes")
                    return ProcesosLogger.reservar_bloque(
                        ruta_archivo, idEmpresa, operador, idServidor, nuevo_bloque_size
                    )

                nuevo_proceso = LoProcesos(
                    idEmpresa=idEmpresa,
                    operador=operador,
                    idServidor=idServidor,
                    archivo=ruta_archivo,
                    byte_inicio=byte_inicio,
                    byte_fin=byte_fin,
                    estado='PROCESANDO',
                    checksum=checksum,
                    bloque_size=bloque_size  # NEW: Guardamos el tamaño usado
                )
                db.session.add(nuevo_proceso)
                db.session.commit()
                return {
                    'idAuditoria': nuevo_proceso.idAuditoria,
                    'byte_inicio': byte_inicio,
                    'byte_fin': byte_fin,
                    'bloque_size': bloque_size  # NEW: Retornamos el tamaño usado
                }

            except Exception as e:
                db.session.rollback()
                print(f"❌ Error reservando bloque: {e}")

                # NEW: Reduce el bloque a la mitad y reintenta (mínimo 1MB)
                nuevo_bloque_size = max(bloque_size // 2, 1048576)
                print(f"🔧 Reduciendo bloque de {bloque_size} a {nuevo_bloque_size} por error")
                return ProcesosLogger.reservar_bloque(
                    ruta_archivo, idEmpresa, operador, idServidor, nuevo_bloque_size
                )

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
