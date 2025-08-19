import React, { useEffect, useState } from 'react'; // Elimina useState, ya no se necesita
import { Line } from 'react-chartjs-2';
import { Chart, registerables } from 'chart.js';
import ModalLogs from './ModalLogs';
import './TableroLogs.css';
import { useWebSocket } from './WebsocketContext';
import { useLogs } from './LogsContext'; // 👈 IMPORTA TU CONTEXTO AQUÍ

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
  // (CÓDIGO NUEVO - AGREGA ESTA LÍNEA)
const { servidores, histogramaData, cargando, error, departamentos, dispatch, lastFetchTimeRef, CACHE_DURATION } = useLogs();

// Normaliza datos de logs para gráficos
  const parseAndNormalizeLogs = (logs) => {
    if (!logs) return [];
    return Object.entries(logs).map(([nivel, count]) => ({
      nivel,
      count
    }));
  };

// Carga datos iniciales de servidores y departamentos 
  // (CÓDIGO NUEVO - REEMPLAZA TU FUNCIÓN cargarDatos)
const cargarDatos = async () => {
  // 👇 Revisa la caché antes de hacer fetch
  const now = Date.now();
  if (now - lastFetchTimeRef.current < CACHE_DURATION) {
    console.log('Usando datos en caché, no se recarga');
    dispatch({ type: 'SET_LOADING', payload: false }); // Para quitar el loading
    return; // Sale de la función sin hacer fetch
  }

  try {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });

    const [resServidores, resDepartamentos] = await Promise.all([
      fetch('http://localhost:8000/api/servidores/?idEmpresa=1'),
      fetch('http://localhost:8000/api/departamentos/?idEmpresa=1')
    ]);

    if (!resServidores.ok || !resDepartamentos.ok) throw new Error('Error al cargar datos');

    const dataServidores = await resServidores.json();
    const dataDepartamentos = await resDepartamentos.json();

    // 👇 Usa dispatch para guardar los datos en el contexto
    dispatch({ type: 'SET_SERVIDORES', payload: dataServidores.resultados });
    dispatch({ type: 'SET_DEPARTAMENTOS', payload: dataDepartamentos.data || [] });

    if (dataDepartamentos.data?.length > 0) {
      setDepartamentoFiltro(dataDepartamentos.data[0].idDepartamento);
    }

    const histogramaPromesas = dataServidores.resultados.map(async (servidor) => {
      const res = await fetch(
        `http://localhost:8000/api/servidores/${servidor.id_servidor}/evolucion-errores/?idEmpresa=1&agrupacion=por_proceso`
      );
      return res.json();
    });

    const resultadosHistograma = await Promise.all(histogramaPromesas);
    const nuevosDatos = {};
    resultadosHistograma.forEach((result, index) => {
      const datosOrdenados = [...result.datos].sort((a, b) => new Date(a.fecha) - new Date(b.fecha));
      nuevosDatos[dataServidores.resultados[index].id_servidor] = datosOrdenados;
    });

    // 👇 Guarda los datos del histograma en el contexto también
    dispatch({ type: 'SET_HISTOGRAM_DATA', payload: nuevosDatos });
    lastFetchTimeRef.current = now; // 👈 Actualiza el timestamp de la última carga

  } catch (err) {
    dispatch({ type: 'SET_ERROR', payload: err.message });
  } finally {
    dispatch({ type: 'SET_LOADING', payload: false });
  }
};

// Conexión WebSocket para actualizaciones en tiempo real
useEffect(() => {
  cargarDatos();
}, []); // 👈 Se ejecuta solo al montar el componente

// useEffect separado para el WebSocket
useEffect(() => {
  const unsubscribe = addMessageHandler((message) => {
    console.log("📦 Mensaje WebSocket recibido:", message);

    if (message.eventType === 'dashboard_update') {
      console.log("🔄 Actualizando solo datos del servidor:", message.data.id_servidor);

      fetch(`http://localhost:8000/api/servidores/${message.data.id_servidor}/evolucion-errores/?idEmpresa=1`)
        .then(res => res.json())
        .then(data => {
          dispatch({
            type: 'UPDATE_HISTOGRAM_DATA',
            payload: {
              servidorId: message.data.id_servidor,
              datos: data.datos.map(item => ({ // 👈 'data' viene de .then(data => ...)
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
          datos: message.data.datos.map(item => ({ // 👈 message.data.datos
            ...item,
            logs: item.logs || { ERROR: 0, WARN: 0, FATAL: 0 }
          }))
        }
      });
    }
    else if (message.eventType === 'proceso_completado') {
      console.log("✅ Proceso completado para servidor:", message.data.id_servidor);
    }
  });

  return unsubscribe;
}, [addMessageHandler]);

// Abre modal con logs filtrados por nivel
  const abrirModalConLogs = async (servidor, nivel, procesoId = null) => {
    try {
      let url = `http://localhost:8000/api/servidores/${servidor.id_servidor}/logs-filtrados/?idEmpresa=1&nivel=${nivel}`;
      if (procesoId) url += `&idAuditoria=${procesoId}`;

      const resLogs = await fetch(url);
      if (!resLogs.ok) throw new Error('No se pudieron obtener los logs');
      const dataLogs = await resLogs.json();

      setLogsSeleccionados(dataLogs.resultados || []);
      setNivelSeleccionado(nivel);
      setServidorNombre(servidor.nombreServidor);
      setMostrarModal(true);
    } catch (error) {
      console.error(error);
      alert('Error al cargar logs');
    }
  };

// Configuración personalizada para gráficos de líneas
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
        title: { display: true, text: 'Procesos' }
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

// Renderizado condicional - Cargando
  if (cargando) {
    return (
      <div className="cargando">
        <div className="spinner"></div>
        <p>Cargando dashboard...</p>
      </div>
    );
  }

// Renderizado condicional - Error 
  if (error) {
    return (
      <div className="error">
        <p>Error al cargar datos: {error}</p>
        <button onClick={cargarDatos}>Reintentar</button>
      </div>
    );
  }

  return (
  <div className="tablero-container">
    <h2>Evolución de Errores por Proceso</h2>

    {/* Contenedor de filtros */}
    <div className="contenedor-filtros-unificado">
      {/* Filtro de departamento */}
      <div className="filtro-item">
        <label>Departamento:</label>
        <select
          value={departamentoFiltro || ''}
          onChange={(e) => setDepartamentoFiltro(e.target.value || null)}
        >
          <option value="">Todos</option>
          {departamentos.map(depto => (
            <option key={depto.idDepartamento} value={depto.idDepartamento}>
              {depto.nombre}
            </option>
          ))}
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
          const labels = datos.map((_, index) => ` ${index + 1}`);

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
              <p className="ruta-servidor">{servidor.ruta}</p>

              <div className="estado-servidor">
                <span className={`badge ${servidor.activo ? 'activo' : 'inactivo'}`}>
                  {servidor.activo ? 'ACTIVO' : 'INACTIVO'}
                </span>
                <span>Procesos: {datos.length}</span>
              </div>
               {/* Gráfico y métricas por servidor */}
              <div className="grafica-container" style={{ height: '320px' }}>
                <Line
                  data={chartData}
                  options={{
                    ...opcionesLineChart(servidor.id_servidor),
                    maintainAspectRatio: false
                  }}
                />
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
    </div>

    {mostrarModal && (
      <ModalLogs
        nivel={nivelSeleccionado}
        logs={logsSeleccionados}
        onClose={() => setMostrarModal(false)}
        servidorNombre={servidorNombre}
      />
    )}
  </div>
);
};

export default TableroLogs;
