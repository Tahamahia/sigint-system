FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY src/ ./src/

ENV NODE_ENV=production
ENV PORT=4000
ENV WS_PORT=4001

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD wget -q --spider http://localhost:4000/health || exit 1

EXPOSE 4000 4001

CMD ["node", "src/index.js"]
