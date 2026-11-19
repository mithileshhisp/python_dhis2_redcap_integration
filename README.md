# python_hivtracker_to_ihmis_pi_datavalue_integration
Python Script to Auto sync HIVTRACKER  programindicators to IHMIS aggregated dataset

# add flask for create web-app for DHIS2
## install

pip install flask requests python-dotenv

pip install --upgrade certifi

pip install --upgrade requests certifi urllib3

pip install flask-cors

pip install python-dotenv

pip install psycopg2-binary

pip install clickhouse-connect

pip install nepali-date_converter

pip install npdatetime

pip install datetime

#https://pypi.org/project/nepali-calendar-utils/

pip install nepali-calendar-utils

pip install nepali

pip install nepali-datetime


-- 
sudo apt update

sudo apt install python3-full python3-venv -y

-- Create virtual environment

cd /home/mithilesh/climet_data_exchange

python3 -m venv venv

-- Activate it

source venv/bin/activate

then

pip install nepali-datetime

pip install --upgrade requests certifi urllib3

pip install python-dotenv

## sudo rm -f -- HIV_*.csv


## for create virtual environment
python3 -m venv venv

source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env

python main.py


python3 -m venv venv

source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env

python main.py

## Installation instructions
## Windows PowerShell

# Create virtual environment
py -m venv venv

# Activate environment
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Create environment file
Copy-Item .env.example .env

# Run integration
python main.py

## Linux / Ubuntu

python3 -m venv venv
source venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
chmod 600 .env

python main.py