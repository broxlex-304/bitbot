# --- Frontend Dockerfile ---
FROM node:20-alpine

# Set environment variables for build
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_OPTIONS=--max-old-space-size=4096

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Build the Next.js app
RUN npm run build

# Expose port 3000
EXPOSE 3000

# Start the app
CMD ["npm", "start"]
