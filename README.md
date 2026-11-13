# HoloHuman3D

### Gesture-Controlled 3D Human Anatomy Exploration

HoloHuman3D is an experimental Python desktop application that combines computer vision, real-time hand tracking, gesture recognition, and interactive 3D human anatomy visualization.

The project aims to make human anatomy exploration more intuitive through natural hand movements rather than conventional mouse-based interaction.

## Features

- Real-time hand tracking using MediaPipe.
- Camera input and image processing using OpenCV.
- Gesture-based interaction and navigation.
- Two-hand interaction experiments.
- Interactive 3D anatomy integration.
- Python desktop interface powered by PySide6.
- Embedded web-based anatomy visualization using Qt WebEngine.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application |
| OpenCV | Camera processing |
| MediaPipe | Hand tracking |
| PySide6 | Desktop interface |
| Qt WebEngine | 3D web integration |
| JavaScript | Anatomy interaction |

## Project Structure

```text
HoloHuman3D/
├── anatomy/
├── assets/
├── companion/
├── docs/
├── interface/
├── modules/
├── shared/
├── tracking/
├── web/
├── main.py
├── requirements.txt
└── README.md
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/vernayamgupta3-creator/HoloHuman3D.git
cd HoloHuman3D
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the environment

Windows:

```powershell
.venv\Scripts\activate
```

### 4. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 5. Run the application

```bash
python main.py
```

## Requirements

- Python 3.12
- Webcam
- Windows desktop environment (current development environment)
- Internet connection may be required for certain external anatomy resources.

## Project Status

**Version:** 0.1.0
**Status:** Experimental — Early Development

This project is actively being developed. Features, interaction methods, and anatomy visualization are subject to change.

## Author

**Vernayam Gupta**

B.Tech Computer Science and Engineering
Artificial Intelligence and Data Science

## Disclaimer

HoloHuman3D is an educational and experimental project. It is not intended for clinical diagnosis or medical decision-making.
