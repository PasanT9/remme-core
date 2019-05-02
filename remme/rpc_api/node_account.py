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
import json
import logging

from remme.clients.node_account import NodeAccountClient
from remme.protos.node_account_pb2 import NodeAccount
from remme.rpc_api.utils import validate_params
from remme.shared.utils import message_to_dict, real_to_client_amount
from remme.shared.forms import get_address_form

__all__ = (
    'get_node_account',
)

logger = logging.getLogger(__name__)


def _filter_shares(shares):
    for share in shares:
        share['reward'] = str(real_to_client_amount(share['reward']))
        share['frozen_share'] = str(real_to_client_amount(share['frozen_share']))
        yield share


@validate_params(get_address_form('node_account_address'))
async def get_node_account(request):
    """
    Get node account.

    Returns:
        Node account data (balance, reputation, node_state) in json.
    """
    client = NodeAccountClient()

    node_address = request.params['node_account_address']
    account = await client.get_account(node_address)

    data = message_to_dict(account)
    data['balance'] = str(real_to_client_amount(data['balance']))
    if 'reputation' in data:
        data['reputation']['frozen'] = str(real_to_client_amount(data['reputation']['frozen']))
        data['reputation']['unfrozen'] = str(real_to_client_amount(data['reputation']['unfrozen']))
    else:
        data['reputation'] = dict()
        data['reputation']['frozen'] = str(real_to_client_amount(0))
        data['reputation']['unfrozen'] = str(real_to_client_amount(0))
    if 'fixed_amount' in data:
        data['fixed_amount'] = str(real_to_client_amount(Decimal(data['fixed_amount'])))
    if 'shares':
        data['shares'] = list(_filter_shares(reversed(data['shares'])))
    return data
