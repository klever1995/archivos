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
                LoProcesos.fechaInicio >= fecha_limite,
                LoProcesos.totalLogsProcesados > 0
            ).order_by(LoProcesos.fechaInicio.desc()).all()

            datos = []
            for proceso in procesos:
                logs_por_nivel = db.session.query(
                    loLogs.nivel,
                    db.func.count(loLogs.idLogAplicacion)
                ).filter(
                    loLogs.idAuditoria == proceso.idAuditoria
                ).group_by(loLogs.nivel).all()

                if logs_por_nivel:
                    datos.append({
                        "fecha": proceso.fechaInicio.isoformat(),
                        "procesos": [{
                            "id_auditoria": proceso.idAuditoria,
                            "estado": proceso.estado,
                            "total_logs": proceso.totalLogsProcesados
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
