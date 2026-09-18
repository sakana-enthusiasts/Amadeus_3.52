"""源字段映射外置。Solubility 的介质必须由记录提供，不能默认当成水。"""

PUBCHEM_PROPERTY_MAP = {
    "Solubility": "water_solubility", "Density": "density", "Refractive Index": "refractive_index",
    "Viscosity": "viscosity", "Melting Point": "melting_point", "Boiling Point": "boiling_point",
    "Vapor Pressure": "vapor_pressure", "Dissociation Constants": "pKa", "LogP": "logP",
    "Surface Tension": "surface_tension",
}
PUBCHEM_COMPUTED_MAP = {
    "MolecularFormula": ("molecular_formula", ""), "MolecularWeight": ("molecular_weight", "g/mol"),
    "CanonicalSMILES": ("canonical_smiles", ""), "ConnectivitySMILES": ("canonical_smiles", ""),
    "IsomericSMILES": ("isomeric_smiles", ""), "SMILES": ("isomeric_smiles", ""),
    "InChI": ("inchi", ""), "InChIKey": ("inchikey", ""), "Charge": ("formal_charge", "1"),
    "XLogP": ("logP", "1"), "TPSA": ("tpsa", "angstrom2"),
    "HBondDonorCount": ("hbd", "1"), "HBondAcceptorCount": ("hba", "1"),
    "RotatableBondCount": ("rotatable_bonds", "1"), "HeavyAtomCount": ("heavy_atom_count", "1"),
    "Complexity": ("complexity", "1"),
}
REST_PROPERTIES = ("CanonicalSMILES", "IsomericSMILES", "InChI", "InChIKey", "MolecularFormula",
                   "MolecularWeight", "Charge", "XLogP", "TPSA", "HBondDonorCount", "HBondAcceptorCount",
                   "RotatableBondCount", "HeavyAtomCount", "Complexity")
DIMENSIONLESS = {"pKa", "logP", "refractive_index"}
