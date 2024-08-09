#%%
# UNRAID STATUS SCREEN
'''
Written to run in Visual Studio Code on Windows with output to Jupyter.
Primarily aimed at layout and logic testing, not fit to run on actual hardware.
'''
import time
START_TIME: float = round(time.time(), 3) # start timing this script
import datetime
STARTED_DATE: datetime = datetime.datetime.now()
import signal
import sys
import gc
import socket
import os
from collections import deque
from PIL import Image
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotx
import psutil
import threading
import concurrent.futures as CF
import yaml

CURRENT_DIR = os.getcwd()
VERSION = "v.3.8 VSCode --- 2024-08"
'''
Changelog (VSCode Edition):
- v.3.8 (2024-08)
    - User configuration is no longer hardcoded into this script and is now an external file (yaml)
        - docstrings have also been removed due to this change (not the VSCode version)
    - Changelog now exists in a separate file, no longer clogging up this script (not the VSCode version)
- v.3.7 (2024-06)
    - The VSCode and actual version of this script have diverged significantly, thus are now two separate "forks"
        - The code has matured enough to allow this
    - From here on out this script will only be for logic and layout testing and changelog will be updated less
- v.3.6 (2024-05-05)
    - v.3.6.3 (2024-05-26)
        - Autoscaling now sets y minimum to 0
        - NEW: Network plot checks NIC status and will display on screen if down
        - NEW: Parse hostname and local IP and display it on screen
        - on-screen debug text tweaks
        - date stamps when exiting
    - v.3.6.2 (2024-05-14)
        - invoke garbage collection tweaks (probably not necessary)
        - remove redundant axis labelling routine and re-utilize the PLOT_CONFIG setting (includes validation as well)
        - slight change to plot style defaults to match most common process managers (eg. Windows Task Manager)
        - small tweaks to plot text and setting the network plot receive as line 0 (was unchanged from v.1.x)
        - NEW: render frame number into plot if debug enabled
        - cleaner time outputs
    - v.3.6.1 (2024-05-06)
        - small tweaks and improvements (envvars and settings parsing, init.sh tweaks again)
    - display renderer now gets sent to a separate thread
        - add profiling switch to measure either plot generation or display rendering
        - thread timeouts now will consider either the plot or render thread
        - add associated logic changes
    - NEW: init.sh now has a profiling option that will summon scalene to profile this script
    - Set minimum refresh rate and do some refactoring with significant code reorganization
    - NEW: dropped frame count tracking if render threads timeout
    - verbose output now has a "•" preceeding the message for clarity
    - add barplot colors as part of user config
- v.3.5 (2024-04-30)
    - v.3.5.1 (2024-05-03)
        - NEW: Render thread timeouts don't kill this script but will just pause the loop for a bit
        - Enhance debug outputs and use stderr for some
        - More init.sh logging tweaks (no more progress bar)
        - Attempt some small processing optimizations
    - NEW: Add network interface setting due to Unraid having interfaces with duplicate data and showing incorrect info
    - Better byte size parsing and consistent use of IEC binary multipliers
    - More robust and elegant handling of misconfigured settings in user config
    - slight init.sh tweaks
    - Avoid edge case of counters overflowing with long-lived systems (via psutil flags)
- v.3.4 (2024-03-12)
    - v.3.4.1 (2024-03-14)
        - NEW: check and parse Unraid version
        - fix weird Ftdi output during check
        - fix error handler catching SIGTERM
        - fix edge case where disk activity can be negative
        - add some type hints
        - NEW: rudimentary progress bar in init.sh file
    - Updated Docker config to no longer require being privileged
        - Docker image will now be able to automatically find the FT232H board
    - Overhaul dependency check output in the init.sh script
        - only logs errors now (less logging junk)
        - NEW: now checks if this is a first run
    - NEW: nice logo in logs
    - better adherence to the Google Python Style Guide
- v.3.3 (2024-03-11)
    - v.3.3.2 (2024-03-12)
        - updated to use modern matplotlib method for image rendering
        - NEW: logic added in case there's no splash screen image found
    - v.3.3.1
        - NEW: thread timeout for rendering now considers CPU load due to low process priority (fancy?)
    - NEW: added profiling logic to adjust plot rendering timeout based on hardware performance
        - just in case there's a memory leak but that shouldn't happen, right?
    - lowered process priority to near-minimum via Docker (remember, this is just a system resource monitor)
    - moved user-config section to the beginning of script
- v.3.2 (2024-03-10)
    - FIXED: Memory leak due to heatmap and bar graph introduced in v.1.x
    - some more code refactoring
- v.3.1 (2024-03-09)
    - optimizations for string manipulation, improving per-loop times (extra ~10%)
    - more accurate timing info and new sample stat when SIGTERM'd
    - revised debug output on rendered image
    - NEW: verbose changelog
- v.3.0 (2024-03-09)
    - NEW: switch to using ThreadPoolExecutor for better performance (almost 2x speed up)
    - improved docstrings and code readability
    - NEW: better exception handling, settings validation, and timeout checks
    - refactoring to make it easier to switch between debugging in VSCode in Windows and actual hardware (this was for me)
- v.2.1 (2024-03-07)
    - NEW: add debug flags and print stats to screen and log
- v.2.0 (2024-03-06)
    - finalize layout
    - NEW: figure out multithreading and refactor around this
- v.1.x (2024-03-02)
    - learn how to actually code in Python
    - figure out how to use matplotlib correctly
    - determine what resources to monitor
    - initial layout changes for plot
    - how do I VSCode
- v.0.x (2024-02)
    - get this script to actually run in a Docker environment
    - modify the script this is based on for my use
    - NEW: graceful exit for when Docker exits (SIGTERM handler here and in init.sh)
    - NEW: splash screen
'''

print(f"Version: {VERSION}")
print(f"Script started: {STARTED_DATE.replace(microsecond=0)}")

# Start our thread pool before anything
mainpool = CF.ThreadPoolExecutor(max_workers=6)
'''
We expect to only run the following:
- update_data() ← one thread
    - 4 workers
- update_plot() ← another thread
- Σ = 6
'''

#==| User Config |========================================================
LOOPCOUNT: int = 61
''' How many loops to run this script in VSCode '''
DEBUG: bool = True 
'''
If True, render the amount of time it took to render the last frame in the plot itself.
Also outputs more info in the log. Personally, I'd leave this set to True.
'''
REFRESH_RATE: int = 0.5
'''
(in seconds)
Don't set REFRESH_RATE too low - we don't want to waste too much CPU.
We need to allow update_plot() to finish while update_data() is still running
to get a more accurate represenation of CPU usage. The rendering portion
is the most CPU intensive action in this script and we should let it finish
while the workers in update_plot() are sleeping.
Testing has shown it takes roughly 100 - 300 milliseconds to render
the entire plot and send it to the display; if REFRESH_RATE is too low then
we are limited to how fast update_plot() can complete.
    REFRESH_RATE should be >= 0.5
'''
PLOT_SIZE: float = 1.25
'''
(in minutes)
How long to keep graph history.
'''
# HIST_SIZE: int = 101 
# ''' how long to keep data; total time = REFRESH_RATE * (HIST_SIZE - 1) '''
ARRAY_PATH: str = "/rootfs/mnt/user0"
''' /rootfs/mnt/user0 is our Unraid array inside this Docker '''
CPU_TEMP_SENSOR: str = "k10temp"
'''
Check the output of psutil.sensors_temperatures() on
your system then update with the correct sensor.
'''
NETWORK_INTERFACE: str = "bond0"
'''
This is the network interface you want to monitor in Unraid.
Not setting this correctly will display incorrect values since
Unraid has multiple interfaces that show duplicate data.
Use the interface names listed in the Unraid GUI.
'''
SPLASH_SCREEN: str = f"{CURRENT_DIR}/background.bmp"
''' Our splash screen when loading or exiting this script '''
PLOT_CONFIG: tuple = (
    #--------------------
    # PLOT 1 (upper plot)
    #--------------------
    {
    'title' : 'C P U',
    'ylim' : (0, 100),
    'line_config' : (
        {'width': 1, 'alpha': 0.6, 'style':'-'}, # CPU
        {'width': 1, 'alpha': 0.6, 'style':'--'}  # Temps
        )
    },
    #--------------------
    # PLOT 2 (CPU core heatmap)
    #--------------------
    {
    'title' : 'C o r e   H e a t m a p',
    #'ylim' : (0, 100),
    'line_config' : (
        {}, # need this just so we can plot
        )
    },
    #--------------------
    # PLOT 3 (middle plot)
    #--------------------
    {
    'title' : 'D i s k s',
    # 'ylim' : (0, 1000),
    'line_config' : (
        {'width': 1, 'alpha': 0.6, 'style':'-'}, # read
        {'width': 1, 'alpha': 0.6, 'style':'--'}, # write
        )
    },
    #--------------------
    # PLOT 4 (bottom plot)
    #--------------------
    {
    'title' : 'N e t w o r k',
    #'ylim' : (0, 1000),
    'line_config' : (
        {'width': 1, 'alpha': 0.6, 'style':'-'}, # sent
        {'width': 1, 'alpha': 0.6, 'style':'--'}, # received
        )
    },
    #--------------------
    # PLOT 5 (Resource usage)
    #--------------------
    {
    #'title' : 'Resources',
    'line_config' : (
        {} # a bar graph
    )
    }
)
''' 
Valid plot properties are:
    - title = name your subplot
    - ylim (min, max) = y-axis limits
        (NB: if ylim is not set, matplotlib will automatically scale for us)
- for lines:
    color, width, style, alpha
'''

BARPLOT_COLORS: list[str] = ['#375e1f','#4a2a7a']
''' Colors for our bar chart, in hexadecimal as a string. '''

#==| End User Config |========================================================

#==| Program setup |==========================================================
#=============================================================================

def print_stderr(*a) -> None:
    global error_count
    print(*a, file = sys.stderr)
    error_count += 1

def check_settings() -> None:
    '''
    Checks if the settings are correct and sets flags or reverts variables to safe fallbacks
    if they're incorrect or invalid.
    '''
    global cpu_temp_available, network_interface_set, array_valid, REFRESH_RATE
    if REFRESH_RATE < 0.5:
        print_stderr("Warning: Refresh rate set too low. Refresh rate will be set to 0.5 seconds.")
        REFRESH_RATE = 0.5
#    if DEBUG_VSCODE_WIN == True:
#        print("Settings are valid.") # always :)
#    else:
    if not hasattr(psutil, "sensors_temperatures"):
        print_stderr("Notice: Temperature readouts not supported on this platform.")
        cpu_temp_available = False
    else:
        temps_test = psutil.sensors_temperatures()
        if not temps_test:
            print_stderr("Warning: No temperatures found on this system.")
            cpu_temp_available = False
        del temps_test
    if cpu_temp_available == True:
        try:
            test1 = psutil.sensors_temperatures()[CPU_TEMP_SENSOR][0].current
            del test1
        except:
            print_stderr(f"Warning: CPU temp {CPU_TEMP_SENSOR} not found.")
            cpu_temp_available = False
    try:
        test2 = psutil.disk_usage(ARRAY_PATH)
        del test2
    except:
        print_stderr(f"Warning: Array path {ARRAY_PATH} does not exist. Defaulting to '/'.")
        array_valid = False
    try:
        test3 = psutil.net_io_counters(pernic=True)[NETWORK_INTERFACE]
        del test3
    except:
        print_stderr(f"Warning: Network interface \'{NETWORK_INTERFACE}\' not found. Network readouts may be incorrect.")
        nic_stats = psutil.net_io_counters(pernic=True)
        nic_names = list(nic_stats.keys())
        print("Notice:\tFor your reference, the following network interfaces were found:")
        for name in nic_names:
            print(f"{name}   ", end='')
        print()
        del nic_stats, nic_names
        network_interface_set = False

    print("Settings verification complete.")
    if DEBUG == True:
        if cpu_temp_available == True:
            print(f"• CPU temp sensor: {CPU_TEMP_SENSOR} on a CPU with {CORE_COUNT} logical core(s)")
        else:
            print(f"• CPU has {CORE_COUNT} logical core(s)")
        if array_valid == True:
            print(f"• Array path: {ARRAY_PATH}")
        if network_interface_set == True:
            print(f"• Network interface: {NETWORK_INTERFACE}")

    # This whole script is structured around 5 entries. If you change this yourself, have fun.
    if len(PLOT_CONFIG) != 5:
        print_stderr(f"ERROR: There must be 5 entries in the PLOT_CONFIG setting. Only {len(PLOT_CONFIG)} were found.")
        raise AssertionError("Insufficient entries in configuration.")

def it_broke(type: int) -> None:
    ''' Our error handler, lmao '''
    mainpool.shutdown(wait=False, cancel_futures=True)
    if type == 1:
        end_time = round(time.time() - START_TIME, 3)
        print(f"- Script ran for {timedelta_clean(end_time)} and sampled {samples} times. {error_count} error(s) occured.")
        raise ResourceWarning("Script terminated due to potential resource exhaustion.")
    else:
        raise GeneratorExit("Script terminated.")
    
def bytes2human(n, format="%(value).1f%(symbol)s") -> str:
    """
    Pulled from _common.py of psutil with the symbols edited to better match this script.

    >>> bytes2human(10000)
    '9.8KiB'
    >>> bytes2human(100001221)
    '95.4MiB'
    """
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
        s.connect(('1.1.1.1', 1))
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

# Initialize a sample counter
samples: int = 0
error_count: int = 0

# Flags for checking user config
cpu_temp_available: bool = True
network_interface_set: bool = True
array_valid: bool = True

# reduce traceback fluff
sys.tracebacklimit = 1
gc.set_threshold(10000, 50, 20)

#==| Environment setup |======================================================
#=============================================================================

# Get hostname and IP address (this should be static since this is Unraid)
UNRAID_HOSTNAME = socket.gethostname()
UNRAID_IP = get_ip()

print(f"Hey there, {UNRAID_HOSTNAME} @ {UNRAID_IP}!")

if DEBUG == True:
    print("• Verbose setting enabled. Verbose data will be prefixed with • in the logs")
    print("  and additional data rendered on-screen.")
    print(f"• We're using: {sys.executable}")
    print(f"• We're running in: {CURRENT_DIR}")
    #print_stderr("• ℹ️ Testing a stderr message on this line.")

UNRAID_VER_FILE = '/rootfs/etc/unraid-version'
try:
    with open(UNRAID_VER_FILE) as unraid_str:
        # String format: 'version="x.x.x"\n'
        input_list = unraid_str.readlines()
    input_as_str = str(input_list[0])
    parse_result = input_as_str.split('"')
    UNRAID_VERSION: str = parse_result[1]
    if DEBUG == True:
        print(f"We're running in Unraid version {UNRAID_VERSION}")
    del input_list, input_as_str, parse_result, UNRAID_VER_FILE
except:
    print_stderr("Warning: are we running in UNRAID?")
    UNRAID_VERSION: str = "Unknown"

# Load our settings file
settings_file = f"{CURRENT_DIR}/settings.yaml"
try:
    with open(settings_file, mode="rb") as file:
        settings_loaded = yaml.safe_load(file)
        print(f"Loaded settings file \'{settings_file}\'")
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
        print_stderr("Unable to parse settings file successfully.")
    finally:
        del settings_loaded
except:
    print_stderr(f"Unable to load settings file ({settings_file}), using default settings.")


DEBUG_VSCODE_WIN: bool = True 
'''
I debugged this in Windows VSCode lmao.
Don't forget to set this to False when running on actual hardware!
'''
# Get us our core count
CORE_COUNT: int = psutil.cpu_count()

# Important; changes some variables if necessary before their first use
check_settings()

# convert from time to plot size
HIST_SIZE = int((PLOT_SIZE * 60) // REFRESH_RATE) + 1

if DEBUG == True:
    print(f"• Using matplotlib {matplotlib.__version__}, {matplotlib.get_backend()} backend")
    print(f"• Using psutil version {psutil.version_info}")

if DEBUG_VSCODE_WIN == True:
    TIMEOUT_WAIT: float = REFRESH_RATE * 40 # raise it for testing
    ARRAY_PATH = 'C:\\'
    array_valid = True
    class disp: # substitute display properties
        width = 240
        height = 320
    def sigterm_handler(): 
        pass
else:
    TIMEOUT_WAIT: float = REFRESH_RATE + 0.25
    matplotlib.use('Agg', force=True)

PROFILING: bool = True
''' Enable or disable the thread timeout profiler, HIGHLY recommended to be left as True '''
if PROFILING == True:
    PROFILER_COUNT: int = 50
    ''' 
    How many samples for our profiler. Don't set too high,
    we need to get our stats for our thread timeouts sooner than later.
    The profiler will run PROFILER_COUNT * REFRESH_RATE seconds.
    '''
time_array: list[float] = []

PROFILE_DISPLAY_RENDER: bool = False
''' 
- True = measure wall time to render plot buffer to display
- False = measure wall time to generate plot
'''
# Get info of our current process
this_process = psutil.Process()
this_process_cpu = this_process.cpu_percent(interval=None)
if DEBUG == True:
    try:
        print(f"• Running on CPU core {this_process.cpu_num()} with {this_process.num_threads()} threads")
    except:
        print(f"• Running with {this_process.num_threads()} threads")

# Setup array of strings we can put latest sensor info into
current_data: list = []
for plot in PLOT_CONFIG: # this will make n+1 indices, perfect for our debug
    for _ in plot['line_config']:
        current_data.append(None)
current_data[-1] = "" # utilize that last index
cpu_percs_cores: list[float] = [] # setup array for CPU core utilization

#==| matplotlib setup |=======================================================
#=============================================================================

# Setup X data storage
x_time: list[int] = [x * REFRESH_RATE for x in range(HIST_SIZE)]
x_time.reverse()

# Setup Y data storage
y_data = [ [deque([None] * HIST_SIZE, maxlen=HIST_SIZE) for _ in plot['line_config']]
           for plot in PLOT_CONFIG
         ]

# Setup plot figure
plt.style.use(matplotx.styles.ayu['dark']) # Ayumu Uehara?
fig, ax = plt.subplots(5, 1, figsize=(disp.width / 100, disp.height / 100),
                       gridspec_kw={'height_ratios': [4, 1, 4, 4, 2]})
fig.subplots_adjust(0.0,0.12,1,0.98) # adjust extent of margins (left, bottom, right, top)
plt.rcParams.update({'font.size': 7})
plt.ioff
plt.style.use('fast')

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
# history_length_text = ax[0].annotate(f"{round(REFRESH_RATE * (HIST_SIZE - 1),0)}s",
#                                      [0.01, -0.05], xycoords='axes fraction', 
#                                      verticalalignment='top',
#                                      horizontalalignment='left',
#                                      family='monospace', fontsize=5, alpha=0.1)
uptime_text = ax[2].annotate('', [0.5, 1.1], xycoords='axes fraction', 
                             verticalalignment='top',
                             horizontalalignment='center',
                             fontvariant='small-caps')
disk_text = ax[2].annotate('', [0.5, 0.3], xycoords='axes fraction', 
                           verticalalignment='center',
                           horizontalalignment='center',
                           fontweight='black',
                           bbox=bbox_setting)
# disk_scale_text = ax[2].annotate("MiB/s", [0.01, -0.05], xycoords='axes fraction', 
#                                      verticalalignment='top',
#                                      horizontalalignment='left',
#                                      family='monospace', fontsize=5, alpha=0.1)
network_text = ax[3].annotate('', [0.5, 0.3], xycoords='axes fraction',
                              verticalalignment='center',
                              horizontalalignment='center',
                              fontweight='black',
                              bbox=bbox_setting)
# network_scale_text = ax[3].annotate("MiB/s",
#                                      [0.01, -0.05], xycoords='axes fraction', 
#                                      verticalalignment='top',
#                                      horizontalalignment='left',
#                                      family='monospace', fontsize=5, alpha=0.1)
memory_text = ax[4].annotate('', [0.5, 0.725], xycoords='axes fraction', 
                             verticalalignment='center',
                             horizontalalignment='center',
                             fontweight='black')
storage_text = ax[4].annotate('', [0.5, 0.225], xycoords='axes fraction', 
                              verticalalignment='center',
                              horizontalalignment='center',
                              fontweight='black')


def annotate_axes(ax, text, fontsize: int = 10) -> None:
    ''' Puts text in the center of the plots '''
    ax.text(0.5, 0.5, text, transform=ax.transAxes,
            ha='center', va='center', fontsize=fontsize, 
            fontstyle='italic', fontweight='normal', 
            alpha=0.4)

try:
    # Setup plot axis
    for plot, a in enumerate(ax):
        # custom settings
        if 'title' in PLOT_CONFIG[plot]:
            annotate_axes(ax[plot],PLOT_CONFIG[plot]['title'])
            # a.set_title(PLOT_CONFIG[plot]['title'], position=(0.5, 0.8))
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
    plot_lines = []
    for plot, config in enumerate(PLOT_CONFIG):
        lines = []
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
except:
    raise Exception("Failed to create plot. This may be caused by incorrect values in \"PLOT_CONFIG\"")
if DEBUG == True:
    print(f"• Plot length: {HIST_SIZE} samples")

# Make plot 1 a heatmap
heatmap = ax[1].imshow(np.matrix(np.zeros(CORE_COUNT)),
                       cmap='gist_heat', vmin=0, vmax=100, aspect='auto', alpha=0.5)

# Make plot 4 a horizontal bar graph
barplot = ax[4].barh([1, 2], [0, 0], color=BARPLOT_COLORS) 
ax[4].set_xlim(right=100) 
ax[4].set_yticks([1, 2],["Array", "Memory"])

# Grab an image of the background, maybe for when we decide to use animations for this
# initial_render = [fig.canvas.copy_from_bbox(ax.bbox) for ax in ax]

#==| Main threads definitons |================================================
#=============================================================================

def update_data() -> None:
    '''
    Generates data for our plot.
    Sends workers to run in our thread pool, waits for them to finish,
    then finishes. The workers sleep for REFRESH_RATE then append to y_data
    and current_data[].
    General form is:
           y_data[plot][line].append(new_data_point)
    Fun fact: this whole routine takes approximately 30 - 70 milliseconds to
    finish, ignorning the blocking done during the REFRESH_RATE interval.
    '''

    #data_start = round(time.time(), 3) # to check how long this function takes
    def cpu_data_load() -> None:
        cpu_percs = psutil.cpu_percent(interval=REFRESH_RATE, percpu=False)
        y_data[0][0].append(cpu_percs)
        cpu_freq = psutil.cpu_freq()
        cpu_f_ghz = round(cpu_freq.current / 1000, 2)
        current_data[0] = f"{cpu_percs}% {cpu_f_ghz} GHz"
        if DEBUG_VSCODE_WIN == True or cpu_temp_available == False:
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
        #current_data[2] = f"R:{round(iospeed_read / 1e6, 2)} MB/s" # old way
        current_data[2] = f"R:{bytes2human(iospeed_read)}/s"
        current_data[3] = f"W:{bytes2human(iospeed_write)}/s"

    def network_data() -> None:
        # network speed, in MiB/s
        nic_isup: bool = True
        if DEBUG_VSCODE_WIN == True or network_interface_set == False:
            net_start = psutil.net_io_counters()
            time.sleep(REFRESH_RATE)
            net_finish = psutil.net_io_counters()
        else:
            nic_isup = psutil.net_if_stats[NETWORK_INTERFACE].isup
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
        _ = cpupoll.result(timeout=TIMEOUT_WAIT)
        _ = cpucorepoll.result(timeout=TIMEOUT_WAIT)
        _ = diskpoll.result(timeout=TIMEOUT_WAIT)
        _ = networkpoll.result(timeout=TIMEOUT_WAIT)
    except TimeoutError: # this shouldn't happen but just in case
        print_stderr("ERROR: Worker threads are taking too long!")
        it_broke(1)
    except SystemExit:
        return
    except:
        it_broke(2)
    #print(f"DEBUG: polling took {round((time.time() - (data_start + REFRESH_RATE)), 3)} seconds ---")

def update_plot() -> None:
    '''
    Read the last polled data generated by update_data(). This will run as soon as update_data() is run
    so that while the workers in update_data() are sleeping we can focus on generating the plot. 
    '''
    plot_start = round(time.time(), 6)
    global current_data
    # gather system stats
    uptime = f"Uptime: {timedelta_clean(time.monotonic())}"
    # uptime = f"Uptime: {datetime.timedelta(seconds=round(time.monotonic()))}"
    if array_valid == True:
        array_use = psutil.disk_usage(ARRAY_PATH)
    else:
        array_use = psutil.disk_usage('/')
    array_total = bytes2human(array_use.total) ; array_used = bytes2human(array_use.used)
    array_str = f"{array_used} / {array_total} ({array_use.percent}%)"
    memory_use = psutil.virtual_memory()
    memory_total = bytes2human(memory_use.total) ; memory_used = bytes2human(memory_use.used)
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
                debug_text.set_text(f"Last render: 0ms")
            else:
                debug_text.set_text(f"Last render: {round(current_data[-1] * 1000, 1)}ms")
            frame_number_text.set_text(f"{samples} | {timedelta_clean(time.time()-START_TIME)}")

    # draw the plots
    canvas = plt.get_current_fig_manager().canvas
    canvas.draw()

    # record how long this function took
    current_data[-1] = round(time.time() - plot_start, 4)
    #print(f"DEBUG: generated in {current_data[-1]} seconds")

def plot_renderer() -> None: # this will never execute in VSCode
    ''' Renders the plot buffer to display. This is the most CPU intense thread. '''
    global current_data
    render_start = time.time()
    canvas = plt.get_current_fig_manager().canvas
    image = Image.frombuffer('RGBA', canvas.get_width_height(), canvas.buffer_rgba())
    disp.image(image, 0)
    if PROFILE_DISPLAY_RENDER == True:
        current_data[-1] = round(time.time() - render_start, 4)

def plot_profiler(samples: int, sample_size: int) -> float:
    '''
    Profiles how long it takes to actually render the image on your specific hardware
    then adjusts the thread timeout so we can set better limits. This runs during the first
    PROFILER_COUNT amount of samples then returns a baseline value to be used in further calculations.
    This will use render times depending on PROFILE_DISPLAY_RENDER.
    '''
    global time_array
    if samples == 0:
        time_array = []
    elif samples > 0 and samples < sample_size:
        time_array.append(current_data[-1])
    elif samples == sample_size:
        time_array.append(current_data[-1])
        avg_render = round(np.average(time_array), 4)
        render_sd = round(np.std(time_array) * 1000, 1)
        render_max = round(np.max(time_array) * 1000, 1)
        render_min = round(np.min(time_array) * 1000, 1)
        real_timeout = round((avg_render * 2), 4) # this is our new stat-driven baseline
        print(f"Profiler stats: {sample_size} samples ({REFRESH_RATE * PROFILER_COUNT}s) | avg render: \
{round(avg_render * 1000, 1)}ms | max/min/SD: {render_max}/{render_min}/{render_sd}ms")
        del time_array, avg_render, render_sd, render_max, render_min
        return real_timeout
    elif samples > sample_size: # in case we use this past the polling amount
        real_timeout = TIMEOUT_WAIT
        return real_timeout
    else:
        print("Profiler failed to determine execution time. Non-critial error.")

def main() -> None:
    '''Loop until Docker shuts down or something breaks.'''
    print(f"DEBUG: Garbage collector: {gc.get_count()} | Collected {gc.collect()} objects.")
    init_time = round(time.time() - START_TIME, 3)
    print(f"Setup took {init_time} seconds.")
    print(f"--- Monitoring started. Refresh rate: {REFRESH_RATE} second(s) | \
Plot range: {round(REFRESH_RATE * (HIST_SIZE - 1),1)}s ({round(REFRESH_RATE * (HIST_SIZE - 1) / 60, 2)}min) ---")
    # register handler for SIGTERM
    if DEBUG_VSCODE_WIN == False:
        signal.signal(signal.SIGTERM, sigterm_handler)
    if PROFILING == True:
        print("Performance tracing enabled, waiting for initial stats...")
    update_data() # get initial stats on startup
    global samples
    current_timeout: float = TIMEOUT_WAIT
    baseline_timeout: float = TIMEOUT_WAIT
    timeout_adjust: float = 0
    if REFRESH_RATE < 1:
        current_timeout = 1
    sample_tester = round(30/REFRESH_RATE, 0)
    # while True:
    i = 0
    print(f"DEBUG:\tLooping {LOOPCOUNT} times, please wait.")
    while i < LOOPCOUNT:
        ''' old way of doing threads '''
        # t1 = threading.Thread(target=update_data, daemon=True) ; t1.name = 'Data Poller'
        # t2 = threading.Thread(target=update_plot,daemon=True); t2.name = 'Plotter'
        # t1.start() ; t2.start()
        # t2.join() ; t1.join()
        data_poller = mainpool.submit(update_data)
        plotter = mainpool.submit(update_plot)
        try: # block until threads finish
            if PROFILE_DISPLAY_RENDER == False:
                _ = plotter.result(timeout=current_timeout)
            else:
                _ = plotter.result(timeout=baseline_timeout)
            # wait for update_plot() to finish, then send the display renderer to the threadpool
            if DEBUG_VSCODE_WIN == False:
                screen_render = mainpool.submit(plot_renderer)
                if PROFILE_DISPLAY_RENDER == True:
                    _ = screen_render.result(timeout=current_timeout)
                else:
                    _ = screen_render.result(timeout=baseline_timeout)
            _ = data_poller.result(timeout=TIMEOUT_WAIT) # this should finish after the above threads are done
            # print(f"DEBUG - Updated timeout: {current_timeout}s") # for debugging the profiler        
        except TimeoutError:
            print_stderr(f"Warning: Render thread timing out. Pausing next refresh for {REFRESH_RATE * 4} seconds.")
            time.sleep(REFRESH_RATE * 4)
            continue
            #it_broke(1)
        except SystemExit:
            break
        except:
            it_broke(2)

        if PROFILING == True: 
            if samples == 0:
                plot_profiler(samples, PROFILER_COUNT)
            elif samples < PROFILER_COUNT:
                plot_profiler(samples, PROFILER_COUNT)
            elif samples == PROFILER_COUNT:
                baseline_timeout = plot_profiler(samples, PROFILER_COUNT)
                current_timeout = baseline_timeout
                print(f"DEBUG:\tTimeout adjusted to {baseline_timeout}s")
                DAILY_EVENT_TIMER = int(86400 // (((time.time() - START_TIME) - init_time) / samples))
                print(f"• Estimated samples per day: {DAILY_EVENT_TIMER}")
            else:
                # dynamically adjust timeout based on CPU load
                timeout_adjust = (baseline_timeout * (y_data[0][0][-1] / 10))
                current_timeout = round(baseline_timeout + timeout_adjust, 3)
                                            
        samples +=1
        i += 1
        if (samples % sample_tester) == 0:
            gc.collect()
            sample_actual_time = round(((time.time() - START_TIME)) * 1000 / samples, 4) # ms
            current_memory_usage = psutil.Process().memory_info().rss
            this_process_cpu = this_process.cpu_percent(interval=None)
            if DEBUG == True:
                print(f"\nℹ️ Periodic stat update @ {samples} samples \
({timedelta_clean(time.time()-START_TIME)}):\n└ {error_count} dropped sample(s) | \
{sample_actual_time}ms avg time/sample\
\n└ Avg CPU: {this_process_cpu}% ({round(this_process_cpu / CORE_COUNT, 3)}% total) | \
Current memory use: {bytes2human(current_memory_usage)}")
    mainpool.shutdown(wait=False, cancel_futures=True)
    end_time = round(time.time() - START_TIME, 3)
    print(f"- ({datetime.datetime.now()}) Script ran for {timedelta_clean(end_time)}, Total samples: {samples}, {error_count} error(s).")
    print("Done.")

# finally enter main loop
if __name__ == '__main__':
    main()

# %%
