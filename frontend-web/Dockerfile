# Fase 1: Compilación Angular (Requiere Node 22+)
FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Fase 2: Servidor Nginx
FROM nginx:alpine

# Valores por defecto: producción (Railway). docker-compose.yml los sobreescribe
# para apuntar al backend local al levantar el stack con `docker compose up`.
ENV BACKEND_UPSTREAM=https://fashionstore-backend-production-4c32.up.railway.app
ENV BACKEND_HOST=fashionstore-backend-production-4c32.up.railway.app

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist/frontend-web/browser /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

