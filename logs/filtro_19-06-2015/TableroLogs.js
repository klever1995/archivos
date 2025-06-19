import React, { useState, useEffect } from 'react';
import { Doughnut } from 'react-chartjs-2';
import { Chart, registerables } from 'chart.js';
import ModalLogs from './ModalLogs';
import './TableroLogs.css';

Chart.register(...registerables);

const TableroLogs = () => {
  const [servidores, setServidores] = useState([]);
  const [metricas, setMetricas] = useState({});
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  const [mostrarModal, setMostrarModal] = useState(false);
  const [logsSeleccionados, setLogsSeleccionados] = useState([]);
  const [nivelSeleccionado, setNivelSeleccionado] = useState('');
  const [servidorNombre, setServidorNombre] = useState('');

  const cargarDatos = async () => {
    try {
      setCargando(true);
      setError(null);

      const resServidores = await fetch('http://localhost:8000/api/servidores/?idEmpresa=1');
      if (!resServidores.ok) throw new Error('Error al cargar servidores');
      const dataServidores = await resServidores.json();
      setServidores(dataServidores.resultados);

      const metricasPromesas = dataServidores.resultados.map(async (servidor) => {
        const resMetricas = await fetch(
          `http://localhost:8000/api/servidores/metricas/${servidor.id_servidor}?idEmpresa=1`
        );
        return resMetricas.json();
      });

      const metricasData = await Promise.all(metricasPromesas);
      const metricasMap = {};
      metricasData.forEach((m, i) => {
        metricasMap[dataServidores.resultados[i].id_servidor] = m;
      });
      setMetricas(metricasMap);
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarDatos();
  }, []);

  const abrirModalConLogs = async (servidor, nivel) => {
    try {
      const url = `http://localhost:8000/api/servidores/${servidor.id_servidor}/logs-filtrados/?idEmpresa=1&nivel=${nivel}`;
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

  const opcionesGrafico = (servidor, labels) => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right',
      },
      tooltip: {
        callbacks: {
          label: function (context) {
            return `${context.label}: ${context.raw}`;
          },
        },
      },
    },
    onClick: async (evt, elements) => {
      if (!elements.length) return;
      const index = elements[0].index;
      const nivel = labels[index];
      await abrirModalConLogs(servidor, nivel);
    },
  });

  if (cargando)
    return (
      <div className="cargando">
        <div className="spinner"></div>
        <p>Cargando dashboard...</p>
      </div>
    );

  if (error)
    return (
      <div className="error">
        <p>Error al cargar datos: {error}</p>
        <button onClick={cargarDatos}>Reintentar</button>
      </div>
    );

  return (
    <div className="tablero-container">
      <h2>Dashboard de Métricas - Todos los Servidores</h2>

      <div className="servidores-grid">
        {servidores.map((servidor) => {
          const datosServidor = metricas[servidor.id_servidor]?.resultados?.[0];
          if (!datosServidor) return null;

          const ordenNiveles = ['FATAL', 'ERROR', 'WARN', 'INFO', 'DEBUG'];
          const logsPorNivel = datosServidor.logs_por_nivel || {};

          // Asegurar que FATAL esté en los datos (si no existe, se omite)
          const niveles = ordenNiveles.filter(
            (nivel) => logsPorNivel[nivel] !== undefined
          );

          // Mapear colores según el orden de niveles
          const coloresMap = {
            FATAL: '#D32F2F',
            ERROR: '#FF6384',
            WARN: '#FFCE56',
            INFO: '#36A2EB',
            DEBUG: '#4BC0C0'
          };

          const valores = niveles.map((nivel) => logsPorNivel[nivel]);
          const colores = niveles.map((nivel) => coloresMap[nivel]);

          const datosNiveles = {
            labels: niveles,
            datasets: [
              {
                data: valores,
                backgroundColor: colores,
                borderWidth: 1,
              },
            ],
          };

          return (
            <div key={servidor.id_servidor} className="servidor-card">
              <h3>{servidor.nombreServidor}</h3>
              <p className="ruta-servidor">{servidor.ruta}</p>

              <div className="estado-servidor">
                <span className={`badge ${servidor.activo ? 'activo' : 'inactivo'}`}>
                  {servidor.activo ? 'ACTIVO' : 'INACTIVO'}
                </span>
                <span>Logs: {datosServidor.total_logs}</span>
              </div>

              <div className="grafica-container">
                <Doughnut data={datosNiveles} options={opcionesGrafico(servidor, niveles)} />
              </div>

              <div className="metricas-rapidas">
                <div className="metrica">
                  <span>Último estado</span>
                  <strong>{datosServidor.ultimo_proceso?.estado || 'N/A'}</strong>
                </div>
                <div className="metrica">
                  <span>Ocurrencias</span>
                  <strong>{datosServidor.promedio_ocurrencias?.toFixed(2) || '0'}</strong>
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
