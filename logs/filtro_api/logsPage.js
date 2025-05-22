import React, { useState, useEffect, useRef } from 'react';

const LogsPage = () => {
  const [archivo, setArchivo] = useState(null);
  const [resultados, setResultados] = useState([]);
  const [autoProcesamiento, setAutoProcesamiento] = useState(false);
  const [intervalo, setIntervalo] = useState(5); // Minutos
  const fileInputRef = useRef(null);

  // Función para procesar el archivo
  const procesarLog = async (file) => {
    if (!file) return;
    
    try {
      const formData = new FormData();
      formData.append('file', file);

      const respuesta = await fetch('http://localhost:8000/procesar-log/', {
        method: 'POST',
        body: formData
      });

      if (!respuesta.ok) throw new Error(`Error ${respuesta.status}`);

      const datos = await respuesta.json();
      setResultados(prev => [...prev, {
        ...datos,
        timestamp: new Date().toLocaleTimeString(),
        archivo: file.name
      }]);

    } catch (err) {
      console.error("Error al procesar:", err);
    }
  };

  // Lógica para volver a leer el archivo en cada ejecución automática
  const procesarArchivoActualizado = async () => {
    if (!archivo) return;

    try {
      // Crear un nuevo File object con los datos actualizados
      const fileData = await readFileAsText(archivo);
      const nuevoArchivo = new File([fileData], archivo.name, {
        type: archivo.type,
        lastModified: Date.now()
      });
      
      await procesarLog(nuevoArchivo);
    } catch (err) {
      console.error("Error al leer archivo:", err);
    }
  };

  // Función para leer el archivo como texto
  const readFileAsText = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (event) => resolve(event.target.result);
      reader.onerror = (error) => reject(error);
      reader.readAsText(file);
    });
  };

  // Configurar el intervalo de auto-procesamiento
  useEffect(() => {
    let intervaloId;

    if (autoProcesamiento) {
      // Procesar inmediatamente al activar
      procesarArchivoActualizado();

      // Configurar intervalo
      intervaloId = setInterval(() => {
        procesarArchivoActualizado();
      }, intervalo * 60 * 1000);
    }

    return () => clearInterval(intervaloId);
  }, [autoProcesamiento, intervalo, archivo]);

  // Manejar la selección de archivo
  const handleFileChange = async (e) => {
    const nuevoArchivo = e.target.files[0];
    if (!nuevoArchivo) return;

    setArchivo(nuevoArchivo);
    await procesarLog(nuevoArchivo);
  };

  return (
    <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
      <h2>Monitor de Logs</h2>

      {/* Selector de archivo (oculto) */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        style={{ display: 'none' }}
        accept=".txt,.log"
      />

      {/* Botón para seleccionar archivo */}
      <button 
        onClick={() => fileInputRef.current.click()}
        style={{ padding: '10px', margin: '10px 0' }}
      >
        {archivo ? `Archivo seleccionado: ${archivo.name}` : 'Seleccionar archivo de log'}
      </button>

      {/* Configuración de auto-procesamiento */}
      {archivo && (
        <div style={{ margin: '20px 0', padding: '15px', border: '1px solid #ddd' }}>
          <h3>Procesamiento Automático</h3>
          <div style={{ margin: '10px 0' }}>
            <label>
              Intervalo (minutos):
              <input
                type="number"
                min="1"
                value={intervalo}
                onChange={(e) => setIntervalo(Number(e.target.value))}
                style={{ marginLeft: '10px', padding: '5px' }}
              />
            </label>
          </div>
          <button
            onClick={() => setAutoProcesamiento(!autoProcesamiento)}
            style={{
              padding: '10px 15px',
              background: autoProcesamiento ? '#ff4444' : '#4CAF50',
              color: 'white',
              border: 'none',
              borderRadius: '4px'
            }}
          >
            {autoProcesamiento ? '⏸ Detener' : '▶ Iniciar'} Auto-Proceso
          </button>
        </div>
      )}

      {/* Resultados */}
      <div style={{ marginTop: '30px' }}>
        <h3>Historial de Procesamiento</h3>
        {resultados.length === 0 ? (
          <p>No hay resultados aún</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {resultados.map((resultado, index) => (
              <li key={index} style={{
                padding: '10px',
                margin: '5px 0',
                background: '#f9f9f9',
                borderLeft: '4px solid #4CAF50'
              }}>
                <strong>{resultado.timestamp}</strong> - {resultado.archivo}
                <div>Logs procesados: {resultado.total_logs}</div>
                <div>Bytes: {resultado.bytes_processed}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default LogsPage;
