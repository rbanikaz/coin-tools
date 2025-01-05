create venv:
python3 -m venv .venv

source venv:
source .venv/bin/activate

install requirements:
pip install -r requirements.txt

source environment vars:
source ~/.ssh/coin-tools.env

run:
./coin-tools manage-wallets list