# Übersicht

Diese Anwendung ermöglicht die Visualisierung und Verwaltung von bereitgestellten CSV Daten, die in einer PostgreSQL-Datenbank gespeichert sind. Sie besteht aus einer Weboberfläche (`index.html`), einem Backend-Skript zur Datenabfrage (`getData.php`), und einem Streamlit-basierten Python-Skript (`test.py`) zur Datenverarbeitung und -visualisierung.

## Vorbedingungen

### Systemvoraussetzungen

- macOS (für Windows und Linux können die Schritte leicht abweichen)
- Terminalzugriff
- Internetverbindung

# Projektübersicht

Hier ist ein Screenshot der Anwendung:

![Screenshot](assets/screenshots/Bildschirmfoto%202025-02-04%20um%2013.40.44.png)

### Software installieren

Führen Sie folgende Schritte im Terminal aus, um alle notwendigen Softwarekomponenten zu installieren:

1. **Homebrew installieren**  
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **PostgreSQL installieren**  
   ```bash
   brew install postgresql
   ```

3. **Python installieren**  
   ```bash
   brew install python
   ```

4. **PHP installieren**  
   ```bash
   brew install php
   ```

### Datenbank einrichten

1. Starten Sie den PostgreSQL-Dienst:
   ```bash
   brew services start postgresql
   ```
   Führen Sie alternativ dein Installations- und Einrichtungsprozess durch

2. Der Username ist "postgres"
3. Das Standardpasswort ist "123456"
4. Öffnen Sie den Terminal
5. Führen Sie den Befehl aus:
   ```bash
   psql -U postgres
   ```
6. Geben Sie "123456" als Passwort ein und bestätigen Sie mit Enter
7. Erstellen Sie die Datenbank:
   ```sql
   CREATE DATABASE examdb;
   ```
8. Beenden Sie die Sitzung:
   ```sql
   \q
   ```

## Anwendung starten (`test.py`)

1. Navigieren Sie zum Projektverzeichnis:
   ```bash
   cd /path/to/csvManagementSystemv2
   ```
2. Erstellen und Aktivieren Sie die virtuelle Umgebung:
   ```bash
    python3 -m venv path/to/venv
    source path/to/venv/bin/activate
    python3 -m pip install xyz
    pip install --upgrade pip
   
   ```
3. Installieren Sie die Bibliotheken:
   ```bash
   pip install -r requirements.txt
   ```

3. Starten Sie die Anwendung:
   ```bash
   python3 -m streamlit run test.py
   ```

## Funktionen des Programms

### 1. CSV-Datei Import
- Hochladen von CSV-Dateien in die Datenbank
- Automatische Erkennung des Dateinamens als Tabellenname
- Vorschau der Daten vor dem Import
- Anpassbare Chunk-Größe für optimierte Performance

### 2. Datenbank-Management
- Anzeige aller vorhandenen Tabellen
- Löschen von Tabellen
- Anzeige der Tabellenstruktur und Datenvorschau
- Exportieren von Tabellen als CSV

### 3. Datenanalyse & Visualisierung
- Interaktive Diagramme mit Plotly
- Verschiedene Diagrammtypen:
  - Liniendiagramme
  - Balkendiagramme 
  - Streudiagramme
  - Histogramme
- Filtermöglichkeiten nach Datum und Werten
- Zoom- und Pan-Funktionen in Diagrammen

### 4. Performance-Optimierung
- Connection Pooling für effiziente Datenbankverbindungen
- Caching von häufig verwendeten Daten
- Chunk-basiertes Laden großer Datensätze
- Automatisches Recycling von Datenbankverbindungen

### 5. Fehlerbehandlung
- Robuste Fehlerbehandlung bei Datenbankoperationen
- Benutzerfreundliche Fehlermeldungen
- Validierung von Eingabedaten
- Automatische Wiederherstellung bei Verbindungsabbrüchen

### 6. Benutzeroberfläche
- Übersichtliches Streamlit Interface
- Intuitive Navigation
- Responsive Designanpassung
- Fortschrittsanzeigen bei längeren Operationen

### 7. Backend-Architektur

#### Datenbankanbindung
- PostgreSQL als robuste, relationale Datenbank
- SQLAlchemy als ORM (Object-Relational Mapping)
- Optimierte Verbindungsverwaltung durch Connection Pooling
- Konfigurierbare Datenbankparameter (Host, Port, Credentials)

#### Datenverarbeitung
- Pandas für effiziente Datenmanipulation
- Chunk-basierte Verarbeitung großer Datensätze
- Automatische Datentyperkennung
- Optimierte Speichernutzung durch gezieltes Memory Management

#### Caching-Strategie
- Mehrschichtiges Caching-System:
  - Datenbankabfragen (TTL: 5 Minuten)
  - Tabellenstrukturen
  - Berechnungsergebnisse
- Automatische Cache-Invalidierung
- Memory-effiziente Cache-Verwaltung

#### API-Struktur
- Modulare Funktionsaufteilung
- Wiederverwendbare Datenbankoperationen
- Standardisierte Fehlerbehandlung
- Asynchrone Verarbeitung für zeitintensive Operationen

#### Sicherheitsaspekte
- Parametrisierte SQL-Abfragen
- Eingabevalidierung
- Sichere Verbindungshandhabung
- Automatisches Verbindungs-Timeout

#### Performance-Optimierung
- Indexierung wichtiger Spalten
- Optimierte SQL-Abfragen
- Lazy Loading von großen Datensätzen
- Effiziente Speichernutzung durch Datentyp-Optimierung
