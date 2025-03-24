# MCP Architecture in OpenManus

This document explains the architecture of the Model Context Protocol (MCP) implementation in OpenManus, focusing on the distinction between tools and resources.

## Overview

OpenManus uses the Model Context Protocol (MCP) to provide a structured way for Large Language Models (LLMs) to interact with external systems. The architecture distinguishes between two types of components:

1. **MCP Tools**: Active components that perform operations or actions
2. **MCP Resources**: Passive data sources that provide information

## Tools vs. Resources

### Tools

Tools are active components that can modify state or perform actions. They are used when the LLM needs to:

- Create, update, or delete data
- Interact with external systems
- Perform computations
- Execute commands

Examples in OpenManus:
- `mysql_rw`: MySQL read/write tool for creating tables and storing data
- `bash`: Execute shell commands
- `browser`: Control a web browser
- `editor`: Edit text files

### Resources

Resources are passive data sources that provide information without modifying external state. They are used when the LLM needs to:

- Retrieve information
- Query data
- Access reference material

Examples in OpenManus:
- `postgres_data`: Read-only PostgreSQL database access

## Benefits of the Distinction

1. **Clearer Intent**: The LLM understands when it's retrieving information vs. taking action
2. **Safety Boundaries**: Resources can be guaranteed read-only, reducing risk
3. **Memory Management**: Tools can be used for persistent storage while resources provide primary data
4. **Cognitive Framework**: Helps the LLM organize its thinking about available capabilities

## Implementation

In OpenManus, tools and resources are implemented as separate classes:

- `BaseTool`: Base class for all tools
- `BaseResource`: Base class for all resources

Both are registered with the MCP server but serve different conceptual purposes.

## Usage in LLM Context

When working with an LLM, you can structure prompts to leverage this distinction:

```
Available Resources (read-only):
- postgres_data: PostgreSQL database with customer records

Available Tools (can modify state):
- mysql_memory: MySQL database for storing checkpoints and memories

When you need information, first check relevant resources.
When you need to take action or store information, use appropriate tools.
```

This approach aligns with how humans think about information access vs. action, making LLM interactions more intuitive and safer.
