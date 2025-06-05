# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
from typing import Dict, Iterator, Tuple, Optional, TextIO, List, Any

class ConfigParser:
    """
    A simple INI-style configuration file parser.

    This parser handles sections ([section_name]), key-value pairs (key = value),
    and comments (lines starting with '#' or ';', or inline after a value using '#' or ';').
    All keys and values are stored and returned as strings.

    A default section (internally named '__init__', accessible via `ConfigParser._DEFAULT_SECTION_NAME`)
    is used for key-value pairs that appear before any explicit section header in a parsed file or string.
    This default section is written to an output file with its name (e.g., `[__init__]`)
    if it contains any entries.

    Parsing Behavior:
    - Section names and keys are case-sensitive.
    - Leading/trailing whitespace is stripped from section names, keys, and values.
    - Lines that are blank, consist only of whitespace, or start with '#' or ';' are ignored.
    - Inline comments (e.g., `key = value # comment`) are stripped from values.
    - If a key is empty after stripping whitespace (e.g., from " = value"), the line is ignored.
    - Section re-declarations during parsing will result in the section being reset (cleared of previous keys).
    """

    _DEFAULT_SECTION_NAME: str = "__init__"

    def __init__(self) -> None:
        """Initializes the ConfigParser with an empty default section."""
        # self.sections stores the configuration data.
        # Format: {"section_name": {"key": "value", ...}, ...}
        self.sections: Dict[str, Dict[str, str]] = {self._DEFAULT_SECTION_NAME: {}}

        # _current_section_name_during_parse tracks the active section context during a parsing operation.
        # It's initialized to the default section name.
        self._current_section_name_during_parse: str = self._DEFAULT_SECTION_NAME

    def __setitem__(self, section_name: Any, section_data: Dict[Any, Any]) -> None:
        """
        Sets or replaces an entire section with the provided dictionary of key-value pairs.
        All keys and values in section_data will be converted to strings.

        Args:
            section_name: The name of the section.
            section_data: A dictionary containing key-value pairs for the section.
                          Non-string keys/values will be converted to strings.
        """
        self.sections[str(section_name)] = {str(k): str(v) for k, v in section_data.items()}

    def _parse_lines(self, lines_iterator: Iterator[str]) -> None:
        """
        Internal helper method to parse configuration data from an iterator of lines.

        Updates `self.sections` with parsed data.
        `self._current_section_name_during_parse` is used to determine the context for
        key-value pairs. It is assumed that `self.sections[self._current_section_name_during_parse]`
        exists when this method is called.

        Args:
            lines_iterator: An iterator yielding lines of text (e.g., from a file or StringIO).
        """
        current_section_dict = self.sections[self._current_section_name_during_parse]

        for line_content in lines_iterator:
            line = line_content.strip()

            # Skip empty lines and full-line comments
            if not line or line.startswith("#") or line.startswith(";"):
                continue

            if line.startswith('[') and line.endswith(']'):
                section_name = line[1:-1].strip()
                if not section_name: # Handles "[]" or "[ ]"
                    continue # Ignore empty section names
                
                self._current_section_name_during_parse = section_name
                # If a section is re-declared, it's reset (cleared of previous keys).
                self.sections[section_name] = {}
                current_section_dict = self.sections[section_name]
            elif '=' in line:
                key_part, value_part = line.split("=", 1)
                key = key_part.strip()

                if not key: # Ignore lines with empty keys (e.g., "= value" or " = value")
                    continue

                value = value_part.strip()

                # Remove inline comments from value. A comment starts with '#' or ';'.
                comment_start_hash = value.find('#')
                comment_start_semicolon = value.find(';')

                comment_pos = -1
                if comment_start_hash != -1 and comment_start_semicolon != -1:
                    comment_pos = min(comment_start_hash, comment_start_semicolon)
                elif comment_start_hash != -1:
                    comment_pos = comment_start_hash
                elif comment_start_semicolon != -1:
                    comment_pos = comment_start_semicolon
                
                if comment_pos != -1:
                    value = value[:comment_pos].strip() # Strip whitespace again after comment removal

                current_section_dict[key] = value
            else:
                # Line is not a comment, not a section header, not a valid key-value pair.
                # Silently ignore such malformed lines.
                # Optionally, a warning could be logged for malformed lines if needed for debugging.
                continue

    def read(self, filepath: str, encoding: str = 'utf-8') -> None:
        """
        Reads and parses configuration data from a file.

        Parsed data is merged into the current configuration. If sections or keys
        are redefined, they overwrite existing ones. The parser's internal state
        for the "current section" is reset to the default section before reading.

        Args:
            filepath: Path to the configuration file.
            encoding: File encoding (defaults to 'utf-8').

        Raises:
            FileNotFoundError: If the specified file does not exist.
            IOError: If any other I/O error occurs during file reading.
        """
        self._current_section_name_during_parse = self._DEFAULT_SECTION_NAME
        if self._DEFAULT_SECTION_NAME not in self.sections: # Ensure default section exists
            self.sections[self._DEFAULT_SECTION_NAME] = {}

        with open(filepath, 'r', encoding=encoding) as f:
            self._parse_lines(f)

    def read_string(self, config_string: str) -> None:
        """
        Reads and parses configuration data from a multi-line string.

        Parsed data is merged similarly to the `read` method. The parser's internal
        state for the "current section" is reset to the default section before parsing.

        Args:
            config_string: A string containing INI-formatted configuration data.
        """
        self._current_section_name_during_parse = self._DEFAULT_SECTION_NAME
        if self._DEFAULT_SECTION_NAME not in self.sections: # Ensure default section exists
            self.sections[self._DEFAULT_SECTION_NAME] = {}
            
        self._parse_lines(io.StringIO(config_string))

    def items(self, section_name: Any) -> Iterator[Tuple[str, str]]:
        """
        Yields (key, value) string tuples for all items in a given section.
        The section name is converted to a string before lookup.

        If the specified section does not exist, this method yields nothing.

        Args:
            section_name: The name of the section from which to retrieve items.

        Yields:
            An iterator of (key, value) string tuples.
        """
        section_data = self.sections.get(str(section_name))
        if section_data is not None:
            yield from section_data.items()

    def write(self, file_object: TextIO) -> None:
        """
        Writes the current configuration data to a file-like object.

        Sections are written, typically in the order they were added or parsed
        (for Python 3.7+ dictionaries where dicts preserve insertion order).
        The default section (`__init__`) is written with its name if it contains items.
        Empty sections (those with no key-value pairs) are not written.
        A blank line is added after each written section for readability.

        Args:
            file_object: An open, writable text file-like object (e.g., opened with open (path, 'w')).
        """
        first_section = True
        for section_name, section_data in self.sections.items():
            if section_data:  # Only write the section if it contains key-value pairs
                if not first_section:
                    file_object.write("\n") # Add a blank line before the following sections
                file_object.write(f"[{section_name}]\n")
                for key, value in section_data.items():
                    file_object.write(f"{key} = {value}\n")
                first_section = False


    def set(self, section_name: Any, key: Any, value: Any) -> None:
        """
        Sets a key-value pair in a specified section.

        If the section does not exist, it is created. The section name, key, and
        value are all converted to strings before storage.

        Args:
            section_name: The name of the section.
            key: The name of the key (option).
            value: The value to set for the key.
        """
        s_name_str = str(section_name)
        if s_name_str not in self.sections:
            self.sections[s_name_str] = {}
        self.sections[s_name_str][str(key)] = str(value)

    def get(self, section_name: Any, key: Any, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieves the value for a key from a specified section.

        Section name and key are converted to strings before lookup.

        Args:
            section_name: The name of the section.
            key: The name of the key (option).
            default: The value to return if the section or key is not found.
                     Defaults to `None`.

        Returns:
            The value associated with the key as a string, or the `default` value
            if the section or key is not found.
        """
        section_data = self.sections.get(str(section_name))
        if section_data is not None:
            return section_data.get(str(key), default)
        return default

    def has_section(self, section_name: Any) -> bool:
        """
        Checks if a section with the given name exists in the configuration.
        The section name is converted to a string before checking.

        Args:
            section_name: The name of the section to check.

        Returns:
            True if the section exists, False otherwise.
        """
        return str(section_name) in self.sections

    def options(self, section_name: Any) -> List[str]:
        """
        Returns a list of option (key) names for the given section.
        The section name is converted to a string before lookup.

        Args:
            section_name: The name of the section.

        Returns:
            A list of strings, where each string is an option name.
            Returns an empty list if the section does not exist or is empty.
        """
        section_data = self.sections.get(str(section_name))
        if section_data is not None:
            return list(section_data.keys())
        return []

    def get_sections(self) -> List[str]:
        """
        Returns a list of all section names present in the configuration.

        This includes the default section name (e.g., `__init__`) if it has been
        populated with items or explicitly created. The order of section names
        typically reflects the order of insertion or parsing (for Python 3.7+ dictionaries).

        Returns:
            A list of strings, where each string is a section name.
        """
        return list(self.sections.keys())

    def clear(self) -> None:
        """
        Removes all sections and keys, resetting the parser to its initial state,
        which contains only an empty default section (e.g., `__init__`).
        The internal current section for parsing is also reset to the default section.
        """
        self.sections.clear()
        self.sections[self._DEFAULT_SECTION_NAME] = {}
        self._current_section_name_during_parse = self._DEFAULT_SECTION_NAME
