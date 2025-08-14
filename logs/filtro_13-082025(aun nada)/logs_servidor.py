from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel
from modelo.loServidores import loServidores
from modelo.loLogs import loLogs
from modelo.loProcesos import LoProcesos
from modelo.loLogsremotos import loLogsremotos
from modelo.loInterpretacionremota import loInterpretacionremota
from websocket_server import manager
from config import db, init_app
from flask import Flask
from fastapi import Path
import logging

# Configuración Flask
flask_app = Flask(__name__)
init_app(flask_app)

router = APIRouter(
    prefix="/api/servidores",
    tags=["Servidores de Logs"],
    responses={404: {"description": "No encontrado"}}
)

logger = logging.getLogger(__name__)

# Modelos Pydantic actualizados
class ServidorResponse(BaseModel):
    id_servidor: int
    nombre: str
    ruta: str
    activo: bool
    fecha_registro: str
    total_procesos: int
    id_acceso_remoto: Optional[int] = None  # Mantener este campo

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
    idAccesoRemoto: int 

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
    limite: int = Query(100, description="Límite de registros", ge=1, le=1000)
):
    try:
        with flask_app.app_context():
            fecha_minima = datetime.now() - timedelta(days=dias_atras)
            
            query = db.session.query(loServidores).filter(
                loServidores.idEmpresa == idEmpresa,
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
                    "total_procesos": len(s.procesos) if hasattr(s, 'procesos') else 0,
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

            # Validar que idAccesoRemoto esté presente
            if not servidor_data.idAccesoRemoto:
                raise HTTPException(
                    status_code=400,
                    detail="Se requiere idAccesoRemoto para crear un servidor"
                )

            nuevo_servidor = loServidores(
                idEmpresa=servidor_data.idEmpresa,
                ruta=servidor_data.ruta,
                nombreServidor=servidor_data.nombreServidor,
                activo=servidor_data.activo,
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

            # --- PASO 1: Eliminar datos dependientes ---
            db.session.query(loLogs).filter_by(idServidor=id_servidor).delete()
            db.session.query(loLogsremotos).filter_by(idServidor=id_servidor).delete()
            db.session.query(loInterpretacionremota).filter_by(idServidor=id_servidor).delete()

            procesos_del_servidor = db.session.query(LoProcesos).filter_by(idServidor=id_servidor).all()
            ids_procesos = [p.idAuditoria for p in procesos_del_servidor]

            if ids_procesos:
                db.session.query(loLogs).filter(loLogs.idAuditoria.in_(ids_procesos)).delete(synchronize_session=False)
                db.session.query(loLogsremotos).filter(loLogsremotos.idAuditoria.in_(ids_procesos)).delete(synchronize_session=False)
                db.session.query(LoProcesos).filter_by(idServidor=id_servidor).delete()

            # --- PASO OPCIONAL: Limpiar acceso remoto si ya no se usa ---
            if servidor.idAccesoRemoto:
                otros_servidores = db.session.query(loServidores)\
                    .filter_by(idAccesoRemoto=servidor.idAccesoRemoto)\
                    .filter(loServidores.idServidor != id_servidor)\
                    .count()

                if otros_servidores == 0:
                    logger.info(f"El acceso remoto {servidor.idAccesoRemoto} ya no está en uso")
                    # Opcional: borrar registro de acceso remoto

            # --- PASO 2: Eliminar el servidor ---
            db.session.delete(servidor)
            db.session.commit()

            return {
                "id_servidor": id_servidor,
                "mensaje": "Servidor eliminado correctamente",
                "tipo": "SERVIDOR"
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error eliminando servidor {id_servidor}: {str(e)}", exc_info=True)
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
async def obtener_evolucion_errores(
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

            # Notificación WebSocket
            await manager.send_json_message(
                data={
                    "eventType": "evolucion_errores_update",
                    "id_servidor": id_servidor,
                    "nombre_servidor": servidor.nombreServidor,
                    "datos": datos,
                    "timestamp": datetime.now().isoformat()
                },
                id_empresa=idEmpresa
            )

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
