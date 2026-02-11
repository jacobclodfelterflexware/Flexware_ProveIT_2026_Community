#!/bin/bash

# Import Docker image into K3s containerd
# Run this script to make the locally built image available to Kubernetes

echo "Importing mqtt-topic-tree:latest into K3s..."

# Import from tar file
if [ -f /tmp/mqtt-topic-tree.tar ]; then
    echo "Using existing tar file..."
    sudo k3s ctr images import /tmp/mqtt-topic-tree.tar
else
    echo "Creating tar file from Docker image..."
    docker save mqtt-topic-tree:latest -o /tmp/mqtt-topic-tree.tar
    echo "Importing to K3s..."
    sudo k3s ctr images import /tmp/mqtt-topic-tree.tar
fi

echo ""
echo "Verifying image import..."
sudo k3s ctr images ls | grep mqtt-topic-tree

echo ""
echo "Restarting deployment to use imported image..."
kubectl rollout restart deployment/mqtt-topic-tree -n frontends

echo ""
echo "Done! Image imported successfully."
echo "Watch deployment status: kubectl get pods -n frontends -w"
