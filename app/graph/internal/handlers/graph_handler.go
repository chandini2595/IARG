package handlers

import (
	"context"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/iarg/graph/internal/models"
	"github.com/iarg/graph/internal/services"
)

type GraphHandler struct {
	neo4j *services.Neo4jService
}

func NewGraphHandler(neo4j *services.Neo4jService) *GraphHandler {
	return &GraphHandler{neo4j: neo4j}
}

func (h *GraphHandler) GetAssets(c *gin.Context) {
	ctx := c.Request.Context()

	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))
	if limit <= 0 {
		limit = 50
	}
	if offset < 0 {
		offset = 0
	}

	assets, err := h.neo4j.GetAssets(ctx, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"assets": assets})
}

func (h *GraphHandler) GetAsset(c *gin.Context) {
	ctx := c.Request.Context()

	id := c.Param("id")
	asset, err := h.neo4j.GetAsset(ctx, id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"asset": asset})
}

func (h *GraphHandler) CreateAsset(c *gin.Context) {
	ctx := c.Request.Context()

	var req models.AssetCreateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	asset := &models.Asset{
		Type:        req.Type,
		Name:        req.Name,
		Owner:       req.Owner,
		Source:      req.Source,
		Description: req.Description,
		Metadata:    req.Metadata,
		Tags:        req.Tags,
	}

	if err := h.neo4j.CreateAsset(ctx, asset); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"asset": asset})
}

func (h *GraphHandler) UpdateAsset(c *gin.Context) {
	ctx := c.Request.Context()
	id := c.Param("id")

	var req models.AssetUpdateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := h.neo4j.UpdateAsset(ctx, id, &req); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.Status(http.StatusNoContent)
}

func (h *GraphHandler) DeleteAsset(c *gin.Context) {
	ctx := c.Request.Context()
	id := c.Param("id")

	if err := h.neo4j.DeleteAsset(ctx, id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.Status(http.StatusNoContent)
}

func (h *GraphHandler) GetDependencies(c *gin.Context) {
	ctx := c.Request.Context()
	assetID := c.Param("id")

	deps, err := h.neo4j.GetDependencies(ctx, assetID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"dependencies": deps})
}

func (h *GraphHandler) AddDependency(c *gin.Context) {
	ctx := c.Request.Context()
	fromAssetID := c.Param("id")

	var req models.DependencyCreateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// If client omits ToAssetID in body, keep error handling consistent.
	if req.ToAssetID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "to_asset_id is required"})
		return
	}

	if err := h.neo4j.CreateDependency(ctx, fromAssetID, &req); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.Status(http.StatusNoContent)
}

func (h *GraphHandler) SearchAssets(c *gin.Context) {
	ctx := context.Background()
	if c.Request != nil {
		ctx = c.Request.Context()
	}

	var req models.AssetSearchRequest
	if err := c.ShouldBindQuery(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Defaults if not provided.
	if req.Limit <= 0 {
		req.Limit = 50
	}
	if req.Offset < 0 {
		req.Offset = 0
	}

	assets, err := h.neo4j.SearchAssets(ctx, &req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"assets": assets})
}

