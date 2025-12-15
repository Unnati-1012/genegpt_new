# backend/app/ncbi_tools.py
"""
NCBI E-utilities API tools for GeneGPT.

Provides access to NCBI gene information and PubMed literature search.
API Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""

import requests
from typing import Dict, Any, List


class NCBITools:
    """
    Client for NCBI E-utilities API.
    
    Provides methods for:
    - Gene search and summary retrieval
    - PubMed literature search
    
    Attributes:
        BASE: Base URL for NCBI E-utilities API
    """
    
    BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def gene_search(self, query: str) -> Dict[str, Any]:
        """
        Search for a gene by name in the NCBI Gene database.
        
        Args:
            query: Gene name or symbol to search for (e.g., "TP53", "BRCA1")
            
        Returns:
            Dict containing either:
            - {"gene_id": str}: The NCBI Gene ID if found
            - {"error": str}: Error message if not found or request failed
        """
        try:
            url = f"{self.BASE}/esearch.fcgi"
            params = {
                "db": "gene",
                "term": query,
                "retmode": "json"
            }

            r = requests.get(url, params=params)
            data = r.json()

            ids = data.get("esearchresult", {}).get("idlist", [])
            if not ids:
                return {"error": f"No gene found for '{query}'"}

            return {"gene_id": ids[0]}

        except Exception as e:
            return {"error": str(e)}

    def gene_summary(self, gene_id: str) -> Dict[str, Any]:
        """
        Get detailed summary information for a gene by its NCBI Gene ID.
        
        Args:
            gene_id: NCBI Gene ID (e.g., "7157" for TP53)
            
        Returns:
            Dict containing:
            - gene_id: The queried gene ID
            - name: Official gene symbol
            - description: Full gene name/description
            - summary: Functional summary of the gene
            
            Or {"error": str} if the request fails
        """
        try:
            url = f"{self.BASE}/esummary.fcgi"
            params = {
                "db": "gene",
                "id": gene_id,
                "retmode": "json"
            }

            r = requests.get(url, params=params)
            data = r.json()

            result = data.get("result", {}).get(gene_id, {})
            summary = result.get("summary", "No summary available")
            name = result.get("name", "")
            description = result.get("description", "")

            return {
                "gene_id": gene_id,
                "name": name,
                "description": description,
                "summary": summary
            }

        except Exception as e:
            return {"error": str(e)}

    def pubmed_search(self, query: str) -> Dict[str, Any]:
        """
        Search PubMed for publications matching a query.
        
        Returns up to 5 matching publications with title, authors, year, abstract and link.
        
        Args:
            query: Search terms for PubMed (e.g., "TP53 cancer", "CRISPR review")
            
        Returns:
            Dict containing either:
            - {"results": List[Dict]}: List of publications, each with:
                - pmid: PubMed ID
                - title: Article title
                - authors: Comma-separated author names
                - year: Publication year
                - abstract: Short description/abstract
                - link: Direct PubMed URL
                - journal: Journal name
            - {"error": str}: Error message if search fails
        """
        try:
            # Step 1 — Query PubMed
            url = f"{self.BASE}/esearch.fcgi"
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": 5,
                "retmode": "json",
                "sort": "relevance"
            }

            r = requests.get(url, params=params)
            data = r.json()
            ids = data.get("esearchresult", {}).get("idlist", [])

            if not ids:
                return {"error": f"No PubMed results found for '{query}'"}

            # Step 2 — Fetch details (summary)
            id_list = ",".join(ids)
            url2 = f"{self.BASE}/esummary.fcgi"
            params2 = {"db": "pubmed", "id": id_list, "retmode": "json"}

            r2 = requests.get(url2, params=params2)
            details = r2.json().get("result", {})
            
            # Step 3 — Fetch abstracts using efetch
            url3 = f"{self.BASE}/efetch.fcgi"
            params3 = {"db": "pubmed", "id": id_list, "retmode": "xml", "rettype": "abstract"}
            
            abstracts = {}
            try:
                r3 = requests.get(url3, params=params3)
                if r3.status_code == 200:
                    # Parse XML to extract abstracts
                    import re
                    xml_text = r3.text
                    # Extract abstracts for each PMID
                    for pmid in ids:
                        # Find abstract text (simplified parsing)
                        abstract_match = re.search(
                            rf'<PMID[^>]*>{pmid}</PMID>.*?<AbstractText[^>]*>(.*?)</AbstractText>',
                            xml_text, re.DOTALL
                        )
                        if abstract_match:
                            abstract = abstract_match.group(1)
                            # Clean up XML tags
                            abstract = re.sub(r'<[^>]+>', '', abstract)
                            # Truncate to first 300 chars
                            if len(abstract) > 300:
                                abstract = abstract[:300] + "..."
                            abstracts[pmid] = abstract
            except Exception:
                pass  # Abstracts are optional

            results = []
            for pmid in ids:
                info = details.get(pmid, {})
                title = info.get("title", "No title")
                authors_list = info.get("authors", [])
                authors = ", ".join([a.get("name", "") for a in authors_list[:5]])  # First 5 authors
                if len(authors_list) > 5:
                    authors += " et al."
                pubdate = info.get("pubdate", "N/A")
                journal = info.get("source", "Unknown Journal")

                # extract year from pubdate
                year = pubdate.split(" ")[0] if pubdate else "N/A"

                results.append({
                    "pmid": pmid,
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "journal": journal,
                    "abstract": abstracts.get(pmid, "Abstract not available"),
                    "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                })

            return {"results": results}

        except Exception as e:
            return {"error": str(e)}
