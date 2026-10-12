"""Crosswalk for matching utility service addresses and account numbers
to Nexus Property Name, Property Code, and Integration Package.

Sources:
1. masters/HOC unit directory(HOC unit directory).csv (Yardi properties with property codes & addresses)
2. masters/utility_properties.xlsx ('Yardi - Query Resolution' tab with direct address -> property mappings)
3. masters/allunits 2026.05.01.csv (Community unit addresses mapped to properties.csv)
4. masters/properties.csv (Canonical Nexus Property Name, Code, Package)
"""

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Tuple, List
import openpyxl

@dataclass
class UtilityPropertyMatch:
    property_name: str
    property_code: str
    integration_package: str
    status: str            # 'READ_OK' or 'NEEDS_REVIEW'
    matched_by: str        # 'address_exact', 'address_building', 'yardi_unit', 'community_unit', etc.
    unit: Optional[str] = None
    gl_code: Optional[str] = None


def normalize_address(addr: str) -> str:
    """Normalize address string for fuzzy/exact matching.
    e.g. '1100 Eastern Ave N.E. Apt - 101' -> '1100 eastern ave ne'
    """
    if not addr:
        return ""
    s = addr.lower()
    # Remove commas, periods, hashes, hyphens
    s = re.sub(r"[\.,#\-]", " ", s)
    # Remove unit/apt/ste parts for building-level matching
    s = re.sub(r"\b(apt|apartment|unit|ste|suite|bldg|building|fl|floor)\b.*", "", s)
    # Standardize directionals
    s = re.sub(r"\bnortheast\b", "ne", s)
    s = re.sub(r"\bnorthwest\b", "nw", s)
    s = re.sub(r"\bsoutheast\b", "se", s)
    s = re.sub(r"\bsouthwest\b", "sw", s)
    s = re.sub(r"\bnorth\b", "n", s)
    s = re.sub(r"\bsouth\b", "s", s)
    s = re.sub(r"\beast\b", "e", s)
    s = re.sub(r"\bwest\b", "w", s)
    # Standardize street suffixes
    s = re.sub(r"\bavenue\b", "ave", s)
    s = re.sub(r"\bstreet\b", "st", s)
    s = re.sub(r"\broad\b", "rd", s)
    s = re.sub(r"\bboulevard\b", "blvd", s)
    s = re.sub(r"\bdrive\b", "dr", s)
    s = re.sub(r"\blane\b", "ln", s)
    s = re.sub(r"\bcourt\b", "ct", s)
    s = re.sub(r"\bcircle\b", "cir", s)
    s = re.sub(r"\bplace\b", "pl", s)
    s = re.sub(r"\bterrace\b", "ter", s)
    s = re.sub(r"\bparkway\b", "pkwy", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


class UtilityLookup:
    def __init__(self, masters_dir: Path):
        self.masters_dir = Path(masters_dir)
        self.prop_catalog: Dict[str, Tuple[str, str, str]] = {}  # norm_name -> (canonical_name, code, pkg)
        self.address_to_property: Dict[str, Tuple[str, str, str]] = {} # norm_addr -> (prop_name, code, pkg)
        self.property_aliases: Dict[str, str] = {} # raw_norm -> canonical_name
        self.yardi_gl_map: Dict[str, str] = {} # norm_prop_name -> gl_code
        self._load_masters()

    def _load_masters(self):
        # 1. Load canonical properties.csv
        props_path = self.masters_dir / "properties.csv"
        if props_path.exists():
            with open(props_path, encoding="utf-8", errors="ignore") as f:
                for row in csv.reader(f):
                    if row and row[0].strip():
                        name = row[0].strip().lstrip('\ufeff')
                        code = row[1].strip() if len(row) > 1 else ""
                        pkg = row[2].strip() if len(row) > 2 else ""
                        norm = name.lower()
                        self.prop_catalog[norm] = (name, code, pkg)

        # 1b. Load property_aliases.csv if present
        aliases_path = self.masters_dir / "property_aliases.csv"
        if aliases_path.exists():
            with open(aliases_path, encoding="utf-8", errors="ignore") as f:
                r = csv.reader(f)
                header = next(r, None)
                for row in r:
                    if row and len(row) >= 2 and row[0].strip() and row[1].strip():
                        self.property_aliases[normalize_address(row[0])] = row[1].strip()

        # 2. Load Yardi Query Resolution from utility_properties.xlsx
        util_xlsx = self.masters_dir / "utility_properties.xlsx"
        if util_xlsx.exists():
            try:
                wb = openpyxl.load_workbook(util_xlsx, data_only=True, read_only=True)
                if 'Yardi - Query Resolution' in wb.sheetnames:
                    s = wb['Yardi - Query Resolution']
                    for row in s.iter_rows(min_row=2, values_only=True):
                        if not row or not any(row):
                            continue
                        prop_code = str(row[0]).strip() if row[0] is not None else ""
                        prop_name = str(row[2] or row[1]).strip() if (row[2] or row[1]) is not None else ""
                        addr = str(row[3]).strip() if row[3] is not None else ""
                        gl_code = str(row[9]).strip() if len(row) > 9 and row[9] is not None else ""
                        if prop_name and addr:
                            norm_addr = normalize_address(addr)
                            if norm_addr:
                                self.address_to_property[norm_addr] = (prop_name, prop_code, "YARDI")
                        if prop_name and gl_code:
                            self.yardi_gl_map[prop_name.lower()] = gl_code
            except Exception as e:
                print(f"Warning: Failed to load Yardi sheet from utility_properties.xlsx: {e}")

        # 3. Load HOC Unit Directory CSV (Yardi properties)
        hoc_path = self.masters_dir / "HOC unit directory(HOC unit directory).csv"
        if hoc_path.exists():
            with open(hoc_path, encoding="utf-8", errors="ignore") as f:
                r = csv.reader(f)
                header = next(r, None)
                for row in r:
                    if row and len(row) >= 4 and row[3].strip():
                        prop_code = row[0].strip()
                        prop_name = row[1].strip()
                        addr = row[3].strip()
                        norm_addr = normalize_address(addr)
                        if norm_addr and norm_addr not in self.address_to_property:
                            self.address_to_property[norm_addr] = (prop_name, prop_code, "YARDI")

        # 4. Load allunits 2026.05.01.csv (Community Unit Directory)
        allunits_path = self.masters_dir / "allunits 2026.05.01.csv"
        if allunits_path.exists():
            with open(allunits_path, encoding="utf-8", errors="ignore") as f:
                r = csv.reader(f)
                # Skip header lines until community data
                for _ in range(7):
                    next(r, None)
                for row in r:
                    if row and len(row) >= 4 and row[3].strip():
                        community = row[0].strip()
                        addr = row[3].strip()
                        norm_addr = normalize_address(addr)
                        if not norm_addr or norm_addr in self.address_to_property:
                            continue

                        # Resolve community to canonical properties.csv
                        comm_lower = community.lower()
                        if comm_lower in self.prop_catalog:
                            p_name, p_code, p_pkg = self.prop_catalog[comm_lower]
                            self.address_to_property[norm_addr] = (p_name, p_code, p_pkg or "INTACCT")
                        else:
                            # Fuzzy/substring match against properties.csv
                            for cat_k, (cat_name, cat_code, cat_pkg) in self.prop_catalog.items():
                                if comm_lower in cat_k or cat_k in comm_lower:
                                    self.address_to_property[norm_addr] = (cat_name, cat_code, cat_pkg or "INTACCT")
                                    break

    def match(self, raw_service_address: str, utility_type: Optional[str] = None) -> UtilityPropertyMatch:
        """Match a raw service address to a known property."""
        if not raw_service_address or not raw_service_address.strip():
            return UtilityPropertyMatch(
                property_name="",
                property_code="",
                integration_package="",
                status="NEEDS_REVIEW",
                matched_by="none"
            )

        norm_input = normalize_address(raw_service_address)

        # 0. Check explicit aliases first
        for alias_norm, canon_name in self.property_aliases.items():
            if alias_norm in norm_input or norm_input in alias_norm:
                canon_lower = canon_name.lower()
                c_name, c_code, c_pkg = self.prop_catalog.get(canon_lower, (canon_name, "", "INTACCT"))
                gl = self.yardi_gl_map.get(canon_lower)
                return UtilityPropertyMatch(
                    property_name=c_name,
                    property_code=c_code,
                    integration_package=c_pkg,
                    status="READ_OK",
                    matched_by="alias_explicit",
                    gl_code=gl
                )

        # 1. Exact match on normalized address
        if norm_input in self.address_to_property:
            name, code, pkg = self.address_to_property[norm_input]
            gl = self.yardi_gl_map.get(name.lower())
            return UtilityPropertyMatch(
                property_name=name,
                property_code=code,
                integration_package=pkg,
                status="READ_OK",
                matched_by="address_exact",
                gl_code=gl
            )

        # 2. Check if the building address is contained in any known address or vice versa
        # (e.g., input has street number + street name matching a directory entry)
        for known_addr, (p_name, p_code, p_pkg) in self.address_to_property.items():
            if norm_input in known_addr or known_addr in norm_input:
                gl = self.yardi_gl_map.get(p_name.lower())
                return UtilityPropertyMatch(
                    property_name=p_name,
                    property_code=p_code,
                    integration_package=p_pkg,
                    status="READ_OK",
                    matched_by="address_building_contains",
                    gl_code=gl
                )

        # 3. Direct match against canonical property names (in case the bill had property name)
        clean_raw = raw_service_address.lower().strip()
        for cat_k, (cat_name, cat_code, cat_pkg) in self.prop_catalog.items():
            if cat_k in clean_raw or clean_raw in cat_k:
                gl = self.yardi_gl_map.get(cat_name.lower())
                return UtilityPropertyMatch(
                    property_name=cat_name,
                    property_code=cat_code,
                    integration_package=cat_pkg,
                    status="READ_OK",
                    matched_by="name_direct",
                    gl_code=gl
                )

        # 4. No confident match found -> Flag for human review
        return UtilityPropertyMatch(
            property_name=raw_service_address,
            property_code="",
            integration_package="",
            status="NEEDS_REVIEW",
            matched_by="none"
        )
