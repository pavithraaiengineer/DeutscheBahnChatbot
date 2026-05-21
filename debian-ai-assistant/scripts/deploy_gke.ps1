param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,

    [string]$Region = "europe-west1",
    [string]$Cluster = "debian-gke",
    [string]$Zone = "europe-west1-b"
)

$Image = "$Region-docker.pkg.dev/$ProjectId/debian/debian-ai-assistant:latest"

docker build -t $Image .
docker push $Image

gcloud container clusters get-credentials $Cluster --zone $Zone --project $ProjectId

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/microservices-map.yaml

Write-Host "Create/update secret from .env:"
Write-Host "kubectl create secret generic debian-secrets -n debian --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -"

(Get-Content k8s/deployment-api.yaml) -replace "PROJECT_ID", $ProjectId | kubectl apply -f -
kubectl apply -f k8s/service-api.yaml
kubectl apply -f k8s/hpa.yaml

kubectl get all -n debian
