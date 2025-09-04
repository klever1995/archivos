from fastapi import APIRouter, Query, HTTPException
from datetime import datetime
from modelo.loDepartamentos import loDepartamentos
from modelo.loServidores import loServidores
from config import db, init_app
from flask import Flask
from typing import Optional

# Configuración de Flask para el contexto
flask_app = Flask(__name__)
init_app(flask_app)

# Router de FastAPI para departamentos
router = APIRouter(
    prefix="/api/departamentos",
    tags=["Departamentos"],
    responses={404: {"description": "No encontrado"}}
)

#Endpoint que obtiniene los departamentos
@router.get("/")
def listar_departamentos(
    idEmpresa: int = Query(..., description="ID de la empresa"),
    nombre: Optional[str] = Query(None, description="Filtrar por nombre (parcial)"),
    limite: int = Query(100, ge=1, le=1000)
):
    try:
        with flask_app.app_context():
            query = db.session.query(loDepartamentos).filter(
                loDepartamentos.idEmpresa == idEmpresa
            )

            if nombre:
                query = query.filter(loDepartamentos.nombre.ilike(f"%{nombre}%"))

            departamentos = query.order_by(
                loDepartamentos.nombre
            ).limit(limite).all()

            return {
                "meta": {
                    "total": len(departamentos),
                    "filtros": {
                        "idEmpresa": idEmpresa,
                        "nombre": nombre,
                        "limite": limite
                    }
                },
                "data": [{
                    "idDepartamento": d.idDepartamento,
                    "nombre": d.nombre,
                    "fechaRegistro": d.fechaRegistro.isoformat(),
                    "totalServidores": db.session.query(loServidores)
                        .filter(loServidores.idDepartamento == d.idDepartamento)
                        .count()
                } for d in departamentos]
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al listar departamentos: {str(e)}"
        )

#Endpoint que crea un departamento
@router.post("/")
def crear_departamento(datos: dict):
    try:
        with flask_app.app_context():

            if not datos.get("nombre"):
                raise HTTPException(status_code=400, detail="Nombre es requerido")

            existe = db.session.query(loDepartamentos).filter(
                loDepartamentos.idEmpresa == datos["idEmpresa"],
                loDepartamentos.nombre == datos["nombre"]
            ).first()
            
            if existe:
                raise HTTPException(
                    status_code=400,
                    detail="Ya existe un departamento con este nombre en la empresa"
                )

            nuevo = loDepartamentos(
                idEmpresa=datos["idEmpresa"],
                nombre=datos["nombre"]
            )
            
            db.session.add(nuevo)
            db.session.commit()

            return {
                "message": "Departamento creado exitosamente",
                "idDepartamento": nuevo.idDepartamento
            }

    except Exception as e:
        db.session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear departamento: {str(e)}"
        )

#Endpoint que borra un departamento
@router.delete("/{idDepartamento}")
def eliminar_departamento(idDepartamento: int):
    try:
        with flask_app.app_context():
            # Verificar si tiene servidores asociados
            servidores = db.session.query(loServidores).filter(
                loServidores.idDepartamento == idDepartamento
            ).count()

            if servidores > 0:
                raise HTTPException(
                    status_code=400,
                    detail="No se puede eliminar: tiene servidores asignados"
                )

            departamento = db.session.query(loDepartamentos).get(idDepartamento)
            if not departamento:
                raise HTTPException(status_code=404, detail="Departamento no encontrado")

            db.session.delete(departamento)
            db.session.commit()

            return {"message": f"Departamento {idDepartamento} eliminado"}

    except HTTPException:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar departamento: {str(e)}"
        )
    
# Endpoint que actualiza un departamento
@router.put("/{idDepartamento}")
def actualizar_departamento(idDepartamento: int, datos: dict):
    try:
        with flask_app.app_context():

            departamento = db.session.query(loDepartamentos).get(idDepartamento)
            if not departamento:
                raise HTTPException(status_code=404, detail="Departamento no encontrado")

            if not datos.get("nombre"):
                raise HTTPException(status_code=400, detail="El nombre es requerido")

            nuevo_nombre = datos["nombre"].strip()

            existe = db.session.query(loDepartamentos).filter(
                loDepartamentos.idEmpresa == departamento.idEmpresa,
                loDepartamentos.nombre == nuevo_nombre,
                loDepartamentos.idDepartamento != idDepartamento 
            ).first()
            
            if existe:
                raise HTTPException(
                    status_code=400,
                    detail="Ya existe otro departamento con este nombre en la empresa"
                )

            departamento.nombre = nuevo_nombre
            db.session.commit()

            return {
                "message": "Departamento actualizado exitosamente",
                "idDepartamento": departamento.idDepartamento
            }

    except HTTPException:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar departamento: {str(e)}"
        )
