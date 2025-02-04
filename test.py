import pandas as pd
from sqlalchemy import create_engine, inspect, text
import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta
import time
import numpy as np
import plotly.graph_objects as go
import re
import random

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
        
        # Metriken in kleineren Spalten anzeigen
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        
        with col1:
            total_rows = int(stats.iloc[0]['total_rows'])
            formatted_rows = (
                f"{total_rows:,.0f}" if total_rows < 1000 
                else f"{total_rows/1000:,.1f}K" if total_rows < 1000000 
                else f"{total_rows/1000000:,.1f}M"
            )
            st.metric(
                "Zeilen",
                formatted_rows,
                help=f"Gesamtanzahl: {total_rows:,}"
            )
        
        with col2:
            unique_indices = int(stats.iloc[0]['unique_indices'])
            formatted_indices = (
                f"{unique_indices}" if unique_indices < 1000 
                else f"{unique_indices/1000:.1f}K"
            )
            st.metric(
                "Indizes",
                formatted_indices,
                help=f"Unique Indizes: {unique_indices:,}"
            )
        
        with col3:
            min_date = date_range.iloc[0]['min_date']
            formatted_min_date = "-"
            if min_date and min_date != 'Kein Datum' and not pd.isna(min_date):
                try:
                    # Konvertiere String-Datum in datetime
                    date_obj = pd.to_datetime(min_date)
                    formatted_min_date = date_obj.strftime('%d.%m.%y')
                except:
                    formatted_min_date = min_date
            st.metric(
                "Start",
                formatted_min_date,
                help="Erster Messtag"
            )
        
        with col4:
            max_date = date_range.iloc[0]['max_date']
            formatted_max_date = "-"
            if max_date and max_date != 'Kein Datum' and not pd.isna(max_date):
                try:
                    # Konvertiere String-Datum in datetime
                    date_obj = pd.to_datetime(max_date)
                    formatted_max_date = date_obj.strftime('%d.%m.%y')
                except:
                    formatted_max_date = max_date
            st.metric(
                "Ende",
                formatted_max_date,
                help="Letzter Messtag"
            )
            
    except Exception as e:
        st.error(f"Fehler bei der Formatierung der Vorschau: {str(e)}")

def search_data_points(engine, table_name: str, search_params: dict) -> pd.DataFrame:
    """Sucht spezifische Datenpunkte in der Datenbank mit verbesserter Formatierung"""
    try:
        conditions = []
        params = {}
        
        # Index-Suche hinzufügen
        if search_params.get('index'):
            conditions.append("index = :search_index")
            params['search_index'] = search_params['index']
        
        # Bestehende Bedingungen...
        if search_params.get('date'):
            conditions.append("date::date = :search_date")
            params['search_date'] = search_params['date']
        
        if search_params.get('time'):
            try:
                time_str = search_params['time']
                if len(time_str.split(':')) == 2:
                    time_str += ':00'
                conditions.append("time::time = :search_time")
                params['search_time'] = time_str
            except Exception as e:
                st.error(f"Ungültiges Zeitformat. Bitte verwenden Sie HH:MM:SS: {str(e)}")
                return pd.DataFrame()
        
        if search_params.get('value') is not None:
            try:
                value = round(float(search_params['value']), 6)
                conditions.append("ABS(value::float - :search_value) < 1e-6")
                params['search_value'] = value
            except ValueError:
                st.error("Ungültiges Zahlenformat für den Suchwert")
                return pd.DataFrame()
        
        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        
        # Index in die Abfrage aufnehmen
        query = f"""
            SELECT 
                index,
                date::date as date,
                time::time as time,
                value::float as value
            FROM {table_name}
            WHERE {where_clause}
            ORDER BY date, time
        """
        
        with engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn, params=params)
            
            if df.empty:
                st.info("Keine Datenpunkte gefunden.")
            else:
                df['value'] = df['value'].round(6)
                df['time'] = df['time'].apply(lambda x: x.strftime('%H:%M:%S'))
                df['date'] = df['date'].apply(lambda x: x.strftime('%Y-%m-%d'))
            
            return df
            
    except Exception as e:
        st.error(f"Fehler bei der Suche: {str(e)}")
        return pd.DataFrame()

def create_visualization(df, selected_table, options=None, search_results=None):
    """Erstellt eine scrollbare Datenvisualisierung mit markierten Suchpunkten"""
    try:
        # Standardoptionen
        if options is None:
            options = {
                'line_type': 'lines+markers',
                'point_size': 6,
                'line_width': 2
            }
        
        # Datenaufbereitung
        plot_df = df.copy()
        
        # Konvertiere Datentypen
        plot_df['value'] = pd.to_numeric(plot_df['value'], errors='coerce')
        
        # Korrekte Konvertierung von Datum und Zeit zu datetime
        plot_df['datetime'] = pd.to_datetime(
            plot_df['date'].astype(str) + ' ' + plot_df['time'].astype(str),
            format='%Y-%m-%d %H:%M:%S'
        )
        
        # Erstelle Grundvisualisierung
        fig = go.Figure()

        # Füge Datenpunkte hinzu
        fig.add_trace(go.Scatter(
            x=plot_df['datetime'],
            y=plot_df['value'],
                mode=options['line_type'],
            name='Messwerte',
            line=dict(
                width=options['line_width'],
                color='#1f77b4'
            ),
            marker=dict(
                size=options['point_size'],
                color='#1f77b4'
            )
        ))

        # Suchresultate mit Index im Hover
        if search_results is not None and not search_results.empty:
            search_df = search_results.copy()
            search_df['datetime'] = pd.to_datetime(
                search_df['date'].astype(str) + ' ' + search_df['time'].astype(str)
            )
            
            fig.add_trace(go.Scatter(
                x=search_df['datetime'],
                y=search_df['value'],
                    mode='markers',
                name='Gefundene Punkte',
                    marker=dict(
                        symbol='star',
                        size=15,
                    color='red',
                    line=dict(color='black', width=1)
                ),
                hovertemplate="<b>Gefundene Punkte:</b><br>" +
                            "Index: %{customdata}<br>" +  # Index anzeigen
                            "Datum: %{x|%Y-%m-%d}<br>" +
                            "Zeit: %{x|%H:%M:%S}<br>" +
                            "Wert: %{y:.6f}<br>" +
                            "<extra></extra>",
                customdata=search_df['index']  # Index für Hover bereitstellen
            ))

        # Layout-Konfiguration mit Legende unter dem Titel
        fig.update_layout(
            title=dict(
                text=f"Zeitreihe für {selected_table}",
                x=0.5,
                y=0.95,  # Titel etwas nach unten verschieben
                font=dict(size=24, color='black')
            ),
            xaxis=dict(
                title=dict(
                    text="Zeitstempel",
                    font=dict(size=14, color='black')
                ),
                rangeslider=dict(visible=True),
                type='date',
                tickformat='%Y-%m-%d<br>%H:%M:%S',
                tickangle=0,
                gridcolor='lightgray',
                showgrid=True,
                tickfont=dict(
                    size=12, 
                    color='black'
                ),
                nticks=10
            ),
            yaxis=dict(
                title=dict(
                text="Messwert",
                    font=dict(size=14, color='black')
                ),
                gridcolor='lightgray',
                showgrid=True,
                fixedrange=False,
                tickfont=dict(size=12, color='black')
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='x unified',
            height=700,
            margin=dict(
                t=120,  # Top-Margin vergrößert für Titel und Legende
                b=100,  # Bottom
                l=80,   # Left
                r=50    # Right
            ),
            showlegend=True,
            legend=dict(
                orientation="h",     # horizontale Ausrichtung
                yanchor="bottom",   # Anker unten
                y=1.02,            # Position direkt unter dem Titel
                xanchor="center",   # zentriert
                x=0.5,             # mittig
                bgcolor='rgba(255, 255, 255, 0.8)',
                font=dict(size=12, color='black'),
                bordercolor='rgba(0, 0, 0, 0.2)',
                borderwidth=1
            )
        )

        # Zusätzliche Interaktionsoptionen
        fig.update_xaxes(rangeslider_thickness=0.05)  # Scrollbar-Höhe
        
        # Aktiviere Zoom und Pan
        fig.update_layout(
            dragmode='pan',  # Standard-Drag-Modus auf Pan setzen
            modebar=dict(
                orientation='v',
                bgcolor='rgba(255, 255, 255, 0.7)'
            ),
            updatemenus=[dict(
                type='buttons',
                showactive=False,
                buttons=[
                    dict(
                        label='Reset Zoom',
                        method='relayout',
                        args=[{'xaxis.autorange': True, 'yaxis.autorange': True}]
                    )
                ],
                pad={"r": 10, "t": 10},
                x=0.1,
                xanchor="right",
                y=1.1,
                yanchor="top"
            )]
        )
        
        return fig

    except Exception as e:
        st.error(f"Fehler bei der Visualisierung: {str(e)}")
        st.error(f"DataFrame Typen: {df.dtypes}")
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

def remove_outliers(df, threshold=3.0):
    """
    Entfernt Ausreißer aus dem DataFrame basierend auf der IQR-Methode
    
    Args:
        df: DataFrame mit 'datetime' und 'value' Spalten
        threshold: IQR-Faktor für die Ausreißererkennung (Standard: 3.0)
    
    Returns:
        DataFrame ohne Ausreißer, Anzahl der Ausreißer, untere und obere Grenze
    """
    df_clean = df.copy()
    
    # Berechne Q1, Q3 und IQR für die Werte
    Q1 = df_clean['value'].quantile(0.25)
    Q3 = df_clean['value'].quantile(0.75)
    IQR = Q3 - Q1
    
    # Definiere die Grenzen für Ausreißer
    lower_bound = Q1 - threshold * IQR
    upper_bound = Q3 + threshold * IQR
    
    # Markiere Ausreißer
    outliers_mask = (df_clean['value'] < lower_bound) | (df_clean['value'] > upper_bound)
    
    # Berechne die Anzahl der Ausreißer
    n_outliers = outliers_mask.sum()
    
    # Entferne Ausreißer
    df_clean = df_clean[~outliers_mask]
    
    return df_clean, n_outliers, lower_bound, upper_bound

def get_random_color():
    """Generiert eine zufällige, ansprechende Farbe"""
    # Vordefinierte, ansprechende Farben
    color_palette = [
            '#1f77b4',  # Blau
            '#ff7f0e',  # Orange
            '#2ca02c',  # Grün
            '#d62728',  # Rot
            '#9467bd',  # Lila
            '#8c564b',  # Braun
            '#e377c2',  # Pink
            '#7f7f7f',  # Grau
        '#bcbd22',  # Olivgrün
        '#17becf',  # Türkis
        '#aec7e8',  # Hellblau
        '#ffbb78',  # Hellorange
        '#98df8a',  # Hellgrün
        '#ff9896',  # Hellrot
        '#c5b0d5',  # Helllila
    ]
    return random.choice(color_palette)

def create_multi_table_visualization(dfs_dict, options):
    """Erstellt eine Visualisierung für mehrere Tabellen mit definierten Standardfarben"""
    try:
        fig = go.Figure()
        
        # Definierte Standardfarben (erste Farbe ist schwarz)
        default_colors = [
            '#000000',  # Schwarz für den ersten Graph
            '#1f77b4',  # Blau
            '#ff7f0e',  # Orange
            '#2ca02c',  # Grün
            '#d62728',  # Rot
            '#9467bd',  # Lila
            '#8c564b',  # Braun
            '#e377c2',  # Pink
            '#bcbd22',  # Olivgrün
            '#17becf',  # Türkis
        ]
        
        for idx, (table_name, df) in enumerate(dfs_dict.items()):
            # Verwende benutzerdefinierte Farbe oder Standardfarbe aus der Liste
            color = options['custom_colors'].get(table_name) or default_colors[idx % len(default_colors)]
            
            plot_df = df.copy()
            
            # Datenaufbereitung
            plot_df['datetime'] = pd.to_datetime(
                plot_df['date'].astype(str) + ' ' + plot_df['time'].astype(str)
            )
            plot_df['value'] = pd.to_numeric(plot_df['value'], errors='coerce')
            
            # Ausreißerbehandlung wenn aktiviert
            if options['remove_outliers']:
                plot_df_clean, n_outliers, lower_bound, upper_bound = remove_outliers(
                    plot_df, 
                    threshold=options['outlier_threshold']
                )
                
                # Zeige Informationen über entfernte Ausreißer
                st.info(f"""
                    **Ausreißeranalyse für {table_name}:**
                    - Entfernte Ausreißer: {n_outliers}
                    - Untere Grenze: {lower_bound:.6f}
                    - Obere Grenze: {upper_bound:.6f}
                """)
                
                # Zeige Ausreißer in separater Trace
                outliers_df = plot_df[~plot_df.index.isin(plot_df_clean.index)]
                if not outliers_df.empty:
                    fig.add_trace(go.Scatter(
                        x=outliers_df['datetime'],
                        y=outliers_df['value'],
                        mode='markers',
                        name=f'{table_name} (Ausreißer)',
                marker=dict(
                            symbol='x',
                            size=10,
                    color=color,
                            line=dict(width=2, color='red')
                ),
                hovertemplate=(
                            "<b>Ausreißer</b><br>" +
                            "Zeitpunkt: %{x}<br>" +
                            "Wert: %{y:.6f}<br>" +
                    "<extra></extra>"
                )
                    ))
                
                # Verwende bereinigte Daten für die Hauptvisualisierung
                plot_df = plot_df_clean
            
            # Hauptlinie mit angepasster Farbe
            fig.add_trace(go.Scatter(
                x=plot_df['datetime'],
                y=plot_df['value'],
                mode=options['line_type'],
                name=table_name,
                line=dict(width=options['line_width'], color=color),
                marker=dict(size=options['point_size'], color=color)
            ))
            
            # Alle statistischen Linien mit der gleichen Farbe aber unterschiedlicher Transparenz
            if options['show_min']:
                min_val = plot_df['value'].min()
                fig.add_trace(go.Scatter(
                    x=[plot_df['datetime'].iloc[0], plot_df['datetime'].iloc[-1]],
                    y=[min_val, min_val],
                    mode='lines',
                    name=f'{table_name} Min',
                    line=dict(dash='dash', width=1, color=color),
                    opacity=0.5
                ))
            
            if options['show_max']:
                max_val = plot_df['value'].max()
                fig.add_trace(go.Scatter(
                    x=[plot_df['datetime'].iloc[0], plot_df['datetime'].iloc[-1]],
                    y=[max_val, max_val],
                    mode='lines',
                    name=f'{table_name} Max',
                    line=dict(dash='dash', width=1, color=color),
                    opacity=0.5
                ))
            
            if options['show_mean']:
                mean_val = plot_df['value'].mean()
                fig.add_trace(go.Scatter(
                    x=[plot_df['datetime'].iloc[0], plot_df['datetime'].iloc[-1]],
                    y=[mean_val, mean_val],
                    mode='lines',
                    name=f'{table_name} Mittelwert',
                    line=dict(dash='dot', width=1, color=color),
                    opacity=0.5
                ))
            
            if options['show_median']:
                median_val = plot_df['value'].median()
                fig.add_trace(go.Scatter(
                    x=[plot_df['datetime'].iloc[0], plot_df['datetime'].iloc[-1]],
                    y=[median_val, median_val],
                    mode='lines',
                    name=f'{table_name} Median',
                    line=dict(dash='dashdot', width=1, color=color),
                    opacity=0.5
                ))

            # Trendlinie
            if options['show_trend']:
                x_numeric = np.arange(len(plot_df))
                z = np.polyfit(x_numeric, plot_df['value'], 1)
                p = np.poly1d(z)
                trend_line = p(x_numeric)
                fig.add_trace(go.Scatter(
                    x=plot_df['datetime'],
                    y=trend_line,
                    mode='lines',
                    name=f'{table_name} Trend',
                    line=dict(dash='solid', width=1, color=color),
                    opacity=0.5
                ))

            # Standardabweichung
            if options['show_std']:
                std_val = plot_df['value'].std()
                mean_val = plot_df['value'].mean()
                fig.add_trace(go.Scatter(
                    x=plot_df['datetime'],
                    y=[mean_val + std_val] * len(plot_df),
                    mode='lines',
                    name=f'{table_name} +σ',
                    line=dict(dash='dot', width=1, color=color),
                    opacity=0.5
                ))
                fig.add_trace(go.Scatter(
                    x=plot_df['datetime'],
                    y=[mean_val - std_val] * len(plot_df),
                    mode='lines',
                    name=f'{table_name} -σ',
                    line=dict(dash='dot', width=1, color=color),
                    opacity=0.5
                ))

            # Perzentile
            if options['show_percentiles']:
                percentile_range = options['percentile_range']
                lower_percentile = plot_df['value'].quantile(percentile_range/100)
                upper_percentile = plot_df['value'].quantile(1 - percentile_range/100)
                fig.add_trace(go.Scatter(
                    x=plot_df['datetime'],
                    y=[upper_percentile] * len(plot_df),
                    mode='lines',
                    name=f'{table_name} {100-percentile_range}. Perzentil',
                    line=dict(dash='dot', width=1, color=color),
                    opacity=0.5
                ))
                fig.add_trace(go.Scatter(
                    x=plot_df['datetime'],
                    y=[lower_percentile] * len(plot_df),
                    mode='lines',
                    name=f'{table_name} {percentile_range}. Perzentil',
                    line=dict(dash='dot', width=1, color=color),
                    opacity=0.5
                ))

            # Gleitender Durchschnitt
            if options['moving_average']:
                window = 5  # Fenstergröße für gleitenden Durchschnitt
                ma = plot_df['value'].rolling(window=window, center=True).mean()
                fig.add_trace(go.Scatter(
                    x=plot_df['datetime'],
                    y=ma,
                    mode='lines',
                    name=f'{table_name} Gleitender Durchschnitt',
                    line=dict(dash='solid', width=1, color=color),
                    opacity=0.5
                ))

        # Layout-Konfiguration
        fig.update_layout(
            title=dict(
                text="Vergleich der ausgewählten Tabellen",
                x=0.5,
                y=0.95,
                font=dict(size=24, color='black')
            ),
            xaxis=dict(
                title=dict(
                    text="Zeitstempel",
                    font=dict(size=14, color='black')
                ),
                rangeslider=dict(visible=True),
                type='date',
                tickformat='%Y-%m-%d<br>%H:%M:%S',
                tickangle=0,
                gridcolor='lightgray',
                showgrid=True,
                tickfont=dict(size=12, color='black')
            ),
            yaxis=dict(
                title=dict(
                    text="Messwert",
                    font=dict(size=14, color='black')
                ),
                gridcolor='lightgray',
                showgrid=True,
                tickfont=dict(size=12, color='black')
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='x unified',
            height=700,
            margin=dict(
                t=120,
                b=100,
                l=80,
                r=50
            ),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                bgcolor='rgba(255, 255, 255, 0.8)',
                font=dict(size=12, color='black'),
                bordercolor='rgba(0, 0, 0, 0.2)',
                borderwidth=1
            )
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

def show_current_table(table_name):
    """Zeigt die aktuelle Tabelle als Überschrift an"""
    st.markdown(f"### 📊 Aktuelle Tabelle: `{table_name}`")

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
                        # Cache leeren statt rerun
                        get_sorted_tables.clear()
                        existing_tables = get_sorted_tables(engine)
                    except Exception as e:
                        st.error(f"Fehler beim Erstellen der Tabelle: {str(e)}")
        
        with tab2:
            table_to_delete = st.selectbox(
                "Wählen Sie eine Tabelle zum Löschen",
                existing_tables if existing_tables else ["Keine Tabellen verfügbar"],
                key="delete_table_select"
            )
            
            if table_to_delete != "Keine Tabellen verfügbar":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Tabelle löschen", type="primary", use_container_width=True):
                        st.session_state.delete_confirmation = True
                
                if st.session_state.get('delete_confirmation', False):
                    with col2:
                        if st.button("Bestätigen", type="secondary", use_container_width=True):
                            if delete_table(engine, table_to_delete):
                                st.success(f"Tabelle '{table_to_delete}' wurde gelöscht!")
                                st.session_state.delete_confirmation = False
                                # Cache leeren statt rerun
                                get_sorted_tables.clear()
                                existing_tables = get_sorted_tables(engine)

        st.subheader("Vorhandene Tabellen")
        selected_table = st.selectbox(
            "Wählen Sie eine Tabelle aus",
            existing_tables if existing_tables else ["Keine Tabellen verfügbar"]
        )

    if selected_table and selected_table != "Keine Tabellen verfügbar":
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Preview",
            "View Data",
            "Upload",
            "Diagram - Single",
            "Diagram - Multi"
        ])

        # Preview Tab
        with tab1:
            show_current_table(selected_table)
            preview_df, stats, date_range = load_preview_data(engine, selected_table)
            format_preview_data(preview_df, stats, date_range)
        
        # View Data Tab
        with tab2:
            show_current_table(selected_table)
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
                                    format="%.20f",
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
        
        # Upload Tab
        with tab3:
            show_current_table(selected_table)
            st.header("CSV-Daten hochladen")
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
                        
                        upload_key = f"upload_{uploaded_file.name}"
                        if st.button(f"'{uploaded_file.name}' übertragen", key=upload_key):
                            try:
                                with engine.connect() as conn:
                                    insert_query = text(f"""
                                        INSERT INTO {selected_table} (index, date, time, value)
                                        VALUES (:index, :date, :time, :value)
                                    """)
                                    
                                    # Batch-Insert für bessere Performance
                                    data_to_insert = df.to_dict('records')
                                    conn.execute(insert_query, data_to_insert)
                                    conn.commit()
                                
                                st.success(f"Daten erfolgreich übertragen!")
                                # Cache für die Vorschau leeren
                                load_preview_data.clear()
                            except Exception as e:
                                st.error(f"Fehler beim Übertragen: {str(e)}")
        
        # Diagram Tab
        with tab4:
            show_current_table(selected_table)
            st.header("Datenvisualisierung")
            
            default_date = datetime.strptime(DEFAULT_DATE, '%Y-%m-%d')
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Startdatum", value=default_date)
            with col2:
                end_date = st.date_input("Enddatum", value=default_date)
            
            try:
                # Konvertiere Datum in String-Format für PostgreSQL
                start_date_str = start_date.strftime('%Y-%m-%d')
                end_date_str = end_date.strftime('%Y-%m-%d')
                
                # Verbesserte Caching-Funktion mit stabilem Hash-Key
                @st.cache_data(ttl=300)
                def get_chart_data(table_name: str, start_date: str, end_date: str) -> pd.DataFrame:
                    query = f"""
                    SELECT 
                            date::date as date,
                            time::time as time,
                        value::float as value
                        FROM {table_name}
                    WHERE date::date BETWEEN :start_date AND :end_date
                        ORDER BY date, time
                    """
                    with engine.connect() as conn:
                        df = pd.read_sql_query(
                            text(query),
                            conn,
                    params={
                                'start_date': start_date,
                                'end_date': end_date
                    }
                )
                    return df

                # Daten abrufen
                df = get_chart_data(selected_table, start_date_str, end_date_str)
                
                if not df.empty:
                    # Visualisierungsoptionen
                    with st.expander("Visualisierungsoptionen"):
                        options = {
                            'line_type': st.selectbox(
                                "Darstellungsart",
                                options=['lines+markers', 'lines', 'markers'],
                                format_func=lambda x: {
                                    'lines+markers': 'Linien + Punkte',
                                    'lines': 'Nur Linien',
                                    'markers': 'Nur Punkte'
                                }[x]
                            ),
                            'point_size': st.slider("Punktgröße", 2, 15, 6),
                            'line_width': st.slider("Linienbreite", 1, 5, 2)
                        }

                    # Initialisiere search_results
                    search_results = None

                    # Suchbereich
                    with st.expander("🔍 Datenpunkte suchen"):
                        search_col1, search_col2 = st.columns(2)
                        
                        with search_col1:
                            search_index = st.text_input(
                                "Index suchen",
                                value="",
                                key="search_index",
                                help="Geben Sie den Index ein"
                            )
                        
                        search_col3, search_col4, search_col5 = st.columns(3)
                        
                        with search_col3:
                            search_date = st.date_input(
                                "Datum suchen",
                                value=None,
                                key="search_date",
                                help="Format: YYYY-MM-DD"
                            )
                        
                        with search_col4:
                            search_time = st.text_input(
                                "Zeit suchen (HH:MM:SS)",
                                value="",
                                key="search_time",
                                help="Format: HH:MM:SS oder HH:MM"
                            )
                            
                            if search_time and not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$', search_time):
                                st.error("Ungültiges Zeitformat. Bitte verwenden Sie HH:MM:SS oder HH:MM")
                                search_time = None
                        
                        with search_col5:
                            search_value = st.number_input(
                                "Wert suchen",
                                value=None,
                                format="%.6f",
                                step=0.000001,
                                key="search_value",
                                help="Dezimalzahl mit bis zu 6 Nachkommastellen"
                            )
                    
                    # Suchparameter sammeln
                    search_params = {}
                    if search_index:
                        search_params['index'] = search_index
                    if search_date:
                        search_params['date'] = search_date.strftime('%Y-%m-%d')
                    if search_time:
                        search_params['time'] = search_time
                    if search_value is not None:
                        search_params['value'] = search_value

                    # Suchergebnisse abrufen
                    if search_params:
                        search_results = search_data_points(engine, selected_table, search_params)
                        if not search_results.empty:
                            st.success(f"{len(search_results)} Datenpunkte gefunden")
                            with st.expander("Gefundene Datenpunkte"):
                                st.dataframe(
                                    search_results,
                                    column_config={
                                        "date": st.column_config.TextColumn("Datum", width="medium"),
                                        "time": st.column_config.TextColumn("Zeit", width="medium"),
                                        "value": st.column_config.NumberColumn(
                                            "Wert",
                                            format="%.6f",
                                            width="medium"
                                        )
                                    }
                                )

                    # Visualisierung erstellen
                    fig = create_visualization(df, selected_table, options, search_results)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                        
                        with st.expander("Statistiken"):
                            st.dataframe(df['value'].describe())
                else:
                    st.warning("Keine Daten für den ausgewählten Zeitraum gefunden.")
                        
            except Exception as e:
                st.error(f"Fehler beim Laden der Daten: {str(e)}")
                    
        # Diagram2 Tab
        with tab5:
            # Zeige die aktuelle Tabelle und den Vergleichsbereich
            st.header("Vergleich mehrerer Tabellen")
            
            # Mehrfachauswahl von Tabellen
            selected_tables_for_comparison = st.multiselect(
                "Wählen Sie die zu vergleichenden Tabellen",
                options=existing_tables,
                default=[selected_table] if selected_table != "Keine Tabellen verfügbar" else None,
                key="comparison_table_selector"
            )
            
            # Datumsauswahl
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
            
            # Datenverarbeitung und Visualisierung
            if selected_tables_for_comparison:
                try:
                    # Daten für alle ausgewählten Tabellen laden
                    dfs_dict = {}
                    start_date_str = start_date.strftime('%Y-%m-%d')
                    end_date_str = end_date.strftime('%Y-%m-%d')
                    
                    # Fortschrittsbalken für das Laden der Daten
                    progress_text = "Lade Daten..."
                    progress_bar = st.progress(0)
                    
                    for idx, table in enumerate(selected_tables_for_comparison):
                        query = f"""
                        SELECT 
                            date::date as date,
                            time::time as time,
                            value::float as value
                            FROM {table}
                            WHERE date::date BETWEEN :start_date AND :end_date
                        ORDER BY date, time
                        """
                        with engine.connect() as conn:
                            df = pd.read_sql_query(
                                text(query),
                                conn,
                            params={
                                'start_date': start_date_str,
                                'end_date': end_date_str
                            }
                        )
                        if not df.empty:
                            dfs_dict[table] = df
                        
                        # Update Fortschrittsbalken
                        progress = (idx + 1) / len(selected_tables_for_comparison)
                        progress_bar.progress(progress)
                    
                    # Entferne Fortschrittsbalken nach dem Laden
                    progress_bar.empty()
                    
                    if dfs_dict:
                        # Container für das Diagramm
                        chart_container = st.container()
                        
                        # Visualisierungsoptionen unter dem Diagramm
                        with st.expander("📊 Visualisierungsoptionen"):
                            # Tabs für verschiedene Optionskategorien
                            viz_tab1, viz_tab2, viz_tab3 = st.tabs([
                                "⚙️ Grundeinstellungen", 
                                "📊 Statistische Anzeigen", 
                                "📈 Erweiterte Analysen"
                            ])
                            
                            # Tab 1: Grundeinstellungen
                            with viz_tab1:
                                col1, col2 = st.columns(2)
                                with col1:
                                    options = {
                                        'line_type': st.selectbox(
                                            "Linientyp",
                                            options=['lines+markers', 'lines', 'markers'],
                                            format_func=lambda x: {
                                                'lines+markers': 'Linien + Punkte',
                                                'lines': 'Nur Linien',
                                                'markers': 'Nur Punkte'
                                            }[x],
                                            key="multi_line_type"
                                        ),
                                        'point_size': st.slider(
                                            "Punktgröße", 
                                            2, 20, 8, 
                                            key="multi_point_size"
                                        ),
                                        'line_width': st.slider(
                                            "Linienbreite", 
                                            1, 10, 2, 
                                            key="multi_line_width"
                                        ),
                                        'color_scheme': st.selectbox(
                                            "Farbschema",
                                            options=[
                                                'Set1', 'Set2', 'Set3', 'Paired', 'Dark2',
                                                'Pastel1', 'Pastel2', 'Bold', 'Safe'
                                            ],
                                            format_func=lambda x: {
                                                'Set1': 'Standard',
                                                'Set2': 'Gedämpft',
                                                'Set3': 'Pastelltöne',
                                                'Paired': 'Paarweise',
                                                'Dark2': 'Dunkel',
                                                'Pastel1': 'Pastell Hell',
                                                'Pastel2': 'Pastell Dunkel',
                                                'Bold': 'Kräftig',
                                                'Safe': 'Farbenblind-freundlich'
                                            }[x],
                                            key="multi_color_scheme"
                                        ),
                                        'custom_colors': {},
                                        'default_colors': {}
                                    }
                                
                                with col2:
                                    options.update({
                                        'remove_outliers': st.checkbox(
                                            "Ausreißer entfernen", 
                                            key="multi_outliers"
                                        ),
                                        'outlier_threshold': st.slider(
                                            "Ausreißer-Schwellwert", 
                                            1.0, 5.0, 3.0, 
                                            0.1,
                                            key="multi_threshold",
                                            help="IQR-Faktor für Ausreißererkennung"
                                        )
                                    })
                                    
                                    # Individuelle Farben für jede ausgewählte Tabelle
                                    if selected_tables_for_comparison:
                                        st.markdown("##### 🎨 Individuelle Farben")
                                        st.markdown("(Standardmäßig wird für jeden Graph eine zufällige Farbe gewählt)")
                                        for table in selected_tables_for_comparison:
                                            color = st.color_picker(
                                                f"Farbe für {table}",
                                                key=f"color_{table}",
                                                help=f"Wählen Sie eine individuelle Farbe für {table}"
                                            )
                                            if color != '#000000':  # Nur wenn eine Farbe ausgewählt wurde
                                                options['custom_colors'][table] = color

                            # Tab 2: Statistische Anzeigen
                            with viz_tab2:
                                col1, col2 = st.columns(2)
                                with col1:
                                    options.update({
                                        'show_min': st.checkbox("Minimum", key="multi_min"),
                                        'show_max': st.checkbox("Maximum", key="multi_max"),
                                        'show_mean': st.checkbox("Mittelwert", key="multi_mean"),
                                        'show_median': st.checkbox("Median", key="multi_median")
                                    })
                                
                                with col2:
                                    options.update({
                                        'show_std': st.checkbox("Standardabweichung (σ)", key="multi_std"),
                                        'show_percentiles': st.checkbox("Perzentile", key="multi_percentiles"),
                                        'percentile_range': st.slider(
                                            "Perzentil-Bereich",
                                            1, 49, 25,
                                            key="multi_percentile_range",
                                            help="Wählen Sie den Perzentilbereich (z.B. 25 = 25. und 75. Perzentil)"
                                        ) if options.get('show_percentiles') else 25
                                    })

                            # Tab 3: Erweiterte Analysen
                            with viz_tab3:
                                col1, col2 = st.columns(2)
                                with col1:
                                    options.update({
                                        'show_trend': st.checkbox(
                                            "Trendlinie", 
                                            key="multi_trend",
                                            help="Zeigt die lineare Trendlinie an"
                                        ),
                                        'moving_average': st.checkbox(
                                            "Gleitender Durchschnitt", 
                                            key="multi_ma",
                                            help="Glättung der Daten durch gleitenden Durchschnitt"
                                        )
                                    })
                                
                                with col2:
                                    if options.get('moving_average'):
                                        options.update({
                                            'ma_window': st.slider(
                                                "Fensterbreite",
                                                3, 21, 5, 2,
                                                key="multi_ma_window",
                                                help="Anzahl der Datenpunkte für gleitenden Durchschnitt"
                                            )
                                        })

                        # Aktualisierte Visualisierung im Container
                        with chart_container:
                            # Info über die verglichenen Tabellen
                            st.markdown(f"**Vergleiche {len(dfs_dict)} Tabellen:**")
                            for table in dfs_dict.keys():
                                st.markdown(f"- `{table}`")
                            
                            fig = create_multi_table_visualization(dfs_dict, options)
                            if fig:
                                st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Keine Daten für den ausgewählten Zeitraum gefunden.")
                
                except Exception as e:
                    st.error(f"Fehler beim Laden der Daten: {str(e)}")
            else:
                st.info("Bitte wählen Sie mindestens eine Tabelle für den Vergleich aus.")

if __name__ == "__main__":
    main()
