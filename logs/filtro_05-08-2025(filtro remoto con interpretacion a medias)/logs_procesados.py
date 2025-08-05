from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional
from modelo.loLogs import loLogs
from config import db, init_app
from flask import Flask

# Configuración de Flask para el contexto
flask_app = Flask(__name__)
init_app(flask_app)

router = APIRouter(
    prefix="/api/logs-aplicacion",
    tags=["Logs de Aplicación"],
    responses={404: {"description": "No encontrado"}}
)

@router.get("/")
def consultar_logs_aplicacion(
    idEmpresa: int = Query(..., description="ID de la empresa a filtrar"),
    dias_atras: int = Query(7, description="Días a retroceder en la consulta"),
    nivel: Optional[str] = Query(None, description="Filtrar por nivel (ERROR, WARN, INFO)"),
    estado: Optional[str] = Query(None, description="Filtrar por estado (ACTIVO, INACTIVO)"),
    componente: Optional[str] = Query(None, description="Filtrar por componente"),
    idServidor: Optional[int] = Query(None, description="Filtrar por ID de servidor"),
    idAuditoria: Optional[int] = Query(None, description="Filtrar por ID de proceso (auditoría)"),  # Cambiado de idProceso
    limite: int = Query(100, description="Límite de registros", ge=1, le=1000)
):
    try:
        with flask_app.app_context():
            fecha_minima = datetime.now() - timedelta(days=dias_atras)
            
            query = db.session.query(loLogs).filter(
                loLogs.idEmpresa == idEmpresa,
                loLogs.fechaCreacion >= fecha_minima
            )
            
            # Aplicar filtros
            if nivel:
                query = query.filter(loLogs.nivel == nivel.upper())
            if estado:
                query = query.filter(loLogs.estado == estado.upper())
            if componente:
                query = query.filter(loLogs.componente.ilike(f"%{componente}%"))
            if idServidor:
                query = query.filter(loLogs.idServidor == idServidor)
            if idAuditoria:
                query = query.filter(loLogs.idAuditoria == idAuditoria)  # Cambiado de idProceso
            
            logs = query.order_by(loLogs.fechaCreacion.desc()).limit(limite).all()
            
            return {
                "meta": {
                    "total_resultados": len(logs),
                    "fecha_minima": fecha_minima.isoformat(),
                    "parametros": {
                        "idEmpresa": idEmpresa,
                        "dias_atras": dias_atras,
                        "nivel": nivel,
                        "estado": estado,
                        "componente": componente,
                        "idServidor": idServidor,
                        "idAuditoria": idAuditoria,  # Cambiado de idProceso
                        "limite": limite
                    }
                },
                "resultados": [{
                    "id_log": log.idLogAplicacion,
                    "empresa": log.idEmpresa,
                    "servidor": log.idServidor,
                    "proceso": log.idAuditoria,  # Cambiado de idProceso
                    "fecha_creacion": log.fechaCreacion.isoformat(),
                    "nivel": log.nivel,
                    "componente": log.componente,
                    "mensaje": log.mensaje,
                    "categoria": log.categoria,
                    "ocurrencias": log.ocurrencias,
                    "estado": log.estado,
                    "hilo": log.hilo,
                    "lineas_afectadas": log.lineas,
                    "respuesta_ia": log.respuestaOpenai if log.respuestaOpenai else None
                } for log in logs]
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar logs: {str(e)}"
        )
