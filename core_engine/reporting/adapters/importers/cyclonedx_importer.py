"""Importer for CycloneDX SBOM JSON artifacts."""

import json
from pathlib import Path
from typing import Dict, List

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport


class CycloneDxImporter:
    """Import CycloneDX summaries into canonical metadata."""

    name = 'cyclonedx'

    def supports(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != '.json':
            return False
        if 'cyclonedx' not in file_path.name.lower():
            return False
        try:
            with file_path.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            return False
        if not isinstance(data, dict):
            return False
        return str(data.get('bomFormat', '')).strip().lower() == 'cyclonedx'

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        with file_path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)

        if not isinstance(data, dict):
            return

        metadata = data.get('metadata', {})
        metadata = metadata if isinstance(metadata, dict) else {}

        tools = metadata.get('tools', [])
        tools = tools if isinstance(tools, list) else []
        tool_names = []
        tool_entries: List[Dict[str, str]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            name = str(tool.get('name', '') or '').strip()
            version = str(tool.get('version', '') or '').strip()
            if not name:
                continue
            label = f'{name} {version}'.strip()
            tool_names.append(label)
            tool_entries.append(
                {
                    'name': name,
                    'version': version,
                }
            )

        manufacturer = metadata.get('manufacturer', {})
        manufacturer = manufacturer if isinstance(manufacturer, dict) else {}
        manufacturer_name = str(manufacturer.get('name', '') or '').strip()

        properties = metadata.get('properties', [])
        properties = properties if isinstance(properties, list) else []
        property_rows: List[Dict[str, str]] = []
        for item in properties:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name', '') or '').strip()
            value = str(item.get('value', '') or '').strip()
            if not name:
                continue
            property_rows.append({'name': name, 'value': value})

        components = data.get('components', [])
        components = components if isinstance(components, list) else []

        flattened: List[Dict[str, str]] = []

        def _visit(component_obj: dict, depth: int) -> None:
            if not isinstance(component_obj, dict):
                return
            supplier = component_obj.get('supplier', {})
            supplier = supplier if isinstance(supplier, dict) else {}

            licenses = component_obj.get('licenses', [])
            licenses = licenses if isinstance(licenses, list) else []
            license_names = []
            for lic in licenses:
                if not isinstance(lic, dict):
                    continue
                license_obj = lic.get('license', {})
                license_obj = (
                    license_obj if isinstance(license_obj, dict) else {}
                )
                license_name = str(license_obj.get('name', '') or '').strip()
                if license_name:
                    license_names.append(license_name)

            flattened.append(
                {
                    'depth': str(depth),
                    'type': str(component_obj.get('type', '') or '').strip(),
                    'name': str(component_obj.get('name', '') or '').strip(),
                    'version': str(component_obj.get('version', '') or '').strip(),
                    'supplier': str(supplier.get('name', '') or '').strip(),
                    'group': str(component_obj.get('group', '') or '').strip(),
                    'licenses': ', '.join(sorted(set(license_names))),
                    'purl': str(component_obj.get('purl', '') or '').strip(),
                    'cpe': str(component_obj.get('cpe', '') or '').strip(),
                }
            )

            nested = component_obj.get('components', [])
            nested = nested if isinstance(nested, list) else []
            for child in nested:
                _visit(child, depth + 1)

        for component in components:
            _visit(component, 0)

        total_components = len(flattened)
        unique_suppliers = len(
            {
                row.get('supplier', '').strip().lower()
                for row in flattened
                if row.get('supplier', '').strip()
            }
        )
        unique_licenses = len(
            {
                license_name.strip().lower()
                for row in flattened
                for license_name in str(row.get('licenses', '')).split(',')
                if license_name.strip()
            }
        )

        flattened.sort(
            key=lambda row: (
                int(row.get('depth', '0') or '0'),
                str(row.get('type', '')).lower(),
                str(row.get('name', '')).lower(),
            )
        )

        report.metadata['cyclonedx'] = {
            'available': True,
            'source_file': str(file_path),
            'bom_format': str(data.get('bomFormat', '') or '').strip(),
            'spec_version': str(data.get('specVersion', '') or '').strip(),
            'bom_version': str(data.get('version', '') or '').strip(),
            'timestamp': str(metadata.get('timestamp', '') or '').strip(),
            'manufacturer': manufacturer_name,
            'tools': tool_names,
            'tools_detailed': tool_entries,
            'tools_count': len(tool_names),
            'properties': property_rows,
            'components_total': total_components,
            'suppliers_total': unique_suppliers,
            'licenses_total': unique_licenses,
            'components': flattened,
        }
