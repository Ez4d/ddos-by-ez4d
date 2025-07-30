import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog, ttk
import requests
import threading
import time
import queue
import json
import os
from datetime import datetime

class WebsiteLoadTester:
    def __init__(self, master):
        self.master = master
        master.title("Website Load Tester")
        master.geometry("800x650") # Set initial window size
        master.grid_rowconfigure(2, weight=1) # Log frame expands vertically
        master.grid_columnconfigure(0, weight=1) # Main column expands horizontally

        self.running = False
        self.bots = []
        self.log_queue = queue.Queue()
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "errors": 0,
            "total_response_time": 0.0,
            "start_time": None
        }

        # --- GUI Elements ---
        style = ttk.Style()
        style.theme_use('clam') # 'clam', 'alt', 'default', 'classic'

        # Configuration Frame
        config_frame = ttk.LabelFrame(master, text="Configuration", padding=(10, 10))
        config_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        config_frame.grid_columnconfigure(1, weight=1) # Make entry field expand

        # Row 0: Target URL
        ttk.Label(config_frame, text="Target URL:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.url_entry = ttk.Entry(config_frame, width=60)
        self.url_entry.grid(row=0, column=1, pady=5, padx=5, sticky="ew")
        self.url_entry.insert(0, "http://localhost:8000/") # Default URL

        # Row 1: Number of Concurrent Bots
        ttk.Label(config_frame, text="Concurrent Bots:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.num_bots_entry = ttk.Entry(config_frame, width=10)
        self.num_bots_entry.grid(row=1, column=1, pady=5, padx=5, sticky="w")
        self.num_bots_entry.insert(0, "5") # Default

        # Row 2: Request Interval
        ttk.Label(config_frame, text="Request Interval (s):").grid(row=2, column=0, sticky="w", pady=5, padx=5)
        self.interval_entry = ttk.Entry(config_frame, width=10)
        self.interval_entry.grid(row=2, column=1, pady=5, padx=5, sticky="w")
        self.interval_entry.insert(0, "1") # Default

        # Row 3: Request Type
        ttk.Label(config_frame, text="Request Type:").grid(row=3, column=0, sticky="w", pady=5, padx=5)
        self.request_type_var = tk.StringVar(master)
        self.request_type_var.set("GET") # default value
        self.request_type_option = ttk.OptionMenu(config_frame, self.request_type_var, "GET", "GET", "POST")
        self.request_type_option.grid(row=3, column=1, sticky="w", pady=5, padx=5)
        self.request_type_var.trace_add("write", self._toggle_post_data_input)

        # Row 4: POST Data
        ttk.Label(config_frame, text="POST Data (JSON):").grid(row=4, column=0, sticky="nw", pady=5, padx=5)
        self.post_data_text = scrolledtext.ScrolledText(config_frame, width=50, height=5, state=tk.DISABLED, wrap=tk.WORD)
        self.post_data_text.grid(row=4, column=1, pady=5, padx=5, sticky="ew")
        self.post_data_text.insert(tk.END, '{"example_key": "example_value"}')


        # Control Buttons Frame
        button_frame = ttk.Frame(master, padding=(10, 5))
        button_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1) # Allow buttons to spread
        button_frame.grid_columnconfigure(1, weight=1)

        self.start_button = ttk.Button(button_frame, text="Start Test", command=self.start_test, style="Accent.TButton")
        self.start_button.grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.stop_button = ttk.Button(button_frame, text="Stop Test", command=self.stop_test, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        style.configure("Accent.TButton", background="green", foreground="white", font=('Arial', 10, 'bold'))
        style.map("Accent.TButton", background=[('active', 'darkgreen')])


        # Logs and Statistics Frame
        log_frame = ttk.LabelFrame(master, text="Logs and Statistics", padding=(10, 10))
        log_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        # Statistics Display
        self.stats_label_text = tk.StringVar()
        self.stats_label_text.set("Stats: Total: 0, Success: 0, Errors: 0 | Req/Sec (Avg): 0.00 | Avg Resp Time: 0.00ms")
        self.stats_label = ttk.Label(log_frame, textvariable=self.stats_label_text, anchor="w", font=('Arial', 10, 'bold'))
        self.stats_label.pack(fill="x", pady=(0, 5))

        self.log_text = scrolledtext.ScrolledText(log_frame, state=tk.DISABLED, bg="#202020", fg="white", font=('Consolas', 9))
        self.log_text.pack(expand=True, fill="both")
        self.log_text.tag_config("success", foreground="lightgreen")
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("info", foreground="lightblue")

        self.export_button = ttk.Button(log_frame, text="Export Logs", command=self.export_logs)
        self.export_button.pack(pady=5, padx=5, anchor="e")

        # Warning Message
        warning_label = ttk.Label(master, text="WARNING: Use this tool ONLY on your own websites. Misuse can be illegal.",
                                 foreground="red", font=("Arial", 10, "bold"))
        warning_label.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        # Start a thread to process log messages from the queue
        self.master.after(100, self._process_log_queue)
        self.master.after(1000, self._update_live_stats) # Update stats every second

    def _toggle_post_data_input(self, *args):
        if self.request_type_var.get() == "POST":
            self.post_data_text.config(state=tk.NORMAL)
        else:
            self.post_data_text.config(state=tk.DISABLED)

    def _log_message(self, message, message_type="info"): # 'info', 'success', 'error'
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}\n", message_type)

    def _process_log_queue(self):
        while not self.log_queue.empty():
            message, tag = self.log_queue.get_nowait()
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message, tag)
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.master.after(100, self._process_log_queue)

    def _update_live_stats(self):
        if self.running and self.stats["start_time"]:
            elapsed_time = time.time() - self.stats["start_time"]
            if elapsed_time > 0:
                avg_req_sec = self.stats["total_requests"] / elapsed_time
            else:
                avg_req_sec = 0.0

            avg_resp_time = 0.0
            if self.stats["successful_requests"] > 0:
                avg_resp_time = (self.stats["total_response_time"] / self.stats["successful_requests"]) * 1000 # in ms

            self.stats_label_text.set(
                f"Stats: Total: {self.stats['total_requests']}, "
                f"Success: {self.stats['successful_requests']}, "
                f"Errors: {self.stats['errors']} | "
                f"Req/Sec (Avg): {avg_req_sec:.2f} | "
                f"Avg Resp Time: {avg_resp_time:.2f}ms"
            )
        elif not self.running:
             self.stats_label_text.set(
                f"Stats: Total: {self.stats['total_requests']}, "
                f"Success: {self.stats['successful_requests']}, "
                f"Errors: {self.stats['errors']} | "
                f"Req/Sec (Avg): 0.00 | "
                f"Avg Resp Time: 0.00ms"
            )

        self.master.after(1000, self._update_live_stats)


    def _bot_session(self, url, interval, request_type, post_data=None, bot_id=None):
        while self.running:
            try:
                self.stats['total_requests'] += 1
                start_time = time.time()
                response = None
                
                # Use a session for persistent connections and cookie handling
                with requests.Session() as session:
                    if request_type == "GET":
                        response = session.get(url, timeout=10)
                    elif request_type == "POST":
                        try:
                            headers = {'Content-Type': 'application/json'}
                            response = session.post(url, json=post_data, headers=headers, timeout=10)
                        except json.JSONDecodeError:
                            self._log_message(f"[Bot {bot_id}] Error: Invalid JSON for POST data in thread config.", "error")
                            self.stats['errors'] += 1
                            time.sleep(interval)
                            continue # Skip to next iteration if JSON is invalid

                if response:
                    end_time = time.time()
                    response_time = (end_time - start_time)
                    self.stats['total_response_time'] += response_time

                    if 200 <= response.status_code < 300: # Success codes typically 2xx
                        self.stats['successful_requests'] += 1
                        self._log_message(f"[Bot {bot_id}] Success: {url} - Status: {response.status_code} - Time: {response_time*1000:.2f}ms", "success")
                    else:
                        self.stats['errors'] += 1
                        self._log_message(f"[Bot {bot_id}] Error: {url} - Status: {response.status_code} - Time: {response_time*1000:.2f}ms - Reason: {response.reason}", "error")
                else:
                    self.stats['errors'] += 1
                    self._log_message(f"[Bot {bot_id}] Error: No response object for {url}", "error")

            except requests.exceptions.Timeout:
                self.stats['errors'] += 1
                self._log_message(f"[Bot {bot_id}] Request Timeout for {url}", "error")
            except requests.exceptions.ConnectionError as e:
                self.stats['errors'] += 1
                self._log_message(f"[Bot {bot_id}] Connection Error for {url}: {e}", "error")
            except requests.exceptions.RequestException as e:
                self.stats['errors'] += 1
                self._log_message(f"[Bot {bot_id}] Request Error (other) for {url}: {e}", "error")
            except Exception as e:
                self.stats['errors'] += 1
                self._log_message(f"[Bot {bot_id}] An unexpected error occurred: {e}", "error")

            time.sleep(interval) # Respect the interval

    def start_test(self):
        if self.running:
            messagebox.showinfo("Info", "Test is already running.")
            return

        url = self.url_entry.get().strip()
        num_bots_str = self.num_bots_entry.get().strip()
        interval_str = self.interval_entry.get().strip()
        request_type = self.request_type_var.get()
        post_data_str = self.post_data_text.get("1.0", tk.END).strip()
        post_data = None

        if not url:
            messagebox.showerror("Input Error", "Target URL cannot be empty.")
            return
        if not url.startswith("http://") and not url.startswith("https://"):
            messagebox.showwarning("URL Warning", "URL should start with http:// or https://. Attempting to add http://")
            url = "http://" + url # Attempt to fix it

        try:
            num_bots = int(num_bots_str)
            if num_bots <= 0:
                raise ValueError("Number of bots must be a positive integer.")
        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid number of bots: {e}")
            return

        try:
            interval = float(interval_str)
            if interval < 0.1: # Enforce a minimum interval for safety
                messagebox.showwarning("Rate Limit Warning", "Request interval is too low (<0.1s). Setting to 0.1 seconds minimum to avoid overwhelming the target.")
                interval = 0.1
            if interval <= 0: # Ensure positive after potential adjustment
                raise ValueError("Request interval must be positive.")
        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid request interval: {e}")
            return

        if request_type == "POST":
            if not post_data_str:
                messagebox.showerror("Input Error", "POST data cannot be empty for POST requests.")
                return
            try:
                post_data = json.loads(post_data_str)
            except json.JSONDecodeError:
                messagebox.showerror("Input Error", "Invalid JSON format for POST data.")
                return

        self.running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        # Clear logs and reset stats
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "errors": 0,
            "total_response_time": 0.0,
            "start_time": time.time()
        }
        self._update_live_stats() # Initial stats update
        self._log_message("Starting load test...", "info")
        self._log_message(f"URL: {url}, Bots: {num_bots}, Interval: {interval}s, Type: {request_type}", "info")


        self.bots = []
        for i in range(num_bots):
            # Pass a unique bot_id for clearer logs
            bot_thread = threading.Thread(target=self._bot_session, args=(url, interval, request_type, post_data, i+1))
            bot_thread.daemon = True # Allows program to exit even if threads are running
            self.bots.append(bot_thread)
            bot_thread.start()

    def stop_test(self):
        if not self.running:
            messagebox.showinfo("Info", "Test is not running.")
            return

        self.running = False
        self._log_message("Stopping load test...", "info")
        # Give threads a small moment to notice the `self.running` flag change
        # A proper join would involve waiting for each thread, but for simplicity
        # and quick GUI response, we rely on daemon threads.
        time.sleep(0.5)

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self._log_message("Load test stopped.", "info")

    def export_logs(self):
        # Get all text from the log widget
        log_content = self.log_text.get("1.0", tk.END)
        if not log_content.strip():
            messagebox.showinfo("Export Logs", "No logs to export.")
            return

        # Open file dialog to choose save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Logs As"
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(log_content)
                messagebox.showinfo("Export Logs", f"Logs successfully exported to:\n{os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export logs: {e}")

def main():
    root = tk.Tk()
    app = WebsiteLoadTester(root)
    root.mainloop()

if __name__ == "__main__":
    main()
