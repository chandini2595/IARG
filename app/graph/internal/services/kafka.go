package services

import (
	"context"
	"fmt"
	"time"

	"github.com/iarg/graph/internal/config"
	"github.com/sirupsen/logrus"
)

// KafkaService is a minimal wrapper to satisfy the service’s runtime wiring.
// The current implementation focuses on health/status and leaves message handling as a future enhancement.
type KafkaService struct {
	brokers []string
	topics  config.KafkaTopics
	logger  *logrus.Logger
}

func NewKafkaService(cfg config.KafkaConfig) (*KafkaService, error) {
	logger := logrus.New()
	logger.SetFormatter(&logrus.JSONFormatter{})

	// Allow running even if kafka is not configured yet (health will report it).
	if len(cfg.Brokers) == 0 {
		return &KafkaService{
			brokers: []string{},
			topics:  cfg.Topics,
			logger:  logger,
		}, nil
	}

	return &KafkaService{
		brokers: cfg.Brokers,
		topics:  cfg.Topics,
		logger:  logger,
	}, nil
}

func (s *KafkaService) Close() error {
	return nil
}

// StartConsumer blocks until the context is canceled.
// This keeps the service structure intact without requiring a full consumer implementation for MVP startup.
func (s *KafkaService) StartConsumer(ctx context.Context, _ *Neo4jService) error {
	s.logger.Info("Kafka consumer started (noop until implemented)")
	<-ctx.Done()
	return nil
}

func (s *KafkaService) HealthCheck(_ context.Context) error {
	if len(s.brokers) == 0 {
		return fmt.Errorf("kafka not configured")
	}

	// Keep health fast and deterministic for local dev.
	// For deeper health checks, integrate kafka-go connectivity + offsets.
	_ = time.Now()
	return nil
}

