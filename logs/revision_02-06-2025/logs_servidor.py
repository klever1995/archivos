from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel  # Para modelos de respuesta
from modelo.loServidores import loServidores
from config import db, init_app
from flask import Flask

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
