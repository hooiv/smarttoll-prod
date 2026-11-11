# ── Build stage ───────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

# ── Production stage ───────────────────────────────────────────────────────
FROM nginx:alpine AS production

# Remove default nginx config. The official entrypoint renders templates at start
# so BILLING_UPSTREAM and BILLING_API_KEY can be injected without a rebuild.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

ENV BILLING_UPSTREAM=http://billing_service:8000 \
    BILLING_API_KEY=supersecretapikey123

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
