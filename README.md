# Brave RAM Monitor

Überwacht und verwaltet den RAM-Verbrauch des Brave Browsers automatisch.

## Features
- Automatische RAM-Überwachung
- Mehrstufiger, sicherer Neustart-Prozess
- Plattformübergreifend (Windows, Linux, macOS)
- Detailliertes Logging

## Installation

```bash
pip install -r requirements.txt
```

## Verwendung

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