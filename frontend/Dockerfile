FROM nginxinc/nginx-unprivileged:1.28-alpine
COPY frontend /usr/share/nginx/html
COPY infra/proxy/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
HEALTHCHECK --interval=20s --timeout=5s CMD wget -q -O /dev/null http://127.0.0.1:8080/health
