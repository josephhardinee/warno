#!/usr/bin/env bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ "$VAGRANT_HOME" = "" ]; then
    VAGRANT_HOME=/vagrant
fi

source $VAGRANT_HOME/data_store/data/parse_yaml.sh
# Pulls the yaml variables out as constant variables.
eval $(parse_yaml $VAGRANT_HOME/data_store/data/config.yml)

if [ "$setup__run_vm_user_portal" = "1" ]; then
    echo "Starting User Portal"
    cd $DIR/src
    if [ "$NO_GUNICORN" = "1" ]
      then
      echo "Starting without GUNICORN"
      python user_portal_server.py >> $VAGRANT_HOME/logs/user_portal_server.log 2>&1 &
    disown
    else
        echo "Starting with Green Unicorn"
        gunicorn -c gunicorn.conf --log-level debug user_portal_server:app >> $VAGRANT_HOME/logs/user_portal_server.log 2>&1 &
    disown
    fi
else
    echo "VM User Portal Disabled in Config"
fi