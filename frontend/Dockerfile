# --- Build stage ---
FROM node:20-alpine AS build

ARG REACT_APP_MAPBOX_TOKEN
ARG REACT_APP_API_BASE_URL
ARG REACT_APP_WS_BASE_URL

ENV REACT_APP_MAPBOX_TOKEN=$REACT_APP_MAPBOX_TOKEN \
    REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL \
    REACT_APP_WS_BASE_URL=$REACT_APP_WS_BASE_URL

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --production=false

COPY . .
RUN npm run build

# --- Production stage ---
FROM nginx:1.27-alpine

COPY --from=build /app/build /usr/share/nginx/html

# SPA fallback: serve index.html for all routes
RUN printf 'server {\n\
    listen 80;\n\
    server_name _;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
\n\
    location /api/ {\n\
        proxy_pass http://backend:8000/api/;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
    }\n\
\n\
    location /ws {\n\
        proxy_pass http://backend:8000/ws;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header Upgrade $http_upgrade;\n\
        proxy_set_header Connection "upgrade";\n\
    }\n\
\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]