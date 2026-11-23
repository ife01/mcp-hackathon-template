# Deployment options

The demonstrated RSA workflow uses the [local wxO MCP toolkit](ibm/local-mcp-toolkit/README.md).
It runs the server over stdio inside watsonx Orchestrate.
Start with the [agent setup guide](../docs/WXO_AGENT_SETUP.md) and apply the current agent policy.

## Other deployment options

| Option | Purpose | Guide |
| --- | --- | --- |
| IBM Code Engine, build from Git | Build and host a container from your repository | [Git build](ibm/code-engine-git-build/README.md) |
| IBM Code Engine, prebuilt image | Host an existing container image | [Prebuilt image](ibm/prebuilt-image/README.md) |
| Local container | Run the HTTP server in a container | [Project README](../README.md) and [Dockerfile](../Dockerfile) |
| cloud.gov | Deploy with the Python buildpack | Comments in [manifest.yaml](../manifest.yaml) |

These options run the same server code. Their guides do not establish a public production deployment.
The dated [verification record](../docs/VERIFICATION.md) identifies the checks that were performed.

## Configuration and access

Use each kit's `.env.example` for deployment configuration. Keep credentials outside Git.
When you fork the project, update repository URLs and image names for your organization.

The server uses stdio by default. A platform port or explicit transport configuration enables HTTP.
The HTTP server has no built-in authentication. Restrict network access or add platform authentication before sharing an endpoint.
See [security and data handling](../SECURITY.md) before deployment.
