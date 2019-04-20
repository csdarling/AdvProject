import numpy as np
import consts

def get_measurement_operator(eigenvalues, eigenvectors):
    '''
    Find the measurement operator with the given eigenvalues and eigenvectors.

    Example inputs:
        eigenvalues  = [0, 1, 2, 3]
        eigenvectors = [[1,0,0,0], [0,1,0,0], [0,0,0,0], [0,0,0,0]]
    '''
    D = np.diag(eigenvalues)
    V = np.array(eigenvectors).T
    M = V @ D @ np.linalg.inv(V)  # M = V D V_inv

    return M

def append_to_dol(dict_of_lists, key, new_val):
    if key not in dict_of_lists:
        dict_of_lists[key] = []

    dict_of_lists[key].append(new_val)

def convert_list_to_string(lst):
    list_of_strs = [str(val) for val in lst]
    return "".join(list_of_strs)

def convert_dol_to_dos(dol):
    '''Convert a dict of lists to a dict of strings.'''
    dos = {}
    for uid in dol:
        dos[uid] = convert_list_to_string(dol[uid])

    return dos

def convert_dod_to_dol(dod):
    '''Convert a dict of dicts to a dict of lists.'''
    dol = {}
    for uid in dod:
        dol[uid] = []
        for timestep in sorted(dod[uid]):
            val = dod[uid][timestep]
            while timestep > len(dol[uid]):
                dol[uid].append(' ')
            dol[uid].append(val)

    return dol

def convert_dod_to_dos(dod):
    '''Convert a dict of dicts to a dict of strings.'''
    dol = convert_dod_to_dol(dod)
    dos = convert_dol_to_dos(dol)
    return dos

def reorder_by_uid(by_timestep):
    '''
    Take a dictionary of the format {timestep: {uid: value, ...}, ...};
    return a dictionary with format {uid: {timestep: value, ...}, ...}.
    '''
    by_uid = {}
    for timestep in by_timestep:
        for uid in by_timestep[timestep]:
            if uid not in by_uid:
                by_uid[uid] = {}
            by_uid[uid][timestep] = by_timestep[timestep][uid]

    return by_uid

def represent_bases_by_chars(bases):
    '''Convert a (dict of dicts of np.arrays) to a (dict of dicts of chars).

    {uid: {timestep: np.array, ...}, ...} --> {uid: {timestep: 'H', ...}, ...}
    '''
    basis_chars = {}
    for uid in bases:
        basis_chars[uid] = {}
        for timestep in bases[uid]:
            basis = bases[uid][timestep]
            basis_char = '?'
            if np.allclose(basis, consts.STANDARD_BASIS):
                basis_char = 'S'
            elif np.allclose(basis, consts.HADAMARD_BASIS):
                basis_char = 'H'
            basis_chars[uid][timestep] = basis_char

    return basis_chars

def add_spaces_to_bitstring(bitstr, idxs, str_len):
    padded_bitstr = ""
    i = 0

    for count in range(str_len):
        if count in idxs:
            padded_bitstr += bitstr[i]
            i += 1
        else:
            padded_bitstr += " "

    return padded_bitstr
