# AgentFlow

AgentFlow is an AI-powered platform for building, orchestrating, and managing workflow automations with intelligent agents. This MVP demonstrates a modular, cloud-native architecture built on Google Cloud Platform (GCP), following best practices in IaC, CI/CD, and agent-driven workflows.

## Structure

- `terraform/`: Infrastructure as Code for GCP resources
- `pipelines/`: Code and data pipelines (CI/CD, data ingestion, monitoring)
- `tools/`: Internal and external tool connectors (PDF parser, Vision API, etc.)
- `models/`: Model execution, prompt templates, Vertex AI runners
- `agents/`: Configurations and templates for intelligent agents
- `ui/`: Frontend and workflow builder placeholders
- `docs/`: Documentation (architecture, setup, workflows)

---

## Getting Started

1. Clone this repo
2. Review `terraform/` for cloud setup
3. Explore `pipelines/` for GCP pipeline configuration
4. See `docs/` for architecture and contribution guidelines

---
