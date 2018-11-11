from math import pi, sin, cos

from consts import (
    EQUIPMENT_STRS,
    PHOTONSRC,
    SPS,
    POLARISER,
    PHOTONDETECTOR,
    POLARIMETER,
    CCHL,
    QCHL
)

import environment
import system

def initialise_system():

    user_specs = {
        "Alice": {SPS: {"out": [POLARISER]},
                  POLARISER: {"in": [SPS], "out": [QCHL]}},
        "Bob":   {PHOTONDETECTOR: {"in": [QCHL], "out": [POLARIMETER]},
                  POLARIMETER: {"in": [PHOTONDETECTOR]}}
    }

    chl_specs = {
        CCHL:  {"in": ["Alice", "Bob"], "out": ["Alice", "Bob"]},
        QCHL:  {"in": ["Alice", "Bob"], "out": ["Alice", "Bob"]}
    }

    env = environment.Environment()
    sys = system.System(env, user_specs, chl_specs)
    return sys

def send_photons(sys):

    def send_polarised_photons(alice, bob):
        # Orientations are degrees anticlockwise from horizontal axis
        print("\n~ Alice: STANDARD BASIS ~\n")
        alice.send_polarised_photon(pi/2)  # Send bit 0 in std basis
        print(" ")
        alice.send_polarised_photon(0)     # Send bit 1 in std basis

        print("\n\n~ Alice: HADAMARD BASIS ~\n")
        alice.send_polarised_photon(pi/4)    # Send bit 0 in Hadamard basis
        print(" ")
        alice.send_polarised_photon(3*pi/4)  # Send bit 1 in Hadamard basis

    alice = sys.users["Alice"]
    bob = sys.users["Bob"]
    # qchl = sys.channels[QCHL]

    bob.start_detecting_photons()
    bob.start_measuring_photons()

    # Measure w.r.t. standard basis
    print("-"*20)
    print("Bob: STANDARD BASIS")
    print("-"*20)
    bob.components[POLARIMETER].set_basis = (0, pi/2)
    send_polarised_photons(alice, bob)
