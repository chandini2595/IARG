FROM golang:1.21-alpine AS builder

WORKDIR /app

# Install dependencies
RUN apk add --no-cache git ca-certificates

# Copy go mod files.
# Note: `go.sum` may be missing in the repo; Go will generate it during `go mod download`.
COPY go.mod ./
RUN go mod download

# Copy source code
COPY . .

# Ensure module graph is complete for this Go version
RUN go mod tidy

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -mod=mod -a -installsuffix cgo -o main ./cmd/server

# Final stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates tzdata wget
WORKDIR /root/

# Copy the binary from builder
COPY --from=builder /app/main .

# Create non-root user
RUN adduser -D -s /bin/sh appuser
USER appuser

# Health check
# Allow extra startup time (neo4j/kafka connectivity can take a bit).
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8001/api/v1/health || exit 1

EXPOSE 8001

CMD ["./main"]