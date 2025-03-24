# Deploying OpenManus on AWS EKS

This guide provides step-by-step instructions for deploying OpenManus on Amazon EKS (Elastic Kubernetes Service).

## Prerequisites

- AWS CLI installed and configured
- kubectl installed
- eksctl installed
- Docker installed
- Access to an AWS account with appropriate permissions

## Deployment Steps

### 1. Create an EKS Cluster

```bash
eksctl create cluster \
  --name openmanus-cluster \
  --region us-east-1 \
  --nodegroup-name standard-nodes \
  --node-type t3.medium \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 3 \
  --managed
```

### 2. Create an ECR Repository

```bash
aws ecr create-repository --repository-name openmanus
```

### 3. Build and Push the Docker Image

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

# Build the Docker image
docker build -t openmanus .

# Tag the image
docker tag openmanus:latest ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/openmanus:latest

# Push the image to ECR
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/openmanus:latest
```

### 4. Update the Kubernetes Manifests

Update the `deployment.yaml` file with your AWS account ID and region:

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
envsubst < deployment.yaml > deployment-updated.yaml
```

### 5. Deploy the Application

```bash
# Create the Kubernetes secrets
kubectl apply -f secrets.yaml

# Deploy PostgreSQL (if using the in-cluster PostgreSQL)
kubectl apply -f postgres-pvc.yaml
kubectl apply -f postgres-deployment.yaml
kubectl apply -f postgres-service.yaml

# Deploy OpenManus
kubectl apply -f deployment-updated.yaml
kubectl apply -f service.yaml
```

### 6. Verify the Deployment

```bash
# Check the deployment status
kubectl get deployments

# Check the pods
kubectl get pods

# Check the services
kubectl get services
```

### 7. Access the Application

Once the LoadBalancer service is provisioned, you can access the application using the external IP:

```bash
kubectl get services openmanus
```

Use the EXTERNAL-IP value to access your application.

## Adapting for HTTP Transport

The default OpenManus setup uses stdio for communication. To use HTTP transport:

1. Modify the `run_mcp.py` file to support HTTP transport
2. Update the Dockerfile to expose the appropriate port
3. Update the Kubernetes service to target the correct port

## Integrating with Pinecone

To integrate with Pinecone in the future:

1. Create a Pinecone account and get your API key
2. Add the Pinecone API key to your Kubernetes secrets
3. Create a new resource class for Pinecone in your OpenManus application
4. Register the Pinecone resource in your MCP server

## Monitoring and Scaling

- Use AWS CloudWatch for monitoring your EKS cluster
- Set up Horizontal Pod Autoscaler (HPA) for automatic scaling
- Configure cluster autoscaling for node-level scaling

## Cleanup

To delete the EKS cluster when you're done:

```bash
eksctl delete cluster --name openmanus-cluster --region us-east-1
```
