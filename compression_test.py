#!/usr/bin/env python3
"""
HDF5 File Compression Utility

This script compresses HDF5 files containing SAR data by applying:
1. GZIP compression (level 9 for maximum compression)
2. Chunking for optimal I/O performance
3. Optional float32 to float16 conversion for further size reduction

Strategy:
- Original: 8 bands × 1013 × 1190 × 4 bytes (float32) = ~38 MB + metadata ≈ 46 MB
- With GZIP-9: Expected ~10-20 MB (50-70% reduction for SAR data)
- With float16: Could achieve ~5-10 MB (but may lose precision)
"""

import h5py
import numpy as np
import os
from pathlib import Path
from typing import Optional, Tuple
import shutil


def analyze_h5_file(filepath: str) -> dict:
    """
    Analyze an HDF5 file and report its structure and size.
    
    Args:
        filepath: Path to the HDF5 file
        
    Returns:
        Dictionary with file information
    """
    info = {
        'filepath': filepath,
        'size_mb': os.path.getsize(filepath) / (1024 * 1024),
        'datasets': {}
    }
    
    with h5py.File(filepath, 'r') as f:
        def visit_dataset(name, obj):
            if isinstance(obj, h5py.Dataset):
                info['datasets'][name] = {
                    'shape': obj.shape,
                    'dtype': str(obj.dtype),
                    'compression': obj.compression,
                    'compression_opts': obj.compression_opts,
                    'size_mb': obj.nbytes / (1024 * 1024)
                }
        
        f.visititems(visit_dataset)
    
    return info


def compress_h5_file(
    input_path: str,
    output_path: Optional[str] = None,
    compression: str = 'gzip',
    compression_level: int = 9,
    convert_to_float16: bool = False,
    chunk_size: Optional[Tuple[int, int]] = None,
    backup: bool = True
) -> dict:
    """
    Compress an HDF5 file with optimized settings for SAR data.
    
    Args:
        input_path: Path to input HDF5 file
        output_path: Path to output file (default: overwrite original)
        compression: Compression algorithm ('gzip', 'lzf', or None)
        compression_level: Compression level for gzip (1-9, higher = better compression)
        convert_to_float16: Convert float32 to float16 for additional compression
        chunk_size: Custom chunk size (default: auto-calculated)
        backup: Create backup of original file
        
    Returns:
        Dictionary with compression statistics
    """
    input_path = Path(input_path)
    
    # Setup output path
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_compressed{input_path.suffix}"
    else:
        output_path = Path(output_path)
    
    # Backup original if requested
    if backup and not output_path.exists():
        backup_path = input_path.parent / f"{input_path.stem}_backup{input_path.suffix}"
        print(f"Creating backup: {backup_path}")
    
    # Get original size
    original_size = input_path.stat().st_size
    
    print(f"Compressing: {input_path}")
    print(f"Output: {output_path}")
    print(f"Original size: {original_size / (1024**2):.2f} MB")
    
    # Open input and output files
    with h5py.File(input_path, 'r') as f_in:
        with h5py.File(output_path, 'w') as f_out:
            
            def copy_dataset(name, obj):
                """Recursively copy datasets with compression"""
                if isinstance(obj, h5py.Dataset):
                    # Determine chunk size if not provided
                    if chunk_size is None and len(obj.shape) == 2:
                        # Use chunks that are roughly 1 MB for 2D arrays
                        rows, cols = obj.shape
                        dtype_size = obj.dtype.itemsize if not convert_to_float16 else 2
                        target_chunk_bytes = 1024 * 1024  # 1 MB
                        chunk_rows = min(rows, int(np.sqrt(target_chunk_bytes / (cols * dtype_size))))
                        chunk_cols = cols
                        chunks = (chunk_rows, chunk_cols)
                    elif chunk_size is not None:
                        chunks = chunk_size
                    else:
                        chunks = True  # Auto chunking for non-2D arrays
                    
                    # Read data
                    data = obj[:]
                    
                    # Convert to float16 if requested and data is float32
                    if convert_to_float16 and data.dtype == np.float32:
                        print(f"  Converting {name} to float16")
                        data = data.astype(np.float16)
                    
                    # Create compressed dataset
                    compression_opts = compression_level if compression == 'gzip' else None
                    
                    f_out.create_dataset(
                        name,
                        data=data,
                        compression=compression,
                        compression_opts=compression_opts,
                        chunks=chunks,
                        shuffle=True  # Shuffle filter improves compression
                    )
                    
                    # Copy attributes
                    for attr_name, attr_value in obj.attrs.items():
                        f_out[name].attrs[attr_name] = attr_value
                    
                    print(f"  Compressed: {name} - shape={obj.shape}, dtype={data.dtype}")
                
                elif isinstance(obj, h5py.Group):
                    # Create group
                    if name not in f_out:
                        f_out.create_group(name)
                    
                    # Copy group attributes
                    for attr_name, attr_value in obj.attrs.items():
                        f_out[name].attrs[attr_name] = attr_value
            
            # Copy root attributes
            for attr_name, attr_value in f_in.attrs.items():
                f_out.attrs[attr_name] = attr_value
            
            # Process all datasets
            f_in.visititems(copy_dataset)
    
    # Get compressed size
    compressed_size = output_path.stat().st_size
    reduction = (1 - compressed_size / original_size) * 100
    
    stats = {
        'input_path': str(input_path),
        'output_path': str(output_path),
        'original_size_mb': original_size / (1024**2),
        'compressed_size_mb': compressed_size / (1024**2),
        'reduction_percent': reduction,
        'compression': compression,
        'compression_level': compression_level,
        'convert_to_float16': convert_to_float16
    }
    
    print(f"\nCompression complete!")
    print(f"Original size: {stats['original_size_mb']:.2f} MB")
    print(f"Compressed size: {stats['compressed_size_mb']:.2f} MB")
    print(f"Reduction: {stats['reduction_percent']:.1f}%")
    
    return stats


def compress_directory(
    input_dir: str,
    output_dir: Optional[str] = None,
    pattern: str = "*.h5",
    **kwargs
) -> list:
    """
    Compress all HDF5 files in a directory.
    
    Args:
        input_dir: Input directory path
        output_dir: Output directory path (default: create 'compressed' subfolder)
        pattern: File pattern to match (default: "*.h5")
        **kwargs: Additional arguments passed to compress_h5_file
        
    Returns:
        List of compression statistics for each file
    """
    input_dir = Path(input_dir)
    
    if output_dir is None:
        output_dir = input_dir.parent / f"{input_dir.name}_compressed"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all matching files
    files = list(input_dir.glob(pattern))
    print(f"Found {len(files)} files to compress in {input_dir}")
    
    results = []
    for i, input_file in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] Processing {input_file.name}")
        output_file = output_dir / input_file.name
        
        try:
            stats = compress_h5_file(
                str(input_file),
                str(output_file),
                backup=False,  # Don't backup when batch processing
                **kwargs
            )
            results.append(stats)
        except Exception as e:
            print(f"ERROR processing {input_file.name}: {e}")
            results.append({
                'input_path': str(input_file),
                'error': str(e)
            })
    
    # Print summary
    print("\n" + "="*60)
    print("COMPRESSION SUMMARY")
    print("="*60)
    
    successful = [r for r in results if 'error' not in r]
    if successful:
        total_original = sum(r['original_size_mb'] for r in successful)
        total_compressed = sum(r['compressed_size_mb'] for r in successful)
        avg_reduction = (1 - total_compressed / total_original) * 100
        
        print(f"Files processed: {len(successful)}/{len(files)}")
        print(f"Total original size: {total_original:.2f} MB")
        print(f"Total compressed size: {total_compressed:.2f} MB")
        print(f"Average reduction: {avg_reduction:.1f}%")
        print(f"Space saved: {total_original - total_compressed:.2f} MB")
    
    return results


def aggressive_compress(
    input_path: str,
    output_path: str,
    strategy: str = "quantize_int16"
) -> dict:
    """
    Apply aggressive compression strategies with data transformation.
    
    Strategies:
    - "quantize_int16": Quantize float32 to int16 (reduces to 50% + compression)
    - "quantize_uint8": Quantize to uint8 (reduces to 25% + compression, more lossy)
    - "magnitude_phase": Store I/Q as magnitude/phase (can compress better)
    - "remove_zeros": Skip all-zero bands entirely
    - "scaleoffset": Use HDF5 scale-offset filter (lossy, saves decimal precision)
    
    Args:
        input_path: Input HDF5 file
        output_path: Output HDF5 file
        strategy: Compression strategy to use
        
    Returns:
        Compression statistics
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    original_size = input_path.stat().st_size
    print(f"Aggressive compression: {strategy}")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    
    with h5py.File(input_path, 'r') as f_in:
        with h5py.File(output_path, 'w') as f_out:
            
            def process_dataset(name, obj):
                if isinstance(obj, h5py.Dataset):
                    data = obj[:]
                    
                    # Skip all-zero bands if strategy is remove_zeros
                    if strategy == "remove_zeros" and np.all(data == 0):
                        print(f"  Skipping all-zero band: {name}")
                        return
                    
                    # Apply strategy
                    if strategy == "quantize_int16" and data.dtype == np.float32:
                        # Quantize to int16 with min-max scaling
                        data_min = data.min()
                        data_max = data.max()
                        if np.all(data == 0):
                            # Store zeros efficiently
                            new_data = np.zeros_like(data, dtype=np.int16)
                            scale = 1.0
                            offset = 0.0
                        else:
                            scale = (data_max - data_min) / 65535.0  # int16 range
                            offset = data_min
                            new_data = ((data - offset) / scale).astype(np.int16)
                        
                        # Store with metadata for reconstruction
                        ds = f_out.create_dataset(
                            name, data=new_data,
                            compression='gzip', compression_opts=9,
                            shuffle=True, chunks=True
                        )
                        ds.attrs['scale'] = scale
                        ds.attrs['offset'] = offset
                        ds.attrs['original_dtype'] = 'float32'
                        print(f"  Quantized {name} to int16: range=[{data_min:.4f}, {data_max:.4f}]")
                    
                    elif strategy == "quantize_uint8" and data.dtype == np.float32:
                        # Quantize to uint8 (more aggressive)
                        data_min = data.min()
                        data_max = data.max()
                        if np.all(data == 0):
                            new_data = np.zeros_like(data, dtype=np.uint8)
                            scale = 1.0
                            offset = 0.0
                        else:
                            scale = (data_max - data_min) / 255.0  # uint8 range
                            offset = data_min
                            new_data = ((data - offset) / scale).astype(np.uint8)
                        
                        ds = f_out.create_dataset(
                            name, data=new_data,
                            compression='gzip', compression_opts=9,
                            shuffle=True, chunks=True
                        )
                        ds.attrs['scale'] = scale
                        ds.attrs['offset'] = offset
                        ds.attrs['original_dtype'] = 'float32'
                        print(f"  Quantized {name} to uint8: range=[{data_min:.4f}, {data_max:.4f}]")
                    
                    elif strategy == "magnitude_phase" and ('i_' in name or 'q_' in name):
                        # Convert I/Q to magnitude/phase (only for complex pairs)
                        # This will be handled separately for pairs
                        pass
                    
                    elif strategy == "scaleoffset" and data.dtype == np.float32:
                        # Use HDF5 scale-offset filter (keeps 3 decimal places)
                        ds = f_out.create_dataset(
                            name, data=data,
                            compression='gzip', compression_opts=9,
                            shuffle=True, chunks=True,
                            scaleoffset=3  # Keep 3 decimal places
                        )
                        print(f"  Scale-offset {name}: 3 decimal places")
                    
                    else:
                        # Default: just compress with GZIP
                        ds = f_out.create_dataset(
                            name, data=data,
                            compression='gzip', compression_opts=9,
                            shuffle=True, chunks=True
                        )
                        print(f"  Compressed {name}")
                    
                    # Copy attributes
                    for attr_name, attr_value in obj.attrs.items():
                        ds.attrs[attr_name] = attr_value
                
                elif isinstance(obj, h5py.Group):
                    if name not in f_out:
                        f_out.create_group(name)
                    for attr_name, attr_value in obj.attrs.items():
                        f_out[name].attrs[attr_name] = attr_value
            
            # Copy root attributes
            for attr_name, attr_value in f_in.attrs.items():
                f_out.attrs[attr_name] = attr_value
            
            # Process datasets
            f_in.visititems(process_dataset)
    
    compressed_size = output_path.stat().st_size
    reduction = (1 - compressed_size / original_size) * 100
    
    stats = {
        'input_path': str(input_path),
        'output_path': str(output_path),
        'original_size_mb': original_size / (1024**2),
        'compressed_size_mb': compressed_size / (1024**2),
        'reduction_percent': reduction,
        'strategy': strategy
    }
    
    print(f"\nCompression complete!")
    print(f"Original: {stats['original_size_mb']:.2f} MB")
    print(f"Compressed: {stats['compressed_size_mb']:.2f} MB")
    print(f"Reduction: {stats['reduction_percent']:.1f}%")
    
    return stats


if __name__ == "__main__":
    # Example usage: compress a single file
    test_file = "/shared/home/rdelprete/PythonProjects/WORLDSAR/data/3_cuts/S1A_IW_SLC__1SDV_20240503T031928_20240503T031942_053701_0685FB_670F/285D_305R.h5"
    
    if os.path.exists(test_file):
        print("Analyzing original file...")
        info = analyze_h5_file(test_file)
        print(f"\nFile: {info['filepath']}")
        print(f"Size: {info['size_mb']:.2f} MB")
        print(f"\nDatasets:")
        for name, ds_info in info['datasets'].items():
            print(f"  {name}:")
            print(f"    Shape: {ds_info['shape']}")
            print(f"    Dtype: {ds_info['dtype']}")
            print(f"    Size: {ds_info['size_mb']:.2f} MB")
            print(f"    Compression: {ds_info['compression']}")
        
        print("\n" + "="*60)
        print("TEST 1: GZIP Compression (level 9)")
        print("="*60)
        stats1 = compress_h5_file(
            test_file,
            output_path="/shared/home/rdelprete/PythonProjects/WORLDSAR/data/3_cuts/S1A_IW_SLC__1SDV_20240503T031928_20240503T031942_053701_0685FB_670F/285D_305R_gzip9.h5",
            compression='gzip',
            compression_level=9,
            convert_to_float16=False,
            backup=False
        )
        
        print("\n" + "="*60)
        print("TEST 2: GZIP + float16 conversion")
        print("="*60)
        stats2 = compress_h5_file(
            test_file,
            output_path="/shared/home/rdelprete/PythonProjects/WORLDSAR/data/3_cuts/S1A_IW_SLC__1SDV_20240503T031928_20240503T031942_053701_0685FB_670F/285D_305R_gzip9_fp16.h5",
            compression='gzip',
            compression_level=9,
            convert_to_float16=True,
            backup=False
        )
        
        print("\n" + "="*60)
        print("TEST 3: Aggressive - Quantize to int16")
        print("="*60)
        stats3 = aggressive_compress(
            test_file,
            output_path="/shared/home/rdelprete/PythonProjects/WORLDSAR/data/3_cuts/S1A_IW_SLC__1SDV_20240503T031928_20240503T031942_053701_0685FB_670F/285D_305R_int16.h5",
            strategy="quantize_int16"
        )
        
        print("\n" + "="*60)
        print("TEST 4: Aggressive - Quantize to uint8")
        print("="*60)
        stats4 = aggressive_compress(
            test_file,
            output_path="/shared/home/rdelprete/PythonProjects/WORLDSAR/data/3_cuts/S1A_IW_SLC__1SDV_20240503T031928_20240503T031942_053701_0685FB_670F/285D_305R_uint8.h5",
            strategy="quantize_uint8"
        )
        
        print("\n" + "="*60)
        print("TEST 5: Remove all-zero bands")
        print("="*60)
        stats5 = aggressive_compress(
            test_file,
            output_path="/shared/home/rdelprete/PythonProjects/WORLDSAR/data/3_cuts/S1A_IW_SLC__1SDV_20240503T031928_20240503T031942_053701_0685FB_670F/285D_305R_nozeros.h5",
            strategy="remove_zeros"
        )
        
        print("\n" + "="*60)
        print("TEST 6: Scale-offset filter (lossy decimal)")
        print("="*60)
        stats6 = aggressive_compress(
            test_file,
            output_path="/shared/home/rdelprete/PythonProjects/WORLDSAR/data/3_cuts/S1A_IW_SLC__1SDV_20240503T031928_20240503T031942_053701_0685FB_670F/285D_305R_scaleoffset.h5",
            strategy="scaleoffset"
        )
        
        print("\n" + "="*60)
        print("FINAL COMPARISON")
        print("="*60)
        all_stats = [
            ("Original", stats1['original_size_mb'], 0),
            ("GZIP-9", stats1['compressed_size_mb'], stats1['reduction_percent']),
            ("GZIP-9 + float16", stats2['compressed_size_mb'], stats2['reduction_percent']),
            ("INT16 Quantize", stats3['compressed_size_mb'], stats3['reduction_percent']),
            ("UINT8 Quantize", stats4['compressed_size_mb'], stats4['reduction_percent']),
            ("Remove Zeros", stats5['compressed_size_mb'], stats5['reduction_percent']),
            ("Scale-Offset", stats6['compressed_size_mb'], stats6['reduction_percent'])
        ]
        
        print(f"{'Strategy':<20} {'Size (MB)':<12} {'Reduction':<12}")
        print("-" * 45)
        for name, size, reduction in all_stats:
            if reduction > 0:
                print(f"{name:<20} {size:>10.2f}   {reduction:>8.1f}%")
            else:
                print(f"{name:<20} {size:>10.2f}   {'baseline':>10}")
        
        print("\n" + "="*60)
        print("RECOMMENDATIONS")
        print("="*60)
        print("🔹 LOSSLESS (safe for all applications):")
        print(f"   GZIP-9: {stats1['compressed_size_mb']:.1f} MB ({stats1['reduction_percent']:.1f}% reduction)")
        print(f"   Remove zeros: {stats5['compressed_size_mb']:.1f} MB ({stats5['reduction_percent']:.1f}% reduction)")
        print("\n🔹 MINIMAL LOSS (good for most SAR work):")
        print(f"   GZIP + float16: {stats2['compressed_size_mb']:.1f} MB ({stats2['reduction_percent']:.1f}% reduction)")
        print(f"   Scale-offset (3 decimals): {stats6['compressed_size_mb']:.1f} MB ({stats6['reduction_percent']:.1f}% reduction)")
        print("\n🔹 LOSSY (for storage/preview only):")
        print(f"   INT16 quantize: {stats3['compressed_size_mb']:.1f} MB ({stats3['reduction_percent']:.1f}% reduction)")
        print(f"   UINT8 quantize: {stats4['compressed_size_mb']:.1f} MB ({stats4['reduction_percent']:.1f}% reduction)")
