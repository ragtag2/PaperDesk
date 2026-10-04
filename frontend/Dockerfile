FROM node:24-bookworm-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig*.json vite.config.ts ./
COPY src ./src

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_DEMO_MODE=false
RUN test -n "$VITE_API_BASE_URL" || (echo 'Set VITE_API_BASE_URL to the browser-accessible API URL.' >&2; exit 1)
RUN npm run build

FROM nginx:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
