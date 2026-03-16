from analysis.dependencies import network as _network

build_network_data = _network.build_network_data
load_proposal_json_documents = _network.load_proposal_json_documents
normalize_proposal_ids = _network.normalize_proposal_ids
save_network_data_artifacts = _network.save_network_data_artifacts

__all__ = [
    "build_network_data",
    "load_proposal_json_documents",
    "normalize_proposal_ids",
    "save_network_data_artifacts",
    "load_bip_json_documents",
]


def load_bip_json_documents(source_dir):
    # Backward-compatible alias.
    return load_proposal_json_documents(source_dir)
