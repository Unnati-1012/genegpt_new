# backend/app/ensembl_tools.py

import requests
from typing import Dict, Any, List, Optional


class EnsemblTools:
    """
    Thin wrapper around the Ensembl REST API.
    Docs: https://rest.ensembl.org
    """

    BASE = "https://rest.ensembl.org"

    def __init__(self, user_agent: str = "GeneGPT/1.0"):
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": user_agent,
        })

    # --------------- internal helper ---------------

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE}{path}"
        try:
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None

    # --------------- LOOKUP BY SYMBOL ---------------

    def lookup_gene(self, symbol: str, species: str = "human") -> Optional[Dict[str, Any]]:
        """
        Lookup a gene by HGNC symbol using xrefs/symbol.
        species: "human", "mouse", etc. Ensembl expects "homo_sapiens", "mus_musculus"...
        We map a few friendly names.
        """
        species_map = {
            "human": "homo_sapiens",
            "mouse": "mus_musculus",
        }
        ens_species = species_map.get(species.lower(), species)

        data = self._get(f"/xrefs/symbol/{ens_species}/{symbol}")
        if not data:
            return None

        # Take the first Ensembl gene entry
        gene_entry = next((x for x in data if x.get("type") == "gene"), None)
        if not gene_entry:
            gene_entry = data[0]

        stable_id = gene_entry.get("id")
        if not stable_id:
            return None

        return self.lookup_id(stable_id)

    # --------------- LOOKUP BY STABLE ID ---------------

    def lookup_id(self, stable_id: str) -> Optional[Dict[str, Any]]:
        """
        General lookup for any Ensembl stable ID (gene / transcript / protein).
        """
        data = self._get(f"/lookup/id/{stable_id}", params={"expand": 1})
        if not data:
            return None

        # Normalise fields we care about
        obj_type = data.get("object_type", "")
        desc = data.get("description", "") or ""
        display_name = data.get("display_name") or ""
        species = data.get("species", "")
        start = data.get("start")
        end = data.get("end")
        seq_region = data.get("seq_region_name")

        return {
            "id": data.get("id"),
            "object_type": obj_type,
            "display_name": display_name,
            "description": desc,
            "species": species,
            "seq_region_name": seq_region,
            "start": start,
            "end": end,
            "strand": data.get("strand"),
            "biotype": data.get("biotype"),
            "version": data.get("version"),
            "parent": data.get("Parent"),
            # Keep original record if needed
            "raw": data,
        }

    # --------------- TRANSCRIPTS FOR A GENE ---------------

    def gene_transcripts(self, gene_id: str) -> List[Dict[str, Any]]:
        """
        Return a list of transcripts for an Ensembl gene ID.
        """
        data = self._get(f"/lookup/id/{gene_id}", params={"expand": 1})
        if not data:
            return []

        transcripts = data.get("Transcript", []) or []

        out = []
        for t in transcripts:
            out.append({
                "id": t.get("id"),
                "biotype": t.get("biotype"),
                "length": t.get("length"),
                "start": t.get("start"),
                "end": t.get("end"),
                "strand": t.get("strand"),
            })
        return out

    # --------------- REGION SEQUENCE ---------------

    def region_sequence(self, region: str, species: str = "human") -> Optional[Dict[str, Any]]:
        """
        Fetch sequence for a genomic region like '7:140424943-140624564:1'.
        """
        species_map = {
            "human": "homo_sapiens",
            "mouse": "mus_musculus",
        }
        ens_species = species_map.get(species.lower(), species)

        # /sequence/region/:species/:region
        data = self._get(f"/sequence/region/{ens_species}/{region}")
        if not data:
            return None

        return {
            "id": data.get("id"),
            "seq": data.get("seq"),
            "length": len(data.get("seq", "")),
        }
