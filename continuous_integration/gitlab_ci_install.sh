#!/bin/bash
# This script was adapted from the pyart install.sh script.
# This script is adapted from the install.sh script from the scikit-learn
# project: https://github.com/scikit-learn/scikit-learn

# This script is meant to be called by the "install" step defined in
# .travis.yml. See http://docs.travis-ci.com/ for more details.
# The behavior of the script is controlled by environment variables defined
# in the .travis.yml in the top level folder of the project.

set -e
# use next line to debug this script
#set -x

# Use Miniconda to provide a Python environment.  This allows us to perform
# a conda based install of the SciPy stack on multiple versions of Python
# as well as use conda and binstar to install additional modules which are not
# in the default repository.
yum install -y gcc
conda update --yes conda

# Install dependencies
conda install --yes numpy nose psutil netcdf4 psycopg2 pandas backports
pip install pyyaml Flask requests selenium nose-cov nose-exclude mock sqlalchemy flask-testing blinker flask-sqlalchemy flask-migrate flask-fixtures ijson flask-user configparser flask-restless ciso8601 redis

git clone http://overwatch.pnl.gov/hard505/pypro-aflib.git
cd pypro-aflib
python setup.py install
cd ..

# install coverage modules
# set up testing environment variables
source utility_setup_scripts/set_vagrant_env.sh
