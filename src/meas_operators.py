# Hermitian measurement operators

import numpy as np

##############################################################################
# 1 - Q U B I T  S Y S T E M
##############################################################################

# Standard basis
M_S1 = np.array([[0, 0],
                 [0, 1]])

# Hadamard basis
M_H1 = 0.5 * np.array([[ 1, -1],
                       [-1,  1]])


##############################################################################
# 2 - Q U B I T  S Y S T E M
##############################################################################

# MEASURE THE LEFT QUBIT

# Standard basis
M_S2_1 = np.array([[0, 0, 0, 0],
                   [0, 0, 0, 0],
                   [0, 0, 1, 0],
                   [0, 0, 0, 1]])

# Hadamard basis
M_H2_1 = 0.5 * np.array([[ 1,  0, -1,  0],
                         [ 0,  1,  0, -1],
                         [-1,  0,  1,  0],
                         [ 0, -1,  0,  1]])


# MEASURE THE RIGHT QUBIT

# Standard basis
M_S2_0 = np.array([[0, 0, 0, 0],
                   [0, 1, 0, 0],
                   [0, 0, 0, 0],
                   [0, 0, 0, 1]])

# Hadamard basis
M_H2_0 = 0.5 * np.array([[ 1, -1,  0,  0],
                         [-1,  1,  0,  0],
                         [ 0,  0,  1, -1],
                         [ 0,  0, -1,  1]])