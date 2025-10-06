import React, { useEffect, useState } from 'react';
import { Line } from 'react-chartjs-2';
import { Chart, registerables } from 'chart.js';
import ModalLogs from './ModalLogs';
import './TableroLogs.css';
import { useWebSocket } from './WebsocketContext';
import { useLogs } from './LogsContext'; 
import { useModalLogsCache } from './ModalLogsContext';
import { PUERTO_CONFIG } from './puertoConfig';

Chart.register(...registerables);

//Dashboard de las métricas de los servidores
const TableroLogs = () => {

  const [mostrarModal, setMostrarModal] = useState(false);
  const [logsSeleccionados, setLogsSeleccionados] = useState([]);
  const [nivelSeleccionado, setNivelSeleccionado] = useState('');
  const [servidorNombre, setServidorNombre] = useState('');
  const [fechaDesde, setFechaDesde] = useState(new Date().toISOString().split('T')[0]);
  const [fechaHasta, setFechaHasta] = useState(new Date().toISOString().split('T')[0]);
  const [departamentoFiltro, setDepartamentoFiltro] = useState(null);
  const { addMessageHandler } = useWebSocket();
  const { servidores, histogramaData, cargando, error, departamentos, dispatch, lastFetchTimeRef, CACHE_DURATION } = useLogs();
  const { agregarAlCache, obtenerDelCache } = useModalLogsCache();
  const [cargandoModal, setCargandoModal] = useState(false);
  const [procesosActivos, setProcesosActivos] = useState([]);
//Normalizar datos de logs para gráficos
  const parseAndNormalizeLogs = (logs) => {
    if (!logs) return [];
    return Object.entries(logs).map(([nivel, count]) => ({
      nivel,
      count
    }));
  };

//Carga datos iniciales de servidores y departamentos 
const cargarDatos = async () => {
  const now = Date.now();
  if (now - lastFetchTimeRef.current < CACHE_DURATION) {
    console.log('Usando datos en caché, no se recarga');
    dispatch({ type: 'SET_LOADING', payload: false });
    return; 
  }

  try {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });

    const [resServidores, resDepartamentos] = await Promise.all([
      fetch(`http://localhost:${PUERTO_CONFIG.PUERTO}/api/servidores/?idEmpresa=1`),
      fetch(`http://localhost:${PUERTO_CONFIG.PUERTO}/api/departamentos/?idEmpresa=1`)
    ]);

    if (!resServidores.ok || !resDepartamentos.ok) throw new Error('Error al cargar datos');

    const dataServidores = await resServidores.json();
    const dataDepartamentos = await resDepartamentos.json();

//Uso de dispatch para guardar los datos en el contexto
    dispatch({ type: 'SET_SERVIDORES', payload: dataServidores.resultados });
    dispatch({ type: 'SET_DEPARTAMENTOS', payload: dataDepartamentos.data || [] });

    if (dataDepartamentos.data?.length > 0) {
      setDepartamentoFiltro(dataDepartamentos.data[0].idDepartamento);
    }

    const histogramaPromesas = dataServidores.resultados.map(async (servidor) => {
      const res = await fetch(
        `http://localhost:${PUERTO_CONFIG.PUERTO}/api/servidores/${servidor.id_servidor}/evolucion-errores/?idEmpresa=1&agrupacion=por_proceso`
      );
      return res.json();
    });

    const resultadosHistograma = await Promise.all(histogramaPromesas);
    const nuevosDatos = {};
    resultadosHistograma.forEach((result, index) => {
      const datosOrdenados = [...result.datos].sort((a, b) => new Date(a.fecha) - new Date(b.fecha));
      nuevosDatos[dataServidores.resultados[index].id_servidor] = datosOrdenados;
    });

    dispatch({ type: 'SET_HISTOGRAM_DATA', payload: nuevosDatos });
    lastFetchTimeRef.current = now; 

  } catch (err) {
    dispatch({ type: 'SET_ERROR', payload: err.message });
  } finally {
    dispatch({ type: 'SET_LOADING', payload: false });
  }
};

//Cargar procesos activos
const cargarProcesosActivos = async () => {
  try {
    const res = await fetch(`http://localhost:${PUERTO_CONFIG.PUERTO}/api/v1/interpretacion/procesos-activos`);
    if (res.ok) {
      const data = await res.json();
      setProcesosActivos(data);
    }
  } catch (err) {
    console.error('Error cargando procesos activos:', err);
  }
};

//Conexión WebSocket para actualizaciones en tiempo real
useEffect(() => {
  cargarDatos();
  cargarProcesosActivos();
}, []); 

//useEffect separado para el WebSocket
useEffect(() => {
  const unsubscribe = addMessageHandler((message) => {
    console.log("📦 Mensaje WebSocket recibido:", message);

    if (message.eventType === 'dashboard_update') {
      console.log("🔄 Actualizando solo datos del servidor:", message.data.id_servidor);

      fetch(`http://localhost:${PUERTO_CONFIG.PUERTO}/api/servidores/${message.data.id_servidor}/evolucion-errores/?idEmpresa=1`)
        .then(res => res.json())
        .then(data => {
          dispatch({
            type: 'UPDATE_HISTOGRAM_DATA',
            payload: {
              servidorId: message.data.id_servidor,
              datos: data.datos.map(item => ({ 
                ...item,
                logs: item.logs || { ERROR: 0, WARN: 0, FATAL: 0 }
              }))
            }
          });
        });
    }
    else if (message.eventType === 'evolucion_errores_update') {
      dispatch({
        type: 'UPDATE_HISTOGRAM_DATA',
        payload: {
          servidorId: message.data.id_servidor,
          datos: message.data.datos.map(item => ({ 
            ...item,
            logs: item.logs || { ERROR: 0, WARN: 0, FATAL: 0 }
          }))
        }
      });
    }
    else if (message.eventType === 'proceso_completado') {
      console.log("✅ Proceso completado para servidor:", message.data.id_servidor);
      cargarProcesosActivos();
    }
  });

  return unsubscribe;
}, [addMessageHandler]);

//Abre modal con logs filtrados por nivel - CON CACHÉ
const abrirModalConLogs = async (servidor, nivel, procesoId = null) => {
  setMostrarModal(true);
  setCargandoModal(true);
  setNivelSeleccionado(nivel);
  setServidorNombre(servidor.nombreServidor);
  setLogsSeleccionados([]); 
  try {
    //Generar clave única para el caché
    const cacheKey = procesoId 
      ? `${servidor.id_servidor}-${nivel}-${procesoId}`
      : `${servidor.id_servidor}-${nivel}`;

    //Verificar si tenemos datos en caché
    const cachedLogs = obtenerDelCache(cacheKey);
    
    if (cachedLogs) {
      //Usar datos del caché
      console.log('📦 Usando logs desde caché:', cacheKey);
      setLogsSeleccionados(cachedLogs);
      setCargandoModal(false);
      return;
    }

    //Si no hay caché, hacer la petición normal
    console.log('🌐 Fetching logs desde API:', cacheKey);
    let url = `http://localhost:${PUERTO_CONFIG.PUERTO}/api/servidores/${servidor.id_servidor}/logs-filtrados/?idEmpresa=1&nivel=${nivel}`;
    if (procesoId) url += `&idAuditoria=${procesoId}`;

    const resLogs = await fetch(url);
    if (!resLogs.ok) throw new Error('No se pudieron obtener los logs');
    const dataLogs = await resLogs.json();
    const resultados = dataLogs.resultados || [];

    //Guardar en caché para próximas veces
    agregarAlCache(cacheKey, resultados);
    console.log('💾 Datos guardados en caché:', cacheKey);

    setLogsSeleccionados(resultados);
    
  } catch (error) {
    console.error('❌ Error al cargar logs:', error);
    alert('Error al cargar logs');
  } finally {
    setCargandoModal(false);
  }
};

//Configuración para los graficos del histograma
  const opcionesLineChart = (servidorId) => ({
    responsive: true,
    interaction: {
      mode: 'index',
      intersect: false
    },
    scales: {
      y: {
        beginAtZero: true,
        title: { display: true, text: 'Cantidad de logs' }
      },
      x: {
        title: { display: true, text: 'Hora del Proceso' },
        ticks: {
          maxRotation: 90,    
          minRotation: 90,   
          autoSkip: true,    
          padding: 5         
        }
      }
    },
    onClick: (event, elements) => {
      if (elements.length > 0) {
        const chart = event.chart;
        const points = chart.getElementsAtEventForMode(
          event,
          'nearest',
          { intersect: true },
          false
        );

        if (points.length > 0) {
          const clickedElement = points[0];
          const datasetIndex = clickedElement.datasetIndex;
          const niveles = ['FATAL', 'ERROR', 'WARN'];
          const nivel = niveles[datasetIndex];
          const procesoId = histogramaData[servidorId][clickedElement.index]?.procesos?.[0]?.id_auditoria;

          if (procesoId) {
            const servidor = servidores.find(s => s.id_servidor === servidorId);
            abrirModalConLogs(servidor, nivel, procesoId);
          }
        }
      }
    },
    plugins: {
      tooltip: {
        callbacks: {
          label: (context) => `${context.dataset.label}: ${context.raw}`
        }
      }
    }
  });

//Renderizado condicional - Cargando
  if (cargando) {
    return (
      <div className="cargando">
        <div className="spinner"></div>
        <p>Cargando dashboard...</p>
      </div>
    );
  }

//Renderizado condicional - Error 
  if (error) {
    return (
      <div className="error">
        <p>Error al cargar datos: {error}</p>
        <button onClick={cargarDatos}>Reintentar</button>
      </div>
    );
  }

//Componente de resumen de criticidad
const ResumenCriticidad = ({ datosFiltrados }) => {
  if (!datosFiltrados || datosFiltrados.length === 0) {
    return <div className="sin-datos-grafico">
      <p>Sin datos</p>
    </div>;
  }

 //Calcular métricas del nivelError
  let criticos = 0;
  let normales = 0;
  let leves = 0;
  let total_errores = 0;

  datosFiltrados.forEach(proceso => {
    const metricas = proceso.metricas_criticidad;
    if (metricas) {
      criticos += metricas.criticos || 0;
      normales += metricas.normales || 0;
      leves += metricas.leves || 0;
      total_errores += metricas.total_errores || 0;
    }
  });

  //Calcular porcentajes del nivelError
  const porcentaje_critico = total_errores > 0 ? round((criticos / total_errores) * 100, 2) : 0;
  const porcentaje_normal = total_errores > 0 ? round((normales / total_errores) * 100, 2) : 0;
  const porcentaje_leve = total_errores > 0 ? round((leves / total_errores) * 100, 2) : 0;

  // Determinar nivel de alerta general
  let nivel_alerta = "bajo";
  if (porcentaje_critico >= 80) {
    nivel_alerta = "critico";
  } else if (porcentaje_critico >= 30) {
    nivel_alerta = "medio";
  }
  function round(value, decimals) {
    return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
  }

  return (
    <div className={`resumen-servidor ${nivel_alerta}`}>    
      <div className="resumen-metricas">
        <div className="metrica-nivel">
          <span>CRÍTICOS: {criticos} [{porcentaje_critico}%]</span>
          <div className="barra-progreso">
            <div 
              className="barra-critico" 
              style={{ width: `${porcentaje_critico}%` }}
            ></div>
          </div>
        </div>
        
        <div className="metrica-nivel">
          <span>NORMALES: {normales} [{porcentaje_normal}%]</span>
          <div className="barra-progreso">
            <div 
              className="barra-normal" 
              style={{ width: `${porcentaje_normal}%` }}
            ></div>
          </div>
        </div>
        
        <div className="metrica-nivel">
          <span>LEVES: {leves} [{porcentaje_leve}%]</span>
          <div className="barra-progreso">
            <div 
              className="barra-leve" 
              style={{ width: `${porcentaje_leve}%` }}
            ></div>
          </div>
        </div>
      </div>
      
      <div className="resumen-total" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Total: {total_errores} errores</span>
        <span className={`badge-criticidad ${nivel_alerta}`}>
          {nivel_alerta.toUpperCase()}
        </span>
      </div>
    </div>
  );
};

//Panel de los niveles de error
const PanelServidoresCriticos = ({ servidores }) => {
  const servidoresCriticos = servidores.filter(servidor => {
    const datosFiltrados = (histogramaData[servidor.id_servidor] || []).filter(item => {
      const fechaItem = new Date(item.fecha);
      const desde = new Date(fechaDesde + "T00:00:00");
      const hasta = new Date(fechaHasta + "T23:59:59");
      return fechaItem >= desde && fechaItem <= hasta;
    });

    //Calcular total de errores críticos
    const totalCriticos = datosFiltrados.reduce((sum, proceso) => {
      const metricas = proceso.metricas_criticidad;
      return sum + (metricas?.criticos || 0);
    }, 0);
    
    return totalCriticos > 0; 
  });

  if (servidoresCriticos.length === 0) return null;

  return (
    <div className="alerta-ambiente-critico">
      <span className="icono-alerta">⚠️</span>
      <span className="texto-alerta">
        {`${servidoresCriticos.length} servidor${servidoresCriticos.length !== 1 ? 'es' : ''} crítico${servidoresCriticos.length !== 1 ? 's' : ''}`}
      </span>
    </div>
  );
};

//Calcular servidores críticos por ambiente
const calcularCriticosPorAmbiente = () => {
  const criticosPorAmbiente = {};
  
  departamentos.forEach(depto => {
    const servidoresEnAmbiente = servidores.filter(servidor => 
      servidor.id_departamento == depto.idDepartamento
    );
    
    let servidoresCriticosEnAmbiente = 0;
    
    servidoresEnAmbiente.forEach(servidor => {
      const datosFiltrados = (histogramaData[servidor.id_servidor] || []).filter(item => {
        const fechaItem = new Date(item.fecha);
        const desde = new Date(fechaDesde + "T00:00:00");
        const hasta = new Date(fechaHasta + "T23:59:59");
        return fechaItem >= desde && fechaItem <= hasta;
      });
      
      const totalCriticos = datosFiltrados.reduce((sum, proceso) => {
        const metricas = proceso.metricas_criticidad;
        return sum + (metricas?.criticos || 0);
      }, 0);
      
      if (totalCriticos > 0) {
        servidoresCriticosEnAmbiente++;
      }
    });
    
    criticosPorAmbiente[depto.idDepartamento] = servidoresCriticosEnAmbiente;
  });
  
  return criticosPorAmbiente;
};

const criticosPorAmbiente = calcularCriticosPorAmbiente();

  return (
    <div className="tablero-container">
    {/* Contenedor flex para título y botón */}
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <h2>Evolución de Errores por Proceso</h2>
      <button 
        onClick={() => window.location.href = 'http://localhost:3000/'} 
        className="btn-ir-graficos"
      >
        ← Volver al Menú
      </button>
    </div>

        {/* Contenedor de filtros */}
        <div className="contenedor-filtros-unificado">

      <div className="filtros-principales">
        {/* Filtro de departamento */}
        <div className="filtro-item">
          <label>Ambiente:</label>
          <select
            value={departamentoFiltro || ''}
            onChange={(e) => setDepartamentoFiltro(e.target.value || null)}
          >
            <option value="">Todos</option>
            {departamentos.map(depto => {
              const totalCriticos = criticosPorAmbiente[depto.idDepartamento] || 0;
              return (
                <option key={depto.idDepartamento} value={depto.idDepartamento}>
                  {depto.nombre} {totalCriticos > 0 ? `🔴 ${totalCriticos}` : '🟢'}
                </option>
              );
            })}
          </select>
        </div>
        {/* Filtro de fecha */}
        <div className="filtro-item">
          <label>Desde:</label>
          <input
            type="date"
            value={fechaDesde}
            onChange={(e) => setFechaDesde(e.target.value)}
          />
        </div>
        <div className="filtro-item">
          <label>Hasta:</label>
          <input
            type="date"
            value={fechaHasta}
            onChange={(e) => setFechaHasta(e.target.value)}
          />
        </div>
      </div>
      
      {/* PANEL DE SERVIDORES CRÍTICOS */}
      <PanelServidoresCriticos servidores={servidores} />
    </div>

    {/* Renderizado de tarjetas de servidor */}
    <div className="servidores-grid">
      {servidores
        .filter(servidor => !departamentoFiltro || servidor.id_departamento == departamentoFiltro)
        .map((servidor) => {
          const datosFiltrados = (histogramaData[servidor.id_servidor] || []).filter(item => {
            const fechaItem = new Date(item.fecha);
            const desde = new Date(fechaDesde + "T00:00:00");
            const hasta = new Date(fechaHasta + "T23:59:59");
            return fechaItem >= desde && fechaItem <= hasta;
          });

          const datos = datosFiltrados.slice().sort((a, b) => new Date(a.fecha) - new Date(b.fecha));
          const labels = datos.map(item => {
            const fecha = new Date(item.fecha);
            return fecha.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
          });

          const fatalData = datos.map(item => {
            const normalizedLogs = parseAndNormalizeLogs(item.logs);
            return normalizedLogs
              .filter(log => log.nivel === 'FATAL')
              .reduce((sum, log) => sum + (log.count || 1), 0);
          });

          const errorData = datos.map(item => {
            const normalizedLogs = parseAndNormalizeLogs(item.logs);
            return normalizedLogs
              .filter(log => log.nivel === 'ERROR')
              .reduce((sum, log) => sum + (log.count || 1), 0);
          });

          const warnData = datos.map(item => {
            const normalizedLogs = parseAndNormalizeLogs(item.logs);
            return normalizedLogs
              .filter(log => log.nivel === 'WARN')
              .reduce((sum, log) => sum + (log.count || 1), 0);
          });

          const chartData = {
            labels,
            datasets: [
              {
                label: 'FATAL',
                data: fatalData,
                borderColor: '#D32F2F',
                backgroundColor: 'rgba(211, 47, 47, 0.1)',
                tension: 0.3,
                borderWidth: 2
              },
              {
                label: 'ERROR',
                data: errorData,
                borderColor: '#1976D2',
                backgroundColor: 'rgba(255, 99, 132, 0.1)',
                tension: 0.3,
                borderWidth: 2
              },
              {
                label: 'WARN',
                data: warnData,
                borderColor: '#FFCE56',
                backgroundColor: 'rgba(255, 206, 86, 0.1)',
                tension: 0.3,
                borderWidth: 2
              }
            ]
          };

          return (
            <div key={servidor.id_servidor} className="servidor-card">
              <h3>{servidor.nombreServidor}</h3>
              <p className="nombre-servidor" style={{ fontWeight: 'bold', color: '#2c3e50', margin: '4px 0', fontSize: '14px' }}>
                {servidor.nombre} 
              </p>
              <p className="ruta-servidor">{servidor.ruta}</p>

              <div className="estado-servidor">
                <div className="estado-linea">
                  <span className={`badge ${procesosActivos.some(p => p.id_servidor === servidor.id_servidor) ? 'activo' : 'inactivo'}`}>
                    {procesosActivos.some(p => p.id_servidor === servidor.id_servidor) ? 'ACTIVO' : 'INACTIVO'}
                  </span>
                </div>
                <div className="procesos-linea">
                  <span>Procesos: {datos.length}</span>
                </div>
              </div>
              {/* Resumen de criticidad */}
              <div className="resumen-criticidad-container">
                <ResumenCriticidad datosFiltrados={datosFiltrados} />
              </div>
               {/* Gráfico y métricas por servidor */}
               <div className="grafica-container" style={{ height: '320px' }}>
                {!histogramaData[servidor.id_servidor] ? (
                  <div className="cargando-grafico">
                    <div className="spinner-pequeno"></div>
                    <p>Cargando gráfico...</p>
                  </div>
                ) : datos.length === 0 ? (
                  <div className="sin-datos-grafico">
                    <p>No hay datos en el período seleccionado</p>
                  </div>
                ) : (
                  <Line
                    data={chartData}
                    options={{
                      ...opcionesLineChart(servidor.id_servidor),
                      maintainAspectRatio: false
                    }}
                  />
                )}
              </div>
               {/* Métricas y botones */}
              <div className="metricas-rapidas">
                <div className="metrica">
                  <span>Total FATAL:</span>
                  <strong>{fatalData.reduce((a, b) => a + b, 0)}</strong>
                </div>
                <div className="metrica">
                  <span>Total ERROR:</span>
                  <strong>{errorData.reduce((a, b) => a + b, 0)}</strong>
                </div>
                <div className="metrica">
                  <span>Total WARN:</span>
                  <strong>{warnData.reduce((a, b) => a + b, 0)}</strong>
                </div>
              </div>
                <div className="botones-errores">
                  <button 
                    onClick={() => abrirModalConLogs(servidor, 'FATAL')}
                    className="boton-comun boton-fatal"
                  >
                    Ver FATAL 
                  </button>
                  <button 
                    onClick={() => abrirModalConLogs(servidor, 'ERROR')}
                    className="boton-comun boton-error"
                  >
                    Ver ERROR 
                  </button>
                  <button 
                    onClick={() => abrirModalConLogs(servidor, 'WARN')}
                    className="boton-comun boton-warn"
                  >
                    Ver WARN 
                  </button>
                </div>
            </div>
          );
        })}
        {/* Mensaje cuando no hay servidores en el ambiente filtrado */}
  {servidores.filter(servidor => !departamentoFiltro || servidor.id_departamento == departamentoFiltro).length === 0 && (
    <div className="mensaje-sin-servidores">
      <p>Este ambiente no tiene servidores registrados</p>
    </div>
  )}
</div>

    {mostrarModal && (
      <ModalLogs
        nivel={nivelSeleccionado}
        logs={logsSeleccionados}
        onClose={() => setMostrarModal(false)}
        servidorNombre={servidorNombre}
        fechaDesde={fechaDesde}       
        fechaHasta={fechaHasta} 
        cargando={cargandoModal}   
      />
    )}
  </div>
);
};

export default TableroLogs;
