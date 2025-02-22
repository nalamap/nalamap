#!/bin/sh
# Substitute environment variables in the Nginx config template and output the final config
envsubst '$BACKEND_PROTOCOL $BACKEND_URL' < /etc/nginx/nginx.conf.envsubst > /etc/nginx/nginx.conf

# Execute the command passed to the entrypoint (nginx)
exec "$@"
