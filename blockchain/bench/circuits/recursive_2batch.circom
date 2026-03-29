pragma circom 2.0.0;

include "poseidon.circom";
include "comparators.circom";
include "gates.circom";

template BatchVerify() {
    signal input transactions[4];
    signal input expectedRoot;
    signal output valid;
    
    component h0 = Poseidon(2);
    h0.inputs[0] <== transactions[0];
    h0.inputs[1] <== transactions[1];
    
    component h1 = Poseidon(2);
    h1.inputs[0] <== transactions[2];
    h1.inputs[1] <== transactions[3];
    
    component h2 = Poseidon(2);
    h2.inputs[0] <== h0.out;
    h2.inputs[1] <== h1.out;
    
    component check = IsZero();
    check.in <== h2.out - expectedRoot;
    valid <== check.out;
}

// Verify 2 batches recursively
template RecursiveVerify2() {
    signal input batch0_txs[4];
    signal input batch1_txs[4];
    signal input root0;
    signal input root1;
    signal output valid;
    
    component v0 = BatchVerify();
    v0.transactions[0] <== batch0_txs[0];
    v0.transactions[1] <== batch0_txs[1];
    v0.transactions[2] <== batch0_txs[2];
    v0.transactions[3] <== batch0_txs[3];
    v0.expectedRoot <== root0;
    
    component v1 = BatchVerify();
    v1.transactions[0] <== batch1_txs[0];
    v1.transactions[1] <== batch1_txs[1];
    v1.transactions[2] <== batch1_txs[2];
    v1.transactions[3] <== batch1_txs[3];
    v1.expectedRoot <== root1;
    
    component and = AND();
    and.a <== v0.valid;
    and.b <== v1.valid;
    
    valid <== and.out;
}

component main = RecursiveVerify2();
