def generar_reporte_logs(bloques: list, idServidor: int, idAuditoria: int) -> dict:
    """Procesa bloques de logs en paralelo y genera reporte."""
    reporte = defaultdict(lambda: {
        'count': 0,
        'lineas': [],
        'nivel': '',
        'categoria': '',
        'componente': '',
        'hilo': '',
        'mensaje': '',
        'mensaje_normalizado': '',
        'hash': ''
    })

    def _procesar_chunk(chunk: list, reporte_local: dict):
        for bloque in chunk:
            lineas_bloque = bloque['contenido'].split('\n')
            _procesar_bloque_optimizado(lineas_bloque, str(bloque['linea_inicio']), reporte_local)

    # Procesamiento paralelo por chunks de 2000 bloques
    chunk_size = 2000
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for i in range(0, len(bloques), chunk_size):
            chunk = bloques[i:i + chunk_size]
            futures.append(executor.submit(_procesar_chunk, chunk, reporte))
        
        for future in futures:
            future.result()

    # Inserción a BD (original)
    total_insertados = insertar_logs_a_bd(reporte, idServidor, idAuditoria)
    logger.info(f"✅ Reporte generado. Logs únicos: {len(reporte)} | Insertados: {total_insertados}")
    return reporte


---------------------------------------------------------------------------------------


def _procesar_bloque_optimizado(bloque_actual: list, linea_inicio: str, reporte: dict):
    """Versión optimizada de procesar_bloque con hash MD5 para comparación rápida."""
    mensaje_completo = "".join(bloque_actual).strip()
    nivel = extraer_nivel(mensaje_completo)
    
    # Normalización y hash
    mensaje_normalizado = re.sub(r'^\d{2}:\d{2}:\d{2},\d{3}\s*', '', mensaje_completo).strip()
    mensaje_normalizado = re.sub(r'\([^)]+\)', '(THREAD)', mensaje_normalizado)
    mensaje_normalizado = re.sub(r'\d+', '[NUM]', mensaje_normalizado).lower()
    hash_mensaje = hashlib.md5(mensaje_normalizado.encode()).hexdigest()

    # Búsqueda eficiente por hash
    clave_existente = next(
        (k for k in reporte if k[0] == nivel and reporte[k]['hash'] == hash_mensaje),
        None
    )

    if not clave_existente:
        clave = (
            nivel,
            categorizar_mensaje(mensaje_completo),
            mensaje_normalizado
        )
        reporte[clave].update({
            'hash': hash_mensaje,
            'componente': extraer_componente(mensaje_completo),
            'hilo': extraer_hilo(mensaje_completo),
            'mensaje': mensaje_completo
        })
    else:
        clave = clave_existente

    # Actualización atómica
    reporte[clave]['count'] += 1
    reporte[clave]['lineas'].append(linea_inicio)

-------------------------------------------------------------------------------

def insertar_logs_a_bd(reporte: dict, idServidor: int, idAuditoria: int) -> int:
    """Inserción masiva optimizada con filtrado temprano."""
    niveles_importantes = {'ERROR', 'FATAL', 'WARN'}
    fecha_actual = datetime.now()
    logs_nuevos = []
    logs_a_insertar = []

    try:
        with flask_app.app_context():
            # Filtrado rápido y preparación de datos
            for (nivel, categoria, _), datos in reporte.items():
                if nivel not in niveles_importantes:
                    continue

                mensaje_normalizado = datos['mensaje_normalizado']
                hash_error = datos['hash']  # Usamos el hash precalculado

                # Verificar error conocido (consulta optimizada)
                error_conocido = db.session.query(
                    loErrorconocido.respuestaopenai
                ).filter(
                    loErrorconocido.hasherror == hash_error,
                    loErrorconocido.nivel == nivel
                ).first()

                if not error_conocido and nivel in {'ERROR', 'FATAL'}:
                    logs_nuevos.append({
                        'hash': hash_error,
                        'mensaje': mensaje_normalizado,
                        'nivel': nivel
                    })

                logs_a_insertar.append({
                    'idEmpresa': 1,
                    'idServidor': idServidor,
                    'idAuditoria': idAuditoria,
                    'operador': 0,
                    'mensaje': mensaje_normalizado,
                    'nivel': nivel,
                    'componente': datos['componente'],
                    'hilo': datos['hilo'][:200] if datos['hilo'] else None,
                    'categoria': categoria,
                    'estado': 'ACTIVO',
                    'lineas': datos['lineas'],
                    'ocurrencias': datos['count'],
                    'respuestaOpenai': error_conocido.respuestaopenai if error_conocido else None,
                    'fechaCreacion': fecha_actual
                })

            # Inserción masiva en paralelo
            if logs_nuevos:
                with ThreadPoolExecutor(max_workers=3) as executor:
                    respuestas = list(executor.map(
                        lambda log: Consulta_ia_openai().interpretar_logs(log['mensaje'][:2000]),
                        logs_nuevos
                    ))

                # Actualizar respuestas OpenAI
                db.session.bulk_insert_mappings(loErrorconocido, [{
                    'hasherror': log['hash'],
                    'mensajenormalizado': log['mensaje'],
                    'nivel': log['nivel'],
                    'respuestaopenai': respuesta,
                    'fechaCreacion': fecha_actual
                } for log, respuesta in zip(logs_nuevos, respuestas)])

            db.session.bulk_insert_mappings(loLogs, logs_a_insertar)
            db.session.commit()
            return len(logs_a_insertar)

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error en inserción: {str(e)}")
        return 0
