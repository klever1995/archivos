import React, { useState, useEffect } from 'react';
import './ModalAccesos.css';

// Componente modal para gestionar accesos remotos de una empresa.
  const ModalAccesos = ({ idEmpresa, onClose }) => {
  const [accesos, setAccesos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [nuevoAcceso, setNuevoAcceso] = useState({
    usuario: '',
    contrasena: '',
    hostname: ''
  });
  const [servidoresVinculados, setServidoresVinculados] = useState({});

// Obtener los accesos remotos:
  const fetchAccesos = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/accesos-remotos/?idEmpresa=${idEmpresa}`);
      if (!response.ok) throw new Error('Error al obtener accesos');
      const data = await response.json();
      setAccesos(data.data);
      
//Cuenta los servidores vinculados
      const conteoServidores = {};
      for (const acceso of data.data) {
        const res = await fetch(`http://localhost:8000/api/accesos-remotos/contar-servidores?idAccesoRemoto=${acceso.idAcceso}`);
        const countData = await res.json();
        conteoServidores[acceso.idAcceso] = countData.total;
      }
      setServidoresVinculados(conteoServidores);
      
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setNuevoAcceso(prev => ({ ...prev, [name]: value }));
  };

//Crea nuevo acceso y actualiza la lista
  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('http://localhost:8000/api/accesos-remotos/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...nuevoAcceso,
          idEmpresa
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Error al crear acceso');
      }

      await fetchAccesos();
      setShowForm(false);
      setNuevoAcceso({
        usuario: '',
        contrasena: '',
        hostname: ''
      });
    } catch (err) {
      setError(err.message);
    }
  };

// Elimina un acceso remoto
  const handleEliminarAcceso = async (idAcceso) => {
    const count = servidoresVinculados[idAcceso] || 0;
    
    if (!window.confirm(
      `¿Estás seguro de eliminar este acceso? ${count > 0 ? 
      `\n\nADVERTENCIA: Esto eliminará también los ${count} servidores vinculados y todos sus logs asociados.` : ''}`
    )) return;

    try {
      const response = await fetch(`http://localhost:8000/api/accesos-remotos/${idAcceso}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Error al eliminar acceso');
      }

      await fetchAccesos();
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchAccesos();
  }, [idEmpresa]);

// Muestra carga mientras se fetchean los datos.
  if (loading) return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-contenedor" onClick={e => e.stopPropagation()}>
        <button className="modal-cerrar" onClick={onClose}>×</button>
        <div className="cargando">Cargando accesos...</div>
      </div>
    </div>
  );

// Muestra errores si falla la carga.
  if (error) return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-contenedor" onClick={e => e.stopPropagation()}>
        <button className="modal-cerrar" onClick={onClose}>×</button>
        <div className="error-modal">Error: {error}</div>
      </div>
    </div>
  );

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-contenedor" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Lista de Accesos Remotos</h2>
          <div>
            {/* Botón para agregar nuevo acceso */}
            <button className="btn-agregar" onClick={() => setShowForm(true)}>
              + Nuevo Acceso
            </button>
            <button className="modal-cerrar" onClick={onClose}>×</button>
          </div>
        </div>
        {/* Formulario para agregar accesos*/}
        {showForm && (
          <div className="formulario-acceso">
            <h3>Agregar Nuevo Acceso</h3>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>Usuario:</label>
                <input
                  type="text"
                  name="usuario"
                  value={nuevoAcceso.usuario}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div className="form-group">
                <label>Contraseña:</label>
                <input
                  type="password"
                  name="contrasena"
                  value={nuevoAcceso.contrasena}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div className="form-group">
                <label>Hostname:</label>
                <input
                  type="text"
                  name="hostname"
                  value={nuevoAcceso.hostname}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div className="form-buttons">
                <button type="submit">Guardar</button>
                <button type="button" onClick={() => setShowForm(false)}>
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        )}
        {/* Tabla de accesos existentes */}
        <div className="tabla-contenedor">
          <table className="tabla-accesos">
            <thead>
              <tr>
                <th>ID</th>
                <th>Usuario</th>
                <th>Contraseña</th>
                <th>Hostname</th>
                <th>Fecha Registro</th>
                <th>Servidores</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {accesos.map((acceso) => (
                <tr key={acceso.idAcceso}>
                  <td>{acceso.idAcceso}</td>
                  <td>{acceso.usuario}</td>
                  <td className="contrasena">••••••••</td>
                  <td>{acceso.hostname}</td>
                  <td>
                    {new Date(acceso.fechaRegistro).toLocaleString('es-ES', {
                      day: '2-digit',
                      month: '2-digit',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </td>
                  <td>{servidoresVinculados[acceso.idAcceso] || 0}</td>
                  <td>
                    <button 
                      onClick={() => handleEliminarAcceso(acceso.idAcceso)}
                      className="btn-eliminar"
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ModalAccesos;
