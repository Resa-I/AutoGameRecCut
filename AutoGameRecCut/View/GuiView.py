import os

from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, 
                               QWidget, QPushButton, QLineEdit, QLabel, QCheckBox,
                              QTextEdit, QFileDialog, QSpinBox, QGroupBox, QGridLayout,
                              QComboBox,QProgressBar)
from PySide6.QtGui import QIcon

from ServiceRessourcen.Resource_path_for_exe import Resource_path

class GuiView(QMainWindow):
    """
    its a Gui
    """
    def __init__(self,gui_settings_saver,input_valid):
        super().__init__()
        self.settings = gui_settings_saver.load()
        self.gui_settings_saver=gui_settings_saver
        
        self.validator = input_valid
        self.gui_controller = None 
        self.setWindowTitle("AutoGameRec&Cut")
                
        icon_path = Resource_path(os.path.join("ressourcen", "Icon", "app_icon.ico"))
        icon = QIcon(icon_path)
        self.setWindowIcon(icon)

        #initial state
        self._setup_ui()
        self._apply_settings() #Load saved input values
        self._setup_initial_state()
        self._connect_signals()
        self.setGeometry(100, 100, 600, 500)

    def set_gui_controller(self, gui_controller):
        self.gui_controller = gui_controller

        #Save input values and shutdown
    def closeEvent(self, event):
        self._collect_settings()
        self.gui_settings_saver.save(self.settings)
        self.gui_controller.on_window_close()
        super().closeEvent(event)

        #Set saved input values in the UI
    def _apply_settings(self):
        self.input_path_edit.setText(self.settings.get("input_path", ""))
        self.output_path_edit.setText(self.settings.get("output_path", ""))
        self.reaction_time_spinbox.setValue(int(self.settings.get("reaction_time", 500)))
        self.kill_rec_threshold_spinbox.setValue(int(self.settings.get("kill_rec_threshold", 3)))
        self.pre_sec_spinbox.setValue(int(self.settings.get("pre_sec", 1)))     
        self.post_sec_spinbox.setValue(int(self.settings.get("post_sec", 1))) 
        self.auto_rec_checkbox.setChecked(bool(self.settings.get("auto_rec", False)))
        self.auto_analysis_checkbox.setChecked(bool(self.settings.get("auto_analyse", False)))
        saved_source = self.settings.get("source", "OBS") 
        source_index = self.source_dropdown.findText(saved_source)
        if source_index >= 0:
            self.source_dropdown.setCurrentIndex(source_index)

        #Collect input values from the UI to save in a Json
    def _collect_settings(self):
        self.settings["input_path"] = self.input_path_edit.text()
        self.settings["output_path"] = self.output_path_edit.text()
        self.settings["reaction_time"] = self.reaction_time_spinbox.value()
        self.settings["kill_rec_threshold"] = self.kill_rec_threshold_spinbox.value()
        self.settings["pre_sec"] = self.pre_sec_spinbox.value()    
        self.settings["post_sec"] = self.post_sec_spinbox.value()   
        self.settings["auto_rec"] = self.auto_rec_checkbox.isChecked()
        self.settings["auto_analyse"] = self.auto_analysis_checkbox.isChecked()
        self.settings["source"] = self.source_dropdown.currentText()

        #Create the entire UI
    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        self._create_recording_controls(main_layout)     
        
        self._create_analysis_settings(main_layout)
        self._create_path_settings(main_layout)
        self._create_gpu_info(main_layout)
        self._create_status_log(main_layout)
    
        #Create recording buttons and Auto Rec checkbox
    def _create_recording_controls(self, parent_layout):
        group = QGroupBox("Control")
        layout = QGridLayout(group)

        self.auto_analysis_checkbox = QCheckBox("Analysis and Cut")
        self.auto_rec_checkbox = QCheckBox("Auto Rec")
        self.start_button = QPushButton("Recording start")
        self.stop_button = QPushButton("Recording stop")   
        self.source_label = QLabel("Capture Source:")
        self.source_dropdown = QComboBox()
        self.source_dropdown.addItems(["OBS", "Windows API"])

        layout.addWidget(self.auto_rec_checkbox, 0, 1)
        layout.addWidget(self.auto_analysis_checkbox, 0, 0)
        layout.addWidget(self.start_button, 0, 2)
        layout.addWidget(self.source_label, 0, 4)
        layout.addWidget(self.source_dropdown, 1, 4)

        layout.addWidget(self.start_button, 1, 0)
        layout.addWidget(self.stop_button, 1, 1)
        
        parent_layout.addWidget(group)

        #Create path input fields with browse buttons
    def _create_path_settings(self, parent_layout):
        group = QGroupBox("Manual Video Analysis")
        layout = QGridLayout(group)
        
        layout.addWidget(QLabel("Input Folder:"), 0, 0)
        self.input_path_edit = QLineEdit()
        layout.addWidget(self.input_path_edit, 0, 1)
        self.input_browse_button = QPushButton("Browse...")
        self.input_browse_button.clicked.connect(self._browse_input_path)
        layout.addWidget(self.input_browse_button, 0, 2)
        
        layout.addWidget(QLabel("Output Folder:"), 1, 0)
        self.output_path_edit = QLineEdit()
        layout.addWidget(self.output_path_edit, 1, 1)
        self.output_browse_button = QPushButton("Browse...")
        self.output_browse_button.clicked.connect(self._browse_output_path)
        layout.addWidget(self.output_browse_button, 1, 2)

        self.analyze_button = QPushButton("Start Video Analysis and Cut")
        layout.addWidget(self.analyze_button)
        layout.addWidget(self.analyze_button)
        parent_layout.addWidget(group)
    
        #Create analysis settings
    def _create_analysis_settings(self, parent_layout):
        group = QGroupBox("Cut Settings")
        layout = QGridLayout(group)
    
        # Kill-threshold
        layout.addWidget(QLabel("Frag Series for Cut:"),0, 0)
        self.kill_rec_threshold_spinbox = QSpinBox()
        self.kill_rec_threshold_spinbox.setRange(1, 5)
        self.kill_rec_threshold_spinbox.setValue(1)
        layout.addWidget(self.kill_rec_threshold_spinbox, 0, 1)

        layout.addWidget(QLabel("Time before Frag:"), 1, 0)
        self.pre_sec_spinbox = QSpinBox()
        self.pre_sec_spinbox.setRange(1, 20)
        self.pre_sec_spinbox.setValue(5)  # Standard 1s
        layout.addWidget(self.pre_sec_spinbox, 1, 1)
        layout.addWidget(QLabel("s"), 1, 2)

        layout.addWidget(QLabel("Time after Frag:"), 2, 0)
        self.post_sec_spinbox = QSpinBox()
        self.post_sec_spinbox.setRange(1, 20)
        self.post_sec_spinbox.setValue(2)  # Standard 1s
        layout.addWidget(self.post_sec_spinbox, 2, 1)
        layout.addWidget(QLabel("s"), 2, 2)
    

        layout.addWidget(QLabel("Reaction-Time:"), 3, 0)
        self.reaction_time_spinbox = QSpinBox()
        self.reaction_time_spinbox.setRange(10, 1000)
        self.reaction_time_spinbox.setValue(500)
        layout.addWidget(self.reaction_time_spinbox, 3, 1)
        layout.addWidget(QLabel("ms"), 3, 2)

        parent_layout.addWidget(group)

    def _create_gpu_info(self, parent_layout):
        group = QGroupBox("Hardware-Info")
        layout = QHBoxLayout(group)
        
        layout.addWidget(QLabel("GPU:"))
        self.gpu_label = QLabel("GPU Detecting...")
        layout.addWidget(self.gpu_label)
        layout.addStretch()
        
        parent_layout.addWidget(group)
    
    def _create_status_log(self, parent_layout):
        group = QGroupBox("Status & Logs")
        layout = QVBoxLayout(group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(1000)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
         # Load progress for killdetectloop
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)   
        self.progress_bar.setValue(0)        
        layout.addWidget(self.progress_bar)

        parent_layout.addWidget(group)
    
        #Connect UI signals to view methods
    def _connect_signals(self):
        self.start_button.clicked.connect(self._on_start_recording)
        self.stop_button.clicked.connect(self._on_stop_recording)
        self.analyze_button.clicked.connect(self._on_start_analysis)
        self.auto_rec_checkbox.toggled.connect(self._on_auto_rec_toggled)
        self.auto_analysis_checkbox.toggled.connect(self._on_auto_analysis_toggled)
        self.source_dropdown.currentTextChanged.connect(self._on_source_changed)
    
    def _setup_initial_state(self):
        self.stop_button.setEnabled(False)
        self.log_message("Application started")
    
        #Select file or folder for video input
    def _browse_input_path(self):
        start_dir = self.input_path_edit.text().strip()
        if not start_dir or not Path(start_dir).exists():
            start_dir = str(Path.home())

        path, _ = QFileDialog.getOpenFileName(
            self,
            "select Video-Input",
            start_dir,
            "All data (*.*)"
        )

        if not path:  # if nothing was selected
            # Fallback: try folder instead of file
            folder = QFileDialog.getExistingDirectory(
                self,
                "Ordner auswaehlen",
                start_dir
            )
            if folder:
                path = folder

        if path:
            self.input_path_edit.setText(path)

        #Select output folder
    def _browse_output_path(self):
        start_dir = self.output_path_edit.text().strip()
        if not start_dir or not Path(start_dir).exists():
            start_dir = str(Path.home())

        folder = QFileDialog.getExistingDirectory(
            self,
            "select Output folder",
            start_dir
        )
        if folder:
            self.output_path_edit.setText(folder)
    
    def _on_start_recording(self):
        data = self._get_form_data()
        is_valid, errors = self.validator.valid(data)
        
        if is_valid:
            if self.gui_controller:
                self.gui_controller.start_recording(data)
        else:
            for error in errors:
                self.log_message(f"Error: {error}")
    
    def _on_stop_recording(self):
        data = self._get_form_data()
        is_valid, errors = self.validator.valid(data)
        
        if is_valid:
            if self.gui_controller:
                self.gui_controller.stop_recording()
        else:
            for error in errors:
                self.log_message(f"Error: {error}")
    
    def _on_start_analysis(self):
        data = self._get_form_data()
        is_valid, msg = self.validator.valid(data)
        
        if is_valid:
            if self.gui_controller:
                self.gui_controller.start_analysis(data)
        else:
            self.log_message(f"Error: Video-Input: {msg}")
    
        #Called when the "Auto Rec" checkbox is switched
    def _on_auto_rec_toggled(self, checked):
        data = self._get_form_data()
        is_valid, msg = self.validator.valid(data)

        if is_valid:
            if self.gui_controller:
                self.gui_controller.set_auto_rec(checked, data)

        #Called when the "auto_analysis" checkbox is switched
    def _on_auto_analysis_toggled(self, checked):
        data = self._get_form_data()
        is_valid, msg = self.validator.valid(data)

        if is_valid:
            self.gui_controller._check_initial_auto_analyse_state()

        #Collect all form data
    def _get_form_data(self):
        """Collect all data"""
        return {
        'input_path': self.input_path_edit.text(),
        'output_path': self.output_path_edit.text(),
        'reaction_time': self.reaction_time_spinbox.value(),
        'kill_rec_threshold': self.kill_rec_threshold_spinbox.value(),
        'pre_sec': self.pre_sec_spinbox.value(),     
        'post_sec': self.post_sec_spinbox.value(),   
        'auto_rec': self.auto_rec_checkbox.isChecked(),
        "auto_analyse": self.auto_analysis_checkbox.isChecked(),
        'source': self.source_dropdown.currentText()
        }
    
    def set_recording_state(self, is_recording):
        self.start_button.setEnabled(not is_recording)
        self.stop_button.setEnabled(is_recording)
    
    def set_gpu_info(self, gpu_text):
        self.gpu_label.setText(gpu_text)
    
    def _on_source_changed(self):
        data = self._get_form_data()
        if self.gui_controller:
            self.gui_controller.set_Source(data)

    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def set_progress_gui(self, value: int):
        if 0 <= value <= 100:
            self.progress_bar.setValue(value)