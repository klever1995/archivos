from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel  # Para modelos de respuesta
from modelo.loServidores import loServidores
from modelo.loLogs import loLogs
from modelo.loProcesos import LoProcesos
from config import db, init_app
from flask import Flask
from fastapi import Path

# Configuración Flask (necesaria para SQLAlchemy en tu caso)
flask_app = Flask(__name__)
init_app(flask_app)

router = APIRouter(
    prefix="/api/servidores",
    tags=["Servidores de Logs"],
    responses={404: {"description": "No encontrado"}}
)

# Modelo Pydantic para respuesta estructurada
class ServidorResponse(BaseModel):
    id_servidor: int
    nombre: str
    ruta: str
    activo: bool
    fecha_registro: str
    total_procesos: int

class MetaResponse(BaseModel):
    total_resultados: int
    fecha_minima: str
    parametros: dict

class ServidorListResponse(BaseModel):
    meta: MetaResponse
    resultados: List[ServidorResponse]

class MetricaServidorResponse(BaseModel):
    id_servidor: int
    nombre_servidor: str
    ruta: str
    activo: bool
    ultimo_proceso: Optional[dict]  # Datos del último proceso (similar a LO_PROCESOS)
    total_logs: int
    logs_por_nivel: dict  # Ej: {"INFO": 10, "ERROR": 2}
    promedio_ocurrencias: float

class MetricasListResponse(BaseModel):
    meta: MetaResponse  # Reutilizamos tu clase Meta existente
    resultados: List[MetricaServidorResponse]

# Modelo Pydantic para respuesta de logs filtrados
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

@router.get("/", response_model=ServidorListResponse)
def consultar_servidores(
    idEmpresa: int = Query(..., description="ID de la empresa a filtrar"),
    dias_atras: int = Query(30, description="Cantidad de días hacia atrás para filtrar"),
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo/inactivo"),
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
                        "limite": limite
                    }
                },
                "resultados": [{
                    "id_servidor": s.idServidor,
                    "nombre": s.nombreServidor,
                    "ruta": s.ruta,
                    "activo": s.activo,
                    "fecha_registro": s.fechaRegistro.isoformat(),
                    "total_procesos": len(s.procesos) if hasattr(s, 'procesos') else 0
                } for s in servidores]
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar servidores: {str(e)}"
        )

# Modelo Pydantic para creación
class ServidorCreate(BaseModel):
    idEmpresa: int
    ruta: str
    nombreServidor: str
    activo: bool = False

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
            
            nuevo_servidor = loServidores(
                idEmpresa=servidor_data.idEmpresa,
                ruta=servidor_data.ruta,
                nombreServidor=servidor_data.nombreServidor,
                activo=servidor_data.activo
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
def eliminar_servidor(
    id_servidor: int = Path(..., description="ID del servidor a eliminar")
):
    try:
        with flask_app.app_context():
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
    dias_atras: int = Query(7, description="Rango de días para métricas históricas")
):
    try:
        with flask_app.app_context():
            # 1. Validar servidor
            servidor = db.session.query(loServidores).filter_by(
                idServidor=id_servidor,
                idEmpresa=idEmpresa
            ).first()
            
            if not servidor:
                raise HTTPException(status_code=404, detail="Servidor no encontrado")

            # 2. Obtener último proceso
            ultimo_proceso = db.session.query(LoProcesos).filter_by(
                idServidor=id_servidor
            ).order_by(LoProcesos.fechaInicio.desc()).first()

            # 3. CORRECCIÓN: Usar filter() en lugar de filter_by() para condiciones complejas
            fecha_limite = datetime.now() - timedelta(days=dias_atras)
            logs_por_nivel = db.session.query(
                loLogs.nivel,
                db.func.count(loLogs.idLogAplicacion)
            ).filter(
                loLogs.idServidor == id_servidor,
                loLogs.fechaCreacion >= fecha_limite
            ).group_by(loLogs.nivel).all()

            # 4. Estructurar respuesta
            return {
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

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al calcular métricas: {str(e)}"
        )

class LogsFiltradosListResponse(BaseModel):
    meta: MetaResponse
    resultados: List[LogFiltradoResponse]

@router.get("/{id_servidor}/logs-filtrados/", response_model=LogsFiltradosListResponse)
def obtener_logs_filtrados(
    id_servidor: int = Path(..., description="ID del servidor a consultar"),
    idEmpresa: int = Query(..., description="ID de la empresa"),
    nivel: Optional[str] = Query(None, description="Nivel de log (ERROR, WARN, INFO)"),
    dias_atras: Optional[int] = Query(None, description="Rango de días para filtrar")
):
    try:
        with flask_app.app_context():
            # Validar servidor
            servidor = db.session.query(loServidores).filter_by(
                idServidor=id_servidor,
                idEmpresa=idEmpresa
            ).first()
            
            if not servidor:
                raise HTTPException(status_code=404, detail="Servidor no encontrado")

            # Consulta base
            query = db.session.query(loLogs).filter(
                loLogs.idServidor == id_servidor
            )

            # Fecha mínima (usar fecha muy antigua si no viene dias_atras)
            fecha_minima = datetime.min if dias_atras is None else datetime.now() - timedelta(days=dias_atras)
            query = query.filter(loLogs.fechaCreacion >= fecha_minima)

            # Validar nivel si viene
            if nivel:
                nivel = nivel.upper()
                if nivel not in ['ERROR', 'WARN', 'INFO']:
                    raise HTTPException(status_code=400, detail="Nivel debe ser ERROR, WARN o INFO")
                query = query.filter(loLogs.nivel == nivel)

            # Obtener logs
            logs = query.order_by(loLogs.fechaCreacion.desc()).all()

            return {
                "meta": {
                    "total_resultados": len(logs),
                    "fecha_minima": fecha_minima.isoformat(),  # Siempre tendrá valor
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
