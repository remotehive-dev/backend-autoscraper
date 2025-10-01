from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
import spacy
import re
from collections import Counter, defaultdict
import logging
# from sqlalchemy.orm import Session  # Using MongoDB instead
from backend.core.deps import get_db
from backend.models.scraping_session import ScrapingSession, ScrapingResult

logger = logging.getLogger(__name__)

@dataclass
class SelectorPattern:
    """Represents a learned selector pattern"""
    selector: str
    confidence: float
    success_rate: float
    domain_pattern: str
    content_type: str
    usage_count: int
    last_used: datetime
    performance_score: float

@dataclass
class MLPrediction:
    """ML prediction result"""
    predicted_selectors: List[str]
    confidence_scores: List[float]
    optimization_suggestions: List[str]
    expected_success_rate: float
    estimated_response_time: float
    risk_factors: List[str]

@dataclass
class PatternInsight:
    """Insights from pattern analysis"""
    pattern_type: str
    description: str
    confidence: float
    impact_score: float
    recommendation: str
    supporting_data: Dict[str, Any]

@dataclass
class AdaptiveLearningMetrics:
    """Metrics for adaptive learning performance"""
    pattern_accuracy: float
    learning_rate: float
    adaptation_speed: float
    prediction_confidence: float
    optimization_impact: float
    model_stability: float

class MLIntelligenceEngine:
    """Advanced ML engine for scraping optimization and pattern recognition"""
    
    def __init__(self):
        self.selector_classifier = RandomForestClassifier(n_estimators=100, random_state=42)
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.text_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.scaler = StandardScaler()
        self.clustering_model = KMeans(n_clusters=5, random_state=42)
        
        # Load spaCy model for NLP
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy English model not found. Some NLP features will be limited.")
            self.nlp = None
        
        # Pattern storage
        self.learned_patterns: Dict[str, List[SelectorPattern]] = defaultdict(list)
        self.domain_insights: Dict[str, Dict[str, Any]] = {}
        self.performance_history: List[Dict[str, Any]] = []
        
        # Model states
        self.is_trained = False
        self.last_training_time: Optional[datetime] = None
        self.training_data_size = 0
        
    def extract_features_from_html(self, html_content: str, url: str) -> Dict[str, Any]:
        """Extract features from HTML content for ML analysis"""
        features = {
            'url_length': len(url),
            'html_length': len(html_content),
            'tag_count': len(re.findall(r'<[^>]+>', html_content)),
            'class_count': len(re.findall(r'class="[^"]*"', html_content)),
            'id_count': len(re.findall(r'id="[^"]*"', html_content)),
            'form_count': len(re.findall(r'<form[^>]*>', html_content, re.IGNORECASE)),
            'table_count': len(re.findall(r'<table[^>]*>', html_content, re.IGNORECASE)),
            'div_count': len(re.findall(r'<div[^>]*>', html_content, re.IGNORECASE)),
            'span_count': len(re.findall(r'<span[^>]*>', html_content, re.IGNORECASE)),
            'link_count': len(re.findall(r'<a[^>]*>', html_content, re.IGNORECASE)),
            'image_count': len(re.findall(r'<img[^>]*>', html_content, re.IGNORECASE)),
            'script_count': len(re.findall(r'<script[^>]*>', html_content, re.IGNORECASE)),
            'style_count': len(re.findall(r'<style[^>]*>', html_content, re.IGNORECASE)),
        }
        
        # Extract domain features
        domain = self._extract_domain(url)
        features.update({
            'domain': domain,
            'is_subdomain': len(domain.split('.')) > 2,
            'has_www': url.startswith('http://www.') or url.startswith('https://www.'),
            'is_https': url.startswith('https://'),
            'path_depth': len([p for p in url.split('/')[3:] if p]),
        })
        
        # Text analysis features
        if self.nlp:
            text_content = re.sub(r'<[^>]+>', ' ', html_content)
            doc = self.nlp(text_content[:1000])  # Limit for performance
            features.update({
                'entity_count': len(doc.ents),
                'sentence_count': len(list(doc.sents)),
                'avg_word_length': np.mean([len(token.text) for token in doc if token.is_alpha]) if doc else 0,
            })
        
        return features
    
    def analyze_selector_patterns(self, successful_selectors: List[str], 
                                failed_selectors: List[str], 
                                domain: str) -> List[PatternInsight]:
        """Analyze selector patterns to identify success factors"""
        insights = []
        
        # Analyze successful patterns
        if successful_selectors:
            success_patterns = self._extract_selector_patterns(successful_selectors)
            for pattern, count in success_patterns.most_common(5):
                insight = PatternInsight(
                    pattern_type="successful_selector",
                    description=f"Pattern '{pattern}' appears in {count} successful selectors",
                    confidence=min(count / len(successful_selectors), 1.0),
                    impact_score=count * 0.1,
                    recommendation=f"Consider using selectors with pattern '{pattern}' for {domain}",
                    supporting_data={"pattern": pattern, "count": count, "domain": domain}
                )
                insights.append(insight)
        
        # Analyze failed patterns
        if failed_selectors:
            failed_patterns = self._extract_selector_patterns(failed_selectors)
            for pattern, count in failed_patterns.most_common(3):
                insight = PatternInsight(
                    pattern_type="failed_selector",
                    description=f"Pattern '{pattern}' appears in {count} failed selectors",
                    confidence=min(count / len(failed_selectors), 1.0),
                    impact_score=-count * 0.1,
                    recommendation=f"Avoid selectors with pattern '{pattern}' for {domain}",
                    supporting_data={"pattern": pattern, "count": count, "domain": domain}
                )
                insights.append(insight)
        
        return insights
    
    def predict_optimal_selectors(self, html_content: str, url: str, 
                                target_content_type: str = "general") -> MLPrediction:
        """Predict optimal selectors for given HTML content"""
        domain = self._extract_domain(url)
        features = self.extract_features_from_html(html_content, url)
        
        # Get domain-specific patterns
        domain_patterns = self.learned_patterns.get(domain, [])
        
        # Generate candidate selectors based on HTML structure
        candidate_selectors = self._generate_candidate_selectors(html_content)
        
        # Score selectors based on learned patterns
        scored_selectors = []
        for selector in candidate_selectors:
            score = self._score_selector(selector, domain_patterns, features)
            scored_selectors.append((selector, score))
        
        # Sort by score and take top candidates
        scored_selectors.sort(key=lambda x: x[1], reverse=True)
        top_selectors = scored_selectors[:10]
        
        # Generate optimization suggestions
        suggestions = self._generate_optimization_suggestions(features, domain_patterns)
        
        # Estimate performance metrics
        expected_success_rate = self._estimate_success_rate(top_selectors, domain_patterns)
        estimated_response_time = self._estimate_response_time(features)
        
        # Identify risk factors
        risk_factors = self._identify_risk_factors(features, html_content)
        
        return MLPrediction(
            predicted_selectors=[s[0] for s in top_selectors],
            confidence_scores=[s[1] for s in top_selectors],
            optimization_suggestions=suggestions,
            expected_success_rate=expected_success_rate,
            estimated_response_time=estimated_response_time,
            risk_factors=risk_factors
        )
    
    def learn_from_scraping_results(self, session_id: int, db) -> AdaptiveLearningMetrics:  # db: Any - Using MongoDB instead
        """Learn from scraping session results to improve future predictions"""
        # Fetch session data
        session = db.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        results = db.query(ScrapingResult).filter(ScrapingResult.session_id == session_id).all()
        
        # Process results for learning
        learning_data = []
        for result in results:
            if result.extracted_data and result.selectors_used:
                features = self.extract_features_from_html(
                    result.html_snapshot or "", 
                    result.url
                )
                
                learning_data.append({
                    'features': features,
                    'selectors': result.selectors_used,
                    'success': result.status == 'completed',
                    'response_time': result.response_time or 0,
                    'domain': self._extract_domain(result.url)
                })
        
        if not learning_data:
            logger.warning(f"No learning data available for session {session_id}")
            return self._get_default_metrics()
        
        # Update learned patterns
        self._update_learned_patterns(learning_data)
        
        # Retrain models if enough new data
        if len(learning_data) >= 10:
            self._retrain_models(learning_data)
        
        # Calculate learning metrics
        metrics = self._calculate_learning_metrics(learning_data)
        
        # Store performance history
        self.performance_history.append({
            'timestamp': datetime.now(),
            'session_id': session_id,
            'data_points': len(learning_data),
            'metrics': metrics
        })
        
        return metrics
    
    def get_domain_insights(self, domain: str) -> Dict[str, Any]:
        """Get comprehensive insights for a specific domain"""
        patterns = self.learned_patterns.get(domain, [])
        
        if not patterns:
            return {
                'domain': domain,
                'pattern_count': 0,
                'average_success_rate': 0.0,
                'recommended_selectors': [],
                'insights': ["No historical data available for this domain"]
            }
        
        # Calculate statistics
        success_rates = [p.success_rate for p in patterns]
        confidence_scores = [p.confidence for p in patterns]
        
        # Get top performing patterns
        top_patterns = sorted(patterns, key=lambda p: p.performance_score, reverse=True)[:5]
        
        insights = [
            f"Domain has {len(patterns)} learned patterns",
            f"Average success rate: {np.mean(success_rates):.1f}%",
            f"Average confidence: {np.mean(confidence_scores):.1f}%",
            f"Most successful selector type: {self._get_most_common_selector_type(patterns)}"
        ]
        
        return {
            'domain': domain,
            'pattern_count': len(patterns),
            'average_success_rate': np.mean(success_rates),
            'average_confidence': np.mean(confidence_scores),
            'recommended_selectors': [p.selector for p in top_patterns],
            'top_patterns': [{
                'selector': p.selector,
                'success_rate': p.success_rate,
                'confidence': p.confidence,
                'usage_count': p.usage_count
            } for p in top_patterns],
            'insights': insights
        }
    
    def detect_anomalies(self, session_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect anomalies in scraping session data"""
        if not session_data or not self.is_trained:
            return []
        
        # Prepare features for anomaly detection
        features = []
        for data in session_data:
            feature_vector = [
                data.get('response_time', 0),
                data.get('content_length', 0),
                data.get('success_rate', 0),
                len(data.get('selectors_used', [])),
                data.get('status_code', 200)
            ]
            features.append(feature_vector)
        
        if len(features) < 2:
            return []
        
        # Detect anomalies
        features_scaled = self.scaler.transform(features)
        anomaly_scores = self.anomaly_detector.decision_function(features_scaled)
        anomalies = self.anomaly_detector.predict(features_scaled)
        
        # Return anomalous data points
        anomalous_sessions = []
        for i, (data, score, is_anomaly) in enumerate(zip(session_data, anomaly_scores, anomalies)):
            if is_anomaly == -1:  # Anomaly detected
                anomalous_sessions.append({
                    'index': i,
                    'data': data,
                    'anomaly_score': float(score),
                    'reason': self._explain_anomaly(data, features[i])
                })
        
        return anomalous_sessions
    
    def generate_optimization_report(self, time_period_days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive optimization report"""
        cutoff_date = datetime.now() - timedelta(days=time_period_days)
        recent_history = [
            h for h in self.performance_history 
            if h['timestamp'] >= cutoff_date
        ]
        
        if not recent_history:
            return {
                'period': f"Last {time_period_days} days",
                'summary': "No data available for the specified period",
                'recommendations': []
            }
        
        # Calculate overall metrics
        total_sessions = len(recent_history)
        total_data_points = sum(h['data_points'] for h in recent_history)
        
        # Aggregate metrics
        avg_pattern_accuracy = np.mean([
            h['metrics'].pattern_accuracy for h in recent_history
        ])
        avg_learning_rate = np.mean([
            h['metrics'].learning_rate for h in recent_history
        ])
        
        # Generate recommendations
        recommendations = self._generate_system_recommendations(recent_history)
        
        # Domain performance analysis
        domain_performance = self._analyze_domain_performance()
        
        return {
            'period': f"Last {time_period_days} days",
            'summary': {
                'total_sessions_analyzed': total_sessions,
                'total_data_points': total_data_points,
                'average_pattern_accuracy': avg_pattern_accuracy,
                'average_learning_rate': avg_learning_rate,
                'model_training_status': 'Trained' if self.is_trained else 'Not Trained',
                'last_training': self.last_training_time.isoformat() if self.last_training_time else None
            },
            'domain_performance': domain_performance,
            'recommendations': recommendations,
            'learning_trends': self._calculate_learning_trends(recent_history)
        }
    
    # Private helper methods
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lower()
    
    def _extract_selector_patterns(self, selectors: List[str]) -> Counter:
        """Extract common patterns from selectors"""
        patterns = []
        for selector in selectors:
            # Extract tag names
            tags = re.findall(r'\b[a-z]+(?=\s|\.|#|\[|$)', selector)
            patterns.extend(tags)
            
            # Extract class patterns
            classes = re.findall(r'\.[a-zA-Z][a-zA-Z0-9_-]*', selector)
            patterns.extend([c[1:] for c in classes])  # Remove the dot
            
            # Extract ID patterns
            ids = re.findall(r'#[a-zA-Z][a-zA-Z0-9_-]*', selector)
            patterns.extend([i[1:] for i in ids])  # Remove the hash
        
        return Counter(patterns)
    
    def _generate_candidate_selectors(self, html_content: str) -> List[str]:
        """Generate candidate selectors from HTML content"""
        selectors = []
        
        # Common content selectors
        common_selectors = [
            'h1', 'h2', 'h3', 'p', 'div', 'span', 'a', 'img',
            '.content', '.main', '.article', '.post', '.title',
            '#content', '#main', '#article', '#post',
            '[data-content]', '[data-title]', '[data-text]',
            '.text', '.description', '.summary', '.excerpt'
        ]
        
        # Extract class and ID names from HTML
        classes = re.findall(r'class="([^"]+)"', html_content)
        ids = re.findall(r'id="([^"]+)"', html_content)
        
        # Add class-based selectors
        for class_attr in classes[:20]:  # Limit to avoid too many candidates
            class_names = class_attr.split()
            for class_name in class_names:
                if len(class_name) > 2:  # Avoid very short class names
                    selectors.append(f'.{class_name}')
        
        # Add ID-based selectors
        for id_name in ids[:10]:  # Limit to avoid too many candidates
            if len(id_name) > 2:
                selectors.append(f'#{id_name}')
        
        selectors.extend(common_selectors)
        return list(set(selectors))  # Remove duplicates
    
    def _score_selector(self, selector: str, domain_patterns: List[SelectorPattern], 
                       features: Dict[str, Any]) -> float:
        """Score a selector based on learned patterns and features"""
        base_score = 0.5  # Default score
        
        # Check against learned patterns
        for pattern in domain_patterns:
            if self._selectors_similar(selector, pattern.selector):
                base_score += pattern.performance_score * 0.3
        
        # Adjust based on selector type
        if selector.startswith('#'):  # ID selectors are generally more specific
            base_score += 0.2
        elif selector.startswith('.'):  # Class selectors are moderately specific
            base_score += 0.1
        
        # Adjust based on HTML features
        if 'div_count' in features and features['div_count'] > 50:
            if 'div' in selector:
                base_score -= 0.1  # Penalize div selectors on div-heavy pages
        
        return min(max(base_score, 0.0), 1.0)  # Clamp between 0 and 1
    
    def _selectors_similar(self, selector1: str, selector2: str) -> bool:
        """Check if two selectors are similar"""
        # Simple similarity check - can be enhanced
        return selector1 == selector2 or (
            selector1.replace(' ', '') == selector2.replace(' ', '')
        )
    
    def _generate_optimization_suggestions(self, features: Dict[str, Any], 
                                         patterns: List[SelectorPattern]) -> List[str]:
        """Generate optimization suggestions based on features and patterns"""
        suggestions = []
        
        if features.get('script_count', 0) > 10:
            suggestions.append("Consider using Selenium for JavaScript-heavy pages")
        
        if features.get('html_length', 0) > 100000:
            suggestions.append("Large HTML content detected - consider targeted selectors")
        
        if len(patterns) < 3:
            suggestions.append("Limited historical data - results may improve over time")
        
        if not features.get('is_https', True):
            suggestions.append("HTTP site detected - consider security implications")
        
        return suggestions
    
    def _estimate_success_rate(self, scored_selectors: List[Tuple[str, float]], 
                              patterns: List[SelectorPattern]) -> float:
        """Estimate success rate based on selector scores and patterns"""
        if not scored_selectors:
            return 0.5
        
        # Use average of top selector scores
        top_scores = [score for _, score in scored_selectors[:3]]
        base_rate = np.mean(top_scores)
        
        # Adjust based on historical patterns
        if patterns:
            historical_rate = np.mean([p.success_rate for p in patterns])
            base_rate = (base_rate + historical_rate) / 2
        
        return min(max(base_rate, 0.1), 0.95)  # Clamp between 10% and 95%
    
    def _estimate_response_time(self, features: Dict[str, Any]) -> float:
        """Estimate response time based on page features"""
        base_time = 1000  # Base 1 second
        
        # Adjust based on content size
        html_length = features.get('html_length', 0)
        if html_length > 50000:
            base_time += (html_length - 50000) * 0.01
        
        # Adjust based on complexity
        script_count = features.get('script_count', 0)
        if script_count > 5:
            base_time += script_count * 100
        
        return min(base_time, 10000)  # Cap at 10 seconds
    
    def _identify_risk_factors(self, features: Dict[str, Any], html_content: str) -> List[str]:
        """Identify potential risk factors for scraping"""
        risks = []
        
        if features.get('script_count', 0) > 20:
            risks.append("High JavaScript usage may require browser automation")
        
        if 'captcha' in html_content.lower():
            risks.append("CAPTCHA protection detected")
        
        if 'cloudflare' in html_content.lower():
            risks.append("Cloudflare protection may be present")
        
        if features.get('form_count', 0) > 5:
            risks.append("Multiple forms detected - may require authentication")
        
        return risks
    
    def _update_learned_patterns(self, learning_data: List[Dict[str, Any]]) -> None:
        """Update learned patterns based on new data"""
        for data in learning_data:
            domain = data['domain']
            selectors = data['selectors']
            success = data['success']
            
            for selector in selectors:
                # Find existing pattern or create new one
                existing_pattern = None
                for pattern in self.learned_patterns[domain]:
                    if pattern.selector == selector:
                        existing_pattern = pattern
                        break
                
                if existing_pattern:
                    # Update existing pattern
                    existing_pattern.usage_count += 1
                    existing_pattern.last_used = datetime.now()
                    # Update success rate with exponential moving average
                    alpha = 0.1
                    existing_pattern.success_rate = (
                        alpha * (100.0 if success else 0.0) + 
                        (1 - alpha) * existing_pattern.success_rate
                    )
                    existing_pattern.performance_score = (
                        existing_pattern.success_rate * existing_pattern.confidence / 100.0
                    )
                else:
                    # Create new pattern
                    new_pattern = SelectorPattern(
                        selector=selector,
                        confidence=50.0,  # Initial confidence
                        success_rate=100.0 if success else 0.0,
                        domain_pattern=domain,
                        content_type="general",
                        usage_count=1,
                        last_used=datetime.now(),
                        performance_score=50.0 if success else 0.0
                    )
                    self.learned_patterns[domain].append(new_pattern)
    
    def _retrain_models(self, learning_data: List[Dict[str, Any]]) -> None:
        """Retrain ML models with new data"""
        try:
            # Prepare training data
            X = []
            y = []
            
            for data in learning_data:
                features = data['features']
                feature_vector = [
                    features.get('html_length', 0),
                    features.get('tag_count', 0),
                    features.get('class_count', 0),
                    features.get('id_count', 0),
                    features.get('script_count', 0),
                    len(data.get('selectors', [])),
                    data.get('response_time', 0)
                ]
                X.append(feature_vector)
                y.append(1 if data['success'] else 0)
            
            if len(X) >= 10 and len(set(y)) > 1:  # Need minimum data and both classes
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42
                )
                
                # Fit scaler and transform data
                X_train_scaled = self.scaler.fit_transform(X_train)
                X_test_scaled = self.scaler.transform(X_test)
                
                # Train classifier
                self.selector_classifier.fit(X_train_scaled, y_train)
                
                # Train anomaly detector
                self.anomaly_detector.fit(X_train_scaled)
                
                # Update training status
                self.is_trained = True
                self.last_training_time = datetime.now()
                self.training_data_size = len(X)
                
                logger.info(f"Models retrained with {len(X)} data points")
            
        except Exception as e:
            logger.error(f"Error retraining models: {e}")
    
    def _calculate_learning_metrics(self, learning_data: List[Dict[str, Any]]) -> AdaptiveLearningMetrics:
        """Calculate adaptive learning metrics"""
        if not learning_data:
            return self._get_default_metrics()
        
        # Calculate success rate
        successes = sum(1 for data in learning_data if data['success'])
        pattern_accuracy = (successes / len(learning_data)) * 100
        
        # Calculate learning rate (improvement over time)
        learning_rate = min(len(learning_data) * 0.1, 10.0)  # Simple heuristic
        
        # Calculate adaptation speed
        unique_domains = len(set(data['domain'] for data in learning_data))
        adaptation_speed = min(unique_domains * 10, 100)
        
        # Calculate prediction confidence
        prediction_confidence = pattern_accuracy * 0.9  # Slightly lower than accuracy
        
        # Calculate optimization impact
        avg_response_time = np.mean([data.get('response_time', 1000) for data in learning_data])
        optimization_impact = max(100 - (avg_response_time / 10), 0)
        
        # Model stability (based on training status)
        model_stability = 90.0 if self.is_trained else 50.0
        
        return AdaptiveLearningMetrics(
            pattern_accuracy=pattern_accuracy,
            learning_rate=learning_rate,
            adaptation_speed=adaptation_speed,
            prediction_confidence=prediction_confidence,
            optimization_impact=optimization_impact,
            model_stability=model_stability
        )
    
    def _get_default_metrics(self) -> AdaptiveLearningMetrics:
        """Get default metrics when no data is available"""
        return AdaptiveLearningMetrics(
            pattern_accuracy=0.0,
            learning_rate=0.0,
            adaptation_speed=0.0,
            prediction_confidence=0.0,
            optimization_impact=0.0,
            model_stability=0.0
        )
    
    def _get_most_common_selector_type(self, patterns: List[SelectorPattern]) -> str:
        """Get the most common selector type from patterns"""
        types = []
        for pattern in patterns:
            if pattern.selector.startswith('#'):
                types.append('ID')
            elif pattern.selector.startswith('.'):
                types.append('Class')
            elif '[' in pattern.selector:
                types.append('Attribute')
            else:
                types.append('Tag')
        
        if types:
            return Counter(types).most_common(1)[0][0]
        return 'Unknown'
    
    def _explain_anomaly(self, data: Dict[str, Any], features: List[float]) -> str:
        """Explain why a data point is considered anomalous"""
        explanations = []
        
        response_time = data.get('response_time', 0)
        if response_time > 5000:
            explanations.append("Unusually high response time")
        
        success_rate = data.get('success_rate', 100)
        if success_rate < 50:
            explanations.append("Low success rate")
        
        status_code = data.get('status_code', 200)
        if status_code >= 400:
            explanations.append(f"HTTP error status: {status_code}")
        
        return "; ".join(explanations) if explanations else "Unusual pattern detected"
    
    def _generate_system_recommendations(self, history: List[Dict[str, Any]]) -> List[str]:
        """Generate system-level recommendations"""
        recommendations = []
        
        if len(history) < 10:
            recommendations.append("Collect more training data to improve ML accuracy")
        
        avg_accuracy = np.mean([h['metrics'].pattern_accuracy for h in history])
        if avg_accuracy < 80:
            recommendations.append("Consider reviewing and optimizing selector strategies")
        
        if not self.is_trained:
            recommendations.append("Train ML models to enable advanced predictions")
        
        return recommendations
    
    def _analyze_domain_performance(self) -> Dict[str, Any]:
        """Analyze performance across different domains"""
        domain_stats = {}
        
        for domain, patterns in self.learned_patterns.items():
            if patterns:
                avg_success = np.mean([p.success_rate for p in patterns])
                total_usage = sum(p.usage_count for p in patterns)
                
                domain_stats[domain] = {
                    'average_success_rate': avg_success,
                    'total_patterns': len(patterns),
                    'total_usage': total_usage,
                    'performance_score': avg_success * (total_usage / 100)
                }
        
        return domain_stats
    
    def _calculate_learning_trends(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate learning trends over time"""
        if len(history) < 2:
            return {'trend': 'insufficient_data'}
        
        # Sort by timestamp
        sorted_history = sorted(history, key=lambda x: x['timestamp'])
        
        # Calculate trend in pattern accuracy
        accuracies = [h['metrics'].pattern_accuracy for h in sorted_history]
        if len(accuracies) >= 2:
            trend = 'improving' if accuracies[-1] > accuracies[0] else 'declining'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'accuracy_change': accuracies[-1] - accuracies[0] if len(accuracies) >= 2 else 0,
            'data_points_trend': len(sorted_history)
        }