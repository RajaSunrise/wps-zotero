# WPS-Zotero Plugin

A Zotero plugin for WPS Office, compatible with Windows, Linux, and macOS.

## Features

- Insert and edit citations/bibliographies.
- Compatible with Zotero 6 and Zotero 7.
- Supports Microsoft Word and Google Docs citation style (mostly).
- **Background Service**: The proxy server now runs in the background automatically, making the "one command" setup seamless.

## Installation

### Prerequisites

- **WPS Office**: Latest version recommended.
- **Zotero**: Version 6 or newer (including Zotero 7).
- **Python 3**: Must be installed and available in your system PATH.

### Windows

1. Download the repository as a ZIP file and extract it.
2. Double-click `windows安装与卸载.bat`.
3. Select option `1` to install.
4. Restart WPS Office.

The installation will automatically set up a background service so the plugin works immediately every time you open WPS.

### Linux / macOS

1. Open a terminal.
2. Clone this repository or extract the ZIP.
3. Run the install script:
   ```bash
   python3 install.py
   ```
4. Restart WPS Office.

## Usage

After installation, you should see a "Zotero" tab in the WPS Writer ribbon.

- **Add/Edit Citation**: Insert a new citation or edit an existing one.
- **Add/Edit Bibliography**: Insert the bibliography at the cursor location.
- **Refresh**: Update citations and bibliography.
- **Preferences**: Change document preferences (citation style).
- **Unlink Citations**: Remove field codes (make plain text).

## Troubleshooting

- **No Zotero tab?**
  - Ensure Python 3 is installed.
  - Check if the plugin is installed in the correct directory (see `install.py` output).
  - For macOS, ensure you have permissions to write to `~/Library/Application Support/Kingsoft/WPS/jsaddons`.

- **Zotero not responding?**
  - Make sure Zotero is running.
  - Check if the proxy server is running (check `~/.wps-zotero-proxy.log` or `%APPDATA%\kingsoft\wps\jsaddons\wps-zotero-proxy.log`).
  - You can try restarting the computer to ensure the background service is running.

## Uninstallation

- **Windows**: Run `windows安装与卸载.bat` and select option `2`.
- **Linux / macOS**: Run `python3 install.py -u`.
