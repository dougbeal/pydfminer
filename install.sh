#!/bin/sh
echo "Setting up python virtual environment"
python3.8 -m venv .  # create virtual environment,   /usr/local/opt/python@3.8/bin/python3
. bin/activate
pip install -r requirements_dev.txt .
