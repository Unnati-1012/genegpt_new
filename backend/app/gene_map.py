# backend/app/gene_map.py
"""
Gene symbol to UniProt accession mapping for GeneGPT.
"""

from typing import Optional


# Common gene symbols mapped to UniProt accessions (human)
KNOWN_GENE_MAP = {
    # Tumor suppressors
    "TP53": "P04637",
    "BRCA1": "P38398",
    "BRCA2": "P51587",
    "RB1": "P06400",
    "PTEN": "P60484",
    "APC": "P25054",
    "VHL": "P40337",
    "NF1": "P21359",
    "NF2": "P35240",
    "WT1": "P19544",
    
    # Oncogenes
    "EGFR": "P00533",
    "KRAS": "P01116",
    "NRAS": "P01111",
    "HRAS": "P01112",
    "BRAF": "P15056",
    "MYC": "P01106",
    "MYCN": "P04198",
    "MDM2": "Q00987",
    "BCL2": "P10415",
    "ABL1": "P00519",
    
    # Kinases
    "AKT1": "P31749",
    "AKT2": "P31751",
    "AKT3": "Q9Y243",
    "PIK3CA": "P42336",
    "MTOR": "P42345",
    "JAK2": "O60674",
    "SRC": "P12931",
    "ERBB2": "P04626",  # HER2
    "HER2": "P04626",
    "MET": "P08581",
    "ALK": "Q9UM73",
    "RET": "P07949",
    "KIT": "P10721",
    "FLT3": "P36888",
    "PDGFRA": "P16234",
    "FGFR1": "P11362",
    "FGFR2": "P21802",
    "FGFR3": "P22607",
    
    # DNA repair
    "ATM": "Q13315",
    "ATR": "Q13535",
    "CHEK1": "O14757",
    "CHEK2": "O96017",
    "RAD51": "Q06609",
    "PALB2": "Q86YC2",
    
    # Cell cycle
    "CDK4": "P11802",
    "CDK6": "Q00534",
    "CDKN1A": "P38936",  # p21
    "CDKN2A": "P42771",  # p16
    "CCND1": "P24385",
    
    # Transcription factors
    "STAT3": "P40763",
    "STAT5A": "P42229",
    "STAT5B": "P51692",
    "NFKB1": "P19838",
    "JUN": "P05412",
    "FOS": "P01100",
    
    # Apoptosis
    "CASP3": "P42574",
    "CASP8": "Q14790",
    "CASP9": "P55211",
    "BAX": "Q07812",
    "BAK1": "Q16611",
    
    # Immune checkpoints
    "PDCD1": "Q15116",  # PD-1
    "CD274": "Q9NZQ7",  # PD-L1
    "CTLA4": "P16410",
    
    # Housekeeping / common
    "GAPDH": "P04406",
    "ACTB": "P60709",
    "TUBB": "P07437",
    "HSP90AA1": "P07900",
    "HSP70": "P0DMV8",
    
    # Insulin/metabolism
    "INS": "P01308",
    "INSR": "P06213",
    "IGF1": "P05019",
    "IGF1R": "P08069",
    "PPARG": "P37231",
    
    # Neuroscience
    "APP": "P05067",
    "MAPT": "P10636",  # Tau
    "SNCA": "P37840",  # Alpha-synuclein
    "PSEN1": "P49768",
    "PSEN2": "P49810",
    "SOD1": "P00441",
    "HTT": "P42858",  # Huntingtin
    
    # COVID / viral
    "ACE2": "Q9BYF1",
    "TMPRSS2": "O15393",
}


def get_accession_for_gene(gene_symbol: str) -> Optional[str]:
    """
    Get UniProt accession for a gene symbol.
    
    Args:
        gene_symbol: Gene symbol (e.g., 'TP53', 'EGFR')
        
    Returns:
        UniProt accession or None if not found
    """
    return KNOWN_GENE_MAP.get(gene_symbol.upper())


def find_gene_in_text(text: str) -> Optional[str]:
    """
    Find a known gene symbol in text and return its accession.
    
    Args:
        text: Text to search
        
    Returns:
        UniProt accession or None
    """
    text_upper = text.upper()
    
    # Check exact match first
    if text_upper.strip() in KNOWN_GENE_MAP:
        return KNOWN_GENE_MAP[text_upper.strip()]
    
    # Check each word
    for word in text_upper.split():
        if word in KNOWN_GENE_MAP:
            return KNOWN_GENE_MAP[word]
    
    return None
