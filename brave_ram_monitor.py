import psutil
import time
import subprocess
import sys

# --- KONFIGURATION ---
# Das maximale RAM-Limit für den Brave Browser in Megabyte (MB)
# Beispiel: 4096 MB = 4 GB
RAM_LIMIT_MB = 4096 

# Der Name des Prozesses (kann je nach Betriebssystem variieren, 'brave' ist am häufigsten)
PROCESS_NAME = "brave"

# Der Pfad zur Brave Browser ausführbaren Datei (EXE)
# Ändere diesen Pfad entsprechend deinem Betriebssystem und deiner Installation!
#
# Beispiel (Windows): 
# BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
#
# Beispiel (macOS):
# BRAVE_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
#
# Beispiel (Linux/Standard):
# BRAVE_PATH = "/usr/bin/brave-browser"

# Wähle den für dein System passenden Pfad oder dekommentiere ihn.
# Für einen ersten Test kann der Pfad auch leer gelassen werden, wenn du Brave manuell startest.
BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" 
# ---------------------

def find_and_monitor_brave():
    """Findet den Brave-Prozess und überwacht dessen Speichernutzung."""
    
    brave_processes = [p for p in psutil.process_iter(['name', 'memory_info']) 
                       if PROCESS_NAME in p.info['name'].lower()]

    if not brave_processes:
        print(f"[{time.strftime('%H:%M:%S')}] Brave Browser Prozess ({PROCESS_NAME}) nicht gefunden.")
        return 0 # Gibt 0 zurück, da keine RAM-Nutzung gemessen werden konnte

    # Summiere die Speichernutzung aller gefundenen Brave-Prozesse
    # Die Summe ist notwendig, da Chromium-basierte Browser viele Unterprozesse verwenden.
    total_ram_usage_bytes = sum(p.info['memory_info'].rss for p in brave_processes if p.info['memory_info'])
    
    # Konvertierung von Bytes zu Megabyte (MB)
    total_ram_usage_mb = total_ram_usage_bytes / (1024 * 1024)
    
    return total_ram_usage_mb

def restart_brave(processes_to_kill):
    """Beendet die Brave-Prozesse und startet den Browser neu."""
    
    print("-" * 40)
    print(f"[{time.strftime('%H:%M:%S')}] 🔥 RAM-LIMIT von {RAM_LIMIT_MB} MB ÜBERSCHRITTEN.")
    print(f"[{time.strftime('%H:%M:%S')}] Versuche, {len(processes_to_kill)} Brave-Prozesse zu beenden...")

    # Prozesse beenden
    for p in processes_to_kill:
        try:
            p.terminate()
            print(f"[{time.strftime('%H:%M:%S')}] Prozess {p.pid} ({p.name()}) beendet.")
        except psutil.NoSuchProcess:
            pass # Prozess existiert nicht mehr

    # Warten, bis alle Prozesse beendet sind
    gone, alive = psutil.wait_procs(processes_to_kill, timeout=5)

    if alive:
        print(f"[{time.strftime('%H:%M:%S')}] WARNING: {len(alive)} Prozesse konnten nicht beendet werden.")

    # Brave neu starten
    if BRAVE_PATH and not alive:
        print(f"[{time.strftime('%H:%M:%S')}] Starte Brave neu von: {BRAVE_PATH}")
        try:
            # Starte den Browser im Hintergrund
            subprocess.Popen([BRAVE_PATH])
            print(f"[{time.strftime('%H:%M:%S')}] Neustart erfolgreich. Überwachung fortgesetzt.")
        except FileNotFoundError:
            print(f"[{time.strftime('%H:%M:%S')}] FEHLER: Der Pfad '{BRAVE_PATH}' wurde nicht gefunden.")
            print("Bitte korrigiere den BRAVE_PATH in der Konfiguration.")
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Neustart übersprungen (BRAVE_PATH ist leer oder Prozesse aktiv).")

    print("-" * 40)
    time.sleep(30) # Wartezeit nach Neustart

def main():
    """Die Haupt-Überwachungsschleife."""
    
    print(f"Starte Brave RAM Monitor...")
    print(f"Zielprozess: {PROCESS_NAME.capitalize()}")
    print(f"RAM-Limit: {RAM_LIMIT_MB} MB")
    print("-" * 40)

    while True:
        try:
            # 1. Prozesse finden (für die Überwachung)
            brave_processes_monitoring = [p for p in psutil.process_iter(['name', 'memory_info']) 
                                          if PROCESS_NAME in p.info['name'].lower()]
            
            # 2. RAM-Nutzung messen
            current_ram = find_and_monitor_brave()

            if current_ram > 0:
                print(f"[{time.strftime('%H:%M:%S')}] Aktuelle RAM-Nutzung: {current_ram:.2f} MB / Limit: {RAM_LIMIT_MB} MB")

                # 3. Limit überprüfen
                if current_ram > RAM_LIMIT_MB:
                    # 4. Neustart einleiten
                    restart_brave(brave_processes_monitoring)
            
            # Warte 60 Sekunden bis zur nächsten Prüfung
            time.sleep(60) 

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Ein Fehler ist aufgetreten: {e}")
            time.sleep(10) # Warte kurz bei Fehler

if __name__ == "__main__":
    # Überprüfen, ob die benötigten Module installiert sind
    try:
        import psutil
    except ImportError:
        print("Das 'psutil' Modul ist nicht installiert. Bitte installieren Sie es mit:")
        print("pip install psutil")
        sys.exit(1)
        
    main()