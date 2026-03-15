#!/bin/bash
{
# Initialization/bootstrap script for UNRAID_status-screen.
# This file is specifically aimed for our Python Docker.
# If you plan to use this script outside of this use case,
# please use the init-portable script instead.
# For changelog, check the 'changelog.txt' file.
# Version = v.3.11.4
# by: WeegeeNumbuh1
STARTTIME=$(date '+%s')
BASEDIR=$(dirname $0)
export BLINKA_FT232H=1
export PYTHONUNBUFFERED=1
export PIP_ROOT_USER_ACTION=ignore # hide pip complaining we're using root
GREEN='\033[0;32m'
ORANGE='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
FADE='\033[2m'
CHECK_FILE=/home/first_run_complete # flag to check if we've run the setup before
PROFILING_FLAG=${BASEDIR}/profile # put a file named 'profile' in the same directory as this script to run profiling
INTERNET_STAT=0 # 0 = there is internet, 1 = no internet (bad)
SKIP_CHECK=0 # 0 = do not skip dependency checks, 1 = skip

# Define function to send SIGTERM when Docker is shutdown
terminate() {
	echo -e "\n${ORANGE}>>> Shutdown signal received, forwarding to child processes.${NC}"
	kill -15 "$child_pid" 2> /dev/null
	sleep 1s
	echo -e "${GREEN}>>> Shutdown complete.${NC}"
	exit 0
	}

echo -e "\n${ORANGE}>>> Firing up this Docker."
echo -e "${GREEN}>>> Checking dependencies, let's begin.${NC}"

if [ ! -f "${BASEDIR}/main.py" ]; then
	>&2 echo -e "\n${NC}${RED}>>> ERROR: Cannot find ${BASEDIR}/main.py. Cannot start."
	sleep 2s
	exit 1
fi

if [ `id -u` -ne 0 ]; then
	>&2 echo -e "${RED}>>> ERROR: This script must be run as root.${NC}"
	sleep 1s
	exit 1
fi

echo -e "${FADE}"
if [ ! -f "$CHECK_FILE" ]; then
	echo "> First run detected, installing needed dependencies.
  This may take some time depending on your internet connection."
	echo "  Notice: Docker memory usage will be higher for this session."
	VERB_TEXT='Installing: '
else
	echo -n "> Last dependencies check: "
	date -r $CHECK_FILE
	last_check_time=$(date -r $CHECK_FILE '+%s')
	# 1 month = 2592000 seconds
	if [ $((STARTTIME - last_check_time)) -lt 7776000 ]; then
		echo "> Last check was less than 3 months ago, skipping tests 👍"
		SKIP_CHECK=1
	fi
	VERB_TEXT='Checking: '
fi

if [ $SKIP_CHECK -eq 0 ]; then
	echo "> Checking system image..."
	# check internet connection
	wget -q --timeout=10 --spider http://google.com
	if [ $? -ne 0 ]; then
		INTERNET_STAT=1
		>&2 echo -e "${NC}${RED}>>> Warning: Failed to connect to internet. File checking will be skipped.${FADE}"
	fi

	if [ ! -f "$CHECK_FILE" ] && [ $INTERNET_STAT -eq 1 ]; then
		>&2 echo -e "${NC}${RED}>>> ERROR: Initial setup cannot continue. Internet connection is required.${NC}"
		sleep 2s
		exit 1
	fi

	if [ $INTERNET_STAT -eq 0 ]; then
		# we need libusb-1.0
		apt-get update >/dev/null
		dpkg --configure -a >/dev/null
		apt-get install -y libusb-1.0-0 >/dev/null
		# apt-get install -y pypy3 >/dev/null
	fi
	echo "> System image ready."
fi

echo -n "> We have: "
python3 -VV

# Unraid's Docker log does not show lines until it encounters a newline so we do the below:
CHECKMARK='\e[1F\e[30C✅\n' # move cursor up to the beginning one line up then move 30 spaces right
# If you use Dozzle, the above will show up as "FC✅", RIP
# install dependencies
if [ -f "$PROFILING_FLAG" ]; then
	echo -e "ℹ️ Profiling flag detected\n -> ${VERB_TEXT}scalene"
	pip install --upgrade scalene >/dev/null
fi

if [ $SKIP_CHECK -eq 0 ]; then
	echo "> Packages check:"
	if [ $INTERNET_STAT -eq 0 ]; then
		echo -e "${VERB_TEXT}pip"
		python3 -m pip install --upgrade pip >/dev/null
		echo -e "${CHECKMARK}${VERB_TEXT}pyftdi"
		pip3 install --upgrade pyftdi >/dev/null
		echo -e "${CHECKMARK}${VERB_TEXT}adafruit-blinka"
		pip3 install adafruit-blinka >/dev/null
		echo -e "${CHECKMARK}${VERB_TEXT}circuitpython"
		pip3 install adafruit-circuitpython-rgb-display >/dev/null
		echo -e "${CHECKMARK}${VERB_TEXT}matplotlib"
		pip3 install --upgrade matplotlib >/dev/null
		pip3 install --upgrade matplotx >/dev/null
		echo -e "${CHECKMARK}${VERB_TEXT}Pillow"
		pip3 install --upgrade Pillow >/dev/null
		echo -e "${CHECKMARK}${VERB_TEXT}psutil"
		pip3 install --upgrade psutil >/dev/null
		echo -e "${CHECKMARK}${VERB_TEXT}pyyaml"
		pip3 install --upgrade pyyaml >/dev/null
		echo -e "${CHECKMARK}${VERB_TEXT}schedule"
		pip3 install --upgrade schedule >/dev/null
		echo -e "${CHECKMARK}░░░▒▒▓▓ Completed ▓▓▒▒░░░\n"
	else
		echo "  Skipping due to no internet."
	fi
	touch $CHECK_FILE
fi

#echo "> List of installed Python packages:"
#pip list # for debug
ENDTIME=$(date '+%s')
echo "Setup/Initialization took $((ENDTIME - STARTTIME)) second(s)."
echo -e "${NC}"
echo -e "${GREEN}>>> Dependencies check complete."
echo -e "${ORANGE}>>> Entering main loop!${NC}"
echo -e "${FADE}"
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

# fire up the script and watch over it
trap terminate SIGTERM
if [ ! -f "$PROFILING_FLAG" ]; then
	python3 ${BASEDIR}/main.py & child_pid=$!
	# pypy3 /app/main.py & child_pid=$!
	wait "$child_pid"
else
#	echo -e "${ORANGE}>>> Profiling enabled. Profile output will be generated every 60 seconds."
#	python3 -m scalene --cli --reduced-profile --profile-interval 60 /app/main.py & child_pid=$!
	echo -e "${ORANGE}>>> ⚠️ Profiling enabled. You MUST run the below command in a new console window!\n"
	echo -e "python3 -m scalene --cli --reduced-profile --profile-interval 60 ${BASEDIR}/main.py \n"
	echo "Note: this can only be run once. The Docker must be restarted to profile again."
	echo "To quit, shutdown the Docker normally."
	echo "--- To disable profiling on the next run, rename or delete the \"profile\" file."
	python3 -c "exec(\"import time\nwhile True: time.sleep(1)\")" & child_pid=$! # to keep the docker alive
	wait "$child_pid"
fi
# the following will only run if the python script exits with an error
>&2 echo -e "\n${NC}${RED}>>> Warning: Script exited unexpectedly. Please review the logs for error details.${NC}"
exit 1
}