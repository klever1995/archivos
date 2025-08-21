from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional
from modelo.loServidores import loServidores
from modelo.loLogs import loLogs
from modelo.loProcesos import LoProcesos
from modelo.loLogsremotos import loLogsremotos
from modelo.loDepartamentos import loDepartamentos
from modelo.loInterpretacionremota import loInterpretacionremota
from config import db, init_app
from flask import Flask
from fastapi import Path
import logging

# Configuración de Flask para el contexto
flask_app = Flask(__name__)
init_app(flask_app)

# Router de FastAPI para servidores
router = APIRouter(
    prefix="/api/servidores",
    tags=["Servidores de Logs"],
    responses={404: {"description": "No encontrado"}}
)

logger = logging.getLogger(__name__)

#Endpoint que devuelve los servidores
@router.get("/")
def consultar_servidores(
    idEmpresa: int = Query(..., description="ID de la empresa a filtrar"),
    idDepartamento: Optional[int] = Query(None, description="ID del departamento para filtrar"),
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
            
            if idDepartamento is not None:
                query = query.filter(loServidores.idDepartamento == idDepartamento)
            
            if activo is not None:
                query = query.filter(loServidores.activo == activo)
            
            servidores = query.order_by(
                loServidores.fechaRegistro.desc()
            ).limit(limite).all()
            
            ids_departamentos = {s.idDepartamento for s in servidores if s.idDepartamento}
            departamentos = {
                d.idDepartamento: d.nombre
                for d in db.session.query(loDepartamentos)
                    .filter(loDepartamentos.idDepartamento.in_(ids_departamentos))
                    .all()
            } if ids_departamentos else {}
            
            return {
                "meta": {
                    "total_resultados": len(servidores),
                    "fecha_minima": fecha_minima.isoformat(),
                    "parametros": {
                        "idEmpresa": idEmpresa,
                        "idDepartamento": idDepartamento,
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
                    "id_acceso_remoto": s.idAccesoRemoto,
                    "id_departamento": s.idDepartamento,
                    "nombre_departamento": departamentos.get(s.idDepartamento)
                } for s in servidores]
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar servidores: {str(e)}"
        )

#Endpoint que crea servidores
@router.post("/")
def crear_servidor(datos: dict):
    try:
        with flask_app.app_context():
  
            required_fields = ["idEmpresa", "ruta", "nombreServidor", "idAccesoRemoto"]
            for field in required_fields:
                if not datos.get(field):
                    raise HTTPException(status_code=400, detail=f"Campo {field} es requerido")

            if db.session.query(loServidores).filter(
                (loServidores.ruta == datos["ruta"]) | 
                (loServidores.nombreServidor == datos["nombreServidor"])
            ).first():
                raise HTTPException(
                    status_code=400,
                    detail="Ya existe un servidor con esta ruta o nombre"
                )

            if datos.get("idDepartamento"):
                departamento = db.session.query(loDepartamentos).filter_by(
                    idDepartamento=datos["idDepartamento"]
                ).first()
                if not departamento:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No existe el departamento con ID {datos['idDepartamento']}"
                    )

            nuevo_servidor = loServidores(
                idEmpresa=datos["idEmpresa"],
                ruta=datos["ruta"],
                nombreServidor=datos["nombreServidor"],
                activo=datos.get("activo", False),
                idAccesoRemoto=datos["idAccesoRemoto"],
                idDepartamento=datos.get("idDepartamento")
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

# Endpoint que elimina servidores
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

            db.session.query(loLogs).filter_by(idServidor=id_servidor).delete()
            db.session.query(loLogsremotos).filter_by(idServidor=id_servidor).delete()
            db.session.query(loInterpretacionremota).filter_by(idServidor=id_servidor).delete()

            procesos_del_servidor = db.session.query(LoProcesos).filter_by(idServidor=id_servidor).all()
            ids_procesos = [p.idAuditoria for p in procesos_del_servidor]

            if ids_procesos:
                db.session.query(loLogs).filter(loLogs.idAuditoria.in_(ids_procesos)).delete(synchronize_session=False)
                db.session.query(loLogsremotos).filter(loLogsremotos.idAuditoria.in_(ids_procesos)).delete(synchronize_session=False)
                db.session.query(LoProcesos).filter_by(idServidor=id_servidor).delete()

            if servidor.idAccesoRemoto:
                otros_servidores = db.session.query(loServidores)\
                    .filter_by(idAccesoRemoto=servidor.idAccesoRemoto)\
                    .filter(loServidores.idServidor != id_servidor)\
                    .count()

                if otros_servidores == 0:
                    logger.info(f"El acceso remoto {servidor.idAccesoRemoto} ya no está en uso")

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

#Endpoint que devuelve logs filtrados
@router.get("/{id_servidor}/logs-filtrados/")
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

#Endpoint que devuleve las meticas de los logs
@router.get("/{id_servidor}/evolucion-errores/")
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
        logger.error(f"Error en obtener_evolucion_errores: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error al calcular evolución: {str(e)}"
        )
