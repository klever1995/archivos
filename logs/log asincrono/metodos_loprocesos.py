-------------metodos que agregados para poder sacar las lineas----------------archivo metodos_loprocesos.py------------
import sys
import os
from flask import Flask
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
    def iniciar_proceso(idEmpresa: int, operador: int, linea_inicio: int = 1) -> int:  # <-- Añade parámetro
        with app.app_context():
            try:
                nuevo_proceso = LoProcesos(
                    idEmpresa=idEmpresa,
                    operador=operador,
                    fechaInicio=datetime.now(),
                    totalLogsProcesados=0,
                    lineaInicio=linea_inicio  # <-- Guarda línea inicial
                )
                db.session.add(nuevo_proceso)
                db.session.commit()
                print(f"✅ Proceso iniciado (Línea inicio: {linea_inicio}).")
                return nuevo_proceso.idAuditoria
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error al iniciar proceso: {e}")
                return -1

    @staticmethod
    def finalizar_proceso(idAuditoria: int, totalLogs: int, linea_fin: int) -> bool:  # <-- Añade parámetro
        with app.app_context():
            try:
                proceso = db.session.get(LoProcesos, idAuditoria)  # Usa la forma moderna
                if proceso:
                    proceso.fechaFin = datetime.now()
                    proceso.totalLogsProcesados = totalLogs
                    proceso.lineaFin = linea_fin  # <-- Guarda línea final
                    db.session.commit()
                    print(f"✅ Proceso finalizado (Línea fin: {linea_fin}, Total logs: {totalLogs}).")
                    return True
                return False
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error al finalizar proceso: {e}")
                return False
            
#Método que obtiene la duración en segundos de un proceso completado
    @staticmethod
    def obtener_duracion_proceso(idAuditoria: int) -> float:
        with app.app_context():
            proceso = LoProcesos.query.get(idAuditoria)
            if proceso:
                return proceso.duracionSegundos 
            return None

    @staticmethod
    def obtener_ultima_linea(idEmpresa: int) -> int:
        """Devuelve la última línea procesada para una empresa (0 si no hay registros)."""
        with app.app_context():
            proceso = db.session.query(LoProcesos.lineaFin)\
                    .filter_by(idEmpresa=idEmpresa)\
                    .order_by(LoProcesos.idAuditoria.desc())\
                    .first()
            return proceso[0] if proceso else 0
