# Build stage
FROM node:16-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build -- --configuration=production --base-href=/plcopen-editor/

# Production stage
FROM nginx:alpine
COPY --from=build /app/dist/OpenPLC-Editor /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
