<b>Übersicht</b>

Diese Anwendung ermöglicht die Visualisierung und Verwaltung von Daten, die in einer PostgreSQL-Datenbank gespeichert sind. Sie besteht aus einer Weboberfläche (index.html), einem Backend-Skript zur Datenabfrage (getData.php), und einem Streamlit-basierten Python-Skript (test.py) zur Datenverarbeitung und -visualisierung.

<b>Vorbedingungen</b>

Datenbank: 
1. PostgreSQL muss installiert und konfiguriert sein.
2. Das Standardpasswort ist "123456"
3. Öffnen Sie den Terminal
4. psql -U postgres
5. Geben Sie "123456" als Passwort ein und bestägigen Sie mit Enter
6. CREATE DATABASE examdb;
7. \q
8. exit
  
Python:
0. python3 -m pip install --upgrade pip
1. pip install -r requirements.txt
2. requirements.txt installieren mit pip install -r requirements.txt
3. pip3 install -r requirements.txt
4. python3 -m venv myenv
5. source myenv/bin/activate
  

<b>Anwendung starten (test.py)</b>
1. python3 -m streamlit run test.py
   
3. Funktionen:
  1. "Tabelle Erstellen":
     
      1. Geben Sie den Namen einer neuen Tabelle ein
      2. Klicken Sie auf "Tabelle erstellen"
         
  3. "Tabelle löschen":
     
        0. Vorbedingung: Tabellen müssen vorhanden sein 
        1. Klicken Sie auf den Tab "Tabelle löschen"
        2. Wählen Sie per Dropdown eine Tabelle aus
        3. Klicke auf "Tabelle löschen"
        4. Klicke auf bestätigen
    
  5. "CSV Upload":
     
      0. Vorbedingung: Tabellen müssen vorhanden sein 
      1. Klicken Sie auf den Tab "Upload"
      2. Klicken Sie auf "browse files"
      3. Fügen Sie die CSV Assets ein
      4. Klicke auf "übertragen"
      5. Prüfe das Popup "Daten erfolgreich übertragen!"

   3. "Tabelle einsehen":
      
      0. Vorbedingung: Tabellen müssen vorhanden sein 
      1. Klicken Sie auf den Tab "View Data"
      2. Klicken Sie auf "Alle Daten laden"
      5. Prüfe ob die Daten in einer Tabelle korrekt dargestellt sind

           
      
