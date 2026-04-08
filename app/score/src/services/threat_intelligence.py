"""
Threat intelligence service for gathering security data
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

from src.models.asset import Asset, ThreatIntelligence
from src.utils.logging import LoggerMixin
from src.config import settings


class ThreatIntelligenceService(LoggerMixin):
    """Service for gathering threat intelligence data"""
    
    def __init__(self):
        self.api_key = settings.threat_intel_api_key
        self.base_url = settings.threat_intel_base_url
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Cache for threat data
        self.cache: Dict[str, ThreatIntelligence] = {}
        self.cache_ttl = timedelta(hours=6)  # Cache for 6 hours
        
        # Known CVE patterns and threat data
        self.known_threats = self._load_known_threats()
    
    async def initialize(self) -> None:
        """Initialize the threat intelligence service"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'IARG-ThreatIntel/1.0'}
        )
        self.log_event("Threat intelligence service initialized")
    
    async def close(self) -> None:
        """Close the service"""
        if self.session:
            await self.session.close()
    
    async def get_threat_data(self, asset: Asset) -> Optional[ThreatIntelligence]:
        """Get threat intelligence data for an asset"""
        try:
            # Check cache first
            cache_key = f"{asset.id}:{asset.type}:{asset.source}"
            cached_data = self._get_cached_threat_data(cache_key)
            if cached_data:
                return cached_data
            
            # Gather threat intelligence from multiple sources
            threat_data = await self._gather_threat_intelligence(asset)
            
            # Cache the result
            if threat_data:
                self._cache_threat_data(cache_key, threat_data)
            
            return threat_data
            
        except Exception as e:
            self.log_error(e, {"asset_id": asset.id, "component": "threat_intelligence"})
            return self._get_default_threat_data()
    
    async def _gather_threat_intelligence(self, asset: Asset) -> Optional[ThreatIntelligence]:
        """Gather threat intelligence from multiple sources"""
        
        # Initialize threat data
        cve_count = 0
        severity_score = 0.0
        exploit_available = False
        threat_actors = []
        
        # Analyze based on asset type and metadata
        if asset.type == 'repository':
            threat_data = await self._analyze_repository_threats(asset)
        elif asset.type == 'model':
            threat_data = await self._analyze_model_threats(asset)
        elif asset.type == 'dataset':
            threat_data = await self._analyze_dataset_threats(asset)
        else:
            threat_data = await self._analyze_generic_threats(asset)
        
        if threat_data:
            cve_count = threat_data.get('cve_count', 0)
            severity_score = threat_data.get('severity_score', 0.0)
            exploit_available = threat_data.get('exploit_available', False)
            threat_actors = threat_data.get('threat_actors', [])
        
        return ThreatIntelligence(
            cve_count=cve_count,
            severity_score=severity_score,
            exploit_available=exploit_available,
            threat_actors=threat_actors,
            last_updated=datetime.now()
        )
    
    async def _analyze_repository_threats(self, asset: Asset) -> Dict[str, Any]:
        """Analyze threats specific to code repositories"""
        threats = {
            'cve_count': 0,
            'severity_score': 0.0,
            'exploit_available': False,
            'threat_actors': []
        }
        
        # Check for known vulnerable dependencies
        dependencies = asset.metadata.get('dependencies', [])
        for dep in dependencies:
            dep_threats = await self._check_dependency_vulnerabilities(dep)
            threats['cve_count'] += dep_threats.get('cve_count', 0)
            threats['severity_score'] = max(threats['severity_score'], 
                                          dep_threats.get('severity_score', 0.0))
            if dep_threats.get('exploit_available'):
                threats['exploit_available'] = True
        
        # Check for secrets in code
        if await self._check_for_secrets(asset):
            threats['severity_score'] = max(threats['severity_score'], 7.0)
            threats['threat_actors'].append('credential_harvester')
        
        # Check language-specific threats
        language = asset.metadata.get('language', '').lower()
        lang_threats = self._get_language_specific_threats(language)
        threats['cve_count'] += lang_threats.get('cve_count', 0)
        threats['severity_score'] = max(threats['severity_score'], 
                                      lang_threats.get('severity_score', 0.0))
        
        return threats
    
    async def _analyze_model_threats(self, asset: Asset) -> Dict[str, Any]:
        """Analyze threats specific to ML models"""
        threats = {
            'cve_count': 0,
            'severity_score': 5.0,  # Base risk for ML models
            'exploit_available': False,
            'threat_actors': ['model_extraction_attacker', 'adversarial_attacker']
        }
        
        # Check model framework vulnerabilities
        framework = asset.metadata.get('framework', '').lower()
        if framework in ['tensorflow', 'pytorch', 'sklearn']:
            framework_threats = await self._check_framework_vulnerabilities(framework)
            threats['cve_count'] += framework_threats.get('cve_count', 0)
            threats['severity_score'] = max(threats['severity_score'], 
                                          framework_threats.get('severity_score', 0.0))
        
        # Check for model accessibility
        if asset.metadata.get('visibility') == 'public':
            threats['severity_score'] += 2.0
            threats['exploit_available'] = True
            threats['threat_actors'].append('model_inversion_attacker')
        
        return threats
    
    async def _analyze_dataset_threats(self, asset: Asset) -> Dict[str, Any]:
        """Analyze threats specific to datasets"""
        threats = {
            'cve_count': 0,
            'severity_score': 3.0,  # Base risk for datasets
            'exploit_available': False,
            'threat_actors': ['data_poisoner', 'privacy_attacker']
        }
        
        # Check for PII in dataset
        if await self._check_for_pii(asset):
            threats['severity_score'] += 4.0
            threats['threat_actors'].append('pii_harvester')
        
        # Check dataset size and accessibility
        size_mb = asset.metadata.get('size_bytes', 0) / (1024 * 1024)
        if size_mb > 1000:  # Large datasets are more attractive targets
            threats['severity_score'] += 1.0
        
        if asset.metadata.get('visibility') == 'public':
            threats['severity_score'] += 2.0
            threats['exploit_available'] = True
        
        return threats
    
    async def _analyze_generic_threats(self, asset: Asset) -> Dict[str, Any]:
        """Analyze generic threats for other asset types"""
        threats = {
            'cve_count': 0,
            'severity_score': 1.0,  # Base risk
            'exploit_available': False,
            'threat_actors': []
        }
        
        # Check for public exposure
        if asset.metadata.get('visibility') == 'public':
            threats['severity_score'] += 1.0
        
        # Check age-based vulnerabilities
        age_days = (datetime.now() - asset.created_at).days
        if age_days > 365:  # Old assets may have unpatched vulnerabilities
            threats['severity_score'] += 1.0
        
        return threats
    
    async def _check_dependency_vulnerabilities(self, dependency: str) -> Dict[str, Any]:
        """Check vulnerabilities for a specific dependency"""
        # This would integrate with real vulnerability databases
        # For now, return simulated data based on known patterns
        
        known_vulns = {
            'lodash': {'cve_count': 3, 'severity_score': 6.5, 'exploit_available': True},
            'jackson': {'cve_count': 5, 'severity_score': 8.2, 'exploit_available': True},
            'log4j': {'cve_count': 2, 'severity_score': 9.8, 'exploit_available': True},
            'requests': {'cve_count': 1, 'severity_score': 5.3, 'exploit_available': False},
            'numpy': {'cve_count': 1, 'severity_score': 4.2, 'exploit_available': False}
        }
        
        dep_name = dependency.split(':')[0].lower()  # Extract package name
        return known_vulns.get(dep_name, {'cve_count': 0, 'severity_score': 0.0, 'exploit_available': False})
    
    async def _check_for_secrets(self, asset: Asset) -> bool:
        """Check if asset potentially contains secrets"""
        # This would analyze code content for secrets
        # For now, use heuristics based on metadata
        
        indicators = [
            'api_key', 'password', 'secret', 'token', 'credential',
            'private_key', 'certificate', 'config'
        ]
        
        description = asset.description.lower() if asset.description else ''
        name = asset.name.lower()
        
        return any(indicator in description or indicator in name for indicator in indicators)
    
    async def _check_for_pii(self, asset: Asset) -> bool:
        """Check if dataset potentially contains PII"""
        pii_indicators = [
            'personal', 'user', 'customer', 'email', 'phone', 'address',
            'name', 'id', 'ssn', 'medical', 'health', 'financial'
        ]
        
        description = asset.description.lower() if asset.description else ''
        name = asset.name.lower()
        tags = [tag.lower() for tag in asset.tags]
        
        return any(
            indicator in description or 
            indicator in name or 
            any(indicator in tag for tag in tags)
            for indicator in pii_indicators
        )
    
    async def _check_framework_vulnerabilities(self, framework: str) -> Dict[str, Any]:
        """Check vulnerabilities for ML frameworks"""
        framework_vulns = {
            'tensorflow': {'cve_count': 8, 'severity_score': 6.8, 'exploit_available': True},
            'pytorch': {'cve_count': 4, 'severity_score': 5.9, 'exploit_available': False},
            'sklearn': {'cve_count': 2, 'severity_score': 4.1, 'exploit_available': False},
            'keras': {'cve_count': 3, 'severity_score': 5.5, 'exploit_available': False}
        }
        
        return framework_vulns.get(framework, {'cve_count': 0, 'severity_score': 0.0, 'exploit_available': False})
    
    def _get_language_specific_threats(self, language: str) -> Dict[str, Any]:
        """Get threats specific to programming languages"""
        language_threats = {
            'javascript': {'cve_count': 12, 'severity_score': 6.2},
            'python': {'cve_count': 8, 'severity_score': 5.8},
            'java': {'cve_count': 15, 'severity_score': 7.1},
            'c++': {'cve_count': 20, 'severity_score': 8.3},
            'go': {'cve_count': 3, 'severity_score': 4.2},
            'rust': {'cve_count': 1, 'severity_score': 3.1}
        }
        
        return language_threats.get(language, {'cve_count': 0, 'severity_score': 0.0})
    
    def _get_cached_threat_data(self, cache_key: str) -> Optional[ThreatIntelligence]:
        """Get cached threat data"""
        if cache_key in self.cache:
            threat_data = self.cache[cache_key]
            if datetime.now() - threat_data.last_updated < self.cache_ttl:
                return threat_data
            else:
                del self.cache[cache_key]
        return None
    
    def _cache_threat_data(self, cache_key: str, threat_data: ThreatIntelligence) -> None:
        """Cache threat data"""
        self.cache[cache_key] = threat_data
        
        # Clean old cache entries
        if len(self.cache) > 1000:
            oldest_key = min(self.cache.keys(), 
                           key=lambda k: self.cache[k].last_updated)
            del self.cache[oldest_key]
    
    def _get_default_threat_data(self) -> ThreatIntelligence:
        """Get default threat data when real data is unavailable"""
        return ThreatIntelligence(
            cve_count=0,
            severity_score=2.0,  # Low baseline risk
            exploit_available=False,
            threat_actors=[],
            last_updated=datetime.now()
        )
    
    def _load_known_threats(self) -> Dict[str, Any]:
        """Load known threat patterns and indicators"""
        return {
            'high_risk_patterns': [
                'admin', 'root', 'password', 'secret', 'key',
                'token', 'credential', 'private', 'confidential'
            ],
            'vulnerable_packages': [
                'lodash', 'jackson', 'log4j', 'struts', 'spring',
                'jquery', 'bootstrap', 'moment', 'handlebars'
            ],
            'threat_actors': [
                'apt_groups', 'ransomware_operators', 'credential_harvesters',
                'model_extraction_attackers', 'data_poisoners', 'privacy_attackers'
            ]
        }