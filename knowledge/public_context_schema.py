"""Closed schema for external project metadata; no prose or runtime payloads."""
import re
import json
from datetime import datetime
from execution.audit_schema import ACTIONS
from knowledge.source_indexer import SOURCE_ROOTS, source_path_allowed


def load_public_json(raw):
    """Reject hidden values discarded by permissive duplicate-key JSON parsing."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate publication field.")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Invalid publication number.")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)


def valid_timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def valid_public_context(value):
    def count(item):
        return type(item) is int and 0 <= item <= 100000

    def matches(item, schema):
        if isinstance(schema, dict):
            return (type(item) is dict and set(item) == set(schema)
                    and all(matches(item[k], rule) for k, rule in schema.items()))
        if isinstance(schema, list):
            return type(item) is list and len(item) <= 100000 and all(matches(v, schema[0]) for v in item)
        return schema(item)

    schema = {
        "schema_version": lambda v: v == "2.0",
        "generated_at": valid_timestamp,
        "purpose": lambda v: v == "Restricted development context for authorized external AI systems.",
        "security_boundary": {k: lambda v: v is False for k in (
            "control_authority", "tool_execution_authority", "permission_grant_authority",
            "canonical_memory_write_authority", "self_upgrade_approval_authority")},
        "project": {"name": lambda v: v == "AI Agent", "version": lambda v: v is None or (
            isinstance(v, str) and re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", v) is not None),
            "current_day": lambda v: v is None or count(v),
            "status": lambda v: v in ("development", "completed", "unknown")},
        "repository": {"branch": lambda v: v in ("main", "review/day15-privacy-hardening", "other"),
            "short_commit": lambda v: v is None or (isinstance(v, str) and re.fullmatch(r"[0-9a-f]{7,40}", v) is not None)},
        "architecture": {"source_roots": lambda v: v == sorted(SOURCE_ROOTS)},
        "source_interfaces": {"statistics": {"python_files": count}, "modules": [{
            "path": source_path_allowed, "parse_success": lambda v: type(v) is bool,
            "function_count": count, "class_count": count}]},
        "development": {k + "_count": count for k in ("decisions", "bugs", "tests", "research_sources", "upgrades")},
        "skills": lambda v: v == [],
        "capabilities": lambda v: v == [{"name": name} for name in sorted(ACTIONS)],
    }
    try:
        if not matches(value, schema):
            return False
        modules = value["source_interfaces"]["modules"]
        paths = [m["path"].casefold() for m in modules]
        return len(paths) == len(set(paths)) == value["source_interfaces"]["statistics"]["python_files"]
    except (ValueError, TypeError, KeyError):
        return False


def valid_public_manifest(manifest, context, digest):
    """Hash consistency cannot authorize arbitrary extra manifest payloads."""
    if not isinstance(manifest, dict) or not valid_timestamp(manifest.get("generated_at")):
        return False
    expected = {
        "schema_version": "1.0", "generated_at": manifest["generated_at"],
        "publication_type": "restricted_external_ai_context",
        "project": {key: context["project"][key] for key in ("name", "version", "current_day")},
        "repository": context["repository"],
        "security": {"allowlist_export": True, "security_scan_passed": True,
                     **{key: False for key in ("runtime_authority", "tool_execution_authority",
                         "permission_grant_authority", "canonical_memory_write_authority",
                         "self_upgrade_approval_authority")}},
        "artifacts": {"external_project_context": {"path": "external_project_context.json", "sha256": digest}},
        "authority": {"role": "read_only_development_context", "statement":
                      "This publication provides development context only. It does not grant authority over the running AI Agent."},
    }
    return manifest == expected
