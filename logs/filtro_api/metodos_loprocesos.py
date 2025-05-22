import sys
import os
import hashlib
from flask import Flask
from sqlalchemy import text
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import init_app, db 
from modelo.loProcesos import LoProcesos
from datetime import datetime
from modelo.asEmpresa import asEmpresa

app = Flask(__name__)
init_app(app)

#Clase para gestionar procesos de logs en LO_PROCESOS
class ProcesosLogger:

#Método que registra el inicio de un nuevo proceso
    @staticmethod
    def iniciar_proceso(idEmpresa: int, operador: int) -> int:
        with app.app_context():
            try:
                nuevo_proceso = LoProcesos(
                    idEmpresa=idEmpresa,
                    operador=operador,
                    fechaInicio=datetime.now(),
                    totalLogsProcesados=0
                )
                db.session.add(nuevo_proceso)
                db.session.commit()
                print("✅ Proceso iniciado correctamente.")
                return nuevo_proceso.idAuditoria
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error al iniciar proceso: {e}")
                return -1

#Método que marca el fin de un proceso y actualiza el total de logs procesados
    @staticmethod
    def finalizar_proceso(idAuditoria: int, totalLogs: int, ultimo_byte: int) -> bool:
        with app.app_context():
            try:
                proceso = LoProcesos.query.get(idAuditoria)
                if proceso:
                    proceso.fechaFin = datetime.now()
                    proceso.totalLogsProcesados = totalLogs
                    proceso.ultimo_byte_procesado = ultimo_byte  # Nuevo campo
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
        """Genera SHA-256 del archivo para detectar cambios"""
        hash_sha256 = hashlib.sha256()
        with open(ruta_archivo, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    @staticmethod
    def reservar_bloque(ruta_archivo: str, idEmpresa: int, operador: int, bloque_size: int = 1048576) -> dict:
        with app.app_context():
            try:
                # 1. Calcular checksum del archivo ANTES de procesar
                checksum = ProcesosLogger.calcular_checksum(ruta_archivo)  # <- Usamos el método ya existente
                
                # 2. Iniciar transacción con bloqueo
                db.session.begin()

                # 3. Obtener último byte procesado (igual que antes)
                ultimo_proceso = db.session.query(LoProcesos).filter(
                    LoProcesos.archivo == ruta_archivo,
                    LoProcesos.estado.in_(['COMPLETADO', 'PROCESANDO'])
                ).order_by(LoProcesos.byte_fin.desc()).with_for_update().first()

                byte_inicio = ultimo_proceso.byte_fin + 1 if ultimo_proceso else 0
                tamano_archivo = os.path.getsize(ruta_archivo)

                if byte_inicio >= tamano_archivo:
                    db.session.rollback()
                    return None

                byte_fin = min(byte_inicio + bloque_size - 1, tamano_archivo)

                # 4. Crear nuevo proceso CON el checksum
                nuevo_proceso = LoProcesos(
                    idEmpresa=idEmpresa,
                    operador=operador,
                    archivo=ruta_archivo,
                    byte_inicio=byte_inicio,
                    byte_fin=byte_fin,
                    estado='PROCESANDO',
                    checksum=checksum  # <- Aquí guardamos el checksum
                )
                db.session.add(nuevo_proceso)
                db.session.commit()

                return {
                    'idAuditoria': nuevo_proceso.idAuditoria,
                    'byte_inicio': byte_inicio,
                    'byte_fin': byte_fin
                }

            except Exception as e:
                db.session.rollback()
                print(f"❌ Error reservando bloque: {e}")
                return None

    @staticmethod
    def marcar_error(idAuditoria: int):
        """Cambia estado a FALLIDO si hay errores"""
        with app.app_context():
            proceso = LoProcesos.query.get(idAuditoria)
            if proceso:
                proceso.estado = 'FALLIDO'
                db.session.commit()

    @staticmethod
    def obtener_ultimo_byte_procesado(ruta_archivo: str) -> int:
        """Obtiene el último byte procesado para un archivo específico"""
        with app.app_context():
            try:
                ultimo_proceso = db.session.query(LoProcesos).filter(
                    LoProcesos.archivo == ruta_archivo,
                    LoProcesos.estado == 'COMPLETADO'
                ).order_by(LoProcesos.byte_fin.desc()).first()
                
                return ultimo_proceso.byte_fin if ultimo_proceso else 0
            except Exception as e:
                print(f"❌ Error obteniendo último byte: {e}")
                return 0

