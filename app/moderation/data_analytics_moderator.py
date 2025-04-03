from typing import Tuple

class DataAnalyticsModerator:
    """Moderator class to ensure requests are data analytics focused."""

    # Keywords that indicate data analytics related tasks
    DATA_ANALYTICS_KEYWORDS = {
        'analyze', 'analysis', 'data', 'dataset', 'statistics', 'metrics',
        'visualization', 'graph', 'chart', 'plot', 'correlation', 'regression',
        'mean', 'median', 'mode', 'average', 'trend', 'pattern', 'insight',
        'report', 'dashboard', 'excel', 'csv', 'pandas', 'numpy', 'matplotlib',
        'seaborn', 'aggregate', 'groupby', 'filter', 'sort', 'query',
        'calculate', 'compute', 'forecast', 'predict', 'classify',
        'summarize', 'distribution', 'outlier', 'clean', 'preprocess'
    }

    # Keywords that indicate non-data analytics tasks
    RESTRICTED_KEYWORDS = {
        'execute', 'run', 'install', 'download', 'upload', 'delete',
        'remove', 'system', 'os', 'shell', 'command', 'script',
        'network', 'web', 'http', 'api', 'request', 'browser',
        'selenium', 'automate', 'click', 'type', 'keyboard',
        'mouse', 'file', 'directory', 'path', 'create', 'modify'
    }

    @classmethod
    def is_data_analytics_request(cls, request: str) -> Tuple[bool, str]:
        """
        Check if the request is related to data analytics.
        
        Args:
            request: The user request string
            
        Returns:
            Tuple[bool, str]: (is_allowed, reason)
            - is_allowed: True if request is data analytics related
            - reason: Explanation of why request was allowed/denied
        """
        request_lower = request.lower()
        
        # Count matches with data analytics keywords
        analytics_matches = sum(1 for keyword in cls.DATA_ANALYTICS_KEYWORDS 
                              if keyword in request_lower)
        
        # Count matches with restricted keywords
        restricted_matches = sum(1 for keyword in cls.RESTRICTED_KEYWORDS 
                               if keyword in request_lower)
        
        # If there are more data analytics keywords and at least one match
        if analytics_matches > restricted_matches and analytics_matches > 0:
            return True, "Request appears to be data analytics related"
            
        # If there are restricted keywords but no data analytics keywords
        if restricted_matches > 0 and analytics_matches == 0:
            return False, "Request contains restricted operations without data analytics context"
            
        # If no keywords match at all
        if analytics_matches == 0 and restricted_matches == 0:
            return False, "Request does not appear to be related to data analytics"
            
        # If it's ambiguous (equal matches)
        if analytics_matches == restricted_matches:
            return False, "Request is ambiguous - please rephrase to focus on data analytics"
            
        return False, "Request not allowed - please focus on data analytics tasks"
