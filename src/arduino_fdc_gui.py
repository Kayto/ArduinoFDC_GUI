#!/usr/bin/env python3
"""
Arduino FDC GUI - Graphical interface for Arduino Floppy Disk Controller
Connects to COM4 at 115200 baud with CR line termination and no local echo
"""

import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import serial
import threading
import time
import queue
from typing import Optional

from xmodem import XMODEM

class ArduinoFDCGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Arduino FDC GUI")
        self.root.geometry("900x700")
        self.root.minsize(750, 600)  # Minimum size
        
        # Maximize window on startup for better terminal visibility
        self.root.state('zoomed')
        
        # Serial connection settings
        self.serial_port = None
        self.port_name = "COM4"
        self.baud_rate = 115200
        self.connected = False
        
        # Communication queues
        self.tx_queue = queue.Queue()
        self.rx_queue = queue.Queue()
        
        # Current mode tracking
        self.current_mode = "ArduDOS"  # or "Monitor"
        self.switching_modes = False  # Flag to prevent recursive mode switching
        
        # Drive and disk type tracking for status bar
        self.current_drive = "A:"
        self.current_disk_type = "Unknown"
        # Per-drive disk type tracking
        self.drive_a_disk_type = "Unknown"
        self.drive_b_disk_type = "Unknown"
        
        # File listing cache
        self.current_files = []
        self.current_directory = ""
        self.current_path = ""  # Track current path for subdirectory navigation
        self.waiting_for_dir = False
        self.dir_output_buffer = ""
        
        # File content viewing
        self.waiting_for_file_content = False
        self.file_content_buffer = ""
        self.file_content_command = ""  # "type" or "dump"
        self.file_content_filename = ""
        
        # Command echo handling
        self.last_command = ""
        
        # Timing control to prevent disk change detection
        # The key is waiting for the motor to stop, not just arbitrary delays
        self.command_delay = 0.1  # Minimal base delay between commands
        self.last_command_time = 0
        
        # Motor and command completion tracking
        self.waiting_for_command_complete = False
        self.motor_stop_detected = False
        
        # Command completion tracking
        self.waiting_for_prompt = False
        self.last_prompt_time = 0
        
        # UI blocking for motor activity
        self.ui_blocked = False
        self.blocked_buttons = []  # Store buttons to disable/enable

        # XModem state tracking
        self.xmodem_state_lock = threading.Lock()
        self.xmodem_buffer_lock = threading.Lock()
        self.xmodem_active = False
        self.waiting_for_xmodem_banner = False
        self.xmodem_banner_event = threading.Event()
        self.xmodem_banner_text_bytes = b""
        self.xmodem_banner_buffer = bytearray()
        self.xmodem_prefetched = bytearray()
        self.xmodem_banner_found = False
        self.xmodem_operation = None
        self.xmodem_start_delay = 2.0
        self.xmodem_banner_timeout = 15.0
        self.xmodem_packet_timeout = 10.0
        self.xmodem_retry_limit = 16
        self.xmodem_total_size = 0
        self.xmodem_status_var = tk.StringVar(value="Idle")
        self.xmodem_progress_var = tk.StringVar(value="")
        
        # Status bar variables
        self.status_drive_var = tk.StringVar(value="Drive: A:")
        self.status_disktype_var = tk.StringVar(value="Disk Type: Unknown")
        self.status_mode_var = tk.StringVar(value="Mode: ArduDOS")
        
        # Log window state
        self.log_visible = False
        self.log_window = None
        
        self.setup_ui()
        self.start_communication_threads()
        
    def setup_ui(self):
        """Set up the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=0)  # Control panels - fixed width
        main_frame.columnconfigure(1, weight=1)  # Terminal - expands
        main_frame.rowconfigure(0, weight=0)     # Connection bar - fixed height  
        main_frame.rowconfigure(1, weight=1)     # Main content - expands
        main_frame.rowconfigure(2, weight=0)     # Log window - fixed height (optional)
        main_frame.rowconfigure(3, weight=0)     # Status bar - fixed height
        
        # Store main_frame for later log window access
        self.main_frame = main_frame
        
        # Connection frame
        self.setup_connection_frame(main_frame)
        
        # Terminal frame
        self.setup_terminal_frame(main_frame)
        
        # Control panels frame
        self.setup_control_panels(main_frame)
        
        # Status bar at bottom
        self.setup_status_bar(main_frame)
        
    def setup_connection_frame(self, parent):
        """Set up connection controls"""
        conn_frame = ttk.LabelFrame(parent, text="Connection", padding="5")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=(0, 5))
        
        self.port_var = tk.StringVar(value=self.port_name)
        port_entry = ttk.Entry(conn_frame, textvariable=self.port_var, width=10)
        port_entry.grid(row=0, column=1, padx=(0, 10))
        
        ttk.Label(conn_frame, text="Baud:").grid(row=0, column=2, padx=(0, 5))
        
        self.baud_var = tk.StringVar(value=str(self.baud_rate))
        baud_entry = ttk.Entry(conn_frame, textvariable=self.baud_var, width=10)
        baud_entry.grid(row=0, column=3, padx=(0, 10))
        
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=4, padx=(0, 10))
        
        self.status_label = ttk.Label(conn_frame, text="Disconnected", foreground="red")
        self.status_label.grid(row=0, column=5, padx=(0, 10))
        
        # Log toggle button
        self.log_toggle_btn = ttk.Button(conn_frame, text="Show Log", command=self.toggle_log_window, width=10)
        self.log_toggle_btn.grid(row=0, column=6, padx=(0, 10))
        
        # Credit to original author
        ttk.Label(conn_frame, text="ArduinoFDC by David Hansel", 
                 font=("", 8), foreground="gray").grid(row=0, column=7, padx=(10, 0))
        
    def setup_terminal_frame(self, parent):
        """Set up terminal interface"""
        terminal_frame = ttk.LabelFrame(parent, text="Terminal", padding="5")
        terminal_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        terminal_frame.columnconfigure(0, weight=1)
        terminal_frame.rowconfigure(0, weight=1)
        
        # Terminal display
        self.terminal_display = scrolledtext.ScrolledText(
            terminal_frame, 
            height=25, 
            width=80,
            font=("Consolas", 10),
            wrap=tk.NONE,
            state=tk.DISABLED
        )
        self.terminal_display.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Command input
        ttk.Label(terminal_frame, text="Command:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
        self.command_var = tk.StringVar()
        self.command_entry = ttk.Entry(terminal_frame, textvariable=self.command_var, font=("Consolas", 10))
        self.command_entry.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(2, 0))
        self.command_entry.bind('<Return>', self.send_command)
        
        self.send_btn = ttk.Button(terminal_frame, text="Send", command=self.send_command)
        self.send_btn.grid(row=2, column=1, padx=(5, 0), pady=(2, 0))
        
        # Clear button
        clear_btn = ttk.Button(terminal_frame, text="Clear", command=self.clear_terminal)
        clear_btn.grid(row=3, column=0, sticky=tk.W, pady=(5, 0))
        
    def setup_control_panels(self, parent):
        """Set up control panels with tabs for commands"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 5))  # Don't expand vertically (no S)
        
        # ArduDOS tab
        self.ardudos_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.ardudos_tab, text="ArduDOS Commands")
        
        # Monitor tab
        self.monitor_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.monitor_tab, text="Monitor Commands")
        
        # Set up panels in their respective tabs
        self.setup_ardudos_panel(self.ardudos_tab)
        self.setup_monitor_panel(self.monitor_tab)
        
        # Bind tab change event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_change)
    
    def setup_status_bar(self, parent):
        """Set up status bar at bottom of window"""
        status_frame = ttk.Frame(parent, relief=tk.SUNKEN, padding="2")
        status_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Status sections
        ttk.Label(status_frame, textvariable=self.status_mode_var, 
                 relief=tk.SUNKEN, padding="2 1").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(status_frame, textvariable=self.status_drive_var,
                 relief=tk.SUNKEN, padding="2 1").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(status_frame, textvariable=self.status_disktype_var,
                 relief=tk.SUNKEN, padding="2 1").pack(side=tk.LEFT, padx=(0, 10))
        
        # XModem status on the right side
        xmodem_status_frame = ttk.Frame(status_frame)
        xmodem_status_frame.pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Label(xmodem_status_frame, text="XModem:").pack(side=tk.LEFT)
        ttk.Label(xmodem_status_frame, textvariable=self.xmodem_status_var,
                 foreground="blue").pack(side=tk.LEFT, padx=(5, 10))
        ttk.Label(xmodem_status_frame, textvariable=self.xmodem_progress_var,
                 foreground="green").pack(side=tk.LEFT)
    
    def toggle_log_window(self):
        """Toggle visibility of log window"""
        if self.log_visible:
            # Hide log window
            if self.log_window:
                self.log_window.grid_remove()
            self.log_visible = False
            self.log_toggle_btn.config(text="Show Log")
        else:
            # Show log window
            if not self.log_window:
                self.setup_log_window(self.main_frame)
            self.log_window.grid()
            self.log_visible = True
            self.log_toggle_btn.config(text="Hide Log")
    
    def setup_log_window(self, parent):
        """Set up log window frame"""
        log_frame = ttk.LabelFrame(parent, text="Activity Log", padding="5")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        log_frame.columnconfigure(0, weight=1)
        
        # Log display
        self.log_display = scrolledtext.ScrolledText(
            log_frame,
            height=6,
            font=("Consolas", 8),
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.log_display.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Clear log button
        ttk.Button(log_frame, text="Clear Log", command=self.clear_log, width=12).grid(row=0, column=1, padx=(5, 0))
        
        self.log_window = log_frame
    
    def log(self, message):
        """Add message to log window if visible"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        # Always print to console
        print(log_message.strip())
        
        # Add to log window if it exists
        if self.log_window and self.log_visible:
            self.log_display.config(state=tk.NORMAL)
            self.log_display.insert(tk.END, log_message)
            self.log_display.see(tk.END)
            self.log_display.config(state=tk.DISABLED)
    
    def clear_log(self):
        """Clear the log window"""
        if self.log_display:
            self.log_display.config(state=tk.NORMAL)
            self.log_display.delete(1.0, tk.END)
            self.log_display.config(state=tk.DISABLED)
        
    def setup_ardudos_panel(self, parent):
        """Set up ArduDOS command panel with file browser"""
        # Main container with padding
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # File browser frame (left side)
        browser_frame = ttk.LabelFrame(main_frame, text="File Browser", padding="8")
        browser_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        browser_frame.columnconfigure(0, weight=1)
        browser_frame.rowconfigure(1, weight=1)
        
        # Current directory display - compact layout
        dir_frame = ttk.Frame(browser_frame)
        dir_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Directory path on first row
        path_frame = ttk.Frame(dir_frame)
        path_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        path_frame.columnconfigure(1, weight=1)
        
        ttk.Label(path_frame, text="Dir:").grid(row=0, column=0, sticky=tk.W)
        self.current_dir_var = tk.StringVar(value="A:\\")
        dir_label = ttk.Label(path_frame, textvariable=self.current_dir_var, font=("Consolas", 9), width=25)
        dir_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # Navigation buttons on second row - compact
        nav_frame = ttk.Frame(dir_frame)
        nav_frame.grid(row=1, column=0, sticky=tk.W, pady=(3, 0))
        
        self.refresh_btn = ttk.Button(nav_frame, text="Refresh", width=8, command=self.refresh_current_directory)
        self.refresh_btn.grid(row=0, column=0, padx=(0, 5))
        self.home_btn = ttk.Button(nav_frame, text="Home", width=6, command=self.refresh_file_list)
        self.home_btn.grid(row=0, column=1, padx=(0, 5))
        self.up_btn = ttk.Button(nav_frame, text="Up", width=4, command=self.navigate_up)
        self.up_btn.grid(row=0, column=2)
        
        # File listbox with scrollbar
        list_frame = ttk.Frame(browser_frame)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        self.file_listbox = tk.Listbox(list_frame, font=("Consolas", 9), height=15, width=25)
        self.file_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Add double-click handler for directory navigation
        self.file_listbox.bind("<Double-1>", self.on_file_double_click)
        
        file_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_listbox.yview)
        file_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.file_listbox.configure(yscrollcommand=file_scrollbar.set)
        
        # Bind double-click event
        self.file_listbox.bind('<Double-1>', self.on_file_double_click)
        
        # Commands frame (right side)
        commands_frame = ttk.Frame(main_frame)
        commands_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        # File operations
        file_frame = ttk.LabelFrame(commands_frame, text="File Operations", padding="8")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        
        self.type_btn = ttk.Button(file_frame, text="TYPE", width=12, command=self.type_selected_file)
        self.type_btn.grid(row=0, column=0, padx=3, pady=3)
        self.dump_btn = ttk.Button(file_frame, text="DUMP", width=12, command=self.dump_selected_file)
        self.dump_btn.grid(row=0, column=1, padx=3, pady=3)
        self.delete_btn = ttk.Button(file_frame, text="DELETE", width=12, command=self.delete_selected_file)
        self.delete_btn.grid(row=1, column=0, padx=3, pady=3)
        self.write_btn = ttk.Button(file_frame, text="WRITE New", width=12, command=self.write_file)
        self.write_btn.grid(row=1, column=1, padx=3, pady=3)
        
        # Directory operations
        dir_ops_frame = ttk.LabelFrame(commands_frame, text="Directory Operations", padding="8")
        dir_ops_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        
        ttk.Button(dir_ops_frame, text="MKDIR", width=12, command=self.make_directory).grid(row=0, column=0, padx=3, pady=3)
        ttk.Button(dir_ops_frame, text="RMDIR", width=12, command=self.remove_directory).grid(row=0, column=1, padx=3, pady=3)
        
        # Drive operations
        drive_frame = ttk.LabelFrame(commands_frame, text="Drive Selection", padding="8")
        drive_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        
        ttk.Button(drive_frame, text="Drive A:", width=12, command=lambda: self.switch_drive("a:")).grid(row=0, column=0, padx=3, pady=3)
        ttk.Button(drive_frame, text="Drive B:", width=12, command=lambda: self.switch_drive("b:")).grid(row=0, column=1, padx=3, pady=3)
        
        # Disk operations
        disk_frame = ttk.LabelFrame(commands_frame, text="Disk Operations", padding="8")
        disk_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        
        ttk.Button(disk_frame, text="FORMAT (MS-DOS)", width=25, command=self.format_disk).grid(row=0, column=0, columnspan=2, padx=3, pady=3)
        ttk.Button(disk_frame, text="Help", width=12, command=lambda: self.send_cmd("help")).grid(row=1, column=0, columnspan=2, padx=3, pady=3)

        # XModem operations
        xmodem_frame = ttk.LabelFrame(commands_frame, text="XModem Transfers", padding="8")
        xmodem_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 8))

        self.xmodem_send_btn = ttk.Button(
            xmodem_frame,
            text="Send File",
            width=18,
            command=self.xmodem_send_dialog,
        )
        self.xmodem_send_btn.grid(row=0, column=0, padx=3, pady=3, sticky=tk.W)

        self.xmodem_receive_btn = ttk.Button(
            xmodem_frame,
            text="Receive File",
            width=18,
            command=self.xmodem_receive_dialog,
        )
        self.xmodem_receive_btn.grid(row=1, column=0, padx=3, pady=3, sticky=tk.W)

        # XModem status now shown in bottom status bar
        ttk.Label(xmodem_frame, text="(Status shown in bottom status bar)",
                 font=("", 8), foreground="gray").grid(row=2, column=0, columnspan=2, pady=5)
        
        # Disk type setting
        type_frame = ttk.LabelFrame(commands_frame, text="Disk Type Selection", padding="8")
        type_frame.grid(row=5, column=0, sticky=(tk.W, tk.E))
        
        disk_types = [
            ("5.25\" DD", "disktype 0"),
            ("5.25\" HD", "disktype 2"),
            ("3.5\" DD", "disktype 3"),
            ("3.5\" HD", "disktype 4")
        ]
        
        # Layout the first 4 buttons in a 2x2 grid
        for i, (label, cmd) in enumerate(disk_types):
            ttk.Button(type_frame, text=label, width=12,
                      command=lambda c=cmd, l=label: self.set_disk_type(c, l)).grid(row=i//2, column=i%2, padx=3, pady=3)
        
        # Add the "5.25\" DD in HD" button on its own row below the others
        ttk.Button(type_frame, text="5.25\" DD in HD", width=14,
                  command=lambda: self.set_disk_type("disktype 1", "5.25\" DD in HD")).grid(row=2, column=0, columnspan=2, padx=3, pady=3)
    
    def set_disk_type(self, command, disk_type_name):
        """Set disk type and update status bar (ArduDOS or Monitor)"""
        self.send_cmd(command)
        self.current_disk_type = disk_type_name
        # Store disk type for current drive
        if self.current_drive == "A:":
            self.drive_a_disk_type = disk_type_name
        else:
            self.drive_b_disk_type = disk_type_name
        self.status_disktype_var.set(f"Disk Type: {disk_type_name}")
        self.log(f"Disk type set to {disk_type_name} for {self.current_drive}")
    
    def monitor_switch_drive(self, drive_cmd, drive_letter):
        """Switch drive in Monitor mode and update status bar directly"""
        self.send_cmd(drive_cmd)
        self.current_drive = f"{drive_letter}:"
        self.current_path = ""
        self.current_dir_var.set(f"{drive_letter}:\\")
        self.status_drive_var.set(f"Drive: {drive_letter}:")
        # Restore disk type for the selected drive
        if drive_letter == "A":
            self.current_disk_type = self.drive_a_disk_type
        else:
            self.current_disk_type = self.drive_b_disk_type
        self.status_disktype_var.set(f"Disk Type: {self.current_disk_type}")
        self.log(f"Monitor drive switched to {drive_letter}: (disk type: {self.current_disk_type})")
        
    def setup_monitor_panel(self, parent):
        """Set up Monitor command panel - compact layout"""
        # Main container with padding - limit height
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N))  # Don't expand vertically
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Set maximum height for the entire monitor panel
        parent.grid_propagate(False)  # Don't let children control parent size
        parent.configure(height=360)  # Allow room for disk transfer controls
        
        # Sector operations - more compact
        sector_frame = ttk.LabelFrame(main_frame, text="Sector Operations", padding="5")
        sector_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Input fields for sector addressing - single row
        input_frame = ttk.Frame(sector_frame)
        input_frame.grid(row=0, column=0, columnspan=4, pady=(0, 5))
        
        ttk.Label(input_frame, text="Track:").grid(row=0, column=0, sticky=tk.W)
        self.track_var = tk.StringVar(value="0")
        ttk.Entry(input_frame, textvariable=self.track_var, width=5).grid(row=0, column=1, padx=(2, 10))
        
        ttk.Label(input_frame, text="Sector:").grid(row=0, column=2, sticky=tk.W)
        self.sector_var = tk.StringVar(value="1")
        ttk.Entry(input_frame, textvariable=self.sector_var, width=5).grid(row=0, column=3, padx=(2, 10))
        
        ttk.Label(input_frame, text="Head:").grid(row=0, column=4, sticky=tk.W)
        self.head_var = tk.StringVar(value="0")
        ttk.Entry(input_frame, textvariable=self.head_var, width=5).grid(row=0, column=5, padx=(2, 0))
        
        # Sector operation buttons - compact
        ttk.Button(sector_frame, text="Read Sector", width=10, command=self.read_sector).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(sector_frame, text="Write Sector", width=10, command=self.write_sector).grid(row=1, column=1, padx=2, pady=2)
        ttk.Button(sector_frame, text="Read All", width=10, command=lambda: self.send_cmd("r")).grid(row=1, column=2, padx=2, pady=2)
        ttk.Button(sector_frame, text="Read All", width=10, command=lambda: self.send_cmd("r")).grid(row=1, column=2, padx=2, pady=2)
        
        # Buffer and Drive operations in one row - more compact
        ops_frame = ttk.Frame(main_frame)
        ops_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Buffer operations - compact
        buffer_frame = ttk.LabelFrame(ops_frame, text="Buffer Operations", padding="5")
        buffer_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        ttk.Button(buffer_frame, text="Show Buffer", width=10, command=lambda: self.send_cmd("b")).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(buffer_frame, text="Fill Buffer", width=10, command=self.fill_buffer).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(buffer_frame, text="Fill Pattern", width=10, command=lambda: self.send_cmd("B")).grid(row=1, column=0, padx=2, pady=2)
        
        # Drive control - compact
        control_frame = ttk.LabelFrame(ops_frame, text="Drive Control", padding="5")
        control_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        ttk.Button(control_frame, text="Motor On", width=9, command=lambda: self.send_cmd("m 1")).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(control_frame, text="Motor Off", width=9, command=lambda: self.send_cmd("m 0")).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(control_frame, text="Drive A", width=9, command=lambda: self.monitor_switch_drive("s 0", "A")).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(control_frame, text="Drive B", width=9, command=lambda: self.monitor_switch_drive("s 1", "B")).grid(row=1, column=1, padx=2, pady=2)
        
        # Disk type - compact single row
        type_frame = ttk.LabelFrame(main_frame, text="Drive Type Setting", padding="5")
        type_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        monitor_types = [
            ("5.25\" DD", "t 0"),
            ("5.25\" HD", "t 2"),
            ("3.5\" DD", "t 3"),
            ("3.5\" HD", "t 4")
        ]
        
        # Compact disk type buttons in single row (first 4 buttons)
        for i, (label, cmd) in enumerate(monitor_types):
            ttk.Button(type_frame, text=label, width=10,
                      command=lambda c=cmd, l=label: self.set_disk_type(c, l)).grid(row=0, column=i, padx=2, pady=2)
        
        # Add the "5.25\" DD in HD" button on its own row below
        ttk.Button(type_frame, text="5.25\" DD in HD", width=14,
                  command=lambda: self.set_disk_type("t 1", '5.25" DD in HD')).grid(row=1, column=0, columnspan=4, padx=2, pady=2)
        
        # Advanced operations - compact
        adv_frame = ttk.LabelFrame(main_frame, text="Advanced", padding="5")
        adv_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        ttk.Button(adv_frame, text="Format", width=10, command=self.monitor_format).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(adv_frame, text="Write All", width=10, command=self.write_all_sectors).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(adv_frame, text="Help", width=10, command=lambda: self.send_cmd("h")).grid(row=0, column=2, padx=2, pady=2)

        # Disk image transfers (XModem S/R)
        xfer_frame = ttk.LabelFrame(main_frame, text="Disk Image Transfers", padding="5")
        xfer_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))

        self.monitor_receive_disk_btn = ttk.Button(
            xfer_frame,
            text="Download Disk (S)",
            width=18,
            command=self.monitor_receive_disk_image,
        )
        self.monitor_receive_disk_btn.grid(row=0, column=0, padx=2, pady=2, sticky=tk.W)

        self.monitor_send_disk_btn = ttk.Button(
            xfer_frame,
            text="Upload Disk (R)",
            width=18,
            command=self.monitor_send_disk_image,
        )
        self.monitor_send_disk_btn.grid(row=0, column=1, padx=2, pady=2, sticky=tk.W)
        
    def toggle_connection(self):
        """Toggle serial connection"""
        if self.connected:
            self.disconnect()
        else:
            self.connect()
            
    def connect(self):
        """Connect to Arduino FDC"""
        try:
            self.port_name = self.port_var.get()
            self.baud_rate = int(self.baud_var.get())
            
            self.serial_port = serial.Serial(
                port=self.port_name,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            
            self.connected = True
            self.connect_btn.config(text="Disconnect")
            self.status_label.config(text="Connected", foreground="green")
            self.append_to_terminal("Connected to " + self.port_name + "\n")
            
            # Reset drive and disk type status to defaults (Arduino resets to A: on connect)
            self.current_drive = "A:"
            self.current_path = ""
            self.current_disk_type = "Unknown"
            self.drive_a_disk_type = "Unknown"
            self.drive_b_disk_type = "Unknown"
            self.current_dir_var.set("A:\\")
            self.status_drive_var.set("Drive: A:")
            self.status_disktype_var.set("Disk Type: Unknown")
            self.status_mode_var.set("Mode: ArduDOS")
            
            # Initialize in ArduDOS mode - user will manually refresh when ready
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
            
    def disconnect(self):
        """Disconnect from Arduino FDC"""
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            
            self.connected = False
            self.connect_btn.config(text="Connect")
            self.status_label.config(text="Disconnected", foreground="red")
            self.append_to_terminal("Disconnected\n")
            
            # Reset drive and disk type status to defaults
            self.current_drive = "A:"
            self.current_path = ""
            self.current_disk_type = "Unknown"
            self.drive_a_disk_type = "Unknown"
            self.drive_b_disk_type = "Unknown"
            self.current_dir_var.set("A:\\")
            self.status_drive_var.set("Drive: A:")
            self.status_disktype_var.set("Disk Type: Unknown")
            self.status_mode_var.set("Mode: ArduDOS")
            
            # Unblock UI when disconnecting
            self.unblock_ui_for_motor()
            self.waiting_for_command_complete = False
            self.waiting_for_prompt = False
            
        except Exception as e:
            messagebox.showerror("Disconnection Error", f"Failed to disconnect: {str(e)}")
            
    def start_communication_threads(self):
        """Start communication threads"""
        # Receive thread
        self.rx_thread = threading.Thread(target=self.receive_data, daemon=True)
        self.rx_thread.start()
        
        # Process received data
        self.root.after(100, self.process_received_data)
        
    def receive_data(self):
        """Receive data from serial port"""
        while True:
            try:
                if self.connected and self.serial_port and self.serial_port.is_open:
                    if self.serial_port.in_waiting > 0:
                        if self.xmodem_active:
                            time.sleep(0.01)
                            continue

                        data_bytes = self.serial_port.read(self.serial_port.in_waiting)
                        if not data_bytes:
                            time.sleep(0.01)
                            continue

                        data_text = data_bytes.decode('utf-8', errors='ignore')
                        self.rx_queue.put((data_text, data_bytes))
                time.sleep(0.01)
            except Exception as e:
                if self.connected:
                    self.rx_queue.put((f"\nSerial error: {str(e)}\n", b""))
                time.sleep(0.1)
                
    def process_received_data(self):
        """Process data from receive queue"""
        try:
            while not self.rx_queue.empty():
                entry = self.rx_queue.get_nowait()
                if isinstance(entry, tuple):
                    data, raw_bytes = entry
                else:
                    data = entry
                    raw_bytes = data.encode('utf-8', errors='ignore') if isinstance(data, str) else b""

                # If XModem is active, let it consume all the data
                if raw_bytes:
                    xmodem_consumed = self._handle_xmodem_prefetch(raw_bytes)
                    if xmodem_consumed:
                        # Don't display or process this data - XModem owns it
                        continue

                self.append_to_terminal(data)
                
                # Track command completion by looking for prompts
                if ":>" in data or "Command:" in data:
                    was_waiting = self.waiting_for_command_complete
                    # Clear flags FIRST to prevent race conditions
                    self.waiting_for_command_complete = False
                    self.waiting_for_prompt = False
                    self.last_prompt_time = time.time()
                    
                    if was_waiting:
                        self.log(f"Command completed - prompt detected: '{data.strip()}'")
                        self.unblock_ui_for_motor()
                        if self.connected:
                            self.status_label.config(text="Connected", foreground="green")
                
                # Check if we're waiting for DIR output and process it
                if self.waiting_for_dir:
                    self.dir_output_buffer += data
                    self.log(f"Added to DIR buffer: '{data[:50]}...' (total buffer: {len(self.dir_output_buffer)} chars)")
                    # Look for the end of DIR output (prompt appears)
                    if ":>" in data or "Command:" in data:
                        self.log("DIR command completed, parsing output...")
                        self.parse_real_dir_output()
                        self.waiting_for_dir = False
                        self.dir_output_buffer = ""
                
                # Check if we're waiting for file content (TYPE/DUMP) and process it
                if self.waiting_for_file_content:
                    self.file_content_buffer += data
                    # Look for the end of file content (prompt appears)
                    if ":>" in data or "Command:" in data:
                        self.show_file_content_viewer()
                        self.waiting_for_file_content = False
                        self.file_content_buffer = ""
                        
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_received_data)
            
    def _handle_xmodem_prefetch(self, raw_bytes: bytes) -> None:
        """Buffer all serial data during XModem operations.
        
        Returns True if data was consumed by XModem system, False otherwise.
        """
        if not self.waiting_for_xmodem_banner or not raw_bytes:
            return False

        with self.xmodem_buffer_lock:
            pattern = self.xmodem_banner_text_bytes
            if not pattern:
                return False

            self.xmodem_banner_buffer.extend(raw_bytes)

            if not self.xmodem_banner_found:
                if pattern in self.xmodem_banner_buffer:
                    idx = self.xmodem_banner_buffer.find(pattern)
                    end_idx = idx + len(pattern)
                    remainder = self.xmodem_banner_buffer[end_idx:]
                    cleaned = self._sanitize_xmodem_remainder(bytes(remainder))
                    if cleaned:
                        self.xmodem_prefetched.extend(cleaned)
                    self.xmodem_banner_buffer = bytearray()
                    self.xmodem_banner_found = True
                    self.xmodem_banner_event.set()
                else:
                    max_len = len(pattern) + 64
                    if len(self.xmodem_banner_buffer) > max_len:
                        self.xmodem_banner_buffer = self.xmodem_banner_buffer[-max_len:]
            else:
                # After banner found, continue buffering all data for XModem
                self.xmodem_prefetched.extend(raw_bytes)
        
        return True  # Data was consumed by XModem system

    def _sanitize_xmodem_remainder(self, data: bytes) -> bytes:
        """Strip banner text, prompts, and whitespace before XModem handshake."""
        if not data:
            return b""

        # Drop anything up to and including the next newline (banner tail)
        newline_idx = data.find(b"\n")
        if newline_idx != -1:
            data = data[newline_idx + 1 :]

        # Remove carriage returns and leading whitespace remnants
        data = data.lstrip(b"\r\n \t")

        # Remove prompt prefixes like "A:>" that may appear before the transfer
        for prompt in (b"A:>", b"B:>", b"C:>", b"D:>"):
            if data.startswith(prompt):
                data = data[len(prompt) :]
                data = data.lstrip(b"\r\n \t")

        # Remove leading "Command:" echoes if present
        if data.lower().startswith(b"command:"):
            newline = data.find(b"\n")
            if newline != -1:
                data = data[newline + 1 :]
            else:
                data = b""
            data = data.lstrip(b"\r\n \t")

        # Discard any printable text prior to the handshake start (C/NAK/CAN/ACK/EOT)
        handshake_bytes = {0x43, 0x15, 0x18, 0x06, 0x04}
        start_idx = None
        for idx, byte in enumerate(data):
            if byte in handshake_bytes or byte < 0x20:
                start_idx = idx
                break

        if start_idx is not None:
            data = data[start_idx:]
        else:
            data = b""

        cleaned = data.lstrip(b"\r\n")
        if cleaned:
            # Collapse repeated handshake initiators ("C" or NAK spam) to a single byte
            initiators = (0x43, 0x15)
            idx = 0
            while idx < len(cleaned) and cleaned[idx] in initiators:
                idx += 1
            if idx > 1:
                cleaned = cleaned[idx - 1 :]

        if cleaned:
            print(f"DEBUG sanitize remainder -> {cleaned!r}")
        return cleaned

    def _prune_prefetched_handshake(self) -> None:
        """Drop duplicate leading handshake initiators to avoid confusing pyXMODEM."""
        with self.xmodem_buffer_lock:
            if not self.xmodem_prefetched:
                return

            initiators = (0x43, 0x15)
            idx = 0
            prefetched = self.xmodem_prefetched
            while idx < len(prefetched) and prefetched[idx] in initiators:
                idx += 1

            if idx > 1:
                del prefetched[: idx - 1]
                print(
                    f"DEBUG prune_prefetched_handshake removed {idx - 1} duplicate initiators"
                )

    def _trim_xmodem_padding(self, path: str) -> int:
        try:
            with open(path, "r+b") as handle:
                handle.seek(0, os.SEEK_END)
                file_size = handle.tell()
                if file_size == 0:
                    return 0

                pad_bytes = 0
                remaining = file_size
                while remaining > 0:
                    chunk_size = min(4096, remaining)
                    remaining -= chunk_size
                    handle.seek(remaining)
                    chunk = handle.read(chunk_size)
                    idx = len(chunk) - 1
                    while idx >= 0 and chunk[idx] == 0x1A:
                        pad_bytes += 1
                        idx -= 1
                    if idx >= 0:
                        break

                if pad_bytes:
                    handle.truncate(file_size - pad_bytes)
                return pad_bytes
        except OSError:
            return 0

    def append_to_terminal(self, text):
        """Append text to terminal display"""
        self.terminal_display.config(state=tk.NORMAL)
        self.terminal_display.insert(tk.END, text)
        self.terminal_display.see(tk.END)
        self.terminal_display.config(state=tk.DISABLED)
        
    def clear_terminal(self):
        """Clear terminal display"""
        self.terminal_display.config(state=tk.NORMAL)
        self.terminal_display.delete(1.0, tk.END)
        self.terminal_display.config(state=tk.DISABLED)
        
    def send_command(self, event=None):
        """Send command from entry field"""
        command = self.command_var.get().strip()
        if command:
            self.send_cmd(command)
            self.command_var.set("")
            
    def send_cmd(self, command, no_wait: bool = False):
        """Send command to Arduino FDC with proper command completion waiting"""
        if not self.connected or not self.serial_port:
            messagebox.showwarning("Not Connected", "Please connect to Arduino FDC first")
            return
            
        try:
            stripped = command.strip()
            inline_response = stripped.lower() in {"y", "n", "yes", "no"}
            waiting_already = self.waiting_for_command_complete

            # Wait for previous command to complete (motor to stop)
            if waiting_already and not inline_response and not no_wait:
                self.log(f"Waiting for previous command to complete before sending: '{command}'")
                timeout = 3.0  # 3 second timeout (reduced from 10s for better responsiveness)
                start_time = time.time()
                check_count = 0
                while self.waiting_for_command_complete and (time.time() - start_time) < timeout:
                    time.sleep(0.05)  # Shorter sleep for faster response
                    self.root.update()  # Process any incoming data
                    check_count += 1
                    # Extra check every 10 iterations (0.5s)
                    if check_count % 10 == 0 and not self.waiting_for_command_complete:
                        break
                
                if self.waiting_for_command_complete:
                    self.log(f"Timeout waiting for command completion after {timeout}s, proceeding anyway")
                    # Force clear the flag to prevent cascading timeouts
                    self.waiting_for_command_complete = False
                    self.waiting_for_prompt = False
            
            # Minimal delay between commands
            current_time = time.time()
            time_since_last = current_time - self.last_command_time
            if time_since_last < self.command_delay:
                delay_needed = self.command_delay - time_since_last
                time.sleep(delay_needed)
            
            # Send command with CR termination (as specified)
            cmd_bytes = (command + '\r').encode('utf-8')
            self.serial_port.write(cmd_bytes)
            try:
                self.serial_port.flush()
            except Exception:
                pass
            
            # Mark that we're waiting for this command to complete unless it's an inline response
            if inline_response and waiting_already:
                # Keep existing wait state without resetting prompt tracking
                pass
            else:
                if not no_wait:
                    # Motor commands and simple queries respond quickly
                    is_quick_command = stripped.lower().startswith(('m ', 's ', 'h', '?'))
                    self.waiting_for_command_complete = True
                    self.waiting_for_prompt = True
                    if is_quick_command:
                        self.log(f"Quick command detected: '{command}'")
            
            # Update timing
            self.last_command_time = time.time()
            
            # Don't add local echo - Arduino FDC provides its own echo
            # Store the last command for echo filtering if needed
            self.last_command = stripped
            
            if no_wait:
                self.log(f"Sent command: '{command}' - no wait for completion")
            else:
                wait_status = "already waiting" if waiting_already else "now waiting"
                self.log(f"Sent command: '{command}' - {wait_status} for completion")
            
            # Automatically set up DIR monitoring for any dir command
            if self.current_mode == "ArduDOS" and stripped.lower().startswith('dir'):
                self.waiting_for_dir = True
                self.dir_output_buffer = ""
                self.log(f"Set up DIR monitoring for command: '{command}'")
            
            # Update status bar for drive switch commands
            if self.current_mode == "ArduDOS" and stripped.lower() in ['a:', 'b:', 'c:', 'd:']:
                drive_letter = stripped.upper()[0]
                self.current_drive = f"{drive_letter}:"
                self.current_path = ""  # Reset to root when changing drives
                self.current_dir_var.set(f"{drive_letter}:\\")
                self.status_drive_var.set(f"Drive: {drive_letter}:")
                # Restore disk type for the selected drive
                if drive_letter == "A":
                    self.current_disk_type = self.drive_a_disk_type
                else:
                    self.current_disk_type = self.drive_b_disk_type
                self.status_disktype_var.set(f"Disk Type: {self.current_disk_type}")
                self.log(f"Drive switch detected - updated status bar to {drive_letter}:")
            
            # Update status bar for Monitor mode drive switch commands (s 0 = Drive A, s 1 = Drive B)
            # Match 's' followed by 0 or 1 with any spacing: s0, s 0, s  0, etc.
            # No mode check needed - these commands are exclusively for Monitor mode
            cmd_lower = stripped.lower().replace(' ', '')
            if cmd_lower in ['s0', 's1']:
                drive_letter = "A" if cmd_lower == 's0' else "B"
                self.current_drive = f"{drive_letter}:"
                self.current_path = ""  # Reset to root when changing drives
                self.current_dir_var.set(f"{drive_letter}:\\")
                self.status_drive_var.set(f"Drive: {drive_letter}:")
                # Restore disk type for the selected drive
                if drive_letter == "A":
                    self.current_disk_type = self.drive_a_disk_type
                else:
                    self.current_disk_type = self.drive_b_disk_type
                self.status_disktype_var.set(f"Disk Type: {self.current_disk_type}")
                self.log(f"Monitor drive switch detected - updated status bar to {drive_letter}:")
            
            # Update status bar and internal mode for mode switch commands
            if stripped.lower() == 'monitor':
                self.current_mode = "Monitor"
                self.status_mode_var.set("Mode: Monitor")
                self.log("Mode switch to Monitor detected")
            elif stripped.lower() == 'x' and self.current_mode == "Monitor":
                self.current_mode = "ArduDOS"
                self.status_mode_var.set("Mode: ArduDOS")
                self.log("Mode switch to ArduDOS detected")
            
            # Update status bar for disk type commands
            disk_type_map = {
                'disktype 0': '5.25" DD', 't 0': '5.25" DD',
                'disktype 1': '5.25" DD in HD', 't 1': '5.25" DD in HD',
                'disktype 2': '5.25" HD', 't 2': '5.25" HD',
                'disktype 3': '3.5" DD', 't 3': '3.5" DD',
                'disktype 4': '3.5" HD', 't 4': '3.5" HD'
            }
            if stripped.lower() in disk_type_map:
                disk_type_name = disk_type_map[stripped.lower()]
                self.current_disk_type = disk_type_name
                # Store disk type for current drive
                if self.current_drive == "A:":
                    self.drive_a_disk_type = disk_type_name
                else:
                    self.drive_b_disk_type = disk_type_name
                self.status_disktype_var.set(f"Disk Type: {disk_type_name}")
                self.log("Disk type command detected - updated status bar to {disk_type_name}")
            
        except Exception as e:
            messagebox.showerror("Send Error", f"Failed to send command: {str(e)}")
    
    def send_cmd_with_delay(self, command, extra_delay=0.0):
        """Send command with minimal additional delay - main waiting happens in send_cmd"""
        self.send_cmd(command)
        if extra_delay > 0:
            time.sleep(extra_delay)
    
    def send_file_content(self, lines, progress_callback=None):
        """Send file content lines with proper timing for write operations"""
        total_lines = len(lines)
        for i, line in enumerate(lines):
            self.send_cmd_with_delay(line, extra_delay=0.2)  # Extra 200ms for file writes
            if progress_callback:
                progress_callback(i + 1, total_lines)
    
    def send_critical_cmd(self, command, wait_for_prompt=True):
        """Send critical disk command and optionally wait for completion"""
        self.send_cmd_with_delay(command, extra_delay=1.0)  # 1 second delay for critical operations
        if wait_for_prompt:
            # Wait up to 5 seconds for the prompt to return
            timeout = 5.0
            start_time = time.time()
            while self.waiting_for_prompt and (time.time() - start_time) < timeout:
                time.sleep(0.1)
                # Process any pending data
                self.root.update()
    
    def block_ui_for_motor(self):
        """Legacy no-op for former motor lockout."""
        self.ui_blocked = False
        self.blocked_buttons = []
    
    def unblock_ui_for_motor(self):
        """Ensure status label reflects current connection without UI lockout."""
        self.ui_blocked = False
        self.blocked_buttons = []
        if self.connected:
            self.status_label.config(text="Connected", foreground="green")
        else:
            self.status_label.config(text="Disconnected", foreground="red")
    
    def delayed_ui_unblock(self):
        """Legacy shim retained for compatibility."""
        self.unblock_ui_for_motor()
            
    def on_mode_change(self, event=None):
        """Handle mode change (deprecated - now handled by tab switching)"""
        pass
    
    def on_tab_change(self, event=None):
        """Handle tab change event with automatic mode switching"""
        if self.switching_modes:  # Prevent recursive calls
            return
            
        selected_tab = self.notebook.select()
        tab_text = self.notebook.tab(selected_tab, "text")
        
        # Update current mode based on selected tab and send appropriate command
        if tab_text == "ArduDOS Commands" and self.current_mode != "ArduDOS":
            self.switching_modes = True
            self.send_cmd("x")  # Exit monitor mode
            self.current_mode = "ArduDOS"
            self.status_mode_var.set("Mode: ArduDOS")
            # Mode switched - user can manually refresh when ready
            self.root.after(1000, lambda: setattr(self, 'switching_modes', False))
        elif tab_text == "Monitor Commands" and self.current_mode != "Monitor":
            self.switching_modes = True
            self.send_cmd("monitor")  # Enter monitor mode
            self.current_mode = "Monitor"
            self.status_mode_var.set("Mode: Monitor")
            self.root.after(1000, lambda: setattr(self, 'switching_modes', False))
            
    # ArduDOS command helpers
    def type_file(self):
        """Type a file"""
        filename = tk.simpledialog.askstring("Type File", "Enter filename:")
        if filename:
            self.send_cmd(f"type {filename}")
            
    def dump_file(self):
        """Dump a file"""
        filename = tk.simpledialog.askstring("Dump File", "Enter filename:")
        if filename:
            self.send_cmd(f"dump {filename}")
            
    def delete_file(self):
        """Delete a file"""
        filename = tk.simpledialog.askstring("Delete File", "Enter filename:")
        if filename:
            if messagebox.askyesno("Confirm Delete", f"Delete file '{filename}'?"):
                self.send_cmd(f"del {filename}")
                
    def make_directory(self):
        """Make a directory"""
        dirname = tk.simpledialog.askstring(
            "Make Directory", 
            "Enter directory name:",
            parent=self.root
        )
        if dirname:
            full_path = self.get_full_file_path(dirname)
            self.send_cmd(f"mkdir {full_path}")
            # Directory created - use Refresh button to see changes
            
    def remove_directory(self):
        """Remove a directory"""
        dirname = tk.simpledialog.askstring(
            "Remove Directory", 
            "Enter directory name:",
            parent=self.root
        )
        if dirname:
            full_path = self.get_full_file_path(dirname)
            if messagebox.askyesno(
                "Confirm Remove", 
                f"Remove directory '{full_path}'?",
                parent=self.root
            ):
                self.send_cmd(f"rmdir {full_path}")
                # Directory removed - use Refresh button to see changes
                
    def format_disk(self):
        """Format disk with disk type confirmation dialog.
        
        The firmware defaults both drives to 3.5" HD on startup.
        If the physical disk is a different type (e.g. 3.5" DD), the
        format will fail with 'Low-level disk error' unless the correct
        disktype is sent first.  This dialog ensures the right type is
        always configured before formatting.
        """
        self._format_disk_with_type_dialog(quick=False)
            
    def quick_format(self):
        """Quick format disk (filesystem only, no low-level format)"""
        self._format_disk_with_type_dialog(quick=True)
    
    def _format_disk_with_type_dialog(self, quick=False):
        """Show format dialog with disk type selection, then format."""
        if not self.connected:
            messagebox.showwarning("Not Connected",
                                  "Please connect to Arduino FDC first",
                                  parent=self.root)
            return
        
        # Build the dialog
        dialog = tk.Toplevel(self.root)
        fmt_label = "Quick Format" if quick else "Format"
        dialog.title(f"{fmt_label} Disk - {self.current_drive}")
        dialog.geometry("380x280")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 200,
            self.root.winfo_rooty() + 200
        ))
        
        # Info
        ttk.Label(dialog, text=f"{fmt_label} disk in drive {self.current_drive}",
                  font=("Arial", 11, "bold")).pack(pady=(15, 5))
        ttk.Label(dialog, text="Select the disk type that matches your physical disk.\n"
                  "Using the wrong type will cause format errors.",
                  wraplength=340, justify=tk.CENTER).pack(pady=(0, 10))
        
        # Disk type radio buttons
        type_frame = ttk.LabelFrame(dialog, text="Disk Type", padding="8")
        type_frame.pack(padx=15, fill=tk.X)
        
        disk_types = [
            ('3.5" HD  (1.44 MB)', "disktype 4", '3.5" HD'),
            ('3.5" DD  (720 KB)',   "disktype 3", '3.5" DD'),
            ('5.25" HD (1.2 MB)',   "disktype 2", '5.25" HD'),
            ('5.25" DD (360 KB)',   "disktype 0", '5.25" DD'),
            ('5.25" DD in HD drive',"disktype 1", '5.25" DD in HD'),
        ]
        
        # Default selection based on current disk type for this drive
        type_var = tk.StringVar()
        current = self.current_disk_type
        default_cmd = "disktype 4"  # fallback to 3.5" HD
        for label, cmd, name in disk_types:
            if name == current:
                default_cmd = cmd
                break
        type_var.set(default_cmd)
        
        for label, cmd, name in disk_types:
            ttk.Radiobutton(type_frame, text=label, variable=type_var,
                            value=cmd).pack(anchor=tk.W)
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(12, 10))
        
        def do_format():
            dialog.destroy()
            # Determine human-readable name from selection
            selected_cmd = type_var.get()
            selected_name = "Unknown"
            for label, cmd, name in disk_types:
                if cmd == selected_cmd:
                    selected_name = name
                    break
            
            # Final confirmation
            action = "Quick format" if quick else "Format"
            if not messagebox.askyesno(
                "Confirm Format",
                f"{action} disk in drive {self.current_drive} as {selected_name}?\n\n"
                "This will ERASE ALL DATA on the disk.",
                parent=self.root
            ):
                return
            
            # 1) Send disktype command and wait for it to take effect
            self.set_disk_type(selected_cmd, selected_name)
            self.log(f"Set disk type to {selected_name} before format")
            
            # 2) Brief pause so firmware processes the disktype command
            time.sleep(0.3)
            self.root.update()
            
            # 3) Send format command (don't wait for prompt - we'll auto-confirm)
            fmt_cmd = "format /q" if quick else "format"
            self.send_cmd(fmt_cmd)
            self.log(f"Sent '{fmt_cmd}' command to firmware")
            
            # 4) Schedule auto-confirm "y" after firmware prompts
            self.root.after(800, self._auto_confirm_format)
        
        ttk.Button(btn_frame, text=f"{fmt_label}", command=do_format,
                   width=14).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                   width=10).pack(side=tk.LEFT, padx=5)
    
    def _auto_confirm_format(self):
        """Auto-send 'y' to confirm the firmware's format prompt."""
        if not self.connected:
            return
        self.log("Auto-sending 'y' to confirm firmware format prompt")
        self.send_cmd("y")
    
    def write_file(self):
        """Write a new file with multi-line input dialog"""
        # Get filename first
        filename = tk.simpledialog.askstring(
            "Write New File", 
            "Enter filename:",
            parent=self.root
        )
        
        if not filename:
            return
            
        # Create multi-line input dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Write File Content")
        dialog.geometry("600x500")  # Larger size to ensure buttons are visible
        dialog.minsize(500, 400)    # Minimum size
        dialog.resizable(True, True)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        # Instructions - make it clearer
        instruction_frame = ttk.Frame(dialog)
        instruction_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(instruction_frame, text=f"Creating file: {filename}", font=("Arial", 10, "bold")).pack()
        ttk.Label(instruction_frame, text="Type your content below, then click 'Save to Arduino FDC' to write the file").pack()
        ttk.Label(instruction_frame, text="(Empty lines are preserved)").pack()
        
        # Text area with scrollbar
        text_frame = ttk.Frame(dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        text_area = tk.Text(text_frame, wrap=tk.WORD, font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_area.yview)
        text_area.configure(yscrollcommand=scrollbar.set)
        
        text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons - make save more prominent
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        def save_file():
            content = text_area.get("1.0", tk.END).rstrip('\n')  # Remove final newline
            full_path = self.get_full_file_path(filename)
            
            if not content.strip():
                messagebox.showwarning("Empty Content", "Please enter some content for the file.", parent=dialog)
                return
            
            # Use timing-controlled approach to prevent disk change detection
            lines = content.split('\n')
            
            # Send write command - proper completion waiting happens in send_cmd
            self.send_cmd(f"write {full_path}")
            self.append_to_terminal(f"Creating file: {full_path}\n")
            
            # Send content with minimal delays - completion waiting handles timing
            total_lines = len(lines)
            for i, line in enumerate(lines):
                self.send_cmd(line)
                if i % 10 == 0:  # Update progress every 10 lines
                    self.append_to_terminal(f"Sending line {i+1}/{total_lines}...\n")
            
            # Send empty line to finish
            self.send_cmd("")
            
            self.append_to_terminal(f"File content sent. Check terminal for confirmation.\n")
            dialog.destroy()
            
        def cancel():
            dialog.destroy()
            
        # Make save button more prominent
        save_btn = ttk.Button(button_frame, text="💾 Save to Arduino FDC", command=save_file)
        save_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=cancel)
        cancel_btn.pack(side=tk.RIGHT)
        
        # Add sample text to help users understand
        sample_text = "# Example file content\n# You can type or paste text here\n# Multiple lines are supported\n\n# Delete this sample text and add your content"
        text_area.insert("1.0", sample_text)
        text_area.selection_range("1.0", "end")  # Select all sample text so user can easily replace it
        
        # Focus on text area
        text_area.focus_set()
    
    def show_file_content_viewer(self):
        """Show file content in a viewer window"""
        if not self.file_content_buffer.strip():
            messagebox.showinfo("No Content", "No file content to display.")
            return
            
        # Create viewer dialog
        viewer = tk.Toplevel(self.root)
        viewer.title(f"File Content - {self.file_content_filename} ({self.file_content_command.upper()})")
        viewer.geometry("800x600")
        viewer.minsize(600, 400)
        viewer.resizable(True, True)
        viewer.transient(self.root)
        
        # Center the viewer
        viewer.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 100,
            self.root.winfo_rooty() + 100
        ))
        
        # Main frame
        main_frame = ttk.Frame(viewer)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Info frame
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(info_frame, text=f"File: {self.file_content_filename}", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Command: {self.file_content_command.upper()}", font=("Arial", 9)).pack(anchor=tk.W)
        
        # Clean up the content - remove the command echo and prompt
        content = self.file_content_buffer
        lines = content.split('\n')
        cleaned_lines = []
        found_content_start = False
        
        for line in lines:
            line_strip = line.strip()
            
            # Skip command echoes and prompts
            if (line_strip.lower().startswith(self.file_content_command.lower()) or
                line_strip.endswith(':>') or
                line_strip.startswith('Command:') or
                line_strip in ['', 'A:>', 'B:>', 'C:>', 'D:>']):
                continue
            
            # Stop at the next prompt (end of file content)
            if ':>' in line_strip and len(line_strip) <= 4:  # Short prompts like "A:>"
                break
                
            # This is actual file content
            found_content_start = True
            cleaned_lines.append(line)
        
        clean_content = '\n'.join(cleaned_lines).strip()
        
        # Text area with scrollbars
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        text_area = tk.Text(text_frame, wrap=tk.NONE, font=("Consolas", 9), 
                           state=tk.NORMAL, bg="white", fg="black")
        
        # Vertical scrollbar
        v_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_area.yview)
        text_area.configure(yscrollcommand=v_scrollbar.set)
        
        # Horizontal scrollbar
        h_scrollbar = ttk.Scrollbar(text_frame, orient="horizontal", command=text_area.xview)
        text_area.configure(xscrollcommand=h_scrollbar.set)
        
        # Pack scrollbars and text area
        text_area.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        
        # Insert content
        text_area.insert("1.0", clean_content)
        text_area.configure(state=tk.DISABLED)  # Make read-only
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        def copy_all():
            viewer.clipboard_clear()
            viewer.clipboard_append(clean_content)
            messagebox.showinfo("Copied", "File content copied to clipboard!", parent=viewer)
        
        def save_to_file():
            file_path = filedialog.asksaveasfilename(
                parent=viewer,
                title="Save File Content",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=self.file_content_filename
            )
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(clean_content)
                    messagebox.showinfo("Saved", f"Content saved to {file_path}", parent=viewer)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save file: {e}", parent=viewer)
        
        # Buttons
        ttk.Button(button_frame, text="📋 Copy All", command=copy_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="💾 Save to PC", command=save_to_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=viewer.destroy).pack(side=tk.RIGHT)
        
        # Status
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        
        line_count = len(clean_content.split('\n'))
        char_count = len(clean_content)
        ttk.Label(status_frame, text=f"Lines: {line_count} | Characters: {char_count}", 
                 font=("Arial", 8)).pack(anchor=tk.W)
    
    def monitor_format(self):
        """Format disk in monitor mode"""
        if messagebox.askyesno("Confirm Format", 
                             "This will perform a low-level format. Continue?"):
            self.send_cmd("f")
    
    def write_all_sectors(self):
        """Write buffer to all sectors"""
        result = messagebox.askyesnocancel("Write All Sectors", 
                                         "Write current buffer to ALL sectors?\n\n" +
                                         "Choose:\n" +
                                         "Yes = Write with verify\n" +
                                         "No = Write without verify\n" +
                                         "Cancel = Abort")
        if result is True:
            self.send_cmd("w 1")  # With verify
        elif result is False:
            self.send_cmd("w 0")  # Without verify

    # File browser methods
    def refresh_file_list(self):
        """Go to root directory and refresh the file list"""
        if not self.connected or self.current_mode != "ArduDOS" or self.waiting_for_dir:
            return
        
        # Reset to root directory 
        self.current_path = ""
        current_drive = self.current_dir_var.get()[:2]  # Get "A:" or "B:"
        self.current_dir_var.set(f"{current_drive}\\")
        
        # Refresh using DIR (no path = root directory)
        self.refresh_current_directory()
    
    def parse_real_dir_output(self):
        """Parse actual DIR command response and populate file list"""
        self.log("Parsing DIR output. Buffer length: {len(self.dir_output_buffer)}")
        self.log(f"DIR buffer content: '{self.dir_output_buffer[:200]}...'")  # First 200 chars
        
        lines = self.dir_output_buffer.split('\n')
        self.log(f"Split into {len(lines)} lines")
        
        # Clear the listbox
        self.file_listbox.delete(0, tk.END)
        self.current_files = []
        
        # Add ".." entry if not in root directory
        if self.current_path:
            self.file_listbox.insert(tk.END, "📁 ..              <DIR>")
            self.current_files.append(("..", "Directory"))
        
        files_found = 0
        dirs_found = 0
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and command echoes
            if not line:
                continue
                
            self.log(f"Processing line: '{line}'")
                
            # Skip command echoes (lines that look like commands)
            if (line.lower().startswith('dir') or 
                line.endswith(':>') or 
                line.startswith('Command:') or
                line.lower().startswith('a:>') or 
                line.lower().startswith('b:>') or
                'bytes free' in line.lower() or
                'directory of' in line.lower()):
                self.log(f"Skipping command echo: '{line}'")
                continue
                
            # Simple directory detection - look for <DIR> anywhere in the line
            if '<DIR>' in line.upper():
                # Extract directory name - it's the part before <DIR>
                # Format appears to be: "DIRNAME      <DIR>"
                dir_part = line.upper().split('<DIR>')[0].strip()
                if dir_part and dir_part not in ['.', '..'] and not dir_part.startswith('>'):
                    display_entry = f"📁 {dir_part:<15} <DIR>"
                    self.file_listbox.insert(tk.END, display_entry)
                    self.current_files.append((dir_part, "Directory"))
                    dirs_found += 1
                    self.log(f"Found directory: '{dir_part}'")
            
            # Simple file detection - look for lines that don't contain <DIR> but have content
            elif len(line) > 5 and not any(skip in line.lower() for skip in 
                    ['bytes free', 'command:', 'directory of', ':>', 'a:>', 'b:>', '>']):
                # Arduino FDC file format: "FILENAME EXT  SIZE"
                parts = line.split()
                if len(parts) >= 3 and parts[-1].isdigit():  # Last part should be file size
                    filename = parts[0].strip()
                    extension = parts[1].strip()
                    size = parts[-1]
                    
                    # Reconstruct full filename with extension
                    full_filename = f"{filename}.{extension}"
                    
                    display_entry = f"📄 {full_filename:<15} {size:>8}"
                    self.file_listbox.insert(tk.END, display_entry)
                    self.current_files.append((full_filename, "File"))
                    files_found += 1
                    self.log(f"Found file: '{full_filename}' size: {size}")
        
        self.log(f"Final result: {dirs_found} directories, {files_found} files")
        
        # If no files found, show message
        if len(self.current_files) == 0:
            self.file_listbox.insert(tk.END, "< No files or directories found >")
            self.log("No files or directories found")
    
    def parse_dir_response(self):
        """Legacy method - now replaced by parse_real_dir_output"""
        # This method is no longer used but kept for compatibility
        pass
    
    def on_file_double_click(self, event):
        """Handle double-click on file/directory in list"""
        selection = self.file_listbox.curselection()
        if not selection:
            return
            
        file_entry = self.file_listbox.get(selection[0])
        
        # Handle special cases
        if "< No files found >" in file_entry or "< No files or directories found >" in file_entry:
            return
        
        if "<DIR>" in file_entry:
            # Directory navigation
            # Extract directory name (remove emoji and spaces)
            self.log(f"Double-clicked directory entry: '{file_entry}'")
            parts = file_entry.split()
            self.log("Split parts: {parts}")
            if len(parts) >= 2:
                dirname = parts[1]  # Skip emoji, get directory name
                self.log(f"Extracted dirname: '{dirname}'")
                
                if dirname == "..":
                    # Go up one directory
                    self.log("Calling navigate_up()")
                    self.navigate_up()
                else:
                    # Enter directory
                    self.log(f"Calling navigate_to_directory('{dirname}')")
                    self.navigate_to_directory(dirname)
        else:
            # File - show TYPE command
            parts = file_entry.split()
            if len(parts) >= 2:
                filename = parts[1]  # Skip emoji, get filename
                self.type_selected_file_by_name(filename)
                
    def navigate_to_directory(self, dirname):
        """Navigate into a directory"""
        if not self.connected or self.current_mode != "ArduDOS" or self.waiting_for_dir:
            return
            
        # Safety check: if somehow ".." gets here, call navigate_up instead
        if dirname == "..":
            self.navigate_up()
            return
            
        # Update path tracking
        if self.current_path:
            self.current_path += "\\" + dirname
        else:
            self.current_path = dirname
            
        # Update display
        current_drive = self.current_dir_var.get()[:2]  # Get "A:" or "B:"
        self.current_dir_var.set(f"{current_drive}\\{self.current_path}")
        
        # Use DIR command with path instead of CD
        self.refresh_current_directory()
        
    def navigate_up(self):
        """Navigate up one directory level"""
        if not self.connected or self.current_mode != "ArduDOS" or self.waiting_for_dir:
            return
            
        # Update path tracking - properly handle parent directory
        if self.current_path:
            path_parts = self.current_path.split("\\")
            # Remove empty parts that might result from split
            path_parts = [part for part in path_parts if part]
            
            if len(path_parts) > 1:
                # Go up one level: ORG\SUBDIR -> ORG
                self.current_path = "\\".join(path_parts[:-1])
            elif len(path_parts) == 1:
                # Go to root: ORG -> root
                self.current_path = ""
            else:
                # Already at root
                self.current_path = ""
        else:
            # Already at root, can't go up further
            return
        
        # Update display
        current_drive = self.current_dir_var.get()[:2]  # Get "A:" or "B:"
        if self.current_path:
            self.current_dir_var.set(f"{current_drive}\\{self.current_path}")
        else:
            self.current_dir_var.set(f"{current_drive}\\")
        
        # Use DIR command with calculated parent path
        self.refresh_current_directory()
        
    def refresh_current_directory(self):
        """Refresh current directory listing using DIR with path"""
        if not self.connected or self.current_mode != "ArduDOS" or self.waiting_for_dir:
            return
        
        # Clear current list
        self.file_listbox.delete(0, tk.END)
        self.current_files = []
        
        # Send DIR command - completion waiting handles timing
        if self.current_path:
            cmd = f"dir {self.current_path}"
            self.log(f"Sending command: '{cmd}' (current_path='{self.current_path}')")
            self.send_cmd(cmd)
        else:
            self.log("Sending command: 'dir' (root directory)")
            self.send_cmd("dir")
    
    def get_selected_filename(self):
        """Get the currently selected filename"""
        selection = self.file_listbox.curselection()
        if not selection:
            return None
            
        file_entry = self.file_listbox.get(selection[0])
        
        # Handle special cases
        if "< Empty Directory >" in file_entry or "< No files found >" in file_entry:
            return None
            
        # Skip directories for file operations
        if "<DIR>" in file_entry:
            return None
            
        # Extract filename from the formatted display entry
        # New format is "📄 FILENAME    SIZE" or "📁 DIRNAME    <DIR>"
        parts = file_entry.split()
        if len(parts) >= 2:
            # Skip the emoji (first part) and get the filename (second part)
            filename = parts[1]
            return filename
        
        return None
    
    def get_selected_item(self):
        """Get the currently selected item (file or directory) with type"""
        selection = self.file_listbox.curselection()
        if not selection:
            return None, None
            
        file_entry = self.file_listbox.get(selection[0])
        
        # Handle special cases
        if "< Empty Directory >" in file_entry or "< No files found >" in file_entry:
            return None, None
            
        # Extract item name from the formatted display entry
        # Format is "📄 FILENAME    SIZE" or "📁 DIRNAME    <DIR>"
        parts = file_entry.split()
        if len(parts) >= 2:
            # Skip the emoji (first part) and get the item name (second part)
            item_name = parts[1]
            
            # Determine type
            if "<DIR>" in file_entry:
                return item_name, "Directory"
            else:
                return item_name, "File"
        
        return None, None
    
    def on_file_double_click(self, event):
        """Handle double-click on file browser items"""
        item_name, item_type = self.get_selected_item()
        
        if item_name and item_type == "Directory":
            # Check if this is the ".." parent directory entry
            if item_name == "..":
                # Use the navigate_up method instead of building invalid path
                self.navigate_up()
            else:
                # Navigate into directory using path-based DIR command
                self.navigate_to_directory(item_name)
        elif item_name and item_type == "File":
            # Double-click on file - TYPE the file
            self.type_selected_file_by_name(item_name)
    
    def navigate_to_directory(self, dirname):
        """Navigate to a subdirectory using path-based DIR command"""
        if not self.connected or self.current_mode != "ArduDOS":
            return
            
        # Build the new path
        if self.current_path:
            new_path = f"{self.current_path}\\{dirname}"
        else:
            new_path = dirname
            
        # Update the current path
        self.current_path = new_path
        
        # Update the directory display
        current_drive = self.current_dir_var.get()[:2]  # Get "A:" or "B:"
        self.current_dir_var.set(f"{current_drive}\\{self.current_path}")
        
        # Send DIR command - completion waiting handles timing
        self.send_cmd(f"dir {new_path}")
    
    def navigate_up(self):
        """Navigate up one directory level"""
        if not self.current_path:
            return  # Already at root
            
        # Go up one level
        path_parts = self.current_path.split('\\')
        if len(path_parts) > 1:
            self.current_path = '\\'.join(path_parts[:-1])
        else:
            self.current_path = ""
            
        # Update display
        current_drive = self.current_dir_var.get()[:2]  # Get "A:" or "B:"
        if self.current_path:
            self.current_dir_var.set(f"{current_drive}\\{self.current_path}")
        else:
            self.current_dir_var.set(f"{current_drive}\\")
            
        # Send DIR command for parent directory - completion waiting handles timing
        if self.current_path:
            self.send_cmd(f"dir {self.current_path}")
        else:
            self.send_cmd("dir")
    
    def get_selected_dirname(self):
        """Get the currently selected directory name"""
        selection = self.file_listbox.curselection()
        if not selection:
            return None
            
        file_entry = self.file_listbox.get(selection[0])
        
        # Handle special cases
        if "< Empty Directory >" in file_entry or "< No files found >" in file_entry:
            return None
            
        # Only return directories
        if "<DIR>" in file_entry:
            # Extract dirname from the formatted display entry
            # Format is "📁 DIRNAME    <DIR>"
            parts = file_entry.split()
            if len(parts) >= 2:
                # Skip the emoji (first part) and get the dirname (second part)
                dirname = parts[1]
                return dirname
        
        return None
    
    def get_full_file_path(self, filename):
        """Get the full path for a file including current directory"""
        if self.current_path:
            return f"{self.current_path}\\{filename}"
        else:
            return filename
    
    def type_selected_file(self):
        """TYPE the selected file"""
        filename = self.get_selected_filename()
        if filename:
            full_path = self.get_full_file_path(filename)
            
            # Set up file content capture
            self.waiting_for_file_content = True
            self.file_content_buffer = ""
            self.file_content_command = "type"
            self.file_content_filename = full_path
            
            # Send TYPE command - completion waiting handles timing
            self.send_cmd(f"type {full_path}")
        else:
            messagebox.showwarning(
                "No Selection", 
                "Please select a file first",
                parent=self.root
            )
    
    def dump_selected_file(self):
        """DUMP the selected file"""
        filename = self.get_selected_filename()
        if filename:
            full_path = self.get_full_file_path(filename)
            
            # Set up file content capture
            self.waiting_for_file_content = True
            self.file_content_buffer = ""
            self.file_content_command = "dump"
            self.file_content_filename = full_path
            
            # Send DUMP command - completion waiting handles timing
            self.send_cmd(f"dump {full_path}")
        else:
            messagebox.showwarning(
                "No Selection", 
                "Please select a file first",
                parent=self.root
            )
    
    def delete_selected_file(self):
        """DELETE the selected file"""
        filename = self.get_selected_filename()
        if filename:
            full_path = self.get_full_file_path(filename)
            if messagebox.askyesno(
                "Confirm Delete", 
                f"Delete file '{full_path}'?",
                parent=self.root
            ):
                self.send_cmd(f"del {full_path}")
                # File deleted - use Refresh button to see changes
        else:
            messagebox.showwarning(
                "No Selection", 
                "Please select a file first",
                parent=self.root
            )
    
    def type_selected_file_by_name(self, filename):
        """TYPE a file by name"""
        full_path = self.get_full_file_path(filename)
        self.send_cmd(f"type {full_path}")
    
    def switch_drive(self, drive_cmd):
        """Switch drive and refresh file list"""
        self.send_cmd(drive_cmd)
        drive_letter = drive_cmd.upper()[0]
        self.current_drive = f"{drive_letter}:"
        self.current_dir_var.set(f"{drive_letter}:\\")
        self.status_drive_var.set(f"Drive: {drive_letter}:")
        # Restore disk type for the selected drive
        if drive_letter == "A":
            self.current_disk_type = self.drive_a_disk_type
        else:
            self.current_disk_type = self.drive_b_disk_type
        self.status_disktype_var.set(f"Disk Type: {self.current_disk_type}")
        # Drive changed - use Refresh button to see new drive contents
            
    # Monitor command helpers
    def read_sector(self):
        """Read a sector"""
        track = self.track_var.get()
        sector = self.sector_var.get()
        head = self.head_var.get()
        
        if head == "0":
            self.send_cmd(f"r {track},{sector}")
        else:
            self.send_cmd(f"r {track},{sector},{head}")
            
    def write_sector(self):
        """Write a sector"""
        track = self.track_var.get()
        sector = self.sector_var.get()
        head = self.head_var.get()
        
        if messagebox.askyesno("Confirm Write", 
                             f"Write buffer to track {track}, sector {sector}, head {head}?"):
            if head == "0":
                self.send_cmd(f"w {track},{sector}")
            else:
                self.send_cmd(f"w {track},{sector},{head}")
                
    def fill_buffer(self):
        """Fill buffer with a value"""
        value = tk.simpledialog.askstring("Fill Buffer", 
                                        "Enter hex value (e.g., FF) or leave empty for pattern:")
        if value is not None:
            if value.strip():
                try:
                    # Validate hex value
                    int(value, 16)
                    self.send_cmd(f"B {int(value, 16)}")
                except ValueError:
                    messagebox.showerror("Invalid Value", "Please enter a valid hex value")
            else:
                self.send_cmd("B")

    def monitor_receive_disk_image(self):
        """Handle monitor command 'S' to read an entire disk via XModem."""
        if not self.connected or not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("Not Connected", "Please connect to Arduino FDC first")
            return

        if self.current_mode != "Monitor":
            messagebox.showinfo("Monitor Mode", "Enter monitor mode before requesting a disk image.")
            return

        if self.xmodem_operation is not None or self.waiting_for_xmodem_banner or self.xmodem_active:
            messagebox.showinfo("XModem Busy", "An XModem transfer is already running.")
            return

        default_name = time.strftime("arduino_disk_%Y%m%d_%H%M%S.img")
        local_path = filedialog.asksaveasfilename(
            title="Save disk image",
            defaultextension=".img",
            initialfile=default_name,
            filetypes=[("Disk Images", "*.img"), ("Binary Files", "*.bin"), ("All Files", "*.*")],
        )

        if not local_path:
            return

        self.prepare_xmodem_state("Receive image via XModem now...", "monitor-receive-disk")
        self.set_xmodem_controls_state("disabled")
        self.xmodem_total_size = 0
        self.xmodem_status_var.set("Download Disk: Waiting...")
        self.xmodem_progress_var.set("Preparing to receive disk image")
        self.log_to_terminal(
            f"\n🔽 DOWNLOAD DISK IMAGE (Monitor S)\nSaving to: '{os.path.basename(local_path)}'\nWaiting for Arduino...\n"
        )

        # Trigger XModem via standard command path but without waiting for prompt
        self.send_cmd('S', no_wait=True)

        threading.Thread(
            target=self._xmodem_receive_worker,
            args=("disk-image", local_path),
            daemon=True,
        ).start()

    def monitor_send_disk_image(self):
        """Handle monitor command 'R' to write an entire disk via XModem."""
        if not self.connected or not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("Not Connected", "Please connect to Arduino FDC first")
            return

        if self.current_mode != "Monitor":
            messagebox.showinfo("Monitor Mode", "Enter monitor mode before writing a disk image.")
            return

        if self.xmodem_operation is not None or self.waiting_for_xmodem_banner or self.xmodem_active:
            messagebox.showinfo("XModem Busy", "An XModem transfer is already running.")
            return

        file_path = filedialog.askopenfilename(
            title="Select disk image to upload",
            filetypes=[("Disk Images", "*.img"), ("Binary Files", "*.bin"), ("All Files", "*.*")],
        )

        if not file_path:
            return

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            messagebox.showerror("Invalid Image", "Selected disk image is empty.")
            return

        if file_size % 128 != 0:
            proceed = messagebox.askyesno(
                "Size Warning",
                "Disk image size is not a multiple of 128 bytes (XModem block size). Continue anyway?",
            )
            if not proceed:
                return

        verify_choice = messagebox.askyesnocancel(
            "Verify After Write",
            "Verify each sector after writing the disk image?\n\nYes = Write with verify\nNo = Write without verify\nCancel = Abort",
        )

        if verify_choice is None:
            return

        command = "R 1" if verify_choice else "R"

        self.prepare_xmodem_state("Send image via XModem now...", "monitor-send-disk")
        self.set_xmodem_controls_state("disabled")
        self.xmodem_total_size = file_size
        verify_note = "WITH VERIFY" if verify_choice else "without verify"
        self.xmodem_status_var.set(f"Upload Disk: Waiting... ({verify_note})")
        self.xmodem_progress_var.set(f"Image: {os.path.basename(file_path)} ({file_size:,} bytes)")
        self.log_to_terminal(
            f"\n🔼 UPLOAD DISK IMAGE (Monitor R {'1' if verify_choice else ''})\nFile: '{os.path.basename(file_path)}'\nSize: {file_size:,} bytes\nVerify: {verify_note}\nWaiting for Arduino...\n"
        )

        # Trigger XModem via standard command path but without waiting for prompt
        self.send_cmd(command, no_wait=True)

        threading.Thread(
            target=self._xmodem_send_worker,
            args=(file_path, os.path.basename(file_path)),
            daemon=True,
        ).start()

    # XModem helpers
    def schedule_on_main_thread(self, callback, *args, **kwargs):
        self.root.after(0, lambda: callback(*args, **kwargs))

    def log_to_terminal(self, text: str) -> None:
        self.schedule_on_main_thread(self.append_to_terminal, text)

    def set_xmodem_status(self, message: str, progress: Optional[str] = None) -> None:
        self.schedule_on_main_thread(self.xmodem_status_var.set, message)
        if progress is not None:
            self.schedule_on_main_thread(self.xmodem_progress_var.set, progress)

    def set_xmodem_controls_state(self, state: str) -> None:
        def update() -> None:
            button_attrs = (
                "xmodem_send_btn",
                "xmodem_receive_btn",
                "monitor_receive_disk_btn",
                "monitor_send_disk_btn",
            )
            buttons = [getattr(self, attr) for attr in button_attrs if hasattr(self, attr)]
            for btn in buttons:
                btn.config(state=state)

        self.schedule_on_main_thread(update)

    def prepare_xmodem_state(self, banner_hint: str, operation: str) -> None:
        encoded = banner_hint.encode("utf-8", errors="ignore") if isinstance(banner_hint, str) else bytes(banner_hint)
        with self.xmodem_buffer_lock:
            self.waiting_for_xmodem_banner = True
            self.xmodem_banner_text_bytes = encoded
            self.xmodem_banner_buffer = bytearray()
            self.xmodem_prefetched = bytearray()
            self.xmodem_banner_found = False
            # Reset one-time XModem send gating flags
            self._xmodem_first_packet_started = False
        print("DEBUG prepare_xmodem_state", operation, encoded)
        self.xmodem_banner_event.clear()
        self.xmodem_operation = operation
        self.set_xmodem_status("Waiting for Arduino...", "")

    def cleanup_xmodem_state(self) -> None:
        with self.xmodem_buffer_lock:
            self.waiting_for_xmodem_banner = False
            self.xmodem_banner_text_bytes = b""
            self.xmodem_banner_buffer = bytearray()
            self.xmodem_prefetched = bytearray()
            self.xmodem_banner_found = False
            self._xmodem_first_packet_started = False
        self.xmodem_operation = None
        self.xmodem_total_size = 0

    def _xmodem_getc(self, size: int, timeout: Optional[float] = 1.0):
        if not self.serial_port or not self.serial_port.is_open:
            return None

        deadline = time.time() + (timeout if timeout is not None else self.xmodem_packet_timeout)
        while True:
            with self.xmodem_buffer_lock:
                if self.xmodem_prefetched:
                    chunk = self.xmodem_prefetched[:size]
                    del self.xmodem_prefetched[:size]
                    print(f"DEBUG getc(prefetched) -> {chunk!r}")
                    return bytes(chunk)

            data = self.serial_port.read(size)
            if data:
                print(f"DEBUG getc(serial) -> {data!r}")
                return data

            if time.time() >= deadline:
                return None

            time.sleep(0.05)

    def _xmodem_putc(self, data: bytes, timeout: Optional[float] = 1.0):
        if not self.serial_port or not self.serial_port.is_open:
            return None
        # For full-disk writes started by monitor 'R', insert a brief, one-time
        # delay right before the very first packet (SOH) is transmitted. This
        # gives the firmware time to stop emitting the initial 'C' handshake and
        # be ready to ACK block 1, reducing "expected ACK; got 'C'" on block 1.
        try:
            if (
                self.xmodem_operation == "monitor-send-disk"
                and not getattr(self, "_xmodem_first_packet_started", False)
            ):
                # Only gate the first write call made by pyXMODEM during send()
                # (which begins with SOH 0x01). A short pause is sufficient.
                time.sleep(0.06)
                self._xmodem_first_packet_started = True
                print("DEBUG first-packet gate: delayed 60ms before first SOH")
        except Exception:
            pass

        self.serial_port.write(data)
        self.serial_port.flush()  # Ensure data is sent immediately
        return len(data)

    def _xmodem_send_callback(self, total_packets: int, success_count: int, error_count: int) -> None:
        bytes_sent = success_count * 128
        if self.xmodem_total_size:
            pct = min(100, int((bytes_sent / self.xmodem_total_size) * 100))
            if self.xmodem_operation == "monitor-send-disk":
                progress = f"Block {success_count}/{total_packets} • {bytes_sent:,}/{self.xmodem_total_size:,} bytes • {pct}% complete"
                status = f"Upload Disk: {pct}% • Errors: {error_count}"
            else:
                progress = f"{bytes_sent}/{self.xmodem_total_size} bytes ({pct}%)"
                status = "Transferring..."
        else:
            progress = f"{bytes_sent} bytes sent"
            status = "Sending..."
        self.schedule_on_main_thread(self.xmodem_progress_var.set, progress)
        self.schedule_on_main_thread(self.xmodem_status_var.set, status)
        # For full-disk writes (monitor 'R'), give the firmware generous time
        # between blocks to complete disk I/O and verify operations, especially
        # for slower sectors. Block 77+ can be particularly slow.
        if self.xmodem_operation == "monitor-send-disk":
            try:
                # Longer pacing after retries, moderate pacing for clean blocks
                if error_count:
                    time.sleep(0.12)  # 120ms after errors
                else:
                    time.sleep(0.08)  # 80ms normal pacing
            except Exception:
                pass

    def _xmodem_recv_callback(self, total_packets: int, success_count: int, error_count: int, packet_size: int) -> None:
        bytes_received = success_count * packet_size
        if self.xmodem_operation == "monitor-receive-disk":
            progress = f"Block {success_count} • {bytes_received:,} bytes received"
            if error_count:
                progress += f" • Retries: {error_count}"
            status = f"Download Disk: Block {success_count} • Errors: {error_count}"
        else:
            progress = f"{bytes_received} bytes received"
            if error_count:
                progress += f" (retries: {error_count})"
            status = "Receiving..."
        self.schedule_on_main_thread(self.xmodem_progress_var.set, progress)
        self.schedule_on_main_thread(self.xmodem_status_var.set, status)

    def _xmodem_send_worker(self, local_path: str, remote_name: str) -> None:
        with self.xmodem_state_lock:
            try:
                if not self.xmodem_banner_event.wait(self.xmodem_banner_timeout):
                    self.set_xmodem_status("Timeout waiting for Arduino", "")
                    self.log_to_terminal("\nXModem send timed out waiting for Arduino banner.\n")
                    return

                # Stop the receive thread from consuming serial so XModem owns the port
                self.xmodem_active = True
                # Allow a brief start delay for the receiver to settle its handshake
                time.sleep(float(self.xmodem_start_delay))
                # Prune any duplicated initiators accumulated during the delay
                self._prune_prefetched_handshake()
                
                # For monitor-send-disk, actively drain any remaining 'C' bytes that
                # continue arriving while the firmware is still in handshake mode.
                # The working file transfers avoid this by waiting for the prompt,
                # giving the firmware time to stop. Since we use no_wait, we must
                # manually consume the tail end of the 'C' spam before pyXMODEM starts.
                if self.xmodem_operation == "monitor-send-disk":
                    drain_deadline = time.time() + 0.15  # 150ms window to drain residual 'C'
                    drained_count = 0
                    while time.time() < drain_deadline:
                        with self.xmodem_buffer_lock:
                            if self.xmodem_prefetched and self.xmodem_prefetched[0] == 0x43:
                                del self.xmodem_prefetched[0]
                                drained_count += 1
                                continue
                        # Also check serial directly
                        if self.serial_port and self.serial_port.in_waiting:
                            chunk = self.serial_port.read(1)
                            if chunk == b'C':
                                drained_count += 1
                                continue
                            elif chunk:
                                # Not a 'C', put it back in prefetch for XModem
                                with self.xmodem_buffer_lock:
                                    self.xmodem_prefetched.extend(chunk)
                                break
                        time.sleep(0.01)
                    if drained_count:
                        print(f"DEBUG send_worker: drained {drained_count} residual 'C' bytes")
                
                with self.xmodem_buffer_lock:
                    prefetched_len = len(self.xmodem_prefetched)
                print(f"DEBUG send_worker prefetched after drain: {prefetched_len}")

                self.set_xmodem_status("Transferring...", "0%")
                self.xmodem_total_size = os.path.getsize(local_path)

                modem = XMODEM(self._xmodem_getc, self._xmodem_putc)
                with open(local_path, "rb") as stream:
                    success = modem.send(
                        stream,
                        retry=self.xmodem_retry_limit,
                        timeout=self.xmodem_packet_timeout,
                        callback=self._xmodem_send_callback,
                    )

                if success:
                    self.set_xmodem_status("Transfer complete", "Done")
                    self.log_to_terminal("\nXModem send completed successfully.\n")
                    self.schedule_on_main_thread(
                        messagebox.showinfo,
                        "XModem",
                        "File sent successfully.",
                    )
                else:
                    self.set_xmodem_status("Transfer failed", "")
                    self.log_to_terminal("\nXModem send failed.\n")
                    self.schedule_on_main_thread(
                        messagebox.showerror,
                        "XModem",
                        "File transfer failed.",
                    )
            except Exception as exc:
                self.set_xmodem_status("Transfer error", "")
                self.log_to_terminal(f"\nXModem send error: {exc}\n")
                self.schedule_on_main_thread(
                    messagebox.showerror,
                    "XModem",
                    f"Transfer error: {exc}",
                )
            finally:
                self.xmodem_active = False
                self.cleanup_xmodem_state()
                self.set_xmodem_controls_state("normal")

    def _xmodem_receive_worker(self, remote_name: str, local_path: str) -> None:
        with self.xmodem_state_lock:
            try:
                if not self.xmodem_banner_event.wait(self.xmodem_banner_timeout):
                    self.set_xmodem_status("Timeout waiting for Arduino", "")
                    self.log_to_terminal("\nXModem receive timed out waiting for Arduino banner.\n")
                    return

                # Stop the receive thread from consuming serial so XModem owns the port
                self.xmodem_active = True
                # Allow a brief start delay for the sender/receiver to settle
                time.sleep(float(self.xmodem_start_delay))
                # Prune any duplicated initiators accumulated during the delay
                self._prune_prefetched_handshake()
                with self.xmodem_buffer_lock:
                    prefetched_len = len(self.xmodem_prefetched)
                print(f"DEBUG recv_worker prefetched after delay: {prefetched_len}")

                self.set_xmodem_status("Receiving...", "0 bytes")

                modem = XMODEM(self._xmodem_getc, self._xmodem_putc)
                with open(local_path, "wb") as stream:
                    result = modem.recv(
                        stream,
                        retry=self.xmodem_retry_limit,
                        timeout=self.xmodem_packet_timeout,
                        callback=self._xmodem_recv_callback,
                    )

                if result is not None:
                    trimmed = self._trim_xmodem_padding(local_path)
                    if trimmed:
                        self.log_to_terminal(
                            f"\nRemoved {trimmed} bytes of XModem padding from '{os.path.basename(local_path)}'.\n"
                        )
                    final_size = result - trimmed if trimmed and result else result
                    self.set_xmodem_status("Transfer complete", f"{final_size} bytes")
                    self.log_to_terminal("\nXModem receive completed successfully.\n")
                    self.schedule_on_main_thread(
                        messagebox.showinfo,
                        "XModem",
                        f"File received successfully.\nSaved to:\n{local_path}",
                    )
                else:
                    self.set_xmodem_status("Transfer failed", "")
                    self.log_to_terminal("\nXModem receive failed.\n")
                    self.schedule_on_main_thread(
                        messagebox.showerror,
                        "XModem",
                        "File transfer failed.",
                    )
            except Exception as exc:
                self.set_xmodem_status("Transfer error", "")
                self.log_to_terminal(f"\nXModem receive error: {exc}\n")
                self.schedule_on_main_thread(
                    messagebox.showerror,
                    "XModem",
                    f"Transfer error: {exc}",
                )
            finally:
                self.xmodem_active = False
                self.cleanup_xmodem_state()
                self.set_xmodem_controls_state("normal")

    def start_xmodem_send(self, local_path: str, remote_name: str) -> None:
        if not self.connected or not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("Not Connected", "Please connect to Arduino FDC first")
            return

        if self.xmodem_operation is not None or self.waiting_for_xmodem_banner or self.xmodem_active:
            messagebox.showinfo("Busy", "An XModem transfer is already running.")
            return

        remote_name = remote_name.strip()
        if not remote_name:
            messagebox.showerror("Invalid Name", "Please provide a filename for the Arduino side.")
            return

        file_size = os.path.getsize(local_path)
        self.xmodem_total_size = file_size
        self.prepare_xmodem_state("Send file via XModem", "send")
        self.set_xmodem_controls_state("disabled")
        self.log_to_terminal(
            f"\nPreparing to send '{os.path.basename(local_path)}' to Arduino as '{remote_name}'.\n"
        )

        self.send_cmd(f"receive {remote_name} {file_size}")

        threading.Thread(
            target=self._xmodem_send_worker,
            args=(local_path, remote_name),
            daemon=True,
        ).start()

    def start_xmodem_receive(self, remote_name: str, local_path: str) -> None:
        if not self.connected or not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("Not Connected", "Please connect to Arduino FDC first")
            return

        if self.xmodem_operation is not None or self.waiting_for_xmodem_banner or self.xmodem_active:
            messagebox.showinfo("Busy", "An XModem transfer is already running.")
            return

        remote_name = remote_name.strip()
        if not remote_name:
            messagebox.showerror("Invalid Name", "Please provide the filename on the Arduino.")
            return

        self.prepare_xmodem_state("Receive file via XModem", "receive")
        self.set_xmodem_controls_state("disabled")
        self.set_xmodem_status("Waiting for Arduino...", "")
        self.log_to_terminal(
            f"\nPreparing to receive '{remote_name}' from Arduino.\n"
        )

        self.send_cmd(f"send {remote_name}")

        threading.Thread(
            target=self._xmodem_receive_worker,
            args=(remote_name, local_path),
            daemon=True,
        ).start()

    def xmodem_send_dialog(self) -> None:
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to Arduino FDC first")
            return

        file_path = filedialog.askopenfilename(
            title="Select file to send",
            filetypes=[("All files", "*.*")],
        )

        if not file_path:
            return

        default_name = os.path.basename(file_path)
        remote_name = tk.simpledialog.askstring(
            "Arduino Filename",
            "Enter filename to use on Arduino:",
            initialvalue=default_name,
            parent=self.root,
        )

        if remote_name is None:
            return

        self.start_xmodem_send(file_path, remote_name)

    def xmodem_receive_dialog(self) -> None:
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to Arduino FDC first")
            return

        selected_name, selected_type = self.get_selected_item()
        default_remote = ""
        if selected_name and selected_type == "File":
            default_remote = self.get_full_file_path(selected_name)

        remote_name = tk.simpledialog.askstring(
            "Arduino Filename",
            "Enter filename to retrieve from Arduino:",
            initialvalue=default_remote or "",
            parent=self.root,
        )

        if remote_name is None:
            return

        remote_name = remote_name.strip()
        if not remote_name:
            messagebox.showerror("Invalid Name", "Please provide the filename on the Arduino.")
            return

        initialfile = os.path.basename(remote_name) if remote_name else "download.bin"
        local_path = filedialog.asksaveasfilename(
            title="Save received file",
            initialfile=initialfile or "download.bin",
            defaultextension="",
            filetypes=[("All files", "*.*")],
        )

        if not local_path:
            return

        self.start_xmodem_receive(remote_name, local_path)


def main():
    # Import simpledialog after creating root to avoid import errors
    global tk
    import tkinter.simpledialog
    tk.simpledialog = tkinter.simpledialog
    
    root = tk.Tk()
    app = ArduinoFDCGUI(root)
    
    # Handle window closing
    def on_closing():
        if app.connected:
            app.disconnect()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
