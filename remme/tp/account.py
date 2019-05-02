# Copyright 2018 REMME
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------

import logging
from sawtooth_sdk.processor.exceptions import InvalidTransaction

from remme.protos.account_pb2 import (
    Account,
    GenesisStatus,
    AccountMethod,
    GenesisPayload,
    TransferPayload
)
from remme.protos.consensus_account_pb2 import ConsensusAccount
from remme.protos.node_account_pb2 import (
    NodeAccount,
)
from remme.tp.node_account import NodeAccountHandler
from remme.settings import GENESIS_ADDRESS
from remme.shared.forms import TransferPayloadForm, GenesisPayloadForm
from remme.shared.constants import Events, EMIT_EVENT
from remme.shared.utils import client_to_real_amount

from .basic import (
    PB_CLASS, PROCESSOR, VALIDATOR, BasicHandler, get_data, get_multiple_data
)

LOGGER = logging.getLogger(__name__)

FAMILY_NAME = 'account'
FAMILY_VERSIONS = ['0.1']


class AccountHandler(BasicHandler):

    def __init__(self):
        super().__init__(FAMILY_NAME, FAMILY_VERSIONS)

    def get_state_processor(self):
        return {
            AccountMethod.TRANSFER: {
                PB_CLASS: TransferPayload,
                PROCESSOR: self._transfer,
                EMIT_EVENT: Events.ACCOUNT_TRANSFER.value,
                VALIDATOR: TransferPayloadForm,
            },
            AccountMethod.GENESIS: {
                PB_CLASS: GenesisPayload,
                PROCESSOR: self._genesis,
                VALIDATOR: GenesisPayloadForm,
            }
        }

    def _genesis(self, context, pub_key, genesis_payload):
        signer_key = self.make_address_from_data(pub_key)
        genesis_status = get_data(context, GenesisStatus, GENESIS_ADDRESS)

        if not genesis_status:
            genesis_status = GenesisStatus()
            genesis_status.status = True

        elif genesis_status.status:
            raise InvalidTransaction('Genesis is already initialized.')

        account = Account()
        account.balance = client_to_real_amount(genesis_payload.total_supply)

        LOGGER.info(
            f'Genesis transaction is generated. Issued {genesis_payload.total_supply} tokens to address {signer_key}',
        )

        return {
            signer_key: account,
            GENESIS_ADDRESS: genesis_status
        }

    def _transfer(self, context, public_key, transfer_payload):
        """
        Make public transfer.

        Public transfer means additional check if address to send tokens from isn't zero address.
        Zero address is used only for internal transactions.

        References:
            - https://github.com/Remmeauth/remme-core/blob/dev/remme/genesis/__main__.py
        """
        if transfer_payload.sender_account_type == TransferPayload.ACCOUNT:
            address = self.make_address_from_data(public_key)

        else:
            address = NodeAccountHandler().make_address_from_data(public_key)

        return self._transfer_from_address(context, address, transfer_payload)

    def is_address_account_type(self, address):
        """
        Check if address is account address type.
        """
        from .consensus_account import ConsensusAccountHandler

        return address.startswith(self._prefix) or \
                address.startswith(NodeAccountHandler()._prefix) or \
                address == ConsensusAccountHandler.CONSENSUS_ADDRESS

    def _transfer_from_address(self, context, address_from, transfer_payload,
                               sender_key='balance', receiver_key='balance'):
        from .consensus_account import ConsensusAccountHandler

        amount = client_to_real_amount(transfer_payload.value)

        if not amount:
            raise InvalidTransaction('Could not transfer with zero amount.')

        if not self.is_address_account_type(address=transfer_payload.address_to):
            raise InvalidTransaction('Receiver address has to be of an account type.')

        if address_from == transfer_payload.address_to:
            raise InvalidTransaction('Account cannot send tokens to itself.')

        pb_classes = {
            '000000': Account,
            AccountHandler()._prefix: Account,
            NodeAccountHandler()._prefix: NodeAccount,
            ConsensusAccountHandler()._prefix: ConsensusAccount,
        }

        sender_account_pb_class = pb_classes.get(address_from[:6])
        receiver_account_pb_class = pb_classes.get(transfer_payload.address_to[:6])

        sender_account, receiver_account = get_multiple_data(context, [
            (address_from, sender_account_pb_class),
            (transfer_payload.address_to, receiver_account_pb_class),
        ])

        if sender_account is None:
            if sender_account_pb_class is NodeAccount:
                raise InvalidTransaction('Node account could not be created in transfer.')
            sender_account = sender_account_pb_class()

        if receiver_account is None:
            if receiver_account_pb_class is NodeAccount:
                raise InvalidTransaction('Node account could not be created in transfer.')
            receiver_account = receiver_account_pb_class()

        sender_balance = getattr(sender_account, sender_key, 0)
        receiver_balance = getattr(receiver_account, receiver_key, 0)

        if sender_balance < amount:
            raise InvalidTransaction(
                f'Not enough transferable balance. Sender\'s current balance: {sender_balance}.',
            )

        setattr(receiver_account, receiver_key, receiver_balance + amount)
        setattr(sender_account, sender_key, sender_balance - amount)

        LOGGER.info(
            f'Transferred {amount} tokens from {address_from} to '
            f'{transfer_payload.address_to}. {address_from} balance: '
            f'{sender_balance}. {transfer_payload.address_to} balance: '
            f'{receiver_balance}',
        )

        return {
            address_from: sender_account,
            transfer_payload.address_to: receiver_account,
        }
