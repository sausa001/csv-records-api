# ---------- deps: install exact versions from package-lock.json ----------
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# ---------- test: unit tests + a production build must pass ----------
FROM deps AS test
COPY . .
RUN npm test && npm run build

# ---------- build: produce static files in /app/dist ----------
FROM deps AS build
COPY . .
RUN npm run build

# ---------- runtime: nginx (non-root, port 8080) serves the app and proxies /api ----------
FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime
ENV API_UPSTREAM=csv-records-api:80
# --chmod=0755: readable by the non-root nginx user (also applies to the templates/ folder Docker creates)
COPY --chmod=0755 nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build --chmod=0755 /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
