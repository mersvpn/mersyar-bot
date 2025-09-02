# This file centralizes constants used across the Marzban actions module.
# This makes it easier to manage and avoid "magic numbers" or strings in the code.

# ===== CONVERSATION STATES =====
# By defining states here, we ensure they are unique across all conversations
# within this module, preventing accidental state clashes.

# --- Search Conversation ---
SEARCH_PROMPT = 0

# --- Note Conversation ---
NOTE_PROMPT = 1

# --- User Modification Conversations ---
ADD_DATA_PROMPT = 2
ADD_DAYS_PROMPT = 3

# --- Add User Conversation ---
ADD_USER_USERNAME = 4
ADD_USER_DATALIMIT = 5
ADD_USER_EXPIRE = 6
ADD_USER_CONFIRM = 7

# --- Template User Conversation ---
# This was the missing constant that caused the ImportError.
SET_TEMPLATE_USER_PROMPT = 8

# ===== PAGINATION =====
USERS_PER_PAGE = 10 # Number of users to show on each page of the user list

# ===== DATA CONVERSION =====
GB_IN_BYTES = 1024 * 1024 * 1024 # 1 Gigabyte in bytes

# ===== DEFAULTS =====
DEFAULT_RENEW_DAYS = 30 # Default number of days to add on smart renewal