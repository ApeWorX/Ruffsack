// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.30;

interface ICaravan {
    function initialize(address[] memory signers, uint256 threshold) external;
}

/**
 *  @title CaravanProxy
 *  @author ApeWorX LTD.
 */
contract CaravanProxy {
    // NOTE: Must be first slot, this matches the same storage variable in `Caravan`
    address internal IMPLEMENTATION;

    // NOTE: NO OTHER VARIABLES ALLOWED

    constructor(address implementation, address[] memory signers, uint256 threshold) {
        IMPLEMENTATION = implementation;

        bytes memory data = abi.encodeCall(ICaravan.initialize, (signers, threshold));
        (bool success, bytes memory err) = implementation.delegatecall(data);
        if (!success) revert(string(err));
    }

    // If no ether, forward to proxy implementation...
    fallback() external {
        assembly {
            let implementation := sload(0)
            calldatacopy(0, 0, calldatasize())
            let success := delegatecall(gas(), implementation, 0, calldatasize(), 0, 0)
            returndatacopy(0, 0, returndatasize())
            if iszero(success) { revert(0, returndatasize()) }
            return(0, returndatasize())
        }
    }

    // ...otherwise receive any ether and do nothing
    receive() external payable {}
}
