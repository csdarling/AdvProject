def bb84(alice, bob):

    str_len = 16

    # Alice constructs a string of random bits and a sequence of random bases.
    alice.bits = alice.generate_random_bits(str_len)
    alice.bases = alice.generate_random_bases(str_len)

    # bob.set_qreceiving(True)  # Do this outside of the protocol

    # Alice sends Bob the corresponding qubits over the quantum channel.
    alice.q_transmit(alice.bits, alice.bases, bob)  # Make this blocking?
    alice.transmit(END, bob, require_response=True)  # Re-transmit if no response

    # Alice and Bob determine which photons were successfully received.
    bob.transmit(bob.timestamps, alice)
    alice.update_bases()

    # Alice and Bob discuss publically compare their bases.
    alice.transmit(alice.bases, bob)
    bob.transmit(bob.bases, alice)

