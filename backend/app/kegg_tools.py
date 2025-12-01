import requests

class KEGGTools:
    BASE = "https://rest.kegg.jp"

    # ----------------------------------------------------
    # INTERNAL CACHE: pathway_id → pathway_name
    # ----------------------------------------------------
    pathway_cache = {}

    def __init__(self):
        """Load all human pathway names once."""
        self.pathway_names = {} 

    # ----------------------------------------------------
    # Load ALL human pathway names (hsa pathways)
    # ----------------------------------------------------
def load_all_pathway_names(self):
    try:
       r = requests.get("https://rest.kegg.jp/list/pathway/hsa", timeout=10)
       
    except Exception:
        return {}
        url = f"{self.BASE}/list/pathway/hsa"
        r = requests.get(url)

        if r.status_code != 200:
            print("⚠️ Failed to load KEGG pathway list.")
            return

        for line in r.text.strip().split("\n"):
            try:
                pid, name = line.split("\t")
                pid = pid.replace("path:", "").strip()
                self.pathway_cache[pid] = name.strip()
            except:
                continue

        print(f"✅ Loaded {len(self.pathway_cache)} KEGG pathways.")

    # ----------------------------------------------------
    # 1) Gene → list of pathway IDs
    # ----------------------------------------------------
    def gene_pathways(self, gene_id: str):
        url = f"{self.BASE}/link/pathway/{gene_id}"
        r = requests.get(url)

        if r.status_code != 200 or not r.text.strip():
            return {"error": f"No KEGG pathways found for {gene_id}"}

        pathways = sorted([
            line.split("\t")[1].replace("path:", "")
            for line in r.text.strip().split("\n")
        ])

        return {"gene": gene_id, "pathways": pathways}

    # ----------------------------------------------------
    # 2) Get readable pathway name (from cache)
    # ----------------------------------------------------
    def pathway_name(self, pid: str) -> str:
        return self.pathway_cache.get(pid, "Unknown pathway")

    # ----------------------------------------------------
    # 3) KEGG pathway raw info
    # ----------------------------------------------------
    def pathway_info(self, pathway_id: str):
        url = f"{self.BASE}/get/{pathway_id}"
        r = requests.get(url)

        if r.status_code != 200:
            return {"error": f"No info found for pathway {pathway_id}"}

        return {"pathway_id": pathway_id, "raw": r.text}

    # ----------------------------------------------------
    # 4) Pathway map (PNG)
    # ----------------------------------------------------
    def pathway_map(self, pid: str):
        pid = pid.replace("hsa", "").replace("map", "").strip()
        url = f"https://www.kegg.jp/kegg/pathway/map/map{pid}.png"

        return f"""
        <iframe src="{url}"
                style="width:100%; height:900px; border:none;">
        </iframe>
        """
