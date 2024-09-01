<!-- Title -->
<div align="center">
    <a href="https://github.com/WeegeeNumbuh1/UNRAID_status-screen">
    <img src="Reference Images/Logo.png" alt="Logo" width="240" height="240">
    </a>
    <h1 align="center">UNRAID Status Screen</h1>
</div>
<!-- end title section -->

An UNRAID system monitoring screen script, powered by Python, [matplotlib](https://matplotlib.org/), and [psutil](https://github.com/giampaolo/psutil).
Designed to run completely in Docker, but can also be run elsewhere.
Probably using matplotlib in ways it wasn't designed for, lmao.

Based on [scripts from Adafruit](https://github.com/adafruit/Adafruit_Learning_System_Guides/tree/main/TFT_Sidekick_With_FT232H) and going overboard with the concept.

## About
This is a personal project that was meant for my personal NAS built inside a [CyberPower UPS](https://www.cyberpowersystems.com/product/ups/battery-backup/lx1500g/).
<br />
The screen (an [ILI9341](http://www.lcdwiki.com/2.8inch_SPI_Module_ILI9341_SKU:MSP2807)) is driven by an [FT232H](https://www.adafruit.com/product/2264) board with all the processing done fully with Python living inside a Docker container.

The project has undergone significant changes that have not been tracked via `git` but the end-goal has been making the main script highly fault-tolerant and passably performant under the constraints of a high-level language interacting with low-level hardware.

> [!NOTE]
> This project additionally is the author's first foray into Python programming; prior to this project I did not have any Python experience whatsoever.
With that in mind, there is potentially unrealized optimizations that can be done, but alas, as this project stands, it should work *good enough*.

### What it looks like:
<div align="center">
    <img src="Reference Images/irl_example.gif" alt="what it looks like">
    </a>
    <br />
    <i>neat!</i>
</div>

## Features
- Fully Python based
- Monitors the following:
    - Overall CPU load
    - CPU temp (automatically finds correct temp sensor)
    - CPU load per core (plots as a heatmap)
    - Current CPU frequency (not graphed)
    - System-wide disk activity
    - Network activity
        - NIC status (will warn if it goes down)
    - Memory usage
    - Array usage
- Small footprint: uses less than 1% CPU on most systems and runs at low-priority
- Adapts to your hardware speed and current CPU load
- Useful verbose logging and stats (user-selectable)
- "Run and done" approach
    - Run the `init.sh` file and it does the rest for you: setup, dependency updates, and more
- Fault-tolerant with clear log output on what went wrong
    - Includes numerous fallbacks for incorrect settings
- Designed to run fully inside a Docker container but can also be run outside of an UNRAID context as well
- Looks neat imho 👍

## Hardware Setup and Wiring
Assuming you actually want to physically replicate this yourself, wire up the components as follows:
<div align="center">
    
| ILI9341 | FT232 |
| --- | --- |
| VCC | 5V |
| GND | GND |
| CS | C0 |
| RESET | C2 |
| DC | C1 |
| MOSI | D1 |
| SLK | D0 |
| LED | 3V |
| MISO | D2 |
    
</div>
Once cobbled together, connect the FT232 board to an available USB port or header on your computer.

## Software Setup
### Prerequisites
- Python 3.7 or newer
- A working internet connection
- Your preferred flavor of Linux

> [!IMPORTANT]
> At a minimum, the `init.sh`, `main.py`, and `settings.yaml` files should be in the same working directory.

> [!TIP]
>The script expects there to be a `background.bmp` or an equivalent `240 x 320` resolution image as a splash image placed in the working directory. This image is shown when first loading and left on the screen once the script is terminated until power is disconnected. The splash image is optional but is recommended.

### Running on UNRAID
The Docker configuration file needed is in the `docker-config` folder.
<br />
*As for how to use this, idk (instructions to come at a later time).*
<br />

Assuming you have the Docker image sorted out using the config file:
<br />
Make a folder in `appdata` and place the needed files in it. With the WebGUI, edit the Docker. Under the `Script Source` option, point it to `/mnt/user/appdata/[yourfolderhere]`.
If the Docker is configured correctly, it will execute the `init.sh` script and should start monitoring your system.
<br />
Check the Docker log for script output.

### Running outside of UNRAID
If running outside of UNRAID (eg. a Raspberry Pi), use the `init-portable.sh` file instead of `init.sh`, heeding the alerts listed in Prerequisites.
Execute `init-portable.sh` in your terminal and it will do the rest, no need to run in Docker. The script will create its own virtual Python environment and do what is needed to run.

### Settings
The `settings.yaml` file has comments built-in that explain all the user-adjustable options that can be configured. Refer to that file for details.
> [!NOTE]
> The script has fallbacks for environment settings like `CPU_TEMP_SENSOR` and `NETWORK_INTERFACE` in case they can't be found, and will list out all available sensors when this happens so that you can correct it in the `settings.yaml` file for next time.

## Version History
**Always refer to the `Changelog.txt` file for detailed changes as this section will only be updated for x.x or larger releases.**
- 3.8 (2024-08-09)
    - First published to Github
    - Settings are no longer hardcoded into script and are now moved to an external settings file
    - Changelog now lives in its own file rather than internal to the script
    - For more detailed changes, see `Changelog.txt`
- 3.7.x and older (2024-02 to 2024-08)
    - See `Changelog.txt`

## Roadmap
- [ ] Figure out blitting with `matplotlib` for significant plot generation speedup
- [ ] Figure out how to make the screen rendering routine work faster
    - [ ] Use multiple cores? Use a GPU library? Who knows... *(might never happen)*

## Acknowledgements
<a href="https://discord.gg/haha98"><img src="https://cdn.discordapp.com/emojis/765011373590970418.webp?size=96&quality=lossless" alt="soootrue" width="64" height="64"></a>
</div>
^ Thanks to the fellow tech nerds in here for all the suggestions over the evolution of this project (mainly watching me go crazy adding in feature creep)
