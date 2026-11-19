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