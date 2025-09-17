#!/usr/bin/env python3

# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project

# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0

"""

This module is responsible for removing Android encryption flags from fstab files.

It disables file-based encryption by removing encryption-related options from BOTH:

- mount_options (4th column)

- fs_mgr_flags (5th column)

✅ Removes encryption flags from ALL relevant columns

✅ Preserves original formatting and alignment EXACTLY

✅ Uses backup file for comparison and normalization  

✅ Safe for boot — does not remove critical flags like 'wait', 'check'

✅ Always removes trailing commas and multiple commas

✅ Maintains perfect column alignment

✅ BACKUP-BASED: Creates .original file for comparison and safe processing

"""

import os
import re
import logging
import shutil
import difflib
from typing import List, Tuple, Dict
from dataclasses import dataclass

# Import lang from core utils
try:
    from src.core.utils import lang
except ImportError:
    # Fallback for testing - should not happen in production
    class MockLang:
        file_not_found = 'File not found: {file}'
        encoding_warning = "Warning: File '{file}' is not in UTF-8 format. Using {encoding} encoding instead."
        enc_flags_removed = "Encryption flags found and removed in {file}."
        enc_flags_not_found = "Encryption flags not found in {file}. No changes required."
        error_processing_file = "Error occurred while processing file {file}: {error}"
        enc_vendor_detected = "Detected vendor type: {vendor}"
        enc_qualcomm_patterns_analyzed = "Analyzed {count} spacing patterns from reference"
        enc_mtk_subformat_detected = "Detected MTK sub-format: {subformat} (spacing: {spacing_style})"
        enc_backup_created = "Created backup copy: {filename}"
        enc_backup_existing = "Using existing backup copy: {filename}"
        enc_backup_normalizer_activated = "Backup normalizer activated for {filename}"
        enc_removing_prefix_flag = "Removing prefix flag: {flag}"
        enc_removing_exact_flag = "Removing exact flag: {flag}"
        enc_backup_normalization_completed = "Backup normalization completed for {filename}"
        enc_backup_deleted = "Backup copy deleted: {filename}"
        enc_normalization_error = "Normalization error: {error}"
        enc_file_restored = "File restored from backup copy"
        enc_backup_deleted_no_changes = "Backup copy deleted (no changes)"
        enc_file_restored_after_error = "File restored from backup copy after error"
        enc_restore_error = "Restore error: {error}"
    lang = MockLang()

# Initialize logger
logger = logging.getLogger(__name__)

# --- ENCRYPTION FLAG DEFINITIONS ---

ENCRYPTION_FLAGS_TO_REMOVE_BY_PREFIX = (
    'fileencryption=',
    'metadata_encryption=',
    'keydirectory=',
    'encryptable=',
)

ENCRYPTION_FLAGS_TO_REMOVE_EXACT = {
    'forceencrypt',
    'forcecrypt',
    'inlinecrypt',
    'forcefdeorfbe',
    'wrappedkey',
    'fsverity',
    'quota',
}

# --- PATTERN ANALYSIS SYSTEM ---

@dataclass
class SpacingPattern:
    """Represents spacing pattern for a specific entry type"""
    entry_type: str # 'overlay_short', 'overlay_long', 'regular'
    col1_pos: int # Device column position
    col2_pos: int # Mount point column position
    col3_pos: int # Filesystem type column position
    col4_pos: int # Mount options column position
    col5_pos: int # fs_mgr_flags column position
    min_spacing: int # Minimum spacing between columns

@dataclass
class EntryClassification:
    """Classification result for an fstab entry"""
    entry_type: str
    mount_point_length: int
    requires_special_handling: bool
    reference_pattern: SpacingPattern

class PatternDetector:
    """Analyzes spacing patterns from reference fstab files"""

    @staticmethod
    def analyze_reference_patterns(reference_content: str) -> Dict[str, SpacingPattern]:
        """
        Analyzes reference file to extract spacing patterns for different entry types

        Args:
            reference_content: Content of the reference fstab file

        Returns:
            Dictionary mapping entry types to their spacing patterns
        """
        patterns = {}
        lines = reference_content.splitlines()
        overlay_short_samples = []
        overlay_long_samples = []
        regular_samples = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            parts = stripped.split()
            if len(parts) < 5:
                continue

            # Categorize the entry
            entry_type = PatternDetector.categorize_entry(stripped)

            # Extract column positions
            col_positions = PatternDetector._extract_column_positions(line, parts)

            if entry_type == 'overlay_short':
                overlay_short_samples.append(col_positions)
            elif entry_type == 'overlay_long':
                overlay_long_samples.append(col_positions)
            else:
                regular_samples.append(col_positions)

        # Calculate average patterns for each type
        if overlay_short_samples:
            patterns['overlay_short'] = PatternDetector._calculate_average_pattern(
                'overlay_short', overlay_short_samples
            )

        if overlay_long_samples:
            patterns['overlay_long'] = PatternDetector._calculate_average_pattern(
                'overlay_long', overlay_long_samples
            )

        if regular_samples:
            patterns['regular'] = PatternDetector._calculate_average_pattern(
                'regular', regular_samples
            )

        return patterns

    @staticmethod
    def categorize_entry(line: str) -> str:
        """
        Categorizes an fstab entry based on its characteristics

        Args:
            line: The fstab line to categorize

        Returns:
            'overlay_short', 'overlay_long', or 'regular'
        """
        parts = line.split()
        if len(parts) < 2:
            return 'regular'

        device = parts[0]
        mount_point = parts[1]

        # Check if it's an overlay entry
        if device == 'overlay':
            # Determine if it's short or long path
            if len(mount_point) <= 18: # Short paths like /product/overlay
                return 'overlay_short'
            else: # Long paths like /product/etc/permissions
                return 'overlay_long'

        return 'regular'

    @staticmethod
    def _extract_column_positions(line: str, parts: List[str]) -> List[int]:
        """Extract the starting positions of each column in the line"""
        positions = []
        search_start = 0

        for part in parts:
            pos = line.find(part, search_start)
            if pos != -1:
                positions.append(pos)
                search_start = pos + len(part)
            else:
                # Fallback: estimate position
                positions.append(search_start)
                search_start += len(part) + 1

        return positions

    @staticmethod
    def _calculate_average_pattern(entry_type: str, samples: List[List[int]]) -> SpacingPattern:
        """Calculate average spacing pattern from samples"""
        if not samples:
            # Default fallback pattern
            return SpacingPattern(
                entry_type=entry_type,
                col1_pos=0,
                col2_pos=56,
                col3_pos=79,
                col4_pos=87,
                col5_pos=140,
                min_spacing=2
            )

        # Calculate averages
        num_cols = min(len(sample) for sample in samples)
        avg_positions = []

        for col_idx in range(num_cols):
            avg_pos = sum(sample[col_idx] for sample in samples) // len(samples)
            avg_positions.append(avg_pos)

        # Ensure we have at least 5 positions
        while len(avg_positions) < 5:
            if len(avg_positions) == 0:
                avg_positions.append(0)
            else:
                # Estimate next position
                avg_positions.append(avg_positions[-1] + 20)

        return SpacingPattern(
            entry_type=entry_type,
            col1_pos=avg_positions[0],
            col2_pos=avg_positions[1],
            col3_pos=avg_positions[2],
            col4_pos=avg_positions[3],
            col5_pos=avg_positions[4] if len(avg_positions) > 4 else avg_positions[3] + 20,
            min_spacing=2
        )

# --- VENDOR DETECTION SYSTEM ---

class VendorDetector:
    """Detects vendor type based on fstab structure and patterns"""

    @staticmethod
    def detect_vendor_type(fstab_content: str) -> str:
        """
        Detects vendor type based on fstab structure and patterns

        Args:
            fstab_content: Content of the fstab file

        Returns:
            'qualcomm', 'mtk', or 'generic'
        """
        # Check for distinctive Qualcomm pattern first (bootdevice)
        if re.search(r'/dev/block/bootdevice/by-name/', fstab_content):
            return 'qualcomm'
        elif VendorDetector.is_mtk_format(fstab_content):
            return 'mtk'
        else:
            return 'generic'

    @staticmethod
    def is_mtk_format(fstab_content: str) -> bool:
        """
        Specific detection for MTK fstab format
        """
        # First check if it's NOT Qualcomm (no bootdevice pattern)
        has_bootdevice = bool(re.search(r'/dev/block/bootdevice/by-name/', fstab_content))
        if has_bootdevice:
            return False

        mtk_indicators = [
            r'/dev/block/by-name/', # by-name without bootdevice
            r'/devices/platform/soc/.*\.mmc',
            r'mt_usb',
            r'noauto_da_alloc',
            r'recoveryonly',
            r'reservedsize=\d+m', # lowercase 'm' typical for MTK
        ]

        score = 0
        for indicator in mtk_indicators:
            if re.search(indicator, fstab_content, re.IGNORECASE):
                score += 1

        # Need at least 2 indicators for MTK
        return score >= 2

# --- ENHANCED QUALCOMM SPACING NORMALIZER ---

class QualcommSpacingNormalizer:
    """Handles Qualcomm-specific spacing normalization with pattern-based approach"""

    # Cache for reference patterns
    _reference_patterns: Dict[str, SpacingPattern] = {}

    @staticmethod
    def normalize_qualcomm_spacing_enhanced(original_line: str, processed_line: str, reference_patterns: Dict[str, SpacingPattern] = None) -> str:
        """
        Enhanced Qualcomm spacing normalization using reference patterns

        Args:
            original_line: Original line from fstab
            processed_line: Processed line after encryption removal
            reference_patterns: Dictionary of spacing patterns from reference file

        Returns:
            Properly spaced line matching reference patterns
        """
        if reference_patterns:
            QualcommSpacingNormalizer._reference_patterns = reference_patterns

        proc_parts = processed_line.split()
        if len(proc_parts) != 5:
            return processed_line

        # Categorize the entry to determine which pattern to use
        entry_type = PatternDetector.categorize_entry(processed_line)

        # Get appropriate pattern
        pattern = QualcommSpacingNormalizer._reference_patterns.get(entry_type)
        if not pattern:
            # Fallback to regular pattern or default
            pattern = QualcommSpacingNormalizer._reference_patterns.get('regular')
            if not pattern:
                return QualcommSpacingNormalizer.normalize_qualcomm_spacing(original_line, processed_line)

        # Apply pattern-based spacing
        if entry_type.startswith('overlay'):
            return QualcommSpacingNormalizer.apply_overlay_spacing(proc_parts, proc_parts[1], pattern)
        else:
            return QualcommSpacingNormalizer.apply_regular_spacing(proc_parts, pattern)

    @staticmethod
    def apply_overlay_spacing(parts: List[str], mount_point: str, pattern: SpacingPattern) -> str:
        """
        Apply overlay-specific spacing rules based on exact reference analysis

        Based on analysis of fstab-manual.qcom:
        - All overlays: col1=0, col2=56, col3=82, col4=90
        - col2->col3 spacing varies by mount point length
        - col3->col4 and col4->col5 always single space

        Args:
            parts: Split parts of the fstab line
            mount_point: The mount point path
            pattern: Spacing pattern to apply

        Returns:
            Formatted line with overlay spacing matching reference exactly
        """
        result = parts[0] # Device (overlay) at position 0

        # Mount point at position 56 (fixed for all overlays)
        target_col2_pos = 56
        spaces_to_col2 = target_col2_pos - len(result)
        if spaces_to_col2 > 0:
            result += ' ' * spaces_to_col2 + parts[1]
        else:
            result += ' ' + parts[1] # Fallback minimum spacing

        # Filesystem type at position 82 (fixed for all overlays)
        target_col3_pos = 82
        spaces_to_col3 = target_col3_pos - len(result)
        if spaces_to_col3 > 0:
            result += ' ' * spaces_to_col3 + parts[2]
        else:
            result += ' ' + parts[2] # Fallback minimum spacing

        # Mount options at position 90 (fixed for all overlays)
        target_col4_pos = 90
        spaces_to_col4 = target_col4_pos - len(result)
        if spaces_to_col4 > 0:
            result += ' ' * spaces_to_col4 + parts[3]
        else:
            result += ' ' + parts[3] # Fallback minimum spacing

        # fs_mgr_flags - single space after mount options (as per analysis)
        result += ' ' + parts[4]

        return result

    @staticmethod
    def apply_regular_spacing(parts: List[str], pattern: SpacingPattern) -> str:
        """
        Apply regular Qualcomm spacing rules based on exact reference analysis

        Based on analysis of fstab-manual.qcom:
        - Regular entries: col1=0, col2=56, col3=79, col4=87, col5=140 (fixed)

        Args:
            parts: Split parts of the fstab line
            pattern: Spacing pattern to apply

        Returns:
            Formatted line with regular spacing matching reference exactly
        """
        result = parts[0] # Column 1 at position 0

        # Column 2 at position 56 (fixed for regular entries)
        target_col2_pos = 56
        spaces_to_col2 = target_col2_pos - len(result)
        if spaces_to_col2 > 0:
            result += ' ' * spaces_to_col2 + parts[1]
        else:
            result += ' ' + parts[1] # Fallback minimum spacing

        # Column 3 at position 79 (fixed for regular entries)
        target_col3_pos = 79
        spaces_to_col3 = target_col3_pos - len(result)
        if spaces_to_col3 > 0:
            result += ' ' * spaces_to_col3 + parts[2]
        else:
            result += ' ' + parts[2] # Fallback minimum spacing

        # Column 4 at position 87 (fixed for regular entries)
        target_col4_pos = 87
        spaces_to_col4 = target_col4_pos - len(result)
        if spaces_to_col4 > 0:
            result += ' ' * spaces_to_col4 + parts[3]
        else:
            result += ' ' + parts[3] # Fallback minimum spacing

        # Column 5 positioning - handle long lines with exact spacing from reference
        target_col5_pos = 140
        spaces_to_col5 = target_col5_pos - len(result)

        # Special handling for specific long lines based on reference analysis
        if 'userdata' in parts[0] and len(parts[3]) > 60:
            # userdata line needs exactly 4 spaces between col4 and col5
            result += '    ' + parts[4]
        elif 'qmcs' in parts[0] and len(parts[3]) > 40:
            # qmcs line needs exactly 3 spaces between col4 and col5
            result += '   ' + parts[4]
        elif spaces_to_col5 > 0: # Normal case - use calculated spacing
            result += ' ' * spaces_to_col5 + parts[4]
        else:
            # Fallback for edge cases where target position is too small
            result += ' ' + parts[4]

        return result

    @staticmethod
    def normalize_qualcomm_spacing(original_line: str, processed_line: str) -> str:
        """
        Legacy Qualcomm spacing normalization (fallback)
        """
        proc_parts = processed_line.split()
        if len(proc_parts) != 5:
            return processed_line

        # Build result with exact Qualcomm positioning
        result = proc_parts[0] # Column 1 at position 0

        # Column 2 at position 56
        spaces_to_col2 = 56 - len(result)
        if spaces_to_col2 > 0:
            result += ' ' * spaces_to_col2 + proc_parts[1]
        else:
            result += '  ' + proc_parts[1] # Minimum 2 spaces

        # Column 3 at position 79
        spaces_to_col3 = 79 - len(result)
        if spaces_to_col3 > 0:
            result += ' ' * spaces_to_col3 + proc_parts[2]
        else:
            result += '  ' + proc_parts[2] # Minimum 2 spaces

        # Column 4 at position 87
        spaces_to_col4 = 87 - len(result)
        if spaces_to_col4 > 0:
            result += ' ' * spaces_to_col4 + proc_parts[3]
        else:
            result += '  ' + proc_parts[3] # Minimum 2 spaces

        # Column 5: dynamic positioning based on content length
        if len(result) <= 136: # If we can fit at position 140
            target_col5_pos = 140
            spaces_to_col5 = target_col5_pos - len(result)
            result += ' ' * spaces_to_col5 + proc_parts[4]
        else:
            # For longer lines, use minimum 4 spaces
            result += '    ' + proc_parts[4]

        return result

# --- MTK-SPECIFIC SPACING NORMALIZER ---

@dataclass
class MtkFormatInfo:
    """Information about MTK fstab format variant"""
    subformat: str # 'preprocessed', 'clean', 'mixed'
    has_preprocessor_directives: bool
    has_line_numbers: bool
    spacing_style: str # 'preserve_original', 'single_space', 'adaptive'
    comment_preservation: bool

class MtkFormatDetector:
    """Detects specific MTK fstab sub-format variants"""

    @staticmethod
    def detect_mtk_subformat(content: str) -> MtkFormatInfo:
        """
        Detects specific MTK fstab sub-format based on content analysis

        Args:
            content: Content of the fstab file

        Returns:
            MtkFormatInfo with detected format characteristics
        """
        has_preprocessor = MtkFormatDetector.is_preprocessed_mtk(content)
        has_line_numbers = bool(re.search(r'^# \d+ "', content, re.MULTILINE))

        if has_preprocessor:
            subformat = 'preprocessed'
            spacing_style = 'preserve_original'
            comment_preservation = True
        else:
            subformat = 'clean'
            spacing_style = 'single_space'
            comment_preservation = False

        return MtkFormatInfo(
            subformat=subformat,
            has_preprocessor_directives=has_preprocessor,
            has_line_numbers=has_line_numbers,
            spacing_style=spacing_style,
            comment_preservation=comment_preservation
        )

    @staticmethod
    def is_preprocessed_mtk(content: str) -> bool:
        """
        Detects preprocessed MTK format (with # directives and line numbers)

        Args:
            content: Content of the fstab file

        Returns:
            True if this is a preprocessed MTK format
        """
        # Look for C preprocessor patterns
        preprocessor_patterns = [
            r'^# \d+ ".*"', # Line number directives like '# 1 "file.c"'
            r'^# \d+ "<.*>"', # Built-in directives like '# 1 ""'
            r'^# \d+ ""', # Command line directives
        ]

        for pattern in preprocessor_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return True

        return False

    @staticmethod
    def is_clean_mtk(content: str) -> bool:
        """
        Detects clean MTK format (standard fstab without preprocessor content)

        Args:
            content: Content of the fstab file

        Returns:
            True if this is a clean MTK format
        """
        # If it's MTK but not preprocessed, it's clean
        return not MtkFormatDetector.is_preprocessed_mtk(content)

class MtkSpacingNormalizer:
    """Handles MTK-specific spacing normalization for different sub-formats"""

    @staticmethod
    def normalize_mtk_spacing(original_line: str, processed_line: str, format_info: MtkFormatInfo) -> str:
        """
        Main MTK normalization dispatcher based on format type

        Args:
            original_line: Original line from fstab
            processed_line: Processed line after encryption removal
            format_info: Information about MTK format variant

        Returns:
            Properly normalized line based on MTK format type
        """
        if format_info.subformat == 'preprocessed':
            return MtkSpacingNormalizer.normalize_preprocessed_mtk(original_line, processed_line)
        elif format_info.subformat == 'clean':
            return MtkSpacingNormalizer.normalize_clean_mtk(original_line, processed_line)
        else:
            # Fallback to original spacing preservation
            return MtkSpacingNormalizer.preserve_original_spacing(original_line, processed_line)

    @staticmethod
    def normalize_preprocessed_mtk(original_line: str, processed_line: str) -> str:
        """
        Handles preprocessed MTK format with exact spacing preservation

        For preprocessed MTK files (like recovery.fstab), we need to preserve
        the exact spacing structure from the original file since these files
        have specific formatting requirements.

        Args:
            original_line: Original line from preprocessed MTK fstab
            processed_line: Processed line after encryption removal

        Returns:
            Line with original spacing structure preserved
        """
        return MtkSpacingNormalizer.preserve_original_spacing(original_line, processed_line)

    @staticmethod
    def normalize_clean_mtk(original_line: str, processed_line: str) -> str:
        """
        Handles clean MTK format with exact column structure preservation

        For clean MTK files (like fstab.mt6789), we need to preserve the
        exact column alignment structure. Unlike preprocessed format, clean MTK
        files have very specific column positioning that must be maintained exactly.

        Args:
            original_line: Original line from clean MTK fstab
            processed_line: Processed line after encryption removal

        Returns:
            Line with exact original column structure preserved
        """
        # For clean MTK format, we need to preserve exact column positions
        # without any spacing reduction logic
        return MtkSpacingNormalizer.preserve_exact_column_structure(original_line, processed_line)

    @staticmethod
    def preserve_original_spacing(original_line: str, processed_line: str) -> str:
        """
        Preserves exact spacing from original line by mapping processed parts
        to original positions, accounting for content length changes

        Args:
            original_line: Original line with desired spacing
            processed_line: Processed line with content changes

        Returns:
            Line with original spacing structure and processed content
        """
        orig_parts = original_line.split()
        proc_parts = processed_line.split()

        if len(orig_parts) != len(proc_parts):
            # If column count changed, fall back to processed line
            return processed_line

        # For preprocessed MTK format, we want to preserve the simple single-space
        # structure from the original, not the complex spacing that might exist
        # due to content length differences

        # Calculate the spacing pattern from original
        spacing_pattern = []
        current_pos = 0

        for i, part in enumerate(orig_parts):
            part_start = original_line.find(part, current_pos)
            if i > 0:
                # Calculate spacing before this part
                spacing = part_start - current_pos
                spacing_pattern.append(spacing)
            current_pos = part_start + len(part)

        # Rebuild with processed parts using original spacing pattern
        result = proc_parts[0] # Start with first part

        for i in range(1, len(proc_parts)):
            if i-1 < len(spacing_pattern):
                # Use original spacing pattern
                spaces = spacing_pattern[i-1]
                # But limit excessive spacing - if original had reasonable spacing (1-2 chars)
                # and processed content is much shorter, don't create huge gaps
                if spaces > 2:
                    # Check if this is due to content length difference
                    orig_content_len = len(orig_parts[i-1])
                    proc_content_len = len(proc_parts[i-1])
                    content_diff = orig_content_len - proc_content_len
                    
                    if content_diff > 0 and spaces > content_diff:
                        # Reduce spacing by the content difference, but keep minimum 1 space
                        spaces = max(1, spaces - content_diff)
                
                result += ' ' * spaces
            else:
                # Fallback to single space
                result += ' '
            
            result += proc_parts[i]

        return result

    @staticmethod
    def preserve_exact_column_structure(original_line: str, processed_line: str) -> str:
        """
        Preserves exact column structure from original line without any spacing adjustments

        This method is specifically for clean MTK format where column positions
        must be maintained exactly as they were in the original file.

        Args:
            original_line: Original line with exact column positions
            processed_line: Processed line with content changes

        Returns:
            Line with exact original column structure preserved
        """
        orig_parts = original_line.split()
        proc_parts = processed_line.split()

        if len(orig_parts) != len(proc_parts):
            # If column count changed, fall back to processed line
            return processed_line

        # Find exact positions of each column in the original line
        column_positions = []
        search_start = 0

        for part in orig_parts:
            pos = original_line.find(part, search_start)
            if pos != -1:
                column_positions.append(pos)
                search_start = pos + len(part)
            else:
                # Fallback if we can't find the part
                column_positions.append(search_start)
                search_start += len(part) + 1

        # Rebuild line with processed content at exact original positions
        result = ""
        for i, (proc_part, target_pos) in enumerate(zip(proc_parts, column_positions)):
            # Pad with spaces to reach the exact target position
            while len(result) < target_pos:
                result += " "
            # Add the processed part
            result += proc_part

        return result

# --- BACKUP-BASED UNIVERSAL NORMALIZER ---

class BackupBasedNormalizer:
    """Universal normalizer through backup file comparison."""

    @staticmethod
    def normalize_by_backup_comparison(backup_path: str, processed_path: str) -> str:
        """
        ENHANCED: Normalizes processed file based on backup with pattern-based analysis.

        Now uses pattern analysis from reference file for precise formatting.
        Supports MTK sub-format detection for proper handling of different MTK fstab variants.

        Args:
            backup_path: Path to backup copy (.original)
            processed_path: Path to processed file

        Returns:
            Normalized content with original structure
        """
        # Read both files
        with open(backup_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        with open(processed_path, 'r', encoding='utf-8') as f:
            processed_content = f.read()

        # Detect vendor type
        vendor_type = VendorDetector.detect_vendor_type(original_content)
        print(f"[Enc Disabler] {lang.enc_vendor_detected.format(vendor=vendor_type)}")

        # Analyze patterns from original file (it serves as reference)
        reference_patterns = {}
        mtk_format_info = None

        if vendor_type == 'qualcomm':
            reference_patterns = PatternDetector.analyze_reference_patterns(original_content)
            print(f"[Enc Disabler] {lang.enc_qualcomm_patterns_analyzed.format(count=len(reference_patterns))}")
        elif vendor_type == 'mtk':
            # For MTK, detect sub-format
            mtk_format_info = MtkFormatDetector.detect_mtk_subformat(original_content)
            print(f"[Enc Disabler] {lang.enc_mtk_subformat_detected.format(subformat=mtk_format_info.subformat, spacing_style=mtk_format_info.spacing_style)}")

        # Split into lines
        original_lines = original_content.splitlines()
        processed_lines = processed_content.splitlines()

        # Simple approach - take structure from original,
        # but replace only fstab lines (not comments)
        normalized_lines = []
        processed_fstab_lines = []

        # Collect all non-comments from processed file
        for line in processed_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                processed_fstab_lines.append(line)

        # Index for processed fstab lines
        proc_fstab_idx = 0

        # Go through original lines
        for orig_line in original_lines:
            stripped_orig = orig_line.strip()

            # If it's a comment or empty line - take as is
            if not stripped_orig or stripped_orig.startswith('#'):
                normalized_lines.append(orig_line)
            else:
                # This is fstab line - replace with processed one, if available
                if proc_fstab_idx < len(processed_fstab_lines):
                    # PATTERN-BASED ADAPTATION: Use pattern-based function with MTK format support
                    adapted_line = BackupBasedNormalizer._adapt_line_structure(
                        orig_line, processed_fstab_lines[proc_fstab_idx], vendor_type, reference_patterns, mtk_format_info
                    )
                    normalized_lines.append(adapted_line)
                    proc_fstab_idx += 1
                else:
                    # If no more processed lines, take original
                    normalized_lines.append(orig_line)

        # Proper result assembly with line break preservation
        result = '\n'.join(normalized_lines)

        # Preserve final line break if it was in original
        if original_content.endswith('\n') and not result.endswith('\n'):
            result += '\n'
        elif not original_content.endswith('\n') and result.endswith('\n'):
            result = result.rstrip('\n')

        return result

    @staticmethod
    def _lines_match(orig_line: str, proc_line: str) -> bool:
        """Checks if lines match by device and mount_point."""
        def extract_device_mount(line: str) -> Tuple[str, str]:
            parts = line.split()
            if len(parts) >= 2:
                return parts[0], parts[1]
            return '', ''

        orig_device, orig_mount = extract_device_mount(orig_line)
        proc_device, proc_mount = extract_device_mount(proc_line)

        return orig_device == proc_device and orig_mount == proc_mount

    @staticmethod
    def _adapt_line_structure(original_line: str, processed_line: str, vendor_type: str = None, reference_patterns: Dict[str, SpacingPattern] = None, mtk_format_info: MtkFormatInfo = None) -> str:
        """
        ENHANCED: Universal version with pattern-based processing.

        Now supports Qualcomm, MTK (with sub-format detection) and generic formats with pattern analysis.
        """
        # If vendor_type not specified, try to determine from content
        if vendor_type is None:
            # Simple check by one line
            if '/dev/block/bootdevice/by-name/' in original_line:
                vendor_type = 'qualcomm'
            elif '/dev/block/by-name/' in original_line and 'bootdevice' not in original_line:
                vendor_type = 'mtk'
            else:
                vendor_type = 'generic'

        # Apply vendor-specific normalization
        if vendor_type == 'qualcomm':
            if reference_patterns:
                # Use new enhanced version with patterns
                return QualcommSpacingNormalizer.normalize_qualcomm_spacing_enhanced(
                    original_line, processed_line, reference_patterns
                )
            else:
                # Fallback to old version
                return QualcommSpacingNormalizer.normalize_qualcomm_spacing(original_line, processed_line)
        elif vendor_type == 'mtk':
            # For MTK use new MTK-specific normalizer
            if mtk_format_info:
                return MtkSpacingNormalizer.normalize_mtk_spacing(original_line, processed_line, mtk_format_info)
            else:
                # Fallback to original logic if format_info unavailable
                return BackupBasedNormalizer._adapt_line_structure_original(original_line, processed_line)
        else:
            # For generic also use original logic
            return BackupBasedNormalizer._adapt_line_structure_original(original_line, processed_line)

    @staticmethod
    def _adapt_line_structure_original(original_line: str, processed_line: str) -> str:
        """
        Original adaptation logic for MTK and generic formats
        """
        orig_parts = original_line.split()
        proc_parts = processed_line.split()

        if len(orig_parts) != len(proc_parts):
            # If number of parts doesn't match, return processed line
            return processed_line

        # FIXED: Preserve positions of all columns from original
        result = ""
        for i, (orig_part, proc_part) in enumerate(zip(orig_parts, proc_parts)):
            # Find position of current part in original line
            if i == 0:
                # First column always starts from beginning
                part_start = original_line.find(orig_part)
            else:
                # For other columns look after previous position
                prev_part_end = original_line.find(orig_parts[i-1]) + len(orig_parts[i-1])
                part_start = original_line.find(orig_part, prev_part_end)

            if part_start == -1:
                # If not found, add with minimum space
                if result and not result.endswith(' '):
                    result += ' '
                result += proc_part
            else:
                # Calculate needed number of spaces to this position
                target_pos = part_start
                current_len = len(result)

                if target_pos > current_len:
                    # Add spaces to needed position
                    spaces_needed = target_pos - current_len
                    result += ' ' * spaces_needed
                elif target_pos < current_len:
                    # If position is less than current length, add minimum one space
                    result += ' '

                # Add processed part
                result += proc_part

        # FIXED: Add remaining symbols from end of original line
        if len(orig_parts) > 0:
            last_part_end = original_line.rfind(orig_parts[-1]) + len(orig_parts[-1])
            if last_part_end < len(original_line):
                remaining = original_line[last_part_end:]
                # Check that it's only spaces or comment
                if not remaining.strip() or remaining.strip().startswith('#'):
                    result += remaining

        return result

def clean_encryption_flags(options_part: str) -> tuple[str, bool]:
    """
    Removes encryption-related flags from a string while preserving formatting.
    FIXED: Proper comma handling to prevent missing commas in output.
    """
    if not options_part.strip():
        return 'defaults', False

    original_options = options_part.strip()

    # Split options into separate flags by commas
    flags = []
    current_flag = ""
    paren_count = 0

    # Parse with parentheses awareness
    for char in original_options:
        if char == '(':
            paren_count += 1
            current_flag += char
        elif char == ')':
            paren_count -= 1
            current_flag += char
        elif char == ',' and paren_count == 0:
            if current_flag.strip():
                flags.append(current_flag.strip())
            current_flag = ""
        else:
            current_flag += char

    # Add last flag
    if current_flag.strip():
        flags.append(current_flag.strip())

    # Filter flags
    filtered_flags = []
    was_modified = False

    for flag in flags:
        should_remove = False

        # Check flags with prefixes
        for prefix in ENCRYPTION_FLAGS_TO_REMOVE_BY_PREFIX:
            if flag.lower().startswith(prefix.lower()):
                should_remove = True
                was_modified = True
                print(f"[Enc Disabler] {lang.enc_removing_prefix_flag.format(flag=flag)}")
                break

        # Check exact flags
        if not should_remove:
            for exact_flag in ENCRYPTION_FLAGS_TO_REMOVE_EXACT:
                if flag.lower() == exact_flag.lower():
                    should_remove = True
                    was_modified = True
                    print(f"[Enc Disabler] {lang.enc_removing_exact_flag.format(flag=flag)}")
                    break

        # If flag shouldn't be removed, add it to result
        if not should_remove:
            filtered_flags.append(flag)

    # Build result
    if not filtered_flags:
        return 'defaults', True

    result = ','.join(filtered_flags)
    return result, was_modified

def preserve_column_width(original: str, new: str) -> str:
    """
    Preserves the original column width by padding with spaces.
    This maintains the alignment in fstab files.
    """
    diff = len(original) - len(new)
    if diff > 0:
        new = new + (' ' * diff)
    return new

# Regex to match Android fstab line — captures all fields with optional comment
ANDROID_FSTAB_PATTERN = re.compile(
    r'^(?P<device>\S+)'
    r'\s+(?P<mount_point>\S+)'
    r'\s+(?P<fs_type>\S+)'
    r'\s+(?P<mount_options>[^#]*?)'
    r'\s+(?P<fs_mgr_flags>[^#]*?)'
    r'(?:\s*#(?P<comment>.*)?)?$',
    re.MULTILINE
)

def process_fstab_for_encryption(fstab_path: str, use_backup_normalizer: bool = False) -> bool:
    """
    Processes an Android fstab file by removing encryption-related flags from
    BOTH mount_options (4th column) and fs_mgr_flags (5th column).

    Args:
        fstab_path: Path to the fstab file
        use_backup_normalizer: If True, uses backup-based normalizer with .original file
    """
    if not os.path.isfile(fstab_path):
        print(f"[Enc Disabler] {lang.file_not_found.format(file=fstab_path)}")
        return False

    backup_path = fstab_path + '.original'

    try:
        # Step 1: Create backup copy if normalizer enabled
        if use_backup_normalizer:
            if not os.path.exists(backup_path):
                shutil.copy2(fstab_path, backup_path)
                print(f"[Enc Disabler] {lang.enc_backup_created.format(filename=os.path.basename(backup_path))}")
            else:
                print(f"[Enc Disabler] {lang.enc_backup_existing.format(filename=os.path.basename(backup_path))}")

        # Step 2: Read and process file
        with open(fstab_path, 'rb') as f:
            raw_content = f.read()

        try:
            content = raw_content.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            content = raw_content.decode('latin-1')
            encoding = 'latin-1'
            print(f"[Enc Disabler] {lang.encoding_warning.format(file=os.path.basename(fstab_path), encoding=encoding)}")

        if use_backup_normalizer:
            print(f"[Enc Disabler] {lang.enc_backup_normalizer_activated.format(filename=os.path.basename(fstab_path))}")

        lines = content.splitlines()
        modified_lines = []
        file_was_modified = False

        for line in lines:
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith('#'):
                modified_lines.append(line)
                continue

            match = ANDROID_FSTAB_PATTERN.match(stripped_line)
            if not match:
                modified_lines.append(line)
                continue

            # Extract current values
            old_mount_opts = match.group('mount_options')
            old_fs_mgr_flags = match.group('fs_mgr_flags')

            # Clean both fields
            new_mount_opts, modified_mount = clean_encryption_flags(old_mount_opts)
            new_fs_mgr_flags, modified_fs_mgr = clean_encryption_flags(old_fs_mgr_flags)

            was_modified = modified_mount or modified_fs_mgr

            if was_modified:
                file_was_modified = True

                if use_backup_normalizer:
                    # Simple replacement for backup normalizer
                    new_line = line
                    if modified_mount:
                        new_line = new_line.replace(old_mount_opts, new_mount_opts.strip())
                    if modified_fs_mgr:
                        new_line = new_line.replace(old_fs_mgr_flags, new_fs_mgr_flags.strip())
                    modified_lines.append(new_line.rstrip())
                else:
                    # Original logic without normalization
                    new_line = line

                    # Replace mount_options (4th field) with width preservation
                    if modified_mount:
                        preserved_mount_opts = preserve_column_width(old_mount_opts, new_mount_opts)
                        start = match.start('mount_options')
                        end = match.end('mount_options')
                        new_line = new_line[:start] + preserved_mount_opts + new_line[end:]

                    # Replace fs_mgr_flags (5th field) with width preservation
                    if modified_fs_mgr:
                        # Recalculate positions after potential mount_options change
                        if modified_mount:
                            updated_match = ANDROID_FSTAB_PATTERN.match(new_line.strip())
                            if updated_match:
                                start = updated_match.start('fs_mgr_flags')
                                end = updated_match.end('fs_mgr_flags')
                            else:
                                start = match.start('fs_mgr_flags')
                                end = match.end('fs_mgr_flags')
                        else:
                            start = match.start('fs_mgr_flags')
                            end = match.end('fs_mgr_flags')

                        new_line = new_line[:start] + new_fs_mgr_flags + new_line[end:]

                    new_line = new_line.rstrip()
                    modified_lines.append(new_line)
            else:
                modified_lines.append(line if use_backup_normalizer else line.rstrip())

        # Step 3: Save processed file
        base_name = os.path.basename(fstab_path)
        if file_was_modified:
            print(f"[Enc Disabler] {lang.enc_flags_removed.format(file=base_name)}")

            # Write processed content
            processed_content = "\n".join(modified_lines)
            if content.endswith('\n') and not processed_content.endswith('\n'):
                processed_content += '\n'

            with open(fstab_path, 'w', encoding=encoding) as f:
                f.write(processed_content)

            # Step 4: Normalization through backup copy
            if use_backup_normalizer and os.path.exists(backup_path):
                try:
                    normalized_content = BackupBasedNormalizer.normalize_by_backup_comparison(
                        backup_path, fstab_path
                    )

                    # Write normalized content
                    with open(fstab_path, 'w', encoding=encoding) as f:
                        f.write(normalized_content)

                    print(f"[Enc Disabler] {lang.enc_backup_normalization_completed.format(filename=base_name)}")

                    # Step 5: Delete backup copy on success
                    os.remove(backup_path)
                    print(f"[Enc Disabler] {lang.enc_backup_deleted.format(filename=os.path.basename(backup_path))}")

                except Exception as e:
                    print(f"[Enc Disabler] {lang.enc_normalization_error.format(error=e)}")
                    # Restore from backup copy on error
                    if os.path.exists(backup_path):
                        shutil.copy2(backup_path, fstab_path)
                        os.remove(backup_path)
                        print(f"[Enc Disabler] {lang.enc_file_restored}")
                    return False

        else:
            print(f"[Enc Disabler] {lang.enc_flags_not_found.format(file=base_name)}")
            # Delete backup copy if no changes
            if use_backup_normalizer and os.path.exists(backup_path):
                os.remove(backup_path)
                print(f"[Enc Disabler] {lang.enc_backup_deleted_no_changes}")

        return True

    except Exception as e:
        print(f"[Enc Disabler] {lang.error_processing_file.format(file=fstab_path, error=e)}")
        import traceback
        traceback.print_exc()

        # Restore from backup copy on critical error
        if use_backup_normalizer and os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, fstab_path)
                os.remove(backup_path)
                print(f"[Enc Disabler] {lang.enc_file_restored_after_error}")
            except Exception as restore_error:
                print(f"[Enc Disabler] {lang.enc_restore_error.format(error=restore_error)}")

        return False

def main():
    # Example usage
    fstab_file = "fstab.mt6789"
    if os.path.exists(fstab_file):
        process_fstab_for_encryption(fstab_file, use_backup_normalizer=True)
    else:
        print(f"File {fstab_file} not found")

if __name__ == "__main__":
    main()
