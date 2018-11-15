#!/bin/python3

import threading
import random
import numpy as np
from math import cos, sin, pi, floor, isclose

class Photon:

    def __init__(self, destination, uid):
        self.uid = uid
        self._destination = destination
        self._polarisation_axis = None
        self._progress()

    def _progress(self):
        self._destination, progress = self._destination.handle_photon(self)
        if progress:
            self._progress()

    def polarise(self, theta):

        if self._polarisation_axis is None:
            self._polarisation_axis = theta

        else:
            # phton_state = sin(theta)|0> + cos(theta)|1>
            # basis_state =   sin(phi)|0> +   cos(phi)|1>
            # bdual_state =   cos(phi)|0> -   sin(phi)|1>
            phi = theta
            theta = self._polarisation_axis

            phi_perp = phi + pi/2
            phi_perp -= 2 * pi * floor(phi_perp / (2 * pi))
            results = [phi, phi_perp]

            coeffs = [sin(theta) * sin(phi) + cos(theta) * cos(phi),
                      sin(theta) * cos(phi) - cos(theta) * sin(phi)]
            prob_distr = [coeff ** 2 for coeff in coeffs]

            idx = np.random.choice(2, 1, p=prob_distr)[0]
            self._polarisation_axis = results[idx]

        return self._polarisation_axis

