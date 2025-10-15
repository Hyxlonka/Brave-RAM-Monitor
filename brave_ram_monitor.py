import time
import subprocess
import sys
import os
import logging
import signal
import ctypes
import threading

# --- Konfigurations-Management ---
def load_or_create_config():
    import json
    """
    Lädt die Konfiguration aus 'config.json' oder erstellt sie.
    Gibt das Konfigurations-Dictionary zurück.
    """
    config_path = 'config.json'
    
    default_config = {
        'RAM_LIMIT_MB': 4096,
        'PROCESS_NAME': "brave",
        'CHECK_INTERVAL_SECONDS': 60,
        'RESTART_WAIT_SECONDS': 30,
        'GRACEFUL_SHUTDOWN_WAIT_SECONDS': 5,
        'LOG_LEVEL': 'INFO'
    }

    if not os.path.exists(config_path):
        logging.info(f"Konfigurationsdatei '{config_path}' nicht gefunden. Erstelle sie mit Standardwerten.")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
            return default_config
        except IOError as e:
            logging.error(f"Fehler beim Erstellen der Konfigurationsdatei: {e}. Verwende Standardwerte.")
            return default_config
    else:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # Fülle fehlende Werte mit Defaults auf
                return {**default_config, **user_config}
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Fehler beim Lesen der Konfigurationsdatei: {e}. Verwende Standardwerte.")
            return default_config

LOG_SEPARATORS = {
    'normal': "-" * 60,
    'heavy': "=" * 60
}

# --- System-Konstanten ---
IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    # Dieser Block ist derzeit leer. Ein 'pass' macht die Absicht deutlich.
    pass


def log_section(message, separator='normal', level=logging.INFO):
    """Loggt eine Nachricht mit Trennzeichen."""
    sep = LOG_SEPARATORS.get(separator, "")
    # Loggt zuerst die Trennlinie und dann die Nachricht für eine saubere Ausgabe.
    logging.log(level, sep)
    logging.log(level, message)
def signal_handler(signum, frame):
    """Behandelt Programm-Beendigung durch Signale für einen sauberen Exit."""
    logging.info("Signal zum Beenden empfangen. Brave RAM Monitor wird heruntergefahren...")
    sys.exit(0)


def _install_package_if_needed(package_name, import_name=None):
    """
    Prüft, ob ein Paket installiert ist, und installiert es bei Bedarf.
    Gibt 'restart_needed' zurück, wenn das Skript neu gestartet werden muss.
    """
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
        return True
    except ImportError:
        log_section(f"🚨 Bibliothek '{package_name}' wird benötigt. Versuche automatische Installation...", separator='heavy', level=logging.WARNING)
        try:
            # Führe die Installation mit --no-cache-dir für eine saubere Installation durch
            install_result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir", package_name],
                capture_output=True, text=True, encoding='utf-8', errors='ignore'
            )
            if install_result.returncode != 0:
                raise subprocess.CalledProcessError(install_result.returncode, install_result.args, install_result.stdout, install_result.stderr)

            # Spezielle Nachbehandlung für pywin32, um die Registrierung der DLLs sicherzustellen.
            if package_name == "pywin32":
                import sysconfig # Nur bei Bedarf importieren
                # Finde den korrekten 'Scripts'-Pfad für die aktuelle Python-Installation
                scripts_dir = sysconfig.get_path('scripts')
                post_install_script = os.path.join(scripts_dir, "pywin32_postinstall.py")
                if os.path.isfile(post_install_script):
                    logging.info("Führe pywin32 Post-Installationsskript aus...")
                    subprocess.run([sys.executable, post_install_script, "-install"], capture_output=True)

                logging.info("✅ 'pywin32' erfolgreich installiert.")
                log_section("Bitte starten Sie das Skript neu, damit die Änderungen wirksam werden.", separator='heavy', level=logging.WARNING)
                return 'restart_needed'

            logging.info(f"✅ '{package_name}' erfolgreich installiert.")
            return 'installed'
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ FEHLER: Installation von '{package_name}' fehlgeschlagen.\n"
                          f"🛠️ Bitte manuell installieren: pip install {package_name}\n"
                          f"📝 Details:\n--- STDOUT ---\n{e.stdout}\n--- STDERR ---\n{e.stderr}")
            return False

import psutil

def find_brave_executable_path():
    """Sucht automatisch nach der Brave-Browser-Anwendung auf dem System."""
    # Wenn das Skript als PyInstaller-Bundle läuft, kann der Pfad anders sein.
    if getattr(sys, 'frozen', False):
        # Dieser Block ist derzeit leer. Ein 'pass' macht die Absicht deutlich.
        pass
    if not IS_WINDOWS:
        # shutil.which ist die robusteste Methode für POSIX-Systeme (Linux/macOS)
        import shutil
        for exe in ("brave-browser", "brave"):
            path = shutil.which(exe)
            if path:
                return path
        return ""

    # Windows-spezifische Suche
    possible_locations = [
        os.path.join(os.environ.get(env, ""), "BraveSoftware\\Brave-Browser\\Application\\brave.exe")
        for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")
    ]
    
    for path in possible_locations:
        if os.path.isfile(path):
            return path
    return ""

def find_active_brave_profiles(brave_processes):
    """
    Identifiziert aktive Brave-Profile durch die Analyse der von den Prozessen geöffneten Dateien.
    Diese Methode ist zuverlässiger als das Parsen von Kommandozeilenargumenten.
    """
    active_profiles = set()
    if not IS_WINDOWS:
        # Auf Nicht-Windows-Systemen ist das Parsen der Kommandozeile oft zuverlässiger.
        # Diese Implementierung kann bei Bedarf hinzugefügt werden.
        return list(active_profiles)

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return list(active_profiles)

    user_data_path = os.path.join(local_app_data, "BraveSoftware", "Brave-Browser", "User Data")
    if not os.path.isdir(user_data_path):
        return list(active_profiles)

    # Wir normalisieren den Pfad für zuverlässige Vergleiche
    user_data_path_norm = os.path.normpath(user_data_path)

    for proc in brave_processes:
        try:
            open_files = proc.open_files()
            for file in open_files:
                file_path_norm = os.path.normpath(file.path)
                # Prüfen, ob die geöffnete Datei im "User Data"-Verzeichnis liegt
                if file_path_norm.startswith(user_data_path_norm):
                    # Extrahiere den Teil des Pfades direkt nach "User Data"
                    relative_path = os.path.relpath(file_path_norm, user_data_path_norm)
                    path_parts = relative_path.split(os.sep)
                    if path_parts:
                        profile_name = path_parts[0]
                        # Gültige Profile sind "Default" oder "Profile X"
                        if profile_name == "Default" or (profile_name.startswith("Profile ") and profile_name.split(" ")[1].isdigit()):
                            active_profiles.add(profile_name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Prozess könnte verschwunden sein oder wir haben keine Rechte, das ist ok.
            continue
    
    return list(active_profiles)

def get_brave_processes_and_memory_and_profiles(config):
    """Ermittelt alle Brave-Prozesse, deren RAM-Verbrauch und die aktiven Profile."""
    brave_processes = []
    total_ram_bytes = 0

    for proc in psutil.process_iter(['name', 'memory_info', 'cmdline']):
        try:
            name = proc.info.get('name', '')
            if name and config['PROCESS_NAME'] in name.lower() and 'crashhandler' not in name.lower():
                brave_processes.append(proc)
                mem_info = proc.info.get('memory_info')
                if mem_info and hasattr(mem_info, 'rss'):
                    total_ram_bytes += mem_info.rss
                            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass  # Prozess ist bereits weg oder unzugänglich, ignorieren.
    
    # Ermittle die aktiven Profile basierend auf den gefundenen Prozessen
    profiles = find_active_brave_profiles(brave_processes)

    return brave_processes, total_ram_bytes / (1024 * 1024), profiles

def log_taskkill_result(result, mode="Graceful"):
    """Loggt das Ergebnis eines 'taskkill'-Befehls."""
    if result.returncode != 0:
        if result.stderr:
            logging.warning(f"Taskkill ({mode}) Warnung: {result.stderr.strip()}")
        if result.stdout:
            # stdout kann bei "Prozess nicht gefunden" nützlich sein, was kein echter Fehler ist
            logging.debug(f"Taskkill ({mode}) Ausgabe: {result.stdout.strip()}")
        return False
    return True


def restart_brave(processes_to_kill, brave_path, profiles, config, have_pywin32):
    """Beendet die Brave-Prozesse und startet den Browser neu."""
    log_section(f"🔥 RAM-Limit überschritten. Starte Neustart-Prozedur.", level=logging.WARNING)
    
    if IS_WINDOWS:
        # Stufe 1: Sanftes Beenden via pywin32 (bevorzugt)
        if have_pywin32:
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
                time.sleep(config['GRACEFUL_SHUTDOWN_WAIT_SECONDS'])
        # Stufe 2: Überprüfen und ggf. mit taskkill (graceful) nachhelfen
        remaining_procs, _, _ = get_brave_processes_and_memory_and_profiles()
        if remaining_procs:
            logging.info("Stufe 2: Sende Anfrage zum Schließen via taskkill (Graceful)...")
            result = subprocess.run(["taskkill", "/IM", config['PROCESS_NAME'] + ".exe", "/T"], 
                                  capture_output=True, text=True, encoding='utf-8', errors='ignore')
            log_taskkill_result(result, "Graceful")
            time.sleep(config['GRACEFUL_SHUTDOWN_WAIT_SECONDS'])
            
            # Stufe 3: Letzte Überprüfung und erzwungenes Beenden
            final_procs, _, _ = get_brave_processes_and_memory_and_profiles()
            if final_procs:
                logging.warning("Graceful Shutdown fehlgeschlagen. Erzwinge das Beenden...")
                result = subprocess.run(["taskkill", "/F", "/IM", config['PROCESS_NAME'] + ".exe", "/T"],
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
        if profiles:
            logging.info(f"🚀 Starte Brave mit {len(profiles)} gefundenen Profilen neu...")
            for profile in profiles:
                logging.info(f"  -> Starte Profil: {profile}")
                try:
                    subprocess.Popen([current_brave_path, f'--profile-directory={profile}'])
                except Exception as e:
                    logging.error(f"❌ Fehler beim Neustart von Profil '{profile}': {e}")
        else:
            logging.info(f"🚀 Starte Brave neu (keine spezifischen Profile gefunden): {current_brave_path}")
            try:
                subprocess.Popen([current_brave_path])
            except Exception as e:
                logging.error(f"❌ Fehler beim Neustart: {e}")
        logging.info("✅ Neustart-Befehle gesendet. Überwachung wird fortgesetzt.")
    else:
        logging.warning("⚠️ Kein Brave-Pfad gefunden. Manueller Neustart erforderlich.")

    log_section("Wartezeit nach Neustart...", separator='normal')
    time.sleep(config['RESTART_WAIT_SECONDS'])

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

def show_startup_info(brave_path, config):
    """Zeigt Startinformationen an."""
    log_section("📊 Starte Brave RAM Monitor...", separator='heavy')
    logging.info(f"⚙️ Logging-Level: {config['LOG_LEVEL']}")
    logging.info(f"🎯 RAM-Limit: {config['RAM_LIMIT_MB']:,} MB")
    
    if brave_path:
        logging.info(f"📂 Brave-Pfad gefunden: {brave_path}")
    else:
        logging.warning("⚠️ Brave-Pfad nicht sofort gefunden. Es wird beim Neustart erneut gesucht.")

def monitor_and_restart(brave_path, config, have_pywin32):
    """Überwacht den RAM-Verbrauch und startet bei Bedarf neu."""
    processes, current_ram, profiles = get_brave_processes_and_memory_and_profiles(config)
    
    if not processes:
        logging.info("🔍 Kein Brave-Prozess gefunden.")
        return
    
    ram_limit = config['RAM_LIMIT_MB']
    if ram_limit > 0:
        ram_percentage = (current_ram / ram_limit) * 100
        status = get_status_emoji(ram_percentage)
        logging.info(f"{status} RAM-Nutzung: {current_ram:,.2f} MB / {ram_limit:,} MB ({ram_percentage:.1f}%)")
        
        if current_ram > ram_limit:
            restart_brave(processes, brave_path, profiles, config, have_pywin32)

def check_admin_rights():
    """Prüft, ob Admin-Rechte vorhanden sind (nur Windows)."""
    if IS_WINDOWS:
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

    # Temporäres Logging für die Initialisierungsphase
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # --- Abhängigkeiten prüfen und installieren ---
    if not _install_package_if_needed("psutil"):
        sys.exit(1)  # psutil ist zwingend erforderlich

    # pywin32 ist nur für Windows optional, aber empfohlen
    pywin32_install_result = _install_package_if_needed("pywin32", "win32gui") if IS_WINDOWS else False
    if pywin32_install_result == 'restart_needed':
        sys.exit(0)
    have_pywin32 = pywin32_install_result is not False

    config = load_or_create_config()
    log_level_from_config = getattr(logging, config.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
    logging.basicConfig(level=log_level_from_config,
                        format='%(asctime)s [%(levelname)s] - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S', force=True) # force=True überschreibt die temporäre Konfig
    logging.getLogger().setLevel(log_level_from_config)

    if not check_admin_rights():
        log_section("⚠️  Script läuft ohne Admin-Rechte. Der erzwungene Neustart (Force-Kill) könnte fehlschlagen.", separator='heavy', level=logging.WARNING)

    brave_path = find_brave_executable_path()
    show_startup_info(brave_path, config)

    # Haupt-Überwachungsschleife
    while True:
        try:
            monitor_and_restart(brave_path, config, have_pywin32)
            time.sleep(config.get('CHECK_INTERVAL_SECONDS', 60))
        except Exception as e:
            logging.critical(f"❌ Unerwarteter Fehler in der Hauptschleife: {e}", exc_info=True)
            # Kurze Pause bei unerwarteten Fehlern
            time.sleep(10)

if __name__ == "__main__":
    main()
