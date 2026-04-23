# Installation & Setup

Setting up Kling UI is straightforward. It requires Python 3.8+ and several dependencies for its GUI and automation features.

## Prerequisites

*   **Python**: Version 3.8 or higher.
*   **Pip**: Python package manager.
*   **FFmpeg**: Required for the video looping (ping-pong) feature.
*   **Google Chrome**: Required if using the Balance Tracking feature.

## Standard Installation

1.  **Extract the Files**: Place the project files in a dedicated folder (e.g., `F:\kling_ui`).
2.  **Install Dependencies**: Run the following command in your terminal:
    ```bash
    pip install requests pillow rich selenium webdriver-manager tkinterdnd2
    ```

## Automated Setup (Windows)

For Windows users, a convenience batch file is provided:
*   Run `run_kling_ui.bat`. 
*   On the first run, it will automatically create a virtual environment (`venv`), install all required dependencies, and launch the application.

## Distribution Version

The `distribution/` folder contains a self-contained version of the application:
1.  Navigate to the `distribution` directory.
2.  Run `run_kling_ui.bat`.
3.  This version handles all environment setup automatically, making it ideal for non-technical users.

## Dependency Verification

You can verify that your environment is correctly set up by running:
```bash
python dependency_checker.py
```
This script will check for missing Python packages and external tools like FFmpeg.
