#!/bin/bash
set -e

echo "Installing global frontend tools..."
npm install -g bower grunt-cli

echo "Installing frontend dependencies..."
cd frontend
npm install
bower install
cd ..

echo "Configuring application..."
if [ ! -f conf/application.conf ]; then
    cp conf/application.sample.conf conf/application.conf
    # Set secret key
    sed -i 's|include "/etc/thehive/secret.conf"|play.http.secret.key="changeme"|g' conf/application.conf
    # Set local storage paths
    sed -i 's|/opt/thp/thehive|./data|g' conf/application.conf
    # Create data directories
    mkdir -p data/database data/index
fi

echo "Starting backend services..."
cd nv-core/event-spine
# Use updated docker-compose with public mirrors
docker-compose up -d
cd ../..

echo "Setup complete. Run './sbt run' to start TheHive."
