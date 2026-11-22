# Frontend image: React build served by an unprivileged Nginx, which also proxies /api.
#   docker build -t regulationdiff-frontend frontend

FROM node:20.18.1-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG BUILD_NUMBER=dev
ARG GIT_COMMIT=local
ENV VITE_BUILD_NUMBER=$BUILD_NUMBER \
    VITE_GIT_COMMIT=$GIT_COMMIT
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27.3-alpine
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV BACKEND_URL=http://backend:8000
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
