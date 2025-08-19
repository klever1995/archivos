from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional
from modelo.loProcesos import LoProcesos
from config import db, init_app
from flask import Flask

# Router de FastAPI para los procesos
router = APIRouter(
    prefix="/api/logs-procesados",
    tags=["Auditoría de Procesamiento"],
    responses={404: {"description": "No encontrado"}}
)

# Endpoint que devuelve los procesos
@router.get("/")
def consultar_procesos(
    idEmpresa: int = Query(..., description="ID de la empresa a filtrar"),
    dias_atras: int = Query(7, description="Cantidad de días hacia atrás para filtrar"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    limite: int = Query(100, description="Límite de registros", ge=1, le=1000)
):
    try:
        flask_app = Flask(__name__)
        init_app(flask_app)

        with flask_app.app_context():
            fecha_minima = datetime.now() - timedelta(days=dias_atras)
            
            query = db.session.query(LoProcesos).filter(
                LoProcesos.idEmpresa == idEmpresa,
                LoProcesos.fechaInicio >= fecha_minima
            )
            
            if estado:
                query = query.filter(LoProcesos.estado == estado.upper())
            
            procesos = query.order_by(LoProcesos.fechaInicio.desc()).limit(limite).all()
            
            return {
                "meta": {
                    "total_resultados": len(procesos),
                    "fecha_minima": fecha_minima.isoformat(),
                    "parametros": {
                        "idEmpresa": idEmpresa,
                        "dias_atras": dias_atras,
                        "estado": estado,
                        "limite": limite
                    }
                },
                "resultados": [{
                    "id_auditoria": p.idAuditoria,
                    "archivo": p.archivo,
                    "estado": p.estado,
                    "rango_bytes": f"{p.byte_inicio}-{p.byte_fin}" if p.byte_inicio is not None else None,
                    "total_logs": p.totalLogsProcesados,
                    "fecha_inicio": p.fechaInicio.isoformat(),
                    "fecha_fin": p.fechaFin.isoformat() if p.fechaFin else None,
                    "duracion_segundos": (p.fechaFin - p.fechaInicio).total_seconds() if p.fechaFin else None
                } for p in procesos]
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar procesos: {str(e)}"
        )
