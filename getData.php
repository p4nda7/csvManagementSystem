<?php
// Verbesserte Konstanten und Konfiguration
define('DB_CONFIG', [
    'host' => 'localhost',
    'name' => 'examDB',
    'user' => 'postgres',
    'pass' => '123456',
    'port' => 5432
]);

// Verbesserte PDO-Optionen
define('PDO_OPTIONS', [
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    PDO::ATTR_EMULATE_PREPARES => false,
    PDO::ATTR_PERSISTENT => true  // Persistente Verbindungen
]);

// Fehlerbehandlung
function handleError($message, $error = null) {
    header('HTTP/1.1 500 Internal Server Error');
    header('Content-Type: application/json');
    echo json_encode([
        'error' => $message,
        'details' => $error ? $error->getMessage() : null,
        'status' => 'error'
    ]);
    exit;
}

// Optimierte Datenbankverbindung
function getDbConnection() {
    static $pdo = null;
    if ($pdo === null) {
        try {
            $dsn = sprintf(
                "pgsql:host=%s;port=%d;dbname=%s",
                DB_CONFIG['host'],
                DB_CONFIG['port'],
                DB_CONFIG['name']
            );
            $pdo = new PDO($dsn, DB_CONFIG['user'], DB_CONFIG['pass'], PDO_OPTIONS);
        } catch (PDOException $e) {
            handleError("Datenbankverbindung fehlgeschlagen", $e);
        }
    }
    return $pdo;
}

// Optimierte Datenabfrage mit Prepared Statements
function fetchData($table, $date, $function = 'raw') {
    $pdo = getDbConnection();
    
    // Vordefinierte Abfragen für bessere Performance
    $queries = [
        'raw' => "SELECT index, date, time, value::numeric as value",
        'average' => "SELECT index, date, time, AVG(value::numeric) as value",
        'min' => "SELECT index, date, time, MIN(value::numeric) as value",
        'max' => "SELECT index, date, time, MAX(value::numeric) as value"
    ];
    
    $baseQuery = $queries[$function] ?? $queries['raw'];
    $query = $baseQuery . " FROM " . $table . " WHERE date = :date";
    
    if ($function !== 'raw') {
        $query .= " GROUP BY index, date, time";
    }
    
    $stmt = $pdo->prepare($query);
    $stmt->execute(['date' => $date]);
    
    return $stmt->fetchAll();
}

// Parameter validieren
function validateParams($params) {
    $required = ['table', 'date'];
    foreach ($required as $param) {
        if (!isset($params[$param]) || empty($params[$param])) {
            handleError("Parameter '$param' fehlt oder ist leer");
        }
    }
    return [
        'table' => filter_var($params['table'], FILTER_SANITIZE_STRING),
        'date' => filter_var($params['date'], FILTER_SANITIZE_STRING),
        'function' => filter_var($params['function'] ?? 'raw', FILTER_SANITIZE_STRING)
    ];
}

// Hauptfunktion
function main() {
    try {
        // Parameter validieren
        $params = validateParams($_GET);
        
        // Datenbankverbindung
        $pdo = getDbConnection();
        
        // Query vorbereiten
        $queryParts = [
            'raw' => "SELECT index, date, time, value::numeric as value",
            'average' => "SELECT index, date, time, AVG(value::numeric) as value",
            'min' => "SELECT index, date, time, MIN(value::numeric) as value",
            'max' => "SELECT index, date, time, MAX(value::numeric) as value",
            'sum' => "SELECT index, date, time, SUM(value::numeric) as value"
        ];
        
        $query = ($queryParts[$params['function']] ?? $queryParts['raw']) . 
                " FROM :table" .
                " WHERE date = :date";
                
        if ($params['function'] !== 'raw') {
            $query .= " GROUP BY index, date, time";
        }
        
        $query .= " ORDER BY date, time, index";
        
        // Query ausführen
        $stmt = $pdo->prepare($query);
        $stmt->execute([
            'table' => $params['table'],
            'date' => $params['date']
        ]);
        
        // Daten abrufen
        $data = $stmt->fetchAll();
        
        // Statistiken berechnen
        $statsStmt = $pdo->prepare("
            SELECT 
                COUNT(*) as count,
                MIN(value::numeric) as min_value,
                MAX(value::numeric) as max_value,
                AVG(value::numeric) as avg_value
            FROM :table
            WHERE date = :date
        ");
        
        $statsStmt->execute([
            'table' => $params['table'],
            'date' => $params['date']
        ]);
        
        $stats = $statsStmt->fetch();
        
        // Erfolgreiche Antwort
        header('Content-Type: application/json');
        echo json_encode([
            'status' => 'success',
            'data' => $data,
            'statistics' => $stats,
            'metadata' => [
                'table' => $params['table'],
                'date' => $params['date'],
                'function' => $params['function']
            ]
        ]);
        
    } catch (Exception $e) {
        handleError("Verarbeitungsfehler", $e);
    }
}

// Ausführung
main();
?> 