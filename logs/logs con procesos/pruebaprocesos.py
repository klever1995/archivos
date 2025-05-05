----------------------------prueba de matodos lo_procesos------------archivo pruebaprocesos.py
from metodos_loprocesos import ProcesosLogger
import time  

if __name__ == "__main__":
    # Ejemplo de uso (igual que antes)
    id_proceso = ProcesosLogger.iniciar_proceso(
        idEmpresa=1,
        operador=100
    )
    
    if id_proceso != -1:
        # Simular procesamiento (añadí un delay para tener duración real)
        print("Procesando...")
        time.sleep(2)  # Simula 2 segundos de trabajo
        
        # Finalizar el proceso (igual que antes)
        ProcesosLogger.finalizar_proceso(
            idAuditoria=id_proceso,
            totalLogs=150
        )
        
        # Opcional: Verificar la duración (nuevo método)
        duracion = ProcesosLogger.obtener_duracion_proceso(id_proceso)
        print(f"Duración calculada: {duracion} segundos")
