# Real-Time Balance Tracking

Kling UI includes a specialized system to monitor your fal.ai credit balance while you work.

## How It Works

Because fal.ai does not provide a balance API for all account types, Kling UI uses **Selenium** to perform automated browser checks:

1.  **Browser Automation**: It launches a headless instance of Chrome using `selenium`.
2.  **Persistent Profile**: It creates a folder called `chrome_profile/` to store your login cookies.
3.  **Manual Login**: On the very first run (or if cookies expire), it will open a visible Chrome window for you to log in to fal.ai.
4.  **Headless Monitoring**: Once logged in, it switches to headless mode (invisible) and refreshes the balance page every 30 seconds.

## Components

*   **`selenium_balance_checker.py`**: The low-level logic that interacts with the browser and extracts the balance text from the HTML.
*   **`balance_tracker.py`**: A high-level thread manager that runs the checker in the background and provides callbacks to the UI.

## Troubleshooting Balance Tracking

*   **Slow Updates**: The checker waits 30 seconds between refreshes to avoid being flagged by anti-bot systems.
*   **Login Required**: If you see "Auth Required" or your balance stays at $0.00 unexpectedly, run `selenium_balance_checker.py` directly to see the browser window and log in manually.
*   **Dependencies**: Ensure Google Chrome is installed and `webdriver-manager` is working correctly.
*   **Disabling**: You can disable balance tracking in the configuration if you prefer not to use it or if you encounter issues.
