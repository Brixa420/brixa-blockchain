pragma circom 2.0.0;

include "poseidon.circom";
include "comparators.circom";

template HashLeftRight() {
    signal input left;
    signal input right;
    signal output hash;
    component hasher = Poseidon(2);
    hasher.inputs[0] <== left;
    hasher.inputs[1] <== right;
    hash <== hasher.out;
}

template BatchMerkleVerify16() {
    signal input transactions[16];
    signal input expectedRoot;
    signal output valid;

    component h0 = HashLeftRight(); h0.left <== transactions[0]; h0.right <== transactions[1];
    component h1 = HashLeftRight(); h1.left <== transactions[2]; h1.right <== transactions[3];
    component h2 = HashLeftRight(); h2.left <== transactions[4]; h2.right <== transactions[5];
    component h3 = HashLeftRight(); h3.left <== transactions[6]; h3.right <== transactions[7];
    component h4 = HashLeftRight(); h4.left <== transactions[8]; h4.right <== transactions[9];
    component h5 = HashLeftRight(); h5.left <== transactions[10]; h5.right <== transactions[11];
    component h6 = HashLeftRight(); h6.left <== transactions[12]; h6.right <== transactions[13];
    component h7 = HashLeftRight(); h7.left <== transactions[14]; h7.right <== transactions[15];

    component h8 = HashLeftRight(); h8.left <== h0.hash; h8.right <== h1.hash;
    component h9 = HashLeftRight(); h9.left <== h2.hash; h9.right <== h3.hash;
    component h10 = HashLeftRight(); h10.left <== h4.hash; h10.right <== h5.hash;
    component h11 = HashLeftRight(); h11.left <== h6.hash; h11.right <== h7.hash;

    component h12 = HashLeftRight(); h12.left <== h8.hash; h12.right <== h9.hash;
    component h13 = HashLeftRight(); h13.left <== h10.hash; h13.right <== h11.hash;

    component h14 = HashLeftRight(); h14.left <== h12.hash; h14.right <== h13.hash;

    component rootCheck = IsZero();
    rootCheck.in <== h14.hash - expectedRoot;
    valid <== rootCheck.out;
}

component main = BatchMerkleVerify16();
