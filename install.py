#!/usr/bin/env python3

import os
import platform
import shutil
import sys
import re
import stat
import subprocess 
from proxy import stop_proxy


# Prevent running as root on Linux
if platform.system() == 'Linux' and os.environ.get('USER') == 'root':
    print("This addon cannot be installed as root!", file=sys.stderr)
    sys.exit(1)


# Check whether Python 3 is in PATH and return the full path
def checkpy():
    def runcmd(cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        code = p.wait()
        res = [line.decode() for line in p.stdout.readlines()]
        return code, res

    if platform.system() == 'Windows':
        cmd = 'where python'
    else:
        cmd = 'which python3'

    code, pyexes = runcmd(cmd)

    # If which python3 failed, try python
    if (code != 0 or len(pyexes) == 0) and platform.system() != 'Windows':
         cmd = 'which python'
         code, pyexes = runcmd(cmd)

    ver = None
    py_path = None

    if len(pyexes) > 0:
        py_path = pyexes[0].strip()
        # Check version
        try:
            # On Windows, python --version might print to stderr?
            p = subprocess.Popen([py_path, '--version'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out, _ = p.communicate()
            res = [out.decode()]
            if len(res) > 0 and 'Python 3' in res[0]:
                ver = res[0].strip()
        except Exception as e:
            print(f"Error checking python version: {e}")

    if ver is None:
        print('Please add Python 3 to the PATH environment variable!')
        # Allow continue but warn? Or fail? The script needs python3.
        # But we are running IN python3 usually.
        py_path = sys.executable
        ver = platform.python_version()
        print(f"Using current python interpreter: {py_path} ({ver})")

    else:
        print('Python found:', ver)
        print('Path:', py_path)
        
    return py_path.replace('\\', '\\\\') # Escape backslashes for JS string


# Determine python path
PYTHON_PATH = checkpy()


# File & directory paths
PKG_PATH = os.path.dirname(os.path.abspath(__file__))
with open(PKG_PATH + os.path.sep + 'version.js') as f:
    VERSION = f.readlines()[0].split('=')[-1].strip()[1:-1]
APPNAME = 'wps-zotero_{}'.format(VERSION)

# Determine ADDON_PATH
if platform.system() == 'Windows':
    ADDON_PATH = os.environ['APPDATA'] + '\\kingsoft\\wps\\jsaddons'
elif platform.system() == 'Darwin':
    # MacOS path
    # Try standard path
    home = os.environ['HOME']
    possible_paths = [
        home + '/Library/Application Support/Kingsoft/WPS/jsaddons',
        home + '/Library/Containers/com.kingsoft.wpsoffice.mac/Data/Library/Application Support/Kingsoft/WPS/jsaddons'
    ]
    ADDON_PATH = possible_paths[0]
    # Check if the second one exists (sandboxed), if so use it?
    # Or maybe we should try to install to both or ask user?
    # For now default to standard Application Support.
    if os.path.exists(possible_paths[1]):
        ADDON_PATH = possible_paths[1]
else:
    # Linux
    ADDON_PATH = os.environ['HOME'] + '/.local/share/Kingsoft/wps/jsaddons'

print(f"Installing to: {ADDON_PATH}")

XML_PATHS = {
    'jsplugins': ADDON_PATH + os.path.sep + 'jsplugins.xml',
    'publish': ADDON_PATH + os.path.sep + 'publish.xml',
    'authwebsite': ADDON_PATH + os.path.sep + 'authwebsite.xml'
}
PROXY_PATH = ADDON_PATH + os.path.sep + 'proxy.py'


def install_startup_service(addon_dir, python_path):
    print("Installing background service for automatic startup...")

    proxy_script = os.path.join(addon_dir, 'proxy.py')

    if platform.system() == 'Linux':
        autostart_dir = os.path.join(os.environ['HOME'], '.config', 'autostart')
        if not os.path.exists(autostart_dir):
            os.makedirs(autostart_dir, exist_ok=True)

        desktop_file = os.path.join(autostart_dir, 'wps-zotero-proxy.desktop')
        with open(desktop_file, 'w') as f:
            f.write(f'''[Desktop Entry]
Type=Application
Name=WPS Zotero Proxy
Exec="{python_path}" "{proxy_script}" --persistent
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=Proxy server for WPS Zotero integration
''')
        print(f"Created autostart entry: {desktop_file}")

        # Start it now
        subprocess.Popen([python_path, proxy_script, '--persistent'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    elif platform.system() == 'Darwin':
        # MacOS LaunchAgent
        launch_agents = os.path.join(os.environ['HOME'], 'Library', 'LaunchAgents')
        if not os.path.exists(launch_agents):
            os.makedirs(launch_agents, exist_ok=True)

        plist_path = os.path.join(launch_agents, 'com.wps-zotero.proxy.plist')
        with open(plist_path, 'w') as f:
            f.write(f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wps-zotero.proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{proxy_script}</string>
        <string>--persistent</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
''')
        print(f"Created LaunchAgent: {plist_path}")

        # Load it now
        try:
            subprocess.run(['launchctl', 'unload', plist_path], stderr=subprocess.DEVNULL)
            subprocess.run(['launchctl', 'load', plist_path], stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Failed to load LaunchAgent: {e}")

    elif platform.system() == 'Windows':
        startup_dir = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
        if not os.path.exists(startup_dir):
            os.makedirs(startup_dir, exist_ok=True)

        # Create a VBS script to run pythonw invisibly
        # Use pythonw if possible for no console
        python_exe = python_path.replace('\\\\', '\\')
        if 'python.exe' in python_exe.lower():
            # Try to use pythonw.exe in same dir
            pythonw = python_exe.lower().replace('python.exe', 'pythonw.exe')
            if os.path.exists(pythonw):
                python_exe = pythonw

        vbs_path = os.path.join(startup_dir, 'wps-zotero-proxy.vbs')
        proxy_script_win = proxy_script.replace('/', '\\')

        with open(vbs_path, 'w') as f:
            # VBScript to run command hidden
            # CreateObject("Wscript.Shell").Run "cmd /c ...", 0, False
            cmd = f'"{python_exe}" "{proxy_script_win}" --persistent'
            f.write(f'CreateObject("Wscript.Shell").Run "{cmd}", 0, False')

        print(f"Created startup script: {vbs_path}")

        # Start it now
        try:
            subprocess.Popen(['wscript', vbs_path], shell=False)
        except Exception as e:
            print(f"Failed to start proxy immediately: {e}")


def remove_startup_service():
    if platform.system() == 'Linux':
        desktop_file = os.path.join(os.environ['HOME'], '.config', 'autostart', 'wps-zotero-proxy.desktop')
        if os.path.exists(desktop_file):
            print(f"Removing {desktop_file}")
            os.remove(desktop_file)

    elif platform.system() == 'Darwin':
        plist_path = os.path.join(os.environ['HOME'], 'Library', 'LaunchAgents', 'com.wps-zotero.proxy.plist')
        if os.path.exists(plist_path):
            try:
                subprocess.run(['launchctl', 'unload', plist_path], stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Failed to unload plist: {e}")
            print(f"Removing {plist_path}")
            os.remove(plist_path)

    elif platform.system() == 'Windows':
        vbs_path = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup', 'wps-zotero-proxy.vbs')
        if os.path.exists(vbs_path):
            print(f"Removing {vbs_path}")
            os.remove(vbs_path)


def uninstall():
    print("Trying to quit proxy server if it's currently listening...")
    stop_proxy()
    remove_startup_service()
    
    def del_rw(action, name, exc):
        os.chmod(name, stat.S_IWRITE)
        os.remove(name)

    if not os.path.isdir(ADDON_PATH):
        return

    for x in os.listdir(ADDON_PATH):
        if os.path.isdir(ADDON_PATH + os.path.sep + x) and 'wps-zotero' in x:
            print('Removing {}'.format(ADDON_PATH + os.path.sep + x))
            shutil.rmtree(ADDON_PATH + os.path.sep + x, onerror=del_rw)

    for fp in XML_PATHS.values():
        if not os.path.isfile(fp):
            continue
        with open(fp) as f:
            xmlStr = f.read()
        records = [(m.start(),m.end()) for m in re.finditer(r'[\ \t]*<.*wps-zotero.*/>\s*', xmlStr)]
        # Reverse order to avoid index shifting
        records.reverse()
        for r in records:
            print('Removing record from {}'.format(fp))
            xmlStr = xmlStr[:r[0]] + xmlStr[r[1]:]

        with open(fp, 'w') as f:
            f.write(xmlStr)


# Uninstall existing installation
print('Uninstalling previous installations if there is any ...')
uninstall()
if len(sys.argv) > 1 and sys.argv[1] == '-u':
    sys.exit()


# Begin installation
print('Installing')


# Create necessary directory and files
if not os.path.exists(ADDON_PATH):
    os.makedirs(ADDON_PATH, exist_ok=True)
if not os.path.exists(XML_PATHS['jsplugins']):
    with open(XML_PATHS['jsplugins'], 'w') as f:
        f.write('''<jsplugins>
</jsplugins>
''')
if not os.path.exists(XML_PATHS['publish']):
    with open(XML_PATHS['publish'], 'w') as f:
        f.write('''<?xml version="1.0" encoding="UTF-8"?>
<jsplugins>
</jsplugins>
''')
if not os.path.exists(XML_PATHS['authwebsite']):
    with open(XML_PATHS['authwebsite'], 'w') as f:
        f.write('''<?xml version="1.0" encoding="UTF-8"?>
<websites>
</websites>
''')


# Copy to jsaddons
target_dir = ADDON_PATH + os.path.sep + APPNAME
shutil.copytree(PKG_PATH, target_dir)

# Create/Update config.js in the installed directory
config_path = os.path.join(target_dir, 'js', 'config.js')
with open(config_path, 'w') as f:
    f.write('// This file is automatically generated by install.py\n')
    f.write(f'const PYTHON_PATH = "{PYTHON_PATH}";\n')
    # Escape backslashes for JS string
    addon_path_js = ADDON_PATH.replace('\\', '\\\\')
    f.write(f'const ADDON_PATH = "{addon_path_js}";\n')


# Write records to XML files
def register(fp, tagname, record):
    with open(fp) as f:
        content = f.read()

    # Check if already registered (should be removed by uninstall, but safety check)
    if 'wps-zotero' in content:
        print(f"Record already exists in {fp}")
        return

    pos = [m.end() for m in re.finditer(r'<' + tagname + r'>\s*', content)]
    if len(pos) == 0:
        # Tag not found, maybe empty file or wrong structure?
        # Try to wrap content in tag if it looks like xml
        if '<?xml' in content:
             # Just append at end? No, need inside root
             pass
        content += f'<{tagname}></{tagname}>'
        pos = [content.index(f'</{tagname}>')]

    i = pos[0]
    with open(fp, 'w') as f:
        f.write(content[:i] + record + os.linesep + content[i:])

rec = '<jsplugin name="wps-zotero" type="wps" url="http://127.0.0.1:3889/" version="{}"/>'.format(VERSION)
register(XML_PATHS['jsplugins'], 'jsplugins', rec)
rec = '<jsplugin url="http://127.0.0.1:3889/" type="wps" enable="enable_dev" install="null" version="{}" name="wps-zotero"/>'.format(VERSION)
register(XML_PATHS['publish'], 'jsplugins', rec)
rec = '<website origin="null" name="wps-zotero" status="enable"/>'
register(XML_PATHS['authwebsite'], 'websites', rec)


# Alleviate the "Zotero window not brought to front" problem.
# https://www.zotero.org/support/kb/addcitationdialog_raised
if os.name == 'nt':
    print('Change zotero preference to alleviate the problem of Zotero window not showing in front.')
    try:
        tmp = os.environ['APPDATA'] + '\\Zotero\\Zotero\\Profiles\\'
        if os.path.exists(tmp):
            for fn in os.listdir(tmp):
                profile_path = os.path.join(tmp, fn)
                if os.path.isdir(profile_path) and os.path.isfile(os.path.join(profile_path, 'prefs.js')):
                    pref_fn = os.path.join(profile_path, 'prefs.js')
                    with open(pref_fn) as f:
                        content = f.read()
                    if 'extensions.zotero.integration.keepAddCitationDialogRaised' in content:
                        content = content.replace('user_pref("extensions.zotero.integration.keepAddCitationDialogRaised", false)', 'user_pref("extensions.zotero.integration.keepAddCitationDialogRaised", true);')
                    else:
                        content += '\nuser_pref("extensions.zotero.integration.keepAddCitationDialogRaised", true);\n'
                    with open(pref_fn, 'w') as f:
                        f.write(content)
    except Exception as e:
        print(f"Failed to update Zotero prefs: {e}")

# Install Startup Service
try:
    install_startup_service(target_dir, PYTHON_PATH.replace('\\\\', '\\'))
except Exception as e:
    print(f"Failed to install startup service: {e}")

print('All done, enjoy!')
print('(run ./install.py -u to uninstall)')
