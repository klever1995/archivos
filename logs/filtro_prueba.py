import pandas as pd
import re
from tqdm import tqdm
import os

# Ruta base del directorio de salida
output_dir = 'C:/Users/klever.robalino/Desktop/Proyecto-Mutualista/backend-asistente/agentes/logs/logs_files'

# Ruta del archivo original (sin el prefijo 'primer_filtro_' ni el sufijo '.log')
file = 'prueba'
file_path = f'{output_dir}/{file}.txt'

# Nombres de los archivos de salida con el prefijo adecuado
output_file_name = f'primer_filtro_{file}.log'
filtered_output_file_name = f'segundo_filtro_{file}.log'

# Obtener la ruta completa de los archivos de salida
output_file_path = os.path.join(output_dir, output_file_name)
filtered_output_file_path = os.path.join(output_dir, filtered_output_file_name)

# Verificar si el directorio de salida existe, si no, crearlo
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Guardar el DataFrame en el archivo CSV (primer filtro)
df_processed.to_csv(output_file_path, index=False, sep=';', header=False, lineterminator='\n')
print(f'Archivo guardado en: {output_file_path}')

# Filtrar el archivo y guardarlo (segundo filtro)
df_filtered = filter_non_info(output_file_path, filtered_output_file_path)
print(f'Archivo filtrado guardado en: {filtered_output_file_path}')




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

# Definir las rutas de los archivos para el segundo filtro
input_file_path = 'segundo_filtro_server.log'
grouped_output_file_path = 'tercer_filtro_server.log'
sorted_output_file_path = 'cuarto_filtro_server.csv'

# Definir patrones de categorización
STRICT_PATTERNS = {
    'start_send': re.compile(r'inicia envio en .*'),
    'end_send': re.compile(r'fin envio en .*'),
    'error': re.compile(r'ERROR|Error|error en .*'),
    'warn': re.compile(r'WARN|Warn|warn en .*'),
    # Añadir más patrones específicos según sea necesario
}

LAX_PATTERNS = {
    'start_send': re.compile(r'inicia envio'),
    'end_send': re.compile(r'fin envio'),
    'error': re.compile(r'ERROR|Error|error'),
    'warn': re.compile(r'WARN|Warn|warn'),
    # Añadir más patrones menos específicos según sea necesario
}

# Lista de niveles de prioridad (ordenada por prioridad)
PRIORITY_LEVELS = ['ERROR', 'WARN', 'INFO', 'DEBUG', 'TRACE']

def categorize_message(message, patterns):
    for category, pattern in patterns.items():
        if pattern.search(message):
            return category
    return 'other'

def manual_read_and_process(input_file_path, patterns):
    data = []
    with open(input_file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        for line in tqdm(lines, desc="Leyendo y procesando archivo"):
            parts = line.strip().split(';')
            if len(parts) == 5:
                parts.append(categorize_message(parts[3], patterns))  # Categorizar el mensaje
                data.append(parts)
    
    # Convertir la lista a un DataFrame
    df = pd.DataFrame(data, columns=['line_number', 'time', 'level', 'message', 'details', 'category'])
    return df

def limit_length(text, max_length=30000):
    # Limitar la longitud del texto a max_length caracteres
    return text if len(text) <= max_length else text[:max_length]

def priority_sort_key(level):
    return PRIORITY_LEVELS.index(level) if level in PRIORITY_LEVELS else len(PRIORITY_LEVELS)

def group_and_aggregate(df, grouped_output_file_path, sorted_output_file_path):
    # Concatenar mensaje y detalles, y limitar a 30,000 caracteres
    df['details'] = df.apply(lambda row: row['message'] + ' ' + row['details'], axis=1)
    df['details'] = df['details'].apply(limit_length)
    df['message'] = df['message'].apply(limit_length)

    # Agrupar por categoría y tipo de nivel
    grouped_data = []
    for name, group in tqdm(df.groupby(['category', 'level']), desc="Agrupando datos"):
        count = len(group)
        last_time = group['time'].iloc[-1]
        line_numbers = ':'.join(group['line_number'].astype(str))
        line_numbers = limit_length(line_numbers)  # Limitar longitud de line_numbers
        details = group['details'].iloc[-1]
        message = group['message'].iloc[-1]
        grouped_data.append([name[0], name[1], count, last_time, line_numbers, details, message])

    df_grouped = pd.DataFrame(grouped_data, columns=['category', 'level', 'count', 'last_time', 'line_numbers', 'details', 'message'])

    # Reemplazar comillas vacías en la columna details
    df_grouped['details'] = df_grouped['details'].replace('', 'Sin detalles')

    # Guardar el DataFrame agrupado en un nuevo archivo
    df_grouped.to_csv(grouped_output_file_path, index=False, sep=';', header=True, lineterminator='\n')
    print('Se imprimió el archivo agrupado:', grouped_output_file_path)

    # Ordenar por prioridad (tipo de nivel) y cantidad de repeticiones
    df_sorted = df_grouped.sort_values(by=['level', 'count'], key=lambda x: x.map(priority_sort_key) if x.name == 'level' else -x)
    df_sorted = df_sorted[['count', 'level', 'message', 'line_numbers', 'details']]
    df_sorted.to_csv(sorted_output_file_path, index=False, sep=';', header=True, lineterminator='\n')
    print('Se imprimió el archivo ordenado:', sorted_output_file_path)

def main():
    # Leer y procesar el archivo original
    lines = read_and_replace(file_path)

    # Etiquetar las líneas
    df_labeled = label_lines(lines)

    # Añadir delimitadores internos y concatenar detalles
    df_processed = add_delimiters(df_labeled)

    # Guardar el DataFrame resultante en un nuevo archivo .log con columnas separadas por punto y coma
    df_processed.to_csv(output_file_path, index=False, sep=';', header=False, lineterminator='\n')

    print('Se imprimió el archivo inicial:', output_file_path)

    # Filtrar y guardar las líneas que no son INFO en un nuevo archivo
    filter_non_info(output_file_path, filtered_output_file_path)

    print('Se imprimió el archivo filtrado sin INFO:', filtered_output_file_path)

    #Segunda parte del proceso ***************************

    precision = 1  # Ajustar la precisión según sea necesario
    patterns = STRICT_PATTERNS if precision < 1.0 else LAX_PATTERNS

    # Leer y procesar manualmente el archivo
    df = manual_read_and_process(input_file_path, patterns)

    # Agrupar y agregar
    group_and_aggregate(df, grouped_output_file_path, sorted_output_file_path)

if __name__ == '__main__':
    main()

