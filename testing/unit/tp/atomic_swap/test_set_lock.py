"""
Provide tests for atomic swap handler setting lock method implementation.
"""
import time

import pytest
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.protobuf.processor_pb2 import TpProcessRequest
from sawtooth_sdk.protobuf.transaction_pb2 import (
    Transaction,
    TransactionHeader,
)

from testing.conftest import create_signer
from testing.mocks.stub import StubContext
from testing.utils.client import proto_error_msg
from remme.protos.account_pb2 import Account
from remme.protos.atomic_swap_pb2 import (
    AtomicSwapInfo,
    AtomicSwapSetSecretLockPayload,
    AtomicSwapMethod,
)
from remme.protos.transaction_pb2 import TransactionPayload
from remme.settings import TRANSACTION_FEE
from remme.shared.utils import hash512, client_to_real_amount
from remme.tp.atomic_swap import AtomicSwapHandler
from remme.tp.basic import BasicHandler
from remme.tp.consensus_account import ConsensusAccountHandler, ConsensusAccount

BOT_PRIVATE_KEY = '1cb15ecfe1b3dc02df0003ac396037f85b98cf9f99b0beae000dc5e9e8b6dab4'
BOT_PUBLIC_KEY = '03ecc5cb4094eb05319be6c7a63ebf17133d4ffaea48cdcfd1d5fc79dac7db7b6b'
BOT_ADDRESS = '112007b9433e1da5c624ff926477141abedfd57585a36590b0a8edc4104ef28093ee30'

SWAP_ID = '033102e41346242476b15a3a7966eb5249271025fc7fb0b37ed3fdb4bcce3884'
SECRET_LOCK = '29c36b8dd380e0426bdc1d834e74a630bfd5d111'

ADDRESS_TO_STORE_SWAP_INFO_BY = BasicHandler(
    name=AtomicSwapHandler().family_name, versions=AtomicSwapHandler()._family_versions[0]
).make_address_from_data(data=SWAP_ID)


TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS = {
    'family_name': AtomicSwapHandler().family_name,
    'family_version': AtomicSwapHandler()._family_versions[0],
}

RANDOM_NODE_PUBLIC_KEY = '039d6881f0a71d05659e1f40b443684b93c7b7c504ea23ea8949ef5216a2236940'

INPUTS = OUTPUTS = [
    ADDRESS_TO_STORE_SWAP_INFO_BY,
    BOT_ADDRESS,
    ConsensusAccountHandler.CONSENSUS_ADDRESS,
]


def test_set_lock_with_empty_proto():
    """
    Case: send empty proto for set lock
    Expect: invalid transaction error
    """
    atomic_swap_init_payload = AtomicSwapSetSecretLockPayload()

    transaction_payload = TransactionPayload()
    transaction_payload.method = AtomicSwapMethod.SET_SECRET_LOCK
    transaction_payload.data = atomic_swap_init_payload.SerializeToString()

    serialized_transaction_payload = transaction_payload.SerializeToString()

    transaction_header = TransactionHeader(
        signer_public_key=BOT_PUBLIC_KEY,
        family_name=TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS.get('family_name'),
        family_version=TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS.get('family_version'),
        inputs=INPUTS,
        outputs=OUTPUTS,
        dependencies=[],
        payload_sha512=hash512(data=serialized_transaction_payload),
        batcher_public_key=RANDOM_NODE_PUBLIC_KEY,
        nonce=time.time().hex().encode(),
    )

    serialized_header = transaction_header.SerializeToString()

    transaction_request = TpProcessRequest(
        header=transaction_header,
        payload=serialized_transaction_payload,
        signature=create_signer(private_key=BOT_PRIVATE_KEY).sign(serialized_header),
    )

    mock_context = StubContext(inputs=INPUTS, outputs=OUTPUTS, initial_state={})

    with pytest.raises(InvalidTransaction) as error:
        AtomicSwapHandler().apply(transaction=transaction_request, context=mock_context)

    assert proto_error_msg(
        AtomicSwapSetSecretLockPayload,
        {
            'swap_id': ['Missed swap_id.'],
            'secret_lock': ['This field is required.'],
        }
    ) == str(error.value)


def test_set_lock_to_atomic_swa():
    """
    Case: set secret lock to atomic swap.
    Expect: secret lock has been set, swap status changed to secret lock is provided.
    """
    atomic_swap_init_payload = AtomicSwapSetSecretLockPayload(
        swap_id=SWAP_ID,
        secret_lock=SECRET_LOCK,
    )

    transaction_payload = TransactionPayload()
    transaction_payload.method = AtomicSwapMethod.SET_SECRET_LOCK
    transaction_payload.data = atomic_swap_init_payload.SerializeToString()

    serialized_transaction_payload = transaction_payload.SerializeToString()

    transaction_header = TransactionHeader(
        signer_public_key=BOT_PUBLIC_KEY,
        family_name=TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS.get('family_name'),
        family_version=TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS.get('family_version'),
        inputs=INPUTS,
        outputs=OUTPUTS,
        dependencies=[],
        payload_sha512=hash512(data=serialized_transaction_payload),
        batcher_public_key=RANDOM_NODE_PUBLIC_KEY,
        nonce=time.time().hex().encode(),
    )

    serialized_header = transaction_header.SerializeToString()

    transaction_request = TpProcessRequest(
        header=transaction_header,
        payload=serialized_transaction_payload,
        signature=create_signer(private_key=BOT_PRIVATE_KEY).sign(serialized_header),
    )

    existing_swap_info_to_lock = AtomicSwapInfo()
    existing_swap_info_to_lock.swap_id = SWAP_ID
    existing_swap_info_to_lock.state = AtomicSwapInfo.OPENED
    serialized_existing_swap_info_to_lock = existing_swap_info_to_lock.SerializeToString()

    bot_account = Account()
    bot_account.balance = client_to_real_amount(TRANSACTION_FEE)
    serialized_bot_account = bot_account.SerializeToString()

    consensus_account = ConsensusAccount()
    consensus_account.block_cost = 0
    serialized_consensus_account = consensus_account.SerializeToString()

    mock_context = StubContext(inputs=INPUTS, outputs=OUTPUTS, initial_state={
        ADDRESS_TO_STORE_SWAP_INFO_BY: serialized_existing_swap_info_to_lock,
        BOT_ADDRESS: serialized_bot_account,
        ConsensusAccountHandler.CONSENSUS_ADDRESS: serialized_consensus_account,
    })

    expected_swap_info = AtomicSwapInfo()
    expected_swap_info.swap_id = SWAP_ID
    expected_swap_info.state = AtomicSwapInfo.SECRET_LOCK_PROVIDED
    expected_swap_info.secret_lock = SECRET_LOCK
    serialized_expected_swap_info = expected_swap_info.SerializeToString()

    expected_bot_account = Account()
    expected_bot_account.balance = 0
    serialized_expected_bot_account = expected_bot_account.SerializeToString()

    expected_consensus_account = ConsensusAccount()
    expected_consensus_account.block_cost = client_to_real_amount(TRANSACTION_FEE)
    serialized_expected_consensus_account = expected_consensus_account.SerializeToString()

    expected_state = {
        ADDRESS_TO_STORE_SWAP_INFO_BY: serialized_expected_swap_info,
        BOT_ADDRESS: serialized_expected_bot_account,
        ConsensusAccountHandler.CONSENSUS_ADDRESS: serialized_expected_consensus_account,
    }

    AtomicSwapHandler().apply(transaction=transaction_request, context=mock_context)

    state_as_list = mock_context.get_state(addresses=[
        ADDRESS_TO_STORE_SWAP_INFO_BY,
        BOT_ADDRESS,
        ConsensusAccountHandler.CONSENSUS_ADDRESS,
    ])
    state_as_dict = {entry.address: entry.data for entry in state_as_list}

    assert expected_state == state_as_dict


def test_set_lock_to_not_initialized_atomic_swap():
    """
    Case: set secret lock to not initialized swap.
    Expect: invalid transaction error is raised with swap was not initiated error message.
    """
    atomic_swap_init_payload = AtomicSwapSetSecretLockPayload(
        swap_id=SWAP_ID,
        secret_lock=SECRET_LOCK,
    )

    transaction_payload = TransactionPayload()
    transaction_payload.method = AtomicSwapMethod.SET_SECRET_LOCK
    transaction_payload.data = atomic_swap_init_payload.SerializeToString()

    serialized_transaction_payload = transaction_payload.SerializeToString()

    transaction_header = TransactionHeader(
        signer_public_key=BOT_PUBLIC_KEY,
        family_name=TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS.get('family_name'),
        family_version=TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS.get('family_version'),
        inputs=INPUTS,
        outputs=OUTPUTS,
        dependencies=[],
        payload_sha512=hash512(data=serialized_transaction_payload),
        batcher_public_key=RANDOM_NODE_PUBLIC_KEY,
        nonce=time.time().hex().encode(),
    )

    serialized_header = transaction_header.SerializeToString()

    transaction_request = TpProcessRequest(
        header=transaction_header,
        payload=serialized_transaction_payload,
        signature=create_signer(private_key=BOT_PRIVATE_KEY).sign(serialized_header),
    )

    mock_context = StubContext(inputs=INPUTS, outputs=OUTPUTS, initial_state={})

    with pytest.raises(InvalidTransaction) as error:
        AtomicSwapHandler().apply(transaction=transaction_request, context=mock_context)

    assert f'Atomic swap was not initiated for identifier {SWAP_ID}!' == str(error.value)


@pytest.mark.parametrize('swap_state', [
    AtomicSwapInfo.CLOSED,
    AtomicSwapInfo.EXPIRED,
])
def test_set_lock_to_already_closed_or_expired_atomic_swap(swap_state):
    """
    Case: set secret lock to already closed or expired atomic swap.
    Expect: invalid transaction error is raised with already operation with closed or expired swap error message.
    """
    atomic_swap_init_payload = AtomicSwapSetSecretLockPayload(
        swap_id=SWAP_ID,
        secret_lock=SECRET_LOCK,
    )

    transaction_payload = TransactionPayload()
    transaction_payload.method = AtomicSwapMethod.SET_SECRET_LOCK
    transaction_payload.data = atomic_swap_init_payload.SerializeToString()

    serialized_transaction_payload = transaction_payload.SerializeToString()

    transaction_header = TransactionHeader(
        signer_public_key=BOT_PUBLIC_KEY,
        family_name=TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS.get('family_name'),
        family_version=TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS.get('family_version'),
        inputs=INPUTS,
        outputs=OUTPUTS,
        dependencies=[],
        payload_sha512=hash512(data=serialized_transaction_payload),
        batcher_public_key=RANDOM_NODE_PUBLIC_KEY,
        nonce=time.time().hex().encode(),
    )

    serialized_header = transaction_header.SerializeToString()

    transaction_request = TpProcessRequest(
        header=transaction_header,
        payload=serialized_transaction_payload,
        signature=create_signer(private_key=BOT_PRIVATE_KEY).sign(serialized_header),
    )

    already_set_lock_swap_info = AtomicSwapInfo()
    already_set_lock_swap_info.swap_id = SWAP_ID
    already_set_lock_swap_info.state = swap_state
    serialized_already_set_lock_swap_info = already_set_lock_swap_info.SerializeToString()

    mock_context = StubContext(inputs=INPUTS, outputs=OUTPUTS, initial_state={
        ADDRESS_TO_STORE_SWAP_INFO_BY: serialized_already_set_lock_swap_info,
    })

    with pytest.raises(InvalidTransaction) as error:
        AtomicSwapHandler().apply(transaction=transaction_request, context=mock_context)

    assert f'No operations can be done upon the swap: {SWAP_ID} as it is already closed or expired.' == str(error.value)


def test_set_lock_to_atomic_swap_with_set_lock():
    """
    Case: set secret lock to atomic swap with already set secret lock.
    Expect: invalid transaction error is raised with secret lock is already added error message.
    """
    atomic_swap_init_payload = AtomicSwapSetSecretLockPayload(
        swap_id=SWAP_ID,
        secret_lock=SECRET_LOCK,
    )

    transaction_payload = TransactionPayload()
    transaction_payload.method = AtomicSwapMethod.SET_SECRET_LOCK
    transaction_payload.data = atomic_swap_init_payload.SerializeToString()

    serialized_transaction_payload = transaction_payload.SerializeToString()

    transaction_header = TransactionHeader(
        signer_public_key=BOT_PUBLIC_KEY,
        family_name=TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS.get('family_name'),
        family_version=TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS.get('family_version'),
        inputs=INPUTS,
        outputs=OUTPUTS,
        dependencies=[],
        payload_sha512=hash512(data=serialized_transaction_payload),
        batcher_public_key=RANDOM_NODE_PUBLIC_KEY,
        nonce=time.time().hex().encode(),
    )

    serialized_header = transaction_header.SerializeToString()

    transaction_request = TpProcessRequest(
        header=transaction_header,
        payload=serialized_transaction_payload,
        signature=create_signer(private_key=BOT_PRIVATE_KEY).sign(serialized_header),
    )

    already_set_lock_swap_info = AtomicSwapInfo()
    already_set_lock_swap_info.swap_id = SWAP_ID
    already_set_lock_swap_info.state = AtomicSwapInfo.OPENED
    already_set_lock_swap_info.secret_lock = SECRET_LOCK
    serialized_already_set_lock_swap_info = already_set_lock_swap_info.SerializeToString()

    mock_context = StubContext(inputs=INPUTS, outputs=OUTPUTS, initial_state={
        ADDRESS_TO_STORE_SWAP_INFO_BY: serialized_already_set_lock_swap_info,
    })

    with pytest.raises(InvalidTransaction) as error:
        AtomicSwapHandler().apply(transaction=transaction_request, context=mock_context)

    assert f'Secret lock is already added for {SWAP_ID}.' == str(error.value)
