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

Beim ersten Start wird automatisch eine `config.json`-Datei erstellt. Sie können diese Datei anpassen, um das Verhalten des Skripts zu steuern:

-   `RAM_LIMIT_MB`: Das RAM-Limit in Megabyte, bei dessen Überschreitung der Neustart ausgelöst wird.
-   `PROCESS_NAME`: Der Name des zu überwachenden Prozesses (z.B. "brave").
-   `CHECK_INTERVAL_SECONDS`: Das Intervall in Sekunden, in dem der RAM-Verbrauch geprüft wird.
-   `RESTART_WAIT_SECONDS`: Die Wartezeit in Sekunden nach einem Neustart, bevor die Überwachung fortgesetzt wird.
-   `WM_CLOSE_WAIT_SECONDS`: Die Wartezeit in Sekunden für den sanften Shutdown (Stufe 1), um dem Browser Zeit zum Speichern zu geben.
-   `GRACEFUL_SHUTDOWN_WAIT_SECONDS`: Die Wartezeit für die `taskkill`-Stufen.
-   `LOG_LEVEL`: Der Detailgrad der Log-Ausgaben (z.B. 'INFO', 'DEBUG', 'WARNING').

## Kompilieren (Optional)

Wenn Sie das Skript zu einer eigenständigen `.exe`-Datei kompilieren möchten, können Sie PyInstaller verwenden. Das Skript ist so konzipiert, dass es auch in kompilierter Form zuverlässig funktioniert.

```bash
pip install pyinstaller
pyinstaller --onefile --windowed brave_ram_monitor.py
```