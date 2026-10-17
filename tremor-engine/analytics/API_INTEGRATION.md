# Quell Analytics API Integration Guide

Welcome team! This document outlines the available FastAPI endpoints for the Quell tremor-management analytics engine. The server runs locally at `http://127.0.0.1:8000`.

Interactive Swagger documentation can be viewed live at: `http://127.0.0.1:8000/docs`

---

## Base URL
`http://127.0.0.1:8000`

---

## Endpoints

### 1. Root Status
* **Endpoint:** `GET /`
* **Description:** Verifies that the analytics engine is online and returns the team roster.
* **Response Example:**
```json
{
  "status": "Quell Analytics Engine is online",
  "team": ["Minna", "Niya", "Shreya", "Aisha"]
}
