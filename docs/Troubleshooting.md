# Troubleshooting Guide

Find solutions to common issues encountered when running Kling UI.

## Application Won't Launch

*   **Python Not Found**: Ensure Python is added to your system PATH.
*   **Missing Dependencies**: Run `python dependency_checker.py` to identify missing packages.
*   **Virtual Environment Issues**: If using the `.bat` file, try deleting the `venv` folder and letting it recreate itself.

## Video Generation Fails

*   **Invalid API Key**: Double-check your fal.ai API key in the configuration.
*   **API Quota/Balance**: Ensure you have enough credits on the fal.ai platform.
*   **Network Issues**: The tool requires an active internet connection to upload images and poll the API.
*   **Image Format**: Ensure your images are in supported formats (JPG, PNG, WebP).
*   **Upload Errors**: The tool uses `freeimage.host`. If this service is down, generation may fail.

## GUI Issues

*   **Drag & Drop Not Working**: Ensure `tkinterdnd2` is correctly installed. On some systems, you may need to install the Tcl/Tk extensions manually.
*   **Window Freezing**: This should not happen due to our threading model, but if it does, check the console for any unhandled exceptions.

## FFmpeg / Looping Issues

*   **"FFmpeg not found"**: You must have FFmpeg installed and in your system PATH for the "Loop Videos" feature to work.
*   **Looped Video is Corrupt**: This can happen if the original video download was interrupted.

## Logs

Check the following files for detailed error information:
*   `kling_automation.log`: Core generation logic logs.
*   `kling_gui.log`: Graphical interface logs.
