# Stage 1: Build the mkdocs site
FROM python:3.12-alpine AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# _sources/ must exist (from sync-repos.sh run before docker build)
COPY . .
RUN mkdocs build

# Stage 2: Serve with nginx
FROM nginx:alpine

# Custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy the built site
COPY --from=builder /app/site /usr/share/nginx/html

# Health check
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://localhost:8080/ || exit 1

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
