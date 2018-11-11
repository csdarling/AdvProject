#!/bin/python3

import logging
from math import sin, cos, pi

from equipment import (
    PhotonSource,
    Polariser,
    PhotonDetector,
    PhotonMeasurementDevice
)

from user import PhotonSender, PhotonReceiver
from channel import QuantumChannel

def send_polarised_photons(alice, bob, q_chl):

    photon_path = [
        alice.components["SPS"],
        alice.components["Polariser"],
        q_chl,
        bob.components["PhotonDetector"],
        bob.components["PhotonMeasurement"]
    ]

    # Orientations are degrees anticlockwise from horizontal axis
    print("\n~ Alice: STANDARD BASIS ~\n")
    alice.send_polarised_photon(pi/2,   photon_path)  # Send bit 0 in std basis
    print(" ")
    alice.send_polarised_photon(0,      photon_path)  # Send bit 1 in std basis

    print("\n\n~ Alice: HADAMARD BASIS ~\n")
    alice.send_polarised_photon(pi/4,   photon_path)  # Send bit 0 in Hadamard basis
    print(" ")
    alice.send_polarised_photon(3*pi/4, photon_path)  # Send bit 1 in Hadamard basis

def main():
    alice = PhotonSender(name="Alice")
    bob = PhotonReceiver(name="Bob")
    q_chl = QuantumChannel([alice, bob])

    bob.start_detecting_photons()
    bob.start_measuring_photons()

    # Measure w.r.t. standard basis
    print("-"*20)
    print("Bob: STANDARD BASIS")
    print("-"*20)
    bob.components["PhotonMeasurement"].set_basis = (0, pi/2)
    send_polarised_photons(alice, bob, q_chl)

    # Measure w.r.t. Hadamard basis
    print("-"*20)
    print("Bob: HADAMARD BASIS")
    print("-"*20)
    bob.components["PhotonMeasurement"].set_basis = (pi/4, 3*pi/4)
    send_polarised_photons(alice, bob, q_chl)

    bob.stop_detecting_photons()
    bob.stop_measuring_photons()

if __name__ == '__main__':
    main()
