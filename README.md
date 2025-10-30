# Auto Game Rec&Cut

*This README is available in English and German. Scroll down for the German version.*

---------------------------------------- English Version ----------------------------------------------------


Analyzes frames from various video inputs and triggers recording via OBS Studio.  
After recording ends, the video is optionally analyzed for kills and automatically trimmed.  
German Demo video: https://www.youtube.com/watch?v=4eHSZeGT5_I

# Motivation
I started experimenting with YOLOv8 and wanted to build my first real-time application:
- Learn Python and improve my programming skills
- Create short-form videos for YouTube

# Technology Stack

## Core Technologies
-  Python 3.9       	– for PyTorch  
-  PySide6 / PyQt       – GUI development  
-  Asyncio / Threading  – asynchronous processing and parallelization  
-  FFmpeg       	– frame input via named pipe, followed by tensorization for AI models  

## Analysis & AI
-  EasyOCR  – text recognition in game frames (killfeed, match start/end)  
-  OpenCV   – image processing (matching, frame cropping, contrast analysis, ROI extraction)  
-  PyTorch  – deep learning framework for model development  
-  YOLOv8   – object detection (in progress); see `VideoAnalyzer_yoloV8.py` → pre-training 
                                                
## Architecture & Structure
  ### Custom MVC (split)
  -  Model:  loops, analyzers, capture implementations (logic & data flow).  
  -  Controller (split): 
    -  ModelController:  orchestrates model events and manages loops/jobs.
    -  GuiController:  UI adapter, reads Model→GUI events and sends GUI→Model commands.
  -  View:  `GuiView` – pure presentation layer.
   
  ### Observer Pattern (Event Queues)
  Model ↔ GUI communication is handled via standardized event queues:
  - `model_to_gui_queue` for Model→GUI events.
  - `gui_to_model_queue` for GUI→Model commands.
  Loops are decoupled from the GUI and only write events to the queue; the GUI reads them and stays in the main thread.
  
  ### Factory Pattern (Frame Capture) 
  At runtime or startup, different frame capture instances and interfaces are created and distributed via a central factory in        
  the `ModelController`. (OBS Studio, File; WinAPI capture is planned.)

  ### OBS Control (obs-websocket)
  Real-time commands are sent to OBS via WebSocket (including authentication), and the recording path is returned. The connection uses the obs-websocket protocol (v5).

# Tools & Environment
-  Visual Studio 2022  – temporary IDE  
-  OBS Studio installation  – recording software (once WinAPI capture is implemented, `OBS-Portable.exe` will be sufficient → no installation required)  
- `ffmpeg-7.1.1-full_build` and `OBS Studio` must be located directly inside the project folder.  

---

# Work in Progress / Todo
- WinAPI Capture (Window Capture)
- Measure and display reaction time for game kills via YOLOv8
- Optimize Framecature-loop (faster)
- Implement analysis FPS for skipped frames → measure analysis duration
- Unit and integration tests
- Improve logging in `GuiView`
- Refactor controllers
- Create `requirements.txt`
- Stops the computer from going into sleep mode


---------------------------------------- Deutsche Version ----------------------------------------------------


Analysiert Frames aus verschiedenen Video-Inputs und startet eine Aufnahme ueber OBS Studio. Nach Beendigung der Aufnahme wird das Video optional nach Kills analysiert und automatisch geschnitten.

Demo-Video:  https://www.youtube.com/watch?v=4eHSZeGT5_I

# Motivation
Ich habe mit YOLOv8 experimentiert und wollte damit meine erste Echtzeit Anwendung entwickeln:
- Python lernen und Programmierkenntnisse verbessern
- Kurzvideos fuer YouTube

# Technologie-Stack

## Kerntechnologien
-  Python 3.9  		– fuer Pytorch  
-  PySide6 / PyQt   	– GUI-Entwicklung  
-  Asyncio / Threading  – asynchrone Verarbeitung und Parallelisierung  
-  FFmpeg  		– Frame-Eingang ueber Named Pipe, anschließend Tensorisierung fuer KI-Modelle  

## Analyse & KI
-  EasyOCR  – Texterkennung in Spiel-Frames (Killfeed, Spielmatch-Start und Ende)  
-  OpenCV   – Bildverarbeitung (Abgleich, Frame Cropping, Kontrastanalyse, ROI-Extraktion)  
-  PyTorch  – Deep-Learning-Framework fuer Modellerstellung 
-  YOLOv8   – Objekterkennung, noch in Arbeit; VideoAnalyzer_yoloV8.py -> Pre-Training 
												
## Architektur & Struktur
### Custom MVC (zweigeteilt)
-  Model:  Loops, Analyzer, Capture-Implementierungen (Logik & Datenfluss).  
-  Controller (zweigeteilt): 
  -  ModelController:  Orchestrierung, verarbeitet Model-Events und steuert Loops/Jobs.
  -  GuiController:  UI-Adapter, liest Model→GUI-Events und sendet GUI→Model-Commands.
-  View:  `GuiView` – reine Darstellung.
 
### Observer-Pattern (Event-Queues)
Kommunikation Model ↔ GUI laeuft ueber standardisierte Events/Queues:
- `model_to_gui_queue` fuer Model→GUI (Events).
- `gui_to_model_queue` fuer GUI→Model (Commands).
Loops sind von der GUI entkoppelt und schreiben nur Events in die Queue; die GUI liest sie und bleibt im Mainthread.

### Factory-Pattern (Frame Capture) 
Zur Laufzeit bzw. Start werden unterschiedliche Frame-Capture-Instanzen und Interfaces im ModelController
ueber eine zentrale Factory erstellt und verteilt. (OBS-Studio, File, das WinAPI-Capture ist in Planung).

### OBS-Steuerung (obs-websocket)
Per WebSocket (inkl. Authentifizierung) werden Echtzeit-Kommandos an OBS gesendet und z. B. der Speicherort des 	aufgenommenen Videos zurückgegeben. Die Verbindung läuft über das obs-websocket-Protokoll (v5) 

# Tools & Umgebung
-  Visual Studio 2022  – IDE (temporaer)  
-  OBS Studio Installation  – Aufnahme-Software (Wenn WinAPI-Capture implementiert ist, wird OBS-Portable.exe ausreichen -> ohne Installation)  
- `ffmpeg-7.1.1-full_build` und `OBS Studio exe` müssen sich direkt im Projektordner befinden.  

---

# Work in Progress / Todo
- WinAPI-Capture(Window Capture)
- Messung und Ausgabe der Reaktionszeit bei Game-Kills via YOLOv8
- Framecature-loop optimieren (schneller)
- analyse-Fps fuer Frames uebersprung implementieren -> Dauer der Analyse
- Unit-Tests und Integrations-Tests
- Log in der `GuiView` verbessern
- Refactor der Controller
- `requirements.txt` erstellen

- schlafmodus verhindern!

