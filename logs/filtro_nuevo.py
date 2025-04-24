import os
import pandas as pd
import re
from tqdm import tqdm

# Definir la ruta del directorio donde deseas guardar los archivos
output_dir = 'C:/Users/klever.robalino/Desktop/Proyecto-Mutualista/backend-asistente/agentes/logs/logs_files'

# Asegúrate de que el directorio exista, si no, lo creamos
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Nombre del archivo original y los archivos de salida
file = 'prueba'
file_path = f'{output_dir}/{file}.txt'

# Crear nombres de archivo de salida
output_file_path = os.path.join(output_dir, f'primer_filtro_{file}.log')
filtered_output_file_path = os.path.join(output_dir, f'segundo_filtro_{file}.log')

# Resto de tu código para procesar el archivo
def read_and_replace(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # Reemplazar ';' por ':'
    lines = [line.replace(';', ':') for line in lines]
    
    # Eliminar líneas en blanco
    lines = [line for line in lines if line.strip()]
    
    return lines

def label_lines(lines):
    data = []
    line_number = 1

    for line in tqdm(lines, desc="Etiquetando líneas"):
        data.append({'line_number': line_number, 'text': line.strip()})
        line_number += 1
    
    return pd.DataFrame(data)

def add_delimiters(df):
    pattern = re.compile(r'^\d{2}:\d{2}:\d{2},\d{3}')
    processed_lines = []
    current_line = ''
    current_line_number = 0
    
    for index, row in tqdm(df.iterrows(), desc="Añadiendo delimitadores", total=len(df)):
        if pattern.match(row['text']):
            if current_line:
                processed_lines.append({'text': current_line.strip()})
            parts = row['text'].split(' ', 2)
            current_line = f"{row['line_number']};{parts[0]};{parts[1]};{parts[2]};" if len(parts) == 3 else row['text']
        else:
            current_line += f":{row['text']}"
    
    if current_line:
        processed_lines.append({'text': current_line.strip()})
    
    return pd.DataFrame(processed_lines)

def filter_non_info(input_file_path, output_file_path):
    # Leer el archivo procesado
    with open(input_file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    data = []
    for line in tqdm(lines, desc="Filtrando líneas no INFO"):
        parts = line.strip().split(';')
        if len(parts) >= 3 and parts[2].strip() != 'INFO':
            data.append(line.strip())

    # Guardar las líneas filtradas en un nuevo archivo
    with open(output_file_path, 'w', encoding='utf-8') as file:
        for line in data:
            file.write(f"{line}\n")

# Leer y procesar el archivo original
lines = read_and_replace(file_path)

# Etiquetar las líneas
df_labeled = label_lines(lines)

# Añadir delimitadores internos y concatenar detalles
df_processed = add_delimiters(df_labeled)

# Guardar el DataFrame resultante en un nuevo archivo .log con columnas separadas por punto y coma
df_processed.to_csv(output_file_path, index=False, sep=';', header=False, lineterminator='\n')
print(f'Archivo guardado en: {output_file_path}')

# Filtrar y guardar las líneas que no son INFO en un nuevo archivo
filter_non_info(output_file_path, filtered_output_file_path)
print(f'Archivo filtrado guardado en: {filtered_output_file_path}')

