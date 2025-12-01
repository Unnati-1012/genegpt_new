import requests
from typing import Dict, List, Any


class ClinVarTools:
    """
    Lightweight ClinVar helper using NCBI E-utilities.

    Public methods used by main.py:
      - variants_for_gene(gene: str) -> dict
      - record_details(clinvar_id: str) -> dict
    """

    def __init__(self, email: str | None = None, api_key: str | None = None):
        self.base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.email = email
        self.api_key = api_key

    # -------------------------------
    # Internal HTTP helper
    # -------------------------------
    def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        p = params.copy()
        p.setdefault("retmode", "json")
        if self.email:
            p["email"] = self.email
        if self.api_key:
            p["api_key"] = self.api_key

        url = f"{self.base}/{endpoint}"
        try:
            r = requests.get(url, params=p, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print("ClinVarTools HTTP error:", e)
            return {"error": f"ClinVar request failed: {e}"}

    # -------------------------------
    # Helpers for parsing ESummary
    # -------------------------------
    @staticmethod
    def _extract_conditions_from_traitset(trait_set_obj: Any) -> List[str]:
        """
        Pull disease / condition names out of a ClinVar 'trait_set' object.
        Works for both the older top-level trait_set and the newer
        *_classification.trait_set blocks.
        """
        conditions: List[str] = []
        if not trait_set_obj:
            return conditions

        def handle_one(ts: Dict[str, Any]) -> None:
            names = ts.get("trait_name", [])
            if isinstance(names, list):
                for n in names:
                    if isinstance(n, dict):
                        txt = n.get("text") or n.get("name")
                        if txt:
                            conditions.append(txt)
                    elif isinstance(n, str):
                        conditions.append(n)
            elif isinstance(names, str):
                conditions.append(names)

        if isinstance(trait_set_obj, list):
            for t in trait_set_obj:
                if isinstance(t, dict):
                    handle_one(t)
        elif isinstance(trait_set_obj, dict):
            handle_one(trait_set_obj)

        return conditions

    @staticmethod
    def _parse_summary_record(rec_id: str, rec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map the slightly messy ClinVar ESummary JSON into a clean dict:

        {
          id, title, type,
          clinical_significance,
          conditions,
          review_status,
          rcvaccession
        }

        Newer ClinVar records often store significance / conditions / review_status
        under classification blocks instead of the older 'clinical_significance'
        and top-level 'trait_set', so we check both.
        """
        # --- 1) Clinical significance ---
        significance = "Unknown"

        cs = rec.get("clinical_significance")
        if isinstance(cs, dict):
            sig = cs.get("description") or cs.get("label")
            if sig:
                significance = sig

        # Fallback to the newer classification objects if needed
        if significance == "Unknown":
            for key in (
                "clinical_impact_classification",
                "germline_classification",
                "oncogenicity_classification",
            ):
                cls = rec.get(key)
                if isinstance(cls, dict):
                    desc = cls.get("description")
                    if desc:
                        significance = desc
                        break

        # --- 2) Conditions (diseases / phenotypes) ---
        conditions: List[str] = []

        # Older schema: top-level trait_set
        conditions.extend(
            ClinVarTools._extract_conditions_from_traitset(rec.get("trait_set"))
        )

        # If still empty, try each classification's trait_set
        if not conditions:
            for key in (
                "clinical_impact_classification",
                "germline_classification",
                "oncogenicity_classification",
            ):
                cls = rec.get(key)
                if isinstance(cls, dict):
                    conditions.extend(
                        ClinVarTools._extract_conditions_from_traitset(
                            cls.get("trait_set")
                        )
                    )
                if conditions:
                    break

        conditions = sorted(set(conditions))

        # --- 3) Review status ---
        review_status = (rec.get("review_status") or "").strip()

        if not review_status:
            for key in (
                "clinical_impact_classification",
                "germline_classification",
                "oncogenicity_classification",
            ):
                cls = rec.get(key)
                if isinstance(cls, dict):
                    rs = (cls.get("review_status") or "").strip()
                    if rs:
                        review_status = rs
                        break

        if not review_status:
            review_status = "Unknown"

        return {
            "id": rec_id,
            "title": rec.get("title", ""),
            "type": rec.get("type", ""),
            "clinical_significance": significance,
            "conditions": conditions,
            "review_status": review_status,
            "rcvaccession": rec.get("accession"),
        }

    # -------------------------------
    # Public: variants for a gene
    # -------------------------------
    def variants_for_gene(self, gene: str, max_results: int = 50) -> Dict[str, Any]:
        """
        Return ClinVar variants for a given gene symbol.

        Output:
          {"results": [ {id, clinical_significance, conditions, review_status, ...}, ... ]}
        """
        gene = gene.strip()
        if not gene:
            return {"error": "Gene symbol is empty."}

        # 1) ESearch to get IDs
        term = f"{gene}[gene]"
        data = self._get(
            "esearch.fcgi",
            {
                "db": "clinvar",
                "term": term,
                "retmax": max_results,
            },
        )

        if "error" in data:
            return data

        try:
            id_list = data["esearchresult"]["idlist"]
        except Exception:
            return {"error": f"No ClinVar IDs found for gene {gene}."}

        if not id_list:
            return {"results": []}

        # 2) ESummary to get details
        sum_data = self._get(
            "esummary.fcgi",
            {
                "db": "clinvar",
                "id": ",".join(id_list),
            },
        )

        if "error" in sum_data:
            return sum_data

        try:
            result = sum_data["result"]
            uids = result["uids"]
        except Exception:
            return {"error": "ClinVar ESummary response not understood."}

        variants: List[Dict[str, Any]] = []
        for uid in uids:
            rec = result.get(uid, {})
            parsed = self._parse_summary_record(uid, rec)
            variants.append(parsed)

        return {"results": variants}

    # -------------------------------
    # Public: details for one ClinVar ID
    # -------------------------------
    def record_details(self, clinvar_id: str) -> Dict[str, Any]:
        """
        Return detailed information for a single ClinVar record ID.
        """
        clinvar_id = str(clinvar_id).strip()
        if not clinvar_id:
            return {"error": "ClinVar ID is empty."}

        sum_data = self._get(
            "esummary.fcgi",
            {
                "db": "clinvar",
                "id": clinvar_id,
            },
        )

        if "error" in sum_data:
            return sum_data

        try:
            result = sum_data["result"]
            rec = result[clinvar_id]
        except Exception:
            return {"error": f"Could not parse ClinVar record {clinvar_id}."}

        return self._parse_summary_record(clinvar_id, rec)
