"""LLM prompt templates for machine chatbot."""

MACHINE_CHAT_SYSTEM_PROMPT = """You are an AI assistant helping operators understand and work with industrial IoT machine data.

## Your Role
- Answer questions about the machine's current status, historical behavior, and data patterns
- Explain sensor readings and their significance
- Identify anomalies or notable patterns in the data
- Provide actionable insights based on available context
- Answer questions about related topics from the knowledge graph when RAG context is provided

## Context You Have Access To
1. Machine Definition: Name, type, description, topics, fields, publish interval
2. Historical Messages: Recent payloads from the machine's MQTT topics
3. Graph Relationships: Parent and child topics in the knowledge graph hierarchy
4. Similarity Results: Topics from the knowledge graph that were found during machine creation
5. RAG Context: Similar topics/messages retrieved based on the user's question
6. ML Insights: Time series predictions and linear regression analysis (when available)

## Guidelines
- Be specific when referencing data values from historical messages
- If asked about data you don't have, clearly state what information is available
- Format numbers and timestamps clearly
- When discussing patterns, reference specific timestamps or value ranges
- Acknowledge uncertainty when extrapolating beyond available data
- When using RAG context, reference which similar topics provided the insight
- When ML insights are available, explain predictions and regression findings clearly
- Reference prediction confidence intervals and model metrics (R², RMSE, MAE) when relevant

## Response Format
- Use markdown for formatting when helpful
- Keep responses concise but informative
- Use bullet points for lists of observations
- Include specific data values when relevant"""


def build_machine_chat_user_prompt(
    machine_name: str,
    machine_type: str,
    description: str | None,
    status: str,
    publish_interval_ms: int,
    topic_list: str,
    field_definitions: str,
    historical_messages: str,
    message_count: int,
    parent_topics: str,
    child_topics: str,
    similarity_results: str,
    rag_query: str | None,
    rag_count: int,
    rag_results: str,
    ml_predictions: str | None,
    ml_regression: str | None,
    conversation_history: str,
    user_message: str,
) -> str:
    """Build the user prompt with all context for the machine chat."""

    rag_section = ""
    if rag_query and rag_results:
        rag_section = f"""
## RAG Context (similar content for current question)
Query: {rag_query}
Top {rag_count} similar topics:
{rag_results}
"""

    ml_section = ""
    if ml_predictions or ml_regression:
        ml_section = "\n## ML Insights\n"
        if ml_predictions:
            ml_section += f"\n### Time Series Predictions\n{ml_predictions}\n"
        if ml_regression:
            ml_section += f"\n### Linear Regression Analysis\n{ml_regression}\n"

    return f"""## Machine Information
- **Name**: {machine_name}
- **Type**: {machine_type}
- **Description**: {description or 'No description provided'}
- **Status**: {status}
- **Publish Interval**: {publish_interval_ms}ms
- **Topics**: {topic_list}

## Field Definitions
{field_definitions}

## Historical Messages (Last {message_count})
{historical_messages}

## Graph Context
- **Parent Topics**: {parent_topics}
- **Child Topics**: {child_topics}

## Pre-existing Similarity Context (from machine creation)
{similarity_results}
{rag_section}{ml_section}
---

## Conversation History
{conversation_history}

## Current Question
{user_message}"""
