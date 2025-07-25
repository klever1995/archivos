import os
import sys  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import socket
from config import db, init_app
from flask import Flask

# Configuración de paths

# Importación de modelos
from modelo.loAccesosremotos import loAccesosremotos
from modelo.asEmpresa import asEmpresa

# Configuración inicial
flask_app = Flask(__name__)
init_app(flask_app)

def main():
    try:
        hostname_actual = socket.gethostname()
        print(f"🖥️ Hostname detectado: {hostname_actual}")

        with flask_app.app_context():
            # Verificación de modelos (forma compatible con SQLAlchemy 2.x)
            print("Modelos registrados:", db.Model.registry._class_registry.keys())
            
            # Consulta optimizada
            acceso = (db.session.query(loAccesosremotos)
                      .join(asEmpresa)
                      .filter(loAccesosremotos.hostname == hostname_actual)
                      .first())

            if not acceso:
                print("❌ No hay configuración para este host en la BD")
                return

            print(f"✅ Acceso configurado encontrado (Ruta: {acceso.rutaRemota})")
            if acceso.empresa:
                print(f"📄 Empresa asociada: {acceso.empresa.nombre}")
            else:
                print("⚠️ No se encontró información de empresa asociada")
                print(hostname_actual)

    except Exception as e:
        print(f"🔥 Error crítico: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
