---
name: hexagonal-architecture
description: Guidelines for implementing hexagonal architecture.
---

# Hexagonal Architecture

- Keep domain logic independent from frameworks, databases, APIs, and external services.
- Organize dependencies to point inward toward the domain and application layers.
- Use domain models for business concepts, rules, and invariants.
- Use application services/use cases to orchestrate workflows.
- Define interfaces/ports in the domain or application layer.
- Implement those interfaces in adapters.
- Keep infrastructure details inside adapters.
- Do not expose SQL rows, HTTP payloads, or external API formats to domain logic.
- Use mappers to convert between infrastructure models and domain models.
- Treat repositories as ports for persistence, not as places for business logic.
- Treat gateways/clients as ports for external systems and AI services.
- Keep controllers, CLIs, and APIs thin.
- Prefer explicit dependency injection over hidden global dependencies.
- Test domain and application logic without requiring databases or external services.
- Allow adapters to change without forcing changes in core business logic.
