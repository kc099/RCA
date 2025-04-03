"""
Data Analytics Filter Module

This module provides filtering capabilities to identify and validate
data analytics related queries.
"""

from typing import Dict, List, Optional, Set, Tuple
import re

class DataAnalyticsFilter:
    """Filter class to identify data analytics related queries."""

    # Default keywords indicating data analytics tasks
    DEFAULT_ANALYTICS_KEYWORDS: Set[str] = {
        'analyze', 'analysis', 'data', 'dataset', 'statistics', 'metrics',
        'visualization', 'graph', 'chart', 'plot', 'correlation', 'regression',
        'mean', 'median', 'mode', 'average', 'trend', 'pattern', 'insight',
        'report', 'dashboard', 'excel', 'csv', 'pandas', 'numpy', 'matplotlib',
        'seaborn', 'aggregate', 'groupby', 'filter', 'sort', 'query',
        'calculate', 'compute', 'forecast', 'predict', 'classify',
        'summarize', 'distribution', 'outlier', 'clean', 'preprocess', 'who', 'are', 'you'
    }

    # Default keywords indicating non-analytics tasks
    DEFAULT_NON_ANALYTICS_KEYWORDS: Set[str] = {
        'execute', 'run', 'install', 'download', 'upload', 'delete',
        'remove', 'system', 'os', 'shell', 'command', 'script',
        'network', 'web', 'http', 'api', 'request', 'browser',
        'selenium', 'automate', 'click', 'type', 'keyboard',
        'mouse', 'file', 'directory', 'path', 'create', 'modify'
    }

    def __init__(
        self,
        custom_analytics_keywords: Optional[List[str]] = None,
        custom_non_analytics_keywords: Optional[List[str]] = None,
        threshold: float = 0.6
    ):
        """
        Initialize the filter with optional custom keywords.

        Args:
            custom_analytics_keywords: Additional analytics keywords
            custom_non_analytics_keywords: Additional non-analytics keywords
            threshold: Minimum score ratio required for analytics classification
        """
        self.analytics_keywords = self.DEFAULT_ANALYTICS_KEYWORDS.copy()
        self.non_analytics_keywords = self.DEFAULT_NON_ANALYTICS_KEYWORDS.copy()
        self.threshold = threshold

        # Add custom keywords if provided
        if custom_analytics_keywords:
            self.analytics_keywords.update(custom_analytics_keywords)
        if custom_non_analytics_keywords:
            self.non_analytics_keywords.update(custom_non_analytics_keywords)

    def is_data_analytics_query(self, query: str) -> Tuple[bool, Dict]:
        """
        Determine if a query is related to data analytics.

        Args:
            query: The query string to analyze

        Returns:
            Tuple containing:
            - Boolean indicating if query is analytics related
            - Dictionary containing analysis details
        """
        query_lower = query.lower()
        words = set(re.findall(r'\w+', query_lower))

        # Count keyword matches
        analytics_matches = words.intersection(self.analytics_keywords)
        non_analytics_matches = words.intersection(self.non_analytics_keywords)

        analytics_score = len(analytics_matches)
        non_analytics_score = len(non_analytics_matches)
        total_words = len(words)

        # Calculate ratios
        analytics_ratio = analytics_score / total_words if total_words > 0 else 0
        non_analytics_ratio = non_analytics_score / total_words if total_words > 0 else 0

        # Prepare analysis results
        analysis = {
            "analytics_matches": list(analytics_matches),
            "non_analytics_matches": list(non_analytics_matches),
            "analytics_score": analytics_score,
            "non_analytics_score": non_analytics_score,
            "analytics_ratio": analytics_ratio,
            "non_analytics_ratio": non_analytics_ratio,
            "total_words": total_words,
            "threshold": self.threshold
        }

        # Determine if query is analytics related
        is_analytics = (
            analytics_ratio >= self.threshold and
            analytics_ratio > non_analytics_ratio
        )

        return is_analytics, analysis

    def get_rejection_message(self, query: str, analysis: Dict) -> str:
        """
        Generate a helpful rejection message for non-analytics queries.

        Args:
            query: The original query
            analysis: Analysis results from is_data_analytics_query

        Returns:
            A formatted rejection message with explanation
        """
        message = (
            "I apologize, but I'm specialized in data analytics tasks only. "
            "Your request appears to be outside my scope.\n\n"
        )

        if analysis["non_analytics_matches"]:
            message += (
                "I noticed terms that suggest non-analytics operations: "
                f"{', '.join(analysis['non_analytics_matches'])}.\n"
            )

        message += (
            "\nTo help you better, could you rephrase your request to focus on "
            "data analysis? For example, you could ask about:\n"
            "- Analyzing datasets\n"
            "- Creating visualizations\n"
            "- Computing statistics\n"
            "- Finding patterns or trends\n"
            "- Generating reports"
        )

        return message
