import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import re
import hashlib
from datetime import datetime
from difflib import SequenceMatcher
from collections import defaultdict
from flask import Flask
from config import init_app, db
from modelo.loLogs import loLogs
from modelo.loErrorconocido import loErrorconocido
from modelo.asEmpresa import asEmpresa



app = Flask(__name__)
init_app(app)

class Logger:
    PATRON_NIVEL = re.compile(r'\b(ERROR|FATAL|WARN|INFO|DEBUG)\b')
    PATRON_COMPONENTE = re.compile(r'\b(?:ERROR|WARN|INFO|DEBUG)\s+\[([^\]]+)\]')
    PATRON_HILO = re.compile(r'\(([^)]+)\)')
    PRIORIDAD = ['ERROR', 'FATAL', 'WARN', 'INFO', 'DEBUG', 'UNKNOWN']
    CATEGORIAS = {
        'start_send': re.compile(r'inicia envio', re.IGNORECASE),
        'end_send': re.compile(r'fin envio', re.IGNORECASE),
        'ftp_error': re.compile(r'FTP.*ERROR', re.IGNORECASE),
        'general_error': re.compile(r'ERROR', re.IGNORECASE),
    }

    @staticmethod
    def es_inicio_log(linea: str) -> bool:
        return bool(re.match(r"\d{2}:\d{2}:\d{2},\d{3}", linea))

    @staticmethod
    def extraer_componente(linea: str) -> str:
        match = re.search(r'\b(?:ERROR|WARN|INFO|DEBUG)\s+\[([^\]]+)\]', linea)
        return match.group(1).strip() if match else "desconocido"

    @staticmethod
    def extraer_hilo(linea: str) -> str:
        match = re.search(r'\(([^)]+)\)', linea)
        return match.group(1).strip() if match else "main"

    @staticmethod
    def extraer_nivel(linea: str) -> str:
        niveles = ['ERROR', 'FATAL', 'WARN', 'INFO', 'DEBUG']
        for nivel in niveles:
            if f' {nivel} ' in linea:
                return nivel
        return 'UNKNOWN'

    @staticmethod
    def categorizar_mensaje(texto: str) -> str:
        for categoria, patron in Logger.CATEGORIAS.items():
            if patron.search(texto):
                return categoria
        return 'otros'

    @staticmethod
    def limitar_longitud(texto: str, max_len=30000) -> str:
        return texto if len(texto) <= max_len else texto[:max_len] + '...'

    @staticmethod
    def prioridad_nivel(nivel: str) -> int:
        return Logger.PRIORIDAD.index(nivel) if nivel in Logger.PRIORIDAD else len(Logger.PRIORIDAD)

    @staticmethod
    def procesar_bloque(bloque_actual, linea_inicio, reporte):
        mensaje_completo = "".join(bloque_actual).strip()
        nivel = Logger.extraer_nivel(mensaje_completo)
        categoria = Logger.categorizar_mensaje(mensaje_completo)
        componente = Logger.extraer_componente(mensaje_completo)
        hilo = Logger.extraer_hilo(mensaje_completo)

        mensaje_normalizado = re.sub(r'^\d{2}:\d{2}:\d{2},\d{3}\s*', '', mensaje_completo).strip()
        mensaje_normalizado = re.sub(r'\([^)]+\)', '(THREAD)', mensaje_normalizado)
        mensaje_normalizado = re.sub(r'\d+', '[NUM]', mensaje_normalizado)
        mensaje_normalizado = mensaje_normalizado.lower()

        clave_existente = None
        for clave_actual in reporte:
            if (nivel == clave_actual[0] and 
                categoria == clave_actual[1] and 
                SequenceMatcher(None, mensaje_normalizado, clave_actual[2]).ratio() >= 0.8):
                clave_existente = clave_actual
                break

        clave = clave_existente if clave_existente else (nivel, categoria, mensaje_normalizado)
        reporte[clave].update({
            'count': reporte[clave]['count'] + 1,
            'lineas': reporte[clave]['lineas'] + [linea_inicio],
            'nivel': nivel,
            'categoria': categoria,
            'componente': componente,
            'hilo': hilo,
            'mensaje': mensaje_completo,
            'mensaje_normalizado': mensaje_normalizado
        })
