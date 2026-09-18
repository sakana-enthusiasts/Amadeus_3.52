"""仅生成独立 parent 副本，公开证据始终绑定 observed form。"""

from dataclasses import replace

from .数据结构 import CompoundIdentity


def standardize_identity(identity: CompoundIdentity) -> CompoundIdentity:
    if not identity.observed_structure:
        return identity
    from rdkit import Chem, rdBase
    from rdkit.Chem.MolStandardize import rdMolStandardize
    mol = Chem.MolFromSmiles(identity.observed_structure)
    if mol is None:
        raise ValueError("Invalid observed SMILES; original chemical form was preserved")
    observed_key = Chem.MolToInchiKey(mol)
    if identity.inchikey and observed_key and identity.inchikey != observed_key:
        raise ValueError("Observed SMILES and InChIKey describe different chemical forms")
    if identity.standardized_parent_structure:
        return replace(identity, inchikey=identity.inchikey or observed_key)
    parent = rdMolStandardize.FragmentParent(rdMolStandardize.Cleanup(mol))
    parent = rdMolStandardize.Uncharger().uncharge(parent)
    return replace(identity, inchikey=identity.inchikey or observed_key,
                   standardized_parent_structure=Chem.MolToSmiles(parent, isomericSmiles=True),
                   standardization_version=f"rdkit-{rdBase.rdkitVersion}:cleanup-fragmentparent-uncharger-v1")
