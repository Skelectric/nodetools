from typing import Protocol, Union, Optional
import pandas as pd
from xrpl.wallet import Wallet
from xrpl.models import Memo
from decimal import Decimal
from nodetools.configuration.configuration import NetworkConfig, NodeConfig
from nodetools.utilities.db_manager import DBConnectionManager
from nodetools.utilities.xrpl_monitor import XRPLWebSocketMonitor

class GenericPFTUtilities(Protocol):
    """Protocol defining the interface for GenericPFTUtilities implementations"""

    @property
    def network_config(self) -> NetworkConfig:
        """Get the network configuration"""
        ...

    @property
    def node_config(self) -> NodeConfig:
        """Get the node configuration"""
        ...

    @property
    def db_connection_manager(self) -> DBConnectionManager:
        """Get the database connection manager"""
        ...

    @property
    def xrpl_monitor(self) -> XRPLWebSocketMonitor:
        """Get the XRPL monitor"""
        ...

    def sync_pft_transaction_history(self):
        """Sync transaction history for all PFT holders"""
        ...

    def get_account_memo_history(self, account_address: str, pft_only: bool = True) -> pd.DataFrame:
        """Get memo history for a given account"""
        ...

    def send_memo_legacy(self, 
            wallet_seed_or_wallet: Union[str, Wallet], 
            destination: str, 
            memo: Union[str, Memo], 
            username: str = None,
            message_id: str = None,
            chunk: bool = False,
            compress: bool = False, 
            encrypt: bool = False,
            pft_amount: Optional[Decimal] = None
        ) -> Union[dict, list[dict]]:
        """Send a memo to a given account"""
        ...
    
    def verify_transaction_response(self, response: str) -> bool:
        """Verify a transaction response"""
        ...

    def get_all_account_compressed_messages(self, account_address: str) -> pd.DataFrame:
        """Get all compressed messages for a given account"""
        ...

    def construct_handshake_memo(self, user: str, ecdh_public_key: str) -> str:
        """Construct a handshake memo"""
        ...

    def construct_memo(self, memo_data: str, memo_type: str, memo_format: str) -> Memo:
        """Construct a standardized memo object for XRPL transactions"""
        ...

    def spawn_wallet_from_seed(self, seed: str) -> Wallet:
        """Spawn a wallet from a seed"""
        ...

    def get_latest_outgoing_context_doc_link(
        self, 
        account_address: str,
        memo_history: pd.DataFrame = None
    ) -> Optional[str]:
        """Get the most recent Google Doc context link sent by this wallet.
        Handles both encrypted and unencrypted links for backwards compatibility.
        """
        ...

    def get_google_doc_text(self, google_url: str) -> Optional[str]:
        """Get the text of a Google Doc"""
        ...

    def get_recent_user_memos(self, account_address: str, num_messages: int) -> str:
        """Get the most recent messages from a user's memo history"""
        ...

    def get_all_account_compressed_messages_for_remembrancer(self, account_address: str) -> pd.DataFrame:
        """Convenience method for getting all messages for a user from the remembrancer's perspective"""
        ...

    async def process_queue_transaction(
            self,
            wallet: Wallet,
            memo: str,
            destination: str,
            pft_amount: Optional[Union[int, float, Decimal]] = None
        ) -> bool:
        """Send and track a node-initiated transaction for queue processing"""
        ...

    def fetch_pft_balance(self, address: str) -> Decimal:
        """Get PFT balance for an account from the XRPL"""
        ...

    def fetch_xrp_balance(self, address: str) -> Decimal:
        """Get XRP balance for an account from the XRPL"""
        ...

    def get_pft_balance(self, account_address: str) -> Decimal:
        """Get PFT balance for an account from the database"""
        ...