---
name: graph-project
description: Guidelines and principles for the Graph Data Platform.
---

# Graph Project

- The Graph Data Platform is an open-source alternative to proprietary research information systems such as Elsevier Pure.
- The platform federates institutional and educational data into a semantically interconnected knowledge graph.
- Core entities include people, publications, labs, startups, courses, lectures, concepts, categories, and other educational resources.
- GraphSearch provides search, recommendations, and discovery over the knowledge graph.
- GraphChat provides conversational access to the knowledge graph through RAG and LLM technologies.

## Platform Services

- Graph Registry
- Graph AI
- Graph Ontology
- Graph Search
- Graph Chat
- Graph DB Client
- Graph ES Client

## Graph Registry

- Graph Registry is the first layer of the platform.
- It ingests structured data and constructs the knowledge graph.
- Data can be imported from JSON files or through a REST API.
- Graph construction workflows are executed through a Python CLI.
- The Registry is the system of record for graph entities and relationships.

## Graph AI

- Graph AI provides semantic analysis and LLM-powered capabilities.
- It is responsible for text processing, concept detection, entity linking, enrichment, summarization, translation, and related AI workflows.
- It supports Graph Registry, Graph Chat, and RAG pipelines.

## Graph Ontology

- Graph Ontology provides the platform's semantic backbone.
- It contains a large concepts graph derived from tens of thousands of Wikipedia concepts.
- It maintains hierarchical category trees and concept relationships.
- It enables entity recognition, concept detection, semantic search, recommendations, and knowledge discovery.
- Ontology structures are shared across all platform services.

## Graph Search

- Graph Search is the search and recommendation engine.
- It enables navigation and discovery across graph entities and relationships.
- It uses Elasticsearch indexes derived from the knowledge graph.

## Graph Chat

- Graph Chat is a RAG-LLM interface built on top of the knowledge graph and search infrastructure.
- It allows conversational interaction with institutional knowledge and educational resources.

## Graph DB Client

- Graph DB Client is a Python CLI for managing MySQL infrastructure and data operations.
- It supports configuration management, import/export workflows, and database administration tasks.

## Graph ES Client

- Graph ES Client is a Python CLI for managing Elasticsearch infrastructure and indexes.
- It supports index creation, maintenance, import/export workflows, and administrative operations.

## Engineering Principles

- Prefer semantic graph relationships over ad-hoc joins when domain meaning is important.
- Preserve clear separation between Registry, AI, Ontology, Search, and Chat responsibilities.
- Reuse ontology concepts and categories whenever semantic classification is required.
- Treat the knowledge graph as the authoritative source of relationships between entities.
- Design components to support both search-based and LLM-based retrieval workflows.
