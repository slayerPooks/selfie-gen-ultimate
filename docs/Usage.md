# Usage Guide

Kling UI offers two primary ways to interact with the video generation engine.

## CLI Mode

Launch the terminal interface:
```bash
python kling_automation_ui.py
```

### CLI Menu Options
1.  **Set API Key**: Enter your fal.ai API key.
2.  **Set Output Folder**: Choose where your generated videos will be saved.
3.  **Process Single File**: Pick one image to convert.
4.  **Process Folder**: Batch process all images in a directory.
5.  **View/Edit Configuration**: Adjust model settings and prompts.
6.  **Launch GUI**: Switches to the graphical interface.
7.  **Check Dependencies**: Runs the environment diagnostic tool.

## GUI Mode

Launch the graphical interface directly:
```bash
python -c "from kling_gui import KlingGUIWindow; KlingGUIWindow().run()"
```
*Note: You can also launch this from Option 6 in the CLI menu.*

### Using the GUI
*   **Drag and Drop**: Simply drag image files (JPG, PNG, WebP) into the central "Drop Zone."
*   **Click-to-Browse**: Click anywhere in the Drop Zone to open a standard file explorer.
*   **Queue Management**: The right panel shows the status of current and pending tasks.
*   **Config Panel**: Adjust models, durations, and prompts on the left.
*   **Verbose Log**: Enable "Verbose GUI Mode" to see detailed polling and upload logs in the bottom panel.

## Common Workflows

### Batch Processing
1.  Place your source images in a folder.
2.  Open Kling UI (CLI or GUI).
3.  Select the folder (CLI) or drag the files (GUI).
4.  Wait for the progress bars to complete.
5.  Generated videos will appear in your specified output folder.

### Loop Effect
If "Loop Videos" is enabled in your configuration, the tool will automatically use FFmpeg to create a "ping-pong" effect, making the video loop seamlessly by playing it forward and then backward.
