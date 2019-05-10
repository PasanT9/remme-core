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

import copy
import logging
import hashlib
import abc
from datetime import datetime, timedelta

import ed25519
import secp256k1
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_der_public_key
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_signing.secp256k1 import (
    Secp256k1PublicKey,
    Secp256k1Context
)
from secp256k1 import lib

from remme.protos.account_pb2 import Account, TransferPayload
from remme.protos.pub_key_pb2 import (
    PubKeyStorage,
    NewPubKeyPayload,
    NewPubKeyStoreAndPayPayload,
    RevokePubKeyPayload,
    PubKeyMethod,
)
from remme.settings.helper import _get_setting_value
from remme.shared.forms import (
    NewPublicKeyPayloadForm,
    RevokePubKeyPayloadForm,
    NewPubKeyStoreAndPayPayloadForm,
)
from .basic import (
    BasicHandler, PB_CLASS, VALIDATOR, PROCESSOR,
    FEE_AUTO_CHARGER, get_multiple_data, get_data
)
from .account import AccountHandler

LOGGER = logging.getLogger(__name__)

FAMILY_NAME = 'pub_key'
FAMILY_VERSIONS = ['0.1']

PUB_KEY_ORGANIZATION = 'REMME'
PUB_KEY_MAX_VALIDITY = timedelta(365)

ECONOMY_IS_ENABLED_VALUE = 'true'


def detect_processor_cls(config):
    if isinstance(config, NewPubKeyPayload.RSAConfiguration):
        return RSAProcessor
    elif isinstance(config, NewPubKeyPayload.ECDSAConfiguration):
        return ECDSAProcessor
    elif isinstance(config, NewPubKeyPayload.Ed25519Configuration):
        return Ed25519Processor
    raise NotImplementedError


class BasePubKeyProcessor(metaclass=abc.ABCMeta):

    def __init__(self, entity_hash, entity_hash_signature,
                 valid_from, valid_to, hashing_algorithm, config):
        self._entity_hash = entity_hash
        self._entity_hash_signature = entity_hash_signature
        self._valid_from = valid_from
        self._valid_to = valid_to
        self._hashing_algorithm = hashing_algorithm
        self._config = config

    @abc.abstractmethod
    def get_hashing_algorithm(self):
        """Return libriary special algoritm in according to protobuf
        """

    def get_public_key(self):
        """Get public key from given signature or points
        """
        return self._config.key

    @abc.abstractmethod
    def verify(self):
        """Verify if signature was successfull
        """


class RSAProcessor(BasePubKeyProcessor):

    def verify(self):
        try:
            verifier = load_der_public_key(self.get_public_key(),
                                           default_backend())
        except ValueError:
            raise InvalidTransaction(
                'Cannot deserialize the provided public key. '
                'Check if it is in DER format.')

        try:
            verifier.verify(self._entity_hash_signature, self._entity_hash,
                            self._get_padding(), self.get_hashing_algorithm()())
            return True
        except Exception:
            return False

    def get_hashing_algorithm(self):
        alg_name = NewPubKeyPayload.HashingAlgorithm \
            .Name(self._hashing_algorithm)
        return getattr(hashes, alg_name)

    def _get_padding(self):
        Padding = NewPubKeyPayload.RSAConfiguration.Padding
        if self._config.padding == Padding.Value('PSS'):
            return padding.PSS(mgf=padding.MGF1(self.get_hashing_algorithm()()),
                               salt_length=padding.PSS.MAX_LENGTH)
        elif self._config.padding == Padding.Value('PKCS1v15'):
            return padding.PKCS1v15()
        else:
            raise NotImplementedError('Unsupported RSA padding')


class ECDSAProcessor(BasePubKeyProcessor):

    def verify(self):
        try:
            pub_key = secp256k1.PublicKey()
            pub_key.deserialize(self.get_public_key())

            assert pub_key.public_key, "No public key defined"

            if pub_key.flags & lib.SECP256K1_CONTEXT_VERIFY != \
               lib.SECP256K1_CONTEXT_VERIFY:
                raise Exception("instance not configured for sig verification")

            msg_digest = self.get_hashing_algorithm()(
                self._entity_hash).digest()
            raw_sig = pub_key.ecdsa_deserialize_compact(
                self._entity_hash_signature)

            verified = lib.secp256k1_ecdsa_verify(
                pub_key.ctx, raw_sig, msg_digest, pub_key.public_key)
        except Exception as e:
            LOGGER.exception(e)
            return False
        else:
            return bool(verified)

    def get_hashing_algorithm(self):
        alg_name = NewPubKeyPayload.HashingAlgorithm \
            .Name(self._hashing_algorithm).lower()
        return getattr(hashlib, alg_name)

    def get_curve_type(self):
        raise NotImplementedError


class Ed25519Processor(BasePubKeyProcessor):

    def verify(self):
        try:
            verifier = ed25519.VerifyingKey(self.get_public_key())
            msg_digest = self.get_hashing_algorithm()(self._entity_hash).digest()
            verifier.verify(self._entity_hash_signature, msg_digest)
            return True
        except Exception:
            return False

    def get_hashing_algorithm(self):
        alg_name = NewPubKeyPayload.HashingAlgorithm \
            .Name(self._hashing_algorithm).lower()
        return getattr(hashlib, alg_name)


class PubKeyHandler(BasicHandler):

    def __init__(self):
        super().__init__(FAMILY_NAME, FAMILY_VERSIONS)

    def get_state_processor(self):
        return {
            PubKeyMethod.STORE: {
                PB_CLASS: NewPubKeyPayload,
                PROCESSOR: self._store_pub_key,
                VALIDATOR: NewPublicKeyPayloadForm,
                FEE_AUTO_CHARGER: False,
            },
            PubKeyMethod.REVOKE: {
                PB_CLASS: RevokePubKeyPayload,
                PROCESSOR: self._revoke_pub_key,
                VALIDATOR: RevokePubKeyPayloadForm,
                FEE_AUTO_CHARGER: False,
            },
            PubKeyMethod.STORE_AND_PAY: {
                PB_CLASS: NewPubKeyStoreAndPayPayload,
                PROCESSOR: self._store_public_key_for_other,
                VALIDATOR: NewPubKeyStoreAndPayPayloadForm,
                FEE_AUTO_CHARGER: False,
            }
        }

    @staticmethod
    def _is_public_key_validity_exceeded(valid_from, valid_to):
        """
        Check if public key validity exceeds the maximum value.
        Public key validity maximum value in one year (365 days).
        """
        valid_from = datetime.fromtimestamp(valid_from)
        valid_to = datetime.fromtimestamp(valid_to)

        if valid_to - valid_from > PUB_KEY_MAX_VALIDITY:
            return False

        return True

    @staticmethod
    def _get_public_key_processor(transaction_payload):
        """
        Get public key processor (class with functionality according to kind of key) class.
        """
        conf_name = transaction_payload.WhichOneof('configuration')
        if not conf_name:
            raise InvalidTransaction('Configuration for public key not set')

        conf_payload = getattr(transaction_payload, conf_name)

        processor_cls = detect_processor_cls(conf_payload)
        processor = processor_cls(
            transaction_payload.entity_hash,
            transaction_payload.entity_hash_signature,
            transaction_payload.valid_from,
            transaction_payload.valid_to,
            transaction_payload.hashing_algorithm,
            conf_payload,
        )

        return processor

    def _store_pub_key(self, context, signer_pubkey, transaction_payload):
        """
        Store public key to the blockchain.

        Flow on client:
        1. Create private and public key (for instance, RSA).
        2. Create random data and sign it with private key to allows node verify signature,
            so ensure the address sent transaction is a real owner of public key.
        3. Send public key, signature, and other information to the node.

        Node does checks: if public key already exists in the blockchain, try to deserialize public key,
        try to verify signature, if validity exceeds.

        If transaction successfully passed checks, node charges fixed tokens price for storing
        public keys (if node economy is enabled) and link public key to the account (address).

        References:
            - https://docs.remme.io/remme-core/docs/family-pub-key.html
            - https://github.com/Remmeauth/remme-client-python/blob/develop/remme/remme_public_key_storage.py
        """
        processor = self._get_public_key_processor(transaction_payload=transaction_payload)

        if not processor.verify():
            raise InvalidTransaction('Invalid signature')

        public_key = processor.get_public_key()

        public_key_to_store_address = self.make_address_from_data(public_key)
        sender_account_address = AccountHandler().make_address_from_data(signer_pubkey)

        public_key_information, sender_account = get_multiple_data(context, [
            (public_key_to_store_address, PubKeyStorage),
            (sender_account_address, Account),
        ])
        if public_key_information:
            raise InvalidTransaction('This public key is already registered.')

        if not sender_account:
            sender_account = Account()

        if not self._is_public_key_validity_exceeded(
            valid_from=transaction_payload.valid_from,
            valid_to=transaction_payload.valid_to,
        ):
            raise InvalidTransaction('The public key validity exceeds the maximum value.')

        public_key_information = PubKeyStorage()
        public_key_information.owner = signer_pubkey
        public_key_information.payload.CopyFrom(transaction_payload)
        public_key_information.is_revoked = False

        state = {
            sender_account_address: sender_account,
            public_key_to_store_address: public_key_information,
        }

        self.set_fee_address(sender_account_address)

        sender_account = self._store_public_key_to_account(
            public_key_to_store_address=public_key_to_store_address,
            public_key_to_store_owner_account=sender_account,
        )

        state.update({
            sender_account_address: sender_account,
        })

        return state

    def _store_public_key_for_other(self, context, signer_pubkey, transaction_payload):
        """
        Store public key for other account.

        The transaction for account which want to pay for other account public keys storing.

        A first account -> send payload -> A second account -> send transaction with first account's public key,
        but sign and pay for storing on own -> Remme-core.

        So Remme core charges tokens from a second account, but store a first account's public key.
        Public key owner here is a first account.

        Arguments:
            context (sawtooth_sdk.processor.context): context to store updated state (blockchain data).
            signer_pubkey: transaction sender public key.
            transaction_payload (pub_key_pb2.NewPubKeyStoreAndPayPayload): payload for storing public key for other.
        """
        new_public_key_payload = transaction_payload.pub_key_payload

        owner_public_key_as_bytes = transaction_payload.owner_public_key
        owner_public_key_as_hex = owner_public_key_as_bytes.hex()

        owner_secp256k1_public_key = Secp256k1PublicKey.from_hex(owner_public_key_as_hex)

        is_owner_public_key_payload_signature_valid = Secp256k1Context().verify(
            signature=transaction_payload.signature_by_owner.hex(),
            message=new_public_key_payload.SerializeToString(),
            public_key=owner_secp256k1_public_key,
        )
        if not is_owner_public_key_payload_signature_valid:
            raise InvalidTransaction('Public key owner\'s signature is invalid.')

        processor = self._get_public_key_processor(transaction_payload=transaction_payload.pub_key_payload)

        if not processor.verify():
            raise InvalidTransaction('Payed public key has invalid signature.')

        public_key = processor.get_public_key()
        public_key_to_store_address = self.make_address_from_data(public_key)

        public_key_to_store_owner_address = AccountHandler().make_address_from_data(owner_public_key_as_hex)
        payer_for_storing_address = AccountHandler().make_address_from_data(signer_pubkey)

        public_key_information, public_key_to_store_owner_account, payer_for_storing_account = get_multiple_data(context, [
            (public_key_to_store_address, PubKeyStorage),
            (public_key_to_store_owner_address, Account),
            (payer_for_storing_address, Account),
        ])

        if public_key_information:
            raise InvalidTransaction('This public key is already registered.')

        if public_key_to_store_owner_account is None:
            public_key_to_store_owner_account = Account()

        if payer_for_storing_account is None:
            payer_for_storing_account = Account()

        if not self._is_public_key_validity_exceeded(
            valid_from=new_public_key_payload.valid_from,
            valid_to=new_public_key_payload.valid_to,
        ):
            raise InvalidTransaction('The public key validity exceeds the maximum value.')

        public_key_information = PubKeyStorage()
        public_key_information.owner = owner_public_key_as_hex
        public_key_information.payload.CopyFrom(new_public_key_payload)
        public_key_information.is_revoked = False

        state = {
            public_key_to_store_owner_address: public_key_to_store_owner_account,
            payer_for_storing_address: payer_for_storing_account,
            public_key_to_store_address: public_key_information,
        }

        self.set_fee_address(payer_for_storing_address)

        public_key_to_store_owner_account = self._store_public_key_to_account(
            public_key_to_store_address=public_key_to_store_address,
            public_key_to_store_owner_account=public_key_to_store_owner_account,
        )

        state.update({
            public_key_to_store_owner_address: public_key_to_store_owner_account,
        })

        return state

    @staticmethod
    def _store_public_key_to_account(public_key_to_store_address, public_key_to_store_owner_account):
        """
        Store public keys to account.
        """
        account = copy.deepcopy(public_key_to_store_owner_account)

        if public_key_to_store_address not in account.pub_keys:
            account.pub_keys.append(public_key_to_store_address)

        return account

    def _revoke_pub_key(self, context, signer_pubkey, revoke_pub_key_payload):
        payer_for_revoke_address = AccountHandler().make_address_from_data(signer_pubkey)
        public_key_information = get_data(context, PubKeyStorage, revoke_pub_key_payload.address)

        if public_key_information is None:
            raise InvalidTransaction('No public key is presented in chain.')

        if signer_pubkey != public_key_information.owner:
            raise InvalidTransaction('Only owner can revoke the public key.')

        if public_key_information.is_revoked:
            raise InvalidTransaction('The public key is already revoked.')

        public_key_information.is_revoked = True
        LOGGER.info('Revoked the pub key on address {}'.format(revoke_pub_key_payload.address))

        self.set_fee_address(payer_for_revoke_address)

        return {
            revoke_pub_key_payload.address: public_key_information,
        }
