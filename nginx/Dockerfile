
FROM nginx:alpine

COPY nginx.conf.envsubst /etc/nginx/nginx.conf.envsubst
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh


EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
