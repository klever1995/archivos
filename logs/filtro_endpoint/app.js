--------------archivo inicial donde estamos cambiando la ruta para ir al js-----------------------
  import React from "react";
import { Route, Routes, Navigate, Link } from "react-router-dom";
import { AuthProvider, useAuth } from "./AuthProvider"; // Contexto de autenticación
import Login from "./login"; // Página de Login
import AdministraUsuariosPantalla from "./AdministraUsuariosPantalla";
import AdministraRolesPantalla from "./AdministraRolesPantalla";
import DatosAlmacenadosPantalla from "./DatosAlmacenadosPantalla";
import CargarDatosPantalla from "./CargarDatosPantalla";
import AdministraEmpresaPantalla from "./AdministraEmpresaPantalla";
import AdministraPruebasPantalla from "./AdministraPruebasPantalla";
import InicioPantalla from "./InicioPantalla";
import LogsPage from './logs/logsPage.js';
import "./App.css";

// Componente para proteger rutas (solo accesibles si el usuario está autenticado)
const ProtectedRoute = ({ element }) => {
  const { user, isInitialized } = useAuth();
  console.log("0 viene a ProtectedRoute::" + user);
  console.log("1 viene a ProtectedRoute::" + isInitialized);

  if (!isInitialized) {
    return <div>Cargando...</div>; // ✅ Evita redirecciones antes de tiempo
  }

  console.log("2 viene a ProtectedRoute::" + user);
  return user ? element : <Navigate to="/login" replace />;
};

// Componente del menú lateral (solo se muestra si el usuario está autenticado)
const Sidebar = () => {
  const { user, logout, isAdmin } = useAuth();
  console.log("++++*******1 isAdmin::" + isAdmin);
  if (!user) {

    return null; // Si no hay usuario autenticado, no mostramos el menú
  }

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
      <div>
        {/* Sidebar solo si el usuario está autenticado */}
        <div className="header">
          <Sidebar />
        </div>

        {/* Definición de rutas */}
        <Routes>
          <Route path="/login" element={<LogsPage />} />
          <Route path="/usuarios" element={<ProtectedRoute element={<AdministraUsuariosPantalla />} />} />
          <Route path="/roles" element={<ProtectedRoute element={<AdministraRolesPantalla />} />} />
          <Route path="/datos-almacenados" element={<ProtectedRoute element={<DatosAlmacenadosPantalla />} />} />
          <Route path="/cargar-datos" element={<ProtectedRoute element={<CargarDatosPantalla />} />} />
          <Route path="/empresa" element={<ProtectedRoute element={<AdministraEmpresaPantalla />} />} />
          <Route path="/administra-pruebas" element={<ProtectedRoute element={<AdministraPruebasPantalla />} />} />
          <Route path="/" element={<ProtectedRoute element={<InicioPantalla />} />} />
        </Routes>
      </div>
    </AuthProvider>
  );
}

export default App;
