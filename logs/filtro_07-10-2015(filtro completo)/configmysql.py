from flask_sqlalchemy import SQLAlchemy
import os
import pymysql
import shutil

db = SQLAlchemy()

CERT_ORIGINAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'certs', 'ca-cert.pem')
CERT_DEST_PATH = os.path.join(os.getcwd(), 'ca-cert.pem')

try:
    if not os.path.exists(CERT_DEST_PATH):
        shutil.copy(CERT_ORIGINAL_PATH, CERT_DEST_PATH)
        print(f">><<Certificado copiado a: {CERT_DEST_PATH}")
    else:
        print(f">><<Certificado ya existe en: {CERT_DEST_PATH}")
except Exception as e:
    print(f">>>>>>Error al copiar el certificado: {e}")

# Configuración base
class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False

# Configuración de desarrollo
class DevelopmentConfig(Config):
    # *** CAMBIO CRÍTICO: Usar variables de entorno también en desarrollo ***
    DB_USER = os.getenv('DB_USER', '')  # Valor por defecto vacío
    DB_PASSWORD = os.getenv('DB_PASSWORD', '') # Valor por defecto vacío
    DB_HOST = os.getenv('DB_HOST', 'asistentebase.mysql.database.azure.com')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME', 'asistentedb')

    SQLALCHEMY_DATABASE_URI = (
        f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    )
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 299,
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 20,
            'ssl': {'ca': 'C:/ASISTENTECEDI/backend/certs/ca-cert.pem'}  # Ruta al certificado SSL corregida
        }
    }

# Configuración de producción
class ProductionConfig(Config):

    print(f"ProductionConfig Certificado usado en>>>>>>>>>>>>>>>xxxxxxxxxxxxxx>>>>>>>>>>: {CERT_DEST_PATH}")
    if os.access(CERT_DEST_PATH, os.R_OK):
        print(f"El certificado existe y es accesible: {CERT_DEST_PATH}")
    else:
        print(f"El certificado existe, pero no se puede leer: {CERT_DEST_PATH}")

    # *** CAMBIO CRÍTICO: Eliminar valores hardcodeados por defecto en producción ***
    DB_USER = os.getenv('DB_USER', '')  # Valor por defecto vacío
    DB_PASSWORD = os.getenv('DB_PASSWORD', '') # Valor por defecto vacío
    DB_HOST = os.getenv('DB_HOST', 'asistentebase.mysql.database.azure.com')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME', 'asistentedb')
    DB_SSL_CA = os.getenv('DB_SSL_CA', '/tmp/ca-cert.pem')

    SQLALCHEMY_DATABASE_URI = (
        f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?ssl_ca={DB_SSL_CA}'
    )
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 299,
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 20,
            #'ssl': {'ca': DB_SSL_CA}
            'ssl': {'ca': CERT_DEST_PATH}
        }
    }

# Inicialización de la aplicación Flask
def init_app(app, environment='production'):
    if environment == 'development':
        app.config.from_object(DevelopmentConfig)
    else:
        app.config.from_object(ProductionConfig)
    db.init_app(app)
