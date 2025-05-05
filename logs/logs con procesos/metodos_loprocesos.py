------------------------clase con los metodos crud de la tabla lo_procesos--------------archivo metodos_loprocesos.py
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
    def finalizar_proceso(idAuditoria: int, totalLogs: int) -> bool:
        with app.app_context():
            try:
                proceso = LoProcesos.query.get(idAuditoria)
                if proceso:
                    proceso.fechaFin = datetime.now()
                    proceso.totalLogsProcesados = totalLogs
                    db.session.commit()
                    print("✅ Proceso finalizado correctamente.")
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
