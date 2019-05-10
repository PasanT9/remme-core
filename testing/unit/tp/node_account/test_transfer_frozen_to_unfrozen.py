"""
Provide tests for account handler apply (genesis) method implementation.
"""
import time
from datetime import datetime, timedelta

import pytest
from freezegun import freeze_time

from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.protobuf.processor_pb2 import TpProcessRequest
from sawtooth_sdk.protobuf.setting_pb2 import Setting
from sawtooth_sdk.protobuf.transaction_pb2 import (
    Transaction,
    TransactionHeader,
)
from remme.protos.node_account_pb2 import (
    NodeAccount,
    NodeAccountMethod,
    ShareInfo,
)
from remme.clients.block_info import (
    CONFIG_ADDRESS,
    BlockInfoClient,
)
from remme.protos.block_info_pb2 import BlockInfo, BlockInfoConfig
from remme.protos.transaction_pb2 import TransactionPayload, EmptyPayload
from remme.settings import SETTINGS_MINIMUM_STAKE, SETTINGS_BLOCKCHAIN_TAX, TRANSACTION_FEE
from remme.settings.helper import _make_settings_key
from remme.shared.utils import hash512, client_to_real_amount
from remme.tp.node_account import NodeAccountHandler
from remme.tp.consensus_account import ConsensusAccountHandler, ConsensusAccount
from testing.conftest import create_signer
from testing.mocks.stub import StubContext
from testing.utils.client import proto_error_msg

RANDOM_NODE_PUBLIC_KEY = '039d6881f0a71d05659e1f40b443684b93c7b7c504ea23ea8949ef5216a2236940'

BALANCE = 100
FROZEN = 300_000
UNFROZEN = 0
MINIMUM_STAKE = 250_000
BLOCKCHAIN_TAX = 0.1

NODE_ACCOUNT_ADDRESS_FROM = '116829d71fa7e120c60fb392a64fd69de891a60c667d9ea9e5d9d9d617263be6c20202'

NODE_ACCOUNT_FROM_PRIVATE_KEY = '1cb15ecfe1b3dc02df0003ac396037f85b98cf9f99b0beae000dc5e9e8b6dab4'

ADDRESS_TO_GET_MINIMUM_STAKE_AMOUNT = _make_settings_key(SETTINGS_MINIMUM_STAKE)
ADDRESS_TO_BLOCKCHAIN_TAX = _make_settings_key(SETTINGS_BLOCKCHAIN_TAX)

BLOCK_INFO_CONFIG_ADDRESS = CONFIG_ADDRESS
BLOCK_INFO_ADDRESS = BlockInfoClient.create_block_address(1000)

INPUTS = OUTPUTS = [
    NODE_ACCOUNT_ADDRESS_FROM,
    ADDRESS_TO_GET_MINIMUM_STAKE_AMOUNT,
    ADDRESS_TO_BLOCKCHAIN_TAX,
    BLOCK_INFO_CONFIG_ADDRESS,
    BLOCK_INFO_ADDRESS,
    ConsensusAccountHandler.CONSENSUS_ADDRESS,
]

TRANSACTION_REQUEST_ACCOUNT_HANDLER_PARAMS = {
    'family_name': NodeAccountHandler().family_name,
    'family_version': NodeAccountHandler()._family_versions[0],
}


def create_context(account_from_frozen_balance, account_to_unfrozen_balance,
                   balance=BALANCE,
                   minimum_stake=MINIMUM_STAKE, blockchain_tax=BLOCKCHAIN_TAX,
                   status=NodeAccount.OPENED, last_defrost_timestamp=0, shares=None):
    """
    Create stub context with initial data.

    Stub context is an interface around Sawtooth state, consider as database.
    State is key-value storage that contains address with its data (i.e. account balance).

    References:
        - https://github.com/Remmeauth/remme-core/blob/dev/testing/mocks/stub.py
    """
    node_account = NodeAccount()
    node_account.balance = client_to_real_amount(balance)
    node_account.node_state = status
    node_account.last_defrost_timestamp = last_defrost_timestamp

    node_account.reputation.frozen = client_to_real_amount(account_from_frozen_balance)
    node_account.reputation.unfrozen = client_to_real_amount(account_to_unfrozen_balance)
    if shares:
        node_account.shares.extend(shares)
    serialized_account_balance = node_account.SerializeToString()

    minimum_stake_setting = Setting()
    minimum_stake_setting.entries.add(key=SETTINGS_MINIMUM_STAKE, value=str(minimum_stake))
    serialized_minimum_stake_setting = minimum_stake_setting.SerializeToString()

    bt_setting = Setting()
    bt_setting.entries.add(key=SETTINGS_BLOCKCHAIN_TAX, value=str(blockchain_tax))
    serialized_bt_setting = bt_setting.SerializeToString()

    block_info_config = BlockInfoConfig()
    block_info_config.latest_block = 1000
    serialized_block_info_config = block_info_config.SerializeToString()

    block_info = BlockInfo()
    block_info.timestamp = int(datetime.now().timestamp())
    serialized_block_info = block_info.SerializeToString()

    consensus_account = ConsensusAccount()
    consensus_account.block_cost = 0
    serialized_consensus_account = consensus_account.SerializeToString()

    initial_state = {
        NODE_ACCOUNT_ADDRESS_FROM: serialized_account_balance,
        ADDRESS_TO_GET_MINIMUM_STAKE_AMOUNT: serialized_minimum_stake_setting,
        ADDRESS_TO_BLOCKCHAIN_TAX: serialized_bt_setting,
        BLOCK_INFO_CONFIG_ADDRESS: serialized_block_info_config,
        BLOCK_INFO_ADDRESS: serialized_block_info,
        ConsensusAccountHandler.CONSENSUS_ADDRESS: serialized_consensus_account,
    }

    return StubContext(inputs=INPUTS, outputs=OUTPUTS, initial_state=initial_state)


def test_transfer_from_frozen_to_unfrozen_more_than_one_month():
    """
    Case: send transaction request, to transfer tokens from reputational frozen balance to
          reputational unfrozen balance when it allowed.
    Expect: frozen and unfrozen balances, stored in state, are changed according to transfer amount.
    """
    internal_transfer_payload = EmptyPayload()

    transaction_payload = TransactionPayload()
    transaction_payload.method = NodeAccountMethod.TRANSFER_FROM_FROZEN_TO_UNFROZEN
    transaction_payload.data = internal_transfer_payload.SerializeToString()

    serialized_transaction_payload = transaction_payload.SerializeToString()

    transaction_header = TransactionHeader(
        signer_public_key=RANDOM_NODE_PUBLIC_KEY,
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
        signature=create_signer(private_key=NODE_ACCOUNT_FROM_PRIVATE_KEY).sign(serialized_header),
    )
    now = datetime.utcnow()

    shares = [
        ShareInfo(
            block_num=10,
            frozen_share=4000,
            reward=10_000,
            block_timestamp=int((now - timedelta(days=28)).timestamp()),
        )
    ]
    mock_context = create_context(account_from_frozen_balance=FROZEN,
                                  account_to_unfrozen_balance=UNFROZEN,
                                  shares=shares)

    NodeAccountHandler().apply(transaction=transaction_request, context=mock_context)

    state_as_list = mock_context.get_state(addresses=[
        NODE_ACCOUNT_ADDRESS_FROM,
    ])
    state_as_dict = {entry.address: entry.data for entry in state_as_list}

    node_acc = NodeAccount()
    node_acc.ParseFromString(state_as_dict[NODE_ACCOUNT_ADDRESS_FROM])

    delta = 0.0333  # 0.4 * 1/12 * 10_000

    assert node_acc.balance == client_to_real_amount(BALANCE - TRANSACTION_FEE)
    assert node_acc.reputation.frozen == client_to_real_amount(FROZEN - delta)
    assert node_acc.reputation.unfrozen == client_to_real_amount(UNFROZEN + delta)

    assert node_acc.last_defrost_timestamp is not None

    assert len(node_acc.shares) == 1

    share = node_acc.shares[0]

    assert share.defrost_months == 1


def test_transfer_from_frozen_to_unfrozen_more_than_one_two_with_already_calculated_frozen_from_previous_month():
    """
    Case: send transaction request, to transfer tokens from reputational frozen balance to
          reputational unfrozen balance when it allowed after two month.
    Expect: frozen and unfrozen balances, stored in state, are changed according to transfer amount.
    """
    internal_transfer_payload = EmptyPayload()

    transaction_payload = TransactionPayload()
    transaction_payload.method = NodeAccountMethod.TRANSFER_FROM_FROZEN_TO_UNFROZEN
    transaction_payload.data = internal_transfer_payload.SerializeToString()

    serialized_transaction_payload = transaction_payload.SerializeToString()

    transaction_header = TransactionHeader(
        signer_public_key=RANDOM_NODE_PUBLIC_KEY,
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
        signature=create_signer(private_key=NODE_ACCOUNT_FROM_PRIVATE_KEY).sign(serialized_header),
    )
    now = datetime.utcnow() + timedelta(days=28)

    shares = [
        ShareInfo(
            block_num=10,
            frozen_share=4000,
            reward=10_000,
            block_timestamp=int((datetime.utcnow() - timedelta(days=28)).timestamp()),
            defrost_months=1,
        ),
        ShareInfo(
            block_num=10,
            frozen_share=4000,
            reward=10_000,
            block_timestamp=int((datetime.utcnow() - timedelta(days=28)).timestamp()),
            defrost_months=0,
        ),
    ]
    with freeze_time(now) as frozen_datetime:
        mock_context = create_context(account_from_frozen_balance=FROZEN,
                                      account_to_unfrozen_balance=UNFROZEN,
                                      shares=shares)
        NodeAccountHandler().apply(transaction=transaction_request,
                                   context=mock_context)

    state_as_list = mock_context.get_state(addresses=[
        NODE_ACCOUNT_ADDRESS_FROM,
    ])
    state_as_dict = {entry.address: entry.data for entry in state_as_list}

    node_acc = NodeAccount()
    node_acc.ParseFromString(state_as_dict[NODE_ACCOUNT_ADDRESS_FROM])

    delta1 = 0.0333  # 0.4 * 1/12 * 10_000
    delta2 = 0.0667  # 0.4 * 2/12 * 10_000
    delta = delta1 + delta2

    assert node_acc.balance == client_to_real_amount(BALANCE - TRANSACTION_FEE)
    assert node_acc.reputation.frozen == client_to_real_amount(FROZEN - delta)
    assert node_acc.reputation.unfrozen == client_to_real_amount(UNFROZEN + delta)

    assert node_acc.last_defrost_timestamp is not None

    assert len(node_acc.shares) == 2

    share1 = node_acc.shares[0]
    share2 = node_acc.shares[1]

    assert share1.defrost_months == 2
    assert share2.defrost_months == 2


def test_transfer_from_frozen_to_unfrozen_one_share_unfrozen_already_and_one_more_than_12_month():
    internal_transfer_payload = EmptyPayload()

    transaction_payload = TransactionPayload()
    transaction_payload.method = NodeAccountMethod.TRANSFER_FROM_FROZEN_TO_UNFROZEN
    transaction_payload.data = internal_transfer_payload.SerializeToString()

    serialized_transaction_payload = transaction_payload.SerializeToString()

    transaction_header = TransactionHeader(
        signer_public_key=RANDOM_NODE_PUBLIC_KEY,
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
        signature=create_signer(private_key=NODE_ACCOUNT_FROM_PRIVATE_KEY).sign(serialized_header),
    )
    now = datetime.utcnow()

    shares = [
        ShareInfo(
            block_num=10,
            frozen_share=4000,
            reward=10_000,
            block_timestamp=int((datetime.utcnow() - timedelta(days=28)).timestamp()),
            defrost_months=1,
        ),
        ShareInfo(
            block_num=10,
            frozen_share=4000,
            reward=10_000,
            block_timestamp=int((datetime.utcnow() - timedelta(days=28 * 12)).timestamp()),
            defrost_months=0,
        ),
    ]
    mock_context = create_context(account_from_frozen_balance=FROZEN,
                                  account_to_unfrozen_balance=UNFROZEN,
                                  shares=shares)

    NodeAccountHandler().apply(transaction=transaction_request, context=mock_context)

    state_as_list = mock_context.get_state(addresses=[
        NODE_ACCOUNT_ADDRESS_FROM,
    ])
    state_as_dict = {entry.address: entry.data for entry in state_as_list}

    node_acc = NodeAccount()
    node_acc.ParseFromString(state_as_dict[NODE_ACCOUNT_ADDRESS_FROM])

    delta1 = 0
    delta2 = 0.4  # 0.4 * 12/12 * 10_000
    delta = delta1 + delta2

    assert node_acc.balance == client_to_real_amount(BALANCE - TRANSACTION_FEE)
    assert node_acc.reputation.frozen == client_to_real_amount(FROZEN - delta)
    assert node_acc.reputation.unfrozen == client_to_real_amount(UNFROZEN + delta)

    assert node_acc.last_defrost_timestamp is not None

    assert len(node_acc.shares) == 1

    share = node_acc.shares[0]

    assert share.defrost_months == 1


def test_transfer_from_frozen_to_unfrozen_remove_shares_more_then_12_month():
    internal_transfer_payload = EmptyPayload()

    transaction_payload = TransactionPayload()
    transaction_payload.method = NodeAccountMethod.TRANSFER_FROM_FROZEN_TO_UNFROZEN
    transaction_payload.data = internal_transfer_payload.SerializeToString()

    serialized_transaction_payload = transaction_payload.SerializeToString()

    transaction_header = TransactionHeader(
        signer_public_key=RANDOM_NODE_PUBLIC_KEY,
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
        signature=create_signer(private_key=NODE_ACCOUNT_FROM_PRIVATE_KEY).sign(serialized_header),
    )
    now = datetime.utcnow()

    shares = [
        ShareInfo(
            block_num=10,
            frozen_share=4000,
            reward=10_000,
            block_timestamp=int((datetime.utcnow() - timedelta(days=28)).timestamp()),
            defrost_months=0,
        ),
        ShareInfo(
            block_num=11,
            frozen_share=4000,
            reward=10_000,
            block_timestamp=int((datetime.utcnow() - timedelta(days=28 * 12)).timestamp()),
            defrost_months=0,
        ),
        ShareInfo(
            block_num=12,
            frozen_share=6000,
            reward=15_000,
            block_timestamp=int((datetime.utcnow() - timedelta(days=28 * 12)).timestamp()),
            defrost_months=0,
        ),
    ]
    mock_context = create_context(account_from_frozen_balance=FROZEN,
                                  account_to_unfrozen_balance=UNFROZEN,
                                  shares=shares)

    NodeAccountHandler().apply(transaction=transaction_request, context=mock_context)

    state_as_list = mock_context.get_state(addresses=[
        NODE_ACCOUNT_ADDRESS_FROM,
    ])
    state_as_dict = {entry.address: entry.data for entry in state_as_list}

    node_acc = NodeAccount()
    node_acc.ParseFromString(state_as_dict[NODE_ACCOUNT_ADDRESS_FROM])

    delta1 = 0.0333  # 0.4 * 1/12 * 10_000
    delta2 = 0.4  # 0.4 * 12/12 * 10_000
    delta3 = 0.9  # 0.6 * 12/12 * 15_000

    delta = delta1 + delta2 + delta3

    assert node_acc.reputation.frozen == client_to_real_amount(FROZEN - delta)
    assert node_acc.reputation.unfrozen == client_to_real_amount(UNFROZEN + delta)

    assert node_acc.last_defrost_timestamp is not None

    assert len(node_acc.shares) == 1

    share = node_acc.shares[0]

    assert share.defrost_months == 1


def test_transfer_from_frozen_already_defrosted_in_two_week_period():
    internal_transfer_payload = EmptyPayload()

    transaction_payload = TransactionPayload()
    transaction_payload.method = NodeAccountMethod.TRANSFER_FROM_FROZEN_TO_UNFROZEN
    transaction_payload.data = internal_transfer_payload.SerializeToString()

    serialized_transaction_payload = transaction_payload.SerializeToString()

    transaction_header = TransactionHeader(
        signer_public_key=RANDOM_NODE_PUBLIC_KEY,
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
        signature=create_signer(private_key=NODE_ACCOUNT_FROM_PRIVATE_KEY).sign(serialized_header),
    )
    mock_context = create_context(account_from_frozen_balance=FROZEN,
                                  account_to_unfrozen_balance=UNFROZEN,
                                  last_defrost_timestamp=int(datetime.utcnow().timestamp()) + 160)

    with pytest.raises(InvalidTransaction) as error:
        NodeAccountHandler().apply(transaction=transaction_request, context=mock_context)

    assert 'Passed not enough time from previous defrost.' == str(error.value)


def test_transfer_from_frozen_share_overflow():
    internal_transfer_payload = EmptyPayload()

    transaction_payload = TransactionPayload()
    transaction_payload.method = NodeAccountMethod.TRANSFER_FROM_FROZEN_TO_UNFROZEN
    transaction_payload.data = internal_transfer_payload.SerializeToString()

    serialized_transaction_payload = transaction_payload.SerializeToString()

    transaction_header = TransactionHeader(
        signer_public_key=RANDOM_NODE_PUBLIC_KEY,
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
        signature=create_signer(private_key=NODE_ACCOUNT_FROM_PRIVATE_KEY).sign(serialized_header),
    )
    now = datetime.utcnow()

    FROZEN = MINIMUM_STAKE + 500

    shares = [
        ShareInfo(
            block_num=10,
            frozen_share=client_to_real_amount(0.6),
            reward=client_to_real_amount(6000),
            block_timestamp=int((datetime.utcnow() - timedelta(days=28)).timestamp()),
            defrost_months=0,
        ),
        ShareInfo(
            block_num=11,
            frozen_share=client_to_real_amount(0.3),
            reward=client_to_real_amount(2000),
            block_timestamp=int((datetime.utcnow() - timedelta(days=28)).timestamp()),
            defrost_months=0,
        ),
        ShareInfo(
            block_num=12,
            frozen_share=client_to_real_amount(0.4),
            reward=client_to_real_amount(2500),
            block_timestamp=int((datetime.utcnow() - timedelta(days=28)).timestamp()),
            defrost_months=0,
        ),
        ShareInfo(
            block_num=13,
            frozen_share=client_to_real_amount(0.7),
            reward=client_to_real_amount(2100),
            block_timestamp=int((datetime.utcnow() - timedelta(days=28)).timestamp()),
            defrost_months=0,
        ),
    ]
    mock_context = create_context(account_from_frozen_balance=FROZEN,
                                  account_to_unfrozen_balance=UNFROZEN,
                                  shares=shares)

    NodeAccountHandler().apply(transaction=transaction_request, context=mock_context)

    state_as_list = mock_context.get_state(addresses=[
        NODE_ACCOUNT_ADDRESS_FROM,
    ])
    state_as_dict = {entry.address: entry.data for entry in state_as_list}

    node_acc = NodeAccount()
    node_acc.ParseFromString(state_as_dict[NODE_ACCOUNT_ADDRESS_FROM])

    delta1 = 300  # 0.6 * 1/12 * 6000
    delta2 = 50  # 0.3 * 1/12 * 2000
    delta3 = 83.25  # 0.4 * 1/12 * 2500
    delta4 = 122.43  # 0.7 * 1/12 * 2100

    delta = delta1 + delta2 + delta3 + delta4

    assert node_acc.reputation.frozen == client_to_real_amount(FROZEN - delta + delta4)
    assert node_acc.reputation.unfrozen == client_to_real_amount(UNFROZEN + delta - delta4)

    assert node_acc.last_defrost_timestamp is not None

    assert len(node_acc.shares) == 4

    share1 = node_acc.shares[0]
    share2 = node_acc.shares[1]
    share3 = node_acc.shares[2]
    share4 = node_acc.shares[3]

    assert share1.defrost_months == 1
    assert share2.defrost_months == 1
    assert share3.defrost_months == 1
    assert share4.defrost_months == 0
