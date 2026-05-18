import os
import sys
import shutil
import time
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QTextEdit, QLabel,
    QTabWidget, QSplitter, QLineEdit, QStatusBar, QFrame, QStyle
)
from PySide6.QtCore import QProcess, Qt, QSize, QTimer, QFileSystemWatcher
from PySide6.QtGui import QFont, QIcon, QKeySequence, QShortcut, QTextCursor, QColor

class CoderunApp(QMainWindow):
    def __init__(self, target_dir=None):
        super().__init__()
        
        # Use target directory if provided, otherwise default to current working directory
        self.target_dir = os.path.abspath(target_dir) if target_dir else os.getcwd()
        
        # Application State
        self.selected_file = None
        self.process = None
        self.compile_start_time = 0
        self.compile_time = 0
        self.run_start_time = 0
        self.run_time = 0
        self.is_compiling = False
        self.is_running_program = False
        
        # Compiler Availability
        self.gcc_version = self.get_compiler_version("gcc")
        self.gpp_version = self.get_compiler_version("g++")
        
        # UI Setup
        self.init_ui()
        self.refresh_files()
        self.update_status("Ready")
        self.write_system_log(f"Successfully loaded workspace folder: {self.target_dir}", success=True)
        
        # File system watcher for instant real-time auto-refresh!
        self.watcher = QFileSystemWatcher(self)
        if os.path.exists(self.target_dir):
            self.watcher.addPath(self.target_dir)
            self.watcher.directoryChanged.connect(self.refresh_files)

    def get_compiler_version(self, compiler):
        """Checks if a compiler is available in the system PATH and returns its version."""
        if not shutil.which(compiler):
            return None
        try:
            # Run compiler --version
            result = subprocess.run([compiler, "--version"], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            first_line = result.stdout.split('\n')[0]
            # Extract version from first line e.g., 'gcc (MinGW-W64 x86_64-posix-seh...) 11.2.0'
            return first_line
        except Exception:
            return "Found (Unknown Version)"

    def init_ui(self):
        self.setWindowTitle("coderun - Local C/C++ Runner")
        self.resize(1000, 650)
        self.setMinimumSize(800, 500)
        
        # Main Widget & Layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        self.setCentralWidget(main_widget)
        
        # --- Top Banner: Folder display and controls ---
        header_widget = QFrame()
        header_widget.setObjectName("headerWidget")
        header_widget.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(12, 8, 12, 8)
        
        folder_icon = QLabel("📁")
        folder_icon.setStyleSheet("font-size: 18px;")
        header_layout.addWidget(folder_icon)
        
        dir_info_layout = QVBoxLayout()
        dir_title = QLabel("CURRENT WORKING DIRECTORY")
        dir_title.setStyleSheet("color: #858585; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        self.dir_path_lbl = QLabel(self.target_dir)
        self.dir_path_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        dir_info_layout.addWidget(dir_title)
        dir_info_layout.addWidget(self.dir_path_lbl)
        header_layout.addLayout(dir_info_layout)
        header_layout.addStretch()
        
        # Top Header Actions
        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.open_folder_btn.clicked.connect(self.select_folder)
        header_layout.addWidget(self.open_folder_btn)
        
        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_btn.clicked.connect(self.refresh_files)
        header_layout.addWidget(self.refresh_btn)
        
        main_layout.addWidget(header_widget)
        
        # --- Missing Compiler Warning ---
        if not self.gcc_version and not self.gpp_version:
            self.warning_banner = QFrame()
            self.warning_banner.setStyleSheet("background-color: #5a1d1d; border: 1px solid #be2e13; border-radius: 4px;")
            warn_layout = QHBoxLayout(self.warning_banner)
            warn_layout.setContentsMargins(12, 6, 12, 6)
            warn_lbl = QLabel("⚠️ NO COMPILER DETECTED: 'gcc' and 'g++' were not found in your PATH. Please install MinGW-w64 or another compiler to run files.")
            warn_lbl.setStyleSheet("color: #ffcccc; font-weight: bold;")
            warn_layout.addWidget(warn_lbl)
            main_layout.addWidget(self.warning_banner)
        else:
            self.warning_banner = None
            
        # --- Splitter (Left: File List Tab, Right: Console & Action Bar) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #2d2d2d; width: 4px; }")
        
        # -- Left Sidebar Widget --
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        left_layout.setSpacing(6)
        
        # File Search Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter files...")
        self.search_input.textChanged.connect(self.filter_files)
        left_layout.addWidget(self.search_input)
        
        # Tab Widget for C vs C++ files
        self.tab_widget = QTabWidget()
        
        # C Files Tab
        self.c_list = QListWidget()
        self.c_list.itemClicked.connect(self.on_file_selected)
        self.tab_widget.addTab(self.c_list, "C Files (.c)")
        
        # C++ Files Tab
        self.cpp_list = QListWidget()
        self.cpp_list.itemClicked.connect(self.on_file_selected)
        self.tab_widget.addTab(self.cpp_list, "C++ Files (.cpp)")
        
        left_layout.addWidget(self.tab_widget)
        splitter.addWidget(left_widget)
        
        # -- Right Main Console Widget --
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        right_layout.setSpacing(8)
        
        # File Action Panel
        actions_frame = QFrame()
        actions_frame.setObjectName("actionsFrame")
        actions_frame.setFrameShape(QFrame.Shape.StyledPanel)
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(10, 8, 10, 8)
        actions_layout.setSpacing(10)
        
        self.active_file_lbl = QLabel("No File Selected")
        self.active_file_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #569cd6;")
        actions_layout.addWidget(self.active_file_lbl)
        actions_layout.addStretch()
        
        # Performance Timing Labels
        self.time_lbl = QLabel("Compile: --s  |  Run: --s")
        self.time_lbl.setStyleSheet("color: #858585; font-family: 'Consolas'; font-size: 11px;")
        actions_layout.addWidget(self.time_lbl)
        
        # Run / Stop / Clear buttons
        self.run_btn = QPushButton("RUN FILE")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.setEnabled(False)
        self.run_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.run_btn.clicked.connect(self.run_selected_file)
        actions_layout.addWidget(self.run_btn)
        
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_btn.clicked.connect(self.terminate_process)
        actions_layout.addWidget(self.stop_btn)
        
        self.clear_btn = QPushButton("Clear Console")
        self.clear_btn.clicked.connect(self.clear_console)
        actions_layout.addWidget(self.clear_btn)
        
        right_layout.addWidget(actions_frame)
        
        # Console output
        self.console = QTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Console output will be displayed here...")
        right_layout.addWidget(self.console)
        
        # Console Interactive Stdin Input Bar
        input_layout = QHBoxLayout()
        input_lbl = QLabel("Standard Input:")
        input_lbl.setStyleSheet("color: #858585; font-size: 11px;")
        self.stdin_input = QLineEdit()
        self.stdin_input.setPlaceholderText("Enter interactive input for standard input (stdin) here and press Enter...")
        self.stdin_input.setEnabled(False)
        self.stdin_input.returnPressed.connect(self.send_stdin)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self.send_stdin)
        
        input_layout.addWidget(input_lbl)
        input_layout.addWidget(self.stdin_input)
        input_layout.addWidget(self.send_btn)
        right_layout.addLayout(input_layout)
        
        splitter.addWidget(right_widget)
        
        # Set initial splitter widths (30% left, 70% right)
        splitter.setSizes([300, 700])
        main_layout.addWidget(splitter)
        
        # --- Bottom Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Set up keyboard shortcuts
        self.setup_shortcuts()
        
        # Apply premium dark developer stylesheet
        self.apply_theme()
        self.update_compiler_status()

    def setup_shortcuts(self):
        """Sets up hotkeys/shortcuts for fast development workflow."""
        # Ctrl+R or F5 to Run File
        self.shortcut_run = QShortcut(QKeySequence("F5"), self)
        self.shortcut_run.activated.connect(self.run_selected_file)
        self.shortcut_run_ctrl = QShortcut(QKeySequence("Ctrl+R"), self)
        self.shortcut_run_ctrl.activated.connect(self.run_selected_file)
        
        # F6 or Ctrl+Shift+R to Refresh file list
        self.shortcut_refresh = QShortcut(QKeySequence("F6"), self)
        self.shortcut_refresh.activated.connect(self.refresh_files)
        self.shortcut_refresh_ctrl = QShortcut(QKeySequence("Ctrl+Shift+R"), self)
        self.shortcut_refresh_ctrl.activated.connect(self.refresh_files)
        
        # Ctrl+L to Clear Output
        self.shortcut_clear = QShortcut(QKeySequence("Ctrl+L"), self)
        self.shortcut_clear.activated.connect(self.clear_console)
        
        # Esc to stop running process
        self.shortcut_stop = QShortcut(QKeySequence("Escape"), self)
        self.shortcut_stop.activated.connect(self.terminate_process)

    def apply_theme(self):
        """Sets custom stylesheets that evoke premium lightweight IDE feel (e.g., VS Code)."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                color: #d4d4d4;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
                font-size: 13px;
            }
            QFrame#headerWidget {
                background-color: #252526;
                border: 1px solid #2d2d2d;
                border-radius: 6px;
            }
            QFrame#actionsFrame {
                background-color: #252526;
                border: 1px solid #2d2d2d;
                border-radius: 4px;
            }
            QTabWidget::pane {
                border: 1px solid #2d2d2d;
                background-color: #252526;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QTabBar::tab {
                background-color: #1e1e1e;
                color: #969696;
                padding: 8px 16px;
                border: 1px solid #2d2d2d;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #252526;
                color: #ffffff;
                border-bottom: 2px solid #0e78c8;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #2d2d2e;
                color: #ffffff;
            }
            QListWidget {
                background-color: #252526;
                border: none;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 4px;
                margin-bottom: 2px;
                color: #cccccc;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #37373d;
                color: #4ec9b0;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #3c3c3c;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px 10px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #007acc;
                background-color: #2d2d2d;
            }
            QLineEdit:disabled {
                background-color: #1e1e1e;
                color: #5a5a5a;
                border: 1px solid #2d2d2d;
            }
            QPushButton {
                background-color: #3c3c3c;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                color: #e1e1e1;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #252526;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #5a5a5a;
                border: 1px solid #2d2d2d;
            }
            QPushButton#runBtn {
                background-color: #0e639c;
                border: 1px solid #0e639c;
                color: #ffffff;
            }
            QPushButton#runBtn:hover {
                background-color: #1177bb;
            }
            QPushButton#runBtn:pressed {
                background-color: #0c5282;
            }
            QPushButton#stopBtn {
                background-color: #9a2617;
                border: 1px solid #9a2617;
                color: #ffffff;
            }
            QPushButton#stopBtn:hover {
                background-color: #be2e13;
            }
            QPushButton#stopBtn:pressed {
                background-color: #7a1d11;
            }
            QTextEdit#console {
                background-color: #181818;
                border: 1px solid #2d2d2d;
                border-radius: 6px;
                padding: 12px;
                color: #d4d4d4;
            }
            QScrollBar:vertical {
                background: #1e1e1e;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #424242;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4f4f4f;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QStatusBar {
                background-color: #007acc;
                color: #ffffff;
            }
        """)

    def update_compiler_status(self):
        """Displays detected compiler versions on status bar."""
        gcc_status = f"GCC: {self.gcc_version.split(') ')[-1] if self.gcc_version else 'Missing'}"
        gpp_status = f"G++: {self.gpp_version.split(') ')[-1] if self.gpp_version else 'Missing'}"
        
        status_msg = f"🔍  Compiler Status:  {gcc_status}   |   {gpp_status}"
        self.status_bar.showMessage(status_msg)

    def refresh_files(self):
        """Scans working directory and populates file lists."""
        self.c_list.clear()
        self.cpp_list.clear()
        
        if not os.path.exists(self.target_dir):
            self.write_system_log(f"Error: Target directory '{self.target_dir}' does not exist.", error=True)
            return

        try:
            files = sorted(os.listdir(self.target_dir))
        except Exception as e:
            self.write_system_log(f"Error listing files: {str(e)}", error=True)
            return

        c_count = 0
        cpp_count = 0

        search_query = self.search_input.text().lower()

        for filename in files:
            # Filter files if there's a search term
            if search_query and search_query not in filename.lower():
                continue
                
            file_path = os.path.join(self.target_dir, filename)
            if os.path.isfile(file_path):
                filename_lower = filename.lower()
                if filename_lower.endswith(".c"):
                    item = QListWidgetItem(f"📄  {filename}")
                    item.setData(Qt.ItemDataRole.UserRole, file_path)
                    self.c_list.addItem(item)
                    c_count += 1
                elif filename_lower.endswith(".cpp") or filename_lower.endswith(".cc") or filename_lower.endswith(".cxx"):
                    item = QListWidgetItem(f"📄  {filename}")
                    item.setData(Qt.ItemDataRole.UserRole, file_path)
                    self.cpp_list.addItem(item)
                    cpp_count += 1

        self.tab_widget.setTabText(0, f"C Files ({c_count})")
        self.tab_widget.setTabText(1, f"C++ Files ({cpp_count})")
        
        # Reset selection if old file is no longer in directory
        if self.selected_file and not os.path.exists(self.selected_file):
            self.selected_file = None
            self.active_file_lbl.setText("No File Selected")
            self.run_btn.setEnabled(False)

    def filter_files(self):
        """Triggered when the search bar value changes."""
        self.refresh_files()

    def select_folder(self):
        """Allows user to dynamically select another working directory."""
        from PySide6.QtWidgets import QFileDialog
        selected = QFileDialog.getExistingDirectory(self, "Select Working Directory", self.target_dir)
        if selected:
            # Update directory
            self.target_dir = os.path.abspath(selected)
            self.dir_path_lbl.setText(self.target_dir)
            
            # Update file system watcher
            if hasattr(self, 'watcher'):
                # Remove old paths
                watched = self.watcher.directories()
                if watched:
                    self.watcher.removePaths(watched)
                # Add new path
                self.watcher.addPath(self.target_dir)
                
            self.refresh_files()
            self.write_system_log(f"Switched workspace directory to: {self.target_dir}", success=True)
            self.update_status("Ready")

    def on_file_selected(self, item):
        """Fires when a user single-clicks a file."""
        self.selected_file = item.data(Qt.ItemDataRole.UserRole)
        filename = os.path.basename(self.selected_file)
        self.active_file_lbl.setText(f"Selected: {filename}")
        
        # Check compiler availability for selected file
        has_compiler = False
        filename_lower = filename.lower()
        if filename_lower.endswith(".c") and self.gcc_version:
            has_compiler = True
        elif (filename_lower.endswith(".cpp") or filename_lower.endswith(".cc") or filename_lower.endswith(".cxx")) and self.gpp_version:
            has_compiler = True
            
        if has_compiler and not self.is_compiling and not self.is_running_program:
            self.run_btn.setEnabled(True)
        else:
            self.run_btn.setEnabled(False)

    def write_system_log(self, text, error=False, success=False):
        """Writes stylized system messages directly to output console."""
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        color_hex = "#a1260d" if error else ("#33a06f" if success else "#007acc")
        self.console.insertHtml(f"<div style='color: {color_hex}; font-family: Consolas; font-weight: bold;'>[System] {text}</div><br>")
        self.console.ensureCursorVisible()

    def clear_console(self):
        """Clears console screen."""
        self.console.clear()

    def update_status(self, status, message=None):
        """Updates internal state visual indicators, active buttons, and bottom state bar."""
        if status == "Ready":
            self.status_bar.setStyleSheet("background-color: #007acc; color: #ffffff;")
            self.status_bar.showMessage(f"Ready  |  Connected to: {self.target_dir}")
            self.run_btn.setEnabled(self.selected_file is not None)
            self.stop_btn.setEnabled(False)
            self.stdin_input.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.refresh_btn.setEnabled(True)
            self.search_input.setEnabled(True)
            self.tab_widget.setEnabled(True)
        elif status == "Compiling":
            self.status_bar.setStyleSheet("background-color: #2b5b84; color: #ffffff;")
            self.status_bar.showMessage(f"🔨 Compiling C/C++ source code...")
            self.run_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.stdin_input.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.search_input.setEnabled(False)
            self.tab_widget.setEnabled(False)
        elif status == "Running":
            self.status_bar.setStyleSheet("background-color: #d18d00; color: #000000; font-weight: bold;")
            self.status_bar.showMessage(f"🚀 Executing binary in background...")
            self.run_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.stdin_input.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.stdin_input.setFocus()
            self.refresh_btn.setEnabled(False)
            self.search_input.setEnabled(False)
            self.tab_widget.setEnabled(False)
        elif status == "Success":
            self.status_bar.setStyleSheet("background-color: #33a06f; color: #ffffff;")
            self.status_bar.showMessage(f"✅ Finished Successfully! " + (message if message else ""))
            self.run_btn.setEnabled(self.selected_file is not None)
            self.stop_btn.setEnabled(False)
            self.stdin_input.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.refresh_btn.setEnabled(True)
            self.search_input.setEnabled(True)
            self.tab_widget.setEnabled(True)
        elif status == "Error":
            self.status_bar.setStyleSheet("background-color: #a1260d; color: #ffffff;")
            self.status_bar.showMessage(f"❌ Failed! " + (message if message else ""))
            self.run_btn.setEnabled(self.selected_file is not None)
            self.stop_btn.setEnabled(False)
            self.stdin_input.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.refresh_btn.setEnabled(True)
            self.search_input.setEnabled(True)
            self.tab_widget.setEnabled(True)

    def update_time_display(self):
        """Render updated compilation & execution performance metrics."""
        comp_str = f"Compile: {self.compile_time:.3f}s" if self.compile_time > 0 else "Compile: --s"
        run_str = f"Run: {self.run_time:.3f}s" if self.run_time > 0 else "Run: --s"
        self.time_lbl.setText(f"{comp_str}  |  {run_str}")

    def run_selected_file(self):
        """Triggers full compilation & execution state machine flow."""
        if not self.selected_file or self.is_compiling or self.is_running_program:
            return

        self.clear_console()
        self.compile_time = 0
        self.run_time = 0
        self.update_time_display()
        
        filename = os.path.basename(self.selected_file)
        
        # Set up state
        self.is_compiling = True
        self.update_status("Compiling")
        
        # Build compile arguments
        output_binary = os.path.join(self.target_dir, "output.exe")
        
        # Check if existing output.exe is locked/running and try to delete it
        if os.path.exists(output_binary):
            try:
                os.remove(output_binary)
            except Exception:
                self.write_system_log("Warning: 'output.exe' is currently locked. Trying to kill running instances...", error=True)
                # Terminate any orphaned output.exe using taskkill
                subprocess.run(["taskkill", "/f", "/im", "output.exe"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                time.sleep(0.2)
                try:
                    os.remove(output_binary)
                except Exception as e:
                    self.write_system_log(f"Error: Cannot overwrite target 'output.exe' output file. Is it locked elsewhere? Details: {str(e)}", error=True)
                    self.is_compiling = False
                    self.update_status("Error", "Output binary locked")
                    return

        filename_lower = filename.lower()
        if filename_lower.endswith(".c"):
            compiler = "gcc"
        else:
            compiler = "g++"
            
        compile_cmd = [compiler, filename, "-o", "output.exe"]
        
        self.write_system_log(f"Compiling: {' '.join(compile_cmd)}")
        self.compile_start_time = time.perf_counter()
        
        # Start compiler QProcess
        self.process = QProcess(self)
        self.process.setWorkingDirectory(self.target_dir)
        self.process.readyReadStandardOutput.connect(self.read_compiler_stdout)
        self.process.readyReadStandardError.connect(self.read_compiler_stderr)
        self.process.finished.connect(self.compile_finished)
        
        # Start compile process
        self.process.start(compiler, compile_cmd[1:])

    def read_compiler_stdout(self):
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(data)
        self.console.ensureCursorVisible()

    def read_compiler_stderr(self):
        data = self.process.readAllStandardError().data().decode('utf-8', errors='replace')
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        # Wrap compiler warning/error messages in slightly light red colors
        self.console.insertHtml(f"<span style='color: #f48771; font-family: Consolas;'>{data.replace('\n', '<br>')}</span>")
        self.console.ensureCursorVisible()

    def compile_finished(self, exit_code, exit_status):
        self.compile_time = time.perf_counter() - self.compile_start_time
        self.update_time_display()
        self.is_compiling = False
        
        if exit_code == 0:
            self.write_system_log(f"Compilation finished successfully in {self.compile_time:.3f} seconds.", success=True)
            self.run_compiled_binary()
        else:
            self.write_system_log(f"Compilation failed with exit code {exit_code}.", error=True)
            self.update_status("Error", f"Compiler failed (Code {exit_code})")
            self.process = None

    def run_compiled_binary(self):
        """Starts executing the successfully compiled output binary."""
        self.is_running_program = True
        self.update_status("Running")
        
        output_binary = os.path.join(self.target_dir, "output.exe")
        if not os.path.exists(output_binary):
            self.write_system_log("Error: Compiled output binary could not be found.", error=True)
            self.update_status("Error", "Binary missing")
            return
            
        self.write_system_log("Executing: output.exe")
        self.run_start_time = time.perf_counter()
        
        # Configure process execution
        self.process = QProcess(self)
        self.process.setWorkingDirectory(self.target_dir)
        self.process.readyReadStandardOutput.connect(self.read_program_stdout)
        self.process.readyReadStandardError.connect(self.read_program_stderr)
        self.process.finished.connect(self.program_finished)
        
        # Launch binary
        self.process.start(output_binary, [])

    def read_program_stdout(self):
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(data)
        self.console.ensureCursorVisible()

    def read_program_stderr(self):
        data = self.process.readAllStandardError().data().decode('utf-8', errors='replace')
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        # Highlight running program errors in red
        self.console.insertHtml(f"<span style='color: #e57373; font-family: Consolas;'>{data.replace('\n', '<br>')}</span>")
        self.console.ensureCursorVisible()

    def send_stdin(self):
        """Sends user keyboard inputs typed in the input line directly into the process's standard input stream."""
        if not self.process or not self.is_running_program:
            return
            
        input_text = self.stdin_input.text()
        # Stream standard input text to running binary process
        self.process.write(input_text.encode('utf-8') + b'\n')
        
        # Display typed text on console so the user sees interactive terminal flow
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertHtml(f"<span style='color: #4ec9b0; font-family: Consolas; font-weight: bold;'>{input_text}</span><br>")
        self.console.ensureCursorVisible()
        
        self.stdin_input.clear()

    def program_finished(self, exit_code, exit_status):
        self.run_time = time.perf_counter() - self.run_start_time
        self.update_time_display()
        self.is_running_program = False
        
        if exit_code == 0:
            self.write_system_log(f"Program executed successfully in {self.run_time:.3f} seconds with exit code {exit_code}.", success=True)
            self.update_status("Success", f"Exit code {exit_code}")
        else:
            self.write_system_log(f"Program terminated with exit code {exit_code}.", error=True)
            self.update_status("Error", f"Exit code {exit_code}")
            
        self.process = None

    def terminate_process(self):
        """Forcibly interrupts compiles or active run processes (critical for infinite loops)."""
        if not self.process:
            return
            
        self.write_system_log("Terminating process forcefully...", error=True)
        self.process.kill()
        
        if self.is_compiling:
            self.is_compiling = False
            self.compile_time = time.perf_counter() - self.compile_start_time
            self.update_status("Error", "Compilation interrupted")
        elif self.is_running_program:
            self.is_running_program = False
            self.run_time = time.perf_counter() - self.run_start_time
            self.update_status("Error", "Program interrupted")
            
        self.update_time_display()
        self.process = None

    def closeEvent(self, event):
        """Cleanup running processes upon closing GUI."""
        if self.process:
            self.process.kill()
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    # Check if target directory is passed via terminal argument (jupyter style launcher)
    target_dir = None
    if len(sys.argv) > 1:
        potential_dir = sys.argv[1]
        if os.path.isdir(potential_dir):
            target_dir = potential_dir
            
    window = CoderunApp(target_dir)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
