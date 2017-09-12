#!/usr/bin/env bash

if [ "$VAGRANT_HOME" = "" ]; then
    VAGRANT_HOME=/vagrant
fi

cp $VAGRANT_HOME/proxy/nginx.conf /etc/nginx/nginx.conf
cp $VAGRANT_HOME/proxy/privkey.pem /etc/ssl/privkey.pem
cp $VAGRANT_HOME/proxy/cacert.pem /etc/ssl/cacert.pem

chmod a+x $VAGRANT_HOME/proxy/runserver.sh
chmod 711 /var/lib/nginx /var/lib/nginx/tmp

cp -r -T $VAGRANT_HOME/proxy/sites-enabled /etc/nginx/sites-enabled

$VAGRANT_HOME/proxy/runserver.sh >> $VAGRANT_HOME/logs/proxy_server.log 2>&1 &
disown
