# Auto Detect Captcha Tool

A powerful automated tool for scanning websites to detect CAPTCHA protections (ReCaptcha, hCaptcha, Turnstile, AWS WAF, etc.) using both DOM analysis and AI Vision (GPT-4o).

This tool uses **Playwright** for browser automation, **Stealth techniques** to bypass WAFs (like Imperva), and **OpenAI GPT-4o** for visual verification.

## Features

*   🕷️ **Smart Crawling**: Automatically scans internal links (Login, Register, Contact pages).
*   🔍 **Multi-Detection**:
    *   **DOM Detector**: Identifies known signatures (iframe, css classes) of major Captcha providers.
    *   **AI Vision (GPT-4o)**: Takes screenshots and uses AI to visually confirm Captchas when DOM analysis is unsure.
*   🛡️ **Anti-Detection**:
    *   Uses **Firefox** browser by default (less detected than Chromium).
    *   Implements **Stealth** scripts to hide automation traces.
    *   Simulates **Human Behavior** (random mouse movements, scrolling).
*   🍪 **Auto-Consent**: Automatically clicks "Accept Cookies" to reveal page content.
*   📝 **Reporting**: Exports found URLs to `captcha_found.txt`.

## Prerequisites

*   Python 3.8+
*   OpenAI API Key (Optional, for AI Vision features)

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/auto-detect-captcha.git
    cd auto-detect-captcha
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Browsers**:
    ```bash
    playwright install firefox
    # If you want to use Chromium instead, run: playwright install chromium
    ```

## Configuration

1.  **Input URLs**:
    Add the websites you want to scan to `urls.txt` (one URL per line).
    ```text
    https://example.com
    https://test-site.org
    ```

2.  **Environment Variables**:
    Create a `.env` file in the root directory to store your API Key:
    ```env
    OPENAI_API_KEY=sk-your-openai-api-key-here
    ```
    *If you don't provide a key, the tool will run in DOM-only mode (faster but less accurate).*

## Usage

Run the scanner:

```bash
python main.py
```

*   The browser window will open (Headless=False) so you can see the scanning process.
*   Results will be printed to the console.
*   URLs with confirmed Captchas are saved to `captcha_found.txt`.

## Project Structure

*   `main.py`: Main logic for scanning, detection, and AI integration.
*   `stealth.py`: Module for evasive scripts to bypass WAFs.
*   `urls.txt`: List of target websites.
*   `requirements.txt`: Python dependencies.
*   `captcha_found.txt`: Output file containing vulnerable URLs.

## Troubleshooting

*   **Imperva/WAF Blocking**: The tool uses Firefox and random mouse movements to mitigate this. If blocked (Error 15), try using a VPN/Proxy or slowing down the scan.
*   **Browser Closes Too Fast**: Adjust the `timeout` settings in `main.py` if you have a slow connection.

## Disclaimer

This tool is for **Educational and Authorized Pentesting purposes only**. Do not use it on websites you do not have permission to test.

