COMPTOX_PROPERTY_MAP = {
    "Water Solubility": "water_solubility", "water solubility": "water_solubility",
    "Boiling Point": "boiling_point", "Melting Point": "melting_point", "Density": "density",
    "Vapor Pressure": "vapor_pressure", "Viscosity": "viscosity", "LogKow": "logP",
    "Octanol Water Partition Coefficient": "logP", "pKa Acidic": "pKa", "pKa Basic": "pKa",
    "Refractive Index": "refractive_index", "Surface Tension": "surface_tension",
}
CHEMISTRY_MAP = {
    "smiles": "observed_smiles", "qsarReadySmiles": "qsar_ready_smiles", "msReadySmiles": "ms_ready_smiles",
    "inchikey": "inchikey", "inchiString": "inchi", "molFormula": "molecular_formula",
}
# 分领域端点来自 EPA CTX OpenAPI，不调用其他源。
DOMAIN_PATHS = {
    "chemistry": "chemical/detail/search/by-dtxsid/{id}?projection=chemicaldetailstandard",
    "experimental": "chemical/property/experimental/search/by-dtxsid/{id}",
    "predicted": "chemical/property/predicted/search/by-dtxsid/{id}",
    "toxval": "hazard/toxval/search/by-dtxsid/{id}",
    "toxref": "hazard/toxref/data/search/by-dtxsid/{id}",
    "bioactivity": "bioactivity/data/search/by-dtxsid/{id}",
    "toxicokinetics": "hazard/adme-ivive/search/by-dtxsid/{id}",
}
