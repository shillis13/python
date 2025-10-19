# AI Persona State Management Models

## Overview
This document proposes data models and operational strategies for capturing an AI persona that begins with a minimal set of core values and progressively gains detailed preferences and opinions. The emphasis is on maintaining continuity in tone and decision-making while allowing the persona to grow richer over time.

## Layered State Architecture
Persona state is separated into hierarchical layers to balance stability with adaptability:

| Layer | Description | Update Cadence | Example Contents |
| --- | --- | --- | --- |
| Core Values | Immutable or slowly changing guiding principles provided at initialization. | Manual review only. | "Respect user autonomy", "Promote scientific literacy" |
| Anchored Beliefs | Durable positions derived from core values; change is rare and requires justification. | Triggered by explicit reviewer approval. | "Default to open standards when possible" |
| Preferences | Semi-stable likes/dislikes, used for default choices. | Periodic (weekly) automated review with moderation checkpoints. | "Prefers concise visualizations", "Prioritize cost-efficiency" |
| Situational Opinions | Short-lived stances formed during interactions; expire automatically. | Expire after TTL (hours–days); refreshed by consistent evidence. | "Current project favors Python" |
| Interaction Log | Optional record of notable interactions and adjustments, used for post-hoc analysis when needed. | Continuous. | "2024-05-08: Adopted preference for readable logging due to user feedback" |

## Schemas
### Core Data Structures
Using JSON Schema notation:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PersonaState",
  "type": "object",
  "required": ["metadata", "core_values", "anchored_beliefs", "preferences", "situational_opinions", "interaction_log"],
  "properties": {
    "metadata": {
      "type": "object",
      "required": ["persona_id", "version", "created_at", "updated_at"],
      "properties": {
        "persona_id": {"type": "string"},
        "version": {"type": "integer", "minimum": 1},
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"},
        "tags": {"type": "array", "items": {"type": "string"}}
      }
    },
    "core_values": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "statement", "rationale", "confidence"],
        "properties": {
          "id": {"type": "string"},
          "statement": {"type": "string"},
          "rationale": {"type": "string"},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1}
        }
      }
    },
    "anchored_beliefs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "statement", "alignment", "sources", "last_reviewed", "status"],
        "properties": {
          "id": {"type": "string"},
          "statement": {"type": "string"},
          "alignment": {
            "type": "array",
            "items": {"type": "string"}
          },
          "sources": {
            "type": "array",
            "items": {"type": "string", "format": "uri"}
          },
          "last_reviewed": {"type": "string", "format": "date-time"},
          "status": {"type": "string", "enum": ["active", "deprecated", "pending_review"]}
        }
      }
    },
    "preferences": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "dimension", "stance", "strength", "evidence"],
        "properties": {
          "id": {"type": "string"},
          "dimension": {"type": "string"},
          "stance": {"type": "string", "enum": ["like", "dislike", "neutral", "avoid", "favor"]},
          "strength": {"type": "number", "minimum": 0, "maximum": 1},
          "evidence": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["interaction_id", "summary", "weight", "timestamp"],
              "properties": {
                "interaction_id": {"type": "string"},
                "summary": {"type": "string"},
                "weight": {"type": "number", "minimum": -1, "maximum": 1},
                "timestamp": {"type": "string", "format": "date-time"}
              }
            }
          }
        }
      }
    },
    "situational_opinions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "topic", "position", "expires_at", "confidence"],
        "properties": {
          "id": {"type": "string"},
          "topic": {"type": "string"},
          "position": {"type": "string"},
          "expires_at": {"type": "string", "format": "date-time"},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1}
        }
      }
    },
    "interaction_log": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "timestamp", "type", "summary", "linked_entities"],
        "properties": {
          "id": {"type": "string"},
          "timestamp": {"type": "string", "format": "date-time"},
          "type": {"type": "string", "enum": ["observation", "update", "review"]},
          "summary": {"type": "string"},
          "linked_entities": {
            "type": "array",
            "items": {"type": "string"}
          },
          "attachments": {
            "type": "array",
            "items": {"type": "string", "format": "uri"}
          }
        }
      }
    }
  }
}
```

### Graph Overlay
Maintain a knowledge graph overlay for cross-referencing relationships:

- Nodes: values, beliefs, preferences, opinions, users, topics.
- Edges: `supports`, `conflicts_with`, `derived_from`, `supersedes`, `requested_by`.
- Each edge stores provenance metadata (timestamps, sources) and confidence scores.

## Update Rules
1. **Evidence Ingestion**
   - Each interaction adds an `observation` log entry.
   - Use weighted scoring to adjust preference strength: `new_strength = clamp(old_strength + learning_rate * weight, 0, 1)`.
   - Evidence older than a decay threshold decreases weight exponentially (`weight *= e^{-λΔt}`).

2. **Promotion/Demotion between Layers**
   - Promote preference → anchored belief when cumulative confidence exceeds threshold and conflicts are resolved.
   - Demote anchored belief → preference when evidence becomes stale or conflicts accumulate.
   - Promotions require human approval for safety-critical domains.

3. **TTL Expiration**
   - Situational opinions expire after `expires_at`; periodic job purges expired entries.
   - Opinions with consistent reinforcement can escalate into preferences with supervisory review.

4. **Versioning**
   - Increment `metadata.version` whenever core values or anchored beliefs change.
   - Maintain changelog referencing interaction IDs and reviewers.

## Conflict Resolution
1. **Detection**
   - Run graph cycle detection for incompatible edges (`conflicts_with`).
   - Evaluate contradictions via rule engine: e.g., opposing stances on same dimension with high strength.

2. **Resolution Strategies**
   - **Priority Ordering**: Core values > Anchored beliefs > Preferences > Opinions.
   - **Mediation Workflow**: Flag conflicts for human review when involving top two layers.
   - **Automatic Adjustment**: For lower layers, reduce strengths using softmax normalization across competing stances.
   - **Outcome Recording**: When an adjustment materially changes behavior, capture a short summary in the interaction log.

## Persistence Mechanics
- Store persona state in an append-only event stream (e.g., PostgreSQL + JSONB or Kafka log).
- Rebuild materialized views for current state using event-sourcing pattern.
- Snapshot current state periodically for fast retrieval, keeping version metadata for rollback when necessary.
- Provide lightweight access controls to ensure that persona mutations come from trusted services.

## Operational Guardrails
- **Change Budgeting**: Cap the number of automatic promotions or demotions per interval to keep shifts gradual.
- **Diversity Check**: Periodically audit that preferences draw from a variety of interaction sources to limit echo chambers.

## Expansion Workflow
1. Initialize persona with curated core values and baseline anchored beliefs.
2. Collect interaction evidence, tagging each with topic, sentiment, and quality score.
3. Run nightly batch job to recompute preferences, apply decay, detect conflicts, and queue pending promotions.
4. Present review dashboard summarizing proposed changes with rationales.
5. Upon approval, write signed update events, increment version, and notify dependent systems.

## Monitoring & Tuning
- Track metrics such as number of active beliefs, average preference strength, conflict rate, and time since last curator review.
- Alert on unexpected churn or drift beyond configurable limits so stewards can intervene early.
- Periodically sample interactions to verify that the persona still reflects the desired voice and objectives.
