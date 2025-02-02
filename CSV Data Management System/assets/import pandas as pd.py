import pandas as pd
import re

def generate_table_structure(csv_file_path):
    # CSV einlesen (nur die erste Zeile)
    try:
        df = pd.read_csv(csv_file_path, nrows=0)
    except Exception as e:
        return f"Fehler beim Einlesen der Datei: {e}"

    # Spaltennamen auslesen
    columns = df.columns.tolist()

    # Tabelle und Spaltennamen vorschlagen
    table_name = "generated_table"
    sql_columns = []

    for col in columns:
        # Spaltennamen in SQL-konformes Format umwandeln
        col_clean = re.sub(r'\W+', '_', col.lower().strip())
        col_clean = col_clean if col_clean else "unnamed_column"
        sql_columns.append(f"{col_clean} TEXT")  # Standard: TEXT

    # SQL-Statement generieren
    sql_create_table = f"CREATE TABLE {table_name} (\n" + ",\n".join(sql_columns) + "\n);"
    return sql_create_table

# Beispielaufruf
csv_file_path = "beispiel.csv"  # Pfad zur CSV-Datei
print(generate_table_structure(csv_file_path))