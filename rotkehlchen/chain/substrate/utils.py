from typing import get_args

from substrateinterface import Keypair
from substrateinterface.utils.ss58 import is_valid_ss58_address

from rotkehlchen.types import SUPPORTED_SUBSTRATE_CHAINS, SupportedBlockchain

from .types import KusamaNodeName, PolkadotNodeName, SubstrateAddress, SubstratePublicKey

KUSAMA_NODES_TO_CONNECT_AT_START = (
    KusamaNodeName.OWN,
    KusamaNodeName.PARITY,
    KusamaNodeName.ELARA,
    KusamaNodeName.ONFINALITY,
)

POLKADOT_NODES_TO_CONNECT_AT_START = (
    PolkadotNodeName.OWN,
    PolkadotNodeName.PARITY,
    PolkadotNodeName.ELARA,
    PolkadotNodeName.ONFINALITY,
)

SUBSTRATE_NODE_CONNECTION_TIMEOUT = 10


def is_valid_kusama_address(value: str) -> bool:
    return is_valid_ss58_address(value=value, valid_ss58_format=2)


def is_valid_polkadot_address(value: str) -> bool:
    return is_valid_ss58_address(value=value, valid_ss58_format=0)


def get_substrate_address_from_public_key(
        chain: SUPPORTED_SUBSTRATE_CHAINS,
        public_key: SubstratePublicKey,
) -> SubstrateAddress:
    """Return a valid address for the given Substrate chain and public key.

    Public key: 32 len str, leading '0x' is optional.

    May raise:
    - AttributeError: if public key is not a string.
    - TypeError: if ss58_format is not an int.
    - ValueError: if public key is not 32 bytes long or the ss58_format is not
    a valid int.
    """
    assert chain in get_args(SUPPORTED_SUBSTRATE_CHAINS)
    if chain == SupportedBlockchain.KUSAMA:
        ss58_format = 2
    else:  # polkadot
        ss58_format = 0

    keypair = Keypair(
        public_key=public_key,
        ss58_format=ss58_format,
    )
    return SubstrateAddress(keypair.ss58_address)
