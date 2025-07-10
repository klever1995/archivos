-----------------------------logs_servidor.py
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel
from modelo.loServidores import loServidores
from modelo.loLogs import loLogs
from modelo.loProcesos import LoProcesos
from config import db, init_app
from flask import Flask
from fastapi import Path

# Configuración Flask
flask_app = Flask(__name__)
init_app(flask_app)

router = APIRouter(
    prefix="/api/servidores",
    tags=["Servidores de Logs"],
    responses={404: {"description": "No encontrado"}}
)

# Modelos Pydantic actualizados
class ServidorResponse(BaseModel):
    id_servidor: int
    nombre: str
    ruta: str
    activo: bool
    fecha_registro: str
    total_procesos: int
    es_remoto: bool  # Nuevo campo
    id_acceso_remoto: Optional[int] = None  # Nuevo campo

class MetaResponse(BaseModel):
    total_resultados: int
    fecha_minima: str
    parametros: dict

class ServidorListResponse(BaseModel):
    meta: MetaResponse
    resultados: List[ServidorResponse]

class ServidorCreate(BaseModel):
    idEmpresa: int
    ruta: str
    nombreServidor: str
    activo: bool = False
    esRemoto: bool = False  # Nuevo campo
    idAccesoRemoto: Optional[int] = None  # Nuevo campo

class MetricaServidorResponse(BaseModel):
    id_servidor: int
    nombre_servidor: str
    ruta: str
    activo: bool
    es_remoto: bool  # Nuevo campo
    id_acceso_remoto: Optional[int] = None  # Nuevo campo
    ultimo_proceso: Optional[dict]
    total_logs: int
    logs_por_nivel: dict
    promedio_ocurrencias: float

class MetricasListResponse(BaseModel):
    meta: MetaResponse
    resultados: List[MetricaServidorResponse]

class LogFiltradoResponse(BaseModel):
    id_log: int
    fecha_creacion: str
    nivel: str
    mensaje: str
    componente: Optional[str]
    ocurrencias: int
    lineas: Optional[List[str]]
    respuestaOpenai: Optional[str]

class LogsFiltradosListResponse(BaseModel):
    meta: MetaResponse
    resultados: List[LogFiltradoResponse]

class EvolucionErroresResponse(BaseModel):
    id_servidor: int
    nombre_servidor: str
    datos: List[dict]

# Endpoints actualizados
@router.get("/", response_model=ServidorListResponse)
def consultar_servidores(
    idEmpresa: int = Query(..., description="ID de la empresa a filtrar"),
    dias_atras: int = Query(30, description="Cantidad de días hacia atrás para filtrar"),
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo/inactivo"),
    es_remoto: Optional[bool] = Query(None, description="Filtrar por tipo de servidor"),
    limite: int = Query(100, description="Límite de registros", ge=1, le=1000)
):
    try:
        with flask_app.app_context():
            fecha_minima = datetime.now() - timedelta(days=dias_atras)
            
            query = db.session.query(loServidores).filter(
                loServidores.idEmpresa == idEmpresa,
                loServidores.fechaRegistro >= fecha_minima
            )
            
            if activo is not None:
                query = query.filter(loServidores.activo == activo)
            
            if es_remoto is not None:
                query = query.filter(loServidores.esRemoto == es_remoto)
            
            servidores = query.order_by(
                loServidores.fechaRegistro.desc()
            ).limit(limite).all()
            
            return {
                "meta": {
                    "total_resultados": len(servidores),
                    "fecha_minima": fecha_minima.isoformat(),
                    "parametros": {
                        "idEmpresa": idEmpresa,
                        "dias_atras": dias_atras,
                        "activo": activo,
                        "es_remoto": es_remoto,
                        "limite": limite
                    }
                },
                "resultados": [{
                    "id_servidor": s.idServidor,
                    "nombre": s.nombreServidor,
                    "ruta": s.ruta,
                    "activo": s.activo,
                    "fecha_registro": s.fechaRegistro.isoformat(),
                    "total_procesos": len(s.procesos) if hasattr(s, 'procesos') else 0,
                    "es_remoto": s.esRemoto,
                    "id_acceso_remoto": s.idAccesoRemoto
                } for s in servidores]
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar servidores: {str(e)}"
        )

@router.post("/")
def crear_servidor(servidor_data: ServidorCreate):
    try:
        with flask_app.app_context():
            # Validar servidor duplicado
            if db.session.query(loServidores).filter(
                (loServidores.ruta == servidor_data.ruta) | 
                (loServidores.nombreServidor == servidor_data.nombreServidor)
            ).first():
                raise HTTPException(
                    status_code=400,
                    detail="Ya existe un servidor con esta ruta o nombre"
                )
            
            # Validar que si es remoto, tenga idAccesoRemoto válido
            if servidor_data.esRemoto and not servidor_data.idAccesoRemoto:
                raise HTTPException(
                    status_code=400,
                    detail="Se requiere idAccesoRemoto para servidores remotos"
                )
            
            nuevo_servidor = loServidores(
                idEmpresa=servidor_data.idEmpresa,
                ruta=servidor_data.ruta,
                nombreServidor=servidor_data.nombreServidor,
                activo=servidor_data.activo,
                esRemoto=servidor_data.esRemoto,
                idAccesoRemoto=servidor_data.idAccesoRemoto
            )
            
            db.session.add(nuevo_servidor)
            db.session.commit()
            
            return {
                "id_servidor": nuevo_servidor.idServidor,
                "mensaje": "Servidor registrado correctamente"
            }
            
    except Exception as e:
        db.session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear servidor: {str(e)}"
        )

@router.delete("/{id_servidor}")
def eliminar_servidor(id_servidor: int = Path(..., description="ID del servidor a eliminar")):
    with flask_app.app_context():
        try:
            servidor = db.session.query(loServidores).filter_by(idServidor=id_servidor).first()

            if not servidor:
                raise HTTPException(
                    status_code=404,
                    detail=f"No se encontró el servidor con ID {id_servidor}"
                )

            db.session.delete(servidor)
            db.session.commit()

            return {
                "id_servidor": id_servidor,
                "mensaje": "Servidor eliminado correctamente"
            }

        except Exception as e:
            db.session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error al eliminar servidor: {str(e)}"
            )

@router.get("/metricas/{id_servidor}", response_model=MetricasListResponse)
def obtener_metricas_servidor(
    id_servidor: int = Path(..., description="ID del servidor a consultar"),
    idEmpresa: int = Query(..., description="ID de la empresa"),
    dias_atras: int = Query(100, description="Rango de días para métricas históricas")
):
    try:
        with flask_app.app_context():
            servidor = db.session.query(loServidores).filter_by(
                idServidor=id_servidor,
                idEmpresa=idEmpresa
            ).first()
            
            if not servidor:
                raise HTTPException(status_code=404, detail="Servidor no encontrado")

            ultimo_proceso = db.session.query(LoProcesos).filter_by(
                idServidor=id_servidor
            ).order_by(LoProcesos.fechaInicio.desc()).first()

            fecha_limite = datetime.now() - timedelta(days=dias_atras)
            logs_por_nivel = db.session.query(
                loLogs.nivel,
                db.func.count(loLogs.idLogAplicacion)
            ).filter(
                loLogs.idServidor == id_servidor,
                loLogs.fechaCreacion >= fecha_limite
            ).group_by(loLogs.nivel).all()

            response_data = {
                "meta": {
                    "total_resultados": 1,
                    "fecha_minima": fecha_limite.isoformat(),
                    "parametros": {"id_servidor": id_servidor, "dias_atras": dias_atras}
                },
                "resultados": [{
                    "id_servidor": servidor.idServidor,
                    "nombre_servidor": servidor.nombreServidor,
                    "ruta": servidor.ruta,
                    "activo": servidor.activo,
                    "es_remoto": servidor.esRemoto,
                    "id_acceso_remoto": servidor.idAccesoRemoto,
                    "ultimo_proceso": {
                        "estado": ultimo_proceso.estado if ultimo_proceso else None,
                        "logs_procesados": ultimo_proceso.totalLogsProcesados if ultimo_proceso else 0
                    },
                    "total_logs": sum(count for _, count in logs_por_nivel),
                    "logs_por_nivel": {nivel: count for nivel, count in logs_por_nivel},
                    "promedio_ocurrencias": db.session.query(
                        db.func.avg(loLogs.ocurrencias)
                    ).filter(loLogs.idServidor == id_servidor).scalar() or 0
                }]
            }

            if any(count > 0 for _, count in logs_por_nivel):
                from websocket_server import manager
                import asyncio
                
                asyncio.run(manager.send_json_message({
                    "eventType": "metrics_update",
                    "data": {
                        "idServidor": id_servidor,
                        "logs_por_nivel": {nivel: count for nivel, count in logs_por_nivel},
                        "total_logs": sum(count for _, count in logs_por_nivel),
                        "timestamp": datetime.now().isoformat()
                    }
                }, id_empresa=idEmpresa))

            return response_data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al calcular métricas: {str(e)}"
        )

@router.get("/{id_servidor}/logs-filtrados/", response_model=LogsFiltradosListResponse)
def obtener_logs_filtrados(
    id_servidor: int = Path(..., description="ID del servidor a consultar"),
    idEmpresa: int = Query(..., description="ID de la empresa"),
    nivel: Optional[str] = Query(None, description="Nivel de log (FATAL, ERROR, WARN, INFO)"),
    dias_atras: Optional[int] = Query(None, description="Rango de días para filtrar")
):
    try:
        with flask_app.app_context():
            servidor = db.session.query(loServidores).filter_by(
                idServidor=id_servidor,
                idEmpresa=idEmpresa
            ).first()
            
            if not servidor:
                raise HTTPException(status_code=404, detail="Servidor no encontrado")

            query = db.session.query(loLogs).filter(
                loLogs.idServidor == id_servidor
            )

            fecha_minima = datetime.min if dias_atras is None else datetime.now() - timedelta(days=dias_atras)
            query = query.filter(loLogs.fechaCreacion >= fecha_minima)

            if nivel:
                nivel = nivel.upper()
                if nivel not in ['FATAL', 'ERROR', 'WARN', 'INFO']:
                    raise HTTPException(
                        status_code=400, 
                        detail="Nivel debe ser FATAL, ERROR, WARN o INFO"
                    )
                query = query.filter(loLogs.nivel == nivel)

            logs = query.order_by(loLogs.fechaCreacion.desc()).all()

            return {
                "meta": {
                    "total_resultados": len(logs),
                    "fecha_minima": fecha_minima.isoformat(),
                    "parametros": {
                        "id_servidor": id_servidor,
                        "nivel": nivel,
                        "dias_atras": dias_atras
                    }
                },
                "resultados": [{
                    "id_log": log.idLogAplicacion,
                    "fecha_creacion": log.fechaCreacion.isoformat(),
                    "nivel": log.nivel,
                    "mensaje": log.mensaje,
                    "componente": log.componente,
                    "ocurrencias": log.ocurrencias,
                    "lineas": log.lineas,
                    "respuestaOpenai": log.respuestaOpenai
                } for log in logs]
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al filtrar logs: {str(e)}"
        )

@router.get("/{id_servidor}/evolucion-errores/", response_model=EvolucionErroresResponse)
def obtener_evolucion_errores(
    id_servidor: int = Path(..., description="ID del servidor a consultar"),
    idEmpresa: int = Query(..., description="ID de la empresa"),
    agrupacion: str = Query("por_proceso", description="Agrupación por 'proceso' o 'dia'")
):
    try:
        with flask_app.app_context():
            servidor = db.session.query(loServidores).filter_by(
                idServidor=id_servidor,
                idEmpresa=idEmpresa
            ).first()
            
            if not servidor:
                raise HTTPException(status_code=404, detail="Servidor no encontrado")

            fecha_limite = datetime.now() - timedelta(days=30)
            procesos = db.session.query(LoProcesos).filter(
                LoProcesos.idServidor == id_servidor,
                LoProcesos.fechaInicio >= fecha_limite
            ).order_by(LoProcesos.fechaInicio.desc()).all()

            datos = []
            for proceso in procesos:
                logs_por_nivel = db.session.query(
                    loLogs.nivel,
                    db.func.count(loLogs.idLogAplicacion)
                ).filter(
                    loLogs.idAuditoria == proceso.idAuditoria
                ).group_by(loLogs.nivel).all()

                datos.append({
                    "fecha": proceso.fechaInicio.isoformat(),
                    "procesos": [{
                        "id_auditoria": proceso.idAuditoria,
                        "estado": proceso.estado
                    }],
                    "logs": {nivel: count for nivel, count in logs_por_nivel}
                })

            return {
                "id_servidor": id_servidor,
                "nombre_servidor": servidor.nombreServidor,
                "meta": {
                    "total_resultados": len(datos),
                    "fecha_minima": fecha_limite.isoformat(),
                    "parametros": {
                        "id_servidor": id_servidor,
                        "agrupacion": agrupacion
                    }
                },
                "datos": datos
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al calcular evolución: {str(e)}"
        )







----------------------lo_Accesosarchivos.py
from config import db

class loAccesosarchivos(db.Model):
    __tablename__ = 'LO_ACCESOSARCHIVOS'  

    idArchivo = db.Column('idArchivo', db.Integer, primary_key=True, autoincrement=True)
    idAcceso = db.Column('idAcceso', db.Integer, 
                        db.ForeignKey('LO_ACCESOSREMOTOS.idAcceso'),  # ¡MAYÚSCULAS en FK!
                        nullable=False)
    rutaArchivo = db.Column('rutaArchivo', db.String(500), nullable=False)
    patronFiltro = db.Column('patronFiltro', db.String(100), server_default='ERROR')  # server_default para valor por defecto en BD

    # Relación (backref debe coincidir con LO_ACCESOSREMOTOS)
    acceso = db.relationship('loAccesosremotos', 
                           backref='lo_accesosarchivos',  
                           foreign_keys=[idAcceso])






---------------------------------lo_Accesosremotos.py
from config import db

class loAccesosremotos(db.Model):
    __tablename__ = 'LO_ACCESOSREMOTOS'  # Exactamente como en tu BD con mayúsculas

    idAcceso = db.Column('idAcceso', db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column('idEmpresa', db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    usuario = db.Column('usuario', db.String(100), nullable=False)
    contrasena = db.Column('contrasena', db.String(255), nullable=False)
    rutaRemota = db.Column('rutaRemota', db.String(500), nullable=False)
    activo = db.Column('activo', db.Boolean, default=True)
    fechaRegistro = db.Column('fechaRegistro', db.DateTime, server_default=db.func.current_timestamp())
    hostname = db.Column('hostname', db.String(255), nullable=False, unique=True)

    # Relación corregida (usando el nombre de la clase exacto)
    empresa = db.relationship('asEmpresa', backref='accesos_remotos')




-------------------------lo_Logsremotos.py
from config import db
from datetime import datetime

class LoLogsRemotos(db.Model):
    __tablename__ = 'LO_LOGSREMOTOS'

    idLogRemoto = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idEmpresa = db.Column(db.Integer, db.ForeignKey('AS_EMPRESA.idEmpresa'), nullable=False)
    idServidor = db.Column(db.Integer, db.ForeignKey('LO_SERVIDORES.idServidor'), nullable=False)
    idAuditoria = db.Column(db.Integer, db.ForeignKey('LO_PROCESOS.idAuditoria'), nullable=False)
    fechaCreacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    nivel = db.Column(db.String(10), nullable=False)
    mensaje = db.Column(db.Text, nullable=True)
    categoria = db.Column(db.String(100), nullable=True)
    ocurrencias = db.Column(db.Integer, default=1, nullable=True)

    # Relaciones
    empresa = db.relationship('AsEmpresa', backref='logs_remotos')
    servidor = db.relationship('LoServidores', backref='logs_remotos')
    proceso = db.relationship('LoProcesos', backref='logs_remotos')

    def __repr__(self):
        return f"<LoLogsRemotos idLogRemoto={self.idLogRemoto} nivel={self.nivel} fecha={self.fechaCreacion}>"













----------------------------------------prueba.py
import os
import sys
from datetime import datetime

# Configuración de entorno
os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from consumos.consulta_ia_openai import Consulta_ia_openai

def analizar_error(log_error: str):
    try:
        consulta = Consulta_ia_openai()
        
        # Medir tiempo de respuesta
        inicio = datetime.now()
        respuesta = consulta.interpretar_logs(log_error)
        tiempo_respuesta = (datetime.now() - inicio).total_seconds()
        
        # Formatear salida
        print("\n🔍 Análisis de OpenAI:")
        print(respuesta)
        print(f"\n⏱️ Tiempo de respuesta: {tiempo_respuesta:.2f} segundos")
        
        return respuesta
        
    except Exception as e:
        print(f"\n❌ Error al consultar OpenAI: {str(e)}")
        return None

if __name__ == "__main__":
    log_ejemplo = """
    2023-11-15 14:30:22 [ERROR] [nginx] 502 Bad Gateway
    upstream prematurely closed connection while reading response header
    """
    
    analizar_error(log_ejemplo)
