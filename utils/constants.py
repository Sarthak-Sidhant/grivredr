"""
Constants - Centralized configuration values for the scraper factory

Replaces magic numbers scattered throughout the codebase.
"""

# =============================================================================
# TIMING CONSTANTS (in seconds)
# =============================================================================

# Page load waits
WAIT_PAGE_SETTLE = 2.0  # Time to let page settle after load
WAIT_PAGE_TRANSITION = 1.5  # Time to wait for page transitions
WAIT_NETWORK_IDLE = 30.0  # Max wait for network idle

# Element interaction waits
WAIT_DROPDOWN_OPEN = 0.8  # Wait for dropdown animation
WAIT_DROPDOWN_CLOSE = 0.3  # Wait after closing dropdown
WAIT_FIELD_FOCUS = 0.1  # Wait after focusing field
WAIT_FIELD_BLUR = 0.3  # Wait after blur for validation
WAIT_FIELD_INTERACTION = 0.2  # General interaction delay

# Cascade waits
WAIT_CASCADE_DEFAULT = 1.5  # Default wait for child dropdown to load
WAIT_CASCADE_SLOW = 2.0  # Wait for slower cascades (department->officer)
WAIT_CASCADE_FAST = 1.0  # Wait for fast cascades (state->district)

# Search/typing waits
WAIT_SEARCH_RESULTS = 0.8  # Wait for search results to appear
WAIT_TYPE_DELAY_MS = 50  # Delay between keystrokes in ms


# =============================================================================
# RETRY CONSTANTS
# =============================================================================

MAX_VALIDATION_ATTEMPTS = 3  # Max attempts to validate scraper
MAX_PLAYWRIGHT_ATTEMPTS = 2  # Max browser automation retries
MAX_API_RETRIES = 3  # Max API call retries
MAX_HEALING_ATTEMPTS = 2  # Max self-healing attempts

RETRY_BASE_DELAY = 1.0  # Base delay for exponential backoff (seconds)
RETRY_MAX_DELAY = 10.0  # Maximum delay between retries


# =============================================================================
# SIMILARITY THRESHOLDS
# =============================================================================

PATTERN_SIMILARITY_THRESHOLD = 0.3  # Minimum Jaccard similarity for pattern match
DISCOVERY_CONFIDENCE_THRESHOLD = 0.6  # Minimum confidence to accept discovery
FRAMEWORK_DETECTION_THRESHOLD = 0.2  # Minimum confidence for framework detection
VALIDATION_CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence for validation pass


# =============================================================================
# LIMITS
# =============================================================================

MAX_FIELDS_TO_EXPLORE = 20  # Max form fields to explore in discovery
MAX_DROPDOWN_OPTIONS = 100  # Max options to extract from dropdown
MAX_SIMILAR_PATTERNS = 3  # Max similar patterns to retrieve
MAX_CODE_SNIPPETS = 10  # Max code snippets to extract per scraper
MAX_ERROR_LOG_LENGTH = 500  # Max characters for error messages

# Token limits
MAX_PROMPT_TOKENS = 4000  # Max tokens for AI prompts
MAX_HTML_SNIPPET_CHARS = 5000  # Max chars of HTML to include in prompts
MAX_SCREENSHOT_SIZE_MB = 5  # Max screenshot size


# =============================================================================
# TIMEOUTS (in milliseconds)
# =============================================================================

TIMEOUT_PAGE_LOAD = 30000  # 30 seconds
TIMEOUT_ELEMENT_WAIT = 5000  # 5 seconds
TIMEOUT_ELEMENT_CLICK = 3000  # 3 seconds
TIMEOUT_SCRAPER_TEST = 60000  # 60 seconds


# =============================================================================
# CSS SELECTORS
# =============================================================================

# Common submit button selectors (in priority order)
SUBMIT_BUTTON_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button.btn-primary',
    '.submit-btn',
    'button:has-text("Submit")',
    'button:has-text("Register")',
    '*[onclick*="submit"]',
]

# Common error message selectors
ERROR_MESSAGE_SELECTORS = [
    '.error',
    '.invalid',
    '.text-danger',
    '.error-message',
    '[class*="error"]',
    '.validation-error',
    '.field-error',
]

# Ant Design specific selectors
ANT_SELECT_DROPDOWN = ".ant-select-dropdown"
ANT_SELECT_OPTION = ".ant-select-item-option"
ANT_SELECT_WRAPPER = "div[class*='ant-select']"

# Select2 specific selectors
SELECT2_CONTAINER = ".select2-container"
SELECT2_DROPDOWN = ".select2-dropdown"
SELECT2_RESULTS = ".select2-results__option"
SELECT2_SEARCH = ".select2-search__field"


# =============================================================================
# UI FRAMEWORKS
# =============================================================================

FRAMEWORK_INDICATORS = {
    "ant_design": ["ant-", "antd-"],
    "select2": ["select2-", "select2-container"],
    "bootstrap": ["form-control", "form-group", "btn-primary"],
    "material_ui": ["Mui", "MuiFormControl"],
    "asp_net": ["ctl00_", "__VIEWSTATE", ".aspx"],
}


# =============================================================================
# FILE PATHS
# =============================================================================

DEFAULT_PORTALS_DIR = "portals"
DEFAULT_SCRAPERS_DIR = "scrapers"
DEFAULT_OUTPUTS_DIR = "outputs"
DEFAULT_KNOWLEDGE_DIR = "knowledge"
DEFAULT_CACHE_DIR = "cache"

PATTERNS_DB_NAME = "patterns.db"
FIELD_MAPPINGS_SUFFIX = "_field_mappings.json"


# =============================================================================
# API CONFIGURATION
# =============================================================================

# Model names (MegaLLM compatible)
MODEL_FAST = "claude-haiku-4.5"
MODEL_BALANCED = "claude-sonnet-4.5"
MODEL_POWERFUL = "claude-opus-4.5"

# Default model for different tasks
MODEL_FOR_VISION = MODEL_BALANCED
MODEL_FOR_CODE_GEN = MODEL_POWERFUL
MODEL_FOR_HEALING = MODEL_BALANCED
MODEL_FOR_STATUS = MODEL_FAST

# API pricing (per million tokens)
API_PRICING = {
    "claude-haiku-4.5": {"input": 1.0, "output": 5.0},
    "claude-sonnet-4.5": {"input": 3.0, "output": 15.0},
    "claude-opus-4.5": {"input": 5.0, "output": 25.0},
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
    "claude-opus-4-5-20250929": {"input": 15.0, "output": 75.0},
}
