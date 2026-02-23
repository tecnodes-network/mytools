import tkinter as tk
import customtkinter as ctk
import subprocess
import json
import os
import sys
import threading
import time
import socket
from pathlib import Path
from tkinter import filedialog, messagebox

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class Settings:
    def __init__(self):
        self.app_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'TunnelManager')
        os.makedirs(self.app_data_dir, exist_ok=True)
        self.settings_file = os.path.join(self.app_data_dir, 'settings.json')
        self.config_path = self.load_settings()
        
    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r') as f:
                data = json.load(f)
                path = data.get('config_path')
                if path and os.path.exists(os.path.dirname(path)):
                    return path
        return self.get_default_config_path()
    
    def get_default_config_path(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "tunnel_profiles.json")
    
    def save_settings(self):
        with open(self.settings_file, 'w') as f:
            json.dump({'config_path': self.config_path}, f)
    
    def set_config_path(self, path):
        self.config_path = path
        self.save_settings()

class SSHTunnel:
    def __init__(self, profile):
        self.profile = profile
        self.process = None
        self.status = "Disconnected"
        self.pid = None
        self.log_callback = None
        self._stop_check = threading.Event()
        
    def is_running(self):
        """Check if SSH process is alive"""
        return self.process is not None and self.process.poll() is None
        
    def is_port_open(self, host, port, timeout=2):
        """Check if local port is actually listening"""
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except:
            return False
        
    def start(self):
        if self.is_running():
            return False
            
        forwards = []
        test_ports = []
        
        for fwd in self.profile.get('forwards', []):
            local = fwd['local']
            remote_host = fwd.get('remote_host', 'localhost')
            remote_port = fwd['remote']
            forwards.extend(['-L', f"{local}:{remote_host}:{remote_port}"])
            test_ports.append(local)
        
        cmd = [
            'ssh',
            '-p', str(self.profile.get('ssh_port', 22)),
            '-i', os.path.expanduser(self.profile['key']),
            '-o', 'ServerAliveInterval=60',
            '-o', 'ServerAliveCountMax=3',
            '-o', 'ExitOnForwardFailure=yes',
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            '-N'
        ] + forwards + [f"{self.profile['user']}@{self.profile['host']}"]
        
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self.process = subprocess.Popen(cmd, creationflags=creation_flags, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            self.pid = self.process.pid
            self.status = "Connecting..."
            self._stop_check.clear()
            
            if self.log_callback:
                self.log_callback(f"Connecting to {self.profile['host']}...")
            
            time.sleep(1.5)
            if self.process.poll() is not None:
                error = self.process.stderr.read().decode() if self.process.stderr else "Connection failed immediately"
                self.status = f"Failed: {error[:50]}"
                self.process = None
                if self.log_callback:
                    self.log_callback(f"Failed to connect to {self.profile['host']}: {error[:100]}")
                return False
            
            time.sleep(1)
            port_open = False
            for port in test_ports:
                if self.is_port_open('127.0.0.1', port, timeout=3):
                    port_open = True
                    break
            
            if not port_open:
                time.sleep(2)
                for port in test_ports:
                    if self.is_port_open('127.0.0.1', port, timeout=2):
                        port_open = True
                        break
            
            if not port_open:
                self.process.terminate()
                self.status = "Failed: Port not listening"
                self.process = None
                if self.log_callback:
                    self.log_callback(f"Tunnel to {self.profile['host']} failed: No local port listening")
                return False
            
            self.status = "Connected"
            if self.log_callback:
                self.log_callback(f"Connected to {self.profile['host']}")
            
            threading.Thread(target=self._monitor, daemon=True).start()
            return True
            
        except Exception as e:
            self.status = f"Error: {e}"
            if self.log_callback:
                self.log_callback(f"Error: {e}")
            return False
            
    def stop(self):
        self._stop_check.set()
        if self.process:
            try:
                self.process.terminate()
                time.sleep(0.5)
                if self.process.poll() is None:
                    self.process.kill()
            except Exception as e:
                pass
            self.process = None
            self.pid = None
        self.status = "Disconnected"
        if self.log_callback:
            self.log_callback(f"Disconnected from {self.profile['host']}")
            
    def _monitor(self):
        if self.process:
            self.process.wait()
            was_running = self.status == "Connected"
            self.status = "Disconnected"
            self.process = None
            if was_running and self.log_callback and not self._stop_check.is_set():
                self.log_callback(f"Tunnel to {self.profile['host']} disconnected unexpectedly")

class TunnelManager:
    def __init__(self, settings):
        self.settings = settings
        self.profiles = []
        self.tunnels = {}
        self.load_profiles()
        
    def load_profiles(self):
        if os.path.exists(self.settings.config_path):
            try:
                with open(self.settings.config_path, 'r') as f:
                    self.profiles = json.load(f)
            except:
                self.profiles = []
        else:
            self.profiles = []
            
    def save_profiles(self):
        try:
            os.makedirs(os.path.dirname(self.settings.config_path), exist_ok=True)
            with open(self.settings.config_path, 'w') as f:
                json.dump(self.profiles, f, indent=2)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save profiles: {e}")
            return False
            
    def get_tunnel(self, profile_id):
        if profile_id not in self.tunnels:
            profile = self.profiles[profile_id]
            self.tunnels[profile_id] = SSHTunnel(profile)
        return self.tunnels[profile_id]

class ProfileDialog(ctk.CTkToplevel):
    def __init__(self, parent, profile=None, profile_idx=None, save_callback=None):
        super().__init__(parent)
        self.profile = profile
        self.profile_idx = profile_idx
        self.save_callback = save_callback
        self.forwards_list = []
        
        self.title("Edit Profile" if profile else "Add Profile")
        self.geometry("600x700")
        self.transient(parent)
        self.grab_set()
        
        self.container = ctk.CTkFrame(self)
        self.container.pack(fill="both", expand=True, padx=20, pady=20)
        
        header_text = "Edit Profile" if profile else "New Profile"
        ctk.CTkLabel(self.container, text=header_text, font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(0, 20))
        
        self.name_var = tk.StringVar(value=profile.get('name', '') if profile else '')
        self.host_var = tk.StringVar(value=profile.get('host', '') if profile else '')
        self.port_var = tk.StringVar(value=str(profile.get('ssh_port', 22)) if profile else '22')
        self.user_var = tk.StringVar(value=profile.get('user', '') if profile else '')
        self.key_var = tk.StringVar(value=profile.get('key', '') if profile else '')
        
        self._create_form_row("Profile Name:", self.name_var, "e.g., Production MySQL")
        self._create_form_row("Host:", self.host_var, "e.g., 167.235.33.106")
        self._create_form_row("SSH Port:", self.port_var, "e.g., 1221")
        self._create_form_row("Username:", self.user_var, "e.g., akhan")
        self._create_key_row()
        
        ctk.CTkLabel(self.container, text="Port Forwards", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(20, 10))
        ctk.CTkLabel(self.container, text="Local Port → Remote Host:Remote Port", text_color="gray").pack(anchor="w")
        
        self.forwards_frame = ctk.CTkScrollableFrame(self.container, height=200)
        self.forwards_frame.pack(fill="x", pady=10)
        
        if profile and profile.get('forwards'):
            for fwd in profile['forwards']:
                self.add_forward(fwd.get('local', ''), fwd.get('remote_host', 'localhost'), fwd.get('remote', ''))
        else:
            self.add_forward()
        
        ctk.CTkButton(self.container, text="+ Add Another Port Forward", command=lambda: self.add_forward()).pack(pady=5)
        
        btn_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20)
        
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, fg_color="gray").pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Save", command=self.save).pack(side="right", padx=5)
        
    def _create_form_row(self, label, var, placeholder):
        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        frame.pack(fill="x", pady=5)
        ctk.CTkLabel(frame, text=label, width=100).pack(side="left")
        entry = ctk.CTkEntry(frame, textvariable=var, placeholder_text=placeholder)
        entry.pack(side="left", fill="x", expand=True, padx=5)
        
    def _create_key_row(self):
        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        frame.pack(fill="x", pady=5)
        ctk.CTkLabel(frame, text="SSH Key:", width=100).pack(side="left")
        entry = ctk.CTkEntry(frame, textvariable=self.key_var)
        entry.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(frame, text="Browse", width=80, command=self.browse_key).pack(side="left")
        
    def browse_key(self):
        path = filedialog.askopenfilename(filetypes=[("SSH Key", "*"), ("All Files", "*.*")])
        if path:
            self.key_var.set(path)
            
    def add_forward(self, local="", host="localhost", remote=""):
        row = ctk.CTkFrame(self.forwards_frame)
        row.pack(fill="x", pady=3)
        
        ctk.CTkLabel(row, text="Local", width=50).pack(side="left")
        local_entry = ctk.CTkEntry(row, width=70, placeholder_text="3306")
        local_entry.insert(0, local)
        local_entry.pack(side="left", padx=2)
        
        ctk.CTkLabel(row, text="→", width=20).pack(side="left")
        
        host_entry = ctk.CTkEntry(row, width=100, placeholder_text="localhost")
        host_entry.insert(0, host)
        host_entry.pack(side="left", padx=2)
        
        ctk.CTkLabel(row, text=":", width=10).pack(side="left")
        
        remote_entry = ctk.CTkEntry(row, width=70, placeholder_text="3306")
        remote_entry.insert(0, remote)
        remote_entry.pack(side="left", padx=2)
        
        remove_btn = ctk.CTkButton(row, text="×", width=30, fg_color="darkred", hover_color="red",
                                   command=lambda: self.remove_forward(row, data))
        remove_btn.pack(side="right", padx=5)
        
        data = {'local': local_entry, 'host': host_entry, 'remote': remote_entry, 'frame': row}
        self.forwards_list.append(data)
        
    def remove_forward(self, row, data):
        row.destroy()
        if data in self.forwards_list:
            self.forwards_list.remove(data)
            
    def save(self):
        if not all([self.name_var.get(), self.host_var.get(), self.user_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return
            
        forwards = []
        for f in self.forwards_list:
            local = f['local'].get()
            remote = f['remote'].get()
            if local and remote:
                forwards.append({
                    'local': local,
                    'remote': remote,
                    'remote_host': f['host'].get() or 'localhost'
                })
        
        if not forwards:
            messagebox.showerror("Error", "Add at least one port forward")
            return
            
        profile = {
            'name': self.name_var.get(),
            'host': self.host_var.get(),
            'ssh_port': int(self.port_var.get() or 22),
            'user': self.user_var.get(),
            'key': self.key_var.get(),
            'forwards': forwards
        }
        
        if self.save_callback:
            self.save_callback(profile, self.profile_idx)
        self.destroy()

class App:
    def __init__(self):
        self.settings = Settings()
        self.manager = TunnelManager(self.settings)
        
        self.root = ctk.CTk()
        self.root.title("SSH Tunnel Manager Pro")
        self.root.geometry("1000x700")
        self.root.minsize(900, 600)
        
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        self.card_refs = {}
        self.log_height = 120
        self.min_log_height = 60
        self.max_log_height = 400
        
        self._build_ui()
        self.update_status()
        
    def _build_ui(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self.root, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)
        
        title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=20, pady=(30, 20))
        ctk.CTkLabel(title_frame, text="🔒 Tunnel Manager", font=ctk.CTkFont(size=22, weight="bold")).pack()
        
        btn_style = {"width": 200, "height": 40, "corner_radius": 8}
        
        ctk.CTkButton(self.sidebar, text="+ Add Profile", command=self.add_profile, **btn_style).grid(row=1, column=0, padx=20, pady=10)
        ctk.CTkButton(self.sidebar, text="▶ Start All", command=self.start_all, fg_color="green", hover_color="darkgreen", **btn_style).grid(row=2, column=0, padx=20, pady=10)
        ctk.CTkButton(self.sidebar, text="⏹ Stop All", command=self.stop_all, fg_color="red", hover_color="darkred", **btn_style).grid(row=3, column=0, padx=20, pady=10)
        
        ctk.CTkFrame(self.sidebar, height=2, fg_color="gray30").grid(row=4, column=0, sticky="ew", padx=20, pady=20)
        
        ctk.CTkButton(self.sidebar, text="⚙ Settings", command=self.open_settings, fg_color="gray30", **btn_style).grid(row=5, column=0, padx=20, pady=10)
        
        self.sidebar_status = ctk.CTkLabel(self.sidebar, text="Ready", text_color="gray")
        self.sidebar_status.grid(row=7, column=0, padx=20, pady=20)
        
        # Main Content
        self.main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=0)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=0)
        
        # Header Stats
        self.header_frame = ctk.CTkFrame(self.main_frame)
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.header_frame.grid_columnconfigure(1, weight=1)
        self.header_frame.grid_columnconfigure(2, weight=1)
        
        self.stat_total = self._create_stat_card(self.header_frame, "Total Profiles", "0", 0)
        self.stat_active = self._create_stat_card(self.header_frame, "Active Tunnels", "0", 1, "green")
        self.stat_inactive = self._create_stat_card(self.header_frame, "Inactive", "0", 2, "red")
        
        # Profiles List
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        
        # Draggable Sash
        self.sash = ctk.CTkFrame(self.main_frame, height=6, fg_color="gray40", cursor="sb_v_double_arrow")
        self.sash.grid(row=2, column=0, sticky="ew", pady=(0, 0))
        self.sash.bind("<Button-1>", self._on_sash_click)
        self.sash.bind("<B1-Motion>", self._on_sash_drag)
        self.sash.bind("<Enter>", lambda e: self.sash.configure(fg_color="gray60"))
        self.sash.bind("<Leave>", lambda e: self.sash.configure(fg_color="gray40"))
        
        # Activity Log
        self.log_frame = ctk.CTkFrame(self.main_frame, height=self.log_height)
        self.log_frame.grid(row=3, column=0, sticky="ew", pady=(0, 0))
        self.log_frame.grid_propagate(False)
        
        ctk.CTkLabel(self.log_frame, text="Activity Log", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=5)
        self.log_text = ctk.CTkTextbox(self.log_frame, height=self.log_height-30, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.refresh_profiles()
        
    def _on_sash_click(self, event):
        self._sash_start_y = event.y_root
        self._sash_start_height = self.log_height
        
    def _on_sash_drag(self, event):
        delta = self._sash_start_y - event.y_root
        new_height = self._sash_start_height + delta
        new_height = max(self.min_log_height, min(self.max_log_height, new_height))
        
        if new_height != self.log_height:
            self.log_height = new_height
            self.log_frame.configure(height=self.log_height)
            self.log_text.configure(height=self.log_height-30)
            
    def _create_stat_card(self, parent, title, value, col, color=None):
        card = ctk.CTkFrame(parent)
        card.grid(row=0, column=col, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(card, text=title, text_color="gray").pack(pady=(10, 0))
        label = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=28, weight="bold"), text_color=color)
        label.pack(pady=(0, 10))
        return label
        
    def log(self, message):
        self.log_text.configure(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        
    def refresh_profiles(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.card_refs.clear()
        
        total = len(self.manager.profiles)
        active = sum(1 for i in range(total) if self.manager.get_tunnel(i).is_running())
        self.stat_total.configure(text=str(total))
        self.stat_active.configure(text=str(active))
        self.stat_inactive.configure(text=str(total - active))
        
        for idx, profile in enumerate(self.manager.profiles):
            self._create_profile_card(idx, profile)
            
    def _create_profile_card(self, idx, profile):
        card = ctk.CTkFrame(self.scroll_frame, border_width=2, border_color="gray30")
        card.grid(row=idx, column=0, sticky="ew", pady=8, padx=5)
        card.grid_columnconfigure(0, weight=0)
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(2, weight=0)
        
        status_frame = ctk.CTkFrame(card, width=60, fg_color="transparent")
        status_frame.grid(row=0, column=0, rowspan=2, padx=15, pady=15)
        status_frame.grid_propagate(False)
        
        status_circle = ctk.CTkLabel(status_frame, text="●", font=ctk.CTkFont(size=32), text_color="red")
        status_circle.pack(expand=True)
        
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="nsew", pady=15)
        
        name = profile.get('name', f'Profile {idx+1}')
        host = f"{profile['user']}@{profile['host']}:{profile.get('ssh_port', 22)}"
        
        ctk.CTkLabel(info_frame, text=name, font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=host, text_color="gray").pack(anchor="w", pady=2)
        
        forwards_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        forwards_frame.pack(anchor="w", pady=5)
        
        for fwd in profile.get('forwards', []):
            local = fwd['local']
            remote = f"{fwd.get('remote_host', 'localhost')}:{fwd['remote']}"
            
            tag = ctk.CTkFrame(forwards_frame, fg_color="gray80", corner_radius=6, border_width=1, border_color="gray60")
            tag.pack(side="left", padx=2)
            
            label = ctk.CTkLabel(tag, text=f"{local} → {remote}", font=ctk.CTkFont(size=11), text_color="gray10")
            label.pack(padx=8, pady=3)
        
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=15, pady=15)
        
        toggle_btn = ctk.CTkButton(btn_frame, text="Start", width=70, height=32, 
                                   command=lambda i=idx: self.toggle_tunnel(i))
        toggle_btn.pack(side="left", padx=2)
        
        ctk.CTkButton(btn_frame, text="Edit", width=60, height=32, fg_color="gray40",
                     command=lambda i=idx: self.edit_profile(i)).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="🗑", width=40, height=32, fg_color="darkred", 
                     command=lambda i=idx: self.delete_profile(i)).pack(side="left", padx=2)
        
        self.card_refs[idx] = {
            'card': card,
            'status': status_circle,
            'toggle_btn': toggle_btn
        }
        
    def toggle_tunnel(self, idx):
        tunnel = self.manager.get_tunnel(idx)
        tunnel.log_callback = self.log
        
        if tunnel.is_running():
            tunnel.stop()
            self.log(f"Stopped {self.manager.profiles[idx]['name']}")
        else:
            def connect():
                tunnel.start()
            threading.Thread(target=connect, daemon=True).start()
                
        self.refresh_profiles()
        
    def start_all(self):
        self.log("Starting all tunnels...")
        def start_all_thread():
            for i in range(len(self.manager.profiles)):
                tunnel = self.manager.get_tunnel(i)
                tunnel.log_callback = self.log
                if not tunnel.is_running():
                    tunnel.start()
                    time.sleep(0.5)
        threading.Thread(target=start_all_thread, daemon=True).start()
        
    def stop_all(self):
        self.log("Stopping all tunnels...")
        for i in range(len(self.manager.profiles)):
            self.manager.get_tunnel(i).stop()
        self.refresh_profiles()
        
    def update_status(self):
        active_count = 0
        for idx, refs in self.card_refs.items():
            tunnel = self.manager.get_tunnel(idx)
            status = tunnel.status
            
            if tunnel.is_running():
                refs['status'].configure(text_color="green")
                refs['toggle_btn'].configure(text="Stop", fg_color="red", hover_color="darkred")
                active_count += 1
            elif status.startswith("Failed") or status.startswith("Error"):
                refs['status'].configure(text_color="orange")
                refs['toggle_btn'].configure(text="Start", fg_color=["#3B8ED0", "#1F6AA5"])
            else:
                refs['status'].configure(text_color="red")
                refs['toggle_btn'].configure(text="Start", fg_color=["#3B8ED0", "#1F6AA5"])
                
        total = len(self.manager.profiles)
        self.stat_active.configure(text=str(active_count))
        self.stat_inactive.configure(text=str(total - active_count))
        
        if active_count > 0:
            self.sidebar_status.configure(text=f"{active_count} active", text_color="green")
        else:
            self.sidebar_status.configure(text="All tunnels stopped", text_color="gray")
            
        self.root.after(1000, self.update_status)
        
    def add_profile(self):
        dialog = ProfileDialog(self.root, save_callback=self.save_profile)
        
    def edit_profile(self, idx):
        profile = self.manager.profiles[idx]
        dialog = ProfileDialog(self.root, profile=profile, profile_idx=idx, save_callback=self.save_profile)
        
    def save_profile(self, profile, idx=None):
        if idx is not None:
            tunnel = self.manager.get_tunnel(idx)
            was_running = tunnel.is_running()
            if was_running:
                tunnel.stop()
            self.manager.profiles[idx] = profile
            if idx in self.manager.tunnels:
                del self.manager.tunnels[idx]
            self.log(f"Updated profile: {profile['name']}")
        else:
            self.manager.profiles.append(profile)
            self.log(f"Added new profile: {profile['name']}")
            
        self.manager.save_profiles()
        self.refresh_profiles()
        
    def delete_profile(self, idx):
        if messagebox.askyesno("Confirm", "Delete this profile?"):
            tunnel = self.manager.get_tunnel(idx)
            tunnel.stop()
            if idx in self.manager.tunnels:
                del self.manager.tunnels[idx]
            del self.manager.profiles[idx]
            self.manager.save_profiles()
            self.refresh_profiles()
            self.log("Profile deleted")
            
    def open_settings(self):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Settings", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)
        
        frame = ctk.CTkFrame(dialog)
        frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(frame, text="Config File Location:").pack(anchor="w", padx=10, pady=5)
        
        path_var = tk.StringVar(value=self.settings.config_path)
        entry = ctk.CTkEntry(frame, textvariable=path_var)
        entry.pack(fill="x", padx=10, pady=5)
        
        def browse():
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile="tunnel_profiles.json"
            )
            if path:
                path_var.set(path)
                
        ctk.CTkButton(frame, text="Browse...", command=browse).pack(anchor="e", padx=10, pady=5)
        
        def save():
            new_path = path_var.get()
            if new_path:
                if not os.path.exists(new_path) and os.path.exists(self.settings.config_path):
                    import shutil
                    shutil.copy(self.settings.config_path, new_path)
                self.settings.set_config_path(new_path)
                self.manager.settings = self.settings
                self.manager.load_profiles()
                self.refresh_profiles()
                self.log(f"Settings saved. Config: {new_path}")
                dialog.destroy()
                
        ctk.CTkButton(dialog, text="Save", command=save).pack(pady=20)
        
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = App()
    app.run()