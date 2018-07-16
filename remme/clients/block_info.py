import logging

from remme.clients.basic import BasicClient
from remme.protos.block_info_pb2 import BlockInfo, BlockInfoConfig

LOGGER = logging.getLogger(__name__)

NAMESPACE = '00b10c'
CONFIG_ADDRESS = NAMESPACE + '01' + '0' * 62
BLOCK_INFO_NAMESPACE = NAMESPACE + '00'


class BlockInfoClient(BasicClient):
    def __init__(self):
        super().__init__(None)

    def get_block_info(self, block_num):
        bi = BlockInfo()
        bi.ParseFromString(self.get_value(self.create_block_address(block_num)))
        return bi

    def get_many_block_info(self, start, end):
        result = []
        for i in range(start, end):
            result += [self.get_block_info(i)]
        return result

    def get_block_info_config(self):
        bic = BlockInfoConfig()
        bic.ParseFromString(self.get_value(CONFIG_ADDRESS))
        return bic

    def create_block_address(self, block_num):
        return BLOCK_INFO_NAMESPACE + hex(block_num)[2:].zfill(62)
