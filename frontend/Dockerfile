# --- Build stage ---
FROM node:20-alpine AS build

ARG REACT_APP_MAPBOX_TOKEN
ARG REACT_APP_API_BASE_URL
ARG REACT_APP_WS_BASE_URL

ENV REACT_APP_MAPBOX_TOKEN=$REACT_APP_MAPBOX_TOKEN \
    REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL \
    REACT_APP_WS_BASE_URL=$REACT_APP_WS_BASE_URL

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# --- Production stage ---
FROM nginx:1.27-alpine

COPY --from=build /app/build /usr/share/nginx/html

# Write nginx config template with PORT placeholder
RUN mkdir -p /etc/nginx/templates && \
    printf 'server {\n    listen ${PORT};\n    server_name _;\n    root /usr/share/nginx/html;\n    index index.html;\n\n    location / {\n        try_files $uri $uri/ /index.html;\n    }\n\n    location /static/ {\n        expires 1y;\n        add_header Cache-Control "public, immutable";\n    }\n}\n' > /etc/nginx/templates/default.conf.template && \
    rm -f /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
