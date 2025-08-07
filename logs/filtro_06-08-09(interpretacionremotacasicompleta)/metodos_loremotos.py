def interpretar_logs_remotos(id_servidor: int, batch_size: int = 100) -> bool:
    """Interpretación remota con IA y guardado de resultados por servidor."""
    with app.app_context():
        try:
            # 1. Validar servidor
            servidor = db.session.get(loServidores, id_servidor)
            if not servidor or not servidor.esRemoto:
                raise ValueError("ID de servidor remoto inválido")

            # 2. Obtener último proceso de filtrado
            ultimo_proceso = db.session.query(LoProcesos.idAuditoria)\
                .filter_by(idServidor=id_servidor, tipoProceso='FILTRADOREMOTO')\
                .order_by(LoProcesos.idAuditoria.desc())\
                .first()
            
            if not ultimo_proceso:
                raise ValueError("No existe proceso FILTRADOREMOTO para este servidor")

            # 3. Crear nueva interpretación
            interpretacion = loInterpretacionremota(
                idProcesoFiltrado=ultimo_proceso.idAuditoria,
                idServidor=id_servidor,
                fechaInicio=datetime.now(),
                estado='PROCESANDO',
                ultimoLogProcesado=0,
                totalLogsInterpretados=0
            )
            db.session.add(interpretacion)
            db.session.flush()

            # 4. Obtener logs nuevos
            logs = db.session.query(loLogsremotos).filter(
                loLogsremotos.idServidor == id_servidor,
                loLogsremotos.idLogRemoto > interpretacion.ultimoLogProcesado
            ).order_by(loLogsremotos.idLogRemoto).limit(batch_size).all()

            if not logs:
                interpretacion.estado = 'COMPLETADO'
                interpretacion.fechaFin = datetime.now()
                db.session.commit()
                logger.info(f"No hay logs nuevos en servidor {id_servidor}.")
                return True

            # 5. Procesamiento de logs
            logs_nuevos = []
            logs_a_guardar = []
            fecha_actual = datetime.now()
            consulta_ia = Consulta_ia_openai()

            for log in logs:
                mensaje_normalizado = re.sub(r'\d+', '[NUM]', log.mensaje.lower())
                hash_error = hashlib.sha256(mensaje_normalizado.encode()).hexdigest()

                error_conocido = db.session.query(loErrorconocido).filter_by(
                    hasherror=hash_error,
                    nivel=log.nivel
                ).first()

                if not error_conocido and log.nivel in {'ERROR', 'FATAL'}:
                    logs_nuevos.append({
                        'log': log,
                        'mensaje_normalizado': log.mensaje[:2000],
                        'hash_error': hash_error
                    })
                    logger.debug(f"📡 Log {log.idLogRemoto} marcado para consulta IA (nivel: {log.nivel})")

                logs_a_guardar.append({
                    'log': log,
                    'hash_error': hash_error,
                    'error_conocido': error_conocido
                })

            # 6. Consulta IA para logs nuevos
            respuestas_ia = []
            if logs_nuevos:
                try:
                    logger.info(f"🔎 Enviando {len(logs_nuevos)} consultas a IA...")
                    
                    for log in logs_nuevos:
                        try:
                            inicio = time.time()
                            respuesta = consulta_ia.interpretar_logs(log['mensaje_normalizado'])
                            duracion = time.time() - inicio
                            
                            if not respuesta or not isinstance(respuesta, str):
                                logger.error(f"🛑 Respuesta inválida de IA para log {log['log'].idLogRemoto}")
                                continue
                            
                            logger.info(f"✅ IA respondió en {duracion:.2f}s - Log {log['log'].idLogRemoto}")
                            respuestas_ia.append((log['hash_error'], respuesta))
                            
                            nuevo_error = loErrorconocido(
                                hasherror=log['hash_error'],
                                mensajenormalizado=log['mensaje_normalizado'],
                                nivel=log['log'].nivel,
                                respuestaopenai=respuesta,
                                fechaprimeraocurrencia=fecha_actual,
                                fechaultimaactualizacion=fecha_actual
                            )
                            db.session.add(nuevo_error)
                            
                        except Exception as e:
                            logger.error(f"❌ Fallo en log {log['log'].idLogRemoto}: {type(e).__name__} - {str(e)}")
                            continue

                    db.session.commit()

                except Exception as e:
                    logger.error(f"Error al consultar IA: {str(e)}")
                    db.session.rollback()

            # 7. Guardar en loLogs (CORRECCIÓN APLICADA AQUÍ)
            logs_insertar = []
            for item in logs_a_guardar:
                respuesta = None
                
                if item['error_conocido']:
                    respuesta = item['error_conocido'].respuestaopenai
                    logger.debug(f"♻️ Usando caché para log {item['log'].idLogRemoto}")
                else:
                    for hash_err, resp in respuestas_ia:
                        if hash_err == item['hash_error']:
                            respuesta = resp
                            break
                
                if respuesta:
                    logs_insertar.append(loLogs(
                                                idEmpresa=servidor.idEmpresa,
                        idServidor=id_servidor,
                        idAuditoria=item['log'].idAuditoria,
                        operador=0,
                        nivel=item['log'].nivel,
                        componente=item['log'].componente,
                        hilo=item['log'].hilo,
                        mensaje=item['log'].mensaje,
                        categoria=item['log'].categoria,
                        ocurrencias=item['log'].ocurrencias,
                        lineas=item['log'].lineas,
                        respuestaOpenai=respuesta,
                        fechaCreacion=fecha_actual

                    ))
                    interpretacion.ultimoLogProcesado = item['log'].idLogRemoto  # Mantener esto

            # CONTADOR CORREGIDO (ASIGNACIÓN ÚNICA)
            interpretacion.totalLogsInterpretados = len(logs_insertar)

            if logs_insertar:
                db.session.bulk_save_objects(logs_insertar)
                logger.info(f"💽 Guardados {len(logs_insertar)} logs en BD")
            
            # 8. Actualizar estado final
            interpretacion.estado = 'COMPLETADO' if len(logs) < batch_size else 'PROCESANDO'
            interpretacion.fechaFin = datetime.now() if interpretacion.estado == 'COMPLETADO' else None
            db.session.commit()
            
            logger.info(f"📊 Interpretación completada. Logs procesados: {len(logs_insertar)}")
            return True

        except Exception as e:
            logger.error(f"💥 Error en servidor {id_servidor}: {str(e)}", exc_info=True)
            db.session.rollback()
            if 'interpretacion' in locals():
                interpretacion.estado = 'FALLIDO'
                db.session.commit()
            return False
