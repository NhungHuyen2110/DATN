FROM nginx:1.28-alpine
COPY frontend/ /usr/share/nginx/html/
COPY infra/frontend.conf /etc/nginx/conf.d/default.conf
COPY infra/runtime-config.js /usr/share/nginx/html/runtime-config.js
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/health/live || exit 1
