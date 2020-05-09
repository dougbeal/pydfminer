# setup venv
PATH="/usr/local/opt/python@3.8/bin/:$PATH" /usr/local/opt/python@3.8/bin/python3.8 -m venv .  # create virtual environment,   /usr/local/opt/python@3.8/bin/python3

# activate venv
. bin/activate

# install dependencies
pip install -r requirements_dev.txt 
pip install .


# freeze deps
pip freeze -r requirements.txt -r requirements_dev.txt 
