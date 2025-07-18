# syntax=docker/dockerfile:1

### 1) deps stage: install and cache all dependencies ###
FROM node:22-slim AS deps

WORKDIR /app

# Copy lockfiles & package manifests
COPY package.json yarn.lock* package-lock.json* pnpm-lock.yaml* .npmrc* ./

# Install via the available package manager
RUN \
  if [ -f yarn.lock ]; then yarn install --frozen-lockfile; \
  elif [ -f package-lock.json ]; then npm ci; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm install --frozen-lockfile; \
  else echo "Lockfile not found." && exit 1; \
  fi


### 2) builder stage: bring down the build deps & build the app ###
FROM node:22-slim AS builder

WORKDIR /app

# Install only what’s needed to compile any native modules (e.g. SWC, image libs, etc.)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 \
      build-essential \
      libc6-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy node_modules from deps
COPY --from=deps /app/node_modules ./node_modules

# Copy rest of the project
COPY . .

# Build your Next.js app
RUN \
  if [ -f yarn.lock ]; then yarn build; \
  elif [ -f package-lock.json ]; then npm run build; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm build; \
  else echo "Lockfile not found." && exit 1; \
  fi


### 3) runner stage: production image ###
FROM node:22-slim AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1

# Create a non-root user
RUN groupadd --system nodejs && useradd --system --gid nodejs nextjs

# Copy built output from builder
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Optional: copy next.config.js if you rely on it at runtime
# COPY next.config.js ./

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
