# deploy/dependencies.md (Prerequisite Software Checklist)

The following software must be available in the cluster or infrastructure prior to deployment.

| Dependency | Purpose | Target Version |
|------------|---------|----------------|
| **Kubernetes Cluster** | App hosting & execution | `>= 1.25` |
| **PostgreSQL DB** | Persistent Thread checkpointer and VFS | `>= 15.0` |
| **Ingress Controller** | Routing external HTTP traffic | NGINX / Traefik |
| **API Keys** | OpenAI, Anthropic, or Gemini | Valid LLM Provider keys |
| **Opik Observability** | Trace logging (Optional) | Comet Opik / Self-hosted instance |
