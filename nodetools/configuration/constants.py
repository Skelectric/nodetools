from enum import Enum
from decimal import Decimal
from pathlib import Path
import re

CONFIG_DIR = Path.home().joinpath("postfiatcreds")

# AI MODELS
DEFAULT_OPENROUTER_MODEL = 'anthropic/claude-3.5-sonnet:beta'
DEFAULT_OPEN_AI_MODEL = 'chatgpt-4o-latest'
DEFAULT_ANTHROPIC_MODEL = 'claude-3-5-sonnet-20241022'

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# XRPL CONSTANTS
MIN_XRP_PER_TRANSACTION = Decimal('0.000001')  # Minimum XRP amount per transaction
MIN_XRP_BALANCE = 2  # Minimum XRP balance to be able to perform a transaction, corresponding to XRP reserve
MAX_CHUNK_SIZE = 1024
XRP_MEMO_STRUCTURAL_OVERHEAD = 100  # JSON structure, quotes, etc.

# Verification Constants
VERIFY_STATE_INTERVAL = 300  # 5 minutes

# Maximum history length
MAX_HISTORY = 15  # TODO: rename this to something more descriptive

# Versioning Constants
MEMO_VERSION = "1.0"
UNIQUE_ID_VERSION = "1.0"  # Unique ID pattern for memo types
UNIQUE_ID_PATTERN_V1 = re.compile(fr'(v{UNIQUE_ID_VERSION}\.(?:\d{{4}}-\d{{2}}-\d{{2}}_\d{{2}}:\d{{2}}(?:__[A-Z0-9]{{2,4}})?))')

class SystemMemoType(Enum):
    INITIATION_REWARD = 'INITIATION_REWARD'  # name is memo_type, value is memo_data pattern
    HANDSHAKE = 'HANDSHAKE'
    HANDSHAKE_RESPONSE = 'HANDSHAKE_RESPONSE'
    INITIATION_RITE = 'INITIATION_RITE'
    GOOGLE_DOC_CONTEXT_LINK = 'google_doc_context_link'

SYSTEM_MEMO_TYPES = [memo_type.value for memo_type in SystemMemoType]

class PFTSendDistribution(Enum):
    """Controls how PFT amounts are distributed across memo chunks"""
    DISTRIBUTE_EVENLY = "distribute_evenly"  # Split total PFT amount evenly across all chunks
    LAST_CHUNK_ONLY = "last_chunk_only"     # Send entire PFT amount with last chunk only
    FULL_AMOUNT_EACH = "full_amount_each"   # Send full PFT amount with each chunk
