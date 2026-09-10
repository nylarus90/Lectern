"""Single source of truth for the application version."""

__version__ = "1.2.0"

APP_NAME = "Lectern"
APP_ID = "lectern"
ORG_NAME = "Lectern"

#: The names used up to 1.1.1, kept only to find and adopt what that version
#: left behind: its data directory and its environment variable. Nothing new
#: is ever written under them. (The installer carries its own copy.)
LEGACY_APP_ID = "openreader"
LEGACY_ENV = "OPENREADER_DATA_DIR"
