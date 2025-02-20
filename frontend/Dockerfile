# Stage 1: Build the React app with Node.js 22
FROM node:22-alpine AS builder
WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json ./
RUN yarn install

# Copy the rest of the source code and build the app
COPY . .
RUN yarn build

# Stage 2: Serve the built app using custom Nginx with envsubst for runtime config
FROM nginx:alpine

# Copy custom Nginx configuration template and entrypoint script
COPY nginx/nginx.conf.envsubst /etc/nginx/nginx.conf.envsubst
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Remove default static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy the build output from the builder stage to Nginx's html directory
COPY --from=builder /app/out/ /usr/share/nginx/html

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
