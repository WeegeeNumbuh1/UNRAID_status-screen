#!/bin/bash
# Initialization/bootstrap script for our Python Docker.
# For changelog, check the 'changelog.txt' file.
# Version = v.3.8.1
# by: WeegeeNumbuh1
STARTTIME=$(date '+%s')
BASEDIR=$(dirname $0)
export BLINKA_FT232H=1
export PYTHONUNBUFFERED=1
export PIP_ROOT_USER_ACTION=ignore # hide pip complaining we're using root
VENVPATH=/tmp/python-env
GREEN='\033[0;32m'
ORANGE='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
FADE='\033[2m'
CHECK_FILE=${VENVPATH}/first_run_complete
PROFILING_FLAG=/app/profile
INTERNET_STAT=0 # think return codes

# Define function to send SIGTERM to python when SIGINT is detected
terminate() {
	echo -e "\n${ORANGE}>>> Shutdown signal received, forwarding to child processes.${NC}"
	kill -15 "$child_pid" 2> /dev/null
	sleep 1s
	echo -e "${GREEN}>>> Shutdown complete.${NC}"
	exit 0
	}
	
echo -e "\n${ORANGE}>>> This is the portable script. This will set up the python file to run in a virtual environment."
echo -e "${GREEN}>>> Checking dependencies, let's begin.${NC}"
if [ `id -u` -ne 0 ]; then
    echo "Please run as root."
    exit
fi
echo -e "${FADE}"
if [ ! -f "$CHECK_FILE" ];
then 
	echo "> First run detected, installing needed dependencies.
  This may take some time depending on your internet connection."
	VERB_TEXT='Installing: '
else
	echo -n "> Last dependencies check: "
	date -r $CHECK_FILE
	VERB_TEXT='Checking: '
fi
echo "> Checking system image..."

# check internet connection
wget -q --timeout=10 --spider http://google.com
if [ $? -ne 0 ]; then
	INTERNET_STAT = 1
fi

if [ ! -f "$CHECK_FILE" -a $INTERNET_STAT -eq 1 ]; then
	>&2 echo -e "${NC}${RED}>>> ERROR: Internet connection could not be established. Initial setup cannot continue.${NC}"
	sleep 2s
	exit 1
fi

if [ ! -f "$CHECK_FILE" ];
then 
	apt-get update >/dev/null
	dpkg --configure -a >/dev/null
	apt-get install -y libusb-1.0-0 >/dev/null
	apt-get install -y locales >/dev/null
	apt-get install -y libopenblas0 >/dev/null
	apt-get install -y python3-venv >/dev/null
	sed -i 's/^# *\(en_US.UTF-8\)/\1/' /etc/locale.gen
	locale-gen
	echo "export LC_ALL=en_US.UTF-8" >> ~/.bashrc
	echo "export LANG=en_US.UTF-8" >> ~/.bashrc
	echo "export LANGUAGE=en_US.UTF-8" >> ~/.bashrc
	
fi
#apt-get install -y python-venv >/dev/null
if [ ! -d "$VENVPATH" ];
then
    mkdir ${VENVPATH}
    echo "> Making virtual environment..."
	#pip3 install --upgrade --user virtualenv >/dev/null
	#virtualenv ${VENVPATH} >/dev/null
	python3 -m venv ${VENVPATH}
fi
echo "> System image ready."
echo -n "> We have: "
${VENVPATH}/bin/python3 -VV
# Unraid's Docker log does not show lines until it encounters a newline so we do the below:
CHECKMARK='\e[1F\e[30C✅\n' # move cursor up to the beginning one line up then move 30 spaces right
# If you use Dozzle, the above will show up as "FC✅", RIP
# install dependencies
if [ ! -f "$CHECK_FILE" ];
then 
	echo "> Packages check:"
	echo -e "${VERB_TEXT}pip"
	${VENVPATH}/bin/python3 -m pip install --upgrade pip >/dev/null
	echo -e "${CHECKMARK}${VERB_TEXT}pyftdi"
	${VENVPATH}/bin/pip3 install --upgrade pyftdi >/dev/null
	echo -e "${CHECKMARK}${VERB_TEXT}adafruit-blinka"
	${VENVPATH}/bin/pip3 install --upgrade adafruit-blinka >/dev/null
	echo -e "${CHECKMARK}${VERB_TEXT}circuitpython"
	${VENVPATH}/bin/pip3 install --upgrade adafruit-circuitpython-rgb-display >/dev/null
	echo -e "${CHECKMARK}${VERB_TEXT}matplotlib"
	${VENVPATH}/bin/pip3 install --upgrade matplotlib >/dev/null
	${VENVPATH}/bin/pip3 install --upgrade matplotx >/dev/null
	echo -e "${CHECKMARK}${VERB_TEXT}Pillow"
	${VENVPATH}/bin/pip3 install --upgrade Pillow >/dev/null
	echo -e "${CHECKMARK}${VERB_TEXT}psutil"
	${VENVPATH}/bin/pip3 install --upgrade psutil >/dev/null
	echo -e "${CHECKMARK}${VERB_TEXT}pyyaml"
	pip3 install --upgrade pyyaml >/dev/null
	if [ -f "$PROFILING_FLAG" ];
	then
		echo -e "${CHECKMARK}ℹ️ Profiling flag detected\n -> ${VERB_TEXT}scalene"
		pip install --upgrade scalene >/dev/null
	fi
fi
echo -e "${CHECKMARK}░░░▒▒▓▓ Completed ▓▓▒▒░░░\n"
#echo "> List of installed Python packages:"
#pip list # for debug
touch $CHECK_FILE
ENDTIME=$(date '+%s')
echo "Setup/Initialization took $((ENDTIME - STARTTIME)) seconds."
echo -e "${NC}"
echo -e "${GREEN}>>> Dependencies check complete."
echo -e "${ORANGE}>>> Entering main loop!${NC}"
if [ ! -f "${BASEDIR}/main.py" ]; then
	echo -e "\n${NC}${RED}>>> ERROR: Cannot find ${BASEDIR}/main.py."
	sleep 2s
	exit 1
fi
echo -ne "${FADE}"
echo "                                                  ";
echo "   ██   ██ ███   ██ ██████   █████  ██ ██████     ";
echo "   ██   ██ ████  ██ ██   ██ ██   ██ ██ ██   ██    ";
echo "   ██   ██ ██ ██ ██ ██████  ███████ ██ ██   ██    ";
echo "   ██   ██ ██  ████ ██   ██ ██   ██ ██ ██   ██    ";
echo "    █████  ██   ███ ██   ██ ██   ██ ██ ██████     ";
echo "                                                  ";
echo "███████ ████████  █████  ████████ ██   ██ ███████ ";
echo "██         ██    ██   ██    ██    ██   ██ ██      ";
echo "███████    ██    ███████    ██    ██   ██ ███████ ";
echo "     ██    ██    ██   ██    ██    ██   ██      ██ ";
echo "███████    ██    ██   ██    ██     █████  ███████ ";
echo "                                                  ";
echo " ███████  █████ ██████  ███████ ███████ ███   ██  ";
echo " ██      ██     ██   ██ ██      ██      ████  ██  ";
echo " ███████ ██     ██████  █████   █████   ██ ██ ██  ";
echo "      ██ ██     ██   ██ ██      ██      ██  ████  ";
echo " ███████  █████ ██   ██ ███████ ███████ ██   ███  ";
echo "                                                  ";
echo "   ░       ░      ░             ░  ░     ░    ░   ";
echo " ░ ░  ░   ░░   ░  ▒  ░░      ░  ▒  ░ ░   ░    ░   ";
echo " ░ ▒  ▒   ░▒ ░ ▒░ ▒  ░▒ ░    ▒  ▒▒░░ ░   ░  ░ ▒  ░";
echo " ▒▒▓▒ ▒ ░ ▒▓ ░▒▓░░▓  ▒▓▒░ ░░▒▒  ▓▒▓░ ░▒  ▒ ░░ ▒░ ░";
echo "░▒▓▓▓▓▓ ░▓▓▓ ▒▓▓▒░▓▓░▒▓███  by: WeegeeNumbuh1  ███";

echo ""
echo -e "${NC}${RED}>>> Use Ctrl+C to quit.${FADE}"
# fire up the script and watch over it
trap terminate SIGINT
if [ ! -f "$PROFILING_FLAG" ];
then
	${VENVPATH}/bin/python3 ${BASEDIR}/main.py & child_pid=$!
	# pypy3 /app/main.py & child_pid=$!
	wait "$child_pid"
else
	echo -e "${ORANGE}>>> ⚠️ Profiling enabled. You MUST run the below command in a new console window!"
	echo -e "python3 -m scalene --cli --reduced-profile --profile-interval 60 ${BASEDIR}/main.py \n"
	echo "Note: this can only be run once. This terminal must be restarted to profile again."
	echo "--- To disable profiling on the next run, rename or delete the \"profile\" file."
	python3 -c "exec(\"import time\nwhile True: time.sleep(1)\")" & child_pid=$! # to keep the docker alive
	wait "$child_pid"
fi
# the following will only run if the python script exits with an error
>&2 echo -e "\n${NC}${RED}>>> Warning: Script exited unexpectedly.
             Please review the output above for error details.${NC}"
exit 1