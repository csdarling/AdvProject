from math import pi, sin, cos
import multiprocessing as mp
import time

from consts import *
import environment
import system
import equipment

def initialise_system():

    user_specs = {
        "Alice": {#BB84: {"in": [CCHL], "out": [CCHL]},
                  SPS: {"out": [POLARISER]},
                  POLARISER: {"in": [SPS], "out": [QCHL]}},
        "Bob":   {#BB84: {"in": [CCHL], "out": [CCHL]},
                  POLARIMETER: {"in": [QCHL]}}
    }

    chl_specs = {
        # CCHL:  {"in" : [("Alice", BB84), ("Bob", BB84)],
        #         "out": [("Alice", BB84), ("Bob", BB84)]},
        QCHL:  {"in" : [("Alice", POLARISER)],
                "out": [("Bob", POLARIMETER)]}
    }

    env = environment.Environment()
    sys = system.System(env, user_specs, chl_specs)
    return sys

def send_photons(sys):

    def send_polarised_photons(alice, bob):
        # Orientations are degrees anticlockwise from horizontal axis
        print("\n~ Alice: STANDARD BASIS ~\n")
        alice.send_polarised_photon(pi/2)  # Send bit 0 in std basis
        # bob.read_measurement()
        print(" ")
        alice.send_polarised_photon(0)     # Send bit 1 in std basis
        # bob.read_measurement()

        print("\n\n~ Alice: HADAMARD BASIS ~\n")
        alice.send_polarised_photon(pi/4)    # Send bit 0 in Hadamard basis
        # bob.read_measurement()
        print(" ")
        alice.send_polarised_photon(3*pi/4)  # Send bit 1 in Hadamard basis
        # bob.read_measurement()

    alice = sys.users["Alice"]
    bob = sys.users["Bob"]
    # qchl = sys.channels[QCHL]

    # bob.start_detecting_photons()
    # bob.start_measuring_photons()

    # Measure w.r.t. standard basis
    print("-"*20)
    print("Bob: STANDARD BASIS")
    print("-"*20)
    bob.components[POLARIMETER].set_basis = (pi/2, 0)
    send_polarised_photons(alice, bob)

def run_bb84():
    env = environment.Environment()
    sys = system.System(env)
    alice = sys.add_device("Alice", PHOTONDEVICE)
    bob = sys.add_device("Bob", PHOTONDEVICE)

    sys.start_listening(alice, bob)  # alice.start_listening(bob)
    sys.start_listening(bob, alice)  # bob.start_listenting(alice)
    sys.connect_devices_via_qchl(alice, bob)

    sys.run_bb84(alice, bob)
    time.sleep(1)

    # sys.send_photons(alice, 1.0)  # alice.send_photons(bob, 1.0)
    # sys.send_photons(bob, 0.8)    # bob.send_photons(alice, 0.8)
    # time.sleep(3)

    # sys.send_n_photons(alice, 1, 1.0)
    # sys.stop_sending_photons(alice)
    # sys.send_message(alice, (bob, MSG_STOP_SENDING_PHOTONS, alice))
    # time.sleep(3)

def main():
    # sys = initialise_system()
    # send_photons(sys)
    run_bb84(sys)

if __name__ == '__main__':
    main()

