"""
Utility functions for cross-camera tracking
"""

import json
import os


def create_output_dirs(output_dir='output'):
    """
    Create output directories if they don't exist

    Args:
        output_dir: Base output directory
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'visualizations'), exist_ok=True)


def save_json(data, filepath):
    """
    Save data to JSON file with pretty formatting

    Args:
        data: Data to save
        filepath: Output file path
    """
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✓ Saved to: {filepath}")


def load_json(filepath):
    """
    Load JSON file

    Args:
        filepath: Input file path

    Returns:
        Parsed JSON data
    """
    with open(filepath, 'r') as f:
        return json.load(f)
