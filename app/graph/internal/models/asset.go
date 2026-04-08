package models

import (
	"time"
)

// Asset represents an intangible asset in the system
type Asset struct {
	ID           string                 `json:"id" neo4j:"id"`
	Type         string                 `json:"type" neo4j:"type"`
	Name         string                 `json:"name" neo4j:"name"`
	Owner        string                 `json:"owner" neo4j:"owner"`
	Source       string                 `json:"source" neo4j:"source"`
	Description  string                 `json:"description,omitempty" neo4j:"description"`
	Metadata     map[string]interface{} `json:"metadata,omitempty" neo4j:"metadata"`
	RiskScore    float64                `json:"risk_score,omitempty" neo4j:"risk_score"`
	Value        float64                `json:"value,omitempty" neo4j:"value"`
	CreatedAt    time.Time              `json:"created_at" neo4j:"created_at"`
	UpdatedAt    time.Time              `json:"updated_at" neo4j:"updated_at"`
	LastAccessed *time.Time             `json:"last_accessed,omitempty" neo4j:"last_accessed"`
	Tags         []string               `json:"tags,omitempty" neo4j:"tags"`
	Status       string                 `json:"status" neo4j:"status"`
}

// AssetType constants
const (
	AssetTypeRepository = "repository"
	AssetTypeModel      = "model"
	AssetTypeDataset    = "dataset"
	AssetTypeDocument   = "document"
	AssetTypeCode       = "code"
	AssetTypeAPI        = "api"
)

// AssetSource constants
const (
	SourceGitHub      = "github"
	SourceHuggingFace = "huggingface"
	SourceSnowflake   = "snowflake"
	SourceGoogleDrive = "google_drive"
)

// AssetStatus constants
const (
	StatusActive    = "active"
	StatusInactive  = "inactive"
	StatusArchived  = "archived"
	StatusDeleted   = "deleted"
)

// Dependency represents a relationship between assets
type Dependency struct {
	FromAssetID string                 `json:"from_asset_id" neo4j:"from_asset_id"`
	ToAssetID   string                 `json:"to_asset_id" neo4j:"to_asset_id"`
	Type        string                 `json:"type" neo4j:"type"`
	Metadata    map[string]interface{} `json:"metadata,omitempty" neo4j:"metadata"`
	CreatedAt   time.Time              `json:"created_at" neo4j:"created_at"`
}

// DependencyType constants
const (
	DependencyTypeImports    = "imports"
	DependencyTypeInherits   = "inherits"
	DependencyTypeUses       = "uses"
	DependencyTypeContains   = "contains"
	DependencyTypeReferences = "references"
	DependencyTypeTrainedOn  = "trained_on"
)

// AssetCreateRequest represents the request to create a new asset
type AssetCreateRequest struct {
	Type        string                 `json:"type" binding:"required,oneof=repository model dataset document code api"`
	Name        string                 `json:"name" binding:"required"`
	Owner       string                 `json:"owner" binding:"required"`
	Source      string                 `json:"source" binding:"required,oneof=github huggingface snowflake google_drive"`
	Description string                 `json:"description,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	Tags        []string               `json:"tags,omitempty"`
}

// AssetUpdateRequest represents the request to update an asset
type AssetUpdateRequest struct {
	Name         *string                `json:"name,omitempty"`
	Description  *string                `json:"description,omitempty"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
	Tags         []string               `json:"tags,omitempty"`
	Status       *string                `json:"status,omitempty"`
	LastAccessed *time.Time             `json:"last_accessed,omitempty"`
}

// DependencyCreateRequest represents the request to create a dependency
type DependencyCreateRequest struct {
	ToAssetID string                 `json:"to_asset_id" binding:"required"`
	Type      string                 `json:"type" binding:"required,oneof=imports inherits uses contains references trained_on"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// AssetSearchRequest represents search parameters
type AssetSearchRequest struct {
	Query  string   `form:"q"`
	Type   string   `form:"type"`
	Owner  string   `form:"owner"`
	Source string   `form:"source"`
	Tags   []string `form:"tags"`
	Limit  int      `form:"limit"`
	Offset int      `form:"offset"`
}

// AssetGraph represents the graph structure of assets and their relationships
type AssetGraph struct {
	Nodes []Asset      `json:"nodes"`
	Edges []Dependency `json:"edges"`
}

// RiskFactors represents risk assessment factors for an asset
type RiskFactors struct {
	Exposure     float64 `json:"exposure" neo4j:"exposure"`
	Sensitivity  float64 `json:"sensitivity" neo4j:"sensitivity"`
	Criticality  float64 `json:"criticality" neo4j:"criticality"`
	Vulnerability float64 `json:"vulnerability" neo4j:"vulnerability"`
}

// ValuationMetrics represents valuation metrics for an asset
type ValuationMetrics struct {
	RevenueContribution float64 `json:"revenue_contribution" neo4j:"revenue_contribution"`
	UsageRate          float64 `json:"usage_rate" neo4j:"usage_rate"`
	MarketValue        float64 `json:"market_value" neo4j:"market_value"`
	ReplacementCost    float64 `json:"replacement_cost" neo4j:"replacement_cost"`
	DepreciationRate   float64 `json:"depreciation_rate" neo4j:"depreciation_rate"`
}