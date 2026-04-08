package services

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/iarg/graph/internal/config"
	"github.com/iarg/graph/internal/models"
	"github.com/neo4j/neo4j-go-driver/v5/neo4j"
	"github.com/sirupsen/logrus"
)

type Neo4jService struct {
	driver neo4j.DriverWithContext
	logger *logrus.Logger
}

func NewNeo4jService(cfg config.Neo4jConfig) (*Neo4jService, error) {
	driver, err := neo4j.NewDriverWithContext(
		cfg.URI,
		neo4j.BasicAuth(cfg.Username, cfg.Password, ""),
		func(config *neo4j.Config) {
			config.MaxConnectionLifetime = 30 * time.Minute
			config.MaxConnectionPoolSize = 50
			config.ConnectionAcquisitionTimeout = 2 * time.Minute
		},
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create Neo4j driver: %w", err)
	}

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := driver.VerifyConnectivity(ctx); err != nil {
		return nil, fmt.Errorf("failed to verify Neo4j connectivity: %w", err)
	}

	logger := logrus.New()
	logger.SetFormatter(&logrus.JSONFormatter{})

	return &Neo4jService{
		driver: driver,
		logger: logger,
	}, nil
}

func (s *Neo4jService) Close() error {
	return s.driver.Close(context.Background())
}

func (s *Neo4jService) CreateAsset(ctx context.Context, asset *models.Asset) error {
	session := s.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
	defer session.Close(ctx)

	// Generate ID if not provided
	if asset.ID == "" {
		asset.ID = uuid.New().String()
	}

	// Set timestamps
	now := time.Now()
	asset.CreatedAt = now
	asset.UpdatedAt = now

	// Set default status
	if asset.Status == "" {
		asset.Status = models.StatusActive
	}

	query := `
		CREATE (a:Asset {
			id: $id,
			type: $type,
			name: $name,
			owner: $owner,
			source: $source,
			description: $description,
			metadata: $metadata,
			risk_score: $risk_score,
			value: $value,
			created_at: $created_at,
			updated_at: $updated_at,
			last_accessed: $last_accessed,
			tags: $tags,
			status: $status
		})
		RETURN a
	`

	params := map[string]interface{}{
		"id":            asset.ID,
		"type":          asset.Type,
		"name":          asset.Name,
		"owner":         asset.Owner,
		"source":        asset.Source,
		"description":   asset.Description,
		"metadata":      asset.Metadata,
		"risk_score":    asset.RiskScore,
		"value":         asset.Value,
		"created_at":    asset.CreatedAt,
		"updated_at":    asset.UpdatedAt,
		"last_accessed": asset.LastAccessed,
		"tags":          asset.Tags,
		"status":        asset.Status,
	}

	_, err := session.ExecuteWrite(ctx, func(tx neo4j.ManagedTransaction) (interface{}, error) {
		result, err := tx.Run(ctx, query, params)
		if err != nil {
			return nil, err
		}
		return result.Consume(ctx)
	})

	if err != nil {
		s.logger.WithError(err).Error("Failed to create asset")
		return fmt.Errorf("failed to create asset: %w", err)
	}

	s.logger.WithFields(logrus.Fields{
		"asset_id":   asset.ID,
		"asset_type": asset.Type,
		"owner":      asset.Owner,
	}).Info("Asset created successfully")

	return nil
}

func (s *Neo4jService) GetAsset(ctx context.Context, id string) (*models.Asset, error) {
	session := s.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	query := `
		MATCH (a:Asset {id: $id})
		RETURN a
	`

	result, err := session.ExecuteRead(ctx, func(tx neo4j.ManagedTransaction) (interface{}, error) {
		result, err := tx.Run(ctx, query, map[string]interface{}{"id": id})
		if err != nil {
			return nil, err
		}

		if result.Next(ctx) {
			record := result.Record()
			node, ok := record.Get("a")
			if !ok {
				return nil, fmt.Errorf("asset not found")
			}

			return s.nodeToAsset(node.(neo4j.Node))
		}

		return nil, fmt.Errorf("asset not found")
	})

	if err != nil {
		return nil, err
	}

	return result.(*models.Asset), nil
}

func (s *Neo4jService) UpdateAsset(ctx context.Context, id string, updates *models.AssetUpdateRequest) error {
	session := s.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
	defer session.Close(ctx)

	// Build dynamic SET clause
	setParts := []string{"a.updated_at = $updated_at"}
	params := map[string]interface{}{
		"id":         id,
		"updated_at": time.Now(),
	}

	if updates.Name != nil {
		setParts = append(setParts, "a.name = $name")
		params["name"] = *updates.Name
	}
	if updates.Description != nil {
		setParts = append(setParts, "a.description = $description")
		params["description"] = *updates.Description
	}
	if updates.Metadata != nil {
		setParts = append(setParts, "a.metadata = $metadata")
		params["metadata"] = updates.Metadata
	}
	if updates.Tags != nil {
		setParts = append(setParts, "a.tags = $tags")
		params["tags"] = updates.Tags
	}
	if updates.Status != nil {
		setParts = append(setParts, "a.status = $status")
		params["status"] = *updates.Status
	}
	if updates.LastAccessed != nil {
		setParts = append(setParts, "a.last_accessed = $last_accessed")
		params["last_accessed"] = *updates.LastAccessed
	}

	query := fmt.Sprintf(`
		MATCH (a:Asset {id: $id})
		SET %s
		RETURN a
	`, joinStrings(setParts, ", "))

	_, err := session.ExecuteWrite(ctx, func(tx neo4j.ManagedTransaction) (interface{}, error) {
		result, err := tx.Run(ctx, query, params)
		if err != nil {
			return nil, err
		}
		return result.Consume(ctx)
	})

	if err != nil {
		s.logger.WithError(err).WithField("asset_id", id).Error("Failed to update asset")
		return fmt.Errorf("failed to update asset: %w", err)
	}

	return nil
}

func (s *Neo4jService) DeleteAsset(ctx context.Context, id string) error {
	session := s.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
	defer session.Close(ctx)

	query := `
		MATCH (a:Asset {id: $id})
		DETACH DELETE a
	`

	_, err := session.ExecuteWrite(ctx, func(tx neo4j.ManagedTransaction) (interface{}, error) {
		result, err := tx.Run(ctx, query, map[string]interface{}{"id": id})
		if err != nil {
			return nil, err
		}
		return result.Consume(ctx)
	})

	if err != nil {
		s.logger.WithError(err).WithField("asset_id", id).Error("Failed to delete asset")
		return fmt.Errorf("failed to delete asset: %w", err)
	}

	return nil
}

func (s *Neo4jService) GetAssets(ctx context.Context, limit, offset int) ([]*models.Asset, error) {
	session := s.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	query := `
		MATCH (a:Asset)
		WHERE a.status <> 'deleted'
		RETURN a
		ORDER BY a.updated_at DESC
		SKIP $offset
		LIMIT $limit
	`

	result, err := session.ExecuteRead(ctx, func(tx neo4j.ManagedTransaction) (interface{}, error) {
		result, err := tx.Run(ctx, query, map[string]interface{}{
			"limit":  limit,
			"offset": offset,
		})
		if err != nil {
			return nil, err
		}

		var assets []*models.Asset
		for result.Next(ctx) {
			record := result.Record()
			node, ok := record.Get("a")
			if !ok {
				continue
			}

			asset, err := s.nodeToAsset(node.(neo4j.Node))
			if err != nil {
				s.logger.WithError(err).Warn("Failed to convert node to asset")
				continue
			}

			assets = append(assets, asset)
		}

		return assets, nil
	})

	if err != nil {
		return nil, err
	}

	return result.([]*models.Asset), nil
}

func (s *Neo4jService) CreateDependency(ctx context.Context, fromAssetID string, dep *models.DependencyCreateRequest) error {
	session := s.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
	defer session.Close(ctx)

	query := `
		MATCH (from:Asset {id: $from_id}), (to:Asset {id: $to_id})
		CREATE (from)-[r:DEPENDS_ON {
			type: $type,
			metadata: $metadata,
			created_at: $created_at
		}]->(to)
		RETURN r
	`

	params := map[string]interface{}{
		"from_id":    fromAssetID,
		"to_id":      dep.ToAssetID,
		"type":       dep.Type,
		"metadata":   dep.Metadata,
		"created_at": time.Now(),
	}

	_, err := session.ExecuteWrite(ctx, func(tx neo4j.ManagedTransaction) (interface{}, error) {
		result, err := tx.Run(ctx, query, params)
		if err != nil {
			return nil, err
		}
		return result.Consume(ctx)
	})

	if err != nil {
		s.logger.WithError(err).WithFields(logrus.Fields{
			"from_asset_id": fromAssetID,
			"to_asset_id":   dep.ToAssetID,
			"type":          dep.Type,
		}).Error("Failed to create dependency")
		return fmt.Errorf("failed to create dependency: %w", err)
	}

	return nil
}

func (s *Neo4jService) GetDependencies(ctx context.Context, assetID string) ([]*models.Dependency, error) {
	session := s.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	query := `
		MATCH (from:Asset {id: $asset_id})-[r:DEPENDS_ON]->(to:Asset)
		RETURN from.id as from_id, to.id as to_id, r.type as type, r.metadata as metadata, r.created_at as created_at
	`

	result, err := session.ExecuteRead(ctx, func(tx neo4j.ManagedTransaction) (interface{}, error) {
		result, err := tx.Run(ctx, query, map[string]interface{}{"asset_id": assetID})
		if err != nil {
			return nil, err
		}

		var dependencies []*models.Dependency
		for result.Next(ctx) {
			record := result.Record()
			
			dep := &models.Dependency{
				FromAssetID: record.Values[0].(string),
				ToAssetID:   record.Values[1].(string),
				Type:        record.Values[2].(string),
				CreatedAt:   record.Values[4].(time.Time),
			}

			if metadata, ok := record.Values[3].(map[string]interface{}); ok {
				dep.Metadata = metadata
			}

			dependencies = append(dependencies, dep)
		}

		return dependencies, nil
	})

	if err != nil {
		return nil, err
	}

	return result.([]*models.Dependency), nil
}

func (s *Neo4jService) SearchAssets(ctx context.Context, req *models.AssetSearchRequest) ([]*models.Asset, error) {
	session := s.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	// Build dynamic WHERE clause
	whereParts := []string{"a.status <> 'deleted'"}
	params := map[string]interface{}{
		"limit":  req.Limit,
		"offset": req.Offset,
	}

	if req.Query != "" {
		whereParts = append(whereParts, "(a.name CONTAINS $query OR a.description CONTAINS $query)")
		params["query"] = req.Query
	}
	if req.Type != "" {
		whereParts = append(whereParts, "a.type = $type")
		params["type"] = req.Type
	}
	if req.Owner != "" {
		whereParts = append(whereParts, "a.owner = $owner")
		params["owner"] = req.Owner
	}
	if req.Source != "" {
		whereParts = append(whereParts, "a.source = $source")
		params["source"] = req.Source
	}

	query := fmt.Sprintf(`
		MATCH (a:Asset)
		WHERE %s
		RETURN a
		ORDER BY a.updated_at DESC
		SKIP $offset
		LIMIT $limit
	`, joinStrings(whereParts, " AND "))

	result, err := session.ExecuteRead(ctx, func(tx neo4j.ManagedTransaction) (interface{}, error) {
		result, err := tx.Run(ctx, query, params)
		if err != nil {
			return nil, err
		}

		var assets []*models.Asset
		for result.Next(ctx) {
			record := result.Record()
			node, ok := record.Get("a")
			if !ok {
				continue
			}

			asset, err := s.nodeToAsset(node.(neo4j.Node))
			if err != nil {
				s.logger.WithError(err).Warn("Failed to convert node to asset")
				continue
			}

			assets = append(assets, asset)
		}

		return assets, nil
	})

	if err != nil {
		return nil, err
	}

	return result.([]*models.Asset), nil
}

func (s *Neo4jService) HealthCheck(ctx context.Context) error {
	session := s.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	_, err := session.ExecuteRead(ctx, func(tx neo4j.ManagedTransaction) (interface{}, error) {
		result, err := tx.Run(ctx, "RETURN 1", nil)
		if err != nil {
			return nil, err
		}
		return result.Consume(ctx)
	})

	return err
}

// Helper functions
func (s *Neo4jService) nodeToAsset(node neo4j.Node) (*models.Asset, error) {
	props := node.Props
	
	asset := &models.Asset{
		ID:          getString(props, "id"),
		Type:        getString(props, "type"),
		Name:        getString(props, "name"),
		Owner:       getString(props, "owner"),
		Source:      getString(props, "source"),
		Description: getString(props, "description"),
		RiskScore:   getFloat64(props, "risk_score"),
		Value:       getFloat64(props, "value"),
		Status:      getString(props, "status"),
	}

	if createdAt, ok := props["created_at"].(time.Time); ok {
		asset.CreatedAt = createdAt
	}
	if updatedAt, ok := props["updated_at"].(time.Time); ok {
		asset.UpdatedAt = updatedAt
	}
	if lastAccessed, ok := props["last_accessed"].(time.Time); ok {
		asset.LastAccessed = &lastAccessed
	}
	if metadata, ok := props["metadata"].(map[string]interface{}); ok {
		asset.Metadata = metadata
	}
	if tags, ok := props["tags"].([]interface{}); ok {
		asset.Tags = make([]string, len(tags))
		for i, tag := range tags {
			if str, ok := tag.(string); ok {
				asset.Tags[i] = str
			}
		}
	}

	return asset, nil
}

func getString(props map[string]interface{}, key string) string {
	if val, ok := props[key].(string); ok {
		return val
	}
	return ""
}

func getFloat64(props map[string]interface{}, key string) float64 {
	if val, ok := props[key].(float64); ok {
		return val
	}
	return 0
}

func joinStrings(strs []string, sep string) string {
	if len(strs) == 0 {
		return ""
	}
	if len(strs) == 1 {
		return strs[0]
	}
	
	result := strs[0]
	for i := 1; i < len(strs); i++ {
		result += sep + strs[i]
	}
	return result
}