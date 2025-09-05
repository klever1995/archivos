import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './MultiLogProcessor.css';
import ModalAccesos from './ModalAccesos'; 
import { useWebSocket } from './WebsocketContext';
import ModalDepartamentos from './ModalDepartamentos';

//Gestor de servidores
const MultiLogProcessor = () => {
  const [servidores, setServidores] = useState([]);
  const [error, setError] = useState(null);
  const [nuevaRuta, setNuevaRuta] = useState('');
  const [nuevoIntervalo, setNuevoIntervalo] = useState(1);
  const [procesosActivos, setProcesosActivos] = useState([]);
  const timersRef = useRef({});
  const navigate = useNavigate();
  const [mostrarModalAccesos, setMostrarModalAccesos] = useState(false);
  const [idEmpresa] = useState(1);
  const [idAccesoSeleccionado, setIdAccesoSeleccionado] = useState('');
  const [accesosRemotos, setAccesosRemotos] = useState([]);
  const [departamentos, setDepartamentos] = useState([]);
  const [departamentoFiltro, setDepartamentoFiltro] = useState(null); 
  const [nombreServidor, setNombreServidor] = useState('');
  const { addMessageHandler } = useWebSocket();
  const [mostrarModalDepartamentos, setMostrarModalDepartamentos] = useState(false);

  // Carga procesos activos del servidor
  const cargarProcesosActivos = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/interpretacion/procesos-activos');
      if (!res.ok) throw new Error('No se pudieron cargar procesos activos');
      const data = await res.json();
      setProcesosActivos(data);

      setServidores(prev => prev.map(servidor => {
        const procesoActivo = data.find(p => p.id_servidor === servidor.idServidor);
        if (procesoActivo && procesoActivo.intervalo_minutos) {
          return { ...servidor, intervalo: procesoActivo.intervalo_minutos };
        }
        return servidor;
      }));
    } catch (err) {
      console.error(err);
    }
  };

  // Carga inicial de datos: servidores, accesos y departamentos
  const cargarDatosIniciales = async () => {
    try {
      const [servidoresRes, accesosRes, departamentosRes] = await Promise.all([
        fetch('http://localhost:8000/api/servidores/?idEmpresa=1'),
        fetch('http://localhost:8000/api/accesos-remotos/?idEmpresa=1&activo=true'),
        fetch('http://localhost:8000/api/departamentos/?idEmpresa=1')
      ]);

      if (!servidoresRes.ok) throw new Error('Error al cargar servidores');
      
      const dataServidores = await servidoresRes.json();
      const dataAccesos = await accesosRes.json();
      const dataDepartamentos = await departamentosRes.json();

      setServidores(dataServidores.resultados.map(s => ({
        idServidor: s.id_servidor,
        ruta: s.ruta,
        nombre: s.nombre,
        intervalo: 1,
        activo: false,
        idAccesoRemoto: s.id_acceso_remoto,
        idDepartamento: s.id_departamento 
      })));

      setAccesosRemotos(dataAccesos.data || []);
      setDepartamentos(dataDepartamentos.data || []); 
      if (dataDepartamentos.data?.length > 0) {
        setDepartamentoFiltro(dataDepartamentos.data[0].idDepartamento); 
      }

    } catch (err) {
      setError(err.message);
    }
  };

  // Ejecuta la carga inicial de datos y asigna correctamente intervalos
  useEffect(() => {
    const cargarTodoInicial = async () => {
      try {
        const [servidoresRes, accesosRes, departamentosRes, procesosRes] = await Promise.all([
          fetch('http://localhost:8000/api/servidores/?idEmpresa=1'),
          fetch('http://localhost:8000/api/accesos-remotos/?idEmpresa=1&activo=true'),
          fetch('http://localhost:8000/api/departamentos/?idEmpresa=1'),
          fetch('http://localhost:8000/api/v1/interpretacion/procesos-activos')
        ]);

        if (!servidoresRes.ok) throw new Error('Error al cargar servidores');

        const dataServidores = await servidoresRes.json();
        const dataAccesos = await accesosRes.json();
        const dataDepartamentos = await departamentosRes.json();
        const dataProcesos = await procesosRes.json();

        const servidoresIniciales = dataServidores.resultados.map(s => {
          const procesoActivo = dataProcesos.find(p => p.id_servidor === s.id_servidor);
          return {
            idServidor: s.id_servidor,
            ruta: s.ruta,
            nombre: s.nombre,
            intervalo: procesoActivo?.intervalo_minutos || 1,
            activo: procesoActivo?.en_ejecucion || false,
            idAccesoRemoto: s.id_acceso_remoto,
            idDepartamento: s.id_departamento
          };
        });

        setServidores(servidoresIniciales);
        setProcesosActivos(dataProcesos);
        setAccesosRemotos(dataAccesos.data || []);
        setDepartamentos(dataDepartamentos.data || []);

        if (dataDepartamentos.data?.length > 0) {
          setDepartamentoFiltro(dataDepartamentos.data[0].idDepartamento);
        }
      } catch (err) {
        setError(err.message);
      }
    };

    cargarTodoInicial();

    const unsubscribe = addMessageHandler((message) => {
      if (message.eventType === 'proceso_completado') {
        const idProceso = message.data.id_servidor;

        setServidores(prev => prev.map(s => {
          if (s.activo && s.idServidor === idProceso) {
            if (timersRef.current[s.idServidor]) {
              clearTimeout(timersRef.current[s.idServidor]);
            }
            timersRef.current[s.idServidor] = setTimeout(() => {
              procesarServidor(s.idServidor, s.ruta, s.intervalo);
            }, s.intervalo * 60 * 1000);
          }
          return s;
        }));
      }
    });

    return () => {
      unsubscribe();
      Object.values(timersRef.current).forEach(timer => clearTimeout(timer));
    };
  }, [addMessageHandler]);

// Inicia procesamiento de logs 
  const procesarServidor = async (idServidor, ruta, intervaloMinutos) => {
    try {
      setServidores(prev => prev.map(s =>
        s.idServidor === idServidor ? { ...s, activo: true } : s
      ));

      const servidorActual = servidores.find(s => s.idServidor === idServidor);
      const intervaloReal = intervaloMinutos ?? servidorActual?.intervalo ?? 5;

      const response = await fetch('http://localhost:8000/api/v1/interpretacion/iniciar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_servidor: idServidor,
          batch_size: 100,
          intervalo_minutos: intervaloReal
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Error desconocido');
      }

      await cargarProcesosActivos();

      return await response.json();

    } catch (err) {
      console.error(`Error procesando ${ruta}:`, err);

      setError(`Error en ${ruta}: ${err.message}`);

      setServidores(prev => prev.map(s =>
        s.idServidor === idServidor ? { ...s, activo: false } : s
      ));

      throw err;
    }
  };

//Detener procesamiento de logs
  const detenerProceso = async (idServidor) => {
    try {
      const url = `http://localhost:8000/api/v1/interpretacion/detener?id_servidor=${idServidor}`;
      const response = await fetch(url, { method: 'POST' });
      if (!response.ok) throw new Error(await response.text());

      setServidores(prev => prev.map(s =>
        s.idServidor === idServidor ? { ...s, activo: false } : s
      ));

      if (timersRef.current[idServidor]) {
        clearTimeout(timersRef.current[idServidor]);
        delete timersRef.current[idServidor];
      }

      await cargarProcesosActivos();
      return await response.json();
    } catch (err) {
      console.error('Error deteniendo proceso:', err);
      setError(`Error al detener proceso: ${err.message}`);
      throw err;
    }
  };

// Alterna entre iniciar/detener monitoreo
  const toggleProcesamiento = async (idServidor, ruta, intervalo) => {
    const estaActivo = procesosActivos.some(p => p.id_servidor === idServidor);
    if (!estaActivo) {
      await procesarServidor(idServidor, ruta, intervalo);
    } else {
      await detenerProceso(idServidor);
    }
  };

// Agrega nuevo servidor a monitorear
  const agregarServidor = async () => {
    if (!nuevaRuta.trim()) return setError('Ruta requerida');
    if (!nombreServidor.trim()) return setError('Nombre del servidor requerido');
    if (!idAccesoSeleccionado) return setError('Debe seleccionar un acceso remoto');
    if (!departamentoFiltro) return setError('Selecciona un departamento para el servidor');

    try {
      const response = await fetch('http://localhost:8000/api/servidores/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          idEmpresa: 1,
          ruta: nuevaRuta,
          nombreServidor: nombreServidor,
          activo: false,
          idAccesoRemoto: idAccesoSeleccionado,
          idDepartamento: departamentoFiltro, 
        }),
      });

      if (!response.ok) throw new Error(await response.text());

      const nuevoServidor = await response.json();
      setServidores(prev => [...prev, {
        idServidor: nuevoServidor.id_servidor,
        nombre: nombreServidor,
        ruta: nuevaRuta,
        intervalo: nuevoIntervalo,
        activo: false,
        idAccesoRemoto: idAccesoSeleccionado,
        idDepartamento: departamentoFiltro, 
      }]);
      
      setNuevaRuta('');
      setIdAccesoSeleccionado('');
      setNombreServidor('');
    } catch (err) {
      setError(`Error al guardar: ${err.message}`);
    }
  };

// Elimina servidor y sus procesos asociados
  const eliminarServidor = async (idServidor) => {
    if (!window.confirm("¿Estás seguro de borrar? Todos los procesos y logs asociados serán eliminados.")) return;

    try {
      const response = await fetch(`http://localhost:8000/api/servidores/${idServidor}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('Error al eliminar servidor');

      if (timersRef.current[idServidor]) {
        clearTimeout(timersRef.current[idServidor]);
        delete timersRef.current[idServidor];
      }

      setServidores(prev => prev.filter(s => s.idServidor !== idServidor));
    } catch (err) {
      setError(`Error al eliminar servidor: ${err.message}`);
    }
  };

// Filtra servidores por departamento
  const servidoresFiltrados = departamentoFiltro
    ? servidores.filter(s => s.idDepartamento == departamentoFiltro)
    : servidores;

  return (
    <div className="multi-log-container">
      <div className="header-con-boton">
        <h2>Monitor de Servidores Remotos</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <span style={{ fontWeight: '500', color: '#555' }}>Filtrar por:</span>
          <select 
            className="dropdown-departamentos" 
            value={departamentoFiltro || ''} 
            onChange={(e) => setDepartamentoFiltro(e.target.value || null)}
          >
            <option value="">Todos los departamentos</option>
            {departamentos.map(depto => (
              <option key={depto.idDepartamento} value={depto.idDepartamento}>
                {depto.nombre} ({depto.totalServidores})
              </option>
            ))}
          </select>
          <button onClick={() => setMostrarModalDepartamentos(true)} className="btn-ir-graficos" style={{ backgroundColor: '#6a5acd' }}>
            Gestionar Ambientes
          </button>
          <button onClick={() => setMostrarModalAccesos(true)} className="btn-ir-graficos" style={{ backgroundColor: '#6a5acd' }}>
            Administrar Accesos
          </button>
          <button onClick={() => navigate('/tablero-logs')} className="btn-ir-graficos">
            Ver Dashboard
          </button>
        </div>
      </div>

      {/* Formulario para agregar servidores */}
      <div className="agregar-archivo">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={nuevaRuta}
            onChange={(e) => setNuevaRuta(e.target.value)}
            placeholder="Ej: /ruta/servidor.log"
            style={{ flexGrow: 1, minWidth: '180px' }}
          />
          <input
            type="text"
            value={nombreServidor}
            onChange={(e) => setNombreServidor(e.target.value)}
            placeholder="Nombre del servidor (ej: ServidorWeb01)"
            style={{ flexGrow: 1, minWidth: '180px' }}
            required
          />
          <select
            className="dropdown-accesos"
            value={idAccesoSeleccionado || ''}
            onChange={(e) => setIdAccesoSeleccionado(e.target.value)}
          >
            <option value="">Selecciona acceso remoto</option>
            {accesosRemotos.map((acceso) => (
              <option key={acceso.idAcceso} value={acceso.idAcceso}>
                {acceso.hostname}
              </option>
            ))}
          </select>
        </div>

        <input
          type="number"
          min="1"
          value={nuevoIntervalo}
          onChange={(e) => setNuevoIntervalo(Math.max(1, e.target.valueAsNumber || 5))}
        />
        <button onClick={agregarServidor}>Agregar Servidor</button>
      </div>

      {/* Tabla de servidores */}
      <div className="lista-archivos">
        {servidoresFiltrados.length === 0 ? (
          <p>No hay servidores registrados</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Servidor</th>
                <th>Ruta</th>
                <th>Hostname</th>
                <th>Intervalo (min)</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {servidoresFiltrados.map((s) => {
                const estaActivo = procesosActivos.some(p => p.id_servidor === s.idServidor);
                return (
                  <tr key={s.idServidor}>
                    <td>{s.nombre}</td>
                    <td>{s.ruta}</td>
                    <td>{accesosRemotos.find(a => a.idAcceso === s.idAccesoRemoto)?.hostname || 'No asignado'}</td>
                    <td>
                      <input
                        type="number"
                        min="1"
                        value={s.intervalo}
                        onChange={(e) => {
                          const intervalo = Math.max(1, e.target.valueAsNumber || 5);
                          setServidores(prev => prev.map(ss =>
                            ss.idServidor === s.idServidor ? { ...ss, intervalo } : ss
                          ));                      
                        }}
                        disabled={estaActivo} 
                        title={estaActivo ? "Detenga el proceso para modificar el intervalo" : ""}
                      />
                    </td>
                    <td>
                      <span className={`estado ${estaActivo ? 'activo' : ''}`}>
                        {estaActivo ? '▶ MONITOREANDO' : '⏸ DETENIDO'}
                      </span>
                    </td>
                    <td>
                      <button
                        onClick={() => toggleProcesamiento(s.idServidor, s.ruta, s.intervalo)}
                        className={estaActivo ? 'detener' : 'iniciar'}
                      >
                        {estaActivo ? 'Detener' : 'Iniciar'}
                      </button>
                      <button
                        onClick={() => eliminarServidor(s.idServidor)}
                        className="eliminar"
                      >
                        Eliminar
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {error && (
        <div className="error" onClick={() => setError(null)}>
          ❌ {error}
        </div>
      )}

      {/* Modal Accesos */}
      {mostrarModalAccesos && (
        <div className="modal-overlay">
          <div className="modal-contenido modal-grande">
            <ModalAccesos 
              idEmpresa={idEmpresa} 
              onClose={() => {
                setMostrarModalAccesos(false);
                cargarDatosIniciales();
              }}
            />
          </div>
        </div>
      )}

      {/* Modal Departamentos */}
      {mostrarModalDepartamentos && (
        <div className="modal-overlay">
          <div className="modal-contenido modal-grande">
            <ModalDepartamentos 
              idEmpresa={idEmpresa}
              onClose={() => {
                setMostrarModalDepartamentos(false);
                cargarDatosIniciales();
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default MultiLogProcessor;
