#!/usr/bin/env bash

if [ "$VAGRANT_HOME" = "" ]; then
    VAGRANT_HOME=/vagrant
fi

source $VAGRANT_HOME/data_store/data/parse_yaml.sh
# Pulls the yaml variables out as constant variables.
eval $(parse_yaml $VAGRANT_HOME/data_store/data/config.yml)
eval $(parse_yaml $VAGRANT_HOME/data_store/data/secrets.yml)

USERNAME=$database__DB_USER
DB_NAME=$database__DB_NAME
DB_PASS=$s_database__DB_PASS
TEST_DB_NAME=$database__TEST_DB_NAME

/usr/pgsql-9.3/bin/postgresql93-setup initdb
echo "host all all 0.0.0.0/0 trust" >> /var/lib/pgsql/9.3/data/pg_hba.conf
echo "listen_addresses='*'" >> /var/lib/pgsql/9.3/data/postgresql.conf

sudo -u postgres PGDATA=/var/lib/pgsql/9.3/data /usr/pgsql-9.3/bin/pg_ctl start >> $VAGRANT_HOME/logs/postgres_init.log 2>&1 &
sleep 5
sudo -u postgres psql --command "CREATE USER root WITH SUPERUSER PASSWORD 'password';"
sudo -u postgres psql --command "CREATE USER $USERNAME WITH SUPERUSER PASSWORD '$DB_PASS';"
sudo -u postgres psql --command "CREATE DATABASE $DB_NAME;"
sudo -u postgres psql --command "CREATE DATABASE $TEST_DB_NAME;"
