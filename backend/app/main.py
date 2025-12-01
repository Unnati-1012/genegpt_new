import os
from dotenv import load_dotenv

load_dotenv()
print("Loaded environment:", os.environ.get("GOOGLE_API_KEY"))

import os
from dotenv import load_dotenv
import pathlib

# Path: backend/app/main.py
# Move UP one directory to reach backend/
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

print("Loading .env from:", ENV_PATH)

load_dotenv(ENV_PATH)

print("Loaded GOOGLE_API_KEY:", os.environ.get("GOOGLE_API_KEY"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pathlib
import re

# existing imports...
from .pubchem_tools import PubChemTools

# STRING (NEW)
from .string_tools import STRINGTools
string_db = STRINGTools()

# NEW: Google Image Search  (ONLY THIS ONE)
from .google_image_tools import GoogleImageSearch
image_search = GoogleImageSearch()

# Ensembl
from .ensembl_tools import EnsemblTools
ensembl = EnsemblTools()

# KEGG
from .kegg_tools import KEGGTools
kegg = KEGGTools()

# NCBI
from .ncbi_tools import NCBITools
ncbi = NCBITools()

# PubChem
from .pubchem_tools import PubChemTools
pubchem = PubChemTools()

# STRING (NEW)
from .string_tools import STRINGTools
string_db = STRINGTools()

# Router + LLM
from .uniprot_tools import route_query, multimodal_response, KNOWN_GENE_MAP
from .llm_client import LLMClient

# PDB
from .pdb_tools import PDBTools
pdb = PDBTools()

from .clinvar_tools import ClinVarTools
clinvar = ClinVarTools()

# -------------------------------------------------
# PATH FIX
# -------------------------------------------------
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR.parent / "frontend" / "static"

print("📁 Serving static from:", FRONTEND_DIR)

# -------------------------------------------------
# APP
# -------------------------------------------------
app = FastAPI()
llm = LLMClient()

# -------------------------------------------------
# STATIC
# -------------------------------------------------
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# -------------------------------------------------
# MODELS (Updated for conversation history)
# -------------------------------------------------
class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


# -------------------------------------------------
# CORS
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _render_clinvar_table(gene: str, data: dict):
    """Build reply text + HTML table for a ClinVar variants_for_gene() result."""

    if "error" in data:
        return data["error"], None

    variants = data.get("results", [])
    if not variants:
        return f"No ClinVar variants found for {gene}.", None

    # Count significance categories
    counts = {}
    for v in variants:
        sig = (v.get("clinical_significance") or "Unknown").strip()
        counts[sig] = counts.get(sig, 0) + 1

    # Summary text
    lines = [f"ClinVar variants for {gene}:"]
    for sig, n in counts.items():
        lines.append(f"- {sig}: {n} variants")

    # Build table rows
    rows = ""
    for v in variants:
        vid = v.get("id", "")
        sig = v.get("clinical_significance", "Unknown")
        conds = ", ".join(v.get("conditions", [])) or "—"
        review = v.get("review_status", "Unknown")

        rows += f"""
            <tr>
                <td style='padding:6px;border:1px solid #555;'>{vid}</td>
                <td style='padding:6px;border:1px solid #555;'>{sig}</td>
                <td style='padding:6px;border:1px solid #555;'>{conds}</td>
                <td style='padding:6px;border:1px solid #555;'>{review}</td>
            </tr>
        """

    # Full HTML table
    html = f"""
        <h3>ClinVar variants for <b>{gene}</b></h3>
        <table style='width:100%; border-collapse:collapse; margin-top:8px;'>
            <tr style='background:#333;color:#fff;'>
                <th style='padding:6px;border:1px solid #555;'>ID</th>
                <th style='padding:6px;border:1px solid #555;'>Significance</th>
                <th style='padding:6px;border:1px solid #555;'>Conditions</th>
                <th style='padding:6px;border:1px solid #555;'>Review status</th>
            </tr>
            {rows}
        </table>
    """

    return "\n".join(lines), html


# -------------------------------------------------
# HELPER: PROCESS A SINGLE QUERY
# -------------------------------------------------
async def process_single_query(msg: str, messages: list[dict]):
    lowered = msg.lower()
    print("🔍 Sub-query:", msg)

    # 0) Explicit IMAGE
    if any(word in lowered for word in ["image", "picture", "photo", "diagram"]):
        img_data = image_search.search_images(msg, num=3)

        if "error" in img_data:
            return {"reply": img_data["error"], "html": None}

        results = img_data["results"]

        items_html = []
        for i, r in enumerate(results, start=1):
            url = r["link"]
            title = r["title"]
            items_html.append(
                f"<li style='margin-bottom:8px;'>"
                f"<a href='{url}' target='_blank'>{i}. {title}</a>"
                f"</li>"
            )

        html = (
            "<p>Here are some image links you can click:</p>"
            "<ol style='padding-left:20px;'>"
            + "".join(items_html)
            + "</ol>"
        )
        reply = "Here are some image links related to your query."
        return {"reply": reply, "html": html}

    # -------------------------------------------------
    # 0.5) ClinVar: natural-language mutation / variant queries
    #      e.g. "list mutations for TP53", "variants in BRCA2",
    #           "what variants of MSH2 does clinvar have?"
    # -------------------------------------------------
    clinvar_gene = None

    if any(w in lowered for w in ["mutation", "mutations", "variant", "variants"]):
        tokens = re.split(r"[\s,():]+", msg)

        # Words we should *never* treat as gene symbols
        stopwords = {
            "WHAT",
            "WHICH",
            "VARIANT",
            "VARIANTS",
            "MUTATION",
            "MUTATIONS",
            "OF",
            "IN",
            "FOR",
            "DO",
            "DOES",
            "HAS",
            "HAVE",
            "ALL",
            "ANY",
            "SHOW",
            "LIST",
            "PLEASE",
            "CLINVAR",
            "GENE",
            "WITH",
            "THE",
        }

        # scan from the end – usually the gene symbol is near the end
        for tok in reversed(tokens):
            t = tok.upper().strip()
            if not t:
                continue
            if t in stopwords:
                continue

            # prefer known common genes first
            if t in KNOWN_GENE_MAP:
                clinvar_gene = t
                break

            # otherwise accept reasonable gene-like tokens (letters/digits, length 3–10)
            if re.fullmatch(r"[A-Z0-9]{3,10}", t):
                clinvar_gene = t
                break

    if clinvar_gene:
        data = clinvar.variants_for_gene(clinvar_gene)
        reply_text, html = _render_clinvar_table(clinvar_gene, data)

        if (
            html
            or ("No ClinVar variants" in reply_text)
            or ("error" in reply_text.lower())
        ):
            return {"reply": reply_text, "html": html}

    # ROUTER (UniProt / AlphaFold / etc.)
    routed = route_query(msg)
    if routed:
        print("🔬 Router activated")
        return routed

    # NCBI Gene
    if lowered.startswith("gene") or "ncbi gene" in lowered:
        cleaned = lowered.replace("ncbi gene", "").replace("gene", "").strip()
        result = ncbi.gene_search(cleaned)

        if isinstance(result, dict) and "gene_id" in result:
            summary = ncbi.gene_summary(result["gene_id"])
            return {"reply": str(summary), "html": None}

    # PubMed search
    if lowered.startswith("pubmed "):
        query = msg[len("pubmed ") :].strip()
        results = []

        papers = ncbi.pubmed_search(query)

        if not papers or "error" in papers:
            return {"reply": f"No PubMed results for '{query}'.", "html": None}

        results = papers.get("results", []) or []

        if not results:
            return {"reply": f"No PubMed results for '{query}'.", "html": None}

        items = []
        for i, p in enumerate(results, start=1):
            title = p.get("title", "No title")
            authors = p.get("authors", "Unknown authors")
            year = p.get("year", "N/A")
            pmid = p.get("pmid", "")
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            items.append(
                f"<li style='margin-bottom:10px;'>"
                f"<b>{i}. {title}</b><br>"
                f"<small>{authors} — {year}</small><br>"
                f"<a href='{link}' target='_blank'>🔗 PubMed (PMID {pmid})</a>"
                f"</li>"
            )

        html = "<ol style='padding-left:20px;'>" + "".join(items) + "</ol>"
        return {"reply": f"PubMed results for '{query}':", "html": html}

    # Fake protein blocker
    fake = re.search(
        r"\b(visualize|show|model)\s+([A-Za-z0-9_\-]+)\s+protein\b", lowered
    )
    if fake:
        token = fake.group(2).upper()
        if token not in KNOWN_GENE_MAP and not re.match(
            r"^[A-Z][0-9][A-Z0-9]{3}[0-9]$", token
        ):
            return multimodal_response(
                "This does not appear to be a real protein. Provide a valid UniProt ID.",
                None,
            )

    # KEGG gene
    if lowered.startswith("kegg gene"):
        gene = lowered.replace("kegg gene", "").strip()
        data = kegg.gene_pathways(gene)

        if "error" in data:
            return {"reply": data["error"], "html": None}

        items = []
        for pid in data["pathways"]:
            name = kegg.pathway_name(pid)
            url = f"https://www.kegg.jp/dbget-bin/www_bget?{pid}"
            items.append(
                f"<li><a href='{url}' target='_blank'>{pid}: {name}</a></li>"
            )

        html = "<ul>" + "".join(items) + "</ul>"
        return {"reply": f"KEGG pathways for {gene}:", "html": html}

    # KEGG pathway
    if lowered.startswith("kegg pathway"):
        pid = lowered.replace("kegg pathway", "").strip()
        info = kegg.pathway_info(pid)

        raw = info.get("raw", "")
        name = "Unknown"
        clazz = "Unknown"
        drugs = []

        for line in raw.split("\n"):
            if line.startswith("NAME"):
                name = line.replace("NAME", "").strip()
            if line.startswith("CLASS"):
                clazz = line.replace("CLASS", "").strip()
            if line.startswith("DRUG"):
                drugs.append(line.replace("DRUG", "").strip())

        html = f"""
        <b>Pathway:</b> {pid}<br>
        <b>Name:</b> {name}<br>
        <b>Class:</b> {clazz}<br><br>

        <details>
            <summary><b>Drugs ({len(drugs)})</b></summary>
            <pre>{chr(10).join(drugs)}</pre>
        </details>
        <br>

        <details>
            <summary><b>Full KEGG File</b></summary>
            <pre>{raw}</pre>
        </details>
        """

        return {"reply": f"Details for KEGG pathway {pid}:", "html": html}

    # Explicit ClinVar command
    if lowered.startswith("clinvar"):
        rest = msg.split(" ", 1)[1].strip() if " " in msg else ""

        if not rest:
            return {
                "reply": "Usage:\n- clinvar TP53\n- clinvar id 12345",
                "html": None,
            }

        # ID mode
        id_match = re.fullmatch(r"(id\s+)?(\d+)", rest, flags=re.IGNORECASE)
        if id_match:
            cid = id_match.group(2)
            rec = clinvar.record_details(cid)

            if "error" in rec:
                return {"reply": rec["error"], "html": None}

            lines = [
                f"ClinVar record {rec['id']}",
                f"Title: {rec['title']}",
                f"Type: {rec['type']}",
                f"Clinical significance: {rec['clinical_significance']}",
                f"Conditions: {', '.join(rec['conditions'] or [])}",
                f"Review status: {rec['review_status']}",
                f"RCV accession: {rec.get('rcvaccession','')}",
            ]
            return {"reply": "\n".join(lines), "html": None}

        # Gene mode
        gene = rest.upper()
        data = clinvar.variants_for_gene(gene)

        reply_text, html = _render_clinvar_table(gene, data)
        return {"reply": reply_text, "html": html}

    # STRING DB
    if lowered.startswith("string"):
        token = msg[len("string") :].strip()
        if not token:
            return {"reply": "Use: string <gene_symbol>", "html": None}

        data = string_db.fetch_interactions(token)

        if "error" in data:
            return {"reply": data["error"], "html": None}

        interactions = data.get("interactions", [])
        if not interactions:
            return {"reply": f"No STRING interactions for '{token}'.", "html": None}

        rows = ""
        for item in interactions:
            partner = item["partner"]
            score = item["score"]
            sid = item["string_id"]
            link = f"https://string-db.org/network/{sid}"

            rows += (
                f"<tr>"
                f"<td style='padding:6px;border:1px solid #555;'>"
                f"<a href='{link}' target='_blank'>{partner}</a>"
                f"</td>"
                f"<td style='padding:6px;border:1px solid #555;'>{score}</td>"
                f"</tr>"
            )

        html = f"""
        <h3>STRING Interactions for <b>{token.upper()}</b></h3>

        <table style='width:100%; border-collapse:collapse; margin-top:10px;'>
            <tr style='background:#444;'>
                <th style='padding:8px; border:1px solid #666;'>Partner</th>
                <th style='padding:8px; border:1px solid #666;'>Score</th>
            </tr>
            {rows}
        </table>

        <br>
        <h3>Network Image</h3>
        <img src="{ string_db.network_image(token) }"
             alt="STRING network"
             style="width:100%; border-radius:10px; border:1px solid #555;">
        """

        return {"reply": f"STRING interactions for {token}:", "html": html}

    # Google Images
    if "show me" in lowered or "picture" in lowered:
        img_data = image_search.search_images(msg, num=3)

        if "error" in img_data:
            return {"reply": img_data["error"], "html": None}

        results = img_data.get("results", []) or []
        if not results:
            return {"reply": "No images found.", "html": None}

        md_links = "\n".join(
            [f"- [{r['title']}]({r['link']})" for r in results]
        )

        return {
            "reply": f"Here are some image results for **{msg}**:\n\n{md_links}",
            "html": None,
        }

    # Ensembl
    if lowered.startswith("ensembl"):
        rest = msg[len("ensembl") :].strip()
        parts = rest.split()

        if not parts:
            return {
                "reply": "Specify: ensembl gene <symbol>, ensembl id <ID>, ensembl transcripts <ID>, ensembl region <loc>",
                "html": None,
            }

        subcmd = parts[0].lower()

        if subcmd == "gene" and len(parts) >= 2:
            symbol = parts[1].upper()
            gene = ensembl.lookup_gene(symbol, species="human")
            if not gene:
                return {"reply": f"No Ensembl gene for '{symbol}'.", "html": None}

            r = [
                f"Ensembl gene for {symbol}",
                f"ID: {gene['id']}",
                f"Name: {gene.get('display_name', '')}",
                f"Species: {gene.get('species', '')}",
                f"Description: {gene.get('description', '')}",
                "",
                "Location:",
                f"{gene.get('seq_region_name', '')}:{gene.get('start', '')}-{gene.get('end', '')} (strand {gene.get('strand', '')})",
                "",
                f"Biotype: {gene.get('biotype', '')}",
                f"Version: {gene.get('version', '')}",
            ]
            return {"reply": "\n".join(r), "html": None}

        if subcmd == "id" and len(parts) >= 2:
            stable_id = parts[1].upper()
            obj = ensembl.lookup_id(stable_id)
            if not obj:
                return {"reply": f"No Ensembl record for '{stable_id}'.", "html": None}

            r = [
                f"Ensembl object: {stable_id}",
                f"Type: {obj.get('object_type', '')}",
                f"Name: {obj.get('display_name', '')}",
                f"Species: {obj.get('species', '')}",
                f"Description: {obj.get('description', '')}",
                "",
                "Location:",
                f"{obj.get('seq_region_name', '')}:{obj.get('start', '')}-{obj.get('end', '')} (strand {obj.get('strand', '')})",
                "",
                f"Biotype: {obj.get('biotype', '')}",
                f"Parent: {obj.get('parent', '')}",
            ]
            return {"reply": "\n".join(r), "html": None}

        if subcmd in ("transcript", "transcripts") and len(parts) >= 2:
            gene_id = parts[1]
            transcripts = ensembl.gene_transcripts(gene_id)
            if not transcripts:
                return {
                    "reply": f"No transcripts found for '{gene_id}'.",
                    "html": None,
                }

            lines = [f"Transcripts for {gene_id} (showing {len(transcripts)}):", ""]
            for t in transcripts:
                lines.append(
                    f"- {t['id']} | {t.get('biotype', '')} | "
                    f"{t.get('seq_region_name', '') or ''}:{t.get('start', '')}-{t.get('end', '')} len={t.get('length', '')}"
                )
            return {"reply": "\n".join(lines), "html": None}

        if subcmd == "region" and len(parts) >= 2:
            region = parts[1].replace('"', "").replace("”", "").replace("“", "")
            seq_info = ensembl.region_sequence(region, species="human")
            if not seq_info:
                return {
                    "reply": f"Could not fetch sequence for '{region}'.",
                    "html": None,
                }

            seq = seq_info["seq"]
            preview = seq[:60] + ("..." if len(seq) > 60 else "")

            r = [
                f"Ensembl region sequence ({region})",
                f"Length: {seq_info['length']} bp",
                "",
                "Preview:",
                preview,
            ]
            return {"reply": "\n".join(r), "html": None}

        return {"reply": "Unknown Ensembl command.", "html": None}

    # KEGG Map
    if lowered.startswith("kegg map"):
        pid = lowered.replace("kegg map", "").strip()
        iframe = kegg.pathway_map(pid)
        return {"reply": f"Showing KEGG map for {pid}", "html": iframe}

    # FALLBACK TO LLM
    reply = await llm.get_response_from_messages(messages)
    return multimodal_response(reply, None)


# -------------------------------------------------
# CHAT ENDPOINT
# -------------------------------------------------
@app.post("/chat")
async def chat(req: ChatRequest):

    messages = [m.model_dump() for m in req.messages]
    msg = req.messages[-1].content.strip()

    print("📩 Incoming:", msg)

    if " and " in msg:
        parts = [p.strip() for p in msg.split(" and ") if p.strip()]
    else:
        parts = [msg]

    if len(parts) == 1:
        return await process_single_query(msg, messages)

    combined_reply_parts = []
    combined_html_blocks = []

    for part in parts:
        sub_messages = messages + [{"role": "user", "content": part}]
        res = await process_single_query(part, sub_messages)

        if res.get("reply"):
            combined_reply_parts.append(f"### {part}\n{res['reply']}")

        if res.get("html"):
            combined_html_blocks.append(
                f"<div style='margin:15px 0;padding:12px;border-radius:8px;'>"
                f"<h3>{part}</h3>{res['html']}</div>"
            )

    combined_reply = "\n\n".join(combined_reply_parts) if combined_reply_parts else ""
    combined_html = "".join(combined_html_blocks) if combined_html_blocks else None

    if not combined_reply and combined_html:
        combined_reply = "Here are the results for your combined query."

    return {"reply": combined_reply, "html": combined_html}
