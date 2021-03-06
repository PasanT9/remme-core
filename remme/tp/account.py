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
    Account, GenesisStatus, AccountMethod, GenesisPayload,
    TransferPayload
)
from remme.settings import (
    GENESIS_ADDRESS, ZERO_ADDRESS
)
from remme.shared.forms import TransferPayloadForm, GenesisPayloadForm
from remme.shared.constants import Events, EMIT_EVENT

from .basic import (
    PB_CLASS, PROCESSOR, VALIDATOR, BasicHandler, get_data, get_multiple_data
)


LOGGER = logging.getLogger(__name__)

FAMILY_NAME = 'account'
FAMILY_VERSIONS = ['0.1']


def get_account_by_address(context, address):
    account = get_data(context, Account, address)
    if account is None:
        return Account()
    return account


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
        account.balance = genesis_payload.total_supply

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
        address = self.make_address_from_data(public_key)

        return self._transfer_from_address(context, address, transfer_payload)

    def _transfer_from_address(self, context, address_from, transfer_payload):
        if not transfer_payload.value:
            raise InvalidTransaction('Could not transfer with zero amount.')

        if not transfer_payload.address_to.startswith(self._prefix) \
                and transfer_payload.address_to != ZERO_ADDRESS:
            raise InvalidTransaction('Receiver address has to be of an account type.')

        if address_from == transfer_payload.address_to:
            raise InvalidTransaction('Account cannot send tokens to itself.')

        signer_account, receiver_account = get_multiple_data(context, [
            (address_from, Account),
            (transfer_payload.address_to, Account),
        ])

        if signer_account is None:
            signer_account = Account()

        if receiver_account is None:
            receiver_account = Account()

        if signer_account.balance < transfer_payload.value:
            raise InvalidTransaction(
                f'Not enough transferable balance. Sender\'s current balance: {signer_account.balance}.',
            )

        receiver_account.balance += transfer_payload.value
        signer_account.balance -= transfer_payload.value

        LOGGER.info(
            f'Transferred {transfer_payload.value} tokens from {address_from} to {transfer_payload.address_to}.',
        )

        return {
            address_from: signer_account,
            transfer_payload.address_to: receiver_account,
        }
