# Brave RAM Monitor

Ein robustes Skript zur automatischen Überwachung und Verwaltung des RAM-Verbrauchs des Brave Browsers. Wenn ein konfigurierbares RAM-Limit überschritten wird, startet das Skript den Browser auf sichere Weise neu, um die Systemleistung zu erhalten.

## Features

-   **Automatische RAM-Überwachung:** Prüft in regelmäßigen Abständen den RAM-Verbrauch von Brave.
-   **Intelligenter, mehrstufiger Neustart (Windows):**
    1.  **Sanftes Beenden:** Sendet eine "Schließen"-Anfrage an die Browser-Fenster, damit die Sitzung sauber gespeichert werden kann.
    2.  **Graceful Kill:** Falls das nicht ausreicht, wird ein sanfter `taskkill`-Befehl verwendet.
    3.  **Force Kill:** Als letzte Instanz wird der Prozess erzwungen beendet, um sicherzustellen, dass der RAM freigegeben wird.
-   **Wiederherstellung von Profilen:** Erkennt aktive Browser-Profile und startet sie nach einem Neustart automatisch wieder.
-   **Plattformübergreifend:** Funktioniert unter Windows, Linux und macOS.
-   **Keine manuelle Installation von Abhängigkeiten:** Benötigte Python-Pakete (`psutil`, `pywin32`) werden beim ersten Start automatisch installiert.
-   **Flexible Konfiguration:** Alle wichtigen Parameter können über eine `config.json`-Datei angepasst werden.
-   **Detailliertes Logging:** Gibt klare Informationen über den aktuellen Status und durchgeführte Aktionen aus.

## Installation & Verwendung

Es ist keine manuelle Installation von Paketen erforderlich.

1.  Stellen Sie sicher, dass Python 3 auf Ihrem System installiert ist.
2.  Führen Sie das Skript aus der Kommandozeile aus:

```bash
python brave_ram_monitor.py
```

### Windows-Benutzer
- Für Force-Kill (taskkill /F) werden möglicherweise Admin-Rechte benötigt
- PyWin32 wird automatisch installiert für verbesserte Prozessbehandlung

## Konfiguration
Editiere `config.py` für folgende Einstellungen:
- RAM_LIMIT_MB: Maximaler RAM-Verbrauch in MB
- CHECK_INTERVAL_SECONDS: Prüfintervall
- RESTART_WAIT_SECONDS: Wartezeit nach Neustart