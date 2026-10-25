"""Agent Registry and Governance Policies for the Pixel Astro agent (Lab 3).

    export GOOGLE_CLOUD_PROJECT=ai-devcamp-lab   # read from the environment, not .env
    uv run python governance.py registry-agents
    uv run python governance.py registry-search "bigquery"
    uv run python governance.py engine             # policy engine state
    uv run python governance.py provision          # once, ~3 min; never deprovision
    uv run python governance.py create "<constraint>" --name <policy-id>
    uv run python governance.py list

Policies and the policy engine exist only in us-central1. A policy names an
agent in Agent Registry and is resolved to that agent's identity principal.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import google.auth
from google.auth.transport.requests import AuthorizedSession

LOCATION = "us-central1"
REGISTRY = "https://agentregistry.googleapis.com/v1"
AIPLATFORM = f"https://{LOCATION}-aiplatform.googleapis.com/v1"
AGENT_DISPLAY_NAME = "pixel-astro-agent"


def _session() -> AuthorizedSession:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return AuthorizedSession(credentials)


def _call(method: str, url: str, **kwargs) -> dict:
    resp = _session().request(method, url, timeout=60, **kwargs)
    if resp.status_code >= 400:
        sys.exit(f"{method} {url} -> {resp.status_code}: {resp.text[:500]}")
    return resp.json() if resp.content else {}


def _parent(project: str) -> str:
    return f"projects/{project}/locations/{LOCATION}"


def registry_agents(project: str) -> list[dict]:
    agents = _call("GET", f"{REGISTRY}/{_parent(project)}/agents", params={"pageSize": 100})
    return agents.get("agents", [])


def find_agent(project: str, display_name: str = AGENT_DISPLAY_NAME) -> dict:
    for agent in registry_agents(project):
        if agent.get("displayName") == display_name:
            return agent
    sys.exit(f"{display_name} is not in Agent Registry; deploy it with --agent-identity first.")


def cmd_registry_agents(project: str, _args) -> None:
    for agent in registry_agents(project):
        protocols = ", ".join(p.get("type", "?") for p in agent.get("protocols", []))
        print(f"{agent.get('displayName')}\n  {agent['name']}\n  {agent.get('agentId')}  [{protocols}]")


def cmd_registry_search(project: str, args) -> None:
    found = _call(
        "POST",
        f"{REGISTRY}/projects/{project}/locations/global/mcpServers:search",
        json={"searchString": args.query},
    )
    for server in found.get("mcpServers", []):
        tools = server.get("tools", [])
        urls = ", ".join(i["url"] for i in server.get("interfaces", []))
        print(f"{server.get('displayName')}  ({len(tools)} tools)  {urls}\n  {server.get('description', '')}")


def cmd_engine(project: str, _args) -> None:
    print(json.dumps(_call("GET", f"{AIPLATFORM}/{_parent(project)}/semanticGovernancePolicyEngine"), indent=2))


def cmd_provision(project: str, _args) -> None:
    url = f"{AIPLATFORM}/{_parent(project)}/semanticGovernancePolicyEngine"
    state = _call("GET", url).get("state")
    if state != "INACTIVE":
        sys.exit(f"Policy engine is {state}; not provisioning again (never retry or deprovision).")
    operation = _call("PATCH", url, json={})
    print(f"Provisioning started (~3 min): {operation.get('name')}\nCheck with: governance.py engine")


def cmd_create(project: str, args) -> None:
    agent = find_agent(project)
    body = {
        "displayName": args.name,
        "agent": agent["name"],
        "naturalLanguageConstraint": args.constraint,
        "dryRun": args.dry_run,
    }
    if args.denial_message:
        body["agentResponseCustomization"] = {"denialMessage": args.denial_message}
    operation = _call(
        "POST",
        f"{AIPLATFORM}/{_parent(project)}/semanticGovernancePolicies",
        params={"semanticGovernancePolicyId": args.name},
        json=body,
    )
    print(f"Creating policy {args.name}: {operation.get('name')}")


def cmd_list(project: str, _args) -> None:
    policies = _call("GET", f"{AIPLATFORM}/{_parent(project)}/semanticGovernancePolicies")
    for policy in policies.get("semanticGovernancePolicies", []):
        print(f"{policy['name'].rsplit('/', 1)[-1]}  (dry run: {policy.get('dryRun', False)})")
        print(f"  constraint: {policy.get('naturalLanguageConstraint')}")
        print(f"  agent:      {policy.get('agent')}")
        print(f"  identity:   {policy.get('agentIdentity')}")
        if denial := policy.get("agentResponseCustomization", {}).get("denialMessage"):
            print(f"  denial:     {denial}")


def main() -> None:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        sys.exit("Set GOOGLE_CLOUD_PROJECT (the project ID).")
    parser = argparse.ArgumentParser(description="Agent Registry and Governance Policies.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("registry-agents").set_defaults(run=cmd_registry_agents)
    search = sub.add_parser("registry-search")
    search.add_argument("query")
    search.set_defaults(run=cmd_registry_search)
    sub.add_parser("engine").set_defaults(run=cmd_engine)
    sub.add_parser("provision").set_defaults(run=cmd_provision)
    create = sub.add_parser("create")
    create.add_argument("constraint")
    create.add_argument("--name", required=True)
    create.add_argument("--denial-message", default="")
    create.add_argument("--dry-run", action="store_true")
    create.set_defaults(run=cmd_create)
    sub.add_parser("list").set_defaults(run=cmd_list)
    args = parser.parse_args()
    args.run(project, args)


if __name__ == "__main__":
    main()
