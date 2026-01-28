# WPS-Zotero Plugin

![License](https://img.shields.io/badge/license-GPLv3-blue.svg)
![Version](https://img.shields.io/badge/version-0.1.4-green.svg)

A powerful Zotero integration plugin for WPS Office Writer. Seamlessly cite references and generate bibliographies directly within WPS Office on Windows, Linux, and macOS. Fork From [https://github.com/Tankwyn/WPS-Zotero](https://github.com/Tankwyn/WPS-Zotero).

## 🌟 Features

*   **Cross-Platform**: Works on Windows, Linux, and macOS.
*   **Seamless Integration**: Adds a dedicated "Zotero" tab to the WPS Ribbon.
*   **Smart Citation**: Insert and edit citations using Zotero's powerful search.
*   **Live Bibliography**: Automatically generate and update bibliographies.
*   **Style Support**: Compatible with thousands of citation styles (APA, MLA, Chicago, etc.).
*   **Background Service**: Automatic proxy management for hassle-free connection.
*   **Compatibility**: Supports Zotero 6, Zotero 7 and Zotero 8.

## 📋 Prerequisites

Before installing, ensure you have:

1.  **WPS Office**: [Download Latest Version](https://www.wps.com/) (or https://www.wps.cn for CN version).
2.  **Zotero**: [Download Zotero 6, 7 and 8](https://www.zotero.org/).
3.  **Python 3.x**: Required for the communication bridge.
    *   **Windows**: Ensure "Add Python to PATH" is checked during installation.
    *   **Linux/macOS**: Usually pre-installed, but verify with `python3 --version`.

## 🚀 Installation

### Windows

1.  **Download**: Get the latest source code (Download ZIP) and extract it.
2.  **Run Installer**: Double-click `windows安装与卸载.bat` (Install/Uninstall script).
3.  **Install**: Type `1` and press Enter.
4.  **Restart**: Close and reopen WPS Office completely.

### Linux & macOS

1.  **Terminal**: Open your terminal.
2.  **Navigate**: Go to the downloaded/cloned directory.
	```bash
	git clone https://github.com/RajaSunrise/wps-zotero.git
	
	cd wps-zotero
	```
3.  **Install**:
    ```bash
    python3 install.py
    ```
4. **Proxy**:
   ```bash
   python3 proxy.py
   ```
5.  **Restart**: Restart WPS Office.

> **Note**: The installation sets up a background service that starts automatically. You don't need to run any scripts manually after installation.


### First Run Experience
1.  Open **Zotero** desktop application.
2.  Open **WPS Writer**.
3.  Click "Add/Edit Citation".
4.  If prompted, grant permissions or allow the connection in Zotero.

## 🔧 Troubleshooting

### Common Issues

**1. "Zotero" tab does not appear**
*   **Check Python**: Run `python --version` in CMD/Terminal.
*   **Check Path**: Ensure the plugin folders were created in the WPS `jsaddons` directory.
    *   Windows: `%APPDATA%\kingsoft\wps\jsaddons`
    *   Linux: `~/.local/share/Kingsoft/wps/jsaddons`
    *   macOS: `~/Library/Application Support/Kingsoft/WPS/jsaddons`
*   **Restart**: WPS sometimes needs a full restart (check Task Manager/Activity Monitor to kill all WPS processes).

**2. Nothing happens when clicking buttons**
*   **Is Zotero Running?**: Zotero must be open.
*   **Check Proxy**: The Python background service might not be running.
    *   **Windows**: Check Task Manager for a python process running `proxy.py`.
    *   **Linux/Mac**: Run `ps aux | grep proxy.py`.
*   **Logs**: Check the log file for errors:
    *   Windows: `%APPDATA%\kingsoft\wps\jsaddons\wps-zotero-proxy.log`
    *   Linux/Mac: `~/.wps-zotero-proxy.log`

**3. "Connection Error"**
*   Disable VPNs or Proxies temporarily to test.
*   Check if your firewall is blocking Python.

## 🗑️ Uninstallation

*   **Windows**: Run `windows安装与卸载.bat` and select option `2`.
*   **Linux / macOS**: Run `python3 install.py -u`.

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE.txt](LICENSE.txt) file for details.
