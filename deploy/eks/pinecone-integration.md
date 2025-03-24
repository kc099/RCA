# Integrating Pinecone Vector Database with OpenManus

This guide explains how to integrate Pinecone as a resource in OpenManus and deploy it on AWS EKS.

## 1. Create Pinecone Resource Class

First, create a new resource class for Pinecone:

```python
# app/resource/pinecone_data.py

import json
from typing import Dict, List, Optional, Any

import pinecone
from pinecone import Pinecone, ServerlessSpec

from app.logger import logger
from app.resource.base import BaseResource, ResourceResult


class PineconeResource(BaseResource):
    """Resource for accessing vector embeddings from Pinecone."""

    name: str = "pinecone_data"
    description: str = "Access vector embeddings from Pinecone vector database."

    # Connection parameters
    _pc: Optional[Pinecone] = None
    _index: Optional[Any] = None
    _connection_params: Dict[str, Any] = {}

    def __init__(self):
        """Initialize the Pinecone resource."""
        super().__init__(
            name="pinecone_data",
            description="Access vector embeddings from Pinecone vector database."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "query_vector": {
                    "type": "array",
                    "description": "Vector embedding to query",
                    "items": {"type": "number"},
                },
                "filter": {
                    "type": "object",
                    "description": "Optional metadata filter",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return",
                },
                "include_metadata": {
                    "type": "boolean",
                    "description": "Whether to include metadata in results",
                },
                "namespace": {
                    "type": "string",
                    "description": "Optional namespace to query",
                },
            },
            "required": ["query_vector"],
        }

    async def initialize(
        self,
        api_key: str,
        environment: str = "gcp-starter",
        index_name: str = "openmanus-index",
        dimension: int = 1536,
        metric: str = "cosine",
        create_if_not_exists: bool = True,
    ) -> None:
        """Initialize the connection to Pinecone.
        
        Args:
            api_key: Pinecone API key
            environment: Pinecone environment
            index_name: Name of the Pinecone index
            dimension: Dimension of the vectors
            metric: Distance metric (cosine, dotproduct, euclidean)
            create_if_not_exists: Whether to create the index if it doesn't exist
        """
        # Store connection parameters for reconnection
        self._connection_params = {
            "api_key": api_key,
            "environment": environment,
            "index_name": index_name,
            "dimension": dimension,
            "metric": metric,
            "create_if_not_exists": create_if_not_exists
        }
        
        try:
            logger.info(f"Connecting to Pinecone, environment: {environment}, index: {index_name}")
            
            # Initialize Pinecone client
            self._pc = Pinecone(api_key=api_key)
            
            # Check if index exists
            index_list = self._pc.list_indexes()
            
            if index_name not in index_list.names() and create_if_not_exists:
                logger.info(f"Creating Pinecone index: {index_name}")
                # Create a serverless index
                self._pc.create_index(
                    name=index_name,
                    dimension=dimension,
                    metric=metric,
                    spec=ServerlessSpec(cloud="aws", region="us-west-2")
                )
            
            # Connect to the index
            self._index = self._pc.Index(index_name)
            
            # Test connection with a simple stats query
            stats = self._index.describe_index_stats()
            logger.info(f"Successfully connected to Pinecone index: {index_name}, total vectors: {stats.get('total_vector_count', 0)}")
            
            return ResourceResult(output=f"Successfully connected to Pinecone index: {index_name}")
        except Exception as e:
            error_msg = f"Failed to connect to Pinecone: {str(e)}"
            logger.error(error_msg)
            return ResourceResult(error=error_msg)

    async def access(
        self, 
        query_vector: List[float], 
        filter: Optional[Dict] = None, 
        top_k: int = 10,
        include_metadata: bool = True,
        namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query the Pinecone index for similar vectors.

        Args:
            query_vector: Vector embedding to query
            filter: Optional metadata filter
            top_k: Number of results to return
            include_metadata: Whether to include metadata in results
            namespace: Optional namespace to query

        Returns:
            Dict with query results or error message.
        """
        # Check if connection exists and reconnect if needed
        if not self._pc or not self._index:
            try:
                logger.info("Pinecone connection not initialized. Reconnecting...")
                await self.initialize(**self._connection_params)
            except Exception as e:
                logger.error(f"Failed to reconnect to Pinecone: {str(e)}")
                return {"error": f"Error reconnecting to Pinecone: {str(e)}"}

        try:
            # Query the index
            query_params = {
                "vector": query_vector,
                "top_k": top_k,
                "include_metadata": include_metadata,
            }
            
            if filter:
                query_params["filter"] = filter
                
            if namespace:
                query_params["namespace"] = namespace
                
            results = self._index.query(**query_params)
            
            # Format the results
            formatted_results = {
                "matches": []
            }
            
            for match in results.get("matches", []):
                formatted_match = {
                    "id": match.get("id"),
                    "score": match.get("score"),
                }
                
                if include_metadata and "metadata" in match:
                    formatted_match["metadata"] = match.get("metadata")
                    
                formatted_results["matches"].append(formatted_match)
                
            return {"output": json.dumps(formatted_results, indent=2)}
        except Exception as e:
            logger.error(f"Error querying Pinecone: {str(e)}")
            return {"error": f"Error querying Pinecone: {str(e)}"}

    async def cleanup(self) -> None:
        """Clean up resources when resource is no longer needed."""
        # Pinecone doesn't require explicit cleanup
        logger.info("Pinecone resource cleaned up")
        self._pc = None
        self._index = None
```

## 2. Update Kubernetes Secrets for Pinecone

Add Pinecone API key to your Kubernetes secrets:

```yaml
# deploy/eks/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
stringData:
  mysql-host: "68.178.150.182"
  mysql-user: "kc099"
  mysql-password: "Roboworks23!"
  mysql-database: "testdata"
  postgres-host: "postgres-service"
  postgres-user: "postgres"
  postgres-password: "12345"
  postgres-database: "postgres"
  pinecone-api-key: "YOUR_PINECONE_API_KEY"
  pinecone-environment: "gcp-starter"
  pinecone-index: "openmanus-index"
```

## 3. Update the MCPServer to Register Pinecone Resource

Modify the server.py file to include the Pinecone resource:

```python
# app/mcp/server.py (partial)
from app.resource.pinecone_data import PineconeResource

class MCPServer:
    # ...existing code...
    
    def __init__(self, name: str = "openmanus"):
        # ...existing code...
        
        # Initialize resources
        self.resources["postgres_data"] = PostgreSQLResource()
        self.resources["pinecone_data"] = PineconeResource()
    
    # ...existing code...
    
    async def register_all_resources(self) -> None:
        """Register all resources with the server."""
        # Initialize resources
        postgres_resource = PostgreSQLResource()
        pinecone_resource = PineconeResource()
        
        # Register resources with the agent
        self.register_resource(postgres_resource)
        self.register_resource(pinecone_resource)
        
        # Initialize PostgreSQL resource
        await postgres_resource.initialize(
            host="127.0.0.1",
            port=5432,
            user="postgres",
            password="12345",
            database="postgres",
            max_rows=100
        )
        
        # Initialize Pinecone resource
        await pinecone_resource.initialize(
            api_key=os.environ.get("PINECONE_API_KEY", ""),
            environment=os.environ.get("PINECONE_ENVIRONMENT", "gcp-starter"),
            index_name=os.environ.get("PINECONE_INDEX", "openmanus-index"),
            dimension=1536,  # OpenAI embedding dimension
            metric="cosine",
            create_if_not_exists=True
        )
```

## 4. Update Deployment to Include Pinecone Environment Variables

```yaml
# deploy/eks/deployment.yaml (partial)
containers:
- name: openmanus
  image: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/openmanus:latest
  # ...existing configuration...
  env:
  # ...existing environment variables...
  - name: PINECONE_API_KEY
    valueFrom:
      secretKeyRef:
        name: db-credentials
        key: pinecone-api-key
  - name: PINECONE_ENVIRONMENT
    valueFrom:
      secretKeyRef:
        name: db-credentials
        key: pinecone-environment
  - name: PINECONE_INDEX
    valueFrom:
      secretKeyRef:
        name: db-credentials
        key: pinecone-index
```

## 5. Install Pinecone SDK in Requirements

Add the Pinecone SDK to your requirements.txt file:

```
# requirements.txt (append to existing requirements)
pinecone-client>=2.2.1
```

## 6. Example Usage in LLM Context

When working with an LLM, you can now use Pinecone as a resource:

```
Available Resources (read-only):
- postgres_data: PostgreSQL database with customer records
- pinecone_data: Vector database for semantic search

Available Tools (can modify state):
- mysql_memory: MySQL database for storing checkpoints and memories

When you need to perform semantic search, use the pinecone_data resource.
```

## 7. Deployment Considerations

### Scaling with Vector Search

- Pinecone serverless automatically scales based on your usage
- For high-volume applications, consider using Pinecone's dedicated service tier
- Monitor your Pinecone usage and costs through the Pinecone dashboard

### Performance Optimization

- Batch vector operations when possible
- Use metadata filtering to reduce the search space
- Consider using hybrid search (combining vector search with keyword search) for better results

### Security Best Practices

- Rotate your Pinecone API keys regularly
- Use IAM roles with least privilege for AWS resources
- Keep your vector database isolated in a private subnet when possible
