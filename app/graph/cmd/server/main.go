package main

import (
	"context"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/iarg/graph/internal/config"
	"github.com/iarg/graph/internal/handlers"
	"github.com/iarg/graph/internal/middleware"
	"github.com/iarg/graph/internal/services"
	"github.com/sirupsen/logrus"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		logrus.Fatalf("Failed to load configuration: %v", err)
	}

	// Setup logger
	setupLogger(cfg.LogLevel)

	// Initialize services
	neo4jService, err := services.NewNeo4jService(cfg.Neo4j)
	if err != nil {
		logrus.Fatalf("Failed to initialize Neo4j service: %v", err)
	}
	defer neo4jService.Close()

	kafkaService, err := services.NewKafkaService(cfg.Kafka)
	if err != nil {
		logrus.Fatalf("Failed to initialize Kafka service: %v", err)
	}
	defer kafkaService.Close()

	// Initialize handlers
	graphHandler := handlers.NewGraphHandler(neo4jService)
	healthHandler := handlers.NewHealthHandler(neo4jService, kafkaService)

	// Setup Gin router
	if cfg.Environment == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	router := gin.New()
	router.Use(gin.Recovery())
	router.Use(middleware.Logger())
	router.Use(middleware.CORS())
	router.Use(middleware.RequestID())

	// Routes
	v1 := router.Group("/api/v1")
	{
		v1.GET("/health", healthHandler.Health)
		v1.GET("/health/detailed", healthHandler.DetailedHealth)
		
		graph := v1.Group("/graph")
		{
			graph.GET("/assets", graphHandler.GetAssets)
			graph.GET("/assets/:id", graphHandler.GetAsset)
			graph.POST("/assets", graphHandler.CreateAsset)
			graph.PUT("/assets/:id", graphHandler.UpdateAsset)
			graph.DELETE("/assets/:id", graphHandler.DeleteAsset)
			graph.GET("/assets/:id/dependencies", graphHandler.GetDependencies)
			graph.POST("/assets/:id/dependencies", graphHandler.AddDependency)
			graph.GET("/search", graphHandler.SearchAssets)
		}
	}

	// Start Kafka consumer in background
	go func() {
		if err := kafkaService.StartConsumer(context.Background(), neo4jService); err != nil {
			logrus.Errorf("Kafka consumer error: %v", err)
		}
	}()

	// Setup HTTP server
	server := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start server in goroutine
	go func() {
		logrus.Infof("IARG Graph Service starting on port %s", cfg.Port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logrus.Fatalf("Failed to start server: %v", err)
		}
	}()

	// Wait for interrupt signal to gracefully shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logrus.Info("Shutting down server...")

	// Graceful shutdown with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		logrus.Errorf("Server forced to shutdown: %v", err)
	}

	logrus.Info("Server exited")
}

func setupLogger(level string) {
	logrus.SetFormatter(&logrus.JSONFormatter{
		TimestampFormat: time.RFC3339,
	})

	switch level {
	case "debug":
		logrus.SetLevel(logrus.DebugLevel)
	case "info":
		logrus.SetLevel(logrus.InfoLevel)
	case "warn":
		logrus.SetLevel(logrus.WarnLevel)
	case "error":
		logrus.SetLevel(logrus.ErrorLevel)
	default:
		logrus.SetLevel(logrus.InfoLevel)
	}
}