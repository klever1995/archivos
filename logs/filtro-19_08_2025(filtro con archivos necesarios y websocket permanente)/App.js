import React from "react";
import { Route, Routes, Navigate, Link } from "react-router-dom";
import { AuthProvider, useAuth } from "./AuthProvider"; 
import Login from "./login";
import AdministraUsuariosPantalla from "./AdministraUsuariosPantalla";
import AdministraRolesPantalla from "./AdministraRolesPantalla";
import DatosAlmacenadosPantalla from "./DatosAlmacenadosPantalla";
import CargarDatosPantalla from "./CargarDatosPantalla";
import AdministraEmpresaPantalla from "./AdministraEmpresaPantalla";
import AdministraPruebasPantalla from "./AdministraPruebasPantalla";
import InicioPantalla from "./InicioPantalla";
import MultiLogProcessor from './logs/MultiLogProcessor';
import TableroLogs from "./logs/TableroLogs.js";
import { LogsProvider } from "./logs/LogsContext"; 
import { WebSocketProvider } from "./logs/WebsocketContext"; 
import "./App.css";

// Componente para proteger rutas
const ProtectedRoute = ({ element }) => {
  const { user, isInitialized } = useAuth();

  if (!isInitialized) {
    return <div>Cargando...</div>;
  }

  return user ? element : <Navigate to="/login" replace />;
};

// Sidebar
const Sidebar = () => {
  const { user, logout, isAdmin } = useAuth();
  if (!user) return null;

  return (
    <div>
      <div>
        <label className="bienvenido">Bienvenido, {user.name}</label>
      </div>
      <div className="menu">
        <nav>
          <ul>
            <li><Link to="/">Inicio</Link></li>
            <li><Link to="/datos-almacenados">Bases de conocimiento</Link></li>
            {isAdmin && (
              <>
                <li><Link to="/usuarios">Gestión de usuarios</Link></li>
                <li><Link to="/empresa">Configuración general</Link></li>
                <li><Link to="/administra-pruebas">Pruebas</Link></li>
              </>
            )}
            <li><Link to="/login" onClick={logout}>⏻ Salir</Link></li>
          </ul>
        </nav>
      </div>
    </div>
  );
};

function App() {
  return (
    <AuthProvider>
      {/* 👇 Primero WebSocketProvider, luego LogsProvider */}
      <WebSocketProvider idEmpresa={1}>
        <LogsProvider>
          <div>
            <div className="header">
              <Sidebar />
            </div>

            <Routes>
              <Route path="/login" element={<Login />} /> 
              <Route path="/tablero-logs" element={<TableroLogs />} />
              <Route path="/usuarios" element={<ProtectedRoute element={<AdministraUsuariosPantalla />} />} />
              <Route path="/roles" element={<ProtectedRoute element={<AdministraRolesPantalla />} />} />
              <Route path="/datos-almacenados" element={<ProtectedRoute element={<DatosAlmacenadosPantalla />} />} />
              <Route path="/cargar-datos" element={<ProtectedRoute element={<CargarDatosPantalla />} />} />
              <Route path="/empresa" element={<ProtectedRoute element={<AdministraEmpresaPantalla />} />} />
              <Route path="/administra-pruebas" element={<ProtectedRoute element={<AdministraPruebasPantalla />} />} />
              <Route path="/" element={<ProtectedRoute element={<InicioPantalla />} />} />
            </Routes>
          </div>
        </LogsProvider>
      </WebSocketProvider>
    </AuthProvider>
  );
}

export default App;
