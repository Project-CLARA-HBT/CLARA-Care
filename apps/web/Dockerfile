FROM node:26-alpine AS base
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

FROM base AS deps
COPY apps/web/package.json ./package.json
COPY apps/web/package-lock.json ./package-lock.json
RUN npm ci --no-audit --no-fund

FROM base AS builder
ARG NEXT_PUBLIC_API_URL=http://localhost:8100/api/v1
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ARG NEXT_PUBLIC_RESEARCH_OUTPUT_MODES_ENABLED=false
ENV NEXT_PUBLIC_RESEARCH_OUTPUT_MODES_ENABLED=${NEXT_PUBLIC_RESEARCH_OUTPUT_MODES_ENABLED}
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web .
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
