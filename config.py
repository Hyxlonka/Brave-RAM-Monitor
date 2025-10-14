"""
Konfigurationsdatei für den Brave RAM Monitor.
Werte können hier direkt oder durch Umgebungsvariablen gesetzt werden.
"""
import os

def get_env_var(key, default, type_converter=int):
    """
    Holt eine Umgebungsvariable, konvertiert sie zum gewünschten Typ
    und fällt bei Abwesenheit oder Fehler auf einen Standardwert zurück.
    """
    value = os.environ.get(key)
    if value is not None:
        try:
            return type_converter(value)
        except (ValueError, TypeError):
            # Bei Konvertierungsfehler wird der Standardwert verwendet
            pass
    return default

# Konfiguration mit Fallback auf Umgebungsvariablen
RAM_LIMIT_MB = get_env_var('BRAVE_MONITOR_RAM_LIMIT_MB', 4096)
PROCESS_NAME = os.environ.get('BRAVE_MONITOR_PROCESS_NAME', "brave")
CHECK_INTERVAL_SECONDS = get_env_var('BRAVE_MONITOR_CHECK_INTERVAL', 60)
RESTART_WAIT_SECONDS = get_env_var('BRAVE_MONITOR_RESTART_WAIT', 30)
GRACEFUL_SHUTDOWN_WAIT_SECONDS = get_env_var('BRAVE_MONITOR_GRACEFUL_WAIT', 5)
LOG_LEVEL = os.environ.get('BRAVE_MONITOR_LOG_LEVEL', 'INFO').upper()