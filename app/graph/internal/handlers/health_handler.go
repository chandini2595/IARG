package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/iarg/graph/internal/models"
	"github.com/iarg/graph/internal/services"
)

type HealthHandler struct {
	neo4j *services.Neo4jService
	kafka *services.KafkaService
}

func NewHealthHandler(neo4j *services.Neo4jService, kafka *services.KafkaService) *HealthHandler {
	return &HealthHandler{
		neo4j: neo4j,
		kafka: kafka,
	}
}

func (h *HealthHandler) Health(c *gin.Context) {
	if err := h.neo4j.HealthCheck(c.Request.Context()); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"status": "error",
			"neo4j":  err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

func (h *HealthHandler) DetailedHealth(c *gin.Context) {
	neo4jErr := h.neo4j.HealthCheck(c.Request.Context())
	kafkaErr := h.kafka.HealthCheck(c.Request.Context())

	status := models.StatusActive
	if neo4jErr != nil || kafkaErr != nil {
		status = models.StatusInactive
	}

	c.JSON(http.StatusOK, gin.H{
		"status": status,
		"neo4j":  neo4jErr,
		"kafka":  kafkaErr,
	})
}

