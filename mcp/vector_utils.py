#!/usr/bin/env python3
"""
Vector Store ID Detection Utilities

Handles automatic detection of OpenAI vector store IDs from Agency Swarm
created files_vs_* folders or environment variables.
"""

import glob
import logging
import os
import re

logger = logging.getLogger(__name__)


def detect_vector_store_id():
    """
    Detect vector store ID using priority order:
    1. VECTOR_STORE_ID environment variable (highest priority)
    2. Auto-detect from files_vs_* folders in agency directories
    3. Error if none found

    Returns:
        str: Vector store ID (e.g., "vs_123abc456def")

    Raises:
        ValueError: If no vector store configuration is found
    """
    # Priority 1: Environment variable
    env_vector_store_id = os.getenv("VECTOR_STORE_ID", "")
    if env_vector_store_id:
        logger.info(f"Using vector store ID from environment: {env_vector_store_id}")
        return env_vector_store_id

    # Priority 2: Auto-detect from files_vs_* folders
    vs_folders = _find_vector_store_folders()

    if not vs_folders:
        _raise_no_vector_store_error()

    # Handle multiple vector stores
    if len(vs_folders) > 1:
        logger.warning(f"Multiple vector stores found: {vs_folders}")
        # Use the most recently modified one
        latest_folder = max(vs_folders, key=lambda x: os.path.getmtime(x))
        logger.info(f"Using most recently modified: {latest_folder}")
        vs_folder = latest_folder
    else:
        vs_folder = vs_folders[0]
        logger.info(f"Found vector store folder: {vs_folder}")

    # Extract vector store ID from folder name
    return _extract_vector_store_id_from_folder(vs_folder)


def _find_vector_store_folders():
    """
    Search for files_vs_* folders in project directories.

    Returns:
        list: List of found vector store folder paths
    """
    # Search for files_vs_* folders from project root (handles both direct and mcp/ execution)
    search_patterns = [
        "**/files_vs_*",  # Current directory and subdirectories
        "../**/files_vs_*",  # Parent directory and subdirectories (for mcp/ execution)
    ]

    vs_folders = []
    for pattern in search_patterns:
        vs_folders.extend(glob.glob(pattern, recursive=True))

    # Remove duplicates (can happen with overlapping patterns)
    return list(set(vs_folders))


def _extract_vector_store_id_from_folder(vs_folder):
    """
    Extract vector store ID from files_vs_* folder name.

    Args:
        vs_folder (str): Path to vector store folder

    Returns:
        str: Extracted vector store ID

    Raises:
        ValueError: If folder name format is invalid
    """
    folder_name = os.path.basename(vs_folder)
    match = re.match(r"files_vs_(.+)", folder_name)

    if not match:
        logger.error(f"Invalid vector store folder format: {folder_name}")
        logger.error("Expected format: files_vs_[vector_store_id]")
        raise ValueError(f"Invalid vector store folder format: {folder_name}")

    vector_store_id = match.group(1)
    if not str(vector_store_id).startswith("vs_"):
        vector_store_id = "vs_" + vector_store_id
    logger.info(f"Extracted vector store ID: {vector_store_id}")
    return vector_store_id


def _raise_no_vector_store_error():
    """
    Raise a descriptive error when no vector store is found.

    Raises:
        ValueError: With detailed guidance for fixing the issue
    """
    logger.error("No vector store found. Expected either:")
    logger.error("1. VECTOR_STORE_ID environment variable, or")
    logger.error("2. files_vs_* folder created by Agency Swarm")
    logger.error(
        "Run an agency first (e.g., 'cd BasicResearchAgency && python agency.py') to create vector store"
    )
    raise ValueError("No vector store configuration found")
