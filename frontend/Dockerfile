# -----------------------------------------------------------------------------
# frontend/Dockerfile
#
# Docker image for the React Vite dev server on node:20-alpine. package.json is
# copied and npm install runs before source code so the node_modules layer is
# cache-hit on code-only changes. Source is then overridden by the ./frontend:/app
# bind-mount in docker-compose.yml. The named frontend_node_modules volume in
# the compose file preserves the container's node_modules from being shadowed by
# the host mount. For production: replace CMD with `npm run build` and serve
# the resulting dist/ directory from an nginx static file server.
# -----------------------------------------------------------------------------

FROM node:20-alpine

WORKDIR /app

# Install deps first for layer caching
COPY package.json package-lock.json* ./
RUN npm install

# Copy source — overridden by bind-mount in development
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
