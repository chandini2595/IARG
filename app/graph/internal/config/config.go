package config

import (
	"os"
	"strings"

	"github.com/joho/godotenv"
)

type Config struct {
	Environment string
	Port        string
	LogLevel    string
	Neo4j       Neo4jConfig
	Kafka       KafkaConfig
}

type Neo4jConfig struct {
	URI      string
	Username string
	Password string
}

type KafkaConfig struct {
	Brokers []string
	Topics  KafkaTopics
}

type KafkaTopics struct {
	Events          string
	AssetDiscovered string
	GraphUpdated    string
}

func Load() (*Config, error) {
	// Load .env file if it exists
	_ = godotenv.Load()

	return &Config{
		Environment: getEnv("NODE_ENV", "development"),
		Port:        getEnv("PORT", "8001"),
		LogLevel:    getEnv("LOG_LEVEL", "info"),
		Neo4j: Neo4jConfig{
			URI:      getEnv("NEO4J_URI", "bolt://localhost:7687"),
			Username: getEnv("NEO4J_USERNAME", "neo4j"),
			Password: getEnv("NEO4J_PASSWORD", "password123"),
		},
		Kafka: KafkaConfig{
			Brokers: strings.Split(getEnv("KAFKA_BROKERS", "localhost:9092"), ","),
			Topics: KafkaTopics{
				Events:          getEnv("KAFKA_TOPIC_EVENTS", "iarg.events"),
				AssetDiscovered: getEnv("KAFKA_TOPIC_ASSET_DISCOVERED", "iarg.asset.discovered"),
				GraphUpdated:    getEnv("KAFKA_TOPIC_GRAPH_UPDATED", "iarg.graph.updated"),
			},
		},
	}, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}