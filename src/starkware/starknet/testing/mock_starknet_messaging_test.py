import pytest

from starkware.starknet.services.api.messages import StarknetMessageToL1, StarknetMessageToL2
from starkware.starknet.testing.contracts import MockStarknetMessaging


@pytest.fixture
def mock_starknet_contract(eth_test_utils):
    return eth_test_utils.accounts[0].deploy(MockStarknetMessaging)


def test_mock_send_message_from_l2(eth_test_utils, mock_starknet_contract):
    l1_address = eth_test_utils.accounts[0].address
    l2_address = 1
    payload = [56, 78]

    msg = StarknetMessageToL1(
        from_address=l2_address,
        to_address=int(l1_address, 16),
        payload=payload,
    )
    msg_hash = msg.get_hash()
    assert mock_starknet_contract.l2ToL1Messages.call(msg_hash) == 0

    mock_starknet_contract.mockSendMessageFromL2.transact(l2_address, int(l1_address, 16), payload)
    assert mock_starknet_contract.l2ToL1Messages.call(msg_hash) == 1

    mock_starknet_contract.consumeMessageFromL2.transact(l2_address, payload)
    assert mock_starknet_contract.l2ToL1Messages.call(msg_hash) == 0


def test_mock_consume_message_to_l2(eth_test_utils, mock_starknet_contract):
    l1_address = eth_test_utils.accounts[0].address
    l2_address = 1
    selector = 5
    payload = [56, 78]

    nonce = mock_starknet_contract.l1ToL2MessageNonce.call()
    msg = StarknetMessageToL2(
        from_address=int(l1_address, 16),
        to_address=l2_address,
        l1_handler_selector=selector,
        payload=payload,
        nonce=nonce,
    )
    msg_hash = msg.get_hash()
    assert mock_starknet_contract.l1ToL2Messages.call(msg_hash) == 0

    mock_starknet_contract.sendMessageToL2.transact(l2_address, selector, payload)
    assert mock_starknet_contract.l1ToL2Messages.call(msg_hash) == 1

    mock_starknet_contract.mockConsumeMessageToL2.transact(
        int(l1_address, 16),
        l2_address,
        selector,
        payload,
        nonce,
    )
    assert mock_starknet_contract.l1ToL2Messages.call(msg_hash) == 0
