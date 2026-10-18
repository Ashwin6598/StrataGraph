"""
Jira Board and Agile Execution Ingestion Parser.
Parses Jira JSON board exports or REST API payloads into the 5th Pillar:
  Project -> Epic -> Feature -> Story -> Developer / AST Function
Establishes cross-pillar relationships with PRD, ADR, CodeBase, and Operations.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from codegraph.schema import (
    EpicNode,
    AgileFeatureNode,
    StoryNode,
    Relationships
)


class JiraBoardParser:
    """Parses Jira board exports into Program Flow graph nodes and relationships."""

    def __init__(self, project_id: str = "project:payflow"):
        self.project_id = project_id

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Parses a Jira JSON file from disk."""
        path = Path(file_path)
        if not path.exists():
            return {"epics": [], "features": [], "stories": [], "edges": []}

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)

        return self.parse_data(data)

    def parse_data(self, data: Any) -> Dict[str, Any]:
        """Parses Jira board dictionary or array representation."""
        epics: List[EpicNode] = []
        features: List[AgileFeatureNode] = []
        stories: List[StoryNode] = []
        edges: List[Tuple[str, str, str]] = []

        # Handle structured {epics: [...], features: [...], stories: [...]} format
        if isinstance(data, dict) and ("epics" in data or "features" in data or "stories" in data):
            project_id = data.get("project_id", self.project_id)
            epic_lookup = {}
            feature_lookup = {}

            # 1. Parse Epics
            for raw_epic in data.get("epics", []):
                key = raw_epic.get("key", f"EPIC-{len(epics)+1}")
                epic_id = f"epic:{key}"
                epic = EpicNode(
                    id=epic_id,
                    project_id=project_id,
                    key=key,
                    summary=raw_epic.get("summary", ""),
                    description=raw_epic.get("description", ""),
                    status=raw_epic.get("status", "IN_PROGRESS"),
                    owner=raw_epic.get("owner", ""),
                    target_date=raw_epic.get("target_date"),
                    created_date=raw_epic.get("created_date")
                )
                epics.append(epic)
                epic_lookup[key] = epic_id
                edges.append((project_id, Relationships.HAS_EPIC, epic_id))

            # 2. Parse Features
            for raw_feat in data.get("features", []):
                key = raw_feat.get("key", f"FEAT-{len(features)+1}")
                feat_id = f"feat:{key}"
                epic_key = raw_feat.get("epic_key", "")
                epic_id = epic_lookup.get(epic_key, epics[0].id if epics else f"epic:{self.project_id}")

                req_id = raw_feat.get("req_id")
                if req_id and not req_id.startswith("req:"):
                    req_id = f"req:{req_id}"

                feat = AgileFeatureNode(
                    id=feat_id,
                    epic_id=epic_id,
                    key=key,
                    summary=raw_feat.get("summary", ""),
                    description=raw_feat.get("description", ""),
                    service_name=raw_feat.get("service_name"),
                    architecture_diagram=raw_feat.get("architecture_diagram"),
                    status=raw_feat.get("status", "IN_DEVELOPMENT"),
                    req_id=req_id
                )
                features.append(feat)
                feature_lookup[key] = feat_id
                edges.append((epic_id, Relationships.HAS_FEATURE, feat_id))

                if req_id:
                    edges.append((feat_id, Relationships.REALIZES_REQUIREMENT, req_id))

            # 3. Parse Stories
            for raw_story in data.get("stories", []):
                key = raw_story.get("key", f"STORY-{len(stories)+1}")
                story_id = f"story:{key}"
                feat_key = raw_story.get("feature_key", "")
                feat_id = feature_lookup.get(feat_key, features[0].id if features else f"feat:{self.project_id}")

                created_d = raw_story.get("created_date", "2025-10-01")
                resolved_d = raw_story.get("resolved_date")
                cycle_time = raw_story.get("cycle_time_days")
                if cycle_time is None and resolved_d and created_d:
                    try:
                        d1 = datetime.fromisoformat(created_d)
                        d2 = datetime.fromisoformat(resolved_d)
                        cycle_time = float(max(0, (d2 - d1).days))
                    except Exception:
                        cycle_time = None

                func_id = raw_story.get("func_id")
                if func_id and not func_id.startswith("func:"):
                    func_id = f"func:{func_id}"

                story = StoryNode(
                    id=story_id,
                    feature_id=feat_id,
                    key=key,
                    summary=raw_story.get("summary", ""),
                    description=raw_story.get("description", ""),
                    story_points=int(raw_story.get("story_points", 3)),
                    assignee=raw_story.get("assignee", "Unassigned"),
                    status=raw_story.get("status", "DONE"),
                    sprint=raw_story.get("sprint", "Backlog"),
                    created_date=created_d,
                    resolved_date=resolved_d,
                    cycle_time_days=cycle_time,
                    blocked=bool(raw_story.get("blocked", False)),
                    blocker_reason=raw_story.get("blocker_reason"),
                    func_id=func_id
                )
                stories.append(story)
                edges.append((feat_id, Relationships.HAS_STORY, story_id))

                if func_id:
                    edges.append((story_id, Relationships.IMPLEMENTS_CODE, func_id))

                # Cross-link mentions in summary/description (e.g. REQ-001, ADR-001, BUG-112)
                text = f"{story.summary} {story.description}"
                for req_match in re.findall(r"\bREQ-\d+\b", text, re.IGNORECASE):
                    edges.append((story_id, Relationships.REALIZES_REQUIREMENT, f"req:{req_match.upper()}"))
                for adr_match in re.findall(r"\bADR-\d+\b", text, re.IGNORECASE):
                    edges.append((story_id, Relationships.GUIDED_BY_ARCHITECTURE, f"decision:{adr_match.upper()}"))
                for bug_match in re.findall(r"\bBUG-\d+\b", text, re.IGNORECASE):
                    edges.append((story_id, Relationships.RESOLVES_ISSUE, f"issue:{bug_match.upper()}"))

        # Handle standard Jira REST API search response {"issues": [...]}
        elif isinstance(data, dict) and "issues" in data:
            raw_issues = data.get("issues", [])
            epic_lookup = {}
            feature_lookup = {}

            # First pass: Epics
            for item in raw_issues:
                fields = item.get("fields", {})
                itype = fields.get("issuetype", {}).get("name", "").lower()
                key = item.get("key", "")
                if "epic" in itype:
                    epic_id = f"epic:{key}"
                    status_name = fields.get("status", {}).get("name", "IN_PROGRESS").upper()
                    epic = EpicNode(
                        id=epic_id,
                        project_id=self.project_id,
                        key=key,
                        summary=fields.get("summary", ""),
                        description=fields.get("description", "") or "",
                        status=status_name,
                        owner=fields.get("assignee", {}).get("displayName", "") if fields.get("assignee") else "",
                        created_date=fields.get("created", "")[:10] if fields.get("created") else None
                    )
                    epics.append(epic)
                    epic_lookup[key] = epic_id
                    edges.append((self.project_id, Relationships.HAS_EPIC, epic_id))

            # Fallback default epic if none explicitly tagged
            default_epic_id = epics[0].id if epics else f"epic:{self.project_id}:default"
            if not epics:
                def_epic = EpicNode(
                    id=default_epic_id,
                    project_id=self.project_id,
                    key="EPIC-DEF",
                    summary="General Project Agile Execution",
                    status="IN_PROGRESS"
                )
                epics.append(def_epic)
                edges.append((self.project_id, Relationships.HAS_EPIC, default_epic_id))

            # Second pass: Features & Stories
            for item in raw_issues:
                fields = item.get("fields", {})
                itype = fields.get("issuetype", {}).get("name", "").lower()
                key = item.get("key", "")
                if "epic" in itype:
                    continue

                if "feature" in itype:
                    feat_id = f"feat:{key}"
                    epic_link = fields.get("customfield_epic_link") or fields.get("parent", {}).get("key")
                    parent_epic_id = epic_lookup.get(epic_link, default_epic_id)
                    feat = AgileFeatureNode(
                        id=feat_id,
                        epic_id=parent_epic_id,
                        key=key,
                        summary=fields.get("summary", ""),
                        description=fields.get("description", "") or "",
                        status=fields.get("status", {}).get("name", "IN_DEVELOPMENT").upper()
                    )
                    features.append(feat)
                    feature_lookup[key] = feat_id
                    edges.append((parent_epic_id, Relationships.HAS_FEATURE, feat_id))
                else:
                    # Treat as Story / Task / Bug
                    story_id = f"story:{key}"
                    parent_key = fields.get("parent", {}).get("key") or fields.get("customfield_epic_link")
                    feat_id = feature_lookup.get(parent_key)
                    if not feat_id:
                        feat_id = features[0].id if features else f"feat:{self.project_id}:core"
                        if not features:
                            def_feat = AgileFeatureNode(
                                id=feat_id,
                                epic_id=default_epic_id,
                                key="FEAT-DEF",
                                summary="Core Functional Delivery",
                                status="IN_DEVELOPMENT"
                            )
                            features.append(def_feat)
                            edges.append((default_epic_id, Relationships.HAS_FEATURE, feat_id))

                    status_name = fields.get("status", {}).get("name", "TODO").upper()
                    if status_name in ("DONE", "CLOSED", "RESOLVED"):
                        status_name = "DONE"
                    elif status_name in ("IN PROGRESS", "IN DEVELOPMENT"):
                        status_name = "IN_PROGRESS"

                    points = fields.get("customfield_story_points") or fields.get("storyPoints") or 3
                    assignee_obj = fields.get("assignee")
                    assignee = assignee_obj.get("displayName") or assignee_obj.get("emailAddress") if assignee_obj else "Unassigned"

                    created_str = fields.get("created", "2025-10-01")[:10] if fields.get("created") else "2025-10-01"
                    resolved_str = fields.get("resolutiondate", "")[:10] if fields.get("resolutiondate") else None
                    cycle_time = None
                    if resolved_str:
                        try:
                            d1 = datetime.fromisoformat(created_str)
                            d2 = datetime.fromisoformat(resolved_str)
                            cycle_time = float(max(0, (d2 - d1).days))
                        except Exception:
                            pass

                    # Detect blocker
                    blocked = False
                    blocker_reason = None
                    flagged = fields.get("flagged", False) or "blocked" in [l.lower() for l in fields.get("labels", [])]
                    if flagged or "blocked" in (fields.get("summary", "") + fields.get("description", "")).lower():
                        blocked = True
                        blocker_reason = "Flagged blocked in Jira"

                    story = StoryNode(
                        id=story_id,
                        feature_id=feat_id,
                        key=key,
                        summary=fields.get("summary", ""),
                        description=fields.get("description", "") or "",
                        story_points=int(points) if str(points).isdigit() else 3,
                        assignee=assignee,
                        status=status_name,
                        created_date=created_str,
                        resolved_date=resolved_str,
                        cycle_time_days=cycle_time,
                        blocked=blocked,
                        blocker_reason=blocker_reason
                    )
                    stories.append(story)
                    edges.append((feat_id, Relationships.HAS_STORY, story_id))

                    # Parse mentions
                    text = f"{story.summary} {story.description}"
                    for req_m in re.findall(r"\bREQ-\d+\b", text, re.IGNORECASE):
                        edges.append((story_id, Relationships.REALIZES_REQUIREMENT, f"req:{req_m.upper()}"))
                    for adr_m in re.findall(r"\bADR-\d+\b", text, re.IGNORECASE):
                        edges.append((story_id, Relationships.GUIDED_BY_ARCHITECTURE, f"decision:{adr_m.upper()}"))
                    for bug_m in re.findall(r"\bBUG-\d+\b", text, re.IGNORECASE):
                        edges.append((story_id, Relationships.RESOLVES_ISSUE, f"issue:{bug_m.upper()}"))

        return {
            "epics": epics,
            "features": features,
            "stories": stories,
            "edges": edges
        }
