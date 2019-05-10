import os

KEY_DIR = '/etc/sawtooth/keys'
PRIV_KEY_FILE = os.path.join(KEY_DIR, 'validator.priv')
PUB_KEY_FILE = os.path.join(KEY_DIR, 'validator.pub')

SETTINGS_PUB_KEY_ENCRYPTION = 'remme.settings.pub_key_encryption'
SETTINGS_KEY_ZERO_ADDRESS_OWNERS = 'remme.settings.zero_address_owners'
SETTINGS_MINIMUM_STAKE = 'remme.settings.minimum_stake'
SETTINGS_BLOCKCHAIN_TAX = 'remme.settings.blockchain_tax'
SETTINGS_MIN_SHARE = 'remme.settings.min_share'
SETTINGS_GENESIS_OWNERS = 'remme.settings.genesis_owners'
SETTINGS_OBLIGATORY_PAYMENT = 'remme.settings.obligatory_payment'

ZMQ_CONNECTION_TIMEOUT = 30
# Number of seconds to wait for state operations to succeed
STATE_TIMEOUT_SEC = 30

ZERO_ADDRESS = '0' * 70
GENESIS_ADDRESS = '0' * 69 + '1'
NODE_STATE_ADDRESS = '0' * 69 + '2'

DIVISIBILITY_FACTOR = 4
MAX_DEFROST_MONTH = 12
TRANSACTION_FEE = 10
