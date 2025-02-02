import pandas as pd
from sqlalchemy import create_engine, inspect, text
import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta
import time
import numpy as np

# Verbesserte Konfigurationskonstanten
DB_CONFIG = {
    'host': 'localhost',
    'database': 'examdb',
    'user': 'postgres',
    'password': '123456',
    'port': 5432  # Expliziter Port
}
DEFAULT_DATE = '2024-01-24'
PREVIEW_LIMIT = 5

# Verbesserte Datenbankverbindung mit Connection Pooling
@st.cache_resource
def get_database_connection():
    """Erstellt und cached die Datenbankverbindung mit Connection Pooling"""
    try:
        engine = create_engine(
            f'postgresql://{DB_CONFIG["user"]}:{DB_CONFIG["password"]}@{DB_CONFIG["host"]}:{DB_CONFIG["port"]}/{DB_CONFIG["database"]}',
            pool_size=5,  # Optimale Poolgröße
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800  # Verbindungen nach 30 Minuten recyclen
        )
        return engine
    except Exception as e:
        st.error(f"Datenbankverbindung fehlgeschlagen: {str(e)}")
        return None

@st.cache_data(ttl=300)  # Cache für 5 Minuten
def get_sorted_tables(_engine):
    """Cached Funktion zum Abrufen der sortierten Tabellenliste"""
    with _engine.connect() as conn:  # Stellt sicher, dass die Verbindung geschlossen wird
        inspector = inspect(_engine)
        return sorted(inspector.get_table_names())

# Optimierte Datenabfrage mit Chunking
@st.cache_data(ttl=300)
def load_data(_engine, table_name, chunk_size=1000):
    """Lädt Daten in Chunks für bessere Performance"""
    try:
        chunks = []
        with _engine.connect() as conn:
            for chunk_df in pd.read_sql(
                f"SELECT * FROM {table_name}",
                conn,
                chunksize=chunk_size
            ):
                chunks.append(chunk_df)
        return pd.concat(chunks) if chunks else pd.DataFrame()
    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {str(e)}")
        return pd.DataFrame()

@st.cache_data
def load_preview_data(_engine, table_name):
    """Lädt und cached Vorschaudaten"""
    try:
        with _engine.connect() as conn:
            # Prüfe ob Tabelle Daten enthält
            count_query = text(f"SELECT COUNT(*) FROM {table_name}")
            row_count = conn.execute(count_query).scalar()
            
            if row_count == 0:
                st.info(f"Die Tabelle '{table_name}' ist leer.")
                return pd.DataFrame(), pd.DataFrame({'total_rows': [0], 'unique_indices': [0], 'max_index': [0]}), \
                       pd.DataFrame({'min_date': ['Kein Datum'], 'max_date': ['Kein Datum']})
            
            # Vorschau der Daten
            preview_query = text(f"""
                SELECT * FROM {table_name} 
                ORDER BY date, time, index
                LIMIT :limit
            """)
            df = pd.read_sql(preview_query, conn, params={'limit': PREVIEW_LIMIT})
            
            # Statistiken
            stats_query = text(f"""
                SELECT 
                    COUNT(*) as total_rows,
                    COUNT(DISTINCT index) as unique_indices,
                    COUNT(DISTINCT index) as max_index
                FROM {table_name}
            """)
            stats = pd.read_sql(stats_query, conn)
            
            # Datumsbereich
            date_query = text(f"""
                SELECT 
                    MIN(date) as min_date,
                    MAX(date) as max_date
                FROM {table_name}
                WHERE date IS NOT NULL AND date != ''
            """)
            date_range = pd.read_sql(date_query, conn)
            
            # Wenn keine Datumswerte gefunden wurden
            if date_range['min_date'].iloc[0] is None:
                date_range = pd.DataFrame({'min_date': ['Kein Datum'], 'max_date': ['Kein Datum']})
            
            return df, stats, date_range
            
    except Exception as e:
        st.error(f"Fehler beim Laden der Vorschau: {str(e)}")
        st.error(f"Details: {type(e).__name__}: {str(e)}")
        return None, None, None

def format_preview_data(df, stats, date_range):
    """Formatiert die Vorschaudaten für die Anzeige"""
    try:
        if df is None or stats is None or date_range is None:
            return
            
        st.subheader("Tabellenvorschau")
        if df.empty:
            st.info("Keine Daten verfügbar")
        else:
            st.dataframe(df, use_container_width=True)
        
        # Metriken in Spalten anzeigen
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_rows = int(stats.iloc[0]['total_rows'])
            st.metric(
                "Gesamtzeilen",
                format_number(total_rows),
                help=f"Exakte Anzahl: {total_rows:,}"
            )
        
        with col2:
            unique_indices = int(stats.iloc[0]['unique_indices'])
            st.metric(
                "Unique Indizes",
                str(unique_indices),
                help="Anzahl unterschiedlicher Indizes"
            )
        
        with col3:
            min_date = date_range.iloc[0]['min_date']
            st.metric(
                "Erster Tag",
                min_date if min_date != 'Kein Datum' else "-"
            )
        
        with col4:
            max_date = date_range.iloc[0]['max_date']
            st.metric(
                "Letzter Tag",
                max_date if max_date != 'Kein Datum' else "-"
            )
            
    except Exception as e:
        st.error(f"Fehler bei der Formatierung der Vorschau: {str(e)}")

def create_visualization(df, selected_table, options=None):
    """Erstellt die Datenvisualisierung mit erweiterten Optionen"""
    try:
        # Standardoptionen, falls keine übergeben wurden
        if options is None:
            options = {
                'remove_outliers': False,
                'outlier_threshold': 3,
                'show_min_max': False,
                'show_mean': False,
                'show_trend': False,
                'line_type': 'lines+markers',
                'point_size': 8,
                'line_width': 2
            }
        
        # Kopie des Dataframes erstellen und Datentypen konvertieren
        plot_df = df.copy()
        plot_df['value'] = pd.to_numeric(plot_df['value'], errors='coerce')
        plot_df['index'] = pd.to_numeric(plot_df['index'], errors='coerce')
        plot_df['time'] = pd.to_datetime(plot_df['date'] + ' ' + plot_df['time'])
        
        # Ausreißer entfernen wenn gewünscht
        if options['remove_outliers']:
            for idx in plot_df['index'].unique():
                mask = plot_df['index'] == idx
                values = plot_df.loc[mask, 'value']
                if not values.empty:
                    Q1 = values.quantile(0.25)
                    Q3 = values.quantile(0.75)
                    IQR = Q3 - Q1
                    threshold = options['outlier_threshold']
                    outlier_mask = (values < Q1 - threshold * IQR) | (values > Q3 + threshold * IQR)
                    plot_df.loc[mask & outlier_mask, 'value'] = None
        
        # Erstelle Grundvisualisierung
        fig = px.scatter(plot_df, 
                        x='time',
                        y='value',
                        color='index',
                        title=f'Wertverlauf für {selected_table}')
        
        # Füge Linien hinzu wenn gewünscht
        for idx in plot_df['index'].unique():
            df_idx = plot_df[plot_df['index'] == idx]
            
            # Hauptlinie
            fig.add_scatter(
                x=df_idx['time'],
                y=df_idx['value'],
                name=f'Index {idx}',
                mode=options['line_type'],
                line=dict(width=options['line_width']),
                marker=dict(size=options['point_size']),
                showlegend=True
            )
            
            if options['show_min_max']:
                # Minimum und Maximum
                min_val = df_idx['value'].min()
                max_val = df_idx['value'].max()
                min_time = df_idx.loc[df_idx['value'].idxmin(), 'time']
                max_time = df_idx.loc[df_idx['value'].idxmax(), 'time']
                
                fig.add_scatter(
                    x=[min_time],
                    y=[min_val],
                    name=f'Min (Index {idx})',
                    mode='markers',
                    marker=dict(
                        symbol='star',
                        size=15,
                        color='blue'
                    ),
                    showlegend=True
                )
                
                fig.add_scatter(
                    x=[max_time],
                    y=[max_val],
                    name=f'Max (Index {idx})',
                    mode='markers',
                    marker=dict(
                        symbol='star',
                        size=15,
                        color='red'
                    ),
                    showlegend=True
                )
            
            if options['show_mean']:
                # Mittelwertlinie
                mean_val = df_idx['value'].mean()
                fig.add_hline(
                    y=mean_val,
                    line_dash="dash",
                    line_color="gray",
                    annotation_text=f"Mittelwert (Index {idx}): {mean_val:.2f}",
                    annotation_position="top right"
                )
            
            if options['show_trend']:
                # Trendlinie
                z = np.polyfit(range(len(df_idx)), df_idx['value'], 1)
                p = np.poly1d(z)
                fig.add_scatter(
                    x=df_idx['time'],
                    y=p(range(len(df_idx))),
                    name=f'Trend (Index {idx})',
                    mode='lines',
                    line=dict(dash='dot'),
                    showlegend=True
                )
        
        # Layout anpassen
        fig.update_layout(
            title=dict(
                text=f"Wertverlauf für {selected_table}",
                font=dict(size=24, color='#1a1a1a')
            ),
            xaxis_title=dict(
                text="Zeit",
                font=dict(size=14, color='#1a1a1a')
            ),
            yaxis_title=dict(
                text="Messwert",
                font=dict(size=14, color='#1a1a1a')
            ),
            hovermode='closest',
            showlegend=True,
            legend=dict(
                title=dict(
                    text="Datenpunkte",
                    font=dict(size=16, color='#1a1a1a')
                ),
                font=dict(size=12, color='#1a1a1a'),
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='rgba(0, 0, 0, 0.2)',
                borderwidth=1
            ),
            height=800,
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(
                type='date',
                rangeslider=dict(visible=True),
                rangeslider_thickness=0.05,
                gridcolor='lightgrey',
                showgrid=True,
                tickfont=dict(color='#1a1a1a')
            ),
            yaxis=dict(
                gridcolor='lightgrey',
                showgrid=True,
                tickfont=dict(color='#1a1a1a')
            ),
            dragmode='pan'
        )
        
        return fig
    except Exception as e:
        st.error(f"Fehler bei der Visualisierung: {str(e)}")
        return None

def process_csv_data(uploaded_file):
    """Verarbeitet CSV-Daten"""
    try:
        # Debug-Ausgabe
        st.write("CSV Inhalt (erste paar Zeilen):")
        content_preview = uploaded_file.read(1024).decode()  # Erste 1024 Bytes lesen
        st.code(content_preview)
        uploaded_file.seek(0)  # Zurück zum Anfang der Datei
        
        # CSV einlesen mit expliziten Datentypen
        df = pd.read_csv(
            uploaded_file,
            header=None,
            names=['index', 'timestamp', 'value'],
            dtype={
                'index': str,
                'timestamp': str,
                'value': str
            }
        )
        
        st.write("Gelesene Daten vor Verarbeitung:", df.head())
        
        # Timestamp in date und time aufteilen
        df['timestamp'] = pd.to_datetime(df['timestamp'].str.strip())
        df['date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
        df['time'] = df['timestamp'].dt.strftime('%H:%M:%S')
        
        # Finale Daten vorbereiten
        result_df = df[['index', 'date', 'time', 'value']].copy()
        
        # Debug-Ausgabe der finalen Daten
        st.write("Finale Daten für Upload:", result_df.head())
        
        return result_df
    except Exception as e:
        st.error(f"Fehler bei der CSV-Verarbeitung: {str(e)}")
        st.error(f"Details: {type(e).__name__}: {str(e)}")
        return None

def create_multi_table_visualization(dfs_dict, line_width=2, line_style='solid', show_points=True):
    """Erstellt eine Visualisierung für mehrere Tabellen mit individuellen Farben"""
    try:
        # Vordefinierte Farben für die Tabellen
        colors = [
            '#1f77b4',  # Blau
            '#ff7f0e',  # Orange
            '#2ca02c',  # Grün
            '#d62728',  # Rot
            '#9467bd',  # Lila
            '#8c564b',  # Braun
            '#e377c2',  # Pink
            '#7f7f7f',  # Grau
            '#bcbd22',  # Olive
            '#17becf'   # Türkis
        ]
        
        # Line style mapping
        line_styles = {
            'solid': None,
            'dashed': 'dash',
            'dotted': 'dot',
            'dashdot': 'dashdot'
        }
        
        fig = px.scatter()  # Leere Figur erstellen
        
        # Für jede Tabelle eine eigene Farbe verwenden
        for idx, (table_name, df) in enumerate(dfs_dict.items()):
            color = colors[idx % len(colors)]  # Zyklische Farbauswahl
            
            # Konvertiere 'time' zu datetime, falls es ein String ist
            if isinstance(df['time'].iloc[0], str):
                df['time'] = pd.to_datetime(df['date'] + ' ' + df['time'])
            
            # Füge jede Tabelle als separate Trace hinzu
            fig.add_scatter(
                x=df['time'],
                y=df['value'],
                name=table_name,
                mode='lines+markers' if show_points else 'lines',
                line=dict(
                    color=color,
                    width=line_width,
                    dash=line_styles[line_style]
                ),
                marker=dict(
                    color=color,
                    size=8
                ),
                hovertemplate=(
                    f"<b>{table_name}</b><br>" +
                    "Zeit: %{x}<br>" +
                    "Spannung: %{y:.2f} V<br>" +
                    "<extra></extra>"
                )
            )
        
        # Layout anpassen
        fig.update_layout(
            title=dict(
                text="Vergleich aller Tabellen",
                font=dict(size=24, color='#1a1a1a')  # Dunklere Titelfarbe
            ),
            xaxis_title=dict(
                text="Zeit",
                font=dict(size=14, color='#1a1a1a')  # Dunklere Achsenbeschriftung
            ),
            yaxis_title=dict(
                text="Spannung (V)",
                font=dict(size=14, color='#1a1a1a')  # Dunklere Achsenbeschriftung
            ),
            hovermode='closest',
            showlegend=True,
            legend=dict(
                title=dict(
                    text="Tabellen",
                    font=dict(size=16, color='#1a1a1a')  # Dunklere Legendentitel
                ),
                font=dict(size=12, color='#1a1a1a'),  # Dunklere Legendeneinträge
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='rgba(0, 0, 0, 0.2)',
                borderwidth=1
            ),
            height=800,
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(
                rangeslider=dict(visible=True),
                rangeslider_thickness=0.05,
                gridcolor='lightgrey',
                showgrid=True,
                type='date',
                tickfont=dict(color='#1a1a1a')  # Dunklere Achsenbeschriftung
            ),
            yaxis=dict(
                gridcolor='lightgrey',
                showgrid=True,
                tickfont=dict(color='#1a1a1a')  # Dunklere Achsenbeschriftung
            ),
            dragmode='pan'
        )
        
        return fig
    except Exception as e:
        st.error(f"Fehler bei der Multi-Tabellen-Visualisierung: {str(e)}")
        return None

def delete_table(engine, table_name):
    """Löscht eine Tabelle aus der Postgres-Datenbank"""
    try:
        with engine.connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Fehler beim Löschen der Tabelle: {str(e)}")
        return False

def format_number(number):
    """Formatiert Zahlen in lesbares Format"""
    if number >= 1000000:
        return f"{number/1000000:.1f}M"
    elif number >= 1000:
        return f"{number/1000:.1f}K"
    else:
        return str(number)

# Hauptanwendung
def main():
    st.title("CSV zu PostgreSQL Uploader")
    
    engine = get_database_connection()
    if not engine:
        st.stop()
        
    existing_tables = get_sorted_tables(engine)
    
    # Sidebar
    with st.sidebar:
        st.header("Tabellenverwaltung")
        
        tab1, tab2 = st.tabs(["Neue Tabelle", "Tabelle löschen"])
        
        with tab1:
            # Neue Tabelle erstellen
            new_table_name = st.text_input("Name der neuen Tabelle")
            if st.button("Tabelle erstellen") and new_table_name:
                if new_table_name in existing_tables:
                    st.error(f"Tabelle '{new_table_name}' existiert bereits!")
                else:
                    try:
                        # Erstelle Tabelle mit korrekter Struktur
                        create_table_query = text(f"""
                            CREATE TABLE {new_table_name} (
                                index TEXT,
                                date TEXT,
                                time TEXT,
                                value TEXT
                            )
                        """)
                        with engine.connect() as conn:
                            conn.execute(create_table_query)
                            conn.commit()
                        st.success(f"Tabelle '{new_table_name}' wurde erstellt!")
                        get_sorted_tables.clear()
                        time.sleep(0.1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Erstellen der Tabelle: {str(e)}")
        
        with tab2:
            # Tabelle löschen
            table_to_delete = st.selectbox(
                "Wählen Sie eine Tabelle zum Löschen",
                existing_tables if existing_tables else ["Keine Tabellen verfügbar"],
                key="delete_table_select"
            )
            
            # Session State für Löschbestätigung
            if 'delete_confirmation' not in st.session_state:
                st.session_state.delete_confirmation = False
            
            if table_to_delete != "Keine Tabellen verfügbar":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Tabelle löschen", type="primary", use_container_width=True):
                        st.session_state.delete_confirmation = True
                
                if st.session_state.delete_confirmation:
                    with col2:
                        if st.button("Bestätigen", type="secondary", use_container_width=True):
                            if delete_table(engine, table_to_delete):
                                st.success(f"Tabelle '{table_to_delete}' wurde gelöscht!")
                                st.session_state.delete_confirmation = False
                                get_sorted_tables.clear()
                                time.sleep(0.1)
                                st.rerun()

        # Tabellenauswahl
        st.subheader("Vorhandene Tabellen")
        selected_table = st.selectbox(
            "Wählen Sie eine Tabelle aus",
            existing_tables if existing_tables else ["Keine Tabellen verfügbar"]
        )

    if selected_table and selected_table != "Keine Tabellen verfügbar":
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Preview",           # Tab 1
            "View Data",         # Tab 2 (verschoben)
            "Upload",           # Tab 3 (verschoben)
            "Diagram",          # Tab 4 (verschoben)
            "Diagram2"          # Tab 5
        ])

        # Preview Tab
        with tab1:
            preview_df, stats, date_range = load_preview_data(engine, selected_table)
            format_preview_data(preview_df, stats, date_range)
        
        # View Data Tab
        with tab2:
            st.header("Gesamte Daten")
            
            # Automatisches Laden der Daten ohne Button
            try:
                query = text(f"""
                    SELECT * FROM {selected_table}
                    ORDER BY date, time, index
                """)
                df = pd.read_sql(query, engine)
                
                if df.empty:
                    st.info(f"Die Tabelle '{selected_table}' enthält keine Daten.")
                else:
                    # Zeige Anzahl der Datensätze
                    st.success(f"{len(df):,} Datensätze geladen")
                    
                    # Container für die Tabelle mit voller Breite
                    with st.container():
                        # Responsives Layout für die Tabelle
                        st.dataframe(
                            df,
                            use_container_width=True,
                            height=800,  # Noch größere Höhe
                            column_config={
                                "index": st.column_config.TextColumn(
                                    "Index",
                                    width="small",
                                    help="Messreihen-Index"
                                ),
                                "date": st.column_config.TextColumn(
                                    "Datum",
                                    width="small",
                                    help="Messdatum"
                                ),
                                "time": st.column_config.TextColumn(
                                    "Zeit",
                                    width="small",
                                    help="Messzeitpunkt"
                                ),
                                "value": st.column_config.NumberColumn(
                                    "Messwert",
                                    format="%.3f",
                                    help="Gemessener Wert"
                                )
                            },
                            hide_index=True
                        )
                    
                    # Export-Optionen und Statistiken
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.download_button(
                            "💾 Als CSV speichern",
                            df.to_csv(index=False),
                            f"{selected_table}_export.csv",
                            "text/csv",
                            key='download-csv',
                            use_container_width=True
                        )
                    
                    with col2:
                        with st.expander("📊 Statistiken anzeigen"):
                            stats_col1, stats_col2, stats_col3 = st.columns(3)
                            with stats_col1:
                                st.metric("Datensätze", f"{len(df):,}")
                            with stats_col2:
                                st.metric("Zeitraum", f"{df['date'].min()} bis {df['date'].max()}")
                            with stats_col3:
                                st.metric("Unique Indizes", f"{df['index'].nunique():,}")
                                
                            if pd.to_numeric(df['value'], errors='coerce').notna().any():
                                st.write("Messwert-Statistiken:")
                                st.dataframe(
                                    pd.to_numeric(df['value'], errors='coerce').describe().round(3),
                                    use_container_width=True
                                )
                                
            except Exception as e:
                st.error(f"Fehler beim Laden der Daten: {str(e)}")
                st.error(f"Details: {type(e).__name__}: {str(e)}")
        
        # Upload Tab (verschoben)
        with tab3:
            st.header(f"CSV-Daten in Tabelle '{selected_table}' hochladen")
            uploaded_files = st.file_uploader(
                "Wählen Sie CSV Dateien aus",
                type=['csv'],
                accept_multiple_files=True
            )
            
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    st.subheader(f"Verarbeite: {uploaded_file.name}")
                    df = process_csv_data(uploaded_file)
                    
                    if df is not None:
                        st.write("Vorschau der verarbeiteten Daten:")
                        st.dataframe(df.head())
                        
                        if st.button(
                            f"'{uploaded_file.name}' übertragen",
                            key=f"upload_{uploaded_file.name}",
                            use_container_width=True
                        ):
                            try:
                                # Daten in die Datenbank schreiben
                                with engine.connect() as conn:
                                    # Debug-Ausgabe der SQL-Anweisung
                                    insert_query = text(f"""
                                        INSERT INTO {selected_table} (index, date, time, value)
                                        VALUES (:index, :date, :time, :value)
                                    """)
                                    
                                    # Daten als Dictionary für den Upload vorbereiten
                                    data_to_insert = df.to_dict('records')
                                    
                                    # Einzeln einfügen mit Fehlerprotokollierung
                                    for record in data_to_insert:
                                        try:
                                            conn.execute(insert_query, record)
                                        except Exception as e:
                                            st.error(f"Fehler beim Einfügen des Datensatzes {record}: {str(e)}")
                                    
                                    conn.commit()
                                
                                st.success(f"Daten erfolgreich übertragen!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler beim Übertragen: {str(e)}")
                                st.error(f"Details: {type(e).__name__}: {str(e)}")
        
        # Diagram Tab (verschoben)
        with tab4:
            st.header("Datenvisualisierung")
            
            # Visualisierungsoptionen
            with st.expander("Visualisierungsoptionen"):
                col1, col2 = st.columns(2)
                with col1:
                    options = {
                        'remove_outliers': st.checkbox("Ausreißer entfernen"),
                        'outlier_threshold': st.slider(
                            "Ausreißer-Schwellwert (IQR-Faktor)", 
                            min_value=1.0, 
                            max_value=5.0, 
                            value=3.0, 
                            step=0.1
                        ),
                        'show_min_max': st.checkbox("Min/Max anzeigen"),
                        'show_mean': st.checkbox("Mittelwert anzeigen")
                    }
                with col2:
                    options.update({
                        'show_trend': st.checkbox("Trendlinie anzeigen"),
                        'line_type': st.selectbox(
                            "Linientyp",
                            options=['lines+markers', 'lines', 'markers'],
                            format_func=lambda x: {
                                'lines+markers': 'Linien + Punkte',
                                'lines': 'Nur Linien',
                                'markers': 'Nur Punkte'
                            }[x]
                        ),
                        'point_size': st.slider("Punktgröße", 2, 20, 8),
                        'line_width': st.slider("Linienbreite", 1, 10, 2)
                    })
            
            default_date = datetime.strptime(DEFAULT_DATE, '%Y-%m-%d')
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Startdatum", value=default_date)
            with col2:
                end_date = st.date_input("Enddatum", value=default_date)
            
            # Automatische Aktualisierung ohne Button
            try:
                # Konvertiere Datum in String-Format für PostgreSQL
                start_date_str = start_date.strftime('%Y-%m-%d')
                end_date_str = end_date.strftime('%Y-%m-%d')
                
                query = text(f"""
                    SELECT 
                        index::float as index,
                        date,
                        time,
                        value::float as value
                    FROM {selected_table}
                    WHERE date::date BETWEEN :start_date AND :end_date
                    ORDER BY date, time, index
                """)
                
                df = pd.read_sql(
                    query,
                    engine,
                    params={
                        'start_date': start_date_str,
                        'end_date': end_date_str
                    }
                )
                
                if not df.empty:
                    fig = create_visualization(df, selected_table, options)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.subheader("Statistiken")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write("Gesamtstatistiken:")
                            st.dataframe(df['value'].describe())
                        with col2:
                            st.write("Statistiken pro Index:")
                            st.dataframe(df.groupby('index')['value'].describe())
                else:
                    st.warning("Keine Daten für den ausgewählten Zeitraum gefunden.")
                        
            except Exception as e:
                st.error(f"Fehler beim Laden der Daten: {str(e)}")
                    
        # Diagram2 Tab
        with tab5:
            st.header("Vergleich aller Tabellen")
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    "Startdatum",
                    value=datetime.strptime(DEFAULT_DATE, '%Y-%m-%d'),
                    key="multi_start_date"
                )
            with col2:
                end_date = st.date_input(
                    "Enddatum",
                    value=datetime.strptime(DEFAULT_DATE, '%Y-%m-%d'),
                    key="multi_end_date"
                )
            
            # Mehrfachauswahl von Tabellen ohne Default-Wert
            selected_tables = st.multiselect(
                "Wählen Sie die zu vergleichenden Tabellen",
                options=existing_tables,
                default=None,  # Kein Default-Wert
                key="table_selector"
            )
            
            # Session State für ausgewählte Tabellen
            if 'previous_selection' not in st.session_state:
                st.session_state.previous_selection = []
            
            # Nur aktualisieren wenn sich die Auswahl geändert hat
            if selected_tables != st.session_state.previous_selection:
                st.session_state.previous_selection = selected_tables
            
            # Automatische Aktualisierung wenn Tabellen ausgewählt sind
            if selected_tables:
                try:
                    # Daten für alle ausgewählten Tabellen laden
                    dfs_dict = {}
                    start_date_str = start_date.strftime('%Y-%m-%d')
                    end_date_str = end_date.strftime('%Y-%m-%d')
                    
                    for table in selected_tables:
                        query = text(f"""
                            SELECT index, date, time, value 
                            FROM {table}
                            WHERE date::date BETWEEN :start_date AND :end_date
                            ORDER BY date, time, index
                        """)
                        
                        df = pd.read_sql(
                            query,
                            engine,
                            params={
                                'start_date': start_date_str,
                                'end_date': end_date_str
                            }
                        )
                        
                        if not df.empty:
                            dfs_dict[table] = df
                    
                    if dfs_dict:
                        fig = create_multi_table_visualization(dfs_dict)
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Statistiken für alle Tabellen
                            st.subheader("Vergleichende Statistiken")
                            stats_dfs = []
                            for table, df in dfs_dict.items():
                                stats = df['value'].describe()
                                stats.name = table
                                stats_dfs.append(stats)
                            
                            if stats_dfs:
                                combined_stats = pd.concat(stats_dfs, axis=1)
                                st.dataframe(combined_stats)
                    else:
                        st.warning("Keine Daten für den ausgewählten Zeitraum gefunden.")
                except Exception as e:
                    st.error(f"Fehler beim Laden der Vergleichsdaten: {str(e)}")
            else:
                st.info("Bitte wählen Sie mindestens eine Tabelle aus.")

if __name__ == "__main__":
    main()
