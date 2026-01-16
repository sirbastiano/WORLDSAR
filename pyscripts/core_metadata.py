from datetime import datetime
import h5py
import numpy as np


def read_h5(file_path: str) -> tuple[dict, dict]:
    """Read an HDF5 file and return its contents and metadata as dictionaries.
    
    Args:
        file_path: Path to the HDF5 file to read.
        
    Returns:
        Tuple containing:
            - Dictionary with datasets and their values from the HDF5 file
            - Dictionary with metadata (attributes) from the HDF5 file
        
    Raises:
        FileNotFoundError: If the file doesn't exist.
        OSError: If the file cannot be opened or read.
    """
    data = {}
    metadata = {}
    
    with h5py.File(file_path, 'r') as h5_file:
        # Extract root attributes
        metadata['root'] = dict(h5_file.attrs)
        
        def extract_data(name, obj):
            if isinstance(obj, h5py.Dataset):
                data[name] = obj[()]
                # Extract dataset attributes
                if obj.attrs:
                    metadata[name] = dict(obj.attrs)
            elif isinstance(obj, h5py.Group):
                # Extract group attributes
                if obj.attrs:
                    metadata[name] = dict(obj.attrs)
        
        h5_file.visititems(extract_data)
    
    return data, metadata


def extract_core_metadata_sentinel(md: dict) -> dict:
    """
    Extract a minimal, cross-mission–relevant SAR metadata subset
    for geospatial foundation models.

    Args:
        md (dict): Metadata dictionary containing SAR metadata.

    Returns:
        dict: A dictionary containing the extracted metadata subset with the following keys:
            - MISSION
            - ACQUISITION_MODE
            - PRODUCT_TYPE
            - radar_frequency
            - pulse_repetition_frequency
            - range_spacing
            - azimuth_spacing
            - range_bandwidth
            - azimuth_bandwidth
            - PASS
            - avg_scene_height
    """
    def _decode(v):
        # SNAP often stores strings as bytes
        if isinstance(v, (bytes, bytearray)):
            return v.decode('utf-8')
        return v

    keys = [
        'MISSION',
        'ACQUISITION_MODE',
        'PRODUCT_TYPE',
        'radar_frequency',
        'pulse_repetition_frequency',
        'range_spacing',
        'azimuth_spacing',
        'range_bandwidth',
        'azimuth_bandwidth',
        'antenna_pointing',
        'PASS',
        'avg_scene_height',
        'PRODUCT',
        'mds1_tx_rx_polar',
        'mds2_tx_rx_polar',
        'first_line_time',
    ]

    return {
        k: _decode(md.get(k))
        for k in keys
        if k in md
    }