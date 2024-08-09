'''
UNRAID system monitoring screen script.
Powered by Python, matplotlib, and psutil.
Designed to run completely in Docker, but can also be run elsewhere.
Probably using matplotlib in ways it wasn't designed for, lmao.

Based on scripts from:
https://github.com/adafruit/Adafruit_Learning_System_Guides/tree/main/TFT_Sidekick_With_FT232H
and going overboard with the concept, extending it with multithreading + all the stuff you see below.

print("\n\
   ██   ██ ███   ██ ██████   █████  ██ ██████     \n\
   ██   ██ ████  ██ ██   ██ ██   ██ ██ ██   ██    \n\
   ██   ██ ██ ██ ██ ██████  ███████ ██ ██   ██    \n\
   ██   ██ ██  ████ ██   ██ ██   ██ ██ ██   ██    \n\
    █████  ██   ███ ██   ██ ██   ██ ██ ██████     \n\
                                                  \n\
███████ ████████  █████  ████████ ██   ██ ███████ \n\
██         ██    ██   ██    ██    ██   ██ ██      \n\
███████    ██    ███████    ██    ██   ██ ███████ \n\
     ██    ██    ██   ██    ██    ██   ██      ██ \n\
███████    ██    ██   ██    ██     █████  ███████ \n\
                                                  \n\
 ███████  █████ ██████  ███████ ███████ ███   ██  \n\
 ██      ██     ██   ██ ██      ██      ████  ██  \n\
 ███████ ██     ██████  █████   █████   ██ ██ ██  \n\
      ██ ██     ██   ██ ██      ██      ██  ████  \n\
 ███████  █████ ██   ██ ███████ ███████ ██   ███  \n\
                                                  \n\
   ░       ░      ░             ░  ░     ░    ░   \n\
 ░ ░  ░   ░░   ░  ▒  ░░      ░  ▒  ░ ░   ░    ░   \n\
 ░ ▒  ▒   ░▒ ░ ▒░ ▒  ░▒ ░    ▒  ▒▒░░ ░   ░  ░ ▒  ░\n\
 ▒▒▓▒ ▒ ░ ▒▓ ░▒▓░░▓  ▒▓▒░ ░░▒▒  ▓▒▓░ ░▒  ▒ ░░ ▒░ ░\n\
░▒▓▓▓▓▓ ░▓▓▓ ▒▓▓▒░▓▓░▒▓███  by: WeegeeNumbuh1  ███\n")
'''
import time
START_TIME: float = time.time() # start timing this script
import datetime
STARTED_DATE: datetime = datetime.datetime.now()
VERSION: str = "v.3.8 --- 2024-08-09"
import os
os.environ["PYTHONUNBUFFERED"] = "1"
print(f"Version: {VERSION}")
print(f"Script started: {STARTED_DATE.replace(microsecond=0)}")
from pathlib import Path
CURRENT_DIR = Path(__file__).resolve().parent
# Load built-in modules
import signal
import sys
import gc
import threading
import socket
from collections import deque
import concurrent.futures as CF

#==| Default Config |=====================================================
#=========================================================================
DEBUG: bool = True
REFRESH_RATE: float = 3
PLOT_SIZE: float = 5
ARRAY_PATH: str = "/rootfs/mnt/user0"
CPU_TEMP_SENSOR: str = "k10temp"
NETWORK_INTERFACE: str = "bond0"
SPLASH_SCREEN: str = "/app/background.bmp"
IMAGE_ROTATION: int = 180
PLOT_CONFIG: tuple = (
    # --- PLOT 1
    {
    'title' : 'C P U',
    'ylim' : (0, 100),
    'line_config' : (
        {'width': 1, 'alpha': 0.5, 'style': '-'}, # CPU
        {'width': 1, 'alpha': 0.5, 'style': '--'}  # Temps
        )
    },
    # --- PLOT 2 (CPU core heatmap)
    {
    'title' : 'C o r e   H e a t m a p',
    #'ylim' : (0, 100),
    'line_config' : (
        {}, # need this just so we can plot
        )
    },
    # --- PLOT 3 (middle plot)
    {
    'title' : 'D i s k s',
    # 'ylim' : (0, 1000),
    'line_config' : (
        {'width': 1, 'alpha': 0.5, 'style': '-'}, # read
        {'width': 1, 'alpha': 0.5, 'style': '--'}, # write
        )
    },
    # --- PLOT 4 (bottom plot)
    {
    'title' : 'N e t w o r k',
    #'ylim' : (0, 1000),
    'line_config' : (
        {'width': 1, 'alpha': 0.5, 'style': '-'}, # received
        {'width': 1, 'alpha': 0.5, 'style': '--'}, # sent
        )
    },
    # --- PLOT 5 (Resource usage)
    {
    #'title' : 'Resources',
    'line_config' : (
        {} # a bar graph
    )
    }
)
BARPLOT_COLORS: list = ['#375e1f','#4a2a7a']

#==| Program setup |==========================================================
#=============================================================================

def sigterm_handler(signal, frame):
    ''' Cleanly exit when this Docker is shut down. '''
    mainpool.shutdown(wait=False, cancel_futures=True)
    disp.image(bg_image, IMAGE_ROTATION) # leave a splash screen up when we exit
    end_time = round(time.time() - START_TIME, 3)
    print(f"- Exit signal commanded at {datetime.datetime.now()}")
    print(f"  Script ran for {timedelta_clean(end_time)} and sampled {samples} times with {dropped_frames} dropped sample(s).")
    print("Main loop stopped. See you next time!")
    sys.exit(0)

def print_stderr(*a) -> None:
    ''' Wrapper to send a message to stderr. '''
    print(*a, file = sys.stderr)

def check_settings() -> None:
    '''
    Checks if the settings are correct and sets flags or reverts variables to safe fallbacks
    if they're incorrect or invalid.
    '''
    global cpu_temp_available, network_interface_set, array_valid, REFRESH_RATE, CPU_TEMP_SENSOR, IMAGE_ROTATION, PLOT_SIZE
    if REFRESH_RATE < 0.5:
        print_stderr("Warning: Refresh rate set too low. Refresh rate will be set to 0.5 seconds.")
        REFRESH_RATE = 0.5

    if PLOT_SIZE < 1:
        print_stderr(f"Warning: Desired plot duration ({PLOT_SIZE} min) is too short. Value will be reset to 1 minute.")
        PLOT_SIZE = 1

    valid_rotations = [0, 90, 180, 270]
    if IMAGE_ROTATION in valid_rotations:
        pass
    else:
        print_stderr(f"Warning: Current image rotation value ({IMAGE_ROTATION}) is invalid. Value will be reset to \'0\'.")
        IMAGE_ROTATION = 0
    del valid_rotations

    if not hasattr(psutil, "sensors_temperatures"):
        print_stderr("Notice: Temperature readouts not supported on this platform.")
        cpu_temp_available = False
    else:
        temps_test = psutil.sensors_temperatures()
        if not temps_test:
            print_stderr("Notice: No temperatures found on this system.")
            cpu_temp_available = False
        del temps_test
    # probe possible temperature names    
    if cpu_temp_available == True:
        try:
            test1 = psutil.sensors_temperatures()[CPU_TEMP_SENSOR][0].current
            del test1
        except:
            print_stderr(f"Warning: CPU temperature \'{CPU_TEMP_SENSOR}\' not found.")
            # Intel, AMD, then generic names
            probe_sensor_names = iter(['coretemp', 'k10temp', 'k8temp', 'cpu_thermal', 'cpu_thermal_zone'])
            # try until we hit our first success
            while True:
                sensor_entry = next(probe_sensor_names, "nothing")
                if sensor_entry == "nothing":
                    print_stderr("         Continuing without temperature plot.")
                    sensor_list = psutil.sensors_temperatures()
                    print("Notice:  For your reference, the following temperature sensors were found:")
                    for name, entries in sensor_list.items():
                        print(f"{name}   ", end='')
                    print()
                    del sensor_list
                    cpu_temp_available = False
                    break
                try:
                    test1 = psutil.sensors_temperatures()[sensor_entry][0].current
                    # if successful, continue the rest of this block
                    print_stderr(f"Notice: \'{CPU_TEMP_SENSOR}\' was not found but \'{sensor_entry}\' was.\n\
        Please update the configuration to suppress this message in the future.")
                    CPU_TEMP_SENSOR = sensor_entry
                    del test1
                    break
                except:
                    pass

    try:
        test2 = psutil.disk_usage(ARRAY_PATH)
        del test2
    except:
        print_stderr(f"Warning: Array path \'{ARRAY_PATH}\' does not exist. Defaulting to '/'.")
        array_valid = False
    try:
        test3 = psutil.net_io_counters(pernic=True)[NETWORK_INTERFACE]
        del test3
    except:
        print_stderr(f"Warning: Network interface \'{NETWORK_INTERFACE}\' not found. Network readouts may be incorrect.")
        nic_stats = psutil.net_io_counters(pernic=True)
        nic_names = list(nic_stats.keys())
        print("Notice:  For your reference, the following network interfaces were found:")
        for name in nic_names:
            print(f"{name}   ", end='')
        print()
        del nic_stats, nic_names
        network_interface_set = False

    print("Settings verification complete.")
    if DEBUG == True:
        if psutil.cpu_freq().max == 0:
            cpu_max = "[N/A]"
        else:
            cpu_max = round(psutil.cpu_freq().max / 1000, 2)
        if cpu_temp_available == True:
            print(f"• CPU temp sensor: \'{CPU_TEMP_SENSOR}\' on a ~{cpu_max}GHz CPU with {CORE_COUNT} logical core(s)")
        else:
            print(f"• CPU has {CORE_COUNT} logical core(s) @ ~{cpu_max}GHz")
        if array_valid == True:
            print(f"• Array path: \'{ARRAY_PATH}\'")
        if network_interface_set == True:
            print(f"• Network interface: \'{NETWORK_INTERFACE}\'")
    
    # This whole script is structured around 5 entries. If you want to add or remove stuff, have fun 💥
    if len(PLOT_CONFIG) != 5:
        print_stderr(f"ERROR: There must be 5 entries in the PLOT_CONFIG setting. Only {len(PLOT_CONFIG)} were found.")
        raise AssertionError("Insufficient entries in configuration.")

def it_broke(type: int) -> None:
    ''' Our error handler. 1 = thread timeout, any other value is for any unknown error. '''
    disp.image(bg_image, IMAGE_ROTATION)
    mainpool.shutdown(wait=False, cancel_futures=True)
    if type == 1:
        end_time = round(time.time() - START_TIME, 3)
        print(f"- Process exit commanded at {datetime.datetime.now()}")
        print(f"  Script ran for {timedelta_clean(end_time)} and sampled {samples} times with {dropped_frames} dropped sample(s).")
        raise ResourceWarning("Script terminated due to system conditions.")
    else:
        raise GeneratorExit("Script terminated due to unhandled error.")
        
def bytes2human(n, format: str = "%(value).1f%(symbol)s") -> str:
    '''
    Convert bytes to a more readable size.
    Pulled from _common.py of psutil with the symbols edited to better match this script.

    >>> bytes2human(10000)
    '9.8KiB'
    >>> bytes2human(100001221)
    '95.4MiB'
    '''
    symbols = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i + 1) * 10
    for symbol in reversed(symbols[1:]):
        if abs(n) >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            return format % locals()
    return format % dict(symbol=symbols[0], value=n)

def get_ip() -> str:
    ''' Gets us our local IP. Thanks `fatal_error` off of Stack Overflow for this solution. '''
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect(('10.254.254.254', 1)) # doesn't even need to connect
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def timedelta_clean(timeinput: datetime) -> str:
    ''' Cleans up time deltas without the microseconds. '''
    delta_time = datetime.timedelta(seconds=timeinput)
    return str(delta_time).split(".")[0]

def refresh_rate_limiter(setup_time: float) -> None:
    ''' Adjusts refresh rate for really slow systems. '''
    global REFRESH_RATE, PROFILER_COUNT, PROFILE_DISPLAY_RENDER, timeout_wait
    init_refresh = REFRESH_RATE
    if setup_time >= 0 and setup_time < 10:
        return
    elif setup_time >= 10 and setup_time < 16:
        print("Notice: Setup took a considerable amount of time. First run?")
        if REFRESH_RATE < 2:
            print_stderr(f"         Refresh rate will be set to 2 seconds. (was {init_refresh}s)")
            REFRESH_RATE = 2
            timeout_wait = [REFRESH_RATE * 1.5, REFRESH_RATE * 1.5]
        if PROFILING == True:
            PROFILER_COUNT = 100
    elif setup_time >= 16 and setup_time < 24:
        print_stderr("Warning: Setup took a very considerable amount of time.")
        if REFRESH_RATE < 4:
            print_stderr(f"         Refresh rate will be set to 4 seconds. (was {init_refresh}s)")            
            REFRESH_RATE = 4
            timeout_wait = [REFRESH_RATE * 2, REFRESH_RATE * 2]
        if PROFILING == True:
            PROFILER_COUNT = 60
    elif setup_time >= 24 and setup_time < 60:
        print_stderr("Warning: We're running on a literal potato.")
        if REFRESH_RATE < 10:
            REFRESH_RATE = 10
            timeout_wait = [REFRESH_RATE * 2, REFRESH_RATE * 2]
            print_stderr(f"         Refresh rate will be set to 10 seconds. (was {init_refresh}s)")
        if PROFILING == True:
            PROFILER_COUNT = 45
    elif setup_time >= 60:
        print_stderr("ERROR: Setup took too long to finish. This system is unsuitable to run this program.")
        it_broke(1)
    if DEBUG == True:
        plot_settings.set_text(f"Refresh: {REFRESH_RATE}s | Plot: {round(REFRESH_RATE * (HIST_SIZE - 1),1)}s")

def thread_timer(begin_time: float, thread_id: int) -> None:
    ''' Collects how long it takes for the render threads to do their thing. '''
    global current_data
    if thread_id == 0:
        thread_time[0] = round(time.time() - begin_time, 4)
        if PROFILE_DISPLAY_RENDER == 0:
            current_data[-1] = thread_time[0]        
    elif thread_id == 1:
        thread_time[1] = round(time.time() - begin_time, 4)
        if PROFILE_DISPLAY_RENDER == 1:
            current_data[-1] = thread_time[1]        
    else:
        return

# Initialize a sample counter
samples: int = 0
dropped_frames: int = 0

# Flags for checking user config (no type declarations here to work with older python)
cpu_temp_available = True
network_interface_set = True
array_valid = True

#==| Environment setup |======================================================
#=============================================================================

# Get hostname and IP address (this should be static since this is Unraid)
UNRAID_HOSTNAME = socket.gethostname()
UNRAID_IP = get_ip()
print(f"Hey there, {UNRAID_HOSTNAME} @ {UNRAID_IP}!")

# Check Unraid version
UNRAID_VER_FILE: str = '/rootfs/etc/unraid-version'
try:
    with open(UNRAID_VER_FILE) as unraid_str:
        # String format: 'version="x.x.x"\n'
        input_list = unraid_str.readlines()
    UNRAID_VERSION: str = str(input_list[0]).split('"')[1]
    print(f"We're running in Unraid version {UNRAID_VERSION}")
    del input_list, UNRAID_VER_FILE
except:
    print_stderr("Warning: are we running in UNRAID?")
    UNRAID_VERSION: str = "Unknown"

# Load our settings file
if str(CURRENT_DIR) == "/":
    SETTINGS_FILE = f"{CURRENT_DIR}settings.yaml"
else:
    SETTINGS_FILE = f"{CURRENT_DIR}/settings.yaml"
try:
    import yaml
    with open(SETTINGS_FILE, mode="rb") as file:
        settings_loaded = yaml.safe_load(file)
        print(f"Loaded settings file \'{SETTINGS_FILE}\'")
    try:
        DEBUG: bool = settings_loaded['DEBUG']
        REFRESH_RATE: float = settings_loaded['REFRESH_RATE']
        PLOT_SIZE: float = settings_loaded['PLOT_SIZE']
        ARRAY_PATH: str = settings_loaded['ARRAY_PATH']
        CPU_TEMP_SENSOR: str = settings_loaded['CPU_TEMP_SENSOR']
        NETWORK_INTERFACE: str = settings_loaded['NETWORK_INTERFACE']
        SPLASH_SCREEN: str = settings_loaded['SPLASH_SCREEN']
        IMAGE_ROTATION: int = settings_loaded['IMAGE_ROTATION']
        BARPLOT_COLORS: list = settings_loaded['BARPLOT_COLORS']
        PLOT_CONFIG: tuple = settings_loaded['PLOT_CONFIG']
        print("Successfully parsed settings file.")
    except:
        print_stderr("Warning: Unable to parse settings file completely.\n\
         To prevent an inconsistent state, the program will now exit.\n\
         Please check the settings file for any typos.")
        time.sleep(5)
        raise ValueError("Settings file has invalid or missing entries.")
    finally:
        del settings_loaded
except ImportError:
    print_stderr("Warning: Required Python module \'yaml\' could not be loaded and settings file cannot be used.\n\
         Please check your Python environment. Using default settings.")
except:
    print_stderr(f"Warning: Unable to load settings file \'{SETTINGS_FILE}\'\n\
         Using default settings.")

if DEBUG == True:
    print("• Verbose setting enabled. Verbose data will be prefixed with • in the logs")
    print("  and additional data rendered on-screen.")
    print(f"• We're using: {sys.executable}")
    print(f"• We're running in: {CURRENT_DIR}")
    #print_stderr("• ℹ️ Testing a stderr message on this line.")
  
# Reduce traceback fluff and automatic garbage collections
if DEBUG == False:
    sys.tracebacklimit = 0
else:
    sys.tracebacklimit = 1
gc.set_threshold(10000, 50, 20)

# Load in external dependencies after printing where we're running python
try:
    # Python Imaging Library
    from PIL import Image
    # Matplotlib
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotx
    import numpy as np
    # System Stats
    import psutil
except:
    raise ImportError("Required modules failed to load. Check your Python environment.")

# Check environment just in case we're not started by init.sh
if "BLINKA_FT232H" in os.environ:
    if os.environ["BLINKA_FT232H"] != "1":
        os.environ["BLINKA_FT232H"] = "1"
else:
    os.environ["BLINKA_FT232H"] = "1"

# Load in Blinka CircuitPython
try:
    import board
    import digitalio
    import adafruit_rgb_display.ili9341 as ili9341
    from pyftdi.ftdi import Ftdi
except:
    raise ImportError("Cannot load in required interfaces. Possible causes:\n\
             - FT232H board not detected or attached.\n\
             - Insufficient permission to access USB devices. Try running with elevated permissions.\n\
             - The dependencies may not have been set up correctly.")

# print("- Checking status of display:")
try:
    #Ftdi().open_from_url('ftdi:///?') # this will force a SystemExit, don't use
    Ftdi.show_devices()
except:
    it_broke(2)

# Setup display
cs_pin = digitalio.DigitalInOut(board.C0)
dc_pin = digitalio.DigitalInOut(board.C1)
rst_pin = digitalio.DigitalInOut(board.C2)
disp = ili9341.ILI9341(board.SPI(), cs=cs_pin, dc=dc_pin, rst=rst_pin, baudrate=24000000)
if DEBUG == True:
    print(f"• Display size: {disp.width}x{disp.height}")

# Have a splash screen while loading
try:
    bg_image = Image.open(SPLASH_SCREEN).convert('RGB')
except:
    bg_image = Image.new('RGB', (disp.width, disp.height))    
    print_stderr(f"Notice: Unable to load splash screen ({SPLASH_SCREEN}). Check your configuration.")
disp.image(bg_image, IMAGE_ROTATION)

# Get us our core count
CORE_COUNT = os.cpu_count()
if CORE_COUNT == None:
    raise RuntimeError("Cannot determine CPU core count. Program cannot continue.")

# Important; changes some variables if necessary before their first use
check_settings()

# Convert desired plot duration to plot size
HIST_SIZE = int((PLOT_SIZE * 60) // REFRESH_RATE) + 1
''' Our plot length '''
if HIST_SIZE > 501:
    HIST_SIZE = 501
    print_stderr(f"Warning: Desired plot history ({PLOT_SIZE}min) cannot fit into plot. Data will be truncated.")

# our baseline thread timeout until/if the profiler takes over
timeout_wait = [REFRESH_RATE * 1.25, REFRESH_RATE * 1.25]
matplotlib.use('Agg', force=True)

if DEBUG == True:
    print(f"• Using: matplotlib {matplotlib.__version__}, {matplotlib.get_backend()} backend\n\
         psutil {psutil.version_info} | numpy {np.__version__} | PIL {Image.__version__}")
    
# Start our thread pool
mainpool = CF.ThreadPoolExecutor(max_workers=7)
'''
We expect to only run the following:
- update_data() ← one thread
    - 4 workers
- update_plot() ← our plot generator
- plot_renderer() ← our display renderer
- Σ = 7
'''

# Get info of our current process
this_process = psutil.Process()
this_process_cpu = this_process.cpu_percent(interval=None)
if DEBUG == True:
    try:
        print(f"• Running on CPU core {this_process.cpu_num()} with {this_process.num_threads()} threads")
    except:
        print(f"• Running with {this_process.num_threads()} threads")

PROFILING: bool = True
''' Enable or disable the thread timeout profiler, HIGHLY recommended to be left as True '''
PROFILER_COUNT: int = 0
''' 
How many samples for our profiler. Don't set too high,
we need to get our stats for our thread timeouts sooner than later.
The profiler will run PROFILER_COUNT * REFRESH_RATE seconds.
'''
CPU_AFFECT_RATIO: int = 100
''' 
Take our current CPU load (out of 100) and divide by this number.
higher value = less effect, lower = more effect
ex: 100%/200 = 0.5, 100%/100 = 1, 100%/50 = 2, 100%/25 = 4, etc.
'''
if PROFILING == True:
    PROFILER_COUNT = 150 
    CPU_AFFECT_RATIO = 20

time_array: list = [[],[]]
''' 
[
    [] → plot gen times
    [] → render times
]
'''
# initialize where we can measure our thread times
thread_time: list = [0,0]
''' [plot gen, render] '''

PROFILE_DISPLAY_RENDER: int = 2
''' 
Choose which stat to display on screen if DEBUG is enabled.
- 0 = measure wall time to generate plot
- 1 = measure wall time to render plot buffer to display
- anything else = measure both
'''

REFERENCE_RENDER_SPEED: int = 140
'''
This is our reference render speed (ms) based on a Ryzen 7 5700G system (my UNRAID hardware) on v.3.x of this script.
Fun fact, the slowest system this script was tested on was a Broadcom BCM2835 (Raspberry Pi Zero) at 100% CPU load.
It took anywhere between 4-6 seconds to do a single render.
On the opposite end was an overclocked Threadripper 7970X at 5.5GHz and it took approximately ~95ms to complete.
 '''

# Setup arrays we can put latest sensor info into rather than parsing our y_data list every time
current_data: list = []
for plot in PLOT_CONFIG: # this will make n+1 indices
    for _ in plot['line_config']:
        current_data.append(None)
current_data[-1] = "" # utilize that last index
cpu_percs_cores: list = [] # setup array for CPU core utilization

# Setup X data storage
x_time: list = [x * REFRESH_RATE for x in range(HIST_SIZE)]
x_time.reverse()

# Setup Y data storage
y_data = [ [deque([None] * HIST_SIZE, maxlen=HIST_SIZE) for _ in plot['line_config']]
           for plot in PLOT_CONFIG
         ]

#==| matplotlib setup |=======================================================
#=============================================================================

# Setup plot figure
matplotlib.style.use('fast')
plt.ioff
plt.style.use(matplotx.styles.ayu['dark']) # Ayumu Uehara?
fig, ax = plt.subplots(5, 1, figsize=(disp.width / 100, disp.height / 100),
                       gridspec_kw={'height_ratios': [4, 1, 4, 4, 2]})
fig.subplots_adjust(0.0,0.12,1,0.98) # adjust extent of margins (left, bottom, right, top [haha 98])
plt.rcParams.update({'font.size': 7})

# Set up text objects we can update
bbox_setting = dict(facecolor='black', edgecolor='None', pad=0.3, alpha=0.25)
if DEBUG == True:
    unraid_ver_text = ax[4].annotate(f"Unraid version {UNRAID_VERSION}",
                                     [0, -0.2], xycoords='axes fraction',
                                     verticalalignment='top',
                                     horizontalalignment='left',
                                     alpha=0.5, fontsize=6)    
    plot_settings = ax[4].annotate(f"Refresh: {REFRESH_RATE}s | Plot: {round(REFRESH_RATE * (HIST_SIZE - 1),1)}s",
                                   [0, -0.5], xycoords='axes fraction',
                                   verticalalignment='top',
                                   horizontalalignment='left',
                                   alpha=0.5, fontsize=6)
    debug_text = ax[4].annotate('', [1, -0.5], xycoords='axes fraction', 
                                verticalalignment='top',
                                horizontalalignment='right',
                                family='monospace',fontsize=6, alpha=0.5)
    frame_number_text = ax[4].annotate('', [1, -0.25], xycoords='axes fraction', 
                                       verticalalignment='top',
                                       horizontalalignment='right',
                                       family='monospace', fontsize=5, alpha=0.5)
host_test = ax[0].annotate(f"{UNRAID_HOSTNAME} {UNRAID_IP}",
                           [0.5, 1], xycoords='axes fraction',
                           verticalalignment='center',
                           horizontalalignment='center',
                           family='monospace', fontsize=5, alpha=0.5)
cpu_text = ax[0].annotate('', [0.5, 0.3], xycoords='axes fraction', 
                          verticalalignment='center',
                          horizontalalignment='center',
                          fontweight='black',
                          bbox=bbox_setting)
uptime_text = ax[2].annotate('', [0.5, 1.1], xycoords='axes fraction', 
                             verticalalignment='top',
                             horizontalalignment='center',
                             fontvariant='small-caps')
disk_text = ax[2].annotate('', [0.5, 0.3], xycoords='axes fraction', 
                           verticalalignment='center',
                           horizontalalignment='center',
                           fontweight='black',
                           bbox=bbox_setting)
network_text = ax[3].annotate('', [0.5, 0.3], xycoords='axes fraction',
                              verticalalignment='center',
                              horizontalalignment='center',
                              fontweight='black',
                              bbox=bbox_setting)
memory_text = ax[4].annotate('', [0.5, 0.725], xycoords='axes fraction', 
                             verticalalignment='center',
                             horizontalalignment='center',
                             fontweight='black')
storage_text = ax[4].annotate('', [0.5, 0.225], xycoords='axes fraction', 
                              verticalalignment='center',
                              horizontalalignment='center',
                              fontweight='black')

def annotate_axes(ax, text, fontsize: float = 10) -> None:
    ''' Puts text in the center of the plots '''
    ax.text(0.5, 0.5, text, transform=ax.transAxes,
            ha='center', va='center', fontsize=fontsize, 
            fontstyle='italic', fontweight='normal', alpha=0.4)

try:
    # Setup plot axis
    for plot, a in enumerate(ax):
        # custom settings
        if 'title' in PLOT_CONFIG[plot]:
            annotate_axes(ax[plot],PLOT_CONFIG[plot]['title'])
        if 'ylim' in PLOT_CONFIG[plot]:
            a.set_ylim(PLOT_CONFIG[plot]['ylim'])
        if plot == 1: # this is our CPU core heatmap
            a.axis('off')
            # a.yaxis.set_ticklabels([]) # turn off y-tick labels
            # a.set_yticks([])
            continue
        a.xaxis.set_ticklabels([])
        a.tick_params(axis='y', direction='in', pad=-20, labelsize=5)
        a.tick_params(axis='y', which='minor', left=False)
        a.tick_params(axis='x', which='minor', bottom=False)
        if plot == 4: # this is our barplot
            a.tick_params(bottom = False, left=False)
        # turn off all spines
        a.spines['top'].set_visible(False)  
        a.spines['bottom'].set_visible(False)  
        a.spines['right'].set_visible(False)  
        a.spines['left'].set_visible(False)
        # limit and invert x time axis
        if plot == 4: # we don't need to set the x-limits here
            continue
        a.set_xlim(min(x_time), max(x_time))
        a.invert_xaxis()

    # Setup plot lines
    plot_lines: list = []
    for plot, config in enumerate(PLOT_CONFIG):
        lines: list = []
        for index, line_config in enumerate(config['line_config']):
            # create line
            line, = ax[plot].plot(x_time, y_data[plot][index])
            # custom settings
            if 'color' in line_config:
                line.set_color(line_config['color'])
            if 'width' in line_config:
                line.set_linewidth(line_config['width'])
            if 'style' in line_config:
                line.set_linestyle(line_config['style'])
            if 'alpha' in line_config:
                line.set_alpha(line_config['alpha'])
            # add line to list
            lines.append(line)
        plot_lines.append(lines)
        # annotate_axes(ax[plot],AX_NAME[plot])
        
    # Make plot 1 a heatmap
    heatmap = ax[1].imshow(np.matrix(np.zeros(CORE_COUNT)),
                           cmap='gist_heat', vmin=0, vmax=100, aspect='auto', alpha=0.5)

    # Make plot 4 a horizontal bar graph
    barplot = ax[4].barh([1, 2], [0, 0], color=BARPLOT_COLORS)
    ax[4].set_xlim(right=100) 
    ax[4].set_yticks([1, 2],["Array", "Memory"])        
except:
    raise Exception("Failed to create plot. This may be caused by incorrect values in \'PLOT_CONFIG\'")
if DEBUG == True:
    print(f"• Plot length: {HIST_SIZE} samples")

#==| Main threads definitons |================================================
#=============================================================================

def update_data() -> None:
    '''
    Generates data for our plot.
    Sends workers to run in our thread pool, waits for them to finish,
    then returns. The workers sleep for REFRESH_RATE then append to y_data
    and current_data[].
    General form is:
           y_data[plot][line].append(new_data_point)
    '''

    # data_start = round(time.time(), 3) # to check how long this function takes
    def cpu_data_load() -> None:
        cpu_percs = psutil.cpu_percent(interval=REFRESH_RATE, percpu=False)
        y_data[0][0].append(cpu_percs)
        cpu_freq = psutil.cpu_freq()         
        cpu_f_ghz = round(cpu_freq.current / 1000, 2)
        current_data[0] = f"{cpu_percs}% {cpu_f_ghz} GHz"
        if cpu_temp_available == False:
            y_data[0][1].append(None)
            current_data[1] = None
        else:
            cpu_temp = psutil.sensors_temperatures()[CPU_TEMP_SENSOR][0].current
            y_data[0][1].append(cpu_temp)
            current_data[1] = f"{round(cpu_temp, 1)}°C"
        
    def cpu_data_core() -> None:
        global cpu_percs_cores
        cpu_percs_cores_tmp = psutil.cpu_percent(interval=REFRESH_RATE, percpu=True)
        cpu_percs_cores = cpu_percs_cores_tmp # write to cpu_percs_cores after blocking rather than blocking cpu_percs_cores
        y_data[1][0].append(1) # we want a max y-value of 1 for this plot

    def disk_data() -> None:
        # system-wide disk I/O, in MiB/s
        disk_start = psutil.disk_io_counters(nowrap=True)
        time.sleep(REFRESH_RATE)
        disk_finish = psutil.disk_io_counters(nowrap=True)
        iospeed_read = abs(disk_finish.read_bytes - disk_start.read_bytes) / REFRESH_RATE
        iospeed_write = abs(disk_finish.write_bytes - disk_start.write_bytes) / REFRESH_RATE
        y_data[2][0].append(iospeed_read / 1048576)
        y_data[2][1].append(iospeed_write / 1048576)
        current_data[2] = f"R:{bytes2human(iospeed_read)}/s"
        current_data[3] = f"W:{bytes2human(iospeed_write)}/s"

    def network_data() -> None:
        # network speed, in MiB/s
        nic_isup: bool = True
        if network_interface_set == False:
            net_start = psutil.net_io_counters()
            time.sleep(REFRESH_RATE)
            net_finish = psutil.net_io_counters()
        else:
            nic_isup = psutil.net_if_stats()[NETWORK_INTERFACE].isup
            net_start = psutil.net_io_counters(pernic=True, nowrap=True)[NETWORK_INTERFACE]
            time.sleep(REFRESH_RATE)
            net_finish = psutil.net_io_counters(pernic=True, nowrap=True)[NETWORK_INTERFACE]
        network_sent = abs(net_finish.bytes_sent - net_start.bytes_sent) / REFRESH_RATE
        network_recv = abs(net_finish.bytes_recv - net_start.bytes_recv) / REFRESH_RATE
        y_data[3][0].append(network_recv / 1048576)
        y_data[3][1].append(network_sent / 1048576)
        if nic_isup == True:
            current_data[4] = f"▼ {bytes2human(network_recv)}/s"
            current_data[5] = f"▲ {bytes2human(network_sent)}/s"
        else:
            current_data[4] = "⚠️ !!! NETWORK"
            current_data[5] = "DOWN !!! ⚠️"
    
    '''
    This was the old way of threading; this was much slower
    Kept here for notoriety.
    '''
    # t1 = threading.Thread(target=cpu_data_load, name='CPU Poller', daemon=True)
    # t2 = threading.Thread(target=cpu_data_core, name='CPU Core Poller', daemon=True)
    # t3 = threading.Thread(target=disk_data, name='Disk Poller', daemon=True)
    # t4 = threading.Thread(target=network_data, name='Network Poller', daemon=True)
    # t1.start() ; t2.start() ; t3.start() ; t4.start()
    # t1.join() ; t2.join() ; t3.join() ; t4.join()

    '''
    Gather stats over REFRESH_RATE instead of waiting for each one sequentially
    and use the thread pool
    '''
    cpupoll = mainpool.submit(cpu_data_load)
    cpucorepoll = mainpool.submit(cpu_data_core)
    diskpoll = mainpool.submit(disk_data)
    networkpoll = mainpool.submit(network_data)
    try: # block until all threads finish
        _ = cpupoll.result(timeout=timeout_wait[0])
        _ = cpucorepoll.result(timeout=timeout_wait[0])
        _ = diskpoll.result(timeout=timeout_wait[0])
        _ = networkpoll.result(timeout=timeout_wait[0])
    except TimeoutError:
        # relay it to our calling function
        if DEBUG == True:
            print_stderr("• Notice: Worker threads timed out.")
        raise TimeoutError
    except SystemExit:
        return
    except:
        return
    #print(f"DEBUG: polling took {round((time.time() - (data_start + REFRESH_RATE)), 3)} seconds ---")

def update_plot() -> None:
    '''
    Read the last polled data generated by update_data(), update all corresponding elements
    in our plot, then generate an updated plot buffer. This will run as soon as update_data() is started
    so that while the workers spawned by update_data() are sleeping we can focus on generating the plot. 
    This has the effect of the workers being able to monitor the load this thread imposes.
    - thread_id = 0
    '''
    plot_start = time.time()
    # gather system stats
    uptime = f"Uptime: {timedelta_clean(time.monotonic())}"
    if array_valid == True:
        array_use = psutil.disk_usage(ARRAY_PATH)
    else:
        array_use = psutil.disk_usage('/')
    array_total = bytes2human(array_use.total)
    array_used = bytes2human(array_use.used)
    array_str = f"{array_used} / {array_total} ({array_use.percent}%)"
    memory_use = psutil.virtual_memory()
    memory_total = bytes2human(memory_use.total)
    memory_used = bytes2human(memory_use.total - memory_use.available)
    memory_str = f"{memory_used} / {memory_total} ({memory_use.percent}%)"

    # update lines with latest data
    with threading.Lock(): # lock variables just in case
        for plot, lines in enumerate(plot_lines):
            if plot == 1 or plot == 4: # don't plot over our non-graph subplots
                continue
            for index, line in enumerate(lines):
                line.set_ydata(y_data[plot][index])
            # autoscale if not specified
            if 'ylim' not in PLOT_CONFIG[plot].keys():
                ax[plot].relim() # recompute data limits             
                ax[plot].autoscale(enable=True, axis='y') # reenable
                ax[plot].set_ylim(bottom=0) # this leaves y max untouched and sets autoscale off
                ax[plot].autoscale_view(scalex=False) # scale the plot

        # update our heatmap
        heatmap.set_data(np.matrix(cpu_percs_cores))
        # update our barplot
        barplot[0].set_width(array_use.percent)
        barplot[1].set_width(memory_use.percent)
        ''' original setup; this WILL cause a memory leak '''
        # ax[1].pcolormesh([cpu_percs_cores], cmap='hot', vmin=0, vmax=100)
        # ax[4].barh(1, array_use.percent, facecolor='#375e1f')
        # ax[4].barh(2, memory_use.percent, facecolor='#4a2a7a')
        
        # update text in plots with last polled data
        if current_data[1] == None:
            cpu_text.set_text(current_data[0])
        else:
            cpu_text.set_text(f"{current_data[0]} | {current_data[1]}")
        disk_text.set_text(f"{current_data[2]} | {current_data[3]}")
        storage_text.set_text(array_str)
        memory_text.set_text(memory_str)
        network_text.set_text(f"{current_data[4]} | {current_data[5]}")
        uptime_text.set_text(uptime)        
        if DEBUG == True:
            if not current_data[-1]:
                debug_text.set_text("Last render: 0ms")
            else:
                if PROFILE_DISPLAY_RENDER == 0:
                    debug_text.set_text(f"Last plot gen: {round(current_data[-1] * 1000, 1)}ms")
                else:
                    debug_text.set_text(f"Last render: {round(current_data[-1] * 1000, 1)}ms")
            frame_number_text.set_text(f"{samples},{dropped_frames} | {timedelta_clean(time.time()-START_TIME)}")
            
    ''' Draw the plots. This can get really slow; can definitely use blitting (eventually) '''
    canvas = plt.get_current_fig_manager().canvas
    canvas.draw()
    thread_timer(plot_start, 0)

def plot_renderer() -> None:
    '''
    Renders the plot buffer to display. This is usually the most CPU intense thread on faster systems.
    - thread_id = 1 
    '''
    render_start = time.time()
    canvas = plt.get_current_fig_manager().canvas
    # option 1
    image = Image.frombuffer('RGBA', canvas.get_width_height(), canvas.buffer_rgba())
    # option 2 (essentially the same as the above; same performance)
    # image = Image.fromarray(np.asarray(canvas.buffer_rgba()))
    disp.image(image, IMAGE_ROTATION) # this internally calls a numpy calculation
    thread_timer(render_start, 1)

def plot_profiler(samples: int, sample_size: int):
    '''
    Profiles how long it takes to actually render the image on your specific hardware
    then adjusts the thread timeouts so we can set better limits. This runs during the first
    PROFILER_COUNT amount of samples then returns baseline values to be used in further calculations.
    '''
    global time_array
    if samples == 0:
        return
    elif samples > 0 and samples < sample_size:
        time_array[0].append(thread_time[0])
        time_array[1].append(thread_time[1])
    elif samples == sample_size:
        time_array[0].append(thread_time[0])
        time_array[1].append(thread_time[1])
        # generate the stats
        avg_render = np.around(np.average(time_array, axis=1), 4)
        render_sd = np.around(np.std(time_array, axis=1) * 1000, 1)
        render_max = np.around(np.max(time_array, axis=1) * 1000, 1)
        render_min = np.around(np.min(time_array, axis=1) * 1000, 1)
        render_full = np.around((avg_render[0] + avg_render[1]) * 1000, 1)
        # this is our new emperically stat-driven baseline, in seconds
        real_timeout = np.around(((avg_render + (render_sd / 500)) * 2), 4)
        print(f"Profiler stats of {sample_size} samples ({REFRESH_RATE * PROFILER_COUNT}s | \
actual: {round((time.time() - START_TIME) - init_time, 2)}s):")
        print(f"   Plot generation:     avg render: {round(avg_render[0] * 1000, 1)}ms \
| max/min/SD: {render_max[0]}/{render_min[0]}/{render_sd[0]}ms")
        print(f"   Screen render:       avg render: {round(avg_render[1] * 1000, 1)}ms \
| max/min/SD: {render_max[1]}/{render_min[1]}/{render_sd[1]}ms")
        print(f"   Full render average: {render_full}ms ({round((REFERENCE_RENDER_SPEED/render_full) * 100, 1)}% as fast as baseline)")
        del time_array, avg_render, render_sd, render_max, render_min
        return real_timeout
    elif samples > sample_size: # in case we use this past the polling amount
        return
    else:
        return

def main() -> None:
    ''' Loop until Docker shuts down or something breaks. '''
    global samples, dropped_frames, timeout_wait, init_time
    init_gc: int = gc.collect()
    if DEBUG == True:
        print(f"• Initialization cleanup: freed {init_gc} object(s).")
    del init_gc
    init_time = round(time.time() - START_TIME, 3)
    print(f"Setup took {init_time} seconds.")
    refresh_rate_limiter(abs(init_time))
    print(f"--- Monitoring started. Refresh rate: {REFRESH_RATE} second(s) | \
Plot range: {round(REFRESH_RATE * (HIST_SIZE - 1),1)}s ({round(REFRESH_RATE * (HIST_SIZE - 1) / 60, 2)}min) ---")
    # register handler for SIGTERM
    signal.signal(signal.SIGTERM, sigterm_handler)
    update_data() # get initial stats on startup

    current_timeout = timeout_wait 
    ''' thread timeout adjusted per loop, initialized to timeout_wait, (seconds) '''
    baseline_timeout = timeout_wait 
    ''' thread timeout after being set by plot_profiler(), initialized to timeout_wait (seconds) '''
    timeout_adjust = []

    if REFRESH_RATE < 1:
        current_timeout = [1,1]
    if PROFILING == True:
        print("Performance tracing enabled, waiting for stats...")
    if DEBUG == True:
        if PROFILE_DISPLAY_RENDER == 0:
            print("• Display will show plot generation time.")
        elif PROFILE_DISPLAY_RENDER == 1:
            print("• Display will show render thread time.")
        else:
            print("• Display will show full render time.")

    daily_event_timer = int(86400 // REFRESH_RATE) # naive calculation for samples per 24 hours; initial value
    event_timer_resync = int(36000 // REFRESH_RATE) # sub-timer to trigger daily_event_timer recalculation (~10 hours)
    
    while True:
        data_poller = mainpool.submit(update_data)
        plotter = mainpool.submit(update_plot)
        try: # block until all threads finish
            _ = plotter.result(timeout=current_timeout[0])
            # wait for update_plot() to finish, then send the display renderer to the threadpool
            screen_render = mainpool.submit(plot_renderer)
            _ = screen_render.result(timeout=current_timeout[1])
            _ = data_poller.result(timeout=timeout_wait[0]) # this should finish after the above threads are done

        except TimeoutError:
            dropped_frames +=1
            if DEBUG == True:
                print_stderr(f"• Notice: Thread timeout #{dropped_frames}. Skipping next refresh.")
            if (dropped_frames % 10) == 0:
                # bump up baseline timeout values to help reduce timeouts
                baseline_timeout = [round(baseline_timeout[0] * 1.25, 4), round(baseline_timeout[1] * 1.25, 4)]
                timeout_wait = [round(timeout_wait[0] * 1.25, 4), round(timeout_wait[1] * 1.25, 4)]
                print_stderr(f"Warning: Numerous timeouts ({dropped_frames}) detected. Adjusting internal runtime to compensate.")
                if DEBUG == True:
                    print(f"• Updated baseline timeouts: {round(baseline_timeout[0] * 1000, 4)}ms, {round(baseline_timeout[1] * 1000, 4)}ms")
            time.sleep(REFRESH_RATE)
            if dropped_frames > 40: # bail out
                print_stderr("ERROR: Maximum time outs exceeded.")
                it_broke(1)
            continue

        except SystemExit:
            break
        except:
            it_broke(2)
        finally:
            if PROFILE_DISPLAY_RENDER != 0 and PROFILE_DISPLAY_RENDER != 1:
                current_data[-1] = np.sum(thread_time)
        
        if PROFILING == True: # adjusts both baseline_timeout and current_timeout when plot_profiler() is done
            if samples > PROFILER_COUNT:
                # dynamically adjust timeout based on CPU load
                timeout_adjust = np.array(baseline_timeout) * (y_data[0][0][-1] / CPU_AFFECT_RATIO)
                current_timeout = np.around(baseline_timeout + timeout_adjust, 3)
            elif samples == 0:
                plot_profiler(samples, PROFILER_COUNT)
            elif samples < PROFILER_COUNT:
                plot_profiler(samples, PROFILER_COUNT)
            elif samples == PROFILER_COUNT:
                baseline_timeout = plot_profiler(samples, PROFILER_COUNT)
                current_memory_usage = psutil.Process().memory_info().rss
                this_process_cpu = this_process.cpu_percent(interval=None)
                print(f"   CPU & memory usage:  {this_process_cpu}% \
({round(this_process_cpu / CORE_COUNT, 3)}% total CPU) | {bytes2human(current_memory_usage)}")
                if DEBUG == True:
                    print(f"• Got new baseline timeouts: \
{round(baseline_timeout[0] * 1000, 4)}ms, {round(baseline_timeout[1] * 1000, 4)}ms (was {timeout_wait[0]}s)")
            else: 
                pass
                
        samples +=1
        
        if (samples % event_timer_resync) == 0:
            daily_event_timer = int(86400 // (((time.time() - START_TIME) - init_time) / samples))
            gc.collect()
        if (samples % daily_event_timer) == 0:
            gc.collect()
            sample_actual_time = round(((time.time() - START_TIME) - init_time) * 1000 / samples, 3) # ms
            current_memory_usage = psutil.Process().memory_info().rss
            this_process_cpu = this_process.cpu_percent(interval=None)
            print(f"\nℹ️ Periodic stat update @ {samples} samples \
({timedelta_clean(time.time()-START_TIME)}):\n├ {dropped_frames} dropped sample(s) | \
{sample_actual_time}ms avg time/sample\
\n└ Avg CPU: {this_process_cpu}% ({round(this_process_cpu / CORE_COUNT, 3)}% total) | \
Current memory use: {bytes2human(current_memory_usage)}")

# finally enter main loop
if __name__ == '__main__':
    main()