import requests

class NCBITools:
    BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # -------------------------------------------------
    # 1) SEARCH GENE BY NAME
    # -------------------------------------------------
    def gene_search(self, query: str):
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

    # -------------------------------------------------
    # 2) GET GENE SUMMARY
    # -------------------------------------------------
    def gene_summary(self, gene_id: str):
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

    # -------------------------------------------------
    # 3) PUBMED SEARCH (title + authors + year + PMID)
    # -------------------------------------------------
    def pubmed_search(self, query: str):
        try:
            # Step 1 — Query PubMed
            url = f"{self.BASE}/esearch.fcgi"
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": 5,
                "retmode": "json"
            }

            r = requests.get(url, params=params)
            data = r.json()
            ids = data.get("esearchresult", {}).get("idlist", [])

            if not ids:
                return {"error": f"No PubMed results found for '{query}'"}

            # Step 2 — Fetch details
            id_list = ",".join(ids)
            url2 = f"{self.BASE}/esummary.fcgi"
            params2 = {"db": "pubmed", "id": id_list, "retmode": "json"}

            r2 = requests.get(url2, params=params2)
            details = r2.json().get("result", {})

            results = []
            for pmid in ids:
                info = details.get(pmid, {})
                title = info.get("title", "No title")
                authors_list = info.get("authors", [])
                authors = ", ".join([a.get("name", "") for a in authors_list])
                pubdate = info.get("pubdate", "N/A")

                # extract year from pubdate
                year = pubdate.split(" ")[0]

                results.append({
                    "pmid": pmid,
                    "title": title,
                    "authors": authors,
                    "year": year
                })

            return {"results": results}

        except Exception as e:
            return {"error": str(e)}
