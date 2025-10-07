from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

db = SQLAlchemy()

# Configuración base
class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False

# Configuración para SQL Server
class SQLServerConfig(Config):
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')
    DB_NAME = os.getenv('DB_NAME')

    SQLALCHEMY_DATABASE_URI = (
        f'mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?'
        f'driver=ODBC+Driver+18+for+SQL+Server&'
        f'TrustServerCertificate=yes&'
        f'Encrypt=yes'
    )
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 299,
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 20
        }
    }

# Inicialización de la aplicación Flask
def init_app(app, environment='production'):
    app.config.from_object(SQLServerConfig)
    db.init_app(app)
