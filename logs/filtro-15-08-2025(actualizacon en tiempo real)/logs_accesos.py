from fastapi import APIRouter, Query, HTTPException
from typing import Optional  # ¡Este import faltaba!
from datetime import datetime
from modelo.loAccesosremotos import loAccesosremotos
from modelo.loServidores import loServidores
from config import db, init_app
from flask import Flask

flask_app = Flask(__name__)
init_app(flask_app)

router = APIRouter(
    prefix="/api/accesos-remotos",
    tags=["Accesos Remotos"],
    responses={404: {"description": "No encontrado"}}
)

@router.get("/")
def consultar_accesos(
    idEmpresa: int = Query(..., description="ID de la empresa"),
    hostname: Optional[str] = Query(None, description="Filtrar por hostname exacto"),
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo/inactivo"),
    limite: int = Query(100, ge=1, le=1000)
):
    try:
        with flask_app.app_context():
            query = db.session.query(loAccesosremotos).filter(
                loAccesosremotos.idEmpresa == idEmpresa
            )

            if hostname:
                query = query.filter(loAccesosremotos.hostname == hostname)
            if activo is not None:
                query = query.filter(loAccesosremotos.activo == activo)

            accesos = query.order_by(
                loAccesosremotos.fechaRegistro.desc()
            ).limit(limite).all()

            return {
                "meta": {
                    "total": len(accesos),
                    "filtros": {
                        "idEmpresa": idEmpresa,
                        "hostname": hostname,
                        "activo": activo,
                        "limite": limite
                    }
                },
                "data": [{
                    "idAcceso": a.idAcceso,
                    "usuario": a.usuario,
                    "hostname": a.hostname,
                    "activo": a.activo,
                    "fechaRegistro": a.fechaRegistro.isoformat()
                } for a in accesos]
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en consulta: {str(e)}"
        )

@router.post("/", status_code=201)
def crear_acceso(acceso: dict):  # O usa un modelo Pydantic si lo prefieres

    try:
        with flask_app.app_context():
            # Validación básica de campos requeridos
            required_fields = ["idEmpresa", "usuario", "contrasena", "hostname"]
            for field in required_fields:
                if field not in acceso:
                    raise HTTPException(status_code=400, detail=f"Campo requerido: {field}")

            nuevo_acceso = loAccesosremotos(
                idEmpresa=acceso["idEmpresa"],
                usuario=acceso["usuario"],
                contrasena=acceso["contrasena"],
                hostname=acceso["hostname"],
                activo=acceso.get("activo", True)  # Default a True si no se envía
            )
            
            db.session.add(nuevo_acceso)
            db.session.commit()

            return {
                "message": "Acceso remoto creado exitosamente",
                "idAcceso": nuevo_acceso.idAcceso
            }

    except Exception as e:
        db.session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear acceso: {str(e)}"
        )

@router.delete("/{idAcceso}")
def eliminar_acceso(idAcceso: int):
    ctx = flask_app.app_context()
    ctx.push()
    try:
        servidores_vinculados = db.session.query(loServidores).filter(
            loServidores.idAccesoRemoto == idAcceso
        ).count()

        if servidores_vinculados > 0:
            raise HTTPException(
                status_code=400,
                detail="No se puede eliminar: hay servidores vinculados a este acceso"
            )

        acceso = db.session.query(loAccesosremotos).get(idAcceso)
        if not acceso:
            raise HTTPException(status_code=404, detail="Acceso no encontrado")

        db.session.delete(acceso)
        db.session.commit()

        return {"message": f"Acceso {idAcceso} eliminado correctamente"}

    except HTTPException:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar acceso: {str(e)}"
        )
    finally:
        ctx.pop()  # Esto asegura que el contexto se cierra correctamente

@router.get("/contar-servidores")  # Nueva ruta única
def contar_servidores(
    idAccesoRemoto: int = Query(..., alias="idAccesoRemoto") 
):
    try:
        with flask_app.app_context():
            count = db.session.query(loServidores).filter(
                loServidores.idAccesoRemoto == idAccesoRemoto
            ).count()
            
            return {"total": count}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al contar servidores: {str(e)}"
        )

@router.get("/hostnames")
def obtener_hostnames(
    idEmpresa: int = Query(..., description="ID de la empresa"),
    solo_activos: bool = Query(True, description="Filtrar solo accesos activos")
):
    """
    Devuelve lista de hostnames para dropdown en frontend
    """
    try:
        with flask_app.app_context():
            query = db.session.query(
                loAccesosremotos.idAcceso,
                loAccesosremotos.hostname
            ).filter(
                loAccesosremotos.idEmpresa == idEmpresa
            )

            if solo_activos:
                query = query.filter(loAccesosremotos.activo == True)

            resultados = query.order_by(loAccesosremotos.hostname).all()

            return {
                "data": [{
                    "idAcceso": r.idAcceso,
                    "hostname": r.hostname
                } for r in resultados]
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener hostnames: {str(e)}"
        )
