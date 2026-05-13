# social-app Helm chart

Manages the Kubernetes workloads for the social-app microservices.  
Terraform owns the EKS cluster; this chart owns everything inside it.

## Directory layout

```
helm/social-app/
├── Chart.yaml
├── values.yaml            ← defaults (commit this)
├── values-production.yaml ← prod overrides (commit this, no secrets)
└── templates/
    ├── namespace.yaml
    ├── pull-secret.yaml   ← GHCR imagePullSecret
    ├── deployment.yaml    ← auth / post / feed Deployments
    └── service.yaml       ← auth / post / feed NodePort Services
```

## First-time install (local / CI)

```bash
# 1. Point kubectl at the cluster
aws eks update-kubeconfig --region us-east-1 --name yasna-localstack-cluster

# 2. Deploy (supply GHCR PAT at runtime — never commit it)
helm upgrade --install social-app helm/social-app \
  --set imagePullSecret.password=$GHCR_PAT \
  --wait
```

## Updating a service image

Edit `values.yaml` (or a per-env override file) and run the same
`helm upgrade` command. Helm diffs and only restarts affected pods.

## GitHub Actions snippet

```yaml
- name: Deploy via Helm
  run: |
    aws eks update-kubeconfig --region ${{ env.AWS_REGION }} \
      --name ${{ steps.tf-output.outputs.eks_cluster_name }}
    helm upgrade --install social-app helm/social-app \
      --set imagePullSecret.password=${{ secrets.GHCR_PAT }} \
      --wait
```

## Adding a new service

1. Add an entry under `services:` in `values.yaml`.
2. Run `helm upgrade` — no template changes needed.
