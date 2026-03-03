# LLM RP Text-Only Project

## Overview

A research-driven RPG chat application where the game world, NPCs, rules, intentions, and interactions are **described and defined** — but actions and dialogues are **not scripted**. Instead, an LLM agent generates them dynamically at runtime.

## Core Idea

Traditional RPGs script NPC dialogue trees and player interactions. This project takes a different approach:

- **Define** the world: locations, NPCs, rules, relationships, intentions
- **Let the LLM generate** actions, dialogue, and narrative in real-time
- **Force the LLM** to actively discover world data via MCP tools rather than having everything pre-loaded (not RAG)

The goal is to research and validate whether this approach produces coherent, engaging RPG experiences.

## System Components

| Component | Tech | Purpose |
|-----------|------|---------|
| Backend (Agent) | FastAPI, Python 3.13, SQLite | LLM orchestration, MCP tools, world data |
| Backend (API) | FastAPI | Users, game states, chat histories |
| Backend (Admin API) | FastAPI | User management, world database management |
| User SPA | TypeScript, React, MobX, Vite | Player-facing chat interface |
| Admin SPA | TypeScript, React, MobX, Vite | World & user management interface |

## Key Architectural Decisions

- **MCP over RAG**: The LLM collects context via tool calls, not vector search
- **MCP tools are internal**: 100% in-process async functions, no external HTTP or bash
- **LLM backends**: Supports llama.cpp and OpenAI-compatible APIs via HTTP
- **Two SPAs**: User and Admin are separate apps sharing only the login flow
- **JWT authentication**: Stateless tokens shared across both SPAs
