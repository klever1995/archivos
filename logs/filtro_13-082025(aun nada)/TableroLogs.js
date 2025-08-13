import React, { useState, useEffect, useRef } from 'react';
import { Line } from 'react-chartjs-2';
import { Chart, registerables } from 'chart.js';
import ModalLogs from './ModalLogs';
import './TableroLogs.css';

Chart.register(...registerables);

const TableroLogs = () => {
  const [servidores, setServidores] = useState([]);
  const [histogramaData, setHistogramaData] = useState({});
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [logsSeleccionados, setLogsSeleccionados] = useState([]);
  const [nivelSeleccionado, setNivelSeleccionado] = useState('');
  const [servidorNombre, setServidorNombre] = useState('');
  const websocket = useRef(null);
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');

  // Función auxiliar mejorada para manejar logs como objeto o array
  const parseAndNormalizeLogs = (logs) => {
    try {
      let parsedLogs = typeof logs === 'string' ? JSON.parse(logs) : logs;
      
      // Si logs es un objeto (ej: {"FATAL": 3}), lo convertimos a array
      if (parsedLogs && typeof parsedLogs === 'object' && !Array.isArray(parsedLogs)) {
        return Object.entries(parsedLogs).map(([nivel, count]) => ({
          nivel,
          count
        }));
      }
      
      return Array.isArray(parsedLogs) ? parsedLogs : [];
    } catch {
      return [];
    }
  };

  // Conexión WebSocket (se mantiene igual)
  useEffect(() => {
  const connectWebSocket = () => {
    websocket.current = new WebSocket('ws://localhost:8000/ws/1');

    websocket.current.onopen = () => {
      console.log('Conexión WebSocket establecida');
    };

    websocket.current.onmessage = (event) => {
  try {
    // Primero verificamos si es un ping/pong
    if (event.data === "pong") {
      console.log("Ping respondido correctamente");
      return; // No hacemos parse de JSON
    }

    const message = JSON.parse(event.data);

    if (message.eventType === 'histogram_update') {
      const { idServidor, datos } = message.data;
      setHistogramaData(prev => ({
        ...prev,
        [idServidor]: datos
      }));
    }
  } catch (e) {
    console.error('Error procesando mensaje WebSocket:', e);
  }
};

    websocket.current.onerror = (error) => {
      console.error('Error en WebSocket:', error);
    };

    websocket.current.onclose = () => {
      console.log('Conexión WebSocket cerrada, reintentando en 5s');
      setTimeout(connectWebSocket, 5000);
    };
  };

  connectWebSocket();

  // --- Monitoreo de estado cada 5s ---
  const monitorInterval = setInterval(() => {
    if (websocket.current) {
      const estado = websocket.current.readyState;
      console.log('Estado WebSocket:', estado);
      if (estado === WebSocket.OPEN) {
        websocket.current.send("ping"); // opcional
      }
    }
  }, 5000);

  return () => {
    clearInterval(monitorInterval);
    websocket.current?.close();
  };
}, []);

  // Cargar datos iniciales (se mantiene igual)
  const cargarDatos = async () => {
    try {
      setCargando(true);
      setError(null);

      const resServidores = await fetch('http://localhost:8000/api/servidores/?idEmpresa=1');
      if (!resServidores.ok) throw new Error('Error al cargar servidores');
      const dataServidores = await resServidores.json();
      setServidores(dataServidores.resultados);

      const histogramaPromesas = dataServidores.resultados.map(async (servidor) => {
        const res = await fetch(
          `http://localhost:8000/api/servidores/${servidor.id_servidor}/evolucion-errores/?idEmpresa=1&agrupacion=por_proceso`
        );
        return res.json();
      });

      const resultadosHistograma = await Promise.all(histogramaPromesas);
      const nuevosDatos = {};
      resultadosHistograma.forEach((result, index) => {
        // Ordenamos los datos cronológicamente ascendente (más antiguos primero)
        const datosOrdenados = [...result.datos].sort((a, b) => new Date(a.fecha) - new Date(b.fecha));
        nuevosDatos[dataServidores.resultados[index].id_servidor] = datosOrdenados;
      });
      setHistogramaData(nuevosDatos);

    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarDatos();
  }, []);

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

  if (cargando) {
    return (
      <div className="cargando">
        <div className="spinner"></div>
        <p>Cargando dashboard...</p>
      </div>
    );
  }

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

      <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
  <div>
    <label>Desde:</label><br />
    <input
      type="date"
      value={fechaDesde}
      onChange={(e) => setFechaDesde(e.target.value)}
    />
  </div>
  <div>
    <label>Hasta:</label><br />
    <input
      type="date"
      value={fechaHasta}
      onChange={(e) => setFechaHasta(e.target.value)}
    />
  </div>
</div>


      <div className="servidores-grid">
        
        {servidores.map((servidor) => {
          // Aquí ordenamos por fecha ASC solo por si acaso, aunque ya está hecho al cargar
          const datosFiltrados = (histogramaData[servidor.id_servidor] || []).filter(item => {
            if (!fechaDesde && !fechaHasta) return true;
          
            const fechaItem = new Date(item.fecha);
            const desde = fechaDesde ? new Date(fechaDesde + "T00:00:00") : null;
            const hasta = fechaHasta ? new Date(fechaHasta + "T23:59:59") : null;
          
            if (desde && fechaItem < desde) return false;
            if (hasta && fechaItem > hasta) return false;
          
            return true;
          });
          
          
          const datos = datosFiltrados.slice().sort((a, b) => new Date(a.fecha) - new Date(b.fecha));          

          const labels = datos.map((_, index) => ` ${index + 1}`);

          // Datos corregidos para manejar logs como objeto o array
          const fatalData = datos.map(item => {
            const normalizedLogs = parseAndNormalizeLogs(item.logs);
            return normalizedLogs.filter(log => log.nivel === 'FATAL').reduce((sum, log) => sum + (log.count || 1), 0);
          });

          const errorData = datos.map(item => {
            const normalizedLogs = parseAndNormalizeLogs(item.logs);
            return normalizedLogs.filter(log => log.nivel === 'ERROR').reduce((sum, log) => sum + (log.count || 1), 0);
          });

          const warnData = datos.map(item => {
            const normalizedLogs = parseAndNormalizeLogs(item.logs);
            return normalizedLogs.filter(log => log.nivel === 'WARN').reduce((sum, log) => sum + (log.count || 1), 0);
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
                borderColor: '#FF6384',
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

              <div className="grafica-container" style={{ height: '320px' }}>
              <Line 
                data={chartData} 
                options={{
                  ...opcionesLineChart(servidor.id_servidor),
                  maintainAspectRatio: false
                }} 
              />
            </div>

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
