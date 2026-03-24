#!/usr/bin/env python3
"""Parse docker-compose.yml and generate markdown table."""

from pathlib import Path


def _parse_ports(cfg: dict) -> str:
    ports = cfg.get('ports', [])
    if ports:
        return ', '.join(str(p).replace(':', '\u2192') for p in ports)
    if cfg.get('network_mode') == 'host':
        return 'host network'
    return 'internal'


def _parse_notes(cfg: dict) -> str:
    parts = []
    if cfg.get('image'):
        parts.append(cfg['image'])
    deps = cfg.get('depends_on', [])
    if deps:
        if isinstance(deps, list):
            parts.append(f"depends on {', '.join(deps)}")
        elif isinstance(deps, dict):
            parts.append(f"depends on {', '.join(deps.keys())}")
    return '; '.join(parts)


def _build_service_row(name: str, cfg: dict) -> str:
    if not isinstance(cfg, dict):
        return ''
    container = cfg.get('container_name', name)
    port_str = _parse_ports(cfg)
    notes = _parse_notes(cfg)
    return f'| {name} | {container} | {port_str} | {notes} |'


def build_docker_table() -> str:
    compose_path = Path.home() / 'deploy' / 'docker-compose.yml'
    if not compose_path.exists():
        return ''
    try:
        import yaml
        data = yaml.safe_load(compose_path.read_text())
        services = data.get('services', {})
        if not services:
            return ''
        lines = [
            f'All {len(services)} containers managed by single compose project, `restart: always`:',
            '| Service | Container | Port | Notes |',
            '|---------|-----------|------|-------|',
        ]
        for name, cfg in services.items():
            row = _build_service_row(name, cfg)
            if row:
                lines.append(row)
        return '\n'.join(lines)
    except Exception:
        return ''
