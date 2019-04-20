import numpy as np

def calculate_meas_op(e_vals, e_vecs):
    # e_vals = [0,1,2,3]
    # e_vecs = [[1,0,0,0], [0,1,0,0], [0,0,0,0], [0,0,0,0]]

    D = np.diag(e_vals)
    V = np.array(e_vecs).T
    M = V @ D @ np.linalg.inv(V)  # M = V D V_inv

    return M
