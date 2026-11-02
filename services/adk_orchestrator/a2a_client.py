"""A2A Client for Google ADK Master Orchestrator.
Communicates with the CrewAI A2A Service over HTTP according to the A2A v1.0 specification.
"""
import os
from typing import Any, Dict, Optional
import httpx


CREWAI_A2A_URL = os.getenv("CREWAI_A2A_URL", "http://127.0.0.1:8001")


class A2AClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or CREWAI_A2A_URL).rstrip("/")
        self.agent_card: Optional[Dict[str, Any]] = None

    def discover_agent_card(self) -> Dict[str, Any]:
        """Fetches the Agent Card from the standard discovery path."""
        url = f"{self.base_url}/.well-known/agent-card.json"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            self.agent_card = resp.json()
            return self.agent_card

    def send_task(
        self,
        capability: str,
        workflow_id: str,
        payload: Dict[str, Any],
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatches a capability execution request to the CrewAI A2A service."""
        url = f"{self.base_url}/api/a2a/message/send"
        req_data = {
            "capability": capability,
            "workflow_id": workflow_id,
            "trace_id": trace_id,
            "payload": payload,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=req_data)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "ERROR":
                raise RuntimeError(f"CrewAI A2A execution failed: {data.get('error')}")
            return data.get("artifact", {})
