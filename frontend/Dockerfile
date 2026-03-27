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

# Railway sets PORT env var — nginx must listen on it
# Uses envsubst to inject PORT at runtime
RUN printf 'server {\n\
    listen ${PORT};\n\
    server_name _;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
\n\
    # Cache static assets\n\
    location /static/ {\n\
        expires 1y;\n\
        add_header Cache-Control "public, immutable";\n\
    }\n\
}\n' > /etc/nginx/templates/default.conf.template

# Remove default config so the template takes over
RUN rm -f /etc/nginx/conf.d/default.conf

EXPOSE 80

# nginx docker image supports envsubst via templates/ dir automatically
CMD ["nginx", "-g", "daemon off;"]
