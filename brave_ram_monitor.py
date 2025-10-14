import time
import subprocess
import sys
import os
import logging
import signal
import ctypes

from config import (RAM_LIMIT_MB, PROCESS_NAME, CHECK_INTERVAL_SECONDS, 
                    RESTART_WAIT_SECONDS, GRACEFUL_SHUTDOWN_WAIT_SECONDS, LOG_LEVEL)

# --- Logging-Helfer ---
LOG_SEPARATORS = {
    'normal': "-" * 60,
    'heavy': "=" * 60
}

# --- Logging-Konfiguration ---
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def log_section(message, separator='normal', level=logging.INFO):
    """Loggt eine Nachricht mit Trennzeichen."""
    sep = LOG_SEPARATORS.get(separator, LOG_SEPARATORS['normal'])
    logging.log(level, sep)
    logging.log(level, message)
    logging.log(level, sep)
def signal_handler(signum, frame):
    """Behandelt Programm-Beendigung durch Signale für einen sauberen Exit."""
    logging.info("Signal zum Beenden empfangen. Brave RAM Monitor wird heruntergefahren...")
    sys.exit(0)


def _install_package_if_needed(package_name, import_name=None):
    """Prüft, ob ein Paket installiert ist, und installiert es bei Bedarf."""
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
        return True
    except ImportError:
        log_section(f"🚨 Bibliothek '{package_name}' wird benötigt. Versuche automatische Installation...", separator='heavy', level=logging.WARNING)
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            __import__(import_name)  # Erneuter Import-Versuch
            logging.info(f"✅ '{package_name}' erfolgreich installiert.")
            return True
        except (subprocess.CalledProcessError, ImportError) as e:
            logging.error(f"❌ FEHLER: Installation von '{package_name}' fehlgeschlagen.\n"
                          f"🛠️ Bitte manuell installieren: pip install {package_name}\n"
                          f"📝 Details: {e}")
            return False

# --- Abhängigkeiten prüfen und installieren ---
if not _install_package_if_needed("psutil"):
    sys.exit(1)  # psutil ist zwingend erforderlich

import psutil

# pywin32 ist nur für Windows optional, aber empfohlen
HAVE_PYWIN32 = sys.platform == "win32" and _install_package_if_needed("pywin32", "win32gui")

def find_brave_executable_path():
    """Sucht automatisch nach der Brave-Browser-Anwendung auf dem System."""
    # shutil.which ist die robusteste Methode für POSIX-Systeme (Linux/macOS)
    if sys.platform != "win32":
        import shutil
        for exe in ("brave-browser", "brave"):
            path = shutil.which(exe)
            if path:
                return path
        return ""

    # Windows-spezifische Suche
    possible_locations = [
        (os.environ.get("ProgramFiles"), "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
        (os.environ.get("ProgramFiles(x86)"), "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
        (os.environ.get("LOCALAPPDATA"), "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
    ]
    
    for base_path, relative_path in possible_locations:
        if base_path:
            full_path = os.path.join(base_path, relative_path)
            if os.path.isfile(full_path):
                return full_path
    return ""

def get_brave_processes_and_memory():
    """Ermittelt alle Brave-Prozesse und deren gesamten RAM-Verbrauch."""
    brave_processes = []
    total_ram_bytes = 0
    
    for proc in psutil.process_iter(['name', 'memory_info']):
        try:
            name = proc.info.get('name')
            if not name:
                continue
            
            name_lower = name.lower()
            if PROCESS_NAME in name_lower and 'crashhandler' not in name_lower:
                brave_processes.append(proc)
                mem_info = proc.info.get('memory_info')
                if mem_info and hasattr(mem_info, 'rss'):
                    total_ram_bytes += mem_info.rss
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass  # Prozess ist bereits weg oder unzugänglich, ignorieren.
    
    return brave_processes, total_ram_bytes / (1024 * 1024)  # In MB

def log_taskkill_result(result, mode="Graceful"):
    """Loggt das Ergebnis eines Taskkill-Befehls."""
    if result.returncode != 0:
        if result.stderr:
            logging.warning(f"Taskkill ({mode}) Warnung: {result.stderr.strip()}")
        if result.stdout:
            # stdout kann bei "Prozess nicht gefunden" nützlich sein, was kein echter Fehler ist
            logging.debug(f"Taskkill ({mode}) Ausgabe: {result.stdout.strip()}")
        return False
    return True


def restart_brave(processes_to_kill, brave_path):
    """Beendet die Brave-Prozesse und startet den Browser neu."""
    log_section(f"🔥 RAM-Limit überschritten. Starte Neustart-Prozedur.", level=logging.WARNING)
    
    if sys.platform == "win32":
        # Stufe 1: Sanftes Beenden via pywin32 (bevorzugt)
        if HAVE_PYWIN32:
            try:
                import win32gui, win32con, win32process
            except Exception as e: # Fängt alle potenziellen Import- oder Initialisierungsfehler ab
                logging.warning(f"Konnte pywin32 nicht für den Shutdown nutzen (falle auf taskkill zurück). Fehler: {e}")
            else:
                # Dies ist die sauberste Methode: Wir simulieren einen Klick auf das "X" des Fensters.
                # Der Browser erhält eine WM_CLOSE-Nachricht und kann seine Sitzung ordnungsgemäß speichern.
                logging.info("Stufe 1: Sende WM_CLOSE an Brave-Fenster (Graceful via pywin32)...")
                pids_to_kill = set()
                for p in processes_to_kill:
                    try:
                        pids_to_kill.add(p.pid)
                    except psutil.Error: # Fängt NoSuchProcess und andere psutil-Fehler ab
                        continue
                
                # Iteriert durch alle Top-Level-Fenster auf dem Desktop.
                def close_brave_window(hwnd, _):
                    try:
                        if not win32gui.IsWindowVisible(hwnd): return
                        # Ermittelt die Prozess-ID (PID) des Fensters.
                        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                        # Wenn die PID zu einem Brave-Prozess gehört, senden wir die Schließen-Nachricht.
                        if found_pid in pids_to_kill:
                            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    except Exception: # Ignoriere Fehler für einzelne Fenster
                        pass # Fenster könnte bereits geschlossen sein
                try:
                    # Startet die Iteration über alle Fenster.
                    win32gui.EnumWindows(close_brave_window, None)
                except Exception as e:
                    logging.debug(f"EnumWindows/WM_CLOSE schlug fehl, fahre mit taskkill fort. Fehler: {e}")
                
                # Das Warten erfolgt außerhalb des try-Blocks, um sicherzustellen, dass es immer ausgeführt wird.
                time.sleep(GRACEFUL_SHUTDOWN_WAIT_SECONDS)
        # Stufe 2: Überprüfen und ggf. mit taskkill (graceful) nachhelfen
        remaining_procs, _ = get_brave_processes_and_memory()
        if remaining_procs:
            logging.info("Stufe 2: Sende Anfrage zum Schließen via taskkill (Graceful)...")
            result = subprocess.run(["taskkill", "/IM", PROCESS_NAME + ".exe", "/T"], 
                                  capture_output=True, text=True, encoding='utf-8', errors='ignore')
            log_taskkill_result(result, "Graceful")
            time.sleep(GRACEFUL_SHUTDOWN_WAIT_SECONDS)
            
            # Stufe 3: Letzte Überprüfung und erzwungenes Beenden
            final_procs, _ = get_brave_processes_and_memory()
            if final_procs:
                logging.warning("Graceful Shutdown fehlgeschlagen. Erzwinge das Beenden...")
                result = subprocess.run(["taskkill", "/F", "/IM", PROCESS_NAME + ".exe", "/T"],
                                      capture_output=True, text=True, encoding='utf-8', errors='ignore')
                log_taskkill_result(result, "Force")
                time.sleep(2)
    else:
        # Sauberes Beenden für POSIX-Systeme (Linux, macOS)
        parent_procs = []
        pids_to_kill = set()
        try:
            # Kompatible und sichere Methode zum Sammeln von PIDs
            for p in processes_to_kill:
                pid = getattr(p, 'pid', None)
                if pid is not None:
                    pids_to_kill.add(pid) # Python 3.7-kompatibel
        except psutil.Error:
            pass # Fallback auf leeres Set bei unerwartetem Fehler
        for p in processes_to_kill:
            try:
                # Prüfen, ob der Elternprozess nicht auch ein Brave-Prozess ist
                if p.is_running() and p.ppid() not in pids_to_kill:
                    parent_procs.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        logging.info(f"Sende 'terminate' Signal an {len(parent_procs)} Brave-Hauptprozess(e)...")
        for p in parent_procs:
            safe_terminate_process(p)
        
        # Kurze Pause nach dem Versuch, alle Prozesse zu beenden
        time.sleep(2)


    # Neustart des Browsers
    current_brave_path = brave_path or find_brave_executable_path()
    if current_brave_path:
        logging.info(f"🚀 Starte Brave neu von: {current_brave_path}")
        try:
            subprocess.Popen([current_brave_path])
            logging.info("✅ Neustart erfolgreich. Überwachung wird fortgesetzt.")
        except Exception as e:
            logging.error(f"❌ Fehler beim Neustart: {e}")
    else:
        logging.warning("⚠️ Kein Brave-Pfad gefunden. Manueller Neustart erforderlich.")

    log_section("Wartezeit nach Neustart...", separator='normal')
    time.sleep(RESTART_WAIT_SECONDS)

def safe_terminate_process(proc):
    """Beendet einen Prozess sicher mit Fehlerbehandlung und eskaliert zu kill, falls nötig."""
    try:
        proc.terminate()
        proc.wait(timeout=2) # Gib dem Prozess 2 Sekunden Zeit, um auf terminate zu reagieren
    except psutil.TimeoutExpired:
        logging.warning(f"Prozess {proc.pid} hat nicht auf terminate reagiert. Erzwinge Beenden (kill)...")
        proc.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass # Prozess ist bereits weg oder Zugriff verweigert, alles ok.
def get_status_emoji(percentage):
    """Gibt das passende Status-Emoji basierend auf der RAM-Nutzung zurück."""
    if percentage < 80:
        return "🟢"
    elif percentage < 95:
        return "🟡"
    return "🔴"

def show_startup_info(brave_path):
    """Zeigt Startinformationen an."""
    log_section("📊 Starte Brave RAM Monitor...", separator='heavy')
    logging.info(f"⚙️ Logging-Level: {LOG_LEVEL}")
    logging.info(f"🎯 RAM-Limit: {RAM_LIMIT_MB:,} MB")
    
    if brave_path:
        logging.info(f"📂 Brave-Pfad gefunden: {brave_path}")
    else:
        logging.warning("⚠️ Brave-Pfad nicht sofort gefunden. Es wird beim Neustart erneut gesucht.")

def monitor_and_restart(brave_path):
    """Überwacht den RAM-Verbrauch und startet bei Bedarf neu."""
    processes, current_ram = get_brave_processes_and_memory()
    
    if not processes:
        logging.info("🔍 Kein Brave-Prozess gefunden.")
        return
    
    if RAM_LIMIT_MB > 0:
        ram_percentage = (current_ram / RAM_LIMIT_MB) * 100
        status = get_status_emoji(ram_percentage)
        logging.info(f"{status} RAM-Nutzung: {current_ram:,.2f} MB / {RAM_LIMIT_MB:,} MB ({ram_percentage:.1f}%)")
        
        if current_ram > RAM_LIMIT_MB:
            restart_brave(processes, brave_path)

def check_admin_rights():
    """Prüft, ob Admin-Rechte vorhanden sind (nur Windows)."""
    if sys.platform == "win32":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    return True # Auf Nicht-Windows-Systemen wird angenommen, dass root-Rechte nicht nötig sind

def main():
    """Die Haupt-Überwachungsschleife."""
    # Signal-Handler für sauberes Beenden registrieren
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not check_admin_rights():
        log_section("⚠️  Script läuft ohne Admin-Rechte. Der erzwungene Neustart (Force-Kill) könnte fehlschlagen.", separator='heavy', level=logging.WARNING)

    brave_path = find_brave_executable_path()
    show_startup_info(brave_path)
    
    while True:
        try:
            monitor_and_restart(brave_path)
            time.sleep(CHECK_INTERVAL_SECONDS)
        except Exception as e:
            logging.critical(f"❌ Unerwarteter Fehler in der Hauptschleife: {e}", exc_info=True)
            time.sleep(10)

if __name__ == "__main__":
    main()
