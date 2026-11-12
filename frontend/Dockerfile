# ── Build stage ───────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

# ── Production stage ───────────────────────────────────────────────────────
# Unprivileged nginx listens on 8080 and already keeps its pid and temp paths
# under /tmp, so the process does not need to be root.
FROM nginxinc/nginx-unprivileged:1.30-alpine AS production

USER root
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html
USER nginx

ENV BILLING_UPSTREAM=http://billing_service:8000 \
    BILLING_API_KEY=supersecretapikey123

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
